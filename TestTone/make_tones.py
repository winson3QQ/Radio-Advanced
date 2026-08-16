# -*- coding: utf-8 -*-
"""
產生 Demo 3 / Demo 4 用的 1 kHz 測試音檔。

1kHz_staircase.wav   音量階梯，一次掃完，用來找頻偏限幅器的平台
1kHz_steady_XXdB.wav 各級的定值音，用來拍平台區的 FFT 量測圖

1 kHz @ 48 kHz 取樣 = 每週期整數 48 點，段落邊界不會有相位跳變。
每段首尾各 10 ms 升餘弦淡入淡出，避免切換瞬間的喀嚓聲汙染頻譜。
"""
import math
import os
import struct
import wave

SR = 48000          # 取樣率
TONE_HZ = 1000.0    # 測試音頻率
FADE_MS = 10        # 淡入淡出長度
LEVELS_DB = [-45, -40, -35, -30, -25, -20, -15, -10, -5, 0]

STAIR_TONE_S = 2.5  # 階梯每一階的長度
STAIR_GAP_S = 0.3   # 階與階之間的靜音（純載波，當作分隔線）
STAIR_LEAD_S = 2.0  # 開頭的靜音，留一段未調變載波當基準
STEADY_TONE_S = 12.0
STEADY_LEAD_S = 1.0

OUTDIR = os.path.dirname(os.path.abspath(__file__))


def tone(level_db, seconds, phase=0.0):
    """回傳 (samples, 結束時的相位)。samples 為 -1..1 的 float。"""
    amp = 10.0 ** (level_db / 20.0)
    n = int(round(seconds * SR))
    fade = min(int(FADE_MS * SR / 1000), n // 2)
    out = []
    w = 2.0 * math.pi * TONE_HZ / SR
    for i in range(n):
        s = amp * math.sin(phase + w * i)
        if fade:
            if i < fade:
                s *= 0.5 - 0.5 * math.cos(math.pi * i / fade)
            elif i >= n - fade:
                j = n - 1 - i
                s *= 0.5 - 0.5 * math.cos(math.pi * j / fade)
        out.append(s)
    return out, (phase + w * n) % (2.0 * math.pi)


def silence(seconds):
    return [0.0] * int(round(seconds * SR))


def write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))
    print("%-34s %5.1f s" % (os.path.basename(path), len(samples) / float(SR)))


def main():
    buf = silence(STAIR_LEAD_S)
    phase = 0.0
    for db in LEVELS_DB:
        seg, phase = tone(db, STAIR_TONE_S, phase)
        buf += seg + silence(STAIR_GAP_S)
    write_wav(os.path.join(OUTDIR, "1kHz_staircase.wav"), buf)

    for db in LEVELS_DB:
        seg, _ = tone(db, STEADY_TONE_S)
        name = "1kHz_steady_%+03ddB.wav" % db
        write_wav(os.path.join(OUTDIR, name), silence(STEADY_LEAD_S) + seg)


if __name__ == "__main__":
    main()
