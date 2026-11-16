import uuid
from django.db import models
from django.contrib.auth.models import User
from .fields import EncryptedCoordinateField

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=[('manager','Gerencia'),('driver','Conductor'),('client','Cliente')])

class Truck(models.Model):
    code = models.CharField(max_length=12, unique=True)
    plate = models.CharField(max_length=10)
    branch = models.CharField(max_length=40)
    driver = models.ForeignKey(User, on_delete=models.PROTECT, related_name='trucks')
    latitude = EncryptedCoordinateField(default=-42.48)
    longitude = EncryptedCoordinateField(default=-73.76)
    online = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    def __str__(self): return self.code

class Trip(models.Model):
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, related_name='trips')
    date = models.DateField()
    def __str__(self): return f'{self.truck} · {self.date}'

class Delivery(models.Model):
    STATES = [('warehouse','En Bodega'),('route','En Ruta'),('delivered','Entregado conforme'),('rejected','Rechazado')]
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='deliveries')
    client = models.ForeignKey(User, on_delete=models.PROTECT, related_name='deliveries')
    customer = models.CharField(max_length=120)
    address = models.CharField(max_length=200)
    window = models.CharField(max_length=40)
    cargo = models.CharField(max_length=160)
    guide = models.CharField(max_length=20)
    priority = models.PositiveIntegerField(default=3)
    position = models.PositiveIntegerField(default=1)
    state = models.CharField(max_length=16, choices=STATES, default='route')
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    photo = models.FileField(upload_to='entregas/', blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    certificate_sent = models.BooleanField(default=False)
    class Meta: ordering = ['position']

class Reading(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='readings')
    temperature = models.FloatField()
    captured_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['captured_at', 'id']

class Alert(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='alerts')
    kind = models.CharField(max_length=20)
    started_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)
    emailed = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True,blank=True)
    last_observed_at = models.DateTimeField(null=True,blank=True)
    superseded = models.BooleanField(default=False)
    class Meta: constraints = [models.UniqueConstraint(fields=['trip','kind','started_at'], name='unique_thermal_episode')]

class Incident(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE)
    description = models.TextField()
    assistance = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Receipt(models.Model):
    event_id = models.UUIDField(unique=True)
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class Product(models.Model):
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=240, blank=True)
    category = models.CharField(max_length=40)
    unit = models.CharField(max_length=30, default='caja de 5 kg')
    price = models.PositiveIntegerField(help_text='Precio final en pesos chilenos por unidad')
    stock = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    class Meta: ordering = ['category','name']
    def __str__(self): return self.name

class Order(models.Model):
    STATES = [('pending','Pendiente de pago'),('confirmed','Confirmado'),('assigned','Asignado a ruta')]
    event_id = models.UUIDField(unique=True)
    client = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    recipient = models.CharField(max_length=120)
    address = models.CharField(max_length=240)
    branch = models.CharField(max_length=40)
    urgent = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    total = models.PositiveIntegerField()
    state = models.CharField(max_length=16,choices=STATES,default='pending')
    delivery = models.OneToOneField(Delivery,on_delete=models.PROTECT,null=True,blank=True,related_name='order')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']

class OrderItem(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name='items')
    product = models.ForeignKey(Product,on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    unit_price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['order','product'],name='unique_order_product'),models.CheckConstraint(condition=models.Q(quantity__gte=1),name='positive_order_quantity')]
    @property
    def subtotal(self): return self.unit_price*self.quantity

class Payment(models.Model):
    event_id = models.UUIDField(unique=True)
    order = models.ForeignKey(Order,on_delete=models.PROTECT,related_name='payments')
    outcome = models.CharField(max_length=12,choices=[('approved','Aprobado'),('declined','Rechazado'),('cancelled','Cancelado')])
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
