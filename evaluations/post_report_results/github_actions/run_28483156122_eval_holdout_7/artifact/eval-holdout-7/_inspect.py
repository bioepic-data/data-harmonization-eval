import pandas as pd, numpy as np
D="/home/runner/ess-dive_wfsfa_soil_datasets/ess-dive-38e901ec3d7bd24-20230504T211548257225/"
df=pd.read_csv(D+"BM_Merged_T_VWC_0616_1018.csv")
print("VWC file shape",df.shape)
print("cols",df.columns.tolist())
print("depths(cm)",sorted(df['Depth (cm)'].dropna().unique()))
print("first/last",df['date.time'].iloc[0],"/",df['date.time'].iloc[-1])
print("vwc min/max",df['Volumetric Water Content'].min(),df['Volumetric Water Content'].max())
print(df.groupby('Depth (cm)').size())
# interval check at one depth
g=df[df['Depth (cm)']==10].copy()
g['dt']=pd.to_datetime(g['date.time'],format="%m/%d/%y %H:%M",errors='coerce')
print("median interval min (depth10)", g['dt'].diff().dt.total_seconds().median()/60)
print("nat count", g['dt'].isna().sum())
print("\n--- CO2/loc file ---")
co=pd.read_csv(D+"BM_EGM_Well_CO2.csv")
print("shape",co.shape,"cols",co.columns.tolist())
print("Locations",co['Location'].unique())
print("lat/lon",co.iloc[0,1],co.iloc[0,2])
