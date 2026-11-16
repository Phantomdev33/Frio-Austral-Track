"""Validación e ingesta sin duplicados compartidas por la API original y la versionada."""
import math
import uuid
from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Reading

class EventConflict(ValueError):
    pass

def validate_reading(body):
    if not isinstance(body, dict) or isinstance(body.get('temperature'), bool):
        raise ValueError('Lectura inválida.')
    value = float(body['temperature'])
    captured = parse_datetime(body['captured_at'])
    event = uuid.UUID(body['event_id'])
    if not math.isfinite(value) or not -60 <= value <= 50 or not captured or timezone.is_naive(captured) or captured > timezone.now() + timedelta(minutes=1):
        raise ValueError('Lectura inválida.')
    return event, value, captured

def ingest(trip, validated):
    event, value, captured = validated
    reading, created = Reading.objects.get_or_create(event_id=event, defaults={'trip':trip, 'temperature':value, 'captured_at':captured})
    if not created and (reading.trip_id != trip.id or reading.temperature != value or reading.captured_at != captured):
        raise EventConflict('El UUID ya fue utilizado para otra lectura.')
    return str(event)
