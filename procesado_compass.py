#!/usr/bin/env python3
"""
Conversor de archivos .bin de digitalizador CAEN
Convierte al formato de coincidencias con detectores múltiples
"""

import struct
import sys
from pathlib import Path

def read_bin_header(file):
    """
    Lee el header del archivo .bin
    2 bytes: CAEx (identificador del formato)
    """
    header = file.read(2)
    if len(header) != 2:
        raise ValueError("Archivo vacío o header incompleto")
    
    # Verificar identificador CAEx
    if header == b'CA':
        print("Header identificado: CAEx")
        return True
    else:
        print(f"Advertencia: Header no reconocido: {header.hex()}")
        return False

def read_bin_event(file):
    """
    Lee un evento de 18 bytes del archivo .bin
    Formato CAEN (little endian):
    - Bytes 0-1: Board (2 bytes, little endian) - en nuestro caso siempre 0x0000
    - Bytes 2-3: Channel (2 bytes, little endian, 0-7) - número de entrada
    - Bytes 4-11: Timestamp (8 bytes, little endian, en picosegundos)
    - Bytes 12-13: Energy (2 bytes, little endian, en canales)
    - Bytes 14-17: Flags (4 bytes, little endian)
    """
    data = file.read(18)
    if len(data) != 18:
        return None
    
    # Verificar si es un evento vacío (todos ceros)
    if all(b == 0 for b in data):
        # Saltar eventos vacíos y leer el siguiente
        return read_bin_event(file)
    
    # Extraer campos usando little endian
    board = struct.unpack('<H', data[0:2])[0]  # 2 bytes unsigned
    channel = struct.unpack('<H', data[2:4])[0]  # 2 bytes unsigned
    timestamp = struct.unpack('<Q', data[4:12])[0]  # 8 bytes unsigned (picosegundos)
    energy = struct.unpack('<H', data[12:14])[0]  # 2 bytes unsigned
    flags = struct.unpack('<I', data[14:18])[0]  # 4 bytes unsigned
    
    # Validar canal (debe estar en rango 0-7)
    if channel > 7:
        print(f"Advertencia: Canal fuera de rango: {channel}")
        return None
    
    # El detector es el canal + 1 (para mantener compatibilidad con el código original que usa 1-4)
    # Si tienes 8 canales (0-7), los detectores serán 1-8
    detector_id = channel + 1
    
    return {
        'board': board,
        'channel': channel,  # 0-7
        'timestamp': timestamp,  # en picosegundos
        'energy': energy,  # en canales (unsigned)
        'flags': flags,
        'detector': detector_id,  # 1-8 para compatibilidad
    }

def group_events_by_coincidence(events, window_ns=100):
    """
    Agrupa eventos que están dentro de la ventana de coincidencia
    Las coincidencias reales solo pueden ser entre detectores diferentes
    """
    if not events:
        return []
    
    # Convertir ventana de ns a picosegundos
    window_ps = window_ns * 1000
    
    # Ordenar eventos por timestamp
    sorted_events = sorted(events, key=lambda x: x['timestamp'])
    n = len(sorted_events)
    
    # Para eventos pequeños, usar algoritmo simple
    if n <= 100:
        return _group_events_optimal(sorted_events, window_ps)
    else:
        # Para archivos grandes, usar algoritmo heurístico más rápido
        return _group_events_heuristic(sorted_events, window_ps)

