from django.contrib import admin
from .models import Profile, Truck, Trip, Delivery, Reading, Alert, Incident
from .models import Product,Order,OrderItem,Payment
for model in [Product,Order,OrderItem,Payment]:
    admin.site.register(model)
for model in [Profile, Truck, Trip, Delivery, Reading, Alert, Incident]:
    admin.site.register(model)
