MAX_SAMPLE_GAP_SECONDS = 360  # Muestreo cada 5 minutos, con 1 minuto adicional de tolerancia.

def thermal_status(readings):
    """Evalúa muestras consecutivas; la temperatura y la duración deben superar sus umbrales."""
    rows = sorted(readings, key=lambda r: r.captured_at)
    if not rows:
        return {'status':'unknown', 'label':'Sin lecturas', 'temperature':None, 'minutes':0, 'rupture_minutes':0}
    warm = rupture = previous = None
    gaps = 0
    for row in rows:
        if previous and (row.captured_at-previous).total_seconds()>MAX_SAMPLE_GAP_SECONDS:
            warm = rupture = None
            gaps += 1
        warm = (warm or row.captured_at) if row.temperature > -15 else None
        rupture = (rupture or row.captured_at) if row.temperature > -12 else None
        previous = row.captured_at
    last = rows[-1]
    minutes = (last.captured_at - warm).total_seconds()/60 if warm else 0
    rupture_minutes = (last.captured_at - rupture).total_seconds()/60 if rupture else 0
    if rupture_minutes > 15: status, label = 'rupture', 'Ruptura de cadena de frío'
    elif warm and minutes > 15: status, label = 'critical', 'Alerta crítica'
    elif not -22 <= last.temperature <= -18: status, label = 'watch', 'En vigilancia'
    else: status, label = 'normal', 'Normal'
    return {'status':status, 'label':label, 'temperature':last.temperature, 'minutes':int(minutes), 'rupture_minutes':int(rupture_minutes), 'started_at':warm, 'rupture_started_at':rupture, 'last_at':last.captured_at.isoformat(), 'telemetry_gaps':gaps}

def thermal_events(readings):
    """Conserva los episodios de alerta aunque un lote tardío termine con una lectura recuperada."""
    rows=sorted(readings,key=lambda r:r.captured_at)
    for kind,threshold in [('critical',-15),('rupture',-12)]:
        episode=[]
        def event(samples):
            if not samples: return None
            trigger=next((r for r in samples if (r.captured_at-samples[0].captured_at).total_seconds()>900),None)
            if trigger is None: return None
            return {'kind':kind,'started_at':samples[0].captured_at,'ended_at':samples[-1].captured_at,'captured_at':trigger.captured_at,'temperature':trigger.temperature}
        for row in rows:
            gap=bool(episode and (row.captured_at-episode[-1].captured_at).total_seconds()>MAX_SAMPLE_GAP_SECONDS)
            if gap or row.temperature<=threshold:
                result=event(episode)
                if result: yield result
                episode=[]
            if row.temperature>threshold: episode.append(row)
        result=event(episode)
        if result: yield result