def _group_events_optimal(sorted_events, window_ps):
    """
    Algoritmo óptimo para conjuntos pequeños de eventos
    """
    n = len(sorted_events)
    
    # Construir matriz de eventos que pueden estar en coincidencia
    can_coincide = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            # Pueden coincidir si: detectores diferentes Y dentro de ventana
            if (sorted_events[i]['detector'] != sorted_events[j]['detector'] and
                sorted_events[j]['timestamp'] - sorted_events[i]['timestamp'] <= window_ps):
                can_coincide[i][j] = True
                can_coincide[j][i] = True
    
    # Usar enfoque greedy mejorado
    used = [False] * n
    current_grouping = []
    
    for i in range(n):
        if used[i]:
            continue
        
        # Encontrar el mejor grupo que incluya el evento i
        best_group = [i]
        best_group_score = 0
        
        # Buscar todos los eventos que pueden coincidir con i
        candidates = []
        for j in range(i + 1, n):
            if not used[j] and can_coincide[i][j]:
                candidates.append(j)
        
        # Evaluar todas las combinaciones de candidatos
        if candidates:
            from itertools import combinations
            for r in range(min(8, len(candidates)), 0, -1):  # Hasta 8 detectores
                for combo in combinations(candidates, r):
                    # Verificar que todos pueden coincidir entre sí
                    group_indices = [i] + list(combo)
                    valid = True
                    detectors = set()
                    
                    for idx in group_indices:
                        det = sorted_events[idx]['detector']
                        if det in detectors:
                            valid = False
                            break
                        detectors.add(det)
                    
                    if not valid:
                        continue
                    
                    # Verificar que todos estén en coincidencia mutua
                    for idx1 in group_indices:
                        for idx2 in group_indices:
                            if idx1 != idx2 and not can_coincide[idx1][idx2]:
                                valid = False
                                break
                        if not valid:
                            break
                    
                    if valid:
                        # Calcular score del grupo
                        times = [sorted_events[idx]['timestamp'] for idx in group_indices]
                        dispersion = max(times) - min(times)
                        group_score = len(group_indices) * 100 - dispersion
                        
                        if group_score > best_group_score:
                            best_group = group_indices
                            best_group_score = group_score
        
        # Marcar eventos como usados y agregar grupo
        for idx in best_group:
            used[idx] = True
        current_grouping.append([sorted_events[idx] for idx in best_group])
    
    return current_grouping

def _group_events_heuristic(sorted_events, window_ps):
    """
    Algoritmo heurístico más rápido para conjuntos grandes
    """
    grouped = []
    used = [False] * len(sorted_events)
    
    for i in range(len(sorted_events)):
        if used[i]:
            continue
        
        # Iniciar un nuevo grupo
        group = [sorted_events[i]]
        detectors_in_group = {sorted_events[i]['detector']}
        group_indices = [i]
        used[i] = True
        
        # Buscar los eventos más cercanos con detectores diferentes
        candidates = []
        for j in range(i + 1, len(sorted_events)):
            if used[j]:
                continue
            
            # Verificar si está dentro de la ventana
            if sorted_events[j]['timestamp'] - sorted_events[i]['timestamp'] > window_ps:
                break
            
            # Si es un detector diferente, agregarlo como candidato
            if sorted_events[j]['detector'] not in detectors_in_group:
                time_diff = sorted_events[j]['timestamp'] - sorted_events[i]['timestamp']
                candidates.append((j, time_diff))
        
        # Ordenar candidatos por proximidad temporal
        candidates.sort(key=lambda x: x[1])
        
        # Agregar candidatos al grupo si son compatibles
        for j, _ in candidates:
            # Verificar que esté dentro de la ventana de todos los eventos del grupo
            within_window = True
            for event in group:
                if abs(sorted_events[j]['timestamp'] - event['timestamp']) > window_ps:
                    within_window = False
                    break
            
            if within_window and sorted_events[j]['detector'] not in detectors_in_group:
                group.append(sorted_events[j])
                detectors_in_group.add(sorted_events[j]['detector'])
                used[j] = True
        
        grouped.append(group)
    
    return grouped

