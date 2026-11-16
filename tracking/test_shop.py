import uuid
from django.contrib.auth.models import User
from django.test import TestCase,Client
from django.utils import timezone
from .models import Product,Profile,Order,Payment,OrderItem,Truck,Trip,Delivery

class ShopTests(TestCase):
    def setUp(self):
        self.customer=User.objects.create_user('buyer',password='password')
        Profile.objects.create(user=self.customer,role='client')
        self.other=User.objects.create_user('other',password='password')
        Profile.objects.create(user=self.other,role='client')
        self.manager=User.objects.create_user('manager',password='password')
        Profile.objects.create(user=self.manager,role='manager')
        self.driver=User.objects.create_user('driver',password='password')
        Profile.objects.create(user=self.driver,role='driver')
        self.product=Product.objects.create(name='Salmón',category='Salmón',price=50000,stock=10)
        truck=Truck.objects.create(code='FA-018',plate='XXX',branch='Castro',driver=self.driver)
        self.trip=Trip.objects.create(truck=truck,date=timezone.localdate())
        self.client.force_login(self.customer)
    def create(self,**overrides):
        payload={'event_id':str(uuid.uuid4()),'recipient':'Hotel del Sur','address':'Calle Sur 100, Castro','branch':'Castro',f'quantity_{self.product.pk}':'2'}
        payload.update(overrides)
        response=self.client.post('/cliente/pedidos/crear/',payload)
        self.assertEqual(response.status_code,302)
        return Order.objects.latest('pk')
    def pay(self,order,outcome='approved',event=None,**extra):
        return self.client.post(f'/cliente/pedidos/{order.pk}/pago-simulado/',{'event_id':event or str(uuid.uuid4()),'outcome':outcome,**extra})
    def test_pages_render_and_prices(self):
        for path in ['/cliente/','/cliente/catalogo/','/cliente/pedidos/']:
            self.assertEqual(self.client.get(path).status_code,200)
        self.assertContains(self.client.get('/cliente/catalogo/'),'$50.000')
        order=self.create();self.assertEqual(self.client.get(f'/cliente/pedidos/{order.pk}/').status_code,200)
    def test_order_total_calculated_on_server(self):
        order=self.create(total='1',unit_price='1',state='confirmed',urgent='on')
        self.assertEqual(order.total,100000);self.assertEqual(order.state,'pending');self.assertTrue(order.urgent)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,10)
    def test_create_retry_is_idempotent(self):
        event=str(uuid.uuid4());self.create(event_id=event);self.create(event_id=event)
        self.assertEqual(Order.objects.count(),1)
    def test_decline_and_cancel_do_not_confirm_or_consume_stock(self):
        order=self.create()
        for outcome in ['declined','cancelled']:
            self.pay(order,outcome);order.refresh_from_db();self.assertEqual(order.state,'pending')
        self.product.refresh_from_db();self.assertEqual(self.product.stock,10)
        self.assertEqual(order.payments.count(),2)
    def test_approval_and_repeated_posts_only_deduct_once(self):
        order=self.create();event=str(uuid.uuid4())
        self.pay(order,event=event,amount='1');self.pay(order,event=event);self.pay(order)
        order.refresh_from_db();self.product.refresh_from_db()
        self.assertEqual(order.state,'confirmed');self.assertEqual(self.product.stock,8)
        self.assertEqual(Payment.objects.count(),1);self.assertEqual(Payment.objects.get().amount,100000)
    def test_payment_uses_order_price_snapshot(self):
        order=self.create();self.product.price=100;self.product.save()
        self.pay(order)
        self.assertEqual(Payment.objects.get().amount,100000)
    def test_insufficient_stock_rolls_back_every_item(self):
        second=Product.objects.create(name='Centolla',category='Centolla',price=90000,stock=2)
        order=self.create(**{f'quantity_{second.pk}':'2'})
        second.stock=0;second.save()
        self.pay(order)
        self.product.refresh_from_db();order.refresh_from_db()
        self.assertEqual(self.product.stock,10);self.assertEqual(order.state,'pending');self.assertEqual(Payment.objects.count(),0)
    def test_foreign_order_cannot_be_read_or_paid(self):
        order=self.create();self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/cliente/pedidos/{order.pk}/').status_code,404)
        self.assertEqual(self.pay(order).status_code,404)
        self.assertNotContains(self.client.get('/cliente/pedidos/'),'Hotel del Sur')
    def test_driver_cannot_shop_or_assign(self):
        order=self.create();self.client.force_login(self.driver)
        self.assertEqual(self.client.get('/cliente/catalogo/').status_code,403)
        self.assertEqual(self.client.post(f'/operaciones/pedidos/{order.pk}/asignar/',{'trip_id':self.trip.pk}).status_code,403)
    def test_manager_assignment_urgent_priority_and_retry(self):
        order=self.create(urgent='on');self.pay(order);self.client.force_login(self.manager)
        for _ in range(2): self.assertEqual(self.client.post(f'/operaciones/pedidos/{order.pk}/asignar/',{'trip_id':self.trip.pk}).status_code,302)
        order.refresh_from_db()
        self.assertEqual(order.state,'assigned');self.assertEqual(Delivery.objects.count(),1)
        self.assertEqual(order.delivery.priority,1);self.assertEqual(order.delivery.client_id,self.customer.pk)
        self.assertEqual(self.client.get('/operaciones/pedidos/').status_code,200)
        self.client.force_login(self.driver)
        deliveries=self.client.get('/api/estado/').json()['trips'][0]['deliveries']
        self.assertEqual(deliveries[0]['id'],order.delivery_id)
    def test_unpaid_order_cannot_be_assigned(self):
        order=self.create();self.client.force_login(self.manager)
        self.client.post(f'/operaciones/pedidos/{order.pk}/asignar/',{'trip_id':self.trip.pk})
        self.assertEqual(Delivery.objects.count(),0)
    def test_urgent_is_prioritized_for_planning(self):
        normal=self.create();self.pay(normal)
        urgent=self.create(urgent='on');self.pay(urgent)
        self.client.force_login(self.manager)
        response=self.client.get('/operaciones/pedidos/')
        self.assertEqual(list(response.context['orders']),[urgent,normal])
    def test_invalid_quantities_rejected(self):
        for qty in ['-1','999','1.5','x','0']:
            response=self.client.post('/cliente/pedidos/crear/',{'event_id':str(uuid.uuid4()),'recipient':'Hotel','address':'Castro','branch':'Castro',f'quantity_{self.product.pk}':qty})
            self.assertEqual(response.status_code,302)
        self.assertEqual(Order.objects.count(),0)
    def test_csrf_and_post_required(self):
        order=self.create();c=Client(enforce_csrf_checks=True);c.force_login(self.customer)
        self.assertEqual(c.post(f'/cliente/pedidos/{order.pk}/pago-simulado/',{'outcome':'approved','event_id':str(uuid.uuid4())}).status_code,403)
        self.assertEqual(self.client.get(f'/cliente/pedidos/{order.pk}/pago-simulado/').status_code,405)
