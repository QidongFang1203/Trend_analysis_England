import os
import requests
import pandas as pd
import numpy as np
import json
import csv


# access groundwater data from Environment Agency API
def get_data(measures):
    url = os.path.join(
        measures + '/readings?_limit=2000000')
    response = requests.get(url)
    if response.status_code != 200:
        raise ConnectionError(f'{url} status code is {response.status_code}.')
    response = json.loads(response.content)
    if not all('value' not in d for d in response['items']):
        df = pd.DataFrame(response['items'])
        df['value'] = df['value'].astype(float)
        df = df[(df['quality'] == 'Estimated') | (df['quality'] == 'Good')]  # Only 'Good' and 'Estimated' data selected
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df.resample('D').mean(numeric_only=True).dropna(subset=['value'])
    else:
        df = pd.DataFrame()
    return df


def quality_control(gw_daily):
    gw_daily = gw_daily.reset_index()
    # 1. remove 3 times continuous same values (R3TCSV)
    gw_daily['count'] = (gw_daily['value'] != gw_daily['value'].shift()).cumsum()
    counts = gw_daily.groupby('count')['value'].transform('size')
    previous_row = gw_daily['count'].shift(2)
    not_equal = gw_daily['count'].ne(previous_row)
    cumulative_sum = not_equal.cumsum()
    duplicates = cumulative_sum.duplicated(keep=False)
    gw_R3TCSV = gw_daily.loc[~duplicates].reset_index().drop(['index', 'count'], axis=1)

    # 2. remove values with z score > 3 (RVZ3)
    mean = gw_R3TCSV['value'].mean()
    deviation = gw_R3TCSV['value'] - mean
    std_deviation = deviation.std()
    threshold = 3 * std_deviation
    gw_RVZ3 = pd.DataFrame(gw_R3TCSV[deviation.abs() <= threshold]).reset_index().drop(['index'], axis=1)

    # 3. Remove data with one water year with RVI < 0.2 or RVI > 5 (RDRVI)
    gw_RDRVI = gw_RVZ3.reset_index().drop(['index'], axis=1)
    gw_RDRVI.set_index('date', inplace=True)
    Max_Y = gw_RDRVI.resample('YS-OCT').max().dropna()
    Min_Y = gw_RDRVI.resample('YS-OCT').min().dropna()
    Range_Y = Max_Y - Min_Y
    RVI_ALL = []
    for k in range(len(Min_Y)):
        RVI = (Max_Y['value'].iloc[k] - Min_Y['value'].iloc[k]) / np.median(Range_Y)
        RVI_ALL.append(RVI)
        if RVI > 5 or RVI < 0.2:
            remove_year = (gw_RDRVI.index >= Max_Y.index[k].to_pydatetime()) & (
                    gw_RDRVI.index <= (Max_Y.index[k] + pd.DateOffset(years=1)).to_pydatetime())
            gw_RDRVI = gw_RDRVI.loc[~remove_year]

    return gw_RDRVI


if __name__ == '__main__':

    data = pd.read_csv(r"Trend analysis\3470_2024.3.13.csv")
    No = data['No']
    dipped = data['dipped']
    logged = data['logged']
    elev = data['Elevation']
    with open(r'\stations info.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['No', 'data amount', 'mean_depth', 'max_depth', 'min_depth',
                             'first year', 'last year', 'total year', 'cover year'])
        for i in range(0, len(No)):
            print(i)
            # get dipped and/or logged data
            df1 = pd.DataFrame()
            df2 = pd.DataFrame()
            if not pd.isnull(dipped[i]):
                df1 = get_data(dipped[i])
            if not pd.isnull(logged[i]):
                df2 = get_data(logged[i])
            # merge two sources if applicable
            df_combined = pd.concat([df1, df2], axis=0, join='outer').sort_index()
            # resample to daily
            df_combined = df_combined.resample('D').mean(numeric_only=True).dropna(subset=['value'])
            # convert groundwater levels to groundwater depth
            df_combined['value'] = elev[i] - df_combined['value']
            # get groundwater depth data after quality control
            gd = quality_control(df_combined)
            # resample daily data into monthly
            gd_m = gd.resample('MS').mean(numeric_only=True).dropna(subset=['value'])
            # Yearly Mean Groundwater depth
            YMG = gd_m.resample('YS-OCT').mean(numeric_only=True).dropna()
            mean_depth = np.mean(YMG['value'])
            # Data amout control
            if len(gwl) <= 100 or len(YMG) <= 8:
                csv_writer.writerow([No[i], 'no enough data'])
            else:
                first_year = YMG.index[0]
                last_year = YMG.index[-1]
                total_year = int((last_year - first_year).days / 365 + 1)
                csv_writer.writerow(
                    [No[i], len(gd), np.mean(gd['value']), max(gd['value']), min(gd['value']), first_year,
                     last_year, total_year, len(YMG)])
                YMG.to_csv(r'\Annually sampling\%s.csv' % No[i], index=True, encoding='utf-8-sig')
