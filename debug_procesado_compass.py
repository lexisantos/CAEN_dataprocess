from procesado_compass import *
from process_bin_root import folders_has_both
import glob


folders = ["20251125-protonterapia", "20251126-pterapia", "20251127-pterapia"]
path = lambda folder: f"/media/cneafipams/Class_Lexi/Datos_CNEA/CAC_Protonterapia/2025_11_protonterapia/{folder}/DAQ/"

for folder in folders[:1]:
    runs_with_both = folders_has_both(folder, path(folder))
    print('Full paths for', folder)
    for run in runs_with_both[:1]:
        #str_root = path(folder)+ run +"/RAW/*.root" 
        str_bin = path(folder)+ run +"/RAW/*.BIN"
        binpath = glob.glob(str_bin)
        process_bin_file(binpath[0], output_file='output.BIN')