/* Frío-Austral Track. Funciona sin scripts remotos ni servicios externos de mapas. */
(()=>{'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v==null?'—':Number(v).toLocaleString('es-CL',{minimumFractionDigits:1,maximumFractionDigits:1}).replace('-', '−');
const time=v=>v?new Date(v).toLocaleTimeString('es-CL',{hour:'2-digit',minute:'2-digit'}):'—';
const csrf=()=>document.querySelector('[name=csrfmiddlewaretoken]')?.value;
const user=document.body.dataset.user, page=document.body.dataset.page;
let data=null, currentTrip=null, offlineDemo=false, assistance=false, showAll=false, mapRegion='Los Lagos', zoom=1, sound=false, syncRunning=false;
let toastTimer;
function toast(text){$('#toast').textContent=text;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),4500)}
function badge(state,label){return `<span class="badge ${esc(state)}">${esc(label)}</span>`}
function connected(){return navigator.onLine&&!offlineDemo}
async function request(url,body){const form=body instanceof FormData;const response=await fetch(url,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'X-CSRFToken':csrf(),...(form?{}:{'Content-Type':'application/json'})}:{},...(body?{body:form?body:JSON.stringify(body)}:{})});if(!response.ok){let msg='No se pudo completar la operación.';try{msg=(await response.json()).error||msg}catch{}const e=new Error(msg);e.status=response.status;throw e}if(response.redirected)throw new Error('La sesión terminó. Vuelve a ingresar para sincronizar.');return response.json()}
function openDialog(id){$(id).showModal()}
$$('[data-close]').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
$$('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close()}}));
$$('[data-demo]').forEach(b=>b.addEventListener('click',()=>{$('#username').value=b.dataset.demo;$('#password').value='Austral2026!';$('#username').focus()}));

// IndexedDB conserva las fotos y una cola independiente para cada usuario autenticado.
const dbPromise=new Promise((resolve,reject)=>{const r=indexedDB.open('frio-austral-v1',2);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains('events'))r.result.createObjectStore('events',{keyPath:'id'});if(!r.result.objectStoreNames.contains('snapshots'))r.result.createObjectStore('snapshots');else r.transaction.objectStore('snapshots').clear()};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
async function dbRun(store,mode,callback){const db=await dbPromise;return new Promise((resolve,reject)=>{const tx=db.transaction(store,mode),req=callback(tx.objectStore(store));let result;req.onsuccess=()=>{result=req.result};tx.oncomplete=()=>resolve(result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error)})}
const events=async()=>((await dbRun('events','readonly',s=>s.getAll()))||[]).filter(e=>e.user===user);
const saveEvent=e=>dbRun('events','readwrite',s=>s.put({...e,user,created:Date.now()}));
const removeEvent=id=>dbRun('events','readwrite',s=>s.delete(id));
const saveSnapshot=d=>dbRun('snapshots','readwrite',s=>s.put({...d,trips:d.trips.map(({lat,lng,...t})=>t)},user));
const loadSnapshot=()=>dbRun('snapshots','readonly',s=>s.get(user));

async function refresh(silent=false){
 try{
  if(!connected())throw new Error('Sin conexión');
  data=await request('/api/estado/');
  if(page==='driver')await saveSnapshot(data);
  render();
 }catch(error){
  if(page==='driver'){
   if(!data)data=await loadSnapshot().catch(()=>null);
   if(data)render();else if(!silent)toast('Conecta el dispositivo para cargar tu ruta por primera vez.');
  }else if(!silent)toast(error.message);
  if(page==='operations'&&$('#updated'))$('#updated').textContent='Sin conexión · datos sin actualizar';
 }
}
function render(){if(page==='operations')renderDashboard();if(page==='driver')renderDriver()}
function filteredTrips(){const branch=$('#branch')?.value;return (data?.trips||[]).filter(t=>!branch||t.branch===branch)}
function tripState(t){return t.deliveries.some(d=>d.state==='route')?'route':t.deliveries[0]?.state||'warehouse'}
function renderDashboard(){
 const trips=filteredTrips(),critical=trips.filter(t=>['critical','rupture'].includes(t.thermal.status));
 $('#updated').textContent=`Actualizado ${time(data.now)}`;
 $('#today').textContent='▦ '+new Date().toLocaleDateString('es-CL',{day:'numeric',month:'short'});
 $('#total').textContent=trips.length;$('#enroute').textContent=trips.filter(t=>tripState(t)==='route').length;
 $('#route-detail').textContent=`${trips.filter(t=>tripState(t)==='warehouse').length} en bodega · ${trips.filter(t=>['delivered','rejected'].includes(tripState(t))).length} cerrados`;
 $('#critical').textContent=String(critical.length).padStart(2,'0');$('#offline').textContent=String(trips.filter(t=>!t.online).length).padStart(2,'0');
 $('#nav-alert-count').textContent=critical.length;$('#alert-count').textContent=critical.length+' activas';
 const alerts=data.alerts.filter(a=>critical.some(t=>t.truck===a.truck));
 $('#alert-list').innerHTML=critical.length?critical.map(t=>{const alert=alerts.find(a=>a.truck===t.truck&&a.kind===t.thermal.status);return `<div class="alert-card"><div class="alert-top"><b>♧ &nbsp;${esc(t.truck)}</b><strong>${fmt(t.thermal.temperature)} °C</strong></div><p>${esc(t.branch)} · lectura ${time(t.thermal.last_at)}</p><div class="alert-sub">${t.thermal.status==='rupture'?'Ruptura':'Crítica, sin ruptura'} · ${t.thermal.status==='rupture'?t.thermal.rupture_minutes:t.thermal.minutes} min sobre ${t.thermal.status==='rupture'?'−12':'−15'} °C</div><div class="alert-bottom"><small>${alert?.emailed?'✉ Correo generado en demo':'✉ Notificación pendiente'}<br>A Gerencia de Operaciones</small>${alert?.acknowledged?badge('normal','Atendida'):`<button data-ack="${alert?.id||''}">${t.thermal.status==='rupture'?'Coordinar auxilio':'Atender'}</button>`}</div></div>`}).join(''):'<p class="empty-state">✓ Sin alertas críticas en esta sede.</p>';
 const incidents=(data.incident_items||[]).filter(i=>trips.some(t=>t.truck===i.truck));
 if(incidents.length)$('#alert-list').insertAdjacentHTML('beforeend',`<div class="alert-card"><b>Incidencias recibidas</b>${incidents.slice(0,3).map(i=>`<p><strong>${esc(i.truck)} · ${i.assistance?'Solicita auxilio':'Incidencia'}</strong><br>${esc(i.description)}<br><small>${time(i.created_at)}</small></p>`).join('')}</div>`);
 $$('[data-ack]').forEach(b=>b.onclick=async()=>{if(!b.dataset.ack)return;b.disabled=true;try{await request('/api/alerta/'+b.dataset.ack+'/',{});toast('Alerta marcada como atendida.');await refresh(true)}catch(e){toast(e.message);b.disabled=false}});
 for(const status of ['normal','watch','critical'])$('#legend-'+status).textContent=trips.filter(t=>t.online&&(status==='critical'?['critical','rupture'].includes(t.thermal.status):t.thermal.status===status)).length;
 $('#legend-offline').textContent=trips.filter(t=>!t.online).length;
 renderMap(trips);renderTable(trips);
 if(sound&&critical.some(t=>!alerts.find(a=>a.truck===t.truck)?.acknowledged))beep();
}
function renderMap(trips){
 const mapped=trips.filter(t=>(t.branch==='Punta Arenas')===(mapRegion==='Magallanes'));
 $('#map-region').textContent=mapRegion==='Los Lagos'?'◇ Ver Magallanes':'◇ Ver Los Lagos';
 $('.geography').style.transform=`scale(${zoom})`;
 $('.geography').style.opacity=mapRegion==='Magallanes'?'.4':'1';
 $('#map-markers').innerHTML=mapped.map((t,i)=>{
  let x,y;
  if(mapRegion==='Magallanes'){x=38+(t.lng+70.91)*120;y=30+(t.lat+53.16)*300}
  else {x=64+(t.lng+73)*24;y=19+(-t.lat-41.45)*57;if(t.truck==='FA-018'){x=45;y=77}if(t.truck==='FA-012'){x=48;y=32}if(t.truck==='FA-027'){x=53;y=66}}
  x=50+(x-50)*zoom;y=50+(y-50)*zoom;
  return `<button class="map-marker ${!t.online?'unknown':esc(t.thermal.status)}" data-truck="${t.id}" style="left:${Math.min(89,Math.max(10,x))}%;top:${Math.min(85,Math.max(12,y))}%" aria-label="${esc(t.truck)}, ${esc(t.thermal.label)}, ${fmt(t.thermal.temperature)} grados">${[12,18,27].some(n=>t.truck===`FA-${String(n).padStart(3,'0')}`)?'♧ '+esc(t.truck):esc(t.truck.slice(3))}</button>`;
 }).join('');
 $$('.map-marker').forEach(b=>b.onclick=()=>{const t=trips.find(t=>t.id===+b.dataset.truck);$$('.map-marker').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');$('#map-detail').innerHTML=`<b>${esc(t.truck)} · ${fmt(t.thermal.temperature)} °C</b><p>${esc(t.driver)}<br>${esc(t.branch)} · ${t.online?'Datos recibidos':'Sin conexión'}<br>${esc(t.thermal.label)}</p><p>Última lectura ${time(t.thermal.last_at)}</p><small>${t.lat.toFixed(3)}° / ${t.lng.toFixed(3)}° · demo</small>`});
}
function renderTable(trips){
 const search=($('#search').value||'').toLocaleLowerCase(),state=$('#state-filter').value;
 let rows=trips.flatMap(t=>t.deliveries.map(d=>({t,d}))).filter(({t,d})=>(!state||d.state===state)&&`${t.truck} ${t.driver} ${d.customer} ${d.guide}`.toLocaleLowerCase().includes(search));
 rows.sort((a,b)=>{const rank=x=>['critical','rupture'].includes(x.t.thermal.status)?0:!x.t.online?1:2;return rank(a)-rank(b)||a.d.priority-b.d.priority});
 $('#dispatch-summary').textContent=`${trips.length} camiones · ${rows.length} despachos en la selección`;
 const visible=showAll?rows:rows.slice(0,6);
 $('#dispatch-rows').innerHTML=visible.map(({t,d})=>`<tr class="${!t.online?'offline-row':''}" data-detail="${d.id}" tabindex="0" role="button" aria-label="Detalle de ${esc(d.customer)}"><td><strong>${esc(t.truck)}</strong><small>${esc(t.plate)}</small></td><td>${esc(t.driver)}</td><td><strong>${esc(d.customer)}</strong><small>${esc(d.cargo)} · Guía ${esc(d.guide)}</small></td><td><span class="temp-cell ${!t.online?'muted':['critical','rupture'].includes(t.thermal.status)?'red':t.thermal.status==='watch'?'amber':'green'}">${fmt(t.thermal.temperature)} °C</span></td><td><span class="muted">${t.online?'◉ Última lectura recibida':'⌁ Sin conexión'}</span><small>Lectura ${time(t.thermal.last_at)}</small></td><td>${badge(d.state,d.state_label)}<small class="${d.state==='rejected'?'red':''}">${esc(d.rejection_reason||(['critical','rupture'].includes(t.thermal.status)?t.thermal.label:!t.online?'Datos locales aún no recibidos':d.state==='delivered'?'Certificado PDF disponible':''))}</small></td></tr>`).join('')||'<tr><td colspan="6" class="empty-state">No se encontraron despachos.</td></tr>';
 $('#row-count').textContent=`${visible.length} de ${rows.length} despachos · Priorizados por atención operacional`;
 $('#show-all').textContent=showAll?'Mostrar resumen ↑':'Ver todos los despachos →';$('#show-all').hidden=rows.length<=6;
 $$('[data-detail]').forEach(row=>{row.onclick=()=>showDetail(+row.dataset.detail);row.onkeydown=e=>{if(e.key==='Enter')row.click()}});
}
function chart(readings){
 if(!readings.length)return '<p class="muted">Sin lecturas disponibles.</p>';
 const values=readings.map(r=>r.temperature),min=Math.min(-24,...values)-1,max=Math.max(-10,...values)+1;
 const coords=values.map((v,i)=>`${10+i/Math.max(1,values.length-1)*380},${85-(v-min)/(max-min)*75}`).join(' ');
 return `<svg class="reading-chart" viewBox="0 0 400 95" role="img" aria-label="Historial térmico: ${esc(values.map(fmt).join(', '))} grados"><path d="M10 85H390" stroke="#d8e3ed"/><polyline points="${coords}" fill="none" stroke="#246392" stroke-width="2.5"/>${coords.split(' ').map(p=>`<circle cx="${p.split(',')[0]}" cy="${p.split(',')[1]}" r="3" fill="#246392"/>`).join('')}</svg>`;
}
function showDetail(id){
 const t=data.trips.find(t=>t.deliveries.some(d=>d.id===id)),d=t.deliveries.find(d=>d.id===id);
 $('#detail-content').innerHTML=`<h3>${esc(d.customer)}</h3>${badge(d.state,d.state_label)}<div class="detail-line"><span>Camión / conductor</span><b>${esc(t.truck)} · ${esc(t.driver)}</b></div><div class="detail-line"><span>Dirección</span><span>${esc(d.address)}</span></div><div class="detail-line"><span>Recepción</span><span>${esc(d.window)}</span></div><div class="detail-line"><span>Carga</span><span>${esc(d.cargo)}</span></div><div class="detail-line"><span>Observaciones</span><span>${esc(d.notes||'Sin observaciones')}</span></div>${d.rejection_reason?`<p class="red">Rechazo: ${esc(d.rejection_reason)}</p>`:''}<h3 style="margin-top:20px">Lecturas registradas · demo</h3>${chart(t.readings)}<p class="muted">${esc(t.thermal.label)} · Última lectura ${time(t.thermal.last_at)}</p>${d.certificate?`<a class="btn primary" href="${d.certificate}">↓ Descargar certificado PDF</a>`:''}`;
 openDialog('#detail-dialog');
}
if(page==='operations'){
 ['#branch','#search','#state-filter'].forEach(s=>$(s).addEventListener(s==='#search'?'input':'change',renderDashboard));
 $$('[data-branch]').forEach(b=>b.onclick=()=>{$('#branch').value=b.dataset.branch;mapRegion=b.dataset.branch==='Punta Arenas'?'Magallanes':'Los Lagos';renderDashboard()});
 $('#show-all').onclick=()=>{showAll=!showAll;renderTable(filteredTrips())};$('#map-region').onclick=()=>{mapRegion=mapRegion==='Los Lagos'?'Magallanes':'Los Lagos';renderMap(filteredTrips())};
 $('#zoom-in').onclick=()=>{zoom=Math.min(1.8,zoom+.2);renderMap(filteredTrips())};$('#zoom-out').onclick=()=>{zoom=Math.max(.6,zoom-.2);renderMap(filteredTrips())};
 $('#sound-toggle').onclick=()=>{sound=!sound;$('#sound-toggle').setAttribute('aria-pressed',String(sound));$('#sound-toggle').textContent=sound?'♬ Activo':'♬';if(sound)beep();toast(sound?'Sonido de alerta activado.':'Sonido silenciado.')};
 $('#cert-nav').href='#dispatches';$('#cert-nav').onclick=()=>{$('#state-filter').value='delivered';showAll=true;renderTable(filteredTrips())};
}
let audioContext;
function beep(){try{audioContext ||= new (window.AudioContext||window.webkitAudioContext)();const osc=audioContext.createOscillator(),gain=audioContext.createGain();osc.connect(gain);gain.connect(audioContext.destination);osc.frequency.value=660;gain.gain.value=.045;osc.start();gain.gain.exponentialRampToValueAtTime(.001,audioContext.currentTime+.4);osc.stop(audioContext.currentTime+.4)}catch{}}

// La vista del conductor combina la copia del servidor con las operaciones locales aún sin confirmar.
async function renderDriver(){
 currentTrip=data?.trips?.[0];if(!currentTrip)return;
 const queue=await events().catch(()=>[]);
 const pendingReadings=queue.filter(e=>e.type==='reading'&&e.payload.trip_id===currentTrip.id).map(e=>e.payload);
 const t={...currentTrip,readings:[...currentTrip.readings,...pendingReadings].sort((a,b)=>new Date(a.captured_at)-new Date(b.captured_at))};
 if(pendingReadings.length)t.thermal=localThermal(t.readings);
 const thermal=t.thermal,pendingDeliveries=new Map(queue.filter(e=>e.type==='delivery').map(e=>[+e.payload.delivery_id,e.payload]));
 const stops=t.deliveries.map(d=>pendingDeliveries.has(d.id)?{...d,state:pendingDeliveries.get(d.id).state,local:true}:d);
 $('#driver-date').textContent=new Date().toLocaleDateString('es-CL',{weekday:'long',day:'numeric',month:'short'}).toUpperCase()+' · SEDE '+t.branch.toUpperCase();
 $('#driver-truck').textContent=`${t.truck} · ${t.plate} · Vehículo detenido`;
 const online=connected();
 $('#connection').innerHTML=online?`<b>⌁ Conexión disponible · ${queue.length?'sincronización pendiente':'datos sincronizados'}</b><p>${queue.length?'Hay registros locales esperando confirmación del servidor.':'Los registros locales se sincronizan automáticamente.'}</p>`:'<b>⌁ Sin conexión · tus datos están a salvo</b><p>Entregas y fotos guardadas en este teléfono. Se sincronizan automáticamente al recuperar señal.</p>';
 $('#temperature-card').className='temperature-card panel '+thermal.status;
 $('#thermal-label').className='badge '+thermal.status;$('#thermal-label').textContent='● '+thermal.label;
 $('#temperature').textContent=fmt(thermal.temperature);
 $('#temp-status').textContent=thermal.status==='normal'?'Dentro de rango · −22 °C a −18 °C':thermal.status==='watch'?(thermal.temperature>-15?'Sobre −15 °C · temporizador activo':'Fuera del rango operativo · revisar refrigeración'):thermal.status==='rupture'?`${thermal.rupture_minutes} min continuos sobre −12 °C`:`${thermal.minutes} min continuos sobre −15 °C`;
 const remaining=Math.max(0,15-thermal.minutes);
 $('#thermal-extra').innerHTML=thermal.status==='watch'&&thermal.temperature>-15?`<div class="thermal-notice"><b>◷ ${thermal.minutes} de 15 min transcurridos</b><progress value="${thermal.minutes}" max="15"></progress><b>${remaining>0?'Quedan '+remaining+' min hasta el umbral temporal':'Esperando una lectura posterior a los 15 min'}</b><p>Si sigue sobre −15 °C durante más de 15 min, se activa la alarma sonora y visual. El correo espera conectividad.</p></div>`:['critical','rupture'].includes(thermal.status)?'<p class="alarm-copy">♬ Alerta visual activa · <button class="text-button red" id="enable-driver-sound">Activar sonido</button></p>':'';
 if(thermal.telemetry_gaps)$('#thermal-extra').insertAdjacentHTML('beforeend','<div class="notice telemetry-notice"><b>Historial con intervalos sin mediciones</b><p>Más de 6 min entre muestras: los temporizadores se reinician. No se presume continuidad térmica durante esos intervalos.</p></div>');
 $('#reading-time').textContent=`Última lectura: ${time(thermal.last_at)} · ${online?'Datos del simulador':'Lectura local / última disponible'}`;
 $('#thermal-action').innerHTML=thermal.status==='normal'?'':thermal.status==='watch'?'<div class="thermal-notice"><b>Detente en un lugar seguro y revisa la refrigeración.</b><p>Usa la aplicación solo con el vehículo detenido.</p></div>':`<div class="thermal-notice"><b>Detente en un lugar seguro antes de actuar.</b><p>${online?'✉ Correo de demostración generado en el servidor.':'✉ El aviso remoto espera la sincronización.'}</p></div><button class="btn danger" style="width:100%" id="request-help">♧ Solicitar auxilio</button><p class="thermal-foot">${thermal.status==='rupture'?'La temperatura ha superado −12 °C durante más de 15 min: incidencia crítica.':'Alerta por tiempo sobre −15 °C. Esta lectura no implica por sí sola ruptura de cadena de frío.'}</p>`;
 $('#enable-driver-sound')?.addEventListener('click',()=>{sound=true;beep();toast('Sonido activado para las alertas.')});
 $('#request-help')?.addEventListener('click',()=>openIncident(true));
 const done=stops.filter(d=>['delivered','rejected'].includes(d.state)).length;
 $('#route-count').textContent=`${done} de ${stops.length} entregas`;
 $('#route-progress').innerHTML=stops.map((d,i)=>`<i class="${['delivered','rejected'].includes(d.state)?'done':''}"></i>`).join('');
 const remainingStops=stops.filter(d=>!['delivered','rejected'].includes(d.state)).sort((a,b)=>a.priority-b.priority||a.position-b.position),next=remainingStops[0];
 $('#next-delivery').innerHTML=next?`<article class="next-stop"><div class="stop-heading"><span>${String(next.position).padStart(2,'0')} · SIGUIENTE PARADA</span>${badge('priority',next.priority===1?'Prioridad alta':next.priority===2?'Prioridad media':'Prioridad normal')}</div><h3>${esc(next.customer)}</h3><p class="address">${esc(next.address)}</p><p>Recepción ${esc(next.window)}</p><p>▣ ${esc(next.cargo)} · Guía ${esc(next.guide)}</p><a class="btn outline" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(next.address)}" target="_blank" rel="noopener">⌁ Ver ruta</a><button class="btn primary" id="register-delivery">▣ Registrar entrega</button><p class="proof-hint">Incluye foto de guía firmada y observaciones.</p><div class="notice">Al confirmar se genera el certificado PDF con historial de lecturas y se prepara el correo al cliente. Sin señal, el envío espera la sincronización.</div></article>`:'<div class="panel empty-state"><h2>✓ Ruta completada</h2><p>Todas las entregas de hoy están registradas.</p></div>';
 $('#register-delivery')?.addEventListener('click',()=>{const form=$('#delivery-form');form.reset();$('#delivery-id').value=next.id;$('#delivery-customer').textContent=next.customer;$('#reason-field').hidden=true;$('#reason').required=false;openDialog('#delivery-dialog')});
 $('#remaining-deliveries').innerHTML=remainingStops.slice(1).map(d=>`<article class="remaining-stop"><span class="stop-number">${String(d.position).padStart(2,'0')}</span><div><div class="stop-priority"><span>PRIORIDAD ${d.priority===2?'MEDIA':'NORMAL'}</span><span class="mono">${esc(d.window)}</span></div><h3>${esc(d.customer)}</h3><p>${esc(d.address)}</p></div></article>`).join('');
 $('#sync-card').innerHTML=`<h3>${queue.length?'☁ Pendiente de sincronizar · '+queue.length:'☁ Todo sincronizado · '+time(data.now)}</h3><p>${queue.length?'Los registros y fotografías están guardados localmente.':'Tus últimos registros fueron recibidos por el servidor.'}</p><small>Almacenamiento en este navegador y sincronización con reintentos. No borres los datos del navegador mientras haya registros pendientes.</small>${queue.length&&online?'<button class="text-button" id="retry-sync">Reintentar sincronización →</button>':''}`;
 $('#retry-sync')?.addEventListener('click',syncQueue);
 if(sound&&['critical','rupture'].includes(thermal.status))beep();
}

async function syncQueue(){
 if(syncRunning||!connected())return;syncRunning=true;
 try{
  const queue=(await events()).sort((a,b)=>a.created-b.created);
  for(const e of queue){
   if(!connected())break;
   let payload=e.payload;
   if(e.type==='delivery'){payload=new FormData();for(const[k,v]of Object.entries(e.payload)){if(k==='photo'&&v)payload.append(k,v,v.name||'guia.jpg');else if(v!=null)payload.append(k,String(v))}}
   try{await request(e.url,payload);await removeEvent(e.id)}catch(error){toast(error.status===409?'Un registro requiere revisión: '+error.message:error.message);break}
  }
  await refresh(true);
 }catch(error){toast('No se pudo acceder al almacenamiento local: '+error.message)}finally{syncRunning=false}
}

async function enqueue(type,url,payload){
 const id=crypto.randomUUID();payload.event_id=id;
 if(type==='delivery')payload.captured_at=new Date().toISOString();
 await saveEvent({id,type,url,payload});
 toast(connected()?'Registro guardado. Sincronizando…':'Registro y fotografía guardados en este dispositivo.');
 await renderDriver();if(connected())await syncQueue();
}
function openIncident(help=false){assistance=help;$('#incident-form').reset();$('#incident-title').textContent=help?'Solicitar auxilio':'Reportar incidencia';if(help)$('#description').value=`Alerta térmica en ${currentTrip.truck}. Solicito asistencia. Ubicación: `;openDialog('#incident-dialog')}
function localThermal(readings){
 return globalThis.FrioThermal.status(readings);
}
if(page==='driver'){
 setInterval(async()=>{
  if(!$('#auto-sensor').checked||!currentTrip||currentTrip.thermal.temperature==null)return;
  try{const queue=await events(),last=queue.filter(e=>e.type==='reading'&&e.payload.trip_id===currentTrip.id).at(-1)?.payload;
   await enqueue('reading','/api/lecturas/',{trip_id:currentTrip.id,temperature:last?.temperature??currentTrip.thermal.temperature,captured_at:new Date().toISOString()});
  }catch(e){toast('No se pudo guardar la lectura local: '+e.message)}
 },300000);
 $('#simulate-offline').onchange=async e=>{offlineDemo=e.target.checked;await renderDriver();if(!offlineDemo)await syncQueue()};
 $$('[data-scenario]').forEach(b=>b.onclick=async()=>{if(!connected()){toast('Recupera la conexión para cambiar los datos del simulador.');return}b.disabled=true;try{await request('/api/simulador/',{scenario:b.dataset.scenario});await refresh();toast('Escenario de demostración actualizado.')}catch(e){toast(e.message)}finally{b.disabled=false}});
 $('#delivery-state').onchange=e=>{const rejected=e.target.value==='rejected';$('#reason-field').hidden=!rejected;$('#reason').required=rejected};
 $('#delivery-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;try{const file=$('#photo').files[0];if(file&&file.size>8*1024*1024)throw new Error('La foto debe pesar menos de 8 MB.');await enqueue('delivery','/api/entrega/',{delivery_id:$('#delivery-id').value,state:$('#delivery-state').value,reason:$('#reason').value,notes:$('#notes').value,photo:file||null});$('#delivery-dialog').close()}catch(error){toast(error.message)}finally{button.disabled=false}};
 $('#report-incident').onclick=()=>openIncident();
 $('#incident-form').onsubmit=async e=>{e.preventDefault();if(!currentTrip)return;const b=e.target.querySelector('[type=submit]');b.disabled=true;try{await enqueue('incident','/api/incidencia/',{truck_id:currentTrip.truck_id,description:$('#description').value,assistance});$('#incident-dialog').close()}catch(error){toast(error.message)}finally{b.disabled=false}};
 $$('[data-driver-tab]').forEach(b=>b.onclick=async()=>{
  if(b.dataset.driverTab==='route'){window.scrollTo({top:0,behavior:'smooth'});return}
  if(b.dataset.driverTab==='help'){$('#records-content').innerHTML='<h3>Operación segura</h3><p>Detén el vehículo antes de usar la aplicación. Ante una alerta, revisa la refrigeración en un lugar seguro.</p><h3>Sin conexión</h3><p>Mantén abierta la app. Las entregas y fotos se conservan en este navegador y se reintentan al recuperar la señal. Puedes volver a abrir la pantalla del conductor sin red después de cargarla una vez.</p><h3>Prototipo académico</h3><p>El sensor, las ubicaciones y los datos de flota son simulados. Los correos se guardan en la carpeta emails del servidor.</p>';openDialog('#records-dialog');return}
  const queued=await events();$('#records-content').innerHTML=`<h3>Entregas</h3>${currentTrip.deliveries.map(d=>`<article class="record-item">${badge(d.state,d.state_label)}<h3>${esc(d.customer)}</h3><p>Guía ${esc(d.guide)} · ${esc(d.cargo)}</p>${d.certificate?`<a href="${d.certificate}">Descargar certificado PDF ↓</a>`:''}</article>`).join('')}<h3 style="margin-top:20px">Pendientes locales · ${queued.length}</h3>${queued.map(e=>`<p>${({delivery:'Entrega',incident:'Incidencia',reading:'Lectura de temperatura'})[e.type]} · ${time(e.created)} · pendiente</p>`).join('')}<h3 style="margin-top:20px">Lecturas de temperatura</h3>${chart(currentTrip.readings)}${currentTrip.readings.map(r=>`<div class="detail-line"><span>${time(r.captured_at)}</span><b>${fmt(r.temperature)} °C</b></div>`).join('')}`;openDialog('#records-dialog');
 });
 window.addEventListener('online',()=>{toast('Conexión recuperada. Sincronizando registros.');syncQueue()});window.addEventListener('offline',()=>renderDriver());
}
// Al cerrar sesión, eliminar la página offline y conservar la cola pendiente de cada usuario.
$$('form[action="/salir/"]').forEach(form=>form.addEventListener('submit',e=>{if(navigator.serviceWorker.controller)navigator.serviceWorker.controller.postMessage({type:'logout'})}));
if('serviceWorker'in navigator&&user)navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'}).then(async registration=>{
 registration.update().catch(()=>{});
 await navigator.serviceWorker.ready;
 // En la primera visita el worker aún no controla la página; guardar explícitamente la vista del conductor.
 if(page==='driver'&&navigator.onLine){const response=await fetch('/conductor/');if(response.ok&&!response.redirected){const cache=await caches.open('frio-austral-current-session');await cache.put('/conductor/',response)}}
}).catch(()=>{});
if(page==='driver'||page==='operations'){
 refresh().then(()=>{if(page==='driver')syncQueue()});
 setInterval(()=>{if(!document.hidden){if(page==='driver')syncQueue();else refresh(true)}},15000);
}
})();
