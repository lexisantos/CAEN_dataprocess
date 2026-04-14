#import ROOT para manipular archivos root (conda activate {nombre del environment con root})
import struct
import glob, os, bisect
import pandas as pd
import numpy as np
import seaborn.objects as so
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from scipy.signal import find_peaks
from plotly import express as px
import plotly.graph_objects as go

#%% General

def filter_hist(df_hist, counts_min = 0, counts_max = np.inf, ch_min = 0, ch_max = np.inf, Ch_col = 'Energy_Ch'):
    df_hist = df_hist[(df_hist[Ch_col] <= ch_max) & (df_hist[Ch_col] >= ch_min) & (df_hist.Counts >= counts_min) & (df_hist.Counts <= counts_max)]
    return df_hist

#%% Process .root
def encuentraObjetos(rootfile, path="", dictKeys = {'Name':[], 'ClassName': [], 'Path': []}):    
    for key in rootfile.GetListOfKeys():
        name = key.GetName()
        class_name = key.GetClassName()
        full_path = f"{path}/{name}"

        dictKeys['Name'] += [name] 
        dictKeys['ClassName'] += [class_name]
        dictKeys['Path'] += [full_path]
        if class_name == "TDirectoryFile":
            subdir = rootfile.Get(name)
            dictKeys = encuentraObjetos(subdir, full_path, dictKeys = dictKeys)
    return dictKeys

def get_histograms(rootfile):
    df = pd.DataFrame(encuentraObjetos(rootfile))
    df_histograms = df[df.ClassName == 'TH1D'].reset_index(drop=True)
    paths = df_histograms.Path.values
    dict_datos = {}
    for path in paths:
        obj = rootfile.Get(path)
        if not obj:
            dict_datos[path] = pd.DataFrame({'bins_center': [0], 
                                             'counts': [0], 
                                             'error': [0]})
        else:
            nbins = obj.GetNbinsX()
            x = np.array([obj.GetBinCenter(i) for i in range(1, nbins+1)])
            y = np.array([obj.GetBinContent(i) for i in range(1, nbins+1)])
            err = np.array([obj.GetBinError(i) for i in range(1, nbins+1)])
            dict_datos[path] = pd.DataFrame({'bins_center': x, 
                                             'counts': y, 
                                             'error': err})
    return dict_datos

def hist_root(rootfile):
    dict_histograms = get_histograms(rootfile)
    keys = [key for key in list(dict_histograms.keys()) if key.startswith('/Energy/')]
    nro_ch = [int(key.split('CH')[1][0]) for key in keys]
    dfs = []

    for key, ch in zip(keys, nro_ch):
        df_prov = dict_histograms[key].copy()
        df_prov['Ch_Det'] = ch
        dfs.append(df_prov)

    dfROOT = pd.concat(dfs, ignore_index=True)
    return dfROOT

def hist_energy(rootfile, graph = True):
    dict_histogramas = get_histograms(rootfile)
    dict_energy_tiempo = {}

    for key, df in dict_histogramas.items():
        name = 'Energy' if 'Energy' in key else 'Tiempo'
        if name == 'Energy' and graph:
            (
                so.Plot(data = df, x = 'bins_center', y = 'counts')
                .add(so.Dot())
                .add(so.Line())
                .label(title = key, x = name, y = 'Counts')
                .show()
            )
        dict_energy_tiempo[name] = df.bins_center

    df_energy_tiempo = pd.DataFrame(dict_energy_tiempo)
    df_energy_tiempo.Tiempo = df_energy_tiempo.Tiempo/1E12

    return df_energy_tiempo

#%% Process .bin
def bin_to_df(filepath):
    with open(filepath, 'rb') as archive:
        header = archive.read(2)
        iter_data = struct.iter_unpack('<HHQHI', archive.read())

    df = pd.DataFrame([[*line] for line in iter_data], 
                       columns = ['Board', 'Ch_Det', 'Timestamp', 'Energy_Ch', 'Flag'])
    #df['Timestamp'] = df['Timestamp']/1E12
    return df

def hist_bin(df_bin, Ch_col = 'Energy_Ch'):
    df_hist = (df_bin.groupby(['Ch_Det', Ch_col], as_index=False)
               .agg(
                   Counts = ('Flag', "count")
            )).reset_index(drop = True)
    return df_hist

