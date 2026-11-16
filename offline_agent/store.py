"""Módulo A: almacenamiento SQLite, consultas parametrizadas y sincronización con confirmación."""
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from core.crypto import encrypt, decrypt
from core.thermal import thermal_status

class LocalStore:
    def __init__(self, path, key, owner):
        self.key, self.owner = key, owner
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=15)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))

    def close(self):
        self.connection.close()

    def capture(self, trip_id, temperature, captured_at=None):
        if isinstance(temperature,bool): raise ValueError('Temperatura inválida.')
        value=float(temperature)
        if not math.isfinite(value) or not -60 <= value <= 50: raise ValueError('Temperatura inválida.')
        when=captured_at or datetime.now(timezone.utc)
        if when.tzinfo is None or when.utcoffset() is None: raise ValueError('La captura debe tener zona horaria.')
        if not isinstance(trip_id,int) or isinstance(trip_id,bool) or trip_id<1: raise ValueError('Viaje inválido.')
        event_id=str(uuid.uuid4())
        payload={'event_id':event_id,'trip_id':trip_id,'temperature':value,'captured_at':when.isoformat()}
        envelope=encrypt(self.key,json.dumps(payload),f'{self.owner}:{event_id}')
        with self.connection:
            self.connection.execute('INSERT INTO readings(event_id,owner,payload,created_at) VALUES(?,?,?,?)',(event_id,self.owner,envelope,when.isoformat()))
        return payload

    def rows(self, pending_only=False, limit=100):
        sql='SELECT * FROM readings WHERE owner=?'
        params=[self.owner]
        if pending_only: sql+=' AND state=?'; params.append('Pendiente')
        sql+=' ORDER BY created_at,event_id LIMIT ?'; params.append(limit)
        rows=self.connection.execute(sql,params).fetchall()
        return [{**dict(row),'reading':json.loads(decrypt(self.key,row['payload'],f'{self.owner}:{row["event_id"]}'))} for row in rows]

    def local_status(self,trip_id):
        rows=self.rows(limit=100000)
        samples=[SimpleNamespace(temperature=row['reading']['temperature'],captured_at=datetime.fromisoformat(row['reading']['captured_at'])) for row in rows if row['reading']['trip_id']==trip_id]
        return thermal_status(samples)

    def sync(self,send):
        rows=self.rows(pending_only=True)
        if not rows: return 0
        ids={row['event_id'] for row in rows}
        with self.connection:
            self.connection.executemany('UPDATE readings SET attempts=attempts+1 WHERE event_id=? AND owner=?',[(event,self.owner) for event in ids])
        try:
            result=send([row['reading'] for row in rows])
            acknowledged=result.get('acknowledged')
            if not result.get('ok') or not isinstance(acknowledged,list) or not all(isinstance(event,str) and event in ids for event in acknowledged):
                raise ValueError('Confirmación del servidor inválida; se conservan los pendientes.')
            acknowledged=set(acknowledged)
            with self.connection:
                self.connection.executemany("UPDATE readings SET state='Sincronizado',synced_at=?,last_error='' WHERE event_id=? AND owner=? AND state='Pendiente'",[(datetime.now(timezone.utc).isoformat(),event,self.owner) for event in acknowledged])
            return len(acknowledged)
        except Exception:
            # No guardar cuerpos de peticiones, credenciales, ubicaciones ni detalles de excepciones en los registros.
            with self.connection:
                self.connection.executemany('UPDATE readings SET last_error=? WHERE event_id=? AND owner=?',[('Sin confirmación del servidor',event,self.owner) for event in ids])
            raise
