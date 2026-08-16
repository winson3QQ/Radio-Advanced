# -*- coding: utf-8 -*-
"""
從 SDR++ 截圖量測亞音（CTCSS）頻率。

原理：亞音是持續的低頻調變音，在射頻頻譜上是載波兩側間隔 = 亞音頻率的一排邊帶。
量譜線間隔即得亞音頻率，不需要解碼器。

畫面的垂直格線用來當絕對刻度（SDR++ 會挑整數 Hz），所以每張圖都是獨立量測，
不需要拿其中一張當校正基準。

用法:
    python analyze_ctcss.py <資料夾> [--grid-hz 100]

檔名需含 .<頻率>T-CTCS 才能自動比對設定值，例如
    adi-TxLow.Narrow.203.5T-CTCS.png
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

PLOT_X = (350, 1850)     # FFT 繪圖區的水平範圍
PLOT_Y = 700             # 瀑布圖上緣，以下不看
GRID_ROW = 130           # 取這一列找格線（訊號上方的空白處）
GRID_VAL = 90            # SDR++ 格線的灰階值
TRACE_MIN_PROMINENCE = 15  # 譜線需高出底噪的像素數


def gridline_pitch(a):
    """回傳格線間距（px）。"""
    row = a[GRID_ROW, :, :].mean(axis=1)
    xs = np.where(np.abs(row - GRID_VAL) < 4)[0]
    xs = xs[(xs > PLOT_X[0] - 10) & (xs < PLOT_X[1] + 30)]
    if len(xs) < 4:
        return None
    groups = []
    for x in xs:
        if not groups or x - groups[-1][-1] > 3:
            groups.append([x])
        else:
            groups[-1].append(x)
    centres = [int(np.mean(g)) for g in groups]
    return float(np.median(np.diff(centres))) if len(centres) > 3 else None


def trace_peaks(a):
    """回傳黃色 FFT trace 的區域極大值 x 座標。"""
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    yellow = (r > 180) & (g > 170) & (b < 110)
    yellow[PLOT_Y:, :] = False
    yellow[:, :PLOT_X[0]] = False
    yellow[:, PLOT_X[1]:] = False

    height = np.full(a.shape[1], np.nan)
    for x in range(*PLOT_X):
        ys = np.where(yellow[:, x])[0]
        if len(ys):
            height[x] = -ys.min()          # y 越小訊號越強，取負號讓「大 = 強」

    valid = ~np.isnan(height)
    if not valid.any():
        return []
    floor = np.nanmin(height[valid])

    peaks = []
    for x in range(PLOT_X[0] + 6, PLOT_X[1] - 6):
        window = height[x - 6:x + 7]
        if np.isnan(window).any():
            continue
        if height[x] == np.nanmax(window) and height[x] > floor + TRACE_MIN_PROMINENCE:
            if not peaks or x - peaks[-1] > 15:
                peaks.append(x)
            elif height[x] > height[peaks[-1]]:
                peaks[-1] = x
    return peaks


def line_pitch(peaks):
    """譜線間距（px）。取中位數，自動忽略被 VFO 游標線遮住而形成的雙倍間距。

    間距不規律（變異係數 > 10%）代表偵測到的是底噪起伏而非梳齒，回傳 None。
    真正的單音調變邊帶變異係數通常在 3% 以內。
    """
    if len(peaks) < 4:
        return None
    d = np.diff(peaks)
    med = np.median(d)
    # 只留中位數 ±30% 內的間距：同時剔除「被 VFO 線遮住的雙倍間距」與零星假峰
    unit = d[(d > med * 0.7) & (d < med * 1.3)]
    if len(unit) < 3:
        return None
    if unit.std() / unit.mean() > 0.10:
        return None
    return float(np.median(unit))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--grid-hz', type=float, default=100.0,
                    help='一格代表多少 Hz（依 SDR++ 縮放而定，預設 100）')
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.folder, '*.png')))
    if not files:
        sys.exit('找不到 png：%s' % args.folder)

    print('%-10s %6s %9s %8s %11s %8s' %
          ('設定(Hz)', '譜線數', '間距(px)', '佔幾格', '讀出值(Hz)', '誤差'))
    print('-' * 60)

    for path in files:
        name = os.path.basename(path)
        a = np.asarray(Image.open(path).convert('RGB')).astype(int)

        pitch_px = gridline_pitch(a)
        if pitch_px is None:
            print('%-10s  (找不到格線，略過)' % name)
            continue

        peaks = trace_peaks(a)
        pitch = line_pitch(peaks)
        m = re.search(r'\.([\d.]+)T-CTCS', name)
        label = float(m.group(1)) if m else None

        if pitch is None:
            print('%-10s %6d   —— 無梳齒（單一載波）' %
                  (label if label else name, len(peaks)))
            continue

        cells = pitch / pitch_px
        est = cells * args.grid_hz
        if label:
            err = '%+.1f%%' % ((est - label) / label * 100)
            print('%-10.1f %6d %9.1f %8.2f %11.1f %8s'
                  % (label, len(peaks), pitch, cells, est, err))
        else:
            print('%-10s %6d %9.1f %8.2f %11.1f %8s'
                  % (name, len(peaks), pitch, cells, est, '—'))

    print()
    print('格線刻度假設為 %g Hz/格。換過縮放請用 --grid-hz 指定。' % args.grid_hz)


if __name__ == '__main__':
    main()
