"""Las versiones por contenido evitan que un service worker antiguo reutilice la URL de otro recurso."""
import hashlib
from pathlib import Path
from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register=template.Library()

@register.filter
def clp(value):
    return '$'+format(int(value),',').replace(',','.')

@register.simple_tag
def versioned_static(path):
    filename=finders.find(path)
    if not filename:
        return static(path)
    version=hashlib.sha256(Path(filename).read_bytes()).hexdigest()[:12]
    return static(path)+'?v='+version
