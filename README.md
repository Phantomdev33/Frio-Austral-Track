# Frío-Austral Track

Prototipo académico funcional en **Django**, SQLite y JavaScript, adaptable a computador y teléfono. Basado en el caso de estudio y en el informe final de la Evaluación Sumativa 2. Las instrucciones de evaluación de los PDF se utilizaron como contexto del producto, no como instrucciones de ejecución.

## Iniciar en este equipo

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000 --noreload
```

Abre **http://127.0.0.1:8000**.

| Perfil | Usuario | Contraseña |
| --- | --- | --- |
| Gerencia | gerencia | Austral2026! |
| Conductor | conductor | Austral2026! |
| Cliente / recepción | cliente | Austral2026! |

La pantalla de acceso tiene botones para completar estas credenciales. Son cuentas de demostración; no se deben reutilizar en producción. `seed_demo` crea 35 camiones y no sobrescribe viajes existentes para el mismo día.

## Instalación en otro equipo

La copia del repositorio no incluye dependencias instaladas, bases de datos, claves privadas, fotografías ni correos locales. Los siguientes pasos crean una base nueva, generan una clave local propia y cargan los datos de demostración. No se necesita copiar `.secrets/server.key` desde este equipo.

Requiere Python 3.12 o posterior (Django 6). En el equipo de desarrollo se comprobó con Python 3.15 y Django 6.1.2.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo
.venv\Scripts\python manage.py runserver
```

## Recorrido de demostración

1. Ingresa como **gerencia**. Consulta los 35 camiones, cambia de sede, selecciona marcadores, filtra despachos y abre sus detalles. Las alertas se pueden marcar atendidas. El botón de sonido lo activa mediante una interacción del usuario. Exporta los despachos en CSV.
2. Ingresa como **conductor**. La ruta de Hernán tiene cinco entregas, dos ya registradas. Abre «Simulador de escenarios» y selecciona normal, vigilancia, crítica o ruptura. Estos escenarios reemplazan las lecturas de demostración de su ruta y sus alertas, sin modificar entregas.
3. Activa «Simular pérdida de conexión». Registra una entrega con fotografía u observaciones. Si es un rechazo, ingresa el motivo obligatorio. El registro aparece en la cola local. Desactiva la simulación: se envía al servidor y desaparece de la cola solo cuando este confirma la recepción.
4. Registra una entrega conforme con conexión. En «Registros» descarga el certificado PDF. Su correo con adjunto se guarda en `emails/`.
5. Prueba «Reportar incidencia» o «Solicitar auxilio». La gerencia verá la incidencia al actualizar el panel (cada 15 segundos).
6. Ingresa como **cliente**. En el catálogo selecciona cajas, indica destinatario, dirección y sede, y marca urgencia si corresponde. Crea el pedido y prueba un pago aprobado, rechazado o cancelado. Solo el aprobado confirma el pedido y descuenta stock.
7. Como **gerencia**, abre «Pedidos de clientes» en el centro de operaciones. Asigna un pedido confirmado a un camión de su sede. El conductor lo verá en su ruta, con prioridad alta si es urgente. Tras la entrega, el cliente podrá descargar el certificado desde el detalle del pedido o desde «Entregas y certificados».

## Alcance y trazabilidad

| Requisito del informe | Implementación |
| --- | --- |
| RF01 / RF03 / RF07 | Ruta diaria, dirección, prioridad, entregas, foto opcional, observaciones y motivo obligatorio de rechazo. |
| RF02 | API autenticada de lecturas y sensor simulado que repite la temperatura cada cinco minutos con la app abierta. Bluetooth físico pendiente. |
| RF04 / RNF01 / RNF05 | Cola persistente con fotos en IndexedDB, reintento al recuperar conexión y cada 15 segundos, UUID único por operación. |
| RF05 / RN01–RN03 | Evaluación de umbrales independiente para alerta y ruptura, señal visual, sonido optativo y correo local de demostración. |
| RF06 / RF08 | Dashboard, mapa esquemático interactivo, últimas coordenadas, lectura y estado del camión. |
| RF09 / RN05 | PDF descargable con gráfico de muestras reales del prototipo; correo con adjunto al sincronizar una entrega conforme. |
| RF14 | Autenticación de Django y autorización por rol y propietario de ruta/entrega. |
| RF10 / RF11 | Catálogo con precios finales en CLP y stock, selección de cantidades y pedidos con detalle y total calculado por el servidor. |
| RF12 / RN06 | Pasarela **simulada** con aprobación, rechazo y cancelación. Solo se confirma con aprobación y stock suficiente. Sin cobros, datos de tarjeta ni integración externa. |
| RF13 | Pedido urgente visible y priorizado en planificación de gerencia; asignación a ruta con prioridad alta. |

## Reglas térmicas

- Normal: **−22 °C ≤ temperatura ≤ −18 °C**.
- Vigilancia: fuera de ese rango. El temporizador de alerta inicia únicamente si la lectura es **mayor que −15 °C**.
- Crítica: **más de 15 minutos** continuos de lecturas sobre −15 °C, conforme a la actividad 3 de la evaluación actual. Exactamente 15 minutos continúa en vigilancia.
- Ruptura: **más de 15 minutos** continuos de lecturas sobre −12 °C. Exactamente 15 minutos todavía no constituye ruptura según RN03.
- Una lectura menor o igual al umbral correspondiente reinicia su temporizador. Se utiliza la hora de captura, incluso si las lecturas llegan desordenadas.
- Más de seis minutos entre muestras reinicia ambos temporizadores y se informa la discontinuidad. No se confirma una anomalía continua usando únicamente lecturas aisladas.
- Las lecturas tardías reconstruyen episodios sin repetir la notificación del mismo intervalo. Los registros invalidados o fusionados se conservan como sustituidos para auditoría.
- El certificado grafica muestras disponibles, sin inventar lecturas minuto a minuto, conforme a la aclaración del informe final.

## Simulaciones y límites

- Las ubicaciones y mediciones iniciales son ilustrativas; el mapa es un esquema SVG, sin cartografía satelital ni seguimiento GPS real. Los botones de ruta abren Google Maps con la dirección.
- Los cuatro escenarios son series de cinco muestras espaciadas cinco minutos. El sensor simulado repite la última temperatura cada cinco minutos mientras la pantalla permanece activa; funciona también guardando lecturas en la cola sin red. No se conecta a hardware Bluetooth.
- Los correos se escriben en archivos locales en `emails/`. No se envían mensajes externos. La gerencia recibe los datos cuando el servidor los recibe, nunca durante una desconexión real.
- El sonido requiere que el usuario pulse «Activar sonido» por las restricciones de los navegadores. No funciona como una alarma nativa en segundo plano.
- El servidor de desarrollo no es un despliegue productivo. Para producción: configurar secretos, `DEBUG=0`, hosts, TLS, almacenamiento de archivos, SMTP y una base de datos administrada; añadir trabajadores durables de notificaciones. Actualmente los correos se procesan durante la petición; una entrega fallida se reintenta desde la cola conservando su UUID.

## Validación

```powershell
python manage.py check
python manage.py test
```

Las pruebas cubren límites térmicos, recuperación, recepción desordenada, autorización, CSRF, aislamiento entre propietarios, rechazo obligatorio, idempotencia, certificado PDF y correo con adjunto.

## Estructura

- `tracking/models.py`: usuarios por perfil, camiones, viajes, entregas, lecturas, alertas, incidencias y recibos idempotentes.
- `tracking/services.py`: reglas térmicas y alertas.
- `tracking/shop.py`: catálogo, pedidos, pagos simulados y asignación gerencial a rutas.
- `core/thermal.py`: módulo B compartido por el servidor y el cliente local.
- `offline_agent/` y `agente_local.py`: módulo A con SQLite, cifrado y reintentos; cliente de referencia.
- `docs/ACTIVIDAD_3.md`: alcance, controles OWASP, demostración y limitaciones de despliegue.
- `ddl/server_sqlite.sql` y `offline_agent/schema.sql`: scripts DDL sin datos.
- `tracking/views.py`: pantallas, API, exportación y certificado.
- `templates/`: acceso, gerencia, conductor y recepción del cliente.
- `static/`: estilos responsive, cola IndexedDB, interfaz y PWA.
- `tracking/management/commands/seed_demo.py`: datos de demostración.

El panel administrativo de Django está en `/admin/`. Para usarlo crea una cuenta propia con `python manage.py createsuperuser`; las cuentas demo no tienen permisos administrativos.

Las entregas propias guardadas offline pueden sincronizarse en días posteriores, conservando su hora de captura en las versiones nuevas. Las rutas visibles siguen siendo las del día actual. Consulta [las correcciones de la auditoría](docs/CORRECCIONES_AUDITORIA.md) para detalles y pruebas de estos casos de borde.