def BIN_files_classifier(filepath, arr_run_BINs):
    empty_BINs = []
    with_more_ch = {}
    broken_BINs = []

    for run in arr_run_BINs:
        str_bin = filepath + run + "/RAW/*.BIN"
        try:
            binpath = glob.glob(str_bin)[0]
            df_bin = bin_to_df(binpath)
        except Exception:
            broken_BINs.append(run)
            continue

        if df_bin.empty:
            empty_BINs.append(run)
        else:
            n = df_bin.Ch_Det.nunique()
            with_more_ch.setdefault(n, []).append(run)
    return broken_BINs, empty_BINs, with_more_ch

def create_BIN_resumen(filepath):
    runs_only_BIN = folders_has_both(filepath, nro_root=0, nro_BIN=1)
    broken_BINs, empty_BINs, with_more_ch = BIN_files_classifier(filepath, runs_only_BIN)
    resumen = {
        'empty': empty_BINs,
        'broken': broken_BINs,   
    }
    for ii, values in with_more_ch.items():
        resumen[f'{ii}_ch'] = values
    return resumen

def BIN_sanity(filepath, name_csv = 'data_BIN_sanity.csv'):
    if os.path.isfile(filepath + name_csv):
        df = pd.read_csv(filepath + name_csv)
        resumen = {col: df[col].dropna().tolist() for col in df}
    else:
        resumen = create_BIN_resumen(filepath)
        pd.DataFrame.from_dict(resumen, orient= 'index').transpose().to_csv(filepath + name_csv, index=False)
    return resumen


#%% Finding .BIN and .root archives

def find_archives(path_origin, extension: str = ".BIN"):
    archives = glob.glob("**/RAW/*"+extension, root_dir= path_origin, recursive=True)
    df = (pd.DataFrame([path.split('/') for path in archives], columns = ['run', 'RAW', 'filename'])
          .drop(['RAW'], axis = 1)
          .groupby('run', as_index= False)
          .agg(counts = ("filename", "count"))
          .rename(columns = {'counts': f"{extension[1:]}_counts"}))
    return df

def info_BIN_ROOT(path_origin, save_csv = False):
    bins = find_archives(path_origin)
    roots = find_archives(path_origin, extension=".root")
    df_merged = pd.merge(roots, bins, how = 'outer', on = 'run').fillna(0)
    if save_csv:
        df_merged.to_csv(path_origin+f'info_archives.csv')
    return df_merged

def folders_has_both(path_origin: str, nro_BIN: int = 1, nro_root: int = 1):
    '''
    Returns an array of strings.
    '''
    df_folder = info_BIN_ROOT(path_origin)
    runs_with_both = df_folder[(df_folder.root_counts >= nro_BIN) & (df_folder.BIN_counts >= nro_root)].run.values
    return runs_with_both

#%% Calibration

def calibration_ch_en(dfBIN_hist, limits_w = (10, 50), limits_h = (0, np.inf)):
    picos = {}
    for ch in dfBIN_hist.Ch_Det.unique():
        picos[ch] = find_peaks(dfBIN_hist[dfBIN_hist.Ch_Det == ch].Counts.values, width = limits_w, height = limits_h)
    return picos

def apply_calibration_en(df, df_coef, old = 'Energy_Ch', new = 'Energy'):
    '''
    Mapea valores de canales a Energía  partir de los coeficientes de calibración (ec. lineal).

    Input:
        df: DataFrame
        df_coef: DataFrame
            Coeficientes de calibración.

        old: str or dict (D = 'Energy_Ch')
            Columna que será mapeada | Canales de energía.
            Si es un dict, debe indicar a qué detector pertenece cada columna (acorde a la diferenciación en df_coef)
        new: str (D = 'Energy')
            Nombre de nueva(s) columna(s) | Energías en MeV
    
    Output:
        df: DataFrame.
            Columna nueva de energías agregada.

    '''
    coef_dict = df_coef.set_index('det').to_dict(orient='index')
    if type(old) == dict:
        for col, det in old.items():
            coef = coef_dict[det]
            df[col.replace('Energy_Ch', new)] = df[col].map(lambda x: coef['m'] * x + coef['b'])
    else:
        df[new] = df[old].astype(float)
        for det in df['Ch_Det'].unique():
            coef = coef_dict[det]
            df.loc[df['Ch_Det'] == det, new] = (
                df.loc[df['Ch_Det'] == det, new]
                .map(lambda x: coef['m'] * x + coef['b'])
            )
    return df
 
#%% Coincidences

def find_coincidences(df_0, df_1, window_ps):
    coincidences = []
    for i, t in enumerate(df_0.Timestamp.values):
        left = bisect.bisect_left(df_1.Timestamp.values, t - window_ps/2)
        right = bisect.bisect_right(df_1.Timestamp.values, t + window_ps/2)
        for j in range(left, right):
            coincidences.append((i, j))
    return coincidences

