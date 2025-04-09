import pandas as pd
import csv


def piecewise(x, x0, x1, y0, y1):
    if x0 >= x1:
        x2 = x1
        x1 = x0
        x0 = x2
    return np.piecewise(x, [x <= x0, (x0 < x) * (x <= x1), x > x1],
                        [lambda x: y0,
                         lambda x: (x - x0) * (y1 - y0) / (x1 - x0) + y0,
                         lambda x: y1])


def suddenchange(xx, yy, YMG, a0, a1):
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
    ts_re = []
    for r in range(len(YMG)):
        YMG1 = YMG.drop(YMG.index[r])
        ts_s = stats.theilslopes(YMG1['value'], YMG1['sequence'], alpha=0.9)
        ts_re.append(ts_s.slope)
    return ts_re


def classidication(YMG):
    YMG['sequence'] = ((YMG.index - YMG.index[0]).days / 365 + 1).astype(int)
    ts_s = stats.theilslopes(YMG['value'], YMG['sequence'], alpha=0.9)
    xx = np.array(YMG['sequence'], dtype=float)
    yy = np.array(YMG['value'], dtype=float)
    if ts_s.slope < -0.1:  # increasing
        pw_R2, windows, total_year, start_year, end_year = suddenchange(xx, yy, YMG, min(YMG['value']),
                                                                        max(YMG['value']))
        if pw_R2 >= 0.7 and windows / total_year <= 0.5 and windows <= 15:
            label = 'Sudden upward change'
        else:
            ts_re = trendstable(YMG)
            if all(item < 0.1 for item in ts_re):
                label = 'Slow increasing'
            else:
                label = 'No trend'
    elif ts_s.slope > 0.1:  # decreasing
        pw_R2, windows, total_year, start_year, end_year = suddenchange(xx, yy, YMG, min(YMG['value']),
                                                                        max(YMG['value']))
        if pw_R2 >= 0.7 and windows / total_year <= 0.5 and windows <= 15:
            label = 'Sudden downward change'
        else:
            ts_re = trendstable(YMG)
            if all(item > -0.02 for item in ts_re):
                label = 'Slow decreasing'
            else:
                label = 'No trend'
    else:
        pw_R2, windows, total_year, start_year, end_year = suddenchange(xx, yy, YMG, min(YMG['value']),
                                                                        max(YMG['value']))
        label = 'No trend'
    return label, ts_s, pw_R2, windows, start_year, end_year


def read_csv(No):
    data = pd.read_csv(
        r'C:\Users\xe22657\OneDrive - University of Bristol\PhD\ANN_RTD\Data\Pre-processed groudnwater depth\Annually sampling\%s.csv' % No)
    date = data['date'].values[:, None]
    date = [np.datetime64(int(c), 'D') for c in mdates.datestr2num(date[:])]
    gd = pd.DataFrame(data['value'].values[:, None], index=date, columns=['value'])
    return gd


if __name__ == '__main__':
    data = pd.read_csv(r"\stations info.csv")
    data = data[data['state'] == 'qualified'].reset_index().drop(['index'], axis=1)
    No = data['No']

    with open(r'C:\classification.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['No', 'classification', 'ts_slope', 'pw_R2', 'windows', 'start year', 'end year'])
        for i in range(len(No)):
            print(i)
            YMG = read_csv(No[i])
            Trend, ts_s, pw_R2, windows, start_year, end_year = classidication(YMG)
            csv_writer.writerow([No[i], Trend, ts_s.slope, pw_R2, windows, start_year, end_year])
