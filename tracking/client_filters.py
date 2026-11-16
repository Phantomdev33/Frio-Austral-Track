from django import forms
from django.db.models import Q
from .models import Delivery

class DeliveryFilters(forms.Form):
    q=forms.CharField(required=False,max_length=120,label='Buscar una entrega',widget=forms.TextInput(attrs={'type':'search','placeholder':'Destinatario, dirección, guía, carga o camión','autocomplete':'off'}))
    state=forms.ChoiceField(required=False,label='Estado',choices=[('','Todos los estados')]+Delivery.STATES)
    branch=forms.ChoiceField(required=False,label='Sede',choices=[('','Todas las sedes'),('Puerto Montt','Puerto Montt'),('Castro','Castro'),('Punta Arenas','Punta Arenas')])
    date_from=forms.DateField(required=False,label='Fecha de ruta desde',input_formats=['%Y-%m-%d'],widget=forms.DateInput(attrs={'type':'date'}))
    date_to=forms.DateField(required=False,label='Fecha de ruta hasta',input_formats=['%Y-%m-%d'],widget=forms.DateInput(attrs={'type':'date'}))
    certificates=forms.BooleanField(required=False,label='Solo entregas con certificado PDF disponible')
    sort=forms.ChoiceField(required=False,label='Ordenar por',choices=[('newest','Más recientes'),('oldest','Más antiguas'),('customer','Destinatario A–Z')])
    per_page=forms.ChoiceField(required=False,label='Mostrar',choices=[('9','9 por página'),('18','18 por página'),('36','36 por página')])

    def clean(self):
        cleaned=super().clean()
        start,end=cleaned.get('date_from'),cleaned.get('date_to')
        if start and end and start>end:
            self.add_error('date_to','La fecha final debe ser igual o posterior a la inicial.')
        return cleaned

    def apply(self,query):
        if not self.is_valid(): return query.none()
        f=self.cleaned_data
        # Cada término puede aparecer en un campo distinto, pero todos deben coincidir.
        for term in f.get('q','').split():
            query=query.filter(Q(customer__icontains=term)|Q(address__icontains=term)|Q(guide__icontains=term)|Q(cargo__icontains=term)|Q(trip__truck__code__icontains=term)|Q(trip__truck__plate__icontains=term))
        if f.get('state'): query=query.filter(state=f['state'])
        if f.get('branch'): query=query.filter(trip__truck__branch=f['branch'])
        if f.get('date_from'): query=query.filter(trip__date__gte=f['date_from'])
        if f.get('date_to'): query=query.filter(trip__date__lte=f['date_to'])
        if f.get('certificates'): query=query.filter(state='delivered')
        ordering={'newest':['-trip__date','-completed_at','-pk'],'oldest':['trip__date','completed_at','pk'],'customer':['customer','-trip__date','pk']}
        return query.order_by(*ordering.get(f.get('sort'),ordering['newest']))
