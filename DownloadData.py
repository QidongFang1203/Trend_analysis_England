# =============================================================================
# Groundwater Data Downloader and Quality Control Script
#
# Description:
# This script automates the process of fetching groundwater level data from the
# Environment Agency (EA) API, performing a series of quality control checks,
# and processing the data for trend analysis.
#
# The main workflow is as follows:
# 1. Reads a list of monitoring stations from a CSV file.
# 2. For each station, it fetches both "dipped" (manual) and "logged" (automated)
#    data from the EA API.
# 3. Merges and converts the raw water level data into groundwater depth.
# 4. Applies a three-step quality control process to clean the data.
# 5. Calculates summary statistics and saves annually averaged data for stations
#    that have sufficient data for analysis.
# =============================================================================


import os
import requests
import pandas as pd
import numpy as np
import json
import csv


def get_data(measures):
    """
        Fetches and preprocesses time series data from the Environment Agency API.

        Args:
            measures (str): The API URL for a specific measurement station.

        Raises:
            ConnectionError: If the API request fails (status code is not 200).

        Returns:
            pd.DataFrame: A DataFrame containing daily mean values, with 'date' as the index.
                          Returns an empty DataFrame if no valid data is found.
    """
    # Construct the full URL to read a large limit of measurements at once.
    url = os.path.join(measures + '/readings?_limit=2000000')

    # Make the API request
    response = requests.get(url)
    if response.status_code != 200:
        raise ConnectionError(f'{url} status code is {response.status_code}.')
    response = json.loads(response.content)

    # Check if there is any data with a 'value' field to process
    if not all('value' not in d for d in response['items']):
        df = pd.DataFrame(response['items'])
        df['value'] = df['value'].astype(float)
        # Filter out data with poor quality flags, keeping only 'Good' and 'Estimated'
        df = df[(df['quality'] == 'Estimated') | (df['quality'] == 'Good')]
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df.resample('D').mean(numeric_only=True).dropna(subset=['value'])
    else:
        df = pd.DataFrame()
    return df


def quality_control(gw_daily):
    """
        Applies a three-step quality control process to the daily groundwater depth data.

        The steps are:
        1.  R3TCSV:
            Removes any sequence of three or more identical consecutive values,
            which often indicates a sensor malfunction or flat-lining.
        2.  RVZ3:
            Removes outliers by eliminating values with a Z-score greater than 3.
            This identifies points that are more than 3 standard deviations from the mean.
        3.  RDRVI:
            Removes data for any water year where the Range Variation Index (RVI)
            is less than 0.2 or greater than 5, indicating an unusually small or large
            annual fluctuation.

        Args:
            gw_daily (pd.DataFrame): DataFrame with daily groundwater depth data.

        Returns:
            pd.DataFrame: The quality-controlled DataFrame.
    """
    gw_daily = gw_daily.reset_index()
    # 1. Remove 3 Times Continuous Same Values (R3TCSV)
    gw_daily['count'] = (gw_daily['value'] != gw_daily['value'].shift()).cumsum()
    counts = gw_daily.groupby('count')['value'].transform('size')
    previous_row = gw_daily['count'].shift(2)
    not_equal = gw_daily['count'].ne(previous_row)
    cumulative_sum = not_equal.cumsum()
    duplicates = cumulative_sum.duplicated(keep=False)
    gw_R3TCSV = gw_daily.loc[~duplicates].reset_index().drop(['index', 'count'], axis=1)

    # 2. Remove Values with Z score > 3 (RVZ3)
    mean = gw_R3TCSV['value'].mean()
    deviation = gw_R3TCSV['value'] - mean
    std_deviation = deviation.std()
    threshold = 3 * std_deviation
    gw_RVZ3 = pd.DataFrame(gw_R3TCSV[deviation.abs() <= threshold]).reset_index().drop(['index'], axis=1)

    # 3. Remove Data with one water year with RVI < 0.2 or RVI > 5 (RDRVI)
    gw_RDRVI = gw_RVZ3.reset_index().drop(['index'], axis=1)
    gw_RDRVI.set_index('date', inplace=True)
    # Resample by Water Year (starting in October) to find annual max and min
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
    # Read the input file containing station numbers and API links.
    data = pd.read_csv("3470 stations from EA.csv")
    No = data['No']
    dipped = data['dipped']
    logged = data['logged']
    elev = data['Elevation']

    # Open a CSV file to write summary information for each station.
    with open('stations info.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['No', 'data amount', 'mean_depth', 'max_depth', 'min_depth',
                             'first year', 'last year', 'total year', 'cover year'])
        for i in range(0, len(No)):
            print(f"Processing station index: {i}")
            # Get dipped (manual) and/or logged (automated) data if links exist.
            df1 = pd.DataFrame()
            df2 = pd.DataFrame()
            if not pd.isnull(dipped[i]):
                df1 = get_data(dipped[i])
            if not pd.isnull(logged[i]):
                df2 = get_data(logged[i])

            # Merge data from both sources if applicable, then sort by date
            df_combined = pd.concat([df1, df2], axis=0, join='outer').sort_index()

            # Resample to daily mean to handle any overlapping data points
            df_combined = df_combined.resample('D').mean(numeric_only=True).dropna(subset=['value'])

            # Convert groundwater level to groundwater depth
            df_combined['value'] = elev[i] - df_combined['value']

            # Apply the quality control function
            gd = quality_control(df_combined)

            # Resample the cleaned daily data into monthly means
            gd_m = gd.resample('MS').mean(numeric_only=True).dropna(subset=['value'])

            # Resample into yearly means based on the water year
            YMG = gd_m.resample('YS-OCT').mean(numeric_only=True).dropna()


            mean_depth = np.mean(YMG['value'])
            # Data amout control
            if len(gd) <= 100 or len(YMG) <= 8:
                csv_writer.writerow([No[i], 'no enough data'])
            elif mean_depth <= 0:
                csv_writer.writerow([No[i], 'negative mean depth'])
            else:
                first_year = YMG.index[0]
                last_year = YMG.index[-1]
                total_year = int((last_year - first_year).days / 365 + 1)
                csv_writer.writerow(
                    [No[i], len(gd), np.mean(gd['value']), max(gd['value']), min(gd['value']), first_year,
                     last_year, total_year, len(YMG)])
                YMG.to_csv('Annually sampling\%s.csv' % No[i], index=True, encoding='utf-8-sig')
