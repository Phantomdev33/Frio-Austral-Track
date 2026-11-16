from django.db import migrations
import tracking.fields

def encrypt_existing(apps, schema_editor):
    from django.conf import settings
    from core.crypto import encrypt
    Truck = apps.get_model('tracking', 'Truck')
    table = schema_editor.quote_name(Truck._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'SELECT id, latitude, longitude FROM {table}')
        rows = cursor.fetchall()
        for pk, latitude, longitude in rows:
            # Values are bound parameters; table name is migration-owned metadata.
            cursor.execute(f'UPDATE {table} SET latitude=%s, longitude=%s WHERE id=%s', [encrypt(settings.FIELD_ENCRYPTION_KEY, str(float(latitude)), 'truck.latitude'), encrypt(settings.FIELD_ENCRYPTION_KEY, str(float(longitude)), 'truck.longitude'), pk])

class Migration(migrations.Migration):
    dependencies = [('tracking', '0001_initial')]
    operations = [
        migrations.AlterField(model_name='truck', name='latitude', field=tracking.fields.EncryptedCoordinateField(default=-42.48)),
        migrations.AlterField(model_name='truck', name='longitude', field=tracking.fields.EncryptedCoordinateField(default=-73.76)),
        migrations.RunPython(encrypt_existing, reverse_code=None),
    ]
