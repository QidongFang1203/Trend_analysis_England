# =============================================================================
# Groundwater Trend Classification Script
#
# Description:
# This script reads annually averaged groundwater depth data for multiple
# monitoring stations. For each station, it analyses the time series to
# classify its long-term trend into one of the following categories:
#
#   - Sudden upward change
#   - Increasing
#   - Sudden downward change
#   - Decreasing
#   - No trend
#
# The results, including the classification and key trend metrics, are
# saved to a final CSV file.
# =============================================================================


import pandas as pd
import csv


def piecewise(x, x0, x1, y0, y1):
    """
        Defines a mathematical function representing a period of linear change
        between two flat periods (a flat line, followed by a sloped line,
        followed by another flat line). This is used to capture a "sudden change".

        Args:
            x (array): The input time sequence.
            x0, x1 (float): The start and end points of the sloped section.
            y0, y1 (float): The start and end values of the sloped section.

        Returns:
            array: The calculated y-values for the piecewise function.
    """
    if x0 >= x1:
        x2 = x1
        x1 = x0
        x0 = x2
    return np.piecewise(x, [x <= x0, (x0 < x) * (x <= x1), x > x1],
                        [lambda x: y0,
                         lambda x: (x - x0) * (y1 - y0) / (x1 - x0) + y0,
                         lambda x: y1])


def suddenchange(xx, yy, YMG, a0, a1):
    """
        Fits the piecewise function to the data to detect if a "sudden change"
        pattern fits the time series well.

        Args:
            xx (array): The time sequence array.
            yy (array): The groundwater depth array.
            YMG (pd.DataFrame): The annual groundwater data.
            a0, a1 (float): Initial guesses for the start and end values.

        Returns:
            tuple: A tuple containing:
                - R2 (float): A goodness-of-fit score (R-squared).
                - windows (int): The duration of the change in years.
                - total_year (int): The total number of years in the record.
                - start_year (pd.Timestamp): The detected start year of the change.
                - end_year (pd.Timestamp): The detected end year of the change.
    """
    first_year = YMG.index[0]
    last_year = YMG.index[-1]
    params, _ = curve_fit(piecewise, xx, yy,
                          p0=[2, YMG['sequence'].iloc[-2], round(a0), round(a1)],
                          bounds=([1, 2, -100, -100], [YMG['sequence'].iloc[-2], YMG['sequence'].iloc[-1], 1000, 1000]))
    y_t = piecewise(xx, *params)
    R2 = 1 - np.sum(np.square(y_t - yy)) / np.sum(np.square(yy - np.mean(yy)))
    if params[0] < params[1]:
        start_year = YMG.index[0] + pd.DateOffset(years=round(params[0] - 1))
        end_year = start_year + pd.DateOffset(years=round(params[1] - params[0]))
    else:
        start_year = YMG.index[0] + pd.DateOffset(years=round(params[1] - 1))
        end_year = start_year + pd.DateOffset(years=round(params[0] - params[1]))
    windows = int((end_year - start_year).days / 365 + 1)
    total_year = int((last_year - first_year).days / 365 + 1)
    return R2, windows, total_year, start_year, end_year


def trendstable(YMG):
    """
        Checks the stability of the trend by repeatedly calculating the slope
        while leaving out one data point at a time. This helps confirm if a
        trend is consistent or just influenced by a few points.

        Args:
            YMG (pd.DataFrame): The annual groundwater data.

        Returns:
            list: A list of slopes, with each slope calculated from a dataset
                  missing one of the original data points.
    """
    ts_re = []
    for r in range(len(YMG)):
        YMG1 = YMG.drop(YMG.index[r])
        ts_s = stats.theilslopes(YMG1['value'], YMG1['sequence'], alpha=0.9)
        ts_re.append(ts_s.slope)
    return ts_re


def classidication(YMG):
    """
        Classifies the groundwater trend based on a decision tree logic.

        Args:
            YMG (pd.DataFrame): The annual groundwater data.

        Returns:
            tuple: A tuple containing the classification label and key metrics.
    """
    YMG['sequence'] = ((YMG.index - YMG.index[0]).days / 365 + 1).astype(int)
    ts_s = stats.theilslopes(YMG['value'], YMG['sequence'], alpha=0.9)
    xx = np.array(YMG['sequence'], dtype=float)
    yy = np.array(YMG['value'], dtype=float)

    # Trend Classification Logic
    if ts_s.slope < -0.02:  # increasing
        pw_R2, windows, total_year, start_year, end_year = suddenchange(xx, yy, YMG, min(YMG['value']),
                                                                        max(YMG['value']))
        if pw_R2 >= 0.7 and windows / total_year <= 0.5 and windows <= 15:
            label = 'Sudden upward change'
        else:
            ts_re = trendstable(YMG)
            if all(item < 0.1 for item in ts_re):
                label = 'Increasing'
            else:
                label = 'No trend'
    elif ts_s.slope > 0.02:  # decreasing
        pw_R2, windows, total_year, start_year, end_year = suddenchange(xx, yy, YMG, min(YMG['value']),
                                                                        max(YMG['value']))
        if pw_R2 >= 0.7 and windows / total_year <= 0.5 and windows <= 15:
            label = 'Sudden downward change'
        else:
            ts_re = trendstable(YMG)
            if all(item > -0.02 for item in ts_re):
                label = 'Decreasing'
            else:
                label = 'No trend'
    else:
        pw_R2, windows, total_year, start_year, end_year = suddenchange(xx, yy, YMG, min(YMG['value']),
                                                                        max(YMG['value']))
        label = 'No trend'
    return label, ts_s, pw_R2, windows, start_year, end_year


def read_csv(No):
    """
        Reads the annual data for a single station from its CSV file and formats it.

        Args:
            No (str): The station number (used as the filename).

        Returns:
            pd.DataFrame: A DataFrame with the station's annual data.
    """
    data = pd.read_csv('Annually sampling\%s.csv' % No)
    date = data['date'].values[:, None]
    date = [np.datetime64(int(c), 'D') for c in mdates.datestr2num(date[:])]
    gd = pd.DataFrame(data['value'].values[:, None], index=date, columns=['value'])
    return gd


if __name__ == '__main__':
    data = pd.read_csv("stations info.csv")
    data = data[data['state'] == 'qualified'].reset_index().drop(['index'], axis=1)
    No = data['No']

    with open('classification.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['No', 'classification', 'ts_slope', 'pw_R2', 'windows', 'start year', 'end year'])
        for i in range(len(No)):
            print(i)
            YMG = read_csv(No[i])
            # Classify the trend pattern
            Trend, ts_s, pw_R2, windows, start_year, end_year = classidication(YMG)
            # Write the classification results to the output CSV file
            csv_writer.writerow([No[i], Trend, ts_s.slope, pw_R2, windows, start_year, end_year])
