"""Cliente SQLite. La lectura del sensor es simulada, sin BLE nativo."""
import argparse
import getpass
import os
import sys
import time
from pathlib import Path

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'.deps'))
from core.crypto import load_key
from offline_agent.store import LocalStore
from offline_agent.http_client import CloudClient

def main():
    parser=argparse.ArgumentParser(description='Frío-Austral · Módulos A/B con SQLite local cifrado')
    parser.add_argument('command',choices=['capture','status','sync','watch'])
    parser.add_argument('--user',default='conductor')
    parser.add_argument('--trip',type=int)
    parser.add_argument('--temperature',type=float,default=-20.4)
    parser.add_argument('--db',type=Path,default=BASE/'local-data'/'conductor.sqlite3')
    parser.add_argument('--url',default='https://localhost')
    parser.add_argument('--allow-local-http',action='store_true')
    args=parser.parse_args()
    if args.command in ('capture','watch') and not args.trip: parser.error('Indica --trip con el ID de tu viaje.')
    key=load_key('LOCAL_ENCRYPTION_KEY',args.db.with_suffix('.key'),allow_create=not args.db.exists())
    store=LocalStore(args.db,key,args.user)
    try:
        if args.command=='capture':
            store.capture(args.trip,args.temperature)
            status=store.local_status(args.trip)
            print(f'Guardado: Pendiente · {status["label"]} · {status["temperature"]} °C')
            if status.get('telemetry_gaps'): print('Historial con intervalos de más de 6 min sin mediciones. Temporizadores reiniciados.')
            if status['status'] in ('critical','rupture'): print('\a¡ALERTA! Detente en un lugar seguro. Correo pendiente hasta sincronizar.',flush=True)
        elif args.command=='status':
            rows=store.rows()
            print(f'Mostrando {len(rows)} registros de este usuario. Pendientes: {sum(r["state"]=="Pendiente" for r in rows)}')
            for row in rows: print(row['event_id'],row['state'],row['reading']['captured_at'],row['reading']['temperature'])
        else:
            password=os.environ.get('FRIO_PASSWORD') or getpass.getpass('Contraseña (no se guarda en SQLite): ')
            cloud=CloudClient(args.url,args.user,password,allow_local_http=args.allow_local_http)
            if args.command=='sync': print('Confirmados:',store.sync(cloud.send))
            else:
                print('Sensor SIMULADO. Captura cada 5 min; reintenta conexión hasta cada 30 s. Ctrl+C para salir.')
                next_capture=0; next_sync=0; delay=2
                while True:
                    now=time.monotonic()
                    if now>=next_capture:
                        store.capture(args.trip,args.temperature)
                        status=store.local_status(args.trip)
                        print(f'{status["label"]} · {status["temperature"]} °C · almacenado Pendiente',flush=True)
                        if status.get('telemetry_gaps'): print('Historial con intervalos sin mediciones; no se presume continuidad térmica.',flush=True)
                        if status['status'] in ('critical','rupture'): print('\a¡ALERTA CRÍTICA! Revisa la refrigeración.',flush=True)
                        next_capture=now+300
                    if now>=next_sync:
                        try:
                            count=store.sync(cloud.send)
                            if count: print('Sincronizados con confirmación:',count,flush=True)
                            delay=2
                        except Exception:
                            print('Servidor no confirmó. Registros conservados; se reintentará.',flush=True)
                            delay=min(delay*2,30)
                        next_sync=time.monotonic()+delay
                    time.sleep(1)
    except KeyboardInterrupt:
        print('\nCierre seguro; los pendientes permanecen en SQLite.')
    finally:
        store.close()

if __name__=='__main__': main()
