import ROOT 
import pandas as pd
import numpy as np
import seaborn.objects as so

binpath = '/media/cneafipams/Class_Lexi/Datos CNEA/[CAC] Protonterapia/2025_11_protonterapia/20251125-protonterapia/DAQ/20250822_37/RAW/SDataR_20250822_37.BIN'
rootpath = '/media/cneafipams/Class_Lexi/Datos CNEA/[CAC] Protonterapia/2025_11_protonterapia/20251125-protonterapia/DAQ/20250822_37/RAW/HcompassR_20250822_37_20251125_181722.root'

file = ROOT.TFile.Open(rootpath)

def encuentraObjetos(dir_obj, path="", dictKeys = {'Name':[], 'ClassName': [], 'Path': []}):    
    for key in dir_obj.GetListOfKeys():
        name = key.GetName()
        class_name = key.GetClassName()
        full_path = f"{path}/{name}"

        dictKeys['Name'] += [name] 
        dictKeys['ClassName'] += [class_name]
        dictKeys['Path'] += [full_path]

        if class_name == "TDirectoryFile":
            subdir = dir_obj.Get(name)
            dictKeys = encuentraObjetos(subdir, full_path, dictKeys = dictKeys)
    return dictKeys

dfKeys = pd.DataFrame(encuentraObjetos(file))
print(dfKeys)

def get_histograms(df, rootfile):
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

dict_histogramas = get_histograms(dfKeys, file)
dict_energy_tiempo = {}

for key, df in dict_histogramas.items():
    name = 'Energy' if 'Energy' in key else 'Tiempo'
    if name == 'Energy':
        (
            so.Plot(data = df, x = 'bins_center', y = 'counts')
            .add(so.Dot())
            .add(so.Line())
            .label(x = key, y = 'Counts')
            .show()
        )
    dict_energy_tiempo[name] = df.bins_center

df_energy_tiempo = pd.DataFrame(dict_energy_tiempo)
df_energy_tiempo = df_energy_tiempo/1E12

(
    so.Plot(data = df_energy_tiempo, x = 'Tiempo', y = 'Energy')
    .add(so.Dot())
    .add(so.Line())
    .label(x = 'Time [s]', y = 'Channel')
    .show()
)
