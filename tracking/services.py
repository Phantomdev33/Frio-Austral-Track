from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from .models import Alert
from django.db import transaction
from .models import Trip

from core.thermal import thermal_status, thermal_events

@transaction.atomic
def evaluate_trip(trip, *, notify=True):
    Trip.objects.select_for_update().get(pk=trip.pk)
    rows=list(trip.readings.all())
    result = thermal_status(rows)
    existing=list(trip.alerts.select_for_update().order_by('-emailed','created_at','pk'))
    used=set()
    # Conservar la auditoría y ocultar las alertas invalidadas o fusionadas por muestras tardías.
    trip.alerts.update(superseded=True)
    for event in thermal_events(rows):
        kind=event['kind']
        matches=[a for a in existing if a.pk not in used and a.kind==kind and (event['started_at']<=(a.triggered_at or a.started_at)<=event['ended_at'] or a.started_at==event['started_at'])]
        if matches:
            alert=matches[0]
        else:
            alert=Alert.objects.create(trip=trip,kind=kind,started_at=event['started_at'],triggered_at=event['captured_at'])
            existing.append(alert)
        used.add(alert.pk)
        # Las notificaciones previas incluidas en este intervalo reconstruido pertenecen al mismo episodio.
        for merged in matches[1:]: used.add(merged.pk)
        alert.superseded=False
        alert.last_observed_at=event['ended_at']
        alert.triggered_at=alert.triggered_at or alert.started_at
        alert.save(update_fields=['superseded','last_observed_at','triggered_at'])
        if not alert.emailed and notify:
            label='Ruptura de cadena de frío' if kind=='rupture' else 'Alerta crítica'
            send_mail(f'Frío-Austral · {label} · {trip.truck.code}', f'Evento registrado a las {event["captured_at"].isoformat()}. Temperatura: {event["temperature"]} °C. Más de 15 minutos sobre el umbral. Puede corresponder a un lote sincronizado con retraso; revisar el estado actual.', settings.DEFAULT_FROM_EMAIL, [settings.OPERATIONS_EMAIL])
            alert.emailed = True
            alert.save(update_fields=['emailed'])
    return result
