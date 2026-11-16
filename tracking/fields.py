from django.conf import settings
from django.db import models
from core.crypto import encrypt, decrypt

class EncryptedCoordinateField(models.TextField):
    """Almacena coordenadas con cifrado autenticado y devuelve números decimales a la aplicación."""
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return float(decrypt(settings.FIELD_ENCRYPTION_KEY, value, 'truck.' + self.name))

    def to_python(self, value):
        if value is None or isinstance(value, (int, float)):
            return value
        if str(value).startswith('aesgcm:v1:'):
            return float(decrypt(settings.FIELD_ENCRYPTION_KEY, value, 'truck.' + self.name))
        return float(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        return encrypt(settings.FIELD_ENCRYPTION_KEY, str(float(value)), 'truck.' + self.name)
