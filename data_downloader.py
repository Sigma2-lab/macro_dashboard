
"""
data_downloader.py

This file is used to download all the data required to build the dashboard.

Download logic is organised as one function per data series.  Each function
fetches a single series and writes its CSV to ./source_data.  A registry
(SERIES) maps a short key to each function plus its progress message and
failure label.

Public entry points
-------------------
run_all_updates(progress_callback=None)
    Download every series (unchanged public behaviour).
run_selected(keys, progress_callback=None)
    Download only the series whose key is in `keys` (used by the dashboard's
    per-indicator refresh buttons).  Pass keys=None to download everything.

Both return a list of failed series labels (empty list = full success).

@Katalepsis-Lab 2026
"""

import pandas as pd
from pandas_datareader import data as web
from datetime import datetime, timedelta
import requests
import zipfile
import io
import os # Required for file path operations

local_cache_root = "./source_data"


# ──────────────────────────────────────────────────────────────────────────────
# Low-level API helpers
# ──────────────────────────────────────────────────────────────────────────────

# General function to get data from Statistics Canada
def get_statscan_data(pid, series_label, cache_root=local_cache_root):

    url = f"https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip"
    print(f"Downloading new data from {url}...")

    cache_path = os.path.join(cache_root, f"{series_label}.csv")

    try:
        response = requests.get(url)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            file_name = f"{pid}.csv"

            if file_name in z.namelist():

                with z.open(file_name) as f:

                    df = pd.read_csv(f, low_memory=False)
                    print(f'{series_label} data loaded successfully.')

                    # Save new data to cache folder
                    os.makedirs(cache_root, exist_ok = True)
                    return df

    except Exception as e:
        print(f"An error occured during download of {series_label}: {e}")
        return None


## General function to get csv formatted data from BoC Valet API

def get_boc_data(series_id, series_label, cache_root=local_cache_root):
    base_url = f"https://www.bankofcanada.ca/valet/observations/{series_id}/csv"

    cache_path = os.path.join(cache_root, f"{series_label}.csv")
    print(f"Downloading new data from {base_url}...")

    try:
        response = requests.get(base_url)
        response.raise_for_status()

        # The BoC CSV contains metadata at the top.
        # The actual data starts after the "OBSERVATIONS" marker.
        content = response.text
        parts = content.split('"OBSERVATIONS"')

        if len(parts)>1:
            data_str = parts[1].strip()

            df = pd.read_csv(io.StringIO(data_str))
            df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
            df = df[df[series_id].notna()]
            print(f'{series_label} data loaded successfully.')

            os.makedirs(cache_root, exist_ok=True)
            return df

        else:
            print(f"Error: Could not find observation data in response for {series_id}")
            return None

    except Exception as e:
        print(f"An error occured during download of {series_label}: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Per-series download functions
# Each raises on failure; the runner records the failure label.
# ──────────────────────────────────────────────────────────────────────────────

def _dl_CAN_CPI():
    df_CPI = get_statscan_data("18100004", "CAN_CPI")

    # Filtering data
    mask_cpi = (df_CPI['GEO']=="Canada") & (df_CPI['Products and product groups'] == 'All-items')
    subset_cpi = df_CPI[mask_cpi].sort_values(by='REF_DATE', ascending = True)

    CAN_CPI = subset_cpi[['REF_DATE','VALUE']].copy()
    CAN_CPI = CAN_CPI.rename(columns={'REF_DATE':'DATE'})

    CAN_CPI['DATE'] = pd.to_datetime(CAN_CPI['DATE'])
    CAN_CPI = CAN_CPI[CAN_CPI['DATE']>'1998-12']

    # Adding YoY and MoM series
    CAN_CPI['YoY(%)'] = CAN_CPI['VALUE'].pct_change(12, fill_method=None)*100
    CAN_CPI['MoM(%)'] = CAN_CPI['VALUE'].pct_change(1, fill_method=None)*100
    CAN_CPI = CAN_CPI.drop(['VALUE'], axis=1).dropna()

    CAN_CPI.to_csv(f"{local_cache_root}/CAN_CPI.csv")
    print('CAN CPI download successful.')


def _dl_US_CPI():
    US_CPI = web.DataReader('CPIAUCSL', 'fred', start = 1999)
    US_CPI = US_CPI.reset_index()
    US_CPI['DATE'] = pd.to_datetime(US_CPI['DATE'])

    US_CPI['YoY(%)'] = US_CPI['CPIAUCSL'].pct_change(12, fill_method=None)*100
    US_CPI['MoM(%)'] = US_CPI['CPIAUCSL'].pct_change(1, fill_method=None)*100

    US_CPI = US_CPI.drop('CPIAUCSL', axis=1).dropna()

    US_CPI.to_csv(f'{local_cache_root}/US_CPI.csv')
    print(f'US CPI data saved to {local_cache_root}/US_CPI.csv.')


def _dl_CAN_PPI():
    df_PPI = get_statscan_data("18100265", "CAN_PPI")

    # Filtering data
    mask_ppi = (df_PPI['GEO']=="Canada") & (df_PPI['North American Product Classification System (NAPCS)'] == 'Total, Industrial product price index (IPPI)')
    subset_ppi = df_PPI[mask_ppi].sort_values(by='REF_DATE', ascending = True)

    CAN_PPI = subset_ppi[['REF_DATE','VALUE']].copy()
    CAN_PPI = CAN_PPI.rename(columns={'REF_DATE':'DATE'})

    CAN_PPI['DATE'] = pd.to_datetime(CAN_PPI['DATE'])
    CAN_PPI = CAN_PPI[CAN_PPI['DATE']>'1998-12']

    # Adding YoY and MoM series
    CAN_PPI['YoY(%)'] = CAN_PPI['VALUE'].pct_change(12, fill_method=None)*100
    CAN_PPI['MoM(%)'] = CAN_PPI['VALUE'].pct_change(1, fill_method=None)*100
    CAN_PPI = CAN_PPI.drop(['VALUE'], axis=1).dropna()

    CAN_PPI.to_csv(f"{local_cache_root}/CAN_PPI.csv")
    print('CAN PPI download successful.')


def _dl_US_PPI():
    US_PPI = web.DataReader('PPIACO', 'fred', start = 1999)
    US_PPI = US_PPI.reset_index()
    US_PPI['DATE'] = pd.to_datetime(US_PPI['DATE'])

    US_PPI['YoY(%)'] = US_PPI['PPIACO'].pct_change(12, fill_method=None)*100
    US_PPI['MoM(%)'] = US_PPI['PPIACO'].pct_change(1, fill_method=None)*100

    US_PPI = US_PPI.drop('PPIACO', axis=1).dropna()

    US_PPI.to_csv(f'{local_cache_root}/US_PPI.csv')
    print(f'US PPI data saved to {local_cache_root}/US_PPI.csv.')


def _dl_CAN_REV():
    df_REV = get_statscan_data("36100477", "CAN_REV")

    mask_REV = (df_REV['GEO'] == 'Canada') & (df_REV['Levels of government'] == 'Federal general government') & (df_REV['Estimates'] == 'General governments revenue') & (df_REV['Seasonal adjustment'] == "Unadjusted")

    df_REV['REF_DATE'] = pd.to_datetime(df_REV['REF_DATE'])

    subset_REV = df_REV[mask_REV].sort_values(by='REF_DATE', ascending = True)

    CAN_REV = subset_REV[['REF_DATE','VALUE',]].copy()
    CAN_REV = CAN_REV.rename(columns={'REF_DATE':'DATE'})
    CAN_REV['VALUE'] = CAN_REV['VALUE']/1000 # Convert Millions to Billions
    CAN_REV['TTM(B)'] = CAN_REV['VALUE'].rolling(window=4).sum()

    CAN_REV.to_csv(f'{local_cache_root}/CAN_REV.csv')
    print(f'CAN REV data saved to {local_cache_root}/CAN_REV.csv')


def _dl_US_REV():
    US_REV = web.DataReader('NA000327Q', 'fred', start = 1999)
    US_REV = US_REV.reset_index()
    US_REV['DATE'] = pd.to_datetime(US_REV['DATE'])
    US_REV['US_GOVT_REV(B)'] = US_REV['NA000327Q'] / 1000 # Convert Millions to Billions
    US_REV['TTM'] = US_REV['US_GOVT_REV(B)'].rolling(window=4).sum()

    US_REV = US_REV.rename({'NA000327Q':'US_GOVT_REV(M)'}, axis=1).dropna()
    US_REV.to_csv(f'{local_cache_root}/US_REV.csv')
    print(f'US REV data saved to {local_cache_root}/US_REV.csv')


def _dl_CAN_DEBT():
    df_DEBT = get_statscan_data("36100580", "CAN_DEBT")

    mask_debt = (df_DEBT['Sectors'] == 'Federal general government') & (df_DEBT['GEO'] == 'Canada') & (df_DEBT['Valuation'] == 'Book value') & (df_DEBT['Categories'] == 'Debt securities') & (df_DEBT['COORDINATE'] == '1.29.2.55')
    subset_debt = df_DEBT[mask_debt]
    CAN_DEBT = subset_debt[['REF_DATE','VALUE']].copy()
    CAN_DEBT['VALUE'] = CAN_DEBT['VALUE']/1000 # Convert Millions to Billions
    CAN_DEBT = CAN_DEBT.rename({'REF_DATE':'DATE','VALUE':'CAN Govt Debt(B)'}, axis=1)
    CAN_DEBT['YoY(%)'] = CAN_DEBT['CAN Govt Debt(B)'].pct_change(4, fill_method=None) * 100
    CAN_DEBT = CAN_DEBT.dropna()

    CAN_DEBT.to_csv(f'{local_cache_root}/CAN_DEBT.csv')
    print(f'CAN Debt data saved to {local_cache_root}/CAN_DEBT.csv.')


def _dl_US_DEBT():
    US_DEBT = web.DataReader('GFDEBTN', 'fred', start = 1999)
    US_DEBT = US_DEBT.reset_index()
    US_DEBT = US_DEBT.rename({'GFDEBTN':'US Govt Debt(B)'}, axis=1)
    US_DEBT['US Govt Debt(B)'] = US_DEBT['US Govt Debt(B)']/1000 # Convert Millions to Billions

    US_DEBT.to_csv(f'{local_cache_root}/US_DEBT.csv')
    print(f'US Debt data saved to {local_cache_root}/US_DEBT.csv.')


def _dl_CAN_FISC():
    df_FISC = get_statscan_data("36100477", "CAN_SURP_DEF")
    mask_FISC = (df_FISC['Seasonal adjustment'] == 'Unadjusted') & (df_FISC['Levels of government'] == 'Federal general government') & (df_FISC['Estimates']=='General governments surplus or deficit')
    subset_FISC = df_FISC[mask_FISC]

    CAN_FISC = subset_FISC[['REF_DATE','VALUE']].copy()
    CAN_FISC = CAN_FISC.rename({'REF_DATE':'DATE','VALUE':'CAN_FISC(B)'}, axis=1)
    CAN_FISC['CAN_FISC(B)'] = CAN_FISC['CAN_FISC(B)']/1000 # Convert Millions to Billions
    CAN_FISC['DATE'] = pd.to_datetime(CAN_FISC['DATE'])
    CAN_FISC['TTM(B)'] = CAN_FISC['CAN_FISC(B)'].rolling(window=4).sum()

    CAN_FISC = CAN_FISC.dropna()

    CAN_FISC.to_csv(f'{local_cache_root}/CAN_FISC.csv')
    print(f'CAN deficit data saved to {local_cache_root}/CAN_FISC.csv.')


def _dl_US_FISC():
    US_BUDGET = web.DataReader('MTSDS133FMS', 'fred', start = 1999)
    US_BUDGET = US_BUDGET.rename({'MTSDS133FMS':'US_FISC(B)'}, axis=1)
    US_BUDGET['US_FISC(B)'] = US_BUDGET['US_FISC(B)']/1000 # Convert Millions to Billions

    US_BUDGET = US_BUDGET.reset_index()
    US_BUDGET['TTM(B)'] = US_BUDGET['US_FISC(B)'].rolling(window=12).sum()
    US_BUDGET = US_BUDGET.dropna()

    US_BUDGET.to_csv(f'{local_cache_root}/US_FISC.csv')
    print(f'US Debt data saved to {local_cache_root}/US_FISC.csv.')


def _dl_CAN_rGDP():
    df_GDP = get_statscan_data("36100434", "CAN_GDP")
    mask_GDP = (df_GDP['Seasonal adjustment']=='Seasonally adjusted at annual rates')&(df_GDP['North American Industry Classification System (NAICS)']=='All industries [T001]')&(df_GDP['Prices']=='Chained (2017) dollars')
    subset_GDP = df_GDP[mask_GDP]

    CAN_rGDP = subset_GDP[['REF_DATE','VALUE']].copy()

    CAN_rGDP = CAN_rGDP.rename({'REF_DATE':'DATE','VALUE':'rGDP'}, axis=1)
    CAN_rGDP['YoY(%)'] = CAN_rGDP['rGDP'].pct_change(12, fill_method=None)*100
    CAN_rGDP['MoM(%)_annualized'] = ((CAN_rGDP['rGDP'].pct_change(fill_method=None) + 1)**12 - 1)*100   # Monthly data
    CAN_rGDP = CAN_rGDP.dropna()

    CAN_rGDP.to_csv(f'{local_cache_root}/CAN_rGDP.csv')
    print(f'CAN real GDP data saved to {local_cache_root}/CAN_rGDP.csv.')


def _dl_CAN_rGDP_EXP():
    df_GDP_EXP = get_statscan_data("36100104", "CAN_GDP_EXP")
    mask_GDP_EXP = (df_GDP_EXP['Prices'] == 'Chained (2017) dollars') & (df_GDP_EXP['Seasonal adjustment'] == 'Seasonally adjusted at annual rates') & (df_GDP_EXP['Estimates'] == 'Gross domestic product at market prices')
    subset_GDP_EXP = df_GDP_EXP[mask_GDP_EXP]

    CAN_rGDP_EXP = subset_GDP_EXP[['REF_DATE', 'VALUE']].copy()
    CAN_rGDP_EXP = CAN_rGDP_EXP.rename({'REF_DATE': 'DATE', 'VALUE': 'rGDP'}, axis=1)
    CAN_rGDP_EXP['DATE'] = pd.to_datetime(CAN_rGDP_EXP['DATE'])
    CAN_rGDP_EXP['YoY(%)'] = CAN_rGDP_EXP['rGDP'].pct_change(4, fill_method=None) * 100
    CAN_rGDP_EXP['QoQ(%)_annualized'] = ((CAN_rGDP_EXP['rGDP'].pct_change(fill_method=None) + 1)**4 - 1) * 100   # Quarterly data
    CAN_rGDP_EXP = CAN_rGDP_EXP.dropna()

    CAN_rGDP_EXP.to_csv(f'{local_cache_root}/CAN_rGDP_EXP.csv')
    print(f'CAN real GDP (expenditure) data saved to {local_cache_root}/CAN_rGDP_EXP.csv.')


def _dl_US_rGDP():
    US_GDP = web.DataReader('GDPC1', 'fred', start = 1999)
    US_GDP = US_GDP.reset_index()
    US_GDP = US_GDP.rename({'GDPC1':'rGDP'}, axis=1)

    US_GDP['YoY(%)'] = US_GDP['rGDP'].pct_change(4, fill_method=None)*100
    US_GDP['MoM(%)_annualized'] = ((US_GDP['rGDP'].pct_change(fill_method=None) + 1)**4 - 1)*100 # Quarterly data

    US_GDP = US_GDP.dropna()
    US_GDP.to_csv(f'{local_cache_root}/US_rGDP.csv')
    print(f'US real GDP data saved to {local_cache_root}/US_rGDP.csv.')


def _dl_CAN_1Y_INF():
    df_inf = get_boc_data("CES_C1_SHORT_TERM", "CAN_1Y_INF")

    df_inf['DATE'] = pd.PeriodIndex(df_inf['date'], freq='Q').to_timestamp().strftime('%Y-%m')
    df_inf = df_inf.rename(columns={'CES_C1_SHORT_TERM':'INF_EXP_1Y(%)'})

    df_inf.to_csv(f'{local_cache_root}/CAN_1Y_INF.csv')
    print(f'CAN 1Y inflation expectation data saved to {local_cache_root}/CAN_1Y_INF.csv.')


def _dl_CAN_1Y_TBILL():
    df_tbill = get_boc_data("TB.CDN.1Y.MID", "CAN_1Y_TBILL")
    df_tbill = df_tbill.rename(columns={'TB.CDN.1Y.MID':'CAN_1Y_TBILL_yield','date':'DATE'})
    df_tbill['DATE'] = pd.to_datetime(df_tbill['DATE'])

    df_tbill.to_csv(f'{local_cache_root}/CAN_1Y_TBILL.csv')
    print(f'CAN 1Y TBill yield data saved to {local_cache_root}/CAN_1Y_TBILL.csv.')


def _dl_CAN_10Y_INF():
    df_10yinf = get_boc_data("STATIC_ATABLE_V122544_V122553", "CAN_10Y_INF")
    df_10yinf = df_10yinf.rename(columns={'date':'DATE','STATIC_ATABLE_V122544_V122553':'10Y_BE_INF'})
    df_10yinf['DATE'] = pd.to_datetime(df_10yinf['DATE'])

    df_10yinf.to_csv(f'{local_cache_root}/CAN_10Y_INF.csv')
    print(f'CAN 10Y Breakeven Inflation data saved to {local_cache_root}/CAN_10Y_INF.csv.')


def _dl_CAN_10Y_TBILL():
    df_10tbill = get_boc_data("BD.CDN.10YR.DQ.YLD", "CAN_10Y_TBILL")
    df_10tbill = df_10tbill.rename(columns={'BD.CDN.10YR.DQ.YLD':'CAN_10Y_TBILL','date':'DATE'})
    df_10tbill['DATE'] = pd.to_datetime(df_10tbill['DATE'])

    df_10tbill.to_csv(f'{local_cache_root}/CAN_10Y_TBILL.csv')
    print(f'CAN 10Y TBill data saved to {local_cache_root}/CAN_10Y_TBILL.csv.')


def _dl_US_1Y_INF():
    US_1y_inf = web.DataReader('EXPINF1YR', 'fred', start = 1999)
    US_1y_inf = US_1y_inf.reset_index()
    US_1y_inf['DATE'] = pd.to_datetime(US_1y_inf['DATE'])

    US_1y_inf.to_csv(f'{local_cache_root}/US_1Y_INF.csv')
    print(f'US 1Y Inflation expectation data saved to {local_cache_root}/US_1Y_INF.csv.')


def _dl_US_1Y_TBILL():
    US_1y_yield = web.DataReader('DTB1YR', 'fred', start = 1999)
    US_1y_yield = US_1y_yield.rename(columns={'DTB1YR':'US_1Y_TBILL'})
    US_1y_yield = US_1y_yield.reset_index()

    US_1y_yield['DATE'] = pd.to_datetime(US_1y_yield['DATE'])

    US_1y_yield.to_csv(f'{local_cache_root}/US_1Y_TBILL.csv')
    print(f'US 1Y TBill data saved to {local_cache_root}/US_1Y_TBILL.csv.')


def _dl_US_10Y_INF():
    US_10y_inf = web.DataReader('EXPINF10YR', 'fred', start = 1999)
    US_10y_inf = US_10y_inf.reset_index()
    US_10y_inf['DATE'] = pd.to_datetime(US_10y_inf['DATE'])

    US_10y_inf.to_csv(f'{local_cache_root}/US_10Y_INF.csv')
    print(f'US 10Y Inflation expectation data saved to {local_cache_root}/US_10Y_INF.csv.')


def _dl_US_10Y_TBILL():
    US_10y_yield = web.DataReader('DGS10', 'fred', start = 1999)
    US_10y_yield = US_10y_yield.rename(columns={'DGS10':'US_10Y_TBILL'})
    US_10y_yield = US_10y_yield.reset_index()

    US_10y_yield['DATE'] = pd.to_datetime(US_10y_yield['DATE'])

    US_10y_yield.to_csv(f'{local_cache_root}/US_10Y_TBILL.csv')
    print(f'US 10Y TBill data saved to {local_cache_root}/US_10Y_TBILL.csv.')


def _dl_US_CB_BS():
    US_CB_BS = web.DataReader('WALCL', 'fred', start = 1999)
    US_CB_BS['CB_assets(B)'] = US_CB_BS['WALCL']/1000 # Convert Millions to Billions
    US_CB_BS = US_CB_BS.reset_index()
    US_CB_BS['DATE'] = pd.to_datetime(US_CB_BS['DATE'])
    US_CB_BS['Weekly_Change(%)'] = US_CB_BS['CB_assets(B)'].pct_change(fill_method=None) * 100

    # Note: FRED 'WALCL' is weekly, so 13 weeks ~= 3 months
    US_CB_BS['3M_Rolling_Avg_Change(%)'] = US_CB_BS['Weekly_Change(%)'].rolling(window=13).mean()
    US_CB_BS = US_CB_BS.dropna()
    US_CB_BS.to_csv(f'{local_cache_root}/US_CB_BS.csv')
    print(f'US Central bank BS data saved to {local_cache_root}/US_CB_BS.csv.')


def _dl_CAN_CB_BS():
    df_boc = get_boc_data("V36610", "CAN_COB_BS")

    df_boc['CB_assets_B'] = df_boc['V36610']/1000 # Convert Millions to Billions

    df_boc = df_boc.rename(columns={'date':'DATE'})
    df_boc['DATE'] = pd.to_datetime(df_boc['DATE'])

    df_boc['Weekly_Change_%'] = df_boc['CB_assets_B'].pct_change(fill_method=None) * 100

    #3Mo rolling average % change
    df_boc['3M_Rolling_Avg_Change_%'] = df_boc['Weekly_Change_%'].rolling(window=13).mean()

    df_boc = df_boc.dropna()

    df_boc.to_csv(f'{local_cache_root}/CAN_CB_BS.csv')
    print(f'Canada Central bank BS data saved to {local_cache_root}/CAN_CB_BS.csv.')


def _dl_US_INTEREST():
    us_interest = web.DataReader('A091RC1Q027SBEA', 'fred', start=1999)
    us_interest = us_interest.rename(columns={'A091RC1Q027SBEA':'Interest_Payments_B'})
    us_interest = us_interest.reset_index()
    us_interest.to_csv(f'{local_cache_root}/US_INTEREST.csv')
    print(f'US Govt interest data saved to {local_cache_root}/US_INTEREST.csv.')


def _dl_CAN_INTEREST():
    df_int = get_statscan_data('10100015','CAN_INTEREST')
    mask_int = (df_int['GEO'] == 'Canada') & (df_int['Government sectors']=='Federal government') & (df_int['Statement of government operations and balance sheet']=='Interest')
    subset_int = df_int[mask_int]

    can_int = subset_int[['REF_DATE','VALUE']].copy()
    can_int['VALUE'] = can_int['VALUE']/1000 # Convert Millions to Billions
    can_int = can_int.rename(columns={'REF_DATE':'DATE','VALUE':'CAN_INT_B'})
    can_int['TTM(B)'] = can_int['CAN_INT_B'].rolling(window=4).sum()

    can_int.to_csv(f'{local_cache_root}/CAN_INTEREST.csv')
    print(f'Canada Govt interest data saved to {local_cache_root}/CAN_INTEREST.csv.')


def _dl_CAN_CURRENT_ACCOUNT():
    df_CA = get_statscan_data("36100018", "CAN_CURRENT_ACCOUNT")

    mask_ca = (df_CA['Current account'] == 'Total current account') & (df_CA['Receipts, payments and balances'] == 'Balances, seasonally adjusted')

    subset_ca = df_CA[mask_ca]
    CAN_CA = subset_ca[['REF_DATE', 'VALUE']].copy()
    CAN_CA['VALUE'] = CAN_CA['VALUE'] / 1000 # Convert Millions to Billions
    CAN_CA = CAN_CA.rename(columns={'REF_DATE': 'DATE', 'VALUE': 'CAN_CA_Balance(B)'})
    CAN_CA['DATE'] = pd.to_datetime(CAN_CA['DATE'])

    CAN_CA['TTM(B)'] = CAN_CA['CAN_CA_Balance(B)'].rolling(window=4).sum()

    # Calculate rolling 12-quarter Z-score
    CAN_CA['Z-Score(12Q)'] = (CAN_CA['CAN_CA_Balance(B)'] - CAN_CA['CAN_CA_Balance(B)'].rolling(window=12).mean()) / CAN_CA['CAN_CA_Balance(B)'].rolling(window=12).std()

    CAN_CA = CAN_CA.dropna()

    CAN_CA.to_csv(f'{local_cache_root}/CAN_CURRENT_ACCOUNT.csv', index=False)
    print(f'CAN Current Account data saved to {local_cache_root}/CAN_CURRENT_ACCOUNT.csv.')


def _dl_US_CAB():
    US_CAB = web.DataReader('IEABC', 'fred', start=1999)
    US_CAB = US_CAB.reset_index()
    US_CAB['DATE'] = pd.to_datetime(US_CAB['DATE'])

    US_CAB = US_CAB.rename(columns={'IEABC': 'US_Current_Account(B)'})
    US_CAB['US_Current_Account(B)'] = US_CAB['US_Current_Account(B)'] / 1000 # Convert Millions to Billions

    US_CAB['TTM(B)'] = US_CAB['US_Current_Account(B)'].rolling(window=4).sum()

    # Calculate rolling 12-quarter Z-score
    US_CAB['Z-Score(12Q)'] = (US_CAB['US_Current_Account(B)'] - US_CAB['US_Current_Account(B)'].rolling(window=12).mean()) / US_CAB['US_Current_Account(B)'].rolling(window=12).std()

    US_CAB = US_CAB.dropna()

    US_CAB.to_csv(f'{local_cache_root}/US_CAB.csv')
    print(f'US Current Account Balance data saved to {local_cache_root}/US_CAB.csv.')


def _dl_CAN_CAP_FLOWS():
    df_FLOWS = get_statscan_data("36100472", "CAN_CAP_FLOWS")

    mask_flows = (df_FLOWS['GEO'] == "Canada") & (df_FLOWS['Financial account'] == 'Net lending / net borrowing, from financial account') & (df_FLOWS['Countries or regions'] == 'All countries')
    subset_flows = df_FLOWS[mask_flows].sort_values(by='REF_DATE', ascending = True)

    CAN_CAP_FLOWS = subset_flows[['REF_DATE','VALUE']].copy()
    CAN_CAP_FLOWS = CAN_CAP_FLOWS.rename(columns={'REF_DATE':'DATE'})

    CAN_CAP_FLOWS['DATE'] = pd.to_datetime(CAN_CAP_FLOWS['DATE'])

    CAN_CAP_FLOWS['CAN_Net_lending_borrowing(B)'] = CAN_CAP_FLOWS['VALUE'] / 1000 # Convert Millions to Billions

    # Calculate rolling 12-quarter Z-score
    CAN_CAP_FLOWS['Z-Score(12Q)'] = (CAN_CAP_FLOWS['CAN_Net_lending_borrowing(B)'] - CAN_CAP_FLOWS['CAN_Net_lending_borrowing(B)'].rolling(window=12).mean()) / CAN_CAP_FLOWS['CAN_Net_lending_borrowing(B)'].rolling(window=12).std()

    CAN_CAP_FLOWS = CAN_CAP_FLOWS.dropna()

    CAN_CAP_FLOWS.to_csv(f"{local_cache_root}/CAN_CAP_FLOWS.csv")
    print(f'CAN Capital Flows data saved to {local_cache_root}/CAN_CAP_FLOWS.csv.')


def _dl_US_CAP_FLOWS():
    US_FLOWS = web.DataReader('IEANLF', 'fred', start=1999)
    US_FLOWS = US_FLOWS.reset_index()

    US_FLOWS['US_Net_lending_borrowing(B)'] = US_FLOWS['IEANLF'] / 1000 # Convert Millions to Billions
    US_FLOWS = US_FLOWS.drop(columns=['IEANLF'])
    US_FLOWS['DATE'] = pd.to_datetime(US_FLOWS['DATE'])

    # Calculate rolling 12-quarter Z-score
    US_FLOWS['Z-Score(12Q)'] = (US_FLOWS['US_Net_lending_borrowing(B)'] - US_FLOWS['US_Net_lending_borrowing(B)'].rolling(window=12).mean()) / US_FLOWS['US_Net_lending_borrowing(B)'].rolling(window=12).std()

    US_FLOWS = US_FLOWS.dropna()

    US_FLOWS.to_csv(f'{local_cache_root}/US_CAP_FLOWS.csv')
    print(f'US Capital Flows data saved to {local_cache_root}/US_CAP_FLOWS.csv.')


# ──────────────────────────────────────────────────────────────────────────────
# Series registry
# key : (progress message, failure label, download function)
# Order preserved from the original run_all_updates so a full refresh behaves
# identically.
# ──────────────────────────────────────────────────────────────────────────────

SERIES = {
    "CAN_CPI":             ("Updating Canadian CPI...",                          "Canadian CPI",                          _dl_CAN_CPI),
    "US_CPI":              ("Updating US CPI...",                                "US CPI",                                _dl_US_CPI),
    "CAN_PPI":             ("Updating Canadian PPI...",                          "Canada PPI",                            _dl_CAN_PPI),
    "US_PPI":              ("Updating US PPI...",                                "US PPI",                                _dl_US_PPI),
    "CAN_REV":             ("Fetching Canadian Government Revenue...",           "Canada Government Revenue",             _dl_CAN_REV),
    "US_REV":              ("Fetching US Government Revenue...",                 "US Government Revenue",                 _dl_US_REV),
    "CAN_DEBT":            ("Fetching Canadian Government Debt...",              "Canada Government Debt",                _dl_CAN_DEBT),
    "US_DEBT":             ("Fetching US Government Debt...",                    "US Government Debt",                    _dl_US_DEBT),
    "CAN_FISC":            ("Fetching Canadian Fiscal Balance (Surplus/Deficit)...", "Canada Fiscal Balance",            _dl_CAN_FISC),
    "US_FISC":             ("Fetching US Fiscal Balance (Surplus/Deficit)...",   "US Fiscal Balance",                    _dl_US_FISC),
    "CAN_rGDP":            ("Fetching Canadian Real GDP...",                     "Canada Real GDP",                      _dl_CAN_rGDP),
    "CAN_rGDP_EXP":        ("Fetching Canadian Real GDP (Expenditure-based)...", "Canada Real GDP (Expenditure-based)",  _dl_CAN_rGDP_EXP),
    "US_rGDP":             ("Fetching US Real GDP...",                           "US Real GDP",                          _dl_US_rGDP),
    "CAN_1Y_INF":          ("Fetching Canadian 1Y Inflation Expectation...",     "Canada 1Y Inflation Expectation",      _dl_CAN_1Y_INF),
    "CAN_1Y_TBILL":        ("Fetching Canadian 1Y T-Bill Yield...",             "Canada 1Y T-Bill Nominal Yield",       _dl_CAN_1Y_TBILL),
    "CAN_10Y_INF":         ("Fetching Canadian 10Y Breakeven Inflation...",      "Canada 10Y Breakeven Inflation",       _dl_CAN_10Y_INF),
    "CAN_10Y_TBILL":       ("Fetching Canadian 10Y Bond Yield...",              "Canada 10Y T-Bill Nominal Yield",      _dl_CAN_10Y_TBILL),
    "US_1Y_INF":           ("Fetching US 1Y Inflation Expectation...",          "US 1Y Inflation Expectation",          _dl_US_1Y_INF),
    "US_1Y_TBILL":         ("Fetching US 1Y T-Bill Yield...",                   "US 1Y T-Bill Nominal Yield",           _dl_US_1Y_TBILL),
    "US_10Y_INF":          ("Fetching US 10Y Inflation Expectation...",         "US 10Y Inflation Expectation",         _dl_US_10Y_INF),
    "US_10Y_TBILL":        ("Fetching US 10Y Bond Yield...",                    "US 10Y T-Bill Nominal Yield",          _dl_US_10Y_TBILL),
    "US_CB_BS":            ("Fetching US Central Bank Balance Sheet...",         "US Central Bank Balance Sheet",        _dl_US_CB_BS),
    "CAN_CB_BS":           ("Fetching Bank of Canada Balance Sheet...",         "Canada Central Bank Balance Sheet",    _dl_CAN_CB_BS),
    "US_INTEREST":         ("Fetching US Government Interest Payments...",       "US Government Interest Payments",       _dl_US_INTEREST),
    "CAN_INTEREST":        ("Fetching Canadian Government Interest Payments...", "Canada Government Interest Payments",   _dl_CAN_INTEREST),
    "CAN_CURRENT_ACCOUNT": ("Fetching Canadian Current Account Balance...",      "Canada Current Account Balance",       _dl_CAN_CURRENT_ACCOUNT),
    "US_CAB":              ("Fetching US Current Account Balance...",            "US Current Account Balance",           _dl_US_CAB),
    "CAN_CAP_FLOWS":       ("Fetching Canadian Capital Flows...",               "Canada Capital Flows",                 _dl_CAN_CAP_FLOWS),
    "US_CAP_FLOWS":        ("Fetching US Capital Flows...",                      "US Capital Flows",                     _dl_US_CAP_FLOWS),
}


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrators
# ──────────────────────────────────────────────────────────────────────────────

def run_selected(keys=None, progress_callback=None):
    """
    Download the requested series and save CSVs to ./source_data.

    Parameters
    ----------
    keys : iterable[str] | None
        Registry keys (see SERIES) to download.  None = download everything.
        Unknown keys are ignored.
    progress_callback : callable(message: str) | None
        Called before each download block with a status string.

    Returns
    -------
    list[str]
        Labels of series that failed (empty = all selected succeeded).
    """

    def _cb(message):
        if progress_callback is not None:
            progress_callback(message)

    os.makedirs(local_cache_root, exist_ok=True)
    failed_series = []

    for key, (cb_msg, fail_label, fn) in SERIES.items():
        if keys is not None and key not in keys:
            continue

        _cb(cb_msg)
        try:
            fn()
        except Exception as e:
            failed_series.append(fail_label)
            print(f"An error occured during download of {fail_label}: {e}")

    # ── Final status ──────────────────────────────────────────────────────────
    if failed_series:
        error_msg = f"Completed with errors in: {', '.join(failed_series)}"
        _cb(error_msg)
        print(error_msg)
    else:
        _cb("All data updated successfully.")
        print('Everything worked as expected.')

    return failed_series # Return the list of failures


def run_all_updates(progress_callback=None):
    """
    Download all macro data and save CSVs to ./source_data.

    Thin wrapper over run_selected(keys=None); preserved for backwards
    compatibility with the dashboard's "Refresh Global Data" button.

    Returns
    -------
    list[str]
        Labels of series that failed (empty = full success).
    """
    return run_selected(keys=None, progress_callback=progress_callback)


# ──────────────────────────────────────────────────────────────────────────────
# Standalone execution
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    def _print_cb(message):
        print(f"[STATUS] {message}")

    run_all_updates(progress_callback=_print_cb)
