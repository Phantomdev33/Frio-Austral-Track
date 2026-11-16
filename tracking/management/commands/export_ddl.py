from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help='Exporta el esquema SQLite actual sin registros, credenciales ni datos demo.'
    def handle(self,*args,**options):
        if connection.vendor!='sqlite':
            self.stderr.write('Este exportador es exclusivo para el prototipo SQLite.');return
        with connection.cursor() as cursor:
            cursor.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND type IN ('table','index') AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END,name")
            statements=[row[0]+';' for row in cursor.fetchall()]
        target=Path('ddl/server_sqlite.sql');target.parent.mkdir(exist_ok=True)
        target.write_text('-- Esquema final de referencia. Sin datos. Para ejecutar Django, utilizar manage.py migrate.\nPRAGMA foreign_keys=ON;\nBEGIN;\n'+ '\n\n'.join(statements)+'\nCOMMIT;\n',encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(str(target)))
