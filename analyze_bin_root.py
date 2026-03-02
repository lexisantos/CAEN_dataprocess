import ROOT
import seaborn as sns
import seaborn.objects as so
import pandas as pd
from process_bin_root import *
import glob

folders = ["20251125-protonterapia", "20251126-pterapia", "20251127-pterapia"]
path = lambda folder: f"/media/cneafipams/Class_Lexi/Datos_CNEA/CAC_Protonterapia/2025_11_protonterapia/{folder}/DAQ/"

df_folder = info_BIN_ROOT(folders[0], path(folders[0]))
runs_with_both = df_folder[(df_folder.root_counts > 0) & (df_folder.BIN_counts > 0)].run.values

str_root = path(folders[0])+runs_with_both[0]+"/RAW/*.root"
str_bin = path(folders[0])+runs_with_both[0]+"/RAW/*.BIN"

binpath = glob.glob(str_bin)
rootpath = glob.glob(str_root)

print(rootpath[0])

if len(rootpath) == 1:
    rootfile = ROOT.TFile.Open(rootpath[0])
    df_root = encuentraObjetos(rootfile)
    df_bin = bin_to_df(binpath[0])

print(rootfile)

'''
print(df_root.Name.values)
print(df_root.ClassName.values)
print(df_root.Path.values)
'''



'''
(
    so.Plot(data = df_bin, x = 'Timestamp', y = 'Energy')
    .add(so.Dot())
    .add(so.Line())
    .label(x = 'Time [s]', y = 'Channel')
    .show()
)

(
    so.Plot(data = df_energy_tiempo, x = 'Tiempo', y = 'Energy')
    .add(so.Dot())
    .add(so.Line())
    .label(x = 'Time [s]', y = 'Channel')
    .show()
)
'''