def process_bin_file(input_file, output_file, window_ns=100, max_events=None, verbose=True):
    """
    Procesa el archivo .bin completo
    """
    events = []
    event_count = 0
    valid_events = 0
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Procesando archivo: {input_file}")
        print(f"Ventana de coincidencia: {window_ns} ns")
        print(f"{'='*60}\n")
    
    # Inicializar variables de estadísticas
    channel_stats = {}
    first_timestamp = None
    last_timestamp = None
    
    with open(input_file, 'rb') as f:
        # Leer header
        has_header = read_bin_header(f)
        
        while True:
            event = read_bin_event(f)
            if event is None:
                # Intentar leer el siguiente byte por si no está alineado
                if f.read(1):
                    f.seek(-1, 1)  # Retroceder un byte
                    continue
                else:
                    break  # Fin del archivo
            
            events.append(event)
            valid_events += 1
            
            # Guardar primer y último timestamp
            if first_timestamp is None:
                first_timestamp = event['timestamp']
            last_timestamp = event['timestamp']
            
            # Actualizar estadísticas por canal
            ch = event['channel']
            
            if ch not in channel_stats:
                channel_stats[ch] = {
                    'count': 0,
                    'detector': event['detector']
                }
            
            channel_stats[ch]['count'] += 1
            
            if max_events and valid_events >= max_events:
                break
            
            if verbose and valid_events % 100000 == 0:
                print(f"  Eventos procesados: {valid_events}")
    
    # Calcular tiempo total
    if first_timestamp is not None and last_timestamp is not None:
        total_time_ps = last_timestamp - first_timestamp
        total_time_s = total_time_ps / 1e12  # picosegundos a segundos
    else:
        total_time_ps = 0
        total_time_s = 0
    
    if verbose:
        print(f"\nTotal de eventos válidos: {valid_events}")
        
        # Imprimir tabla de estadísticas
        print("\n" + "="*80)
        print(f"{'Canal':<8} {'Detector':<10} {'Eventos':<12} {'Rate (ev/s)':<12}")
        print("="*80)
        
        for ch in sorted(channel_stats.keys()):
            stats = channel_stats[ch]
            nev = stats['count']
            det = stats['detector']
            
            # Calcular rate
            if total_time_s > 0:
                rate_ev = nev / total_time_s
            else:
                rate_ev = 0
            
            print(f"{ch:<8} {det:<10} {nev:<12} {rate_ev:<12.2f}")
        
        print("="*80)
        print(f"Tiempo total: {total_time_s:.2f} segundos ({total_time_ps:.2e} ps)")
    
    # Agrupar eventos por coincidencia
    if verbose:
        print(f"\nAgrupando eventos por ventana de {window_ns} ns...")
    
    grouped_events = group_events_by_coincidence(events, window_ns)
    
    # Escribir archivo de salida en binario
    if verbose:
        print(f"\nEscribiendo archivo de salida: {output_file}")
    
    with open(output_file, 'wb') as f:
        for group in grouped_events:
            for event in group:
                det = event['detector'] & 0xFF
                energy = event['energy'] & 0xFFFF  # 16 bits unsigned
                
                # Escribir detector (2 bytes) + energía (2 bytes) en big endian
                #f.write(struct.pack('>HH', det, energy))
                f.write(struct.pack('>HH', det, energy))
            # Terminador de grupo (FF FF)
            f.write(b'\xFF\xFF')
    
    # Calcular estadísticas de coincidencias
    singles = sum(1 for g in grouped_events if len(g) == 1)
    doubles = sum(1 for g in grouped_events if len(g) == 2)
    triples = sum(1 for g in grouped_events if len(g) == 3)
    quads = sum(1 for g in grouped_events if len(g) == 4)
    more = sum(1 for g in grouped_events if len(g) > 4)
    
    if verbose and len(grouped_events) > 0:
        print(f"\n{'='*60}")
        print(f"RESUMEN DE PROCESAMIENTO")
        print(f"{'='*60}")
        print(f"Eventos totales leídos: {valid_events}")
        print(f"Grupos de coincidencia: {len(grouped_events)}")
        print(f"\nDistribución de coincidencias:")
        print(f"  Singles (1 detector): {singles} ({100*singles/len(grouped_events):.1f}%)")
        print(f"  Dobles (2 detectores): {doubles} ({100*doubles/len(grouped_events):.1f}%)")
        print(f"  Triples (3 detectores): {triples} ({100*triples/len(grouped_events):.1f}%)")
        print(f"  Cuádruples (4 detectores): {quads} ({100*quads/len(grouped_events):.1f}%)")
        if more > 0:
            print(f"  Más de 4 detectores: {more}")
        print(f"{'='*60}\n")
    
    return {
        'total_events': valid_events,
        'total_groups': len(grouped_events),
        'singles': singles,
        'doubles': doubles,
        'triples': triples,
        'quads': quads,
        'more': more,
        'channel_stats': channel_stats,
        'total_time_s': total_time_s,
        'total_time_ps': total_time_ps
    }

