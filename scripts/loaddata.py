# -*- coding: utf-8 -*-
"""loaddata.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1aVbSpq7wekBUrhov8edABCpf_jstFLwA
"""

# Commented out IPython magic to ensure Python compatibility.
# Google Drive マウント
from google.colab import drive
drive.mount('/content/drive')

# %cd /content/drive/My Drive/卒業研究/DeadReckoning_ExperimentalData/ML
# %ls

import datetime

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

from typing import List, Tuple

plt.style.use('ggplot')

def deglim(x: float) -> float:
    return (x + 180) % 360 - 180

def radlim(x: float) -> float:
    return (x + np.pi) % (2*np.pi) - np.pi

def omega2deg(x: List[float], dt=0.02, offset=0) -> List[float]:
    return deglim(np.cumsum(x) * dt + offset)

def omega2rad(x: List[float], dt=0.02, offset=0) -> List[float]:
    return radlim(np.cumsum(x) * dt + offset)

def calcDistance(latitude1: float, longitude1: float,
                 latitude2: float, longitude2: float) -> Tuple[float, float]:
    GRS80_A = 6378137.000            # 長半径 a(m)
    GRS80_E2 = 0.00669438002301188   # 第一遠心率  eの2乗

    # 経度の平均
    my = ((latitude1 + latitude2) / 2.0) * np.pi/180

    # 卯酉線曲率半径を求める(東と西を結ぶ線の半径)
    sinMy = np.sin(my)
    w = np.sqrt(1.0 - GRS80_E2 * sinMy * sinMy)
    n = GRS80_A / w

    # 子午線曲線半径を求める(北と南を結ぶ線の半径)
    mnum = GRS80_A * (1 - GRS80_E2)
    m = mnum / (w * w * w)

    # 緯度，経度の変化量
    deltaLatitude = (latitude2 - latitude1) * np.pi/180
    deltaLongitude = (longitude2 - longitude1) * np.pi/180

    # ｘ，ｙ方向の移動距離
    deltaX = n * np.cos(my) * deltaLongitude
    deltaY = m * deltaLatitude

    # 距離と角度に変換
    distance = (deltaX ** 2 + deltaY ** 2) ** 0.5
    angle = np.arctan2(-deltaY, -deltaX) + np.pi

    return distance, angle

# 外れ値除去
def dropOutlier(x: List[float]) -> List[float]:
    x_copy = x.copy()

    # 平均と標準偏差
    average = np.mean(x_copy)
    sd = np.std(x_copy)

    # 外れ値の基準点
    outlier_min = 0
    outlier_max = average + sd * 2

    # 範囲から外れている値を除く
    x_copy[x_copy < outlier_min] = None
    x_copy[x_copy > outlier_max] = None

    return x_copy

def loadAccData(filename: str, declination=7.1) -> pd.DataFrame:
    df_acc = pd.read_csv(filename, index_col='datetime', parse_dates=True)

    df_acc['angleX[rad]'] += np.pi
    df_acc['angleY[rad]'] += np.pi
    df_acc['angleZ[rad]'] += np.pi

    df_acc['angleX[rad]'] += declination * np.pi/180
    df_acc['angleY[rad]'] += declination * np.pi/180
    df_acc['angleZ[rad]'] += declination * np.pi/180
    df_acc['angleX[rad]'] %= 2 * np.pi
    df_acc['angleY[rad]'] %= 2 * np.pi
    df_acc['angleZ[rad]'] %= 2 * np.pi

    df_acc['angleX[deg]'] = df_acc['angleX[rad]'] * 180/np.pi
    df_acc['angleY[deg]'] = df_acc['angleY[rad]'] * 180/np.pi
    df_acc['angleZ[deg]'] = df_acc['angleZ[rad]'] * 180/np.pi

    df_acc['gyroX[deg/s]'] = df_acc['gyroX[rad/s]'] * 180/np.pi
    df_acc['gyroY[deg/s]'] = df_acc['gyroY[rad/s]'] * 180/np.pi
    df_acc['gyroZ[deg/s]'] = df_acc['gyroZ[rad/s]'] * 180/np.pi

    x = radlim(np.diff(df_acc['angleX[rad]']) / 0.02)
    y = radlim(np.diff(df_acc['angleY[rad]']) / 0.02)
    z = radlim(np.diff(df_acc['angleZ[rad]']) / 0.02)
    df_acc['angleX[rad/s]'] = np.concatenate([[0.0], x])
    df_acc['angleY[rad/s]'] = np.concatenate([[0.0], y])
    df_acc['angleZ[rad/s]'] = np.concatenate([[0.0], z])

    df_acc['angleX[deg/s]'] = df_acc['angleX[rad/s]'] * 180/np.pi
    df_acc['angleY[deg/s]'] = df_acc['angleY[rad/s]'] * 180/np.pi
    df_acc['angleZ[deg/s]'] = df_acc['angleZ[rad/s]'] * 180/np.pi

    return df_acc

def loadRTKData(filename: str) -> pd.DataFrame:
    df_rtk = pd.read_csv(filename)
    df_rtk['datetime'] = df_rtk['date'] + ' ' + df_rtk['time']
    df_rtk['datetime'] = pd.to_datetime(df_rtk['datetime'])
    df_rtk.set_index('datetime', inplace=True)
    df_rtk.index += datetime.timedelta(hours=9)
    df_rtk.index -= datetime.timedelta(seconds=18) # 誤差補正

    df_rtk = df_rtk[['latitude(deg)', 'longitude(deg)']]

    # 速度・角速度算出
    speed_list, angle_list, x_list,  y_list = [0.0], [0.0], [0.0], [0.0]
    omega_list = [0.0]
    for t in range(1, df_rtk.shape[0]):
        dt = (df_rtk.index[t] - df_rtk.index[t-1]).total_seconds()
        distance, angle = calcDistance(df_rtk['latitude(deg)'][t-1],
                                       df_rtk['longitude(deg)'][t-1],
                                       df_rtk['latitude(deg)'][t],
                                       df_rtk['longitude(deg)'][t]) 
        speed = distance / dt
        speed_list.append(speed)

        # 止まっているときは角速度の算出はなし
        if speed < 0.7:
            angle_list.append(None)
            omega_list.append(None)
        elif angle_list[-1] is not None:
            omega = (angle - angle_list[-1]) / dt
            omega = radlim(omega)
            omega_list.append(omega)
            angle_list.append(angle)
        else:
            angle_list.append(angle)
            omega_list.append(None)

        x_list.append(x_list[-1] + distance * np.cos(angle))
        y_list.append(y_list[-1] + distance * np.sin(angle))
    df_rtk['speed[m/s]'], df_rtk['angle[rad]'] = speed_list, angle_list
    df_rtk['omega[rad/s]'] = omega_list
    df_rtk['x'], df_rtk['y'] = x_list, y_list

    # 外れ値除去
    df_rtk['speed[m/s]'] = dropOutlier(df_rtk['speed[m/s]'])

    # 速度・角速度を1秒間の平均に変換
    error_count = -4
    speed_1Hz, omega_1Hz = [], []
    for time in df_rtk.index:
        starttime = time - datetime.timedelta(seconds=0.999)
        df_rtk_part = df_rtk[starttime : time]
        if df_rtk_part.shape[0] != 5:
            error_count += 1
            speed_1Hz.append(None)
            omega_1Hz.append(None)
        else:
            speed_1Hz.append(np.mean(df_rtk_part['speed[m/s]']))
            omega_1Hz.append(np.mean(df_rtk_part['omega[rad/s]']))
    df_rtk['speed_1Hz[m/s]'] = speed_1Hz
    df_rtk['omega_1Hz[rad/s]'] = omega_1Hz

    # 単位変換
    df_rtk['angle[deg]'] = df_rtk['angle[rad]'] * 180/np.pi
    df_rtk['omega[deg/s]'] = df_rtk['omega[rad/s]'] * 180/np.pi
    df_rtk['omega_1Hz[deg/s]'] = df_rtk['omega_1Hz[rad/s]'] * 180/np.pi

    return df_rtk

def loadGPSData(filename: str,
                o_latitude: float,
                o_longitude: float) -> pd.DataFrame:
    df_gps = pd.read_csv(filename)
    df_gps['datetime'] = pd.to_datetime(df_gps['datetime'])
    df_gps.set_index('datetime', inplace=True)

    # 速度算出
    speed_list, angle_list, x_list,  y_list = [0.0], [0.0], [0.0], [0.0]
    for i in range(1, df_gps.shape[0]):
        elapsedTime = (df_gps.index[i] - df_gps.index[i-1]).total_seconds()
        distance, angle = calcDistance(o_latitude,
                                       o_longitude,
                                       df_gps['latitude'][i],
                                       df_gps['longitude'][i]) 
        speed = distance / elapsedTime
        speed_list.append(speed)
        angle_list.append(angle)
        x_list.append(distance * np.cos(angle))
        y_list.append(distance * np.sin(angle))
    df_gps['speed[m/s]'], df_gps['angle[rad]'] = speed_list, angle_list
    df_gps['angle[deg]'] = df_gps['angle[rad]'] * 180/np.pi
    df_gps['x'], df_gps['y'] = x_list, y_list

    return df_gps

