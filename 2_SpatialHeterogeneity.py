import pandas as pd
from geopy.distance import geodesic
from Classification import classidication, read_csv
import csv

if __name__ == '__main__':
    data = pd.read_csv(r"\stations info.csv")
    data = data[(data['total year'] > 8) & ((data['classification'] == 'Slow increasing') | (
                data['classification'] == 'Slow decreasing'))].reset_index().drop(['index'], axis=1)
    No = data['No']
    lat = data['lat']
    long = data['long']
    trend = data['classification']

    with open(r'\15km_consistency.csv',
              'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['No', 'Num of station', 'Num of consistent', 'Num of inconsistent'])
        for i in range(len(No)):
            print(i)
            # first select the data within 0.2 long (about 13km), 0.1 lat (about 11km)
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
                        # Select common period data
                        start = max([GWL_1.index[0], GWL_2.index[0]])
                        end = min([GWL_1.index[-1], GWL_2.index[-1]])
                        GWL_1 = GWL_1[(GWL_1.index >= start) & (GWL_1.index <= end)]
                        GWL_2 = GWL_2[(GWL_2.index >= start) & (GWL_2.index <= end)]
                        if len(GWL_1) > 8 and len(GWL_2) > 8:
                            # Identify the trend classification within the same period
                            Trend_1, ts_s_1, pw_R2_1, windows_1, start_year_1, end_year_1 = classidication(GWL_1)
                            Trend_2, ts_s_2, pw_R2_2, windows_2, start_year_2, end_year_2 = classidication(GWL_2)
                            if Trend_1 == 'No trend' or Trend_2 == 'No trend' or ts_s_1[0]/ts_s_2[0] > 0:
                                label = 'consistent'
                            else:
                                label = 'inconsistent'
                            consistency.append(label)
            csv_writer.writerow(
                [No[i], len(consistency), consistency.count('consistent'), consistency.count('inconsistent')])