def df_coincidences(dfBIN, det_E, det_dE, window_ns):    
    dfBIN_dE = dfBIN[dfBIN.Ch_Det == det_dE].sort_values(by = 'Timestamp')
    dfBIN_E = dfBIN[dfBIN.Ch_Det == det_E].sort_values(by = 'Timestamp')
    
    df_coinc = pd.DataFrame(find_coincidences(dfBIN_E, dfBIN_dE, window_ns*1E3), columns = ['i', 'j'])
    df_coinc['Energy_Ch_E'] = dfBIN_E.iloc[df_coinc.i].Energy_Ch.values
    df_coinc['Energy_Ch_dE'] = dfBIN_dE.iloc[df_coinc.j].Energy_Ch.values

    return df_coinc

#%% Saving Graphs

def create_folder(folder_name):
    if not os.path.exists(folder_name):
        try:
            os.mkdir(folder_name)
            print(f"Folder '{folder_name}' created.")
        except OSError as e:
            print(f"Error creating folder: {e}")
    else:
        print(f"Folder '{folder_name}' already exists.")

def graph_coincidences(df_coinc, nro_bins: int = 200, Energy_col = 'Energy', add_both = False, plot_by = 'matplotlib'):
    E_arr = df_coinc[f'{Energy_col}_E'].values
    if add_both:
        dE_arr = df_coinc[f'{Energy_col}_dE'].values + E_arr
        y_lab = f'(E + dE) [MeV]' 
    else:
        dE_arr = df_coinc[f'{Energy_col}_dE'].values
        y_lab = f'dE [MeV]'
    
    counts, x_edges, y_edges = np.histogram2d(
            E_arr, 
            dE_arr,
            bins= nro_bins  
        )
    if plot_by == 'matplotlib':
        fig = plt.pcolormesh(
        x_edges,
        y_edges,
        counts.T,
        cmap='viridis',
        shading='auto',
        norm = LogNorm(vmin=1, vmax=counts.max()) # or use counts_masked = np.ma.masked_where(counts == 0, counts) instead

        )

        plt.colorbar()
        plt.xlabel(f'E [MeV]')
        plt.ylabel(y_lab)
        plt.show()
    
    elif plot_by == 'plotly':
        z = np.where(counts == 0, np.nan, counts)
        fig = go.Figure(
            data=go.Heatmap(
                x=x_edges,
                y=y_edges,
                z=np.log10(z).T,
                colorscale="Viridis",
                colorbar=dict(title="Counts")
            )
        )

        tickvals = np.arange(0, np.ceil(np.log10(np.nanmax(z)) + 1))
        ticktext = ["1", "10"] + [f"10^{int(t)}" for t in tickvals[2:]] if tickvals.size > 2 else ["1", "10"]

        fig.update_traces(
            colorbar=dict(
                title = 'Counts',
                tickvals = tickvals,
                ticktext = ticktext
            )
        )
        fig.update_layout(
            xaxis_title="E [MeV]",
            yaxis_title=y_lab,
            width=600,
            height=600
        )

        fig.show()
        
    else: 
        fig = None

    find_max = lambda data: np.unravel_index(np.argmax(data, axis=None), data.shape)

    imax, jmax = find_max(counts)
    print('Maximo en', 'E:', E_arr[imax], f'MeV | {y_lab[:-6]}:', dE_arr[jmax], 'MeV')
    return fig


def graph_data_BIN_hist_filt(dfBIN_hist_filt, plot_by = 'matplotlib'):
    if plot_by == 'plotly':
        fig = px.scatter(data_frame= dfBIN_hist_filt, x = 'Energy', y = 'Counts', color = dfBIN_hist_filt.Ch_Det.astype(str),
                title = 'From BIN archive', labels={'Energy': 'Energy [MeV]'})
        fig.show()

    elif plot_by == 'seaborn':
        fig = (
            so.Plot(data = dfBIN_hist_filt, x = 'Energy', y = 'Counts', color = dfBIN_hist_filt.Ch_Det.astype(str))
            .add(so.Dot())
            .label(x = 'Energy [MeV]', y = 'Counts of events [a.u.]', title = 'From BIN archive')
            .show()
        )
    else:
        fig = None
    return fig

