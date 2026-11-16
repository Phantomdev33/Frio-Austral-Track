import json
import uuid
from datetime import timedelta
from types import SimpleNamespace
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Profile, Truck, Trip, Delivery, Reading, Receipt, Incident
from .services import thermal_status, evaluate_trip

class ThermalRulesTests(TestCase):
    def status(self, values, step=5):
        now=timezone.now()
        return thermal_status([SimpleNamespace(temperature=v,captured_at=now+timedelta(minutes=i*step)) for i,v in enumerate(values)])
    def test_normal_range_is_inclusive(self):
        self.assertEqual(self.status([-22,-18])['status'],'normal')
    def test_exact_threshold_does_not_start_timer(self):
        self.assertEqual(self.status([-15]*5)['status'],'watch')
        self.assertEqual(self.status([-15]*5)['minutes'],0)
    def test_critical_requires_fifteen_minutes(self):
        self.assertEqual(self.status([-14]*3)['status'],'watch')
        self.assertEqual(self.status([-14]*4)['status'],'watch')
        self.assertEqual(self.status([-14]*5)['status'],'critical')
    def test_recovery_resets_episode(self):
        self.assertEqual(self.status([-14,-14,-15,-14])['minutes'],0)
    def test_rupture_is_strictly_more_than_fifteen_minutes(self):
        self.assertEqual(self.status([-11]*4)['status'],'watch')
        self.assertEqual(self.status([-11]*5)['status'],'rupture')
        self.assertEqual(self.status([-12]*5)['status'],'critical')
    def test_each_threshold_has_its_own_timer(self):
        state=self.status([-14,-14,-11,-11,-11])
        self.assertEqual(state['status'],'critical')
        self.assertEqual(state['rupture_minutes'],10)
    def test_out_of_order_sync_uses_capture_time(self):
        now=timezone.now()
        rows=[SimpleNamespace(temperature=-14,captured_at=now+timedelta(minutes=i)) for i in [20,0,5,10,15]]
        self.assertEqual(thermal_status(rows)['status'],'critical')

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class WorkflowTests(TestCase):
    def setUp(self):
        self.driver=User.objects.create_user('driver',password='pass')
        Profile.objects.create(user=self.driver,role='driver')
        self.manager=User.objects.create_user('manager',password='pass')
        Profile.objects.create(user=self.manager,role='manager')
        self.customer=User.objects.create_user('client',password='pass',email='client@example.test')
        Profile.objects.create(user=self.customer,role='client')
        self.truck=Truck.objects.create(code='FA-018',plate='LXRD42',branch='Castro',driver=self.driver)
        self.trip=Trip.objects.create(truck=self.truck,date=timezone.localdate())
        self.delivery=Delivery.objects.create(trip=self.trip,client=self.customer,customer='Bordemar',address='Castro',window='11:00',cargo='Salmón',guide='123')
    def test_role_access(self):
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get('/operaciones/').status_code,403)
        self.assertEqual(self.client.get('/conductor/').status_code,200)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get('/api/estado/').status_code,403)
    def test_rejection_reason_required_and_retry_is_idempotent(self):
        self.client.force_login(self.driver)
        payload={'delivery_id':self.delivery.pk,'event_id':str(uuid.uuid4()),'state':'rejected'}
        self.assertEqual(self.client.post('/api/entrega/',payload).status_code,400)
        payload['reason']='Embalaje dañado'
        self.assertEqual(self.client.post('/api/entrega/',payload).status_code,200)
        self.assertEqual(self.client.post('/api/entrega/',payload).status_code,200)
        self.assertEqual(Receipt.objects.count(),1)
        self.delivery.refresh_from_db(); self.assertEqual(self.delivery.rejection_reason,'Embalaje dañado')
    def test_readings_and_alerts_are_idempotent(self):
        self.client.force_login(self.driver)
        now=timezone.now()
        for minutes in [20,15,10,5,0]:
            payload={'trip_id':self.trip.pk,'event_id':str(uuid.uuid4()),'temperature':-14,'captured_at':(now-timedelta(minutes=minutes)).isoformat()}
            for _ in range(2): self.assertEqual(self.client.post('/api/lecturas/',json.dumps(payload),content_type='application/json').status_code,200)
        self.assertEqual(Reading.objects.count(),5)
        self.assertEqual(self.trip.alerts.count(),1)
        from django.core import mail
        self.assertEqual(len(mail.outbox),1)
    def test_foreign_route_cannot_be_modified(self):
        other=User.objects.create_user('other');Profile.objects.create(user=other,role='driver');self.client.force_login(other)
        self.assertEqual(self.client.post('/api/entrega/',{'delivery_id':self.delivery.pk,'state':'rejected','reason':'x','event_id':str(uuid.uuid4())}).status_code,404)
    def test_incident_retry(self):
        self.client.force_login(self.driver)
        payload={'truck_id':self.truck.pk,'description':'Falla de refrigeración','event_id':str(uuid.uuid4()),'assistance':True}
        for _ in range(2): self.assertEqual(self.client.post('/api/incidencia/',json.dumps(payload),content_type='application/json').status_code,200)
        self.assertEqual(Incident.objects.count(),1)
    def test_csrf_required(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.driver)
        self.assertEqual(client.post('/api/simulador/',json.dumps({'scenario':'normal'}),content_type='application/json').status_code,403)
    def test_delivery_generates_pdf_and_email_once(self):
        self.client.force_login(self.driver)
        Reading.objects.create(trip=self.trip,temperature=-20,captured_at=timezone.now())
        payload={'delivery_id':self.delivery.pk,'event_id':str(uuid.uuid4()),'state':'delivered'}
        for _ in range(2): self.assertEqual(self.client.post('/api/entrega/',payload).status_code,200)
        response=self.client.get(f'/certificado/{self.delivery.pk}/')
        self.assertEqual(response.status_code,200);self.assertTrue(response.content.startswith(b'%PDF'))
        from django.core import mail
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(len(mail.outbox[0].attachments),1)
    def test_other_client_cannot_download_certificate(self):
        self.delivery.state='delivered';self.delivery.completed_at=timezone.now();self.delivery.save()
        other=User.objects.create_user('otherclient');Profile.objects.create(user=other,role='client');self.client.force_login(other)
        self.assertEqual(self.client.get(f'/certificado/{self.delivery.pk}/').status_code,403)
