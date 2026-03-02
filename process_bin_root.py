#import ROOT para manipular archivos root (conda activate {nombre del environment con root})
import struct
import glob 
import pandas as pd
import numpy as np
import seaborn.objects as so

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
    dfKeys = pd.DataFrame(dictKeys)
    return dfKeys

def get_histograms(rootfile):
    df = encuentraObjetos(rootfile)
    df_histograms = df[df.ClassName == 'TH1D'].reset_index(drop=True)
    paths = df_histograms.Path.values
    dict_datos = {}
    for path in paths:
        obj = rootfile.Get(path)
        if not obj:
            print("Histogram not found in", path)
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

    df_test = pd.DataFrame([[*line] for line in iter_data], 
                       columns = ['Board', 'Channel', 'Timestamp', 'Energy', 'Flag'])
    df_test['Timestamp'] = df_test['Timestamp']/1E12
    return df_test

#%% Finding .BIN and .root archives

def find_archives(path_origin, extension: str = ".BIN"):
    archives = glob.glob("**/RAW/*"+extension, root_dir= path_origin, recursive=True)
    df = (pd.DataFrame([path.split('/') for path in archives], columns = ['run', 'RAW', 'filename'])
          .drop(columns = ['RAW'], axis = 1)
          .groupby('run', as_index= False)
          .agg(counts = ("filename", "count"))
          .rename(columns = {'counts': f"{extension[1:]}_counts"}))
    return df

def info_BIN_ROOT(folder, path_origin, save_csv = False):
    bins = find_archives(path_origin)
    roots = find_archives(path_origin, extension=".root")
    df_merged = pd.merge(roots, bins, how = 'outer', on = 'run').fillna(0)
    if save_csv:
        df_merged.to_csv(path_origin(folder)+f'{folder}_info_archives.csv')
    return df_merged