def graph_coincidences_hist(run, df_coincidences, plot_by = 'matplotlib', E_col = 'Energy_E', 
                            dE_col = 'Energy_dE', title = None, show = True):
    df_coincidences['E+dE'] = df_coincidences[E_col] + df_coincidences[dE_col]
    
    if plot_by == 'plotly':
        fig = px.histogram(data_frame= df_coincidences, x = 'E+dE', barmode= 'overlay',
                    title = title, labels={'Energy': 'Energy [MeV]'})
    elif plot_by == 'seaborn':
        fig = (
            so.Plot(data = df_coincidences, x = 'E+dE')
            .add(so.Bar(), so.Hist())
            .label(x = 'Energy [MeV]', y = 'Counts of events [a.u.]', title = run)
        )
    else:
        fig = plt.figure()
    
    if show:
        fig.show()

    return fig


#%% Generalization

def run_data_BIN(run, path, calibration = False, name = 'Default', E_dE = (0, 1),
                 filter = {'counts_min': 1, 'ch_min': 1, 'ch_max': 700},
                 run_coincidences = True, window_ns = 600):
    '''
    Define distintos Dataframes a partir del nombre del run y el path donde se encuentran.

    Input:
        run: str
        path: str.
            Ruta absoluta de la carpeta donde se encuentra el run, debe terminar con '/'. En mis ejemplos debería ser path(folder)

        calibration: bool or str (D = False). 
            Si es un bool, se asume que no hay calibración. Si es un str, se asume que es la ruta del archivo .csv con los coeficientes.
        name: str (D = 'Default'). 
            Nombre para guardar/leer los archivos de coincidencias (si run_coincidences es True).
        E_dE: tupla (D = (0, 1)). 
            Número del "canal" para cada detector (E, dE).
        filter: dict (D = {'counts_min': 1, 'ch_min': 1, 'ch_max': 700}).
            Parámetros para filtrar el histograma (counts_min, ch_min, ch_max).
        run_coincidences: bool (D = True).
            Si es True, se buscan coincidencias entre los detectores E y dE.
        window_ns: int (D = 600).
            Ventana de coincidencia en ns.

    Output:
        dfBIN: DataFrame con los datos del archivo .BIN, con la columna de canales de energía.
        dfBIN_hist_filt: DataFrame con el histograma filtrado, con la columna de energía
        df_coinc_wo_0: DataFrame con las coincidencias entre los detectores E y dE, sin las filas del canal de energía 0.    
    '''
    pathBIN = glob.glob(path + run + '/RAW/*.BIN')[0]
    dfBIN = bin_to_df(pathBIN)
    dfBIN_hist = hist_bin(dfBIN)
    dfBIN_hist_filt = filter_hist(dfBIN_hist, counts_min=filter['counts_min'], ch_min=filter['ch_min'], ch_max=filter['ch_max'])

    if run_coincidences:
        try:
            df_coinc_wo_0 = pd.read_csv(path + run + f'/{name}_coincidences.csv') 
        except:
            df_coinc = df_coincidences(dfBIN, det_E = E_dE[0], det_dE = E_dE[1], window_ns = window_ns)
            df_coinc_wo_0 = df_coinc[(df_coinc.Energy_Ch_E > 0) & (df_coinc.Energy_Ch_dE > 0)]
            df_coinc_wo_0.to_csv(path + run + f'/{name}_coincidences.csv', index = False)
    else:
        df_coinc_wo_0 = pd.DataFrame(np.zeros(6), 
                                     columns = ['i', 'j', 'Energy_Ch_E', 'Energy_Ch_dE'])

    if type(calibration) == str:
        df_coef = pd.read_csv(calibration)
        dfBIN = apply_calibration_en(dfBIN, df_coef)
        dfBIN_hist_filt = apply_calibration_en(dfBIN_hist_filt, df_coef)
        df_coinc_wo_0 = apply_calibration_en(df_coinc_wo_0, df_coef, 
                                             old = {'Energy_Ch_E': E_dE[0], 'Energy_Ch_dE': E_dE[1]})

    return dfBIN, dfBIN_hist_filt, df_coinc_wo_0




#%% Precindible

'''
#Barrido de ventana

windows = np.arange(400, 750, 50)*1E3 #ns -> ps
coincidences_ch0ch1 = {}

for window in windows.astype(int):
    coincidences_ch0ch1[str(window)] = find_coincidences(dfBIN_ch0, dfBIN_ch1, window)

plt.figure()
chosen_w = 0

for key, value in coincidences_ch0ch1.items():
    print('Con ventana de', float(key)/1E3, 'ns se tienen', len(value), 'coincidencias')
    if len(value) <= min(len(dfBIN_ch0), len(dfBIN_ch1)) or float(chosen_w) == 0.:
        chosen_w = key
    plt.plot(float(key)/1E3, len(value), 'ko')

plt.xlabel('Ventana [ns]')
plt.ylabel('# Coincidencias')
'''