"""Ejecuta pruebas reales y convierte sus resultados en imagenes PNG."""
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.deps'))
from PIL import Image, ImageDraw, ImageFont


def main():
    output = ROOT / 'output' / 'evidencias_actividad3'
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, 'manage.py', 'test', 'tracking.test_evidencias', '--noinput', '-v', '2']
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
    (output / 'ejecucion.txt').write_text(result.stdout, encoding='utf-8')
    print(result.stdout)
    if result.returncode:
        print('La ejecucion fallo. No se generan imagenes aprobadas.')
        return result.returncode
    records = [json.loads(line.split('EVIDENCIA_JSON:', 1)[1]) for line in result.stdout.splitlines() if 'EVIDENCIA_JSON:' in line]
    if len(records) != 4:
        raise RuntimeError('Se esperaban cuatro resultados verificables.')
    stamp = datetime.now(ZoneInfo('America/Santiago')).isoformat(timespec='seconds')
    (output / 'resultados.json').write_text(json.dumps({'executed_at': stamp, 'command': command, 'scenarios': records}, indent=2, ensure_ascii=False), encoding='utf-8')
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    title_font = ImageFont.truetype(str(fonts / 'consolab.ttf'), 32)
    body_font = ImageFont.truetype(str(fonts / 'consola.ttf'), 23)
    small_font = ImageFont.truetype(str(fonts / 'consola.ttf'), 20)
    report = ['# Evidencias ejecutadas - Actividad 3', '', f'Ejecucion: {stamp}', '',
              'Pruebas de integracion automatizadas con SQLite temporal y API Django.',
              'La desconexion y la perdida del ACK se inyectan en el transporte.',
              'No son capturas de la interfaz web ni una prueba de red fisica.',
              'El correo se comprueba en memoria; no se envia a destinatarios externos.', '',
              'Comando para repetir: `python generar_evidencias.py`.', '',
              'Cada PNG representa la salida de un escenario aprobado. El registro completo',
              'esta en `ejecucion.txt` y los datos estructurados en `resultados.json`.', '']
    for record in records:
        image = Image.new('RGB', (1400, 700), '#101c2b')
        draw = ImageDraw.Draw(image)
        draw.text((45, 32), 'FRIO-AUSTRAL TRACK | ACTIVIDAD 3', font=small_font, fill='#79c5ed')
        draw.text((45, 86), record['number'] + '  ' + record['title'], font=title_font, fill='white')
        draw.text((45, 145), 'APROBADO | prueba de integracion ejecutada', font=body_font, fill='#80e5b1')
        y = 210
        for line in record['lines']:
            for wrapped in textwrap.wrap('> ' + line, width=91):
                draw.text((45, y), wrapped, font=body_font, fill='#e1e8f1')
                y += 32
            y += 10
        draw.line((45, 585, 1355, 585), fill='#34506a', width=2)
        draw.text((45, 605), 'SQLite temporal + API Django; fallos de transporte simulados.', font=small_font, fill='#a8b7c9')
        draw.text((45, 640), 'Ejecucion: ' + stamp, font=small_font, fill='#a8b7c9')
        name = record['number'] + '_resultado.png'
        image.save(output / name)
        report += ['## ' + record['title'], '', *['- ' + line for line in record['lines']], '', f'Imagen: `{name}`', '']
    report += ['## Como obtener capturas de pantalla', '',
               'Abre cada PNG para insertarlo directamente en el informe. Si necesitas una',
               'captura de terminal, abre PowerShell en el proyecto y ejecuta:', '',
               '```powershell', 'python manage.py test tracking.test_evidencias --noinput -v 2', '```', '',
               'Espera el resultado `Ran 4 tests` y `OK`; usa Win + Shift + S para capturar.',
               'Para una salida por escenario, agrega el nombre del metodo de prueba al',
               'selector `tracking.test_evidencias.EvidenciasActividad3Tests`.', '',
               '## Relacion con la escala', '',
               'La escala no impone cuatro capturas. Estas pruebas aportan evidencia del',
               'funcionamiento de ambos modulos y sus casos de borde. No acreditan por si',
               'solas los tres controles OWASP: deben acompanarse de sus pruebas y codigo.', '',
               'La escala tampoco especifica el limite temporal. La regla vigente del',
               'prototipo es tiempo > 15 min; con muestreo cada 5 min se activa en minuto 20.']
    (output / 'LEEME.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    print(f'Listo: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
