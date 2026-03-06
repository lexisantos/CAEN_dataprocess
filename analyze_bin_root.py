import ROOT
from process_bin_root import *
import glob


folders = ["20251125-protonterapia", "20251126-pterapia", "20251127-pterapia"]
path = lambda folder: f"/media/cneafipams/Class_Lexi/Datos_CNEA/CAC_Protonterapia/2025_11_protonterapia/{folder}/DAQ/"

BIN_check = BIN_sanity(path(folders[2]))

print(list(BIN_check.keys()))

print('BINs de runs con 2 canales:')
for run in BIN_check['2_ch']:
    print(run)

'''
import seaborn.objects as so

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

'''
#Para comparar histogramas bin y root --- chequeo que estemos desencriptando (unpack from struct) correctamente
#WARNING: no se discrimina por canal

for folder in folders:
    runs_with_both = folders_has_both(folder, path(folder)) #al menos un BIN y un ROOT
    for run in runs_with_both:
        str_root = path(folder)+ run +"/RAW/*.root" 
        str_bin = path(folder)+ run +"/RAW/*.BIN"
        binpath = glob.glob(str_bin)
        rootpath = glob.glob(str_root)
        if len(rootpath) == 1:
            rootfile = ROOT.TFile.Open(rootpath[0])
            hist_root_dict = get_histograms(rootfile)
            df_bin = hist_bin(binpath[0])
            #Se agrega groupby Channel --> antes de graficar separar por caso de canal
            #ROOT tiene en cuenta esta discriminación?
            graph_hist(df_bin, hist_root_dict, path(folder), name = run)
'''
####
'''
    if run == '20251127_run_alpha_11':
        str_root = path(folder)+ run +"/RAW/*.root" 
        rootpath = glob.glob(str_root)
        rootfile = ROOT.TFile.Open(rootpath[0])
        hist_energy(rootfile)            
'''