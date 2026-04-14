#import ROOT para manipular archivos root (conda activate {nombre del environment con root})
import struct
import glob, os
import pandas as pd
import numpy as np
import seaborn.objects as so
import matplotlib.pyplot as plt

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

def hist_energy(rootfile, graph = True):
    dict_histogramas = get_histograms(rootfile)
    dict_energy_tiempo = {}

    for key, df in dict_histogramas.items():
        name = 'Energy' if 'Energy' in key else 'Tiempo'
        if name == 'Energy':
            (
                so.Plot(data = df, x = 'bins_center', y = 'counts')
                .add(so.Dot())
                .add(so.Line())
                .label(title = key, x = name, y = 'Counts')
                .show()
            )
        dict_energy_tiempo[name] = df.bins_center

    df_energy_tiempo = pd.DataFrame(dict_energy_tiempo)
    df_energy_tiempo = df_energy_tiempo/1E12

    return df_energy_tiempo

#%% Process .bin
def bin_to_df(filepath):
    with open(filepath, 'rb') as archive:
        header = archive.read(2)
        iter_data = struct.iter_unpack('<HHQHI', archive.read())

    df = pd.DataFrame([[*line] for line in iter_data], 
                       columns = ['Board', 'Channel', 'Timestamp', 'Energy', 'Flag'])
    df['Timestamp'] = df['Timestamp']/1E12
    return df

def hist_bin(filepath):
    df_bin = bin_to_df(filepath)
    df_hist = (df_bin.groupby('Channel', 'Energy', as_index=False)
               .agg(Counts = ('Flag', "count")))
    return df_hist

def BIN_sanity(filepath):
    runs_only_BIN = folders_has_both(filepath, nro_root=0, nro_BIN=1)
    empty_BINs = []
    with_more_ch = {}
    broken_BINs = []
    for run in runs_only_BIN:
        str_bin = filepath + run +"/RAW/*.BIN"
        try:
            binpath = glob.glob(str_bin)[0]
            df_bin = bin_to_df(binpath)
        except:
            broken_BINs.append(run)
            pass
        if df_bin.empty:
            empty_BINs.append(run)
        else:
            n = len(df_bin.Channel.unique())
            if n in with_more_ch:
                with_more_ch[n] += [run]
            else:
                with_more_ch[n] = [run]
    
    resumen = {
        'empty': empty_BINs,
        'broken': broken_BINs,   
    }
    for ii, values in with_more_ch.items():
        resumen[f'{ii}_ch'] = values
    return resumen


#%% Finding .BIN and .root archives

def find_archives(path_origin, extension: str = ".BIN"):
    archives = glob.glob("**/RAW/*"+extension, root_dir= path_origin, recursive=True)
    df = (pd.DataFrame([path.split('/') for path in archives], columns = ['run', 'RAW', 'filename'])
          .drop(columns = ['RAW'], axis = 1)
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

def folders_has_both(path_origin, nro_BIN = 1, nro_root = 1):
    df_folder = info_BIN_ROOT(path_origin)
    runs_with_both = df_folder[(df_folder.root_counts >= nro_BIN) & (df_folder.BIN_counts >= nro_root)].run.values
    return runs_with_both

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