import pandas as pd
import numpy as np

def cps_window(df, t_vent_seg, E_vent_MeV = [-np.inf, np.inf]):
    t_arr = df[df.Energy.between(*E_vent_MeV)].Timestamp.values
    t_arr = (t_arr - t_arr[0])/1e12
    bins = (t_arr // t_vent_seg).astype(int)
    cps = np.bincount(bins)
    t_s = np.arange(len(cps))*t_vent_seg
    return t_s, cps

def get_counts(df_BIN, det_ch: list[int], window_s, window_E):
    dfs_dict = {}
    for det in det_ch:
        df_BIN_Ch_cps = pd.DataFrame(columns = ['Time [s]', f'Counts_{window_s}s_'])
        t, cps = cps_window(df_BIN[df_BIN.Ch_Det == det], window_s, window_E)
        df_BIN_Ch_cps['Time [s]'] = t
        df_BIN_Ch_cps[f'Counts_{window_s}s_'] = cps
        dfs_dict[det] = df_BIN_Ch_cps
    return dfs_dict

def see_relation(df_BIN, window_s, window_E, dets = [0, 1]):
    df_dict = get_counts(df_BIN[df_BIN.Ch_Det != 3], det_ch= df_BIN[df_BIN.Ch_Det != 3].Ch_Det.unique(), window_s=window_s, window_E=window_E)
    df1, df0 = list(df_dict.values())
    df_cps_both = pd.merge(df1, df0, how = 'inner', on = 'Time [s]', suffixes = list(df_dict.keys()))
    df_cps_both['rel_{}_{}'.format(*dets)] = df_cps_both[f'Counts_{window_s}s_{dets[0]}']/df_cps_both[f'Counts_{window_s}s_{dets[1]}']
    return df_cps_both