# データのいらない部分削除
def fitData(df_acc, df_rtk, start=0.0, end=0.0):
    starttime_rtk = df_rtk.index[0] + datetime.timedelta(seconds=start)
    starttime_acc = starttime_rtk - datetime.timedelta(seconds=3)
    endtime = df_rtk.index[-1] - datetime.timedelta(seconds=end)
    df_rtk = df_rtk[starttime_rtk : endtime]
    df_acc = df_acc[starttime_acc : endtime]
    return df_acc, df_rtk

# グラフ表示
def plot(df_acc, df_rtk):
    fig1 = plt.figure(figsize=(8, 8))

    # 加速度
    ax1 = fig1.add_subplot(411)
    ax1.plot(df_acc['accX[m/s^2]'], color='tab:blue', label='x', alpha=0.7)
    ax1.plot(df_acc['accY[m/s^2]'], color='tab:orange', label='y', alpha=0.7)
    ax1.plot(df_acc['accZ[m/s^2]'], color='tab:green', label='z', alpha=0.7)
    ax1.set_ylabel('acceleration [m/s^2]')
    ax1.tick_params(bottom=False, labelbottom=False)
    ax1.legend(loc='lower left')

    # 速度
    ax2 = fig1.add_subplot(412, sharex=ax1)
    ax2.plot(df_rtk['speed[m/s]'], color='tab:gray', label='5Hz')
    ax2.plot(df_rtk['speed_1Hz[m/s]'], color='tab:brown', label='1Hz')
    ax2.set_ylabel('velocity [m/s]')
    ax2.tick_params(bottom=False, labelbottom=False)
    ax2.legend(loc='lower left')

    # 角度
    ax3 = fig1.add_subplot(413, sharex=ax1)
    ax3.plot(df_rtk['angle[deg]'], color='tab:gray', label='rtk')
    ax3.plot(df_acc['angleZ[deg]'], color='tab:blue', label='mag', alpha=0.7)
    # angleByGyro = omega2deg(df_acc['gyroX[deg/s]'],
    #                         offset=df_acc['angleZ[deg]'][0])
    angleByGyro = (np.cumsum(df_acc['gyroX[deg/s]']) * 0.02 + df_acc['angleZ[deg]'][0]) % 360
    ax3.plot(angleByGyro, color='tab:red', label='gyro', alpha=0.7)
    ax3.set_ylabel('angle [deg]')
    ax3.tick_params(bottom=False, labelbottom=False)
    ax3.legend(loc='lower left')

    # 角速度
    ax4 = fig1.add_subplot(414, sharex=ax1)
    ax4.plot(df_rtk['omega_1Hz[deg/s]'], color='tab:gray', label='rtk')
    ax4.plot(df_acc['angleZ[deg/s]'].rolling(50).mean(),
             color='tab:blue', label='mag', alpha=0.6)
    ax4.plot(df_acc['gyroX[deg/s]'].rolling(50).mean(),
             color='tab:red', label='gyro', alpha=0.6)
    ax4.set_ylabel('angular velocity [deg/s]')
    ax4.set_xlabel('time')
    ax4.legend(loc='lower left')

    fig1.align_labels()

    # 軌跡
    fig2 = plt.figure(figsize=(8, 8))
    ax = fig2.add_subplot()
    ax.plot(df_rtk['x'], df_rtk['y'], color='tab:blue')
    ax.set_aspect('equal')
    ax.set_xlabel('x [m]')
    ax.set_ylabel('y [m]')

if __name__ == '__main__':
    directory = 'data/191211_1649'
    # directory = 'data/200116_1104'
    # directory = 'data/200116_1121'
    df_acc = loadAccData(directory+'/acc.csv')
    df_rtk = loadRTKData(directory+'/rtk.csv')
    df_acc, df_rtk = fitData(df_acc, df_rtk)
    plot(df_acc, df_rtk)
    
    print(df_acc.keys())
    print(df_rtk.keys())

if __name__ == '__main__':
    df_gps = loadGPSData(directory+'/gps.csv',
                         df_rtk['latitude(deg)'][0],
                         df_rtk['longitude(deg)'][0])
    df_gps = df_gps[df_acc.index[0]:]

    plt.figure(figsize=(8, 8))
    plt.plot(df_rtk['x'], df_rtk['y'], color='tab:gray')
    plt.plot(df_gps['x'], df_gps['y'], color='tab:green')
    plt.axes().set_aspect('equal')
    plt.xlabel('x [m]')
    plt.ylabel('y [m]')