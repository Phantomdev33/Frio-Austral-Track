/* Versión para el navegador de core/thermal.py; las fechas corresponden a la captura de cada muestra. */
globalThis.FrioThermal=Object.freeze({status(readings){
 const ordered=[...readings].sort((a,b)=>new Date(a.captured_at)-new Date(b.captured_at));
 if(!ordered.length)return {temperature:null,status:'unknown',label:'Sin lecturas',minutes:0,rupture_minutes:0,telemetry_gaps:0};
 let warm=null,rupture=null,previous=null,gaps=0;
 for(const r of ordered){const date=new Date(r.captured_at);if(previous&&date-previous>360000){warm=rupture=null;gaps++}warm=r.temperature>-15?(warm||date):null;rupture=r.temperature>-12?(rupture||date):null;previous=date}
 const last=ordered[ordered.length-1],at=new Date(last.captured_at),minutes=warm?Math.floor((at-warm)/60000):0,ruptureMinutes=rupture?Math.floor((at-rupture)/60000):0;
 const status=rupture&&(at-rupture)>900000?'rupture':warm&&(at-warm)>900000?'critical':last.temperature<-22||last.temperature>-18?'watch':'normal';
 return {temperature:last.temperature,status,label:{normal:'Normal',watch:'En vigilancia',critical:'Alerta crítica',rupture:'Ruptura de cadena de frío'}[status],minutes,rupture_minutes:ruptureMinutes,last_at:last.captured_at,telemetry_gaps:gaps};
}});
