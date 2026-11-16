import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.crypto import encrypt, decrypt
from .store import LocalStore
from .http_client import CloudClient

class OfflineStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/'local.sqlite3'
        self.key=AESGCM.generate_key(bit_length=256)
        self.store=LocalStore(self.path,self.key,'conductor')
    def tearDown(self):
        self.store.close();self.directory.cleanup()
    def test_persists_across_restart(self):
        reading=self.store.capture(18,-14.12345)
        self.store.close();self.store=LocalStore(self.path,self.key,'conductor')
        rows=self.store.rows(pending_only=True)
        self.assertEqual(rows[0]['reading'],reading)
        self.assertEqual(rows[0]['state'],'Pendiente')
    def test_network_failure_keeps_pending(self):
        self.store.capture(18,-20)
        def fail(rows): raise ConnectionError('network')
        with self.assertRaises(ConnectionError): self.store.sync(fail)
        self.assertEqual(len(self.store.rows(pending_only=True)),1)
        self.assertEqual(self.store.rows()[0]['attempts'],1)
    def test_lost_ack_retries_same_id(self):
        original=self.store.capture(18,-20)
        received=set()
        def lost(rows):
            received.update(r['event_id'] for r in rows)
            raise TimeoutError('response lost after persistence')
        with self.assertRaises(TimeoutError): self.store.sync(lost)
        def retry(rows):
            received.update(r['event_id'] for r in rows)
            return {'ok':True,'acknowledged':[r['event_id'] for r in rows]}
        self.assertEqual(self.store.sync(retry),1)
        self.assertEqual(received,{original['event_id']})
        self.assertEqual(len(self.store.rows(pending_only=True)),0)
    def test_partial_ack_does_not_remove_unconfirmed(self):
        first=self.store.capture(18,-20);self.store.capture(18,-21)
        self.assertEqual(self.store.sync(lambda rows:{'ok':True,'acknowledged':[first['event_id']]}),1)
        self.assertEqual(len(self.store.rows(pending_only=True)),1)
    def test_invalid_ack_keeps_all(self):
        self.store.capture(18,-20)
        with self.assertRaises(ValueError): self.store.sync(lambda rows:{'ok':True,'acknowledged':['not-sent']})
        self.assertEqual(len(self.store.rows(pending_only=True)),1)
    def test_ciphertext_and_tamper_detection(self):
        reading=self.store.capture(18,-14.123456)
        row=self.store.connection.execute('SELECT payload FROM readings').fetchone()
        self.assertNotIn('temperature',row['payload']);self.assertNotIn('-14.123456',row['payload'])
        other=LocalStore(self.path,AESGCM.generate_key(bit_length=256),'conductor')
        try:
            with self.assertRaises(InvalidTag): other.rows()
        finally: other.close()
        encrypted=encrypt(self.key,'secret','context')
        with self.assertRaises(InvalidTag): decrypt(self.key,encrypted,'other-context')
        self.assertNotEqual(encrypted,encrypt(self.key,'secret','context'))
    def test_sql_injection_owner_is_bound(self):
        self.store.capture(18,-20)
        other=LocalStore(self.path,self.key,"' OR 1=1; DROP TABLE readings;--")
        try: self.assertEqual(other.rows(),[])
        finally: other.close()
        self.assertEqual(len(self.store.rows()),1)
    def test_local_alarm_without_network(self):
        start=datetime.now(timezone.utc)-timedelta(minutes=20)
        for i in range(5): self.store.capture(18,-14,start+timedelta(minutes=i*5))
        self.assertEqual(self.store.local_status(18)['status'],'critical')
        self.assertEqual(len(self.store.rows(pending_only=True)),5)
    def test_rejects_unsafe_transport(self):
        for url in ['http://example.com','http://127.0.0.1:8000','https://user:password@example.com']:
            with self.assertRaises(ValueError): CloudClient(url,'user','password')
        client=CloudClient('https://example.com','user','password')
        self.assertFalse(client.authenticated)
