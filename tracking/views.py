import csv
import io
import json
import math
import uuid
from datetime import timedelta
from functools import wraps
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.db import transaction
from django.http import JsonResponse, HttpResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from .models import Truck, Trip, Delivery, Reading, Alert, Incident, Receipt
from .services import thermal_status, evaluate_trip
from .ingestion import validate_reading, ingest, EventConflict
from django.core.paginator import Paginator
from .client_filters import DeliveryFilters

def role(user):
    return getattr(getattr(user, 'profile', None), 'role', '')

def allowed(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(request, *args, **kwargs):
            if role(request.user) not in roles:
                return HttpResponse('No tienes acceso a esta sección.', status=403)
            return fn(request, *args, **kwargs)
        return wrapped
    return decorator

def home(request):
    if not request.user.is_authenticated: return redirect('signin')
    return redirect({'manager':'dashboard','driver':'driver','client':'catalog'}.get(role(request.user), 'signin'))

def signin(request):
    error = ''
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and role(user):
            login(request, user)
            return redirect('home')
        error = 'Usuario o contraseña incorrectos.'
    return render(request, 'login.html', {'error':error})

@require_POST
def signout(request):
    logout(request)
    return redirect('signin')

def serialize_trip(trip):
    thermal = thermal_status(trip.readings.all())
    truck = trip.truck
    return {'id':trip.id, 'truck_id':truck.id, 'truck':truck.code, 'plate':truck.plate, 'branch':truck.branch, 'driver':truck.driver.get_full_name(), 'online':truck.online, 'lat':truck.latitude, 'lng':truck.longitude, 'last_seen':truck.last_seen.isoformat() if truck.last_seen else None,
            'thermal':{k:v for k,v in thermal.items() if k not in ('started_at','rupture_started_at')},
            'readings':[{'temperature':r.temperature, 'captured_at':r.captured_at.isoformat()} for r in trip.readings.all()],
            'deliveries':[{'id':d.id, 'customer':d.customer, 'address':d.address, 'window':d.window, 'cargo':d.cargo, 'guide':d.guide, 'priority':d.priority, 'position':d.position, 'state':d.state, 'state_label':d.get_state_display(), 'notes':d.notes, 'rejection_reason':d.rejection_reason, 'certificate':f'/certificado/{d.id}/' if d.state=='delivered' else None} for d in trip.deliveries.all()]}

@allowed('manager')
def dashboard(request): return render(request, 'dashboard.html', {'page':'operations'})

@allowed('driver')
def driver(request): return render(request, 'driver.html', {'page':'driver'})

@allowed('client')
def client(request):
    params=request.GET.copy()
    params.setdefault('sort','newest');params.setdefault('per_page','9')
    form=DeliveryFilters(params)
    owned=Delivery.objects.filter(client=request.user).select_related('trip__truck')
    filtered=form.apply(owned)
    size=int(form.cleaned_data.get('per_page') or '9') if form.is_valid() else 9
    results=Paginator(filtered,size).get_page(request.GET.get('page'))
    params.pop('page',None)
    return render(request,'client.html',{'deliveries':results,'results':results,'filter_form':form,'page_query':params.urlencode(),'page':'receipts','has_deliveries':owned.exists(),'available_certificates':filtered.filter(state='delivered').count()})

@allowed('manager','driver')
def state_api(request):
    trips = Trip.objects.select_related('truck__driver').prefetch_related('readings','deliveries').order_by('-date','id')
    if role(request.user)=='driver': trips = trips.filter(truck__driver=request.user, date=timezone.localdate())
    # Mostrar un viaje por camión, conservando la ruta más reciente.
    latest, seen = [], set()
    for trip in trips:
        if trip.truck_id not in seen:
            latest.append(serialize_trip(trip)); seen.add(trip.truck_id)
    alerts = Alert.objects.filter(superseded=False).select_related('trip__truck').order_by('-created_at')
    if role(request.user)=='driver': alerts=alerts.filter(trip__truck__driver=request.user, trip__date=timezone.localdate())
    incidents=Incident.objects.filter(truck_id__in=seen).select_related('truck').order_by('-created_at')
    return JsonResponse({'trips':latest, 'alerts':[{'id':a.id,'truck':a.trip.truck.code,'kind':a.kind,'acknowledged':a.acknowledged,'emailed':a.emailed} for a in alerts], 'incidents':incidents.count(), 'incident_items':[{'truck':i.truck.code,'description':i.description,'assistance':i.assistance,'created_at':i.created_at.isoformat()} for i in incidents[:10]], 'now':timezone.now().isoformat()})

def owned_trip(request, pk):
    query = Trip.objects.all()
    if role(request.user)=='driver': query=query.filter(truck__driver=request.user)
    return get_object_or_404(query, pk=pk)

def pdf_bytes(delivery):
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    result = io.BytesIO()
    p = canvas.Canvas(result, pagesize=(595,842))
    p.setTitle(f'Historial térmico · Guía {delivery.guide}')
    p.setFillColor(HexColor('#102d45')); p.rect(0,720,595,122,fill=1,stroke=0)
    p.setFillColor(HexColor('#ffffff')); p.setFont('Helvetica-Bold',23); p.drawString(40,790,'Frío-Austral Track')
    p.setFont('Helvetica',13); p.drawString(40,757,'Certificado digital · Registro de cadena de frío')
    p.setFillColor(HexColor('#102d45')); p.setFont('Helvetica',11)
    for i,line in enumerate([f'Cliente: {delivery.customer}',f'Guía: {delivery.guide}   |   Camión: {delivery.trip.truck.code}', f'Destino: {delivery.address}',f'Entrega registrada: {timezone.localtime(delivery.completed_at).strftime("%d/%m/%Y %H:%M")}' if delivery.completed_at else 'Entrega sin confirmar']):
        p.drawString(40,685-i*23,line[:95])
    rows=list(delivery.trip.readings.all()); status=thermal_status(rows)
    p.setFont('Helvetica-Bold',13); p.drawString(40,568,'Historial de temperaturas registradas')
    p.setFont('Helvetica',10); p.drawString(40,548,'Muestreo cada 5 minutos. No se interpolan mediciones inexistentes.')
    if rows:
        lo=min(-24,min(r.temperature for r in rows)-2); hi=max(-10,max(r.temperature for r in rows)+2)
        x0,y0,w,h=65,310,480,190
        def y(v): return y0+(v-lo)/(hi-lo)*h
        for temp in [-22,-18,-15,-12]:
            p.setStrokeColor(HexColor('#cbd5e1')); p.line(x0,y(temp),x0+w,y(temp)); p.drawString(30,y(temp)-3,str(temp))
        p.setStrokeColor(HexColor('#246392')); p.setLineWidth(2)
        start=rows[0].captured_at; span=max(1,(rows[-1].captured_at-start).total_seconds())
        points=[(x0+(r.captured_at-start).total_seconds()/span*w,y(r.temperature)) for r in rows]
        for i,(xv,yv) in enumerate(points):
            if i: p.line(*points[i-1],xv,yv)
            p.circle(xv,yv,2,fill=1)
        p.drawString(x0,290,timezone.localtime(rows[0].captured_at).strftime('%H:%M'))
        p.drawRightString(x0+w,290,timezone.localtime(rows[-1].captured_at).strftime('%H:%M'))
    p.setFont('Helvetica-Bold',11); p.drawString(40,246,f'Estado final: {status["label"]}')
    p.setFont('Helvetica',10)
    p.drawString(40,223,f'Lecturas disponibles: {len(rows)}. Consultar incidencias e historial para evaluar el viaje completo.')
    p.drawString(40,201,'Este documento registra mediciones; no garantiza por sí solo la inocuidad del producto.')
    p.setFillColor(HexColor('#64748b')); p.drawString(40,70,'PROTOTIPO ACADÉMICO · Datos y sensores de demostración')
    p.showPage(); p.save()
    return result.getvalue()

def send_certificate(delivery):
    if delivery.certificate_sent or delivery.state != 'delivered': return
    message = EmailMessage(f'Certificado de entrega · Guía {delivery.guide}', 'Adjuntamos el registro térmico de su entrega. Prototipo académico.', settings.DEFAULT_FROM_EMAIL,[delivery.client.email])
    message.attach(f'certificado-{delivery.guide}.pdf',pdf_bytes(delivery),'application/pdf'); message.send()
    delivery.certificate_sent=True; delivery.save(update_fields=['certificate_sent'])

@require_POST
@allowed('driver')
def delivery_api(request):
    try:
        event=uuid.UUID(request.POST.get('event_id',''))
        delivery=get_object_or_404(Delivery,pk=request.POST.get('delivery_id'),trip__truck__driver=request.user,trip__date__lte=timezone.localdate())
        captured=request.POST.get('captured_at')
        completed=parse_datetime(captured) if captured else timezone.now()
        if not completed or timezone.is_naive(completed) or completed>timezone.now()+timedelta(minutes=1): raise ValueError()
        if timezone.localtime(completed).date()<delivery.trip.date: raise ValueError()
        state=request.POST.get('state'); reason=request.POST.get('reason','').strip()
        if state not in ('delivered','rejected'): return JsonResponse({'error':'Estado inválido.'},status=400)
        if state=='rejected' and not reason: return JsonResponse({'error':'Debes indicar el motivo del rechazo.'},status=400)
        photo=request.FILES.get('photo')
        if photo:
            if photo.size>8*1024*1024: return JsonResponse({'error':'La foto debe pesar menos de 8 MB.'},status=400)
            from PIL import Image
            try: Image.open(photo).verify(); photo.seek(0)
            except Exception: return JsonResponse({'error':'El archivo debe ser una imagen válida.'},status=400)
        with transaction.atomic():
            previous=Receipt.objects.filter(event_id=event).first()
            if previous and previous.delivery_id!=delivery.id: return JsonResponse({'error':'Identificador ya utilizado.'},status=409)
            if not previous:
                delivery=Delivery.objects.select_for_update().get(pk=delivery.pk)
                if delivery.state in ('delivered','rejected'): return JsonResponse({'error':'Esta entrega ya fue registrada.'},status=409)
                delivery.state=state; delivery.notes=request.POST.get('notes',''); delivery.rejection_reason=reason
                if photo: delivery.photo=photo
                delivery.completed_at=completed; delivery.save()
                Receipt.objects.create(event_id=event,delivery=delivery)
        send_certificate(delivery)
        return JsonResponse({'ok':True,'id':delivery.id,'certificate':f'/certificado/{delivery.id}/' if state=='delivered' else None})
    except (ValueError,TypeError): return JsonResponse({'error':'Datos inválidos.'},status=400)

@require_POST
@allowed('driver')
def reading_api(request):
    try:
        body=json.loads(request.body); trip=owned_trip(request,body['trip_id'])
        with transaction.atomic():
            ingest(trip,validate_reading(body))
        trip.truck.online=True; trip.truck.last_seen=timezone.now(); trip.truck.save()
        evaluate_trip(trip)
        return JsonResponse({'ok':True})
    except EventConflict: return JsonResponse({'error':'UUID en conflicto.'},status=409)
    except (ValueError,KeyError,TypeError): return JsonResponse({'error':'Lectura inválida.'},status=400)

@require_POST
@allowed('driver')
def batch_readings_api(request):
    """Procesa el lote completo o lo revierte; confirma solo lecturas guardadas de viajes propios."""
    try:
        body=json.loads(request.body)
        if not isinstance(body,dict) or not isinstance(body.get('readings'),list) or not 1 <= len(body['readings']) <= 100:
            raise ValueError()
        validated=[(row,validate_reading(row)) for row in body['readings']]
        ack=[]; trips={}
        with transaction.atomic():
            for row,reading in validated:
                trip=owned_trip(request,row['trip_id'])
                # Admitir lecturas pendientes de viajes históricos propios, nunca de otro conductor.
                ack.append(ingest(trip,reading)); trips[trip.pk]=trip
        for trip in trips.values():
            trip.truck.online=True; trip.truck.last_seen=timezone.now(); trip.truck.save(update_fields=['online','last_seen'])
            evaluate_trip(trip)
        return JsonResponse({'ok':True,'acknowledged':ack})
    except EventConflict: return JsonResponse({'error':'UUID en conflicto; lote no aplicado.'},status=409)
    except (ValueError,KeyError,TypeError): return JsonResponse({'error':'Lote inválido (1 a 100 lecturas).'},status=400)

@require_POST
@allowed('driver')
def incident_api(request):
    try:
        body=json.loads(request.body); truck=get_object_or_404(Truck,pk=body['truck_id'],driver=request.user); description=body['description'].strip()
        if not description or len(description)>3000: raise ValueError()
        event=uuid.UUID(body['event_id'])
        existing=Incident.objects.filter(event_id=event).first()
        if existing and existing.truck_id!=truck.id: return JsonResponse({'error':'Evento ya utilizado.'},status=409)
        Incident.objects.get_or_create(event_id=event,defaults={'truck':truck,'description':description,'assistance':bool(body.get('assistance'))})
        return JsonResponse({'ok':True})
    except (ValueError,KeyError,TypeError): return JsonResponse({'error':'Incidencia inválida.'},status=400)

@require_POST
@allowed('manager')
def alert_api(request,pk):
    alert=get_object_or_404(Alert,pk=pk); alert.acknowledged=True; alert.save(update_fields=['acknowledged'])
    return JsonResponse({'ok':True})

@require_POST
@allowed('driver')
def simulator_api(request):
    if not settings.DEBUG: return HttpResponse(status=403)
    try:
        scenario=json.loads(request.body)['scenario']
        if scenario not in ('normal','watch','critical','rupture'): raise ValueError()
    except (ValueError,KeyError): return JsonResponse({'error':'Escenario inválido.'},status=400)
    trip=Trip.objects.filter(truck__driver=request.user,date=timezone.localdate()).order_by('-id').first()
    if not trip: return JsonResponse({'error':'No hay ruta asignada.'},status=404)
    # Reemplazar únicamente las muestras y alertas del sensor de demostración de este viaje.
    now=timezone.now()
    values={'normal':[-20.8,-20.6,-20.4,-20.5,-20.4], 'watch':[-20.4,-20.1,-18.2,-14.5,-14.2], 'critical':[-14.9,-14.7,-14.4,-14.0,-13.6], 'rupture':[-11.9,-11.8,-11.6,-11.5,-11.4]}[scenario]
    with transaction.atomic():
        trip.readings.all().delete(); trip.alerts.all().delete()
        Reading.objects.bulk_create([Reading(trip=trip,temperature=value,captured_at=now-timedelta(minutes=(4-i)*5)) for i,value in enumerate(values)])
    evaluate_trip(trip)
    return JsonResponse({'ok':True})

@allowed('manager','driver','client')
def certificate(request,pk):
    delivery=get_object_or_404(Delivery,pk=pk,state='delivered')
    if role(request.user)=='driver' and delivery.trip.truck.driver_id!=request.user.id or role(request.user)=='client' and delivery.client_id!=request.user.id: return HttpResponse(status=403)
    response=HttpResponse(pdf_bytes(delivery),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="certificado-{delivery.guide}.pdf"'
    return response

@allowed('manager','driver','client')
def delivery_photo(request,pk):
    delivery=get_object_or_404(Delivery,pk=pk)
    if role(request.user)=='driver' and (delivery.trip.truck.driver_id!=request.user.id or delivery.trip.date!=timezone.localdate()): return HttpResponse(status=403)
    if role(request.user)=='client' and delivery.client_id!=request.user.id: return HttpResponse(status=403)
    if not delivery.photo: return HttpResponse(status=404)
    return FileResponse(delivery.photo.open('rb'),as_attachment=True,filename='evidencia-'+str(delivery.pk)+'.'+delivery.photo.name.rsplit('.',1)[-1])

@allowed('manager')
def report(request):
    response=HttpResponse(content_type='text/csv; charset=utf-8'); response['Content-Disposition']='attachment; filename="despachos.csv"'; response.write('\ufeff')
    writer=csv.writer(response); writer.writerow(['Camión','Conductor','Cliente','Dirección','Estado','Motivo de rechazo'])
    for d in Delivery.objects.select_related('trip__truck__driver'):
        row=[d.trip.truck.code,d.trip.truck.driver.get_full_name(),d.customer,d.address,d.get_state_display(),d.rejection_reason]
        writer.writerow(["'"+s if s.startswith(('=','+','-','@')) else s for s in row])
    return response

def service_worker(request):
    response=FileResponse(open(settings.BASE_DIR/'static'/'sw.js','rb'),content_type='application/javascript')
    response['Service-Worker-Allowed']='/'; response['Cache-Control']='no-cache'
    return response
