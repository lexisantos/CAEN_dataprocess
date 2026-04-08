#import ROOT para manipular archivos root (conda activate {nombre del environment con root})
import struct
import glob, os, bisect
import pandas as pd
import numpy as np
import seaborn.objects as so
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from scipy.signal import find_peaks

#%% General

def filter_hist(df_hist, counts_min = 0, counts_max = np.inf, ch_min = 0, ch_max = np.inf, x_col = 'Energy_Ch'):
    df_hist = df_hist[(df_hist[x_col] <= ch_max) & (df_hist[x_col] >= ch_min) & (df_hist.Counts >= counts_min) & (df_hist.Counts <= counts_max)]
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
        df_prov['Channel'] = ch
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
                       columns = ['Board', 'Channel', 'Timestamp', 'Energy', 'Flag'])
    #df['Timestamp'] = df['Timestamp']/1E12
    return df

def hist_bin(df_bin):
    df_hist = (df_bin.groupby(['Channel', 'Energy_Ch'], as_index=False)
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
            n = df_bin.Channel.nunique()
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
    for ch in dfBIN_hist.Channel.unique():
        picos[ch] = find_peaks(dfBIN_hist[dfBIN_hist.Channel == ch].Counts.values, width = limits_w, height = limits_h)
    return picos

def apply_calibration_en(df, df_coef, col = 'Energy', move_old_to = '', new = 'Energy'):
    if move_old_to != '':
        df[move_old_to] = df[col].values
    df[new] = df[col].astype(float)
    coef_dict = df_coef.set_index('det').to_dict(orient='index')
    for det in df['Channel'].unique():
        coef = coef_dict[det]
        df.loc[df['Channel'] == det, new] = (
            df.loc[df['Channel'] == det, new]
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

def df_coincidences(dfBIN, det_E, det_dE, window_ns, Energy_col = ['Energy_ch', 'Energy']):    
    dfBIN_dE = dfBIN[dfBIN.Channel == det_dE].sort_values(by = 'Timestamp')
    dfBIN_E = dfBIN[dfBIN.Channel == det_E].sort_values(by = 'Timestamp')
    
    df_coinc = pd.DataFrame(find_coincidences(dfBIN_E, dfBIN_dE, window_ns*1E3), columns = ['i', 'j'])
    for col in Energy_col:
        df_coinc[f'{col}_E'] = dfBIN_E.iloc[df_coinc.i][col].values
        df_coinc[f'{col}_dE'] = dfBIN_dE.iloc[df_coinc.j][col].values

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

def graph_coincidences(df_coinc, nro_bins: int = 200, Energy_col = 'Energy', add_both = False):
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

    plt.pcolormesh(
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
    return counts, x_edges, y_edges


def graph_hist(df_bin, hist_root_dict, folder, name = 'Figure', window = 100, save_fig = False):
    save_fig_in = '/Graficos_root_bin'
    create_folder(folder+save_fig_in)
    plt.figure()
    plt.grid(True, ls = '--')
    plt.xlabel('Channel')
    plt.ylabel('Counts')
    for key in list(hist_root_dict.keys()):
        if 'Energy' in key:      
            plt.clf()
            plt.plot(hist_root_dict[key].bins_center, hist_root_dict[key].counts, '.-', label = '.root')
            plt.plot(df_bin.Energy, df_bin.Counts, '.-', label = '.BIN')
            
            plt.tight_layout()
            plt.legend()
            try:
                plt.xlim((df_bin.Energy.min() - window, df_bin.Energy.max() + window))
            except:
                plt.xlim((1700, 1950))
        if save_fig:
            plt.savefig(folder+save_fig_in+'/'+name, format = 'png')
        else:
            plt.show()
    plt.close()


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