MAX_SAMPLE_GAP_SECONDS = 360  # Muestreo cada 5 minutos, con 1 minuto adicional de tolerancia.

def thermal_status(readings, now=None):
    """Asume continuidad entre extremos calientes; now permite estimar el silencio final."""
    rows = sorted(readings, key=lambda r: r.captured_at)
    if not rows:
        return {'status':'unknown', 'label':'Sin lecturas', 'temperature':None, 'minutes':0, 'rupture_minutes':0, 'telemetry_gaps':0, 'gaps':0}
    warm = rupture = previous = None
    gaps = 0
    for row in rows:
        if previous and (row.captured_at-previous.captured_at).total_seconds()>MAX_SAMPLE_GAP_SECONDS:
            gaps += 1
            if not (previous.temperature > -15 and row.temperature > -15):
                warm = None
            if not (previous.temperature > -12 and row.temperature > -12):
                rupture = None
        warm = (warm or row.captured_at) if row.temperature > -15 else None
        rupture = (rupture or row.captured_at) if row.temperature > -12 else None
        previous = row
    last = rows[-1]
    # now estima un episodio abierto; no representa una nueva muestra.
    end = now if now is not None and now > last.captured_at and last.temperature > -15 else last.captured_at
    minutes = (end - warm).total_seconds()/60 if warm else 0
    rupture_minutes = (end - rupture).total_seconds()/60 if rupture else 0
    if rupture_minutes > 15: status, label = 'rupture', 'Ruptura de cadena de frío'
    elif warm and minutes > 15: status, label = 'critical', 'Alerta crítica'
    elif not -22 <= last.temperature <= -18: status, label = 'watch', 'En vigilancia'
    else: status, label = 'normal', 'Normal'
    return {'status':status, 'label':label, 'temperature':last.temperature, 'minutes':int(minutes), 'rupture_minutes':int(rupture_minutes), 'started_at':warm, 'rupture_started_at':rupture, 'last_at':last.captured_at.isoformat(), 'telemetry_gaps':gaps, 'gaps':gaps}

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
            # Dos muestras sobre el umbral conservan el episodio incluso con un hueco.
            if row.temperature<=threshold:
                result=event(episode)
                if result: yield result
                episode=[]
            if row.temperature>threshold: episode.append(row)
        result=event(episode)
        if result: yield result