def process_multiple_bin_files(file_list, output_file, window_ns=100, max_events=None, verbose=True):
    """
    Procesa múltiples archivos .bin y los combina en un solo archivo de salida
    """
    all_events = []
    total_valid_events = 0
    channel_stats_global = {}
    first_timestamp_global = None
    last_timestamp_global = None
    
    if verbose:
        print(f"Ventana de coincidencia: {window_ns} ns\n")
    
    # Leer todos los archivos
    for idx, input_file in enumerate(file_list, 1):
        if verbose:
            print(f"Leyendo archivo {idx}/{len(file_list)}: {Path(input_file).name}")
        
        events_in_file = 0
        
        with open(input_file, 'rb') as f:
            # Leer header
            read_bin_header(f)
            
            while True:
                event = read_bin_event(f)
                if event is None:
                    break
                
                all_events.append(event)
                events_in_file += 1
                total_valid_events += 1
                
                # Actualizar timestamps globales
                if first_timestamp_global is None:
                    first_timestamp_global = event['timestamp']
                last_timestamp_global = event['timestamp']
                
                # Actualizar estadísticas por canal
                ch = event['channel']
                
                if ch not in channel_stats_global:
                    channel_stats_global[ch] = {
                        'count': 0,
                        'detector': event['detector']
                    }
                
                channel_stats_global[ch]['count'] += 1
                
                if max_events and total_valid_events >= max_events:
                    break
        
        if verbose:
            print(f"  Eventos leídos: {events_in_file}")
        
        if max_events and total_valid_events >= max_events:
            print(f"Alcanzado el límite de {max_events} eventos")
            break
    
    # Calcular tiempo total
    if first_timestamp_global is not None and last_timestamp_global is not None:
        total_time_ps = last_timestamp_global - first_timestamp_global
        total_time_s = total_time_ps / 1e12
    else:
        total_time_ps = 0
        total_time_s = 0
    
    if verbose:
        print(f"\nTotal de archivos procesados: {len(file_list)}")
        print(f"Total de eventos válidos: {total_valid_events}")
        print(f"Tiempo total: {total_time_s:.2f} segundos")
    
    # Ordenar todos los eventos por timestamp
    if verbose:
        print(f"\nOrdenando {len(all_events)} eventos por timestamp...")
    all_events.sort(key=lambda x: x['timestamp'])
    
    # Agrupar eventos por coincidencia
    if verbose:
        print(f"Agrupando eventos por ventana de {window_ns} ns...")
    
    grouped_events = group_events_by_coincidence(all_events, window_ns)
    
    # Escribir archivo de salida
    if verbose:
        print(f"\nEscribiendo archivo de salida: {output_file}")
    
    with open(output_file, 'wb') as f:
        for group in grouped_events:
            for event in group:
                det = event['detector'] & 0xFF
                energy = event['energy'] & 0xFFFF
                #f.write(struct.pack('>HH', det, energy))
                f.write(struct.pack('<HH', det, energy))
            f.write(b'\xFF\xFF')
    
    # Calcular estadísticas de coincidencias
    singles = sum(1 for g in grouped_events if len(g) == 1)
    doubles = sum(1 for g in grouped_events if len(g) == 2)
    triples = sum(1 for g in grouped_events if len(g) == 3)
    quads = sum(1 for g in grouped_events if len(g) == 4)
    more = sum(1 for g in grouped_events if len(g) > 4)
    
    if verbose:
        print(f"\nResumen de coincidencias:")
        print(f"  Singles: {singles}")
        print(f"  Dobles: {doubles}")
        print(f"  Triples: {triples}")
        print(f"  Cuádruples: {quads}")
    
    return {
        'total_events': total_valid_events,
        'total_groups': len(grouped_events),
        'singles': singles,
        'doubles': doubles,
        'triples': triples,
        'quads': quads,
        'more': more,
        'files_processed': len(file_list)
    }

