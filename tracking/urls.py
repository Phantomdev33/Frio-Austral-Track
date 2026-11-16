from django.urls import path
from . import views
from . import shop

urlpatterns = [
    path('', views.home, name='home'),
    path('ingresar/', views.signin, name='signin'),
    path('salir/', views.signout, name='signout'),
    path('operaciones/', views.dashboard, name='dashboard'),
    path('conductor/', views.driver, name='driver'),
    path('cliente/', views.client, name='client'),
    path('cliente/catalogo/',shop.catalog,name='catalog'),
    path('cliente/pedidos/',shop.orders,name='orders'),
    path('cliente/pedidos/crear/',shop.create_order,name='create_order'),
    path('cliente/pedidos/<int:pk>/',shop.order_detail,name='order_detail'),
    path('cliente/pedidos/<int:pk>/pago-simulado/',shop.simulate_payment,name='simulate_payment'),
    path('operaciones/pedidos/',shop.operations_orders,name='operations_orders'),
    path('operaciones/pedidos/<int:pk>/asignar/',shop.assign_order,name='assign_order'),
    path('api/estado/', views.state_api),
    path('api/entrega/', views.delivery_api),
    path('api/lecturas/', views.reading_api),
    path('api/v1/lecturas/lote/', views.batch_readings_api),
    path('api/incidencia/', views.incident_api),
    path('api/alerta/<int:pk>/', views.alert_api),
    path('api/simulador/', views.simulator_api),
    path('certificado/<int:pk>/', views.certificate, name='certificate'),
    path('foto/<int:pk>/', views.delivery_photo, name='delivery_photo'),
    path('reporte.csv', views.report, name='report'),
    path('sw.js', views.service_worker),
]
