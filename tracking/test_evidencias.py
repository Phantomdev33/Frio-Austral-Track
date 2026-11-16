"""Escenarios reproducibles de Actividad 3; sin modificar la base de demostracion."""
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from core.thermal import thermal_status
from offline_agent.store import LocalStore
from .models import Profile, Reading, Trip, Truck


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EvidenciasActividad3Tests(TestCase):
    def setUp(self):
        driver = User.objects.create_user('evidencia_conductor')
        Profile.objects.create(user=driver, role='driver')
        truck = Truck.objects.create(code='EV-001', plate='EV0001', branch='Castro', driver=driver)
        self.trip = Trip.objects.create(truck=truck, date=timezone.localdate())
        self.client.force_login(driver)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cola.sqlite3'
        self.key = AESGCM.generate_key(bit_length=256)
        self.store = LocalStore(self.path, self.key, driver.username)
        self.addCleanup(lambda: self.store.close())
        self.start = timezone.now() - timedelta(minutes=50)
        self.responses = []

    def send(self, rows):
        response = self.client.post('/api/v1/lecturas/lote/', json.dumps({'readings': rows}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.responses.append(result)
        return result

    def capture(self, minutes, temperature=-20):
        return self.store.capture(self.trip.pk, temperature, self.start + timedelta(minutes=minutes))

    def evidence(self, number, title, lines):
        print('EVIDENCIA_JSON:' + json.dumps({'number': number, 'title': title, 'lines': lines, 'result': 'APROBADO'}, ensure_ascii=True), flush=True)

    def test_01_sincronizacion_tras_desconexion(self):
        for minute in [0, 5, 10]:
            self.capture(minute)
        def offline(rows):
            raise ConnectionError('Desconexion simulada')
        with self.assertRaises(ConnectionError):
            self.store.sync(offline)
        self.assertEqual(len(self.store.rows(pending_only=True)), 3)
        self.assertEqual(Reading.objects.count(), 0)
        self.store.close()
        self.store = LocalStore(self.path, self.key, 'evidencia_conductor')
        self.assertEqual(len(self.store.rows(pending_only=True)), 3)
        self.assertEqual(self.store.sync(self.send), 3)
        self.assertEqual(len(self.store.rows(pending_only=True)), 0)
        self.assertEqual(Reading.objects.count(), 3)
        self.evidence('01', 'Sincronizacion tras desconexion', [
            'Sin red simulada: 3 lecturas pendientes en SQLite; servidor: 0.',
            'Tras cerrar y reabrir SQLite: se conservan las 3 pendientes.',
            'Conexion recuperada: POST a la API Django -> HTTP 200, 3 ACK.',
            'Resultado: pendientes = 0; lecturas en servidor = 3.'])

    def test_02_reintento_sin_duplicados(self):
        original = self.capture(0)
        def lost_ack(rows):
            self.send(rows)
            raise TimeoutError('ACK perdido despues de guardar en servidor')
        with self.assertRaises(TimeoutError):
            self.store.sync(lost_ack)
        self.assertEqual(Reading.objects.count(), 1)
        self.assertEqual(len(self.store.rows(pending_only=True)), 1)
        self.assertEqual(self.store.sync(self.send), 1)
        self.assertEqual(Reading.objects.count(), 1)
        self.assertEqual(self.responses[0]['acknowledged'], self.responses[1]['acknowledged'])
        self.assertEqual(str(Reading.objects.get().event_id), original['event_id'])
        self.assertEqual(len(self.store.rows(pending_only=True)), 0)
        self.assertEqual(self.store.rows()[0]['attempts'], 2)
        self.evidence('02', 'Reintento sin duplicados', [
            'Primer envio: API guarda 1 lectura; se simula perdida del ACK.',
            'Cliente conserva 1 pendiente; servidor ya contiene 1 lectura.',
            'Segundo envio: mismo UUID, HTTP 200 y mismo ACK.',
            'Resultado: 2 intentos; 1 lectura en servidor; 0 pendientes.',
            'Duplicados = 0; identidad del UUID comprobada.'])

    def test_03_limite_de_quince_minutos(self):
        for minute in [0, 5, 10, 15]:
            self.capture(minute, -14)
        before = self.store.local_status(self.trip.pk)
        self.assertEqual(before['status'], 'watch')
        self.assertEqual(before['minutes'], 15)
        self.store.sync(self.send)
        self.assertEqual(self.trip.alerts.count(), 0)
        self.capture(20, -14)
        after = self.store.local_status(self.trip.pk)
        self.assertEqual(after['status'], 'critical')
        self.assertEqual(after['minutes'], 20)
        self.store.sync(self.send)
        self.assertEqual(self.trip.alerts.filter(kind='critical', superseded=False).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.evidence('03', 'Limite temporal de la alerta critica', [
            'Temperatura simulada: -14 C (mayor que -15 C).',
            'Capturas en minutos 0, 5, 10 y 15: vigilancia; alertas = 0.',
            'Captura en minuto 20: estado local = critical; duracion = 20 min.',
            'Tras sincronizar: 1 alerta critica y 1 correo en memoria.',
            'Regla: mas de 15 minutos; exactamente 15 NO activa alerta.',
            'Tiempo simulado por hora de captura; no se espero 20 min reales.'])

    def test_04_lote_tardio_recuperado(self):
        for minute in [0, 5, 10, 15, 20]:
            self.capture(minute, -14)
        self.capture(25, -20)
        self.assertEqual(Reading.objects.count(), 0)
        self.assertEqual(self.store.local_status(self.trip.pk)['status'], 'normal')
        def reversed_batch(rows):
            return self.send(list(reversed(rows)))
        self.assertEqual(self.store.sync(reversed_batch), 6)
        state = thermal_status(self.trip.readings.all())
        self.assertEqual(state['status'], 'normal')
        alert = self.trip.alerts.get(kind='critical', superseded=False)
        self.assertEqual(alert.started_at, self.start)
        self.assertEqual(alert.triggered_at, self.start + timedelta(minutes=20))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Reading.objects.count(), 6)
        self.evidence('04', 'Lote tardio con recuperacion final', [
            'Sin envio: 5 muestras a -14 C (0..20 min) y 1 a -20 C (25 min).',
            'API recibe las 6 muestras juntas, en orden invertido: HTTP 200.',
            'Estado final = normal; lecturas almacenadas = 6.',
            'Se conserva 1 episodio critico historico, disparado en minuto 20.',
            'Se genera 1 correo en memoria pese a la recuperacion final.',
            'Calculo por hora de captura, no por orden de llegada.'])
