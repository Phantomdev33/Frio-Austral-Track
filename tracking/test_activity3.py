import json
import uuid
from datetime import timedelta
from django.db import connection
from django.test import override_settings, TestCase
from django.utils import timezone
from . import tests as fixtures
from .models import Trip, Reading, Truck

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class Activity3Tests(TestCase):
    setUp = fixtures.WorkflowTests.setUp
    def payload(self,trip=None):
        return {'trip_id':(trip or self.trip).pk,'event_id':str(uuid.uuid4()),'temperature':-20.25,'captured_at':timezone.now().isoformat()}
    def post(self,rows):
        self.client.force_login(self.driver)
        return self.client.post('/api/v1/lecturas/lote/',json.dumps({'readings':rows}),content_type='application/json')
    def test_batch_ack_and_retries(self):
        rows=[self.payload(),self.payload()]
        for _ in range(2):
            r=self.post(rows)
            self.assertEqual(r.status_code,200)
            self.assertEqual(set(r.json()['acknowledged']),{x['event_id'] for x in rows})
        self.assertEqual(Reading.objects.count(),2)
    def test_other_driver_batch_rejected(self):
        self.truck.driver=self.manager;self.truck.save()
        self.assertEqual(self.post([self.payload()]).status_code,404)
        self.assertEqual(Reading.objects.count(),0)
    def test_client_cannot_ingest(self):
        self.client.force_login(self.customer)
        r=self.client.post('/api/v1/lecturas/lote/',json.dumps({'readings':[self.payload()]}),content_type='application/json')
        self.assertEqual(r.status_code,403)
    def test_media_is_not_public(self):
        self.assertEqual(self.client.get('/media/entregas/photo.png').status_code,404)
        self.assertEqual(self.client.get(f'/foto/{self.delivery.pk}/').status_code,302)
    @override_settings(DEBUG=False)
    def test_simulator_not_available_in_production(self):
        self.client.force_login(self.driver)
        r=self.client.post('/api/simulador/',json.dumps({'scenario':'critical'}),content_type='application/json')
        self.assertEqual(r.status_code,403)
    def test_changed_uuid_is_conflict(self):
        row=self.payload();self.assertEqual(self.post([row]).status_code,200)
        row['temperature']=-10
        self.assertEqual(self.post([row]).status_code,409)
        self.assertEqual(Reading.objects.get().temperature,-20.25)
    def test_batch_rollback_on_late_conflict(self):
        old=self.payload();self.post([old]);old['temperature']=-10
        self.assertEqual(self.post([self.payload(),old]).status_code,409)
        self.assertEqual(Reading.objects.count(),1)
    def test_invalid_batch_is_atomic(self):
        valid=self.payload();invalid=self.payload();invalid['temperature']="0); DROP TABLE tracking_reading;--"
        self.assertEqual(self.post([valid,invalid]).status_code,400)
        self.assertEqual(Reading.objects.count(),0)
    def test_today_only_and_historical_deferred_ingestion(self):
        old=Trip.objects.create(truck=self.truck,date=timezone.localdate()-timedelta(days=1))
        self.client.force_login(self.driver)
        result=self.client.get('/api/estado/').json()
        self.assertEqual([t['id'] for t in result['trips']],[self.trip.pk])
        row=self.payload(old);row['captured_at']=(timezone.now()-timedelta(days=1)).isoformat()
        self.assertEqual(self.post([row]).status_code,200)
    def test_locations_encrypted_at_rest(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT latitude,longitude FROM tracking_truck WHERE id=%s',[self.truck.id])
            lat,lng=cursor.fetchone()
        self.assertTrue(lat.startswith('aesgcm:v1:'));self.assertTrue(lng.startswith('aesgcm:v1:'))
        truck=Truck.objects.get(pk=self.truck.pk)
        self.assertAlmostEqual(truck.latitude,-42.48)
        self.assertAlmostEqual(truck.longitude,-73.76)
    def test_password_is_hashed(self):
        self.assertNotEqual(self.driver.password,'pass')
        self.assertTrue(self.driver.check_password('pass'))
    def test_recovery_at_end_of_delayed_batch_preserves_alert(self):
        now=timezone.now();rows=[]
        for minutes in [25,20,15,10,5,0]:
            row=self.payload();row['captured_at']=(now-timedelta(minutes=minutes)).isoformat();row['temperature']=-20 if minutes==0 else -14;rows.append(row)
        self.assertEqual(self.post(list(reversed(rows))).status_code,200)
        self.assertEqual(self.trip.alerts.filter(kind='critical').count(),1)
        from django.core import mail
        self.assertEqual(len(mail.outbox),1)
