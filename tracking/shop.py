import uuid
from django.contrib import messages
from django.db import transaction
from django.db.models import F, Max
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Product,Order,OrderItem,Payment,Trip,Delivery
from .views import allowed

BRANCHES=['Puerto Montt','Castro','Punta Arenas']

@allowed('client')
def catalog(request):
    products=Product.objects.filter(active=True)
    return render(request,'catalog.html',{'products':products,'event_id':uuid.uuid4(),'branches':BRANCHES,'page':'shop'})

@require_POST
@allowed('client')
def create_order(request):
    try:
        event=uuid.UUID(request.POST.get('event_id',''))
        recipient=request.POST.get('recipient','').strip();address=request.POST.get('address','').strip();branch=request.POST.get('branch')
        notes=request.POST.get('notes','').strip();urgent=request.POST.get('urgent')=='on'
        if not recipient or len(recipient)>120 or not address or len(address)>240 or branch not in BRANCHES or len(notes)>2000: raise ValueError('Completa correctamente destinatario, dirección y sede.')
        quantities={}
        for key,value in request.POST.items():
            if key.startswith('quantity_'):
                pk=int(key[9:]);qty=int(value or '0')
                if qty<0 or qty>999: raise ValueError('Las cantidades deben estar entre 0 y 999.')
                if qty: quantities[pk]=qty
        if not quantities: raise ValueError('Selecciona al menos un producto.')
        with transaction.atomic():
            old=Order.objects.filter(event_id=event).first()
            if old:
                same=old.client_id==request.user.pk and old.recipient==recipient and old.address==address and old.branch==branch and old.notes==notes and old.urgent==urgent and dict(old.items.values_list('product_id','quantity'))==quantities
                if not same: raise ValueError('El identificador ya corresponde a otro pedido. Abre el catálogo nuevamente.')
                return redirect('order_detail',pk=old.pk)
            products=list(Product.objects.filter(pk__in=quantities,active=True))
            if len(products)!=len(quantities): raise ValueError('Uno de los productos ya no está disponible.')
            for product in products:
                if product.stock<quantities[product.pk]: raise ValueError(f'Stock insuficiente para {product.name}.')
            total=sum(p.price*quantities[p.pk] for p in products)
            order=Order.objects.create(event_id=event,client=request.user,recipient=recipient,address=address,branch=branch,notes=notes,urgent=urgent,total=total)
            OrderItem.objects.bulk_create([OrderItem(order=order,product=p,name=p.name,unit_price=p.price,quantity=quantities[p.pk]) for p in products])
        return redirect('order_detail',pk=order.pk)
    except (ValueError,TypeError) as error:
        messages.error(request,str(error) or 'Datos de pedido inválidos.')
        return redirect('catalog')

@allowed('client')
def orders(request):
    return render(request,'orders.html',{'orders':Order.objects.filter(client=request.user).prefetch_related('items'),'page':'orders'})

@allowed('client')
def order_detail(request,pk):
    order=get_object_or_404(Order.objects.prefetch_related('items','payments'),pk=pk,client=request.user)
    return render(request,'order_detail.html',{'order':order,'payment_event':uuid.uuid4(),'page':'orders'})

@require_POST
@allowed('client')
def simulate_payment(request,pk):
    order=get_object_or_404(Order,pk=pk,client=request.user)
    try:
        event=uuid.UUID(request.POST.get('event_id',''));outcome=request.POST.get('outcome')
        if outcome not in ('approved','declined','cancelled'): raise ValueError('Resultado de simulación inválido.')
        with transaction.atomic():
            order=Order.objects.select_for_update().get(pk=order.pk)
            previous=Payment.objects.filter(event_id=event).first()
            if previous:
                if previous.order_id!=order.pk or previous.outcome!=outcome: raise ValueError('Identificador de pago en conflicto.')
                return redirect('order_detail',pk=order.pk)
            if order.state!='pending':
                messages.info(request,'Este pedido ya está confirmado. No se realizó otro pago.')
                return redirect('order_detail',pk=order.pk)
            if outcome=='approved':
                # Actualizar solo si hay stock suficiente; así se evita vender más unidades de las disponibles.
                for item in order.items.select_related('product').order_by('product_id'):
                    if not Product.objects.filter(pk=item.product_id,active=True,stock__gte=item.quantity).update(stock=F('stock')-item.quantity):
                        raise ValueError(f'Stock insuficiente para {item.name}. No se confirmó el pago ni se descontaron productos.')
                if not Order.objects.filter(pk=order.pk,state='pending').update(state='confirmed'): raise ValueError('El pedido cambió. Revisa su estado.')
            Payment.objects.create(event_id=event,order=order,outcome=outcome,amount=order.total)
        messages.success(request,'Pago simulado aprobado. Pedido confirmado.' if outcome=='approved' else 'Simulación '+('rechazada' if outcome=='declined' else 'cancelada')+'. El pedido sigue pendiente de pago.')
    except (ValueError,TypeError) as error: messages.error(request,str(error))
    return redirect('order_detail',pk=order.pk)

@allowed('manager')
def operations_orders(request):
    orders=Order.objects.exclude(state='pending').select_related('client','delivery').prefetch_related('items').order_by('-state','-urgent','created_at')
    trips=Trip.objects.filter(date=timezone.localdate()).select_related('truck__driver').order_by('truck__branch','truck__code')
    return render(request,'operations_orders.html',{'orders':orders,'trips':trips})

@require_POST
@allowed('manager')
def assign_order(request,pk):
    try:
        with transaction.atomic():
            order=get_object_or_404(Order.objects.select_for_update(),pk=pk)
            if order.state!='confirmed': raise ValueError('Solo se pueden asignar pedidos confirmados y sin ruta.')
            trip=get_object_or_404(Trip,pk=request.POST.get('trip_id'),date=timezone.localdate(),truck__branch=order.branch)
            if not order.payments.filter(outcome='approved').exists(): raise ValueError('El pedido no tiene un pago aprobado.')
            position=(trip.deliveries.aggregate(last=Max('position'))['last'] or 0)+1
            cargo='; '.join(f'{i.name} · {i.quantity} unidades' for i in order.items.all())[:160]
            delivery=Delivery.objects.create(trip=trip,client=order.client,customer=order.recipient,address=order.address,window='Coordinar recepción',cargo=cargo,guide=f'PED-{order.pk:06d}',priority=1 if order.urgent else 3,position=position,state='route',notes=order.notes)
            if not Order.objects.filter(pk=order.pk,state='confirmed').update(state='assigned',delivery=delivery): raise ValueError('El pedido ya cambió de estado.')
        messages.success(request,'Pedido asignado. Ya aparece en la ruta del conductor.')
    except (ValueError,TypeError) as error: messages.error(request,str(error))
    return redirect('operations_orders')
