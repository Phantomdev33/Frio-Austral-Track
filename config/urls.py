from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [path('admin/', admin.site.urls), path('', include('tracking.urls'))]
# Servir las fotos de evidencia solo mediante la vista autorizada, nunca como archivos públicos.
