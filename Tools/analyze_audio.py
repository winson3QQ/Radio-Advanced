# -*- coding: utf-8 -*-
"""
分析 SDR++ Recorder 錄下的解調音訊（Demo 3 的四格矩陣用）。

會自動切出三段（無載波嘶嘶 / 載波無調變 / 載波+測試音），然後報告：
  * FM 靜噪效果（載波一出現，雜訊掉多少 dB）
  * 測試音基波位準與各次諧波（判斷破音）
  * SNR

用短視窗平均的 FFT，不用長時間相干積分 —— 手機與 SDR 的時鐘各自獨立會漂移，
長視窗相干積分會把訊號抹掉。

用法:
    python analyze_audio.py <wav檔或資料夾> [--tone 1000]
"""
import argparse
import glob
import os
import sys
import wave

import numpy as np

WIN = 8192               # FFT 視窗（0.17 s @48k，解析約 6 Hz）
RUMBLE = (150, 800)      # 低頻雜音帶（機械共振 / 桌面震動會出現在這）


def load(path):
    w = wave.open(path, 'rb')
    sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n)
    w.close()
    dt = {1: np.int8, 2: np.int16, 4: np.int32}[sw]
    x = np.frombuffer(raw, dtype=dt).astype(np.float64) / float(2 ** (8 * sw - 1))
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def envelope(x, sr, step=0.1):
    hop = int(sr * step)
    return np.array([20 * np.log10(np.sqrt(np.mean(x[i:i + hop] ** 2)) + 1e-20)
                     for i in range(0, len(x) - hop, hop)]), hop


def spectrum(seg, sr):
    """短視窗平均頻譜，回傳 (頻率, 等效正弦振幅 dBFS)。"""
    win = np.hanning(WIN)
    cg = win.sum() / WIN
    acc = np.zeros(WIN // 2 + 1)
    cnt = 0
    for i in range(0, len(seg) - WIN, WIN // 2):
        acc += np.abs(np.fft.rfft(seg[i:i + WIN] * win)) ** 2
        cnt += 1
    if cnt == 0:
        return None, None
    return np.fft.rfftfreq(WIN, 1 / sr), 20 * np.log10(2 * np.sqrt(acc / cnt) / (WIN * cg) + 1e-20)


def peak(f, d, lo, hi):
    m = (f > lo) & (f < hi)
    return (d[m].max(), f[m][d[m].argmax()]) if m.any() else (float('nan'), float('nan'))


def rms_db(seg):
    return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-20)


def segments(env, hop, sr, n):
    """依位準把錄音切成三段。回傳 (嘶嘶, 載波無調變, 訊號) 的取樣範圍，找不到就 None。"""
    lo, hi = env.min(), env.max()
    if hi - lo < 12:
        return None
    mid = (lo + hi) / 2
    loud = np.where(env > mid)[0]
    if len(loud) == 0:
        return None
    # 訊號段：位準最高的連續區塊，取中段避開起止過渡
    s, e = loud[0] * hop, (loud[-1] + 1) * hop
    trim = (e - s) // 5
    sig = (s + trim, e - trim)
    quiet = np.where(env < mid)[0]
    qui = ((quiet[0] * hop, (quiet[-1] + 1) * hop) if len(quiet) else None)
    return sig, qui


def analyse(path, tone):
    x, sr = load(path)
    print('=' * 66)
    print('%s   %.1f s @ %d Hz' % (os.path.basename(path), len(x) / sr, sr))
    env, hop = envelope(x, sr)
    print('包絡 最低 %.1f  最高 %.1f dBFS' % (env.min(), env.max()))

    clipped = int((np.abs(x) > 0.99).sum())
    if clipped:
        print('!! 數位削波：%d 個樣本頂到滿刻度，失真數據不可信' % clipped)

    seg = segments(env, hop, sr, len(x))
    if seg is None:
        print('!! 位準全程沒有變化 —— 很可能整段都是空頻道雜訊，訊號沒進來')
        return
    (a, b), qui = seg
    s = x[a:b]
    print('訊號段 %.1f~%.1f s   RMS %.1f dBFS' % (a / sr, b / sr, rms_db(s)))
    if qui:
        q = x[qui[0]:qui[1]]
        print('安靜段 %.1f~%.1f s   RMS %.1f dBFS   → 差 %.1f dB'
              % (qui[0] / sr, qui[1] / sr, rms_db(q), rms_db(s) - rms_db(q)))

    f, d = spectrum(s, sr)
    if f is None:
        print('訊號段太短，無法分析')
        return
    base, bf = peak(f, d, tone * 0.96, tone * 1.04)
    print()
    print('  基波 %5.0f Hz   %7.1f dBFS  (峰值落在 %.0f Hz)' % (tone, base, bf))
    rum, rf = peak(f, d, *RUMBLE)
    flag = 'OK' if base - rum >= 20 else '<<< 未達標，低頻雜音太大'
    print('  %d-%d Hz 雜音  %7.1f dBFS   基波下 %5.1f dB  %s'
          % (RUMBLE[0], RUMBLE[1], rum, base - rum, flag))
    tot = 0.0
    for k in (2, 3, 4, 5):
        v, _ = peak(f, d, tone * k - 40, tone * k + 40)
        tot += (10 ** (v / 20)) ** 2
        flag = 'OK' if base - v >= 20 else '<<< 未達標'
        print('  %d 次諧波       %7.1f dBFS   基波下 %5.1f dB  %s' % (k, v, base - v, flag))
    print('  THD           %7.1f %%' % (100 * np.sqrt(tot) / (10 ** (base / 20))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target', help='wav 檔或資料夾')
    ap.add_argument('--tone', type=float, default=1000.0, help='測試音頻率（預設 1000）')
    args = ap.parse_args()

    if os.path.isdir(args.target):
        files = sorted(glob.glob(os.path.join(args.target, '*.wav')))
    else:
        files = [args.target]
    if not files:
        sys.exit('找不到 wav：%s' % args.target)
    for p in files:
        analyse(p, args.tone)


if __name__ == '__main__':
    main()
