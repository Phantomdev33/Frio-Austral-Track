"""Cifrado AES-256-GCM con un nonce nuevo por operación y datos asociados al contexto."""
import base64
import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def load_key(env_name, path, *, allow_create=False):
    configured = os.environ.get(env_name)
    if configured:
        key = base64.b64decode(configured, validate=True)
    else:
        path = Path(path)
        if not path.exists():
            if not allow_create:
                raise RuntimeError(f'Falta la clave {env_name}. No se crea una clave nueva sobre datos existentes.')
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(base64.b64encode(AESGCM.generate_key(bit_length=256)))
            except FileExistsError:
                pass
        key = base64.b64decode(path.read_bytes(), validate=True)
    if len(key) != 32:
        raise ValueError(f'{env_name} debe contener una clave AES de 32 bytes en Base64.')
    return key

def encrypt(key, plaintext, context):
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode('utf-8'), context.encode('utf-8'))
    return 'aesgcm:v1:' + base64.b64encode(nonce + ciphertext).decode('ascii')

def decrypt(key, envelope, context):
    if not envelope.startswith('aesgcm:v1:'):
        raise ValueError('Se esperaba un valor cifrado AES-GCM v1.')
    raw = base64.b64decode(envelope[10:], validate=True)
    return AESGCM(key).decrypt(raw[:12], raw[12:], context.encode('utf-8')).decode('utf-8')
