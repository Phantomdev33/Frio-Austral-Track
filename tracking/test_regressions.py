import uuid
from datetime import timedelta
from types import SimpleNamespace
from django.test import SimpleTestCase,TestCase,override_settings
from django.utils import timezone
from django.core import mail
from core.thermal import thermal_status,thermal_events
from .models import Reading,Alert,Receipt,Trip
from .services import evaluate_trip
from . import tests as fixtures

class SampleContinuityTests(SimpleTestCase):
    def samples(self,minutes,temperature=-14):
        start=timezone.now()-timedelta(hours=3)
        return [SimpleNamespace(temperature=temperature,captured_at=start+timedelta(minutes=m)) for m in minutes]
    def test_hot_endpoints_preserve_excursion_across_gap(self):
        for temperature, expected in [(-14, 'critical'), (-11, 'rupture')]:
            rows=self.samples([0,5,485],temperature)
            status=thermal_status(rows)
            self.assertEqual(status['status'],expected)
            self.assertEqual(status['minutes'],485)
            self.assertEqual(status['telemetry_gaps'],1)
            self.assertEqual(status['gaps'],1)
            events=list(thermal_events(rows))
            self.assertEqual(len(events),1 if temperature == -14 else 2)
            self.assertEqual(events[0]['started_at'],rows[0].captured_at)
            self.assertEqual(events[0]['captured_at'],rows[-1].captured_at)
            self.assertEqual(events[0]['temperature'],temperature)
    def test_recovery_after_gap_resets_timers(self):
        rows=self.samples([0,5]) + self.samples([485],-20)
        status=thermal_status(rows)
        self.assertEqual(status['status'],'normal')
        self.assertEqual(status['minutes'],0)
        self.assertEqual(status['telemetry_gaps'],1)
        self.assertEqual(list(thermal_events(rows)),[])
    def test_silence_only_advances_with_explicit_now(self):
        for temperature, expected in [(-14,'critical'),(-11,'rupture')]:
            rows=self.samples([0,5],temperature)
            self.assertEqual(thermal_status(rows)['status'],'watch')
            self.assertEqual(thermal_status(rows,now=rows[0].captured_at+timedelta(minutes=40))['status'],expected)
            self.assertEqual(thermal_status(rows,now=rows[0].captured_at)['minutes'],5)
            self.assertEqual(list(thermal_events(rows)),[])
    def test_gap_preserves_each_threshold_independently(self):
        rows=self.samples([0,5],-11)+self.samples([30],-14)
        status=thermal_status(rows)
        self.assertEqual(status['status'],'critical')
        self.assertEqual(status['minutes'],30)
        self.assertEqual(status['rupture_minutes'],0)
    def test_six_minutes_tolerance_is_inclusive(self):
        self.assertEqual(thermal_status(self.samples([0,6,12,18]))['telemetry_gaps'],0)
        self.assertEqual(thermal_status(self.samples([0,6.01,12.02,18.03]))['telemetry_gaps'],3)
    def test_empty_readings_include_gap_counters(self):
        status=thermal_status([])
        self.assertEqual(status['gaps'],0)
        self.assertEqual(status['telemetry_gaps'],0)
    def test_recovered_final_sample_does_not_erase_previous_confirmed_episode(self):
        rows=self.samples([0,5,10,15,20]);rows.append(SimpleNamespace(temperature=-20,captured_at=rows[-1].captured_at+timedelta(minutes=5)))
        self.assertEqual(thermal_status(rows)['status'],'normal');self.assertEqual(len(list(thermal_events(rows))),1)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LateReadingRegressionTests(TestCase):
    setUp=fixtures.WorkflowTests.setUp
    def add(self,minutes,temperature=-14):
        start=timezone.now().replace(microsecond=0)-timedelta(hours=3)
        # Mantener la misma fecha de referencia al incorporar muestras anteriores en cada prueba.
        if not hasattr(self,'epoch'): self.epoch=start
        for minute in minutes: Reading.objects.create(trip=self.trip,temperature=temperature,captured_at=self.epoch+timedelta(minutes=minute))
    def test_earlier_samples_do_not_duplicate_alert_or_mail(self):
        self.add([10,15,20,25,30]);evaluate_trip(self.trip)
        alert=self.trip.alerts.get();alert.acknowledged=True;alert.save()
        self.add([0,5]);evaluate_trip(self.trip);evaluate_trip(self.trip)
        self.assertEqual(self.trip.alerts.count(),1);self.assertEqual(len(mail.outbox),1)
        alert.refresh_from_db();self.assertTrue(alert.acknowledged);self.assertFalse(alert.superseded)
    def test_merging_episodes_does_not_send_another_notification(self):
        self.add([0,5,10,15,20,40,45,50,55,60]);evaluate_trip(self.trip)
        self.assertEqual(len(mail.outbox),1)
        self.add([25,30,35]);evaluate_trip(self.trip)
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(self.trip.alerts.filter(superseded=False).count(),1)
        self.assertEqual(self.trip.alerts.filter(superseded=True).count(),0)
    def test_new_anomaly_after_recovery_still_notifies(self):
        self.add([0,5,10,15,20]);evaluate_trip(self.trip)
        self.add([25],-20);self.add([30,35,40,45,50]);evaluate_trip(self.trip)
        self.assertEqual(self.trip.alerts.filter(superseded=False).count(),2)
        self.assertEqual(len(mail.outbox),2)
    def test_late_recovery_supersedes_unconfirmed_old_alert(self):
        self.add([0,5,10,15,20]);evaluate_trip(self.trip)
        self.add([12],-20);evaluate_trip(self.trip)
        self.assertEqual(self.trip.alerts.filter(superseded=False).count(),0)
        self.assertEqual(self.trip.alerts.filter(superseded=True).count(),1)
        self.assertEqual(len(mail.outbox),1)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/api/estado/').json()['alerts'],[])
    def test_legacy_alert_is_reused_and_invalid_gap_alert_hidden(self):
        self.add([10,15,20,25,30])
        old=Alert.objects.create(trip=self.trip,kind='critical',started_at=self.epoch+timedelta(minutes=10),emailed=True)
        self.add([0,5]);evaluate_trip(self.trip)
        old.refresh_from_db();self.assertFalse(old.superseded)
        self.assertEqual(self.trip.alerts.count(),1)
    def test_no_notify_reconciliation_does_not_send_mail(self):
        self.add([0,5,10,15,20]);evaluate_trip(self.trip,notify=False)
        self.assertEqual(len(getattr(mail,'outbox',[])),0)
        self.assertFalse(self.trip.alerts.get().emailed)
        evaluate_trip(self.trip);self.assertEqual(len(mail.outbox),1)

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class HistoricalDeliveryRegressionTests(TestCase):
    setUp=fixtures.WorkflowTests.setUp
    def post(self,**extra):
        self.client.force_login(self.driver)
        payload={'delivery_id':self.delivery.pk,'event_id':str(uuid.uuid4()),'state':'delivered'}
        payload.update(extra)
        return self.client.post('/api/entrega/',payload)
    def yesterday(self):
        self.trip.date=timezone.localdate()-timedelta(days=1);self.trip.save()
    def test_delivery_can_sync_next_day_and_retry_keeps_original_capture(self):
        self.yesterday()
        captured=timezone.now()-timedelta(days=1)
        event=str(uuid.uuid4())
        for _ in range(2): self.assertEqual(self.post(event_id=event,captured_at=captured.isoformat()).status_code,200)
        self.delivery.refresh_from_db();self.assertEqual(self.delivery.completed_at,captured)
        self.assertEqual(Receipt.objects.count(),1);self.assertEqual(len(mail.outbox),1)
    def test_legacy_queue_without_capture_is_accepted(self):
        self.yesterday();self.assertEqual(self.post(state='rejected',reason='Embalaje dañado').status_code,200)
        self.delivery.refresh_from_db();self.assertEqual(self.delivery.state,'rejected')
    def test_owner_and_today_only_route_visibility_are_preserved(self):
        self.yesterday();self.truck.driver=self.manager;self.truck.save()
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.client.get('/api/estado/').json()['trips'],[])
    def test_future_trip_or_invalid_capture_rejected(self):
        self.trip.date=timezone.localdate()+timedelta(days=1);self.trip.save()
        self.assertEqual(self.post().status_code,404)
        self.trip.date=timezone.localdate();self.trip.save()
        for captured in ['invalid','2020-01-01T10:00:00', (timezone.now()+timedelta(days=1)).isoformat(),(timezone.now()-timedelta(days=2)).isoformat()]:
            self.assertEqual(self.post(captured_at=captured).status_code,400)