def convert_caen_bin(input_file, output_file=None, window_ns=100, max_events=None, verbose=True, auto_detect=False):
    """
    Función principal para convertir archivos .bin CAEN
    
    Parámetros:
    -----------
    input_file : str o list
        - str con wildcards ('*.bin'): procesa todos los coincidentes
        - str sin wildcards: procesa solo ese archivo (a menos que auto_detect=True)
        - list: procesa exactamente esos archivos
    output_file : str
        Archivo de salida (default: basado en input)
    window_ns : float
        Ventana de coincidencia en nanosegundos
    max_events : int
        Número máximo de eventos a procesar
    verbose : bool
        Mostrar información detallada
    auto_detect : bool
        Si True, busca automáticamente archivos relacionados (default: False)
    """
    import glob
    
    # Determinar lista de archivos a procesar
    if isinstance(input_file, list):
        file_list = input_file
    elif '*' in str(input_file):
        file_list = sorted(glob.glob(str(input_file)))
        if not file_list:
            raise FileNotFoundError(f"No se encontraron archivos con el patrón: {input_file}")
    else:
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"El archivo {input_file} no existe")
        
        if auto_detect:
            base_pattern = str(input_path).rsplit('-', 1)[0] + '-*.bin'
            related_files = sorted(glob.glob(base_pattern))
            if len(related_files) > 1:
                if verbose:
                    print(f"Auto-detectados {len(related_files)} archivos relacionados")
                file_list = related_files
            else:
                file_list = [input_file]
        else:
            file_list = [input_file]
    
    # Determinar archivo de salida
    if output_file is None:
        if len(file_list) == 1:
            output_file = str(Path(file_list[0]).stem) + '.fil'
        else:
            base_name = Path(file_list[0]).stem.rsplit('-', 1)[0]
            output_file = base_name + '.fil'
    
    if verbose:
        if len(file_list) > 1:
            print(f"\n{'='*60}")
            print(f"PROCESAMIENTO DE MÚLTIPLES ARCHIVOS")
            print(f"{'='*60}")
            print(f"Archivos a procesar: {len(file_list)}")
            for f in file_list[:5]:
                print(f"  - {Path(f).name}")
            if len(file_list) > 5:
                print(f"  ... y {len(file_list)-5} más")
            print(f"Archivo de salida: {output_file}")
            print(f"{'='*60}\n")
    
    # Procesar archivos
    if len(file_list) == 1:
        return process_bin_file(
            file_list[0], 
            output_file,
            window_ns=window_ns,
            max_events=max_events,
            verbose=verbose
        )
    else:
        return process_multiple_bin_files(
            file_list,
            output_file,
            window_ns=window_ns,
            max_events=max_events,
            verbose=verbose
        )

def show_sample_events(input_file, n_events=10):
    """
    Muestra los primeros n eventos del archivo para inspección
    """
    print(f"\n{'='*80}")
    print(f"MUESTRA DE EVENTOS - {input_file}")
    print(f"{'='*80}\n")
    
    with open(input_file, 'rb') as f:
        # Leer header
        read_bin_header(f)
        
        print(f"{'#':<5} {'Board':<8} {'Canal':<8} {'Detector':<10} {'Timestamp (ps)':<18} {'Energy':<10} {'Flags':<10}")
        print("-" * 80)
        
        for i in range(n_events):
            event = read_bin_event(f)
            if event is None:
                print(f"Fin del archivo después de {i} eventos")
                break
            
            print(f"{i+1:<5} {event['board']:<8} {event['channel']:<8} {event['detector']:<10} "
                  f"{event['timestamp']:<18} {event['energy']:<10} {event['flags']:<#10x}")
    
    print(f"\n{'='*80}\n")

def main():
    """
    Función principal para línea de comandos o Jupyter
    """
    # Detectar si estamos en Jupyter
    try:
        __IPYTHON__
        print("Detectado entorno Jupyter/IPython")
        print("\nUso:")
        print("  # Convertir archivo con ventana de 100 ns")
        print("  stats = convert_caen_bin('archivo.bin', window_ns=100)")
        print("")
        print("  # Ver primeros eventos")
        print("  show_sample_events('archivo.bin', n_events=5)")
        print("")
        print("  # Procesar con ventana de 50 ns y máximo 10000 eventos")
        print("  stats = convert_caen_bin('archivo.bin', window_ns=50, max_events=10000)")
        return
    except NameError:
        pass
    
    # Modo línea de comandos
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convierte archivos .bin CAEN al formato de coincidencias'
    )
    parser.add_argument('input_file', help='Archivo .bin de entrada')
    parser.add_argument('-o', '--output', help='Archivo de salida (default: .fil)')
    parser.add_argument('-w', '--window', type=float, default=100,
                      help='Ventana de coincidencia en ns (default: 100)')
    parser.add_argument('-n', '--max-events', type=int,
                      help='Número máximo de eventos a procesar')
    parser.add_argument('--show-sample', action='store_true',
                      help='Mostrar eventos de muestra')
    
    args = parser.parse_args()
    
    if args.show_sample:
        show_sample_events(args.input_file)
    
    convert_caen_bin(
        args.input_file,
        output_file=args.output,
        window_ns=args.window,
        max_events=args.max_events
    )

if __name__ == '__main__':
    main()