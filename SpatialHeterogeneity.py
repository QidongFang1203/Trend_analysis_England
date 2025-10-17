# =============================================================================
# Groundwater Trend Consistency Analysis Script
#
# Description:
# This script analyzes the spatial consistency of long-term groundwater trends.
# It takes a list of monitoring stations that have already been identified as
# having a 'Increasing' or 'Decreasing' trend over a long period.
# =============================================================================


import pandas as pd
from geopy.distance import geodesic
from Classification import classidication, read_csv
import csv

if __name__ == '__main__':
    # Load and Filter Initial Station Data
    data = pd.read_csv("stations info.csv")
    data = data[(data['total year'] > 8) & ((data['classification'] == 'Increasing') | (
                data['classification'] == 'Decreasing'))].reset_index().drop(['index'], axis=1)
    No = data['No']
    lat = data['lat']
    long = data['long']
    trend = data['classification']

    # Set up the Output CSV File
    with open('15km_consistency.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['No', 'Num of station', 'Num of consistent', 'Num of inconsistent'])

        # Iterate Through Each Qualified Station
        for i in range(len(No)):
            print(i)

            # Find and Analyze Neighboring Stations
            ini_select = data[(data['No'] != No[i]) & (data['lat'] > lat[i] - 0.15) & (data['lat'] < lat[i] + 0.15) &
                              (data['long'] > long[i] - 0.25) & (data['long'] < long[i] + 0.25)].reset_index().drop(
                ['index'], axis=1)
            consistency = []
            for j in range(len(ini_select)):
                GWL_1 = read_csv(No[i])

                # Calculate the distance between the centre point and other points
                distance_km = geodesic((lat[i], long[i]), (ini_select['lat'][j], ini_select['long'][j])).kilometers

                # Select points with distance less than X km
                if distance_km <= 15:
                    if data['Revised aquifers'][i] != 'Unallocated to aquifers' and data['Revised aquifers'][i] == \
                            ini_select['Revised aquifers'][j]:  # 'same aquifers'
                        GWL_2 = read_csv(ini_select['No'][j])

                        # Analyze the Common Time Period
                        start = max([GWL_1.index[0], GWL_2.index[0]])
                        end = min([GWL_1.index[-1], GWL_2.index[-1]])
                        GWL_1 = GWL_1[(GWL_1.index >= start) & (GWL_1.index <= end)]
                        GWL_2 = GWL_2[(GWL_2.index >= start) & (GWL_2.index <= end)]

                        # Ensure there are enough years in the common period for a meaningful comparison
                        if len(GWL_1) > 8 and len(GWL_2) > 8:
                            # Determine Trend Consistency
                            Trend_1, ts_s_1, pw_R2_1, windows_1, start_year_1, end_year_1 = classidication(GWL_1)
                            Trend_2, ts_s_2, pw_R2_2, windows_2, start_year_2, end_year_2 = classidication(GWL_2)
                            if Trend_1 == 'No trend' or Trend_2 == 'No trend' or ts_s_1[0]/ts_s_2[0] > 0:
                                label = 'consistent'
                            else:
                                label = 'inconsistent'
                            consistency.append(label)
            csv_writer.writerow(
                [No[i], len(consistency), consistency.count('consistent'), consistency.count('inconsistent')])
