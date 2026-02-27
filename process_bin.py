
#%%
'''
OLD CODE

import os, struct, glob

import sys
sys.path.append('/media/cneafipams/Class_Lexi/')
#from Codigos_py.Repositorio.procesado_compass import read_bin_event

#import pandas as pd

path = '/media/cneafipams/Class_Lexi/Datos CNEA/[CAC] Protonterapia/2025_11_protonterapia/20251127-pterapia/DAQ/'
path_save = '/media/cneafipams/Class_Lexi/Datos CNEA/[CAC] Protonterapia/2025_11_protonterapia/20251127-pterapia/20251127-pterapia/datos_csv'



def bin_to_df(filepath):
    with open(filepath, 'rb') as archive:
        header = archive.read(2)
        iter_data = struct.iter_unpack('<HHQHI', archive.read())

    df_test = pd.DataFrame([[*line] for line in iter_data], 
                       columns = ['Board', 'Channel', 'Timestamp', 'Energy', 'Flag'])
    df_test['Timestamp'] = df_test['Timestamp']/1E12
    return df_test

df_bin = bin_to_df(binpath)


(
    so.Plot(data = df_bin, x = 'Timestamp', y = 'Energy')
    .add(so.Dot())
    .add(so.Line())
    .label(x = 'Time [s]', y = 'Channel')
    .show()
)

try:
    os.makedirs(path_save, exist_ok=True)
except OSError as e:
    print(f"Error creating folder: {e}")

def bin_to_csv(filepath):
    with open(filepath, 'rb') as archive:
        header = archive.read(2)
        iter_data = struct.iter_unpack('<HHQHI', archive.read())

    df_test = pd.DataFrame([[*line] for line in iter_data], 
                       columns = ['Board', 'Channel', 'Timestamp', 'Energy', 'Flag'])
    df_test['Timestamp'] = df_test['Timestamp']/1E12

    df_test.to_csv(path_save[:-4]+ f'_head_{header.hex()}_'+'.csv')

list_paths = os.listdir(path)
print(list_paths)


binpath = '/media/cneafipams/Class_Lexi/Datos CNEA/[CAC] Protonterapia/2025_11_protonterapia/20251125-protonterapia/DAQ/20250822_37/RAW/SDataR_20250822_37.BIN'
rootpath = '/media/cneafipams/Class_Lexi/Datos CNEA/[CAC] Protonterapia/2025_11_protonterapia/20251125-protonterapia/DAQ/20250822_37/RAW/HcompassR_20250822_37_20251125_181722.root'

#'/media/cneafipams/Class_Lexi/Datos CNEA/[CAC] Protonterapia/2025_11_protonterapia/20251125-protonterapia/DAQ/20251031_run_47/RAW/HcompassR_20251031_run_47_20251125_193609.root'


import ROOT
tfile = ROOT.Tfile.Open(rootpath)
#tree = tfile.Get('Channel')


#print(struct.calcsize('<HQHHHII'))

with open(binpath, 'rb') as archive_bin:
        header = archive_bin.read(2)
        data_bin = struct.unpack('<HHQHI', archive_bin.read(18))

print(header.hex())
print(data_bin)

with open(rootpath, 'rb') as archive_root:
        header = archive_root.read(2)
        test_root = struct.unpack('<hqhhhii', archive_root.read(24))

print(header.hex())
print(test_root)
'''