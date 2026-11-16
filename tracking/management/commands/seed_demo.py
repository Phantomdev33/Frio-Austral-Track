from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from tracking.models import Profile, Truck, Trip, Delivery, Reading
from tracking.services import evaluate_trip
from tracking.models import Product

class Command(BaseCommand):
    help = 'Crea datos académicos sin sobrescribir registros existentes.'
    def handle(self,*args,**options):
        def user(name,first,last,role):
            u,created=User.objects.get_or_create(username=name,defaults={'first_name':first,'last_name':last,'email':name+'@frioaustral.example'})
            if created: u.set_password('Austral2026!'); u.save()
            Profile.objects.get_or_create(user=u,defaults={'role':role})
            return u
        user('gerencia','Elena','Valenzuela','manager')
        driver=user('conductor','Hernán','Castro','driver')
        client=user('cliente','Alberto','Domínguez','client')
        now=timezone.now()
        for name,category,price,stock,description in [
            ('Filete de salmón premium','Salmón',54900,80,'Filetes congelados, selección premium.'),
            ('Salmón porcionado','Salmón',45900,65,'Porciones listas para cocina profesional.'),
            ('Centolla austral','Centolla',89900,24,'Carne de centolla congelada.'),
            ('Pinzas de centolla','Centolla',69900,18,'Selección de pinzas para gastronomía.'),
            ('Mix de mariscos','Mariscos',29900,100,'Selección de mariscos congelados.'),
            ('Choritos sin concha','Mariscos',19900,120,'Choritos limpios y congelados.')]:
            Product.objects.get_or_create(name=name,defaults={'category':category,'price':price,'stock':stock,'description':description})
        for i in range(1,36):
            code=f'FA-{i:03d}'
            person=driver if i==18 else user(f'conductor{i:02d}',*({12:('Rodrigo','Muñoz'),27:('Patricia','Cárdenas'),3:('Luis','Aguilar'),31:('Daniela','Vera'),9:('Sergio','Alarcón')}.get(i,('Conductor',f'Austral {i:02d}'))),'driver')
            branch='Punta Arenas' if i>=30 else ('Castro' if i>=16 else 'Puerto Montt')
            truck,created=Truck.objects.get_or_create(code=code,defaults={'plate':'LXRD-42' if i==18 else f'FA-{100+i}','branch':branch,'driver':person,'online':i not in (18,33),'last_seen':now-timedelta(minutes=15 if i in (18,33) else 0),'latitude':(-53.16+(i-32)*.025 if i>=30 else -41.45-(i%14)*.085),'longitude':(-70.91+(i%3)*.05 if i>=30 else -73.0-(i%7)*.1)})
            trip,created=Trip.objects.get_or_create(truck=truck,date=timezone.localdate())
            if not created: continue
            values=[-20.8,-20.6,-20.4,-20.5,-20.4]
            if i==12: values=[-14.9,-14.7,-14.5,-14,-13.6]
            if i==27: values=[-11.9,-11.8,-11.6,-11.5,-11.4]
            if i in (6,15,25): values=[-20,-19,-17,-14.8,-14.5]
            for j,value in enumerate(values): Reading.objects.create(trip=trip,temperature=value,captured_at=now-timedelta(minutes=(4-j)*5+(15 if not truck.online else 0)))
            if i==18:
                stops=[('Distribuidora Gamboa','Av. Galvarino Riveros 1200, Castro','09:00–09:30','Salmón · 8 cajas','delivered',3),('Hotel de Castro','Chacabuco 202, Castro','10:00–10:30','Centolla · 4 cajas','delivered',2),('Restaurante Bordemar','Av. Pedro Montt 318, Castro','11:00–11:30','Salmón · 12 cajas','route',1),('Mercado Dalcahue','Ramón Freire 210, Dalcahue','12:00–12:30','Mariscos · 6 cajas','route',2),('Mariscos Quemchi','Arturo Prat 165, Quemchi','13:30–14:00','Mariscos · 5 cajas','route',3)]
            else:
                customer={12:'Frigorífico Chacao · Ancud',27:'Mar del Sur · Dalcahue',3:'Centro de distribución · Puerto Montt',31:'Hotel Cabo de Hornos · Punta Arenas',9:'Distribuidora Costanera · Puerto Montt'}.get(i,f'Cliente Austral {i:02d} · {branch}')
                state='warehouse' if i in (1,2,3,4,5,7,8) else ('rejected' if i==9 else ('delivered' if i in (31,32,34) else 'route'))
                stops=[(customer,f'Ruta de distribución, {branch}','09:00–18:00','Salmón · 640 kg',state,1 if i in (12,27) else 3)]
            for j,(customer,address,window,cargo,state,priority) in enumerate(stops):
                Delivery.objects.create(trip=trip,client=client,customer=customer,address=address,window=window,cargo=cargo,guide=f'{8500+i*2+j:06d}',position=j+1,priority=priority,state=state,rejection_reason='Embalaje dañado' if state=='rejected' else '',completed_at=now-timedelta(minutes=20) if state in ('delivered','rejected') else None)
            evaluate_trip(trip)
        self.stdout.write(self.style.SUCCESS('Demo preparada. Usuarios: gerencia / conductor / cliente. Clave: Austral2026!'))
