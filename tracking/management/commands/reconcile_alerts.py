from django.core.management.base import BaseCommand
from tracking.models import Trip
from tracking.services import evaluate_trip

class Command(BaseCommand):
    help='Reconstruye episodios y conserva la auditoría sin enviar correos retrospectivos.'
    def handle(self,*args,**options):
        count=0
        for trip in Trip.objects.all().iterator():
            evaluate_trip(trip,notify=False)
            count+=1
        self.stdout.write(self.style.SUCCESS(f'Viajes revisados: {count}. No se enviaron correos.'))
