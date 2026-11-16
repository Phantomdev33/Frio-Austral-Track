from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from .models import Profile,Truck,Trip,Delivery

class ClientDeliveryFiltersTests(TestCase):
    def setUp(self):
        self.customer=User.objects.create_user('customer');Profile.objects.create(user=self.customer,role='client')
        other=User.objects.create_user('other');Profile.objects.create(user=other,role='client')
        driver=User.objects.create_user('driver');Profile.objects.create(user=driver,role='driver')
        truck=Truck.objects.create(code='FA-018',plate='LXRD42',branch='Castro',driver=driver)
        truck2=Truck.objects.create(code='FA-001',plate='TEST01',branch='Puerto Montt',driver=driver)
        self.today=timezone.localdate()
        recent=Trip.objects.create(truck=truck,date=self.today)
        old=Trip.objects.create(truck=truck2,date=self.today-timedelta(days=10))
        def delivery(trip,customer,state,guide,owner=self.customer):
            return Delivery.objects.create(trip=trip,client=owner,customer=customer,state=state,guide=guide,address='Av. Pedro Montt 318',cargo='Salmón · 5 cajas',window='11:00')
        self.done=delivery(recent,'Restaurante Bordemar','delivered','008542')
        self.pending=delivery(recent,'Hotel del Sur','route','PED-000009')
        self.rejected=delivery(old,'Mercado Antiguo','rejected','008000')
        self.foreign=delivery(recent,'Privado de otro cliente','delivered','SECRET-99',other)
        self.client.force_login(self.customer)
    def fetch(self,**params):
        r=self.client.get('/cliente/',params)
        self.assertEqual(r.status_code,200)
        return r
    def ids(self,response): return [d.pk for d in response.context['deliveries']]
    def test_search_fields_and_combined_terms(self):
        for term in ['Bordemar','008542','FA-018','LXRD42','Pedro Montt','Salmón']:
            self.assertIn(self.done.pk,self.ids(self.fetch(q=term)))
        self.assertEqual(self.ids(self.fetch(q='Bordemar 008542')),[self.done.pk])
        self.assertEqual(self.ids(self.fetch(q='Bordemar noexiste')),[])
    def test_search_and_filters_never_expose_other_customer(self):
        self.assertEqual(self.ids(self.fetch(q='SECRET-99')),[])
        self.assertNotContains(self.fetch(),'Privado de otro cliente')
        self.assertEqual(self.fetch().context['results'].paginator.count,3)
    def test_combined_filters(self):
        response=self.fetch(state='delivered',branch='Castro',certificates='on',q='Bordemar',date_from=str(self.today),date_to=str(self.today))
        self.assertEqual(self.ids(response),[self.done.pk])
        self.assertEqual(response.context['available_certificates'],1)
    def test_date_filters_are_inclusive_and_use_route_date(self):
        self.assertEqual(self.ids(self.fetch(date_to=str(self.today-timedelta(days=1)))),[self.rejected.pk])
        self.assertCountEqual(self.ids(self.fetch(date_from=str(self.today),date_to=str(self.today))),[self.done.pk,self.pending.pk])
    def test_only_certificates_excludes_other_states(self):
        self.assertEqual(self.ids(self.fetch(certificates='on')),[self.done.pk])
        self.assertEqual(self.ids(self.fetch(certificates='on',state='route')),[])
    def test_invalid_filters_explain_instead_of_crashing(self):
        for params in [{'date_from':'bad'},{'date_from':str(self.today),'date_to':'2020-01-01'},{'sort':'DROP TABLE'},{'per_page':'100000'},{'state':'unknown'}]:
            response=self.fetch(**params)
            self.assertEqual(self.ids(response),[])
            self.assertContains(response,'Revisa los filtros indicados')
    def test_ordering(self):
        self.assertEqual(self.ids(self.fetch(sort='oldest'))[0],self.rejected.pk)
        self.assertEqual(self.ids(self.fetch(sort='customer')),[self.pending.pk,self.rejected.pk,self.done.pk])
    def test_pagination_retains_filters_and_handles_bad_page(self):
        for i in range(12):
            Delivery.objects.create(trip=self.done.trip,client=self.customer,customer=f'Restaurante {i}',state='delivered',guide=f'G{i}',address='Castro',cargo='Salmón',window='10:00')
        response=self.fetch(q='Restaurante',certificates='on',per_page='9',page=2)
        self.assertEqual(len(self.ids(response)),4)
        self.assertEqual(response.context['results'].paginator.count,13)
        self.assertContains(response,'certificates=on')
        self.assertContains(response,'q=Restaurante')
        self.assertEqual(self.fetch(page='invalid').context['results'].number,1)
        self.assertEqual(self.fetch(page=999).context['results'].number,2)
    def test_empty_and_no_matches_are_distinct(self):
        self.assertContains(self.fetch(q='not-found'),'No encontramos entregas con esos filtros')
        Delivery.objects.filter(client=self.customer).delete()
        self.assertContains(self.fetch(),'Todavía no tienes entregas asignadas')
