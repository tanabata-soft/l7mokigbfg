#!/usr/bin/env python3
"""譜面生成 v5 / v4: src/game/assets/*.mp3 を解析して src/game/data/charts.json を作る。

v5 の変更点（根拠は docs/CHART-DESIGN.md の「譜面 v5」節、曲別方針は SONGS のメタデータ）:
- V5-1 特徴量レイヤー: HPSS で打撃成分（ドラム）と持続成分を分け、持続成分の
  旋律帯域（600〜6000Hz）＝メロディ／声帯域（600〜3000Hz）×有声度＝ボーカル
  の帯域別オンセット強度と、pyin の F0 をスロット属性に持つ。ゲートの物差しは
  レイヤー強度を全帯域 strength の分布へ順位写像した eff（順位が同じなら値が
  同じになるため、既存の閾値がそのまま意味を持つ）。
- V5-2 主レイヤー選択: フレーズごとに主パート（drums/melody/vocal/mixed）を
  決め（曲別バイアス＋サビの指定レイヤーへのボーナス。サビは連続フレーズを
  グループとして1回だけ決める。通常フレーズ間はヒステリシス 0.08）、
  パターン選択・同時押し・密度の床が見る strength を主レイヤーの eff に切替。
- V5-3 音高コンター: 主レイヤーがメロディ/ボーカルのとき、F0 の動きとレーン
  移動の方向の一致を fit コストに反映（|ΔF0|≥1半音: 同方向 −0.20／逆方向
  +0.45／不動 +0.15。同音反復は jack のゲート緩和にも使う）。
- burst（16分パターン）のゲートだけは主レイヤーで測らない: 持続成分の
  フラックスは16分位置のすべてで高く出て常時開いてしまうため、根拠の
  取り方を曲別に選ぶ（SONGS の burst_basis: main / drums / main65）。
- 特徴量の照合と指標の道具は scripts/analyze-layers.py。

v4 の変更点（オーナー指示「基本両手（両親指）でやることを前提にやりやすい譜面に」。
根拠は docs/CHART-DESIGN.md の「両親指前提（譜面 v4）」節）:
- レーン 0・1 を左親指、2・3 を右親指が受け持つ前提で、両親指のハード制約を
  生成に組み込んだ（制約の正本は scripts/check-two-thumb.py）:
  C1 同時押しは左右に分かれるペアだけ（同側ペア禁止）。
  C2 長押し中は拘束側のノーツを置かない（帯の中は反対側だけ。同時押しの
     ある時刻をまたぐ長押しも置かない）。同時ホールドは同側同士で重ねない。
  C3a 16分の連なりで同側3連を作らない（トリルは左右交互に変更、wave16 の
     形も同側3連が出ない形に変更。フィット時の罰金＋生成後の修復でも担保）。
  C3b 同側2レーン交互（片手トリル）は8分以下の速さで4連まで
     （フィット時の罰金＋生成後の修復で担保）。
  C4 同一レーン連続は従来ルール（hard の縦連だけ例外）を維持。
- 生成後は check-two-thumb.py の check_charts() で全譜面を検証し、違反が
  あれば charts.json を書き出さずに終了する。

v2 の土台（維持）:
- 拍グリッドは librosa の実測拍列に沿わせる（回帰直線＋残差の移動平均で平滑化し、
  16分スロットは隣り合う拍の間を4等分して補間。累積ドリフトが出ない）。
- 選んだスロットの近く（±38ms）に強いオンセットピークがあればスナップする
  （v2 は ±50ms。遠いピークは別のリズム事象のことが多く、寄せると拍グリッドから
  離れてズレ統計が悪化するため v3 で狭めた）。
- 密度は小節ごとの RMS エネルギーに連動。節の切れ目（FEVER境界・エネルギーの
  落ち際）の直前には小さな休符を作る。
- FEVER 区間は密度を上乗せする（v1.9.0、オーナー指示「フィーバー中はノードも
  多くして、気持ちよく叩けるように」）: 計画エネルギーの底上げ＋16分パターンの
  確率アップ（plan_phrase）と、間引きでの FEVER 優先（thin）で効かせる。
- charts.json に実測拍列（beats）も保存し、単体テストがズレを検証する。
- 表示 BPM は回帰から求めた実測値（整数）。FEVER 区間は固定値のまま。

v3 の変更点（設計の根拠は docs/CHART-DESIGN.md）:
- ノーツの置き方を「強度順の貪欲ピック」から「フレーズ単位のパターン割り当て」に
  変えた。半小節を単位に、階段／波／交互／交差／縦連／トリル等の型を意図的に
  割り当て、型の連続として譜面を組み立てる。
- サビ（FEVER）のフレーズでは、最初のサビのパターンの並び（モチーフ）を後の
  サビで再登場させる。2回目はレーン鏡像、3回目は末尾も変化させる。サビ内でも
  後半は前半のパターンを繰り返す。
- 同時押し: サビの小節頭など特に強い拍に2レーン同時押し（hard 中心、normal は
  ごく強い拍だけ、easy はなし）。
- 長押し: オンセットが長く空き、その間も音が鳴り続ける場所（持続音）に置く。
  長さは拍単位。easy は短く少数で長押し中は他のノーツなし、normal は長押し中の
  他レーンノーツが少ないものだけ、hard はサビ中心に長押し＋他レーンタップあり。
- 入れ子（easy ⊆ normal ⊆ hard）は (時刻, レーン) で維持する。normal は hard の
  8分位置の骨格、easy は拍位置のみ。
- 同一レーン3連続は原則禁止。例外は hard の縦連（間隔 170ms 以上の3連まで）。

使い方: .venv/bin/python scripts/generate-charts.py
前提: .venv に librosa、PATH に ffmpeg（mp3 を wav に変換するため）
"""
import bisect
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import librosa

ROOT = Path(__file__).resolve().parent.parent
SR = 22050
HOP = 512

# 曲のメタデータ。曲を足すときは、ここに1曲分を足し、src/assets/<id>.mp3 と
# src/assets/<id>.jpg（ジャケット）を置いて、src/charts.ts の SONGS にも同じ id で
# エントリを足す（手順は docs/START-HERE.md）。
#   title: 表示名
#   audio: 音源（MP3。AAC/m4a はヘッドレス Chromium がデコードできないため使わない）
#   fever: FEVER（サビ）区間 [開始秒, 終了秒) の列。歌詞字幕や波形の盛り上がりから決める
#   chart_v5: True で v5（特徴量レイヤー＋フレーズ単位の主レイヤー選択）を使う
#   layer_bias: 主レイヤー選択の曲別バイアス（drums / melody / vocal への加算）
#   chorus_layer: サビ（FEVER）で優先する主レイヤー
#   chorus_bonus: サビの chorus_layer へのボーナス（既定 0.30）
#   burst_basis: 16分パターンのゲートの根拠（main / drums / main65）
#   chord_gate_drop: 同時押しの強さゲートだけを下げる曲別調整（強弱が均一な曲用。既定 0）
SONGS = {
    # NK-S009『Flavor』の収録曲。音源は src/game/assets/track0N.mp3
    # （CD 側の MP4 から音声だけを MP3 192kbps で書き出したもの）。
    # FEVER（サビ）区間は、歌詞（src/album/sync.ts）の反復ブロックから決める:
    # サビの歌詞ブロックの先頭行の開始秒を開始、末尾行の歌唱が終わる頃を終了とする
    # （NK-S003 での決め方）。
    # サビは歌に合わせて主レイヤーを vocal にする（NK-S003 のオーナー指示）。
    "flavor": {
        "title": "Flavor",
        "audio": "src/game/assets/track01.mp3",
        # サビ1: 52.6「甘くて 少しだけ切ない」〜76.9 の行の歌唱終わり /
        # サビ2: 125.9〜150.3 の行の歌唱終わり（アウトロ前）
        "fever": [[52.0, 84.0], [125.0, 158.0]],
        "chart_v5": True,
        "chorus_layer": "vocal",
        "chorus_bonus": 0.5,
    },
    "anata": {
        "title": "あなた",
        "audio": "src/game/assets/track02.mp3",
        # サビは「あなたの指先も 唇も 体温も」の反復ブロック（3回）:
        # 45.4〜51.7 / 107.7〜114.5 / 162.9〜169.7 の行の歌唱終わり
        "fever": [[45.0, 58.0], [107.0, 120.0], [162.0, 176.0]],
        "chart_v5": True,
        "chorus_layer": "vocal",
        "chorus_bonus": 0.5,
    },
}

START_MS = 2000  # 最初のノーツはイントロ後
END_MARGIN_S = 1.2  # 最後のノーツは曲終了のこれ以上前に置く
HARD_CAP = 820  # hard の総ノーツ数の上限（安全弁。パターン＋同時押し＋長押し込み）
NORMAL_CAP = 410  # normal の総ノーツ数の上限（8分の骨格を強さ順に間引く）
EASY_CAP = 210  # easy の総ノーツ数の上限（拍位置のみを強さ順に間引く）
FEVER_GAP_FILL_S = 2.9  # FEVER 区間でこの秒数を超える空白は、間引きで落ちた候補を戻して埋める
SNAP_WINDOW_MS = 38  # オンセットピークへ寄せる範囲（遠いピークは別のリズム事象なので寄せない）
SNAP_MIN_GAP_MS = 100  # スナップ後に許す同一レーンの最小間隔
LANE_MIN_SHARE = 0.18  # レーン分布の下限（単体テストでも検証）
LANE_MAX_SHARE = 0.32  # レーン分布の上限（単体テストでも検証）
JACK_MIN_GAP_MS = 170  # hard で同一レーン3連（縦連）を許す最小間隔
HOLD_TARGET = 13  # hard の長押し本数の目安
SEED = 20251119

# パターンの語彙。半小節（2拍＝16分スロット8個）を単位に、rel=単位内の16分位置、
# off=レーンの相対オフセット（フィット時に平行移動と鏡像で実レーンへ写す）。
# v4: 16分パターン（burst）は、どのフィットでも同側3連（C3a）にならない形にする。
# - trill は同側2レーンの交互（片手トリル）をやめ、左右交互（0↔2 / 1↔3 系）に変更。
# - wave16 は往復形 [0,1,2,3,2,1,0,1] だと右側3連（2,3,2）が出るため、
#   左右2連ずつの往復 [0,1,3,2,1,0,2,3] に変更（鏡像も同側最大2連）。
# - roll は元から左右2連ずつで問題なし。
PATTERNS = {
    "stair": {"rel": [0, 2, 4, 6], "off": [0, 1, 2, 3], "burst": False},
    "wave": {"rel": [0, 2, 4, 6], "off": [0, 1, 2, 1], "burst": False},
    "alt": {"rel": [0, 2, 4, 6], "off": [0, 1, 0, 1], "burst": False},
    "cross": {"rel": [0, 2, 4, 6], "off": [0, 2, 1, 3], "burst": False},
    "jack": {"rel": [0, 2, 4], "off": [0, 0, 0], "burst": False},
    "trill": {"rel": [0, 1, 2, 3, 4, 5, 6, 7], "off": [0, 2, 0, 2, 0, 2, 0, 2], "burst": True},
    "roll": {"rel": [0, 1, 2, 3, 4, 5, 6, 7], "off": [0, 1, 2, 3, 0, 1, 2, 3], "burst": True},
    "wave16": {"rel": [0, 1, 2, 3, 4, 5, 6, 7], "off": [0, 1, 3, 2, 1, 0, 2, 3], "burst": True},
    "sparse": {"rel": [], "off": [], "burst": False},
}
BURST_PATTERNS = {name for name, p in PATTERNS.items() if p["burst"]}


def to_wav(src: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ar", str(SR), "-ac", "1", str(dst)],
        check=True,
    )


def smoothed_beats(y, sr):
    """実測拍列を平滑化して (拍時刻[s], 回帰周期[s], 実測BPM) を返す。

    平滑化は「拍番号→時刻の回帰直線」＋「残差の移動平均（9拍）」。回帰が全体の
    累積位置（端点）を保ち、移動平均が局所的な追随を残す。最後に単調増加を保証する。
    """
    _, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    beats = np.asarray(beats, dtype=float)
    k = np.arange(len(beats), dtype=float)
    slope, intercept = np.polyfit(k, beats, 1)
    resid = beats - (intercept + slope * k)
    w = 9
    pad = w // 2
    smooth_resid = np.convolve(np.pad(resid, pad, mode="edge"), np.ones(w) / w, mode="valid")
    smoothed = intercept + slope * k + smooth_resid
    min_step = slope * 0.5
    for i in range(1, len(smoothed)):
        if smoothed[i] < smoothed[i - 1] + min_step:
            smoothed[i] = smoothed[i - 1] + min_step
    return smoothed, float(slope), 60.0 / float(slope)


def extend_beats(beats, period, duration):
    """拍列の両端を回帰周期で延長し、曲全体（0〜duration）を覆う拍列にする。"""
    pre = []
    t = beats[0] - period
    while t > -period:
        pre.append(t)
        if t <= 0:
            break
        t -= period
    post = []
    t = beats[-1] + period
    while t < duration + period:
        post.append(t)
        t += period
    return np.array(pre[::-1] + list(beats) + post, dtype=float)


def build_slots(ext_beats, period):
    """16分スロット列。各スロットは dict(beat=拍番号, sub=拍内位置0-3, time=秒)。"""
    slots = []
    for i, bt in enumerate(ext_beats):
        nxt = ext_beats[i + 1] if i + 1 < len(ext_beats) else bt + period
        for sub in range(4):
            slots.append({"beat": i, "sub": sub, "time": float(bt + (nxt - bt) * sub / 4)})
    return slots


def bar_energies(y, sr, ext_beats):
    """小節（4拍）ごとの RMS エネルギーを 0..1 に正規化して返す（拍番号//4 がキー）。"""
    raw = {}
    n = len(ext_beats)
    for bar_start in range(0, n - 4, 4):
        t0, t1 = ext_beats[bar_start], ext_beats[bar_start + 4]
        i0 = max(0, int(t0 * sr))
        i1 = min(len(y), int(t1 * sr))
        if i1 <= i0:
            continue
        rms = float(np.sqrt(np.mean(y[i0:i1] ** 2)))
        raw[bar_start // 4] = 20 * np.log10(max(rms, 1e-6))
    if not raw:
        return {}
    vals = np.array(list(raw.values()))
    lo, hi = np.percentile(vals, 10), np.percentile(vals, 95)
    span = max(hi - lo, 1e-9)
    return {bar: float(min(1.0, max(0.0, (v - lo) / span))) for bar, v in raw.items()}


def slot_strengths(onset_env, sr, times):
    """各スロット時刻の前後 ±45ms でのオンセット強度の最大値。"""
    out = []
    for t in times:
        c = int(t * sr / HOP)
        w = max(1, int(0.045 * sr / HOP))
        lo, hi = max(0, c - w), min(len(onset_env), c + w + 1)
        out.append(float(onset_env[lo:hi].max()) if hi > lo else 0.0)
    return np.array(out)


def onset_peaks(onset_env, sr):
    """強いオンセットピークの (時刻[s], 強さ) 列。局所最大かつ高さが局所最大の55%以上。"""
    env = onset_env
    idx = [i for i in range(1, len(env) - 1) if env[i] >= env[i - 1] and env[i] >= env[i + 1] and env[i] > 0]
    if not idx:
        return []
    heights = env[idx]
    thr = np.percentile(heights, 55)
    return [(i * HOP / sr, float(env[i])) for i in idx if env[i] >= thr]


def snap_notes(notes, peaks):
    """各ノーツを ±SNAP_WINDOW_MS 内の最強オンセットピークへ寄せる。スナップした数を返す。"""
    snapped = 0
    for note in notes:
        t = note["time_ms"] / 1000
        best = None
        for pt, ps in peaks:
            d = abs(pt - t)
            if d * 1000 <= SNAP_WINDOW_MS and (best is None or ps > best[1]):
                best = (pt, ps)
        if best is not None:
            new_ms = int(round(best[0] * 1000))
            if new_ms != note["time_ms"]:
                snapped += 1
            note["time_ms"] = new_ms
    return snapped


def pitch_lanes(y, sr, times_s):
    """音高（piptrack の中央値）の四分位レーン。レーン決定では同点時の参考にだけ使う。"""
    f0, mag = librosa.piptrack(y=y, sr=sr, fmin=80, fmax=1200)
    midis = []
    for t in times_s:
        c = int(t * sr / HOP)
        lo, hi = max(0, c - 2), min(f0.shape[1], c + 3)
        vals = []
        for j in range(lo, hi):
            k = int(np.argmax(mag[:, j]))
            if mag[k, j] > 0 and f0[k, j] > 0:
                vals.append(librosa.hz_to_midi(f0[k, j]))
        midis.append(float(np.median(vals)) if vals else 60.0)
    q = np.percentile(midis, [25, 50, 75])
    return [int(np.searchsorted(q, m)) for m in midis]


# ---- v5: 特徴量レイヤー（V5-1。設計は docs/CHART-DESIGN.md の譜面 v5 節） ----
# スロットに「何の音か」の属性を付ける。帯域別オンセット強度（スペクトラル
# フラックス）、HPSS の打撃/持続分離、pyin の F0 と有声確率から、
# drums / melody / vocal の3レイヤーの strength を作る。
# この段階では特徴量を計算するだけで、生成の挙動は変えない（使うのは V5-2 以降、
# かつ SONGS で chart_v5 を指定した曲だけ）。

LAYER_BANDS = {  # 特徴量レポート用の帯域（Hz）
    "low": (0.0, 160.0),  # キック/ベース
    "midlow": (160.0, 600.0),
    "mid": (600.0, 3000.0),  # ボーカル/リードの存在域
    "high": (6000.0, None),  # ハット/シンバル
}
MELODY_BAND = (600.0, 6000.0)  # リード楽器の存在域（harmonic 成分で見る）
VOCAL_BAND = (600.0, 3000.0)  # ボーカルの存在域（harmonic 成分で見る）


def _band_flux(mag, freqs, lo, hi):
    """STFT 振幅の帯域内スペクトラルフラックス（正の差分の合計）の時系列。"""
    hi = float("inf") if hi is None else hi
    band = mag[(freqs >= lo) & (freqs < hi)]
    if band.size == 0:
        return np.zeros(mag.shape[1])
    diff = np.diff(band, axis=1)
    flux = np.maximum(diff, 0.0).sum(axis=0)
    return np.concatenate([[0.0], flux])


def _sample_max(series, times, sr):
    """slot_strengths と同じ ±45ms 窓の最大値サンプリング。"""
    out = []
    w = max(1, int(0.045 * sr / HOP))
    for t in times:
        c = int(t * sr / HOP)
        lo, hi = max(0, c - w), min(len(series), c + w + 1)
        out.append(float(series[lo:hi].max()) if hi > lo else 0.0)
    return np.array(out)


def compute_layer_features(y, sr, times):
    """スロット時刻列に対する v5 特徴量を dict で返す（すべて times と同じ長さ）。

    drums: 打撃成分（HPSS percussive）のオンセット強度。
    melody: 持続成分（HPSS harmonic）のリード帯域フラックス。
    vocal: 持続成分のボーカル帯域フラックス × 有声確率（フレーム単位で掛けてから抽出）。
    band_*: 全信号の帯域別フラックス（レポート用）。
    f0: pyin の F0（midi。無声・未検出は nan）。voiced: 有声確率。
    harm_rms: 持続成分の RMS（サステイン量。V5-4 用に併記）。
    """
    y_harm, y_perc = librosa.effects.hpss(y)
    onset_perc = librosa.onset.onset_strength(y=y_perc, sr=sr, hop_length=HOP)
    mag_full = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    mag_harm = np.abs(librosa.stft(y_harm, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    flux_harm_mel = _band_flux(mag_harm, freqs, *MELODY_BAND)
    flux_harm_voc = _band_flux(mag_harm, freqs, *VOCAL_BAND)
    bands = {name: _band_flux(mag_full, freqs, lo, hi) for name, (lo, hi) in LAYER_BANDS.items()}

    f0_hz, vflag, vprob = librosa.pyin(
        y_harm,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C6"),
        sr=sr,
        hop_length=HOP,
    )
    # pyin の voiced_prob は絶対値が極端に小さい（有声判定フレームでも平均 0.14
    # 程度）ため、そのままでは重みとして使えない。
    # 有声の物差しは voiced_flag（HMM の判定）を使い、±2フレームの移動平均で
    # 0..1 の柔らかい値にする。voiced_prob は参考として併記しない。
    flag = np.asarray(vflag, dtype=float)
    if len(flag):
        pad = 2
        soft_voiced = np.convolve(
            np.pad(flag, pad, mode="edge"), np.ones(2 * pad + 1) / (2 * pad + 1), mode="valid"
        )
    else:
        soft_voiced = flag
    n_fr = min(len(flux_harm_voc), len(soft_voiced))
    vocal_series = flux_harm_voc[:n_fr] * soft_voiced[:n_fr]
    frame_times = librosa.times_like(f0_hz, sr=sr, hop_length=HOP)
    harm_rms = librosa.feature.rms(y=y_harm, hop_length=HOP)[0]

    f0_out, voiced_out = [], []
    for t in times:
        j = int(np.argmin(np.abs(frame_times - t))) if len(frame_times) else 0
        v = float(soft_voiced[j]) if len(soft_voiced) else 0.0
        voiced_out.append(v)
        val = float("nan")
        for d in (0, -1, 1, -2, 2):
            k = j + d
            if 0 <= k < len(f0_hz) and not np.isnan(f0_hz[k]) and f0_hz[k] > 0:
                val = float(librosa.hz_to_midi(f0_hz[k]))
                break
        f0_out.append(val)

    return {
        "drums": _sample_max(onset_perc, times, sr),
        "melody": _sample_max(flux_harm_mel, times, sr),
        "vocal": _sample_max(vocal_series, times, sr),
        "band_low": _sample_max(bands["low"], times, sr),
        "band_midlow": _sample_max(bands["midlow"], times, sr),
        "band_mid": _sample_max(bands["mid"], times, sr),
        "band_high": _sample_max(bands["high"], times, sr),
        "f0": np.array(f0_out),
        "voiced": np.array(voiced_out),
        "harm_rms": _sample_max(harm_rms, times, sr),
    }


def _rank_map(values, ref):
    """values の順位（パーセンタイル）を ref の分布へ写す。eff_strength 用。

    主レイヤーの strength を全帯域 strength と同じ物差しに乗せるための変換で、
    ゲートの閾値（strength のパーセンタイル）がレイヤー側でも同じ意味になる。
    """
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    pct = ranks / max(1, len(values) - 1)
    return np.quantile(np.asarray(ref, dtype=float), pct)


CHORUS_LAYER_BONUS = 0.30  # サビで曲別方針の主レイヤー（chorus_layer）へ寄せる量
LAYER_HYSTERESIS = 0.08  # 主レイヤーの切替を抑える差（これ未満なら直前を継続）
LAYER_MIXED_FLOOR = 0.16  # 全レイヤーがこの弱さなら mixed（v4 の挙動）にする


def assign_layer_for(meta, pslots, is_chorus, prev_layer):
    """フレーズの主レイヤーを決める（V5-2）。(レイヤー名, スコア) を返す。

    スコアはフレーズ内スロットの lay_n 平均＋曲別バイアス（layer_bias）＋
    サビの指定レイヤーへのボーナス。フレーズ途中で切り替えないための
    ヒステリシスとして、直前の主レイヤーとの差が LAYER_HYSTERESIS 未満なら
    直前を継続する。全レイヤーが弱いフレーズは mixed にする。
    """
    scores = {
        layer: float(np.mean([s["lay_n"][layer] for s in pslots])) if pslots else 0.0
        for layer in ("drums", "melody", "vocal")
    }
    for k, b in meta.get("layer_bias", {}).items():
        if k in scores:
            scores[k] += b
    if is_chorus and meta.get("chorus_layer") in scores:
        # ボーナス量は曲別に上書きできる（chorus_bonus）。サビでもリード楽器が
        # 鳴り続ける曲では、標準量では切り替わらないため
        scores[meta["chorus_layer"]] += meta.get("chorus_bonus", CHORUS_LAYER_BONUS)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] < LAYER_MIXED_FLOOR:
        return "mixed", scores
    if prev_layer in scores and prev_layer != best and scores[best] - scores[prev_layer] < LAYER_HYSTERESIS:
        return prev_layer, scores
    return best, scores


def subdivision_positions(ext_beats):
    """拍列から作る16分細分位置（秒）の配列。ズレ検証用。"""
    pos = []
    for i, bt in enumerate(ext_beats):
        nxt = ext_beats[i + 1] if i + 1 < len(ext_beats) else bt + (ext_beats[i] - ext_beats[i - 1])
        for sub in range(4):
            pos.append(float(bt + (nxt - bt) * sub / 4))
    return np.array(pos)


def drift_stats(charts, subdiv, duration_ms):
    """難易度ごとに、ノーツと最寄り細分位置の符号付きズレ（ms）の統計を返す。

    曲を3分割した各区間の平均ズレが小さい＝回転ドリフトがないことの確認用。
    """
    stats = {}
    edges = [0, duration_ms / 3, 2 * duration_ms / 3, duration_ms + 1]
    for diff, notes in charts.items():
        deltas = []
        for n in notes:
            t = n[0] / 1000
            j = int(np.argmin(np.abs(subdiv - t)))
            deltas.append((subdiv[j] - t) * 1000)  # 細分位置 − ノーツ（符号付き）
        deltas = np.array(deltas)
        times = np.array([n[0] for n in notes], dtype=float)
        thirds = []
        for s in range(3):
            mask = (times >= edges[s]) & (times < edges[s + 1])
            d = deltas[mask]
            thirds.append(
                {
                    "mean": round(float(d.mean()), 1) if len(d) else 0.0,
                    "p90abs": round(float(np.percentile(np.abs(d), 90)), 1) if len(d) else 0.0,
                    "n": int(len(d)),
                }
            )
        stats[diff] = {
            "mean": round(float(deltas.mean()), 1),
            "meanAbs": round(float(np.abs(deltas).mean()), 1),
            "over30": round(float((np.abs(deltas) > 30).mean() * 100), 1),
            "p90abs": round(float(np.percentile(np.abs(deltas), 90)), 1),
            "maxabs": round(float(np.abs(deltas).max()), 1),
            "thirds": thirds,
        }
    return stats


# ---- パターンのフィット（相対オフセット → 実レーン） ----


def pattern_fits(offsets, mirror_only=False):
    """オフセット列の平行移動・鏡像バリエーション（実レーン列の候補）を返す。"""
    if not offsets:
        return [[]]
    mn, mx = min(offsets), max(offsets)
    span = mx - mn
    out = []
    seen = set()
    for mirror in ((True,) if mirror_only else (False, True)):
        base = [(mx - o) if mirror else o for o in offsets]
        base = [o - min(base) for o in base]
        for shift in range(0, 4 - span):
            lanes = tuple(o + shift for o in base)
            if lanes not in seen:
                seen.add(lanes)
                out.append(list(lanes))
    return out


# ---- フレーズと計画 ----


def segment_phrases(playable_bars, boundary_bars):
    """小節列をフレーズ（最大8小節）に分ける。切れ目は boundary_bars。"""
    phrases = []
    cur = []
    for bar in playable_bars:
        if cur and (bar in boundary_bars or len(cur) >= 8):
            phrases.append(cur)
            cur = []
        cur.append(bar)
    if cur:
        phrases.append(cur)
    return phrases


def plan_phrase(rng, phrase, unit_energy, unit_gate, unit_fever, is_chorus):
    """フレーズ内の各半小節にパターン名を割り当てる計画を返す。

    unit_energy(unit) -> 0..1、unit_gate(unit, kind) -> bool（burst/jack を置ける強さか）、
    unit_fever(unit) -> bool（FEVER 区間のユニットか）。
    unit は (bar, half) のタプル。

    FEVER 区間は密度を上げる（オーナー指示）: 計画エネルギーを +0.45 底上げして
    上の段に寄せ、16分パターン（burst）の確率も 0.42 → 0.75 に上げる。底上げは
    計画だけに効かせ、ノーツに残る energy（間引きの優先度など）は実測のままにする。
    難易度の下位（normal / easy）は間引きで自然に増え方が緩やかになる（拍位置だけの
    easy は控えめ、8分位置の normal は中くらい、全部残る hard が一番増える）。
    （底上げ量と burst 確率は 2026-11-20 にオーナー指示「サビの譜面をもっと増やす」
    で +0.30 → +0.45、0.62 → 0.75 に引き上げた。それ以前は Kiso v5 と同じ値）
    """
    units = [(bar, half) for bar in phrase for half in (0, 1)]
    plan = []
    for unit in units:
        e = unit_energy(unit)
        fever = unit_fever(unit)
        pe = min(1.0, e + 0.45) if fever else e
        r = rng.random()
        if pe < 0.28:
            name = "sparse" if r < 0.45 else rng.choice(["wave", "stair"])
        elif pe < 0.62:
            sparse_p = 0.03 if fever else 0.08
            jack_p = 0.065 if fever else 0.115
            if r < sparse_p:
                name = "sparse"
            elif r < jack_p and unit_gate(unit, "jack"):
                name = "jack"
            else:
                name = rng.choice(["stair", "wave", "alt", "cross", "wave", "stair"])
        else:
            burst_p = 0.75 if fever else 0.42
            if r < burst_p and unit_gate(unit, "burst"):
                name = rng.choice(["trill", "roll", "wave16"])
            elif r < burst_p + 0.045 and unit_gate(unit, "jack"):
                name = "jack"
            elif r < burst_p + 0.08 and not fever:
                name = "sparse"
            else:
                # FEVER で burst のゲートが通らなかったユニットは sparse に落とさず
                # 密な8分パターンにする（落とすと密度上げが逆効果になる）
                name = rng.choice(["stair", "wave", "alt", "cross", "wave", "alt"])
        plan.append(name)
    # サビ内では後半に前半のパターンを繰り返す（モチーフの反復）
    if is_chorus and len(plan) >= 10:
        half = len(plan) // 2
        plan[half:] = plan[: len(plan) - half]
    return units, plan


# ---- 実体化 ----


class Realizer:
    """計画どおりにノーツを置きながら、レーンの流れと分布を保つ。"""

    def __init__(self, slot_map, floor_pat, use_eff=False):
        self.slot_map = slot_map
        self.floor_pat = floor_pat
        # v5: フロア判定に主レイヤーの strength（slot["eff"]）を使う（V5-2）
        self.use_eff = use_eff
        self.notes = []
        self.counts = [0, 0, 0, 0]
        self.head_counts = [0, 0, 0, 0]  # 単位の頭（rel=0）のノーツだけの分布。easy の偏り対策
        self.total = 0
        self.prev_lanes = []  # 直近のレーン列（末尾が最新）
        self.recent = []  # 直近のノーツの (16分グリッド位置, レーン)。両親指制約の罰金用
        # 難易度ごとの部分列のレーン履歴（h=全ノーツ, n=8分位置, e=拍位置）。
        # 部分列でも同一レーン3連続を作らないために使う（v2 の assign_lanes と同じ考え方）
        self.level_last = {"h": [], "n": [], "e": []}
        self.next_id = 0

    def slot(self, unit, rel):
        bar, half = unit
        beat = bar * 4 + half * 2 + rel // 4
        return self.slot_map.get((beat, rel % 4))

    def add_note(self, slot, lane, kind, pattern, unit_rel):
        note = {
            "id": self.next_id,
            "time_ms": int(round(slot["time"] * 1000)),
            "lane": lane,
            "hold_ms": 0,
            "tail_ms": 0,
            "kind": kind,
            "pattern": pattern,
            "unit_rel": unit_rel,
            "sub": slot["sub"],
            "beat": slot["beat"],
            "bar": slot["beat"] // 4,
            "strength": slot["strength"],
            "pitch_lane": slot["pitch_lane"],
            "fever": slot["fever"],
            "energy": slot["energy"],
        }
        self.next_id += 1
        self.notes.append(note)
        self.counts[lane] += 1
        if unit_rel == 0:
            self.head_counts[lane] += 1
        self.total += 1
        self.prev_lanes.append(lane)
        self.recent.append((slot["beat"] * 4 + slot["sub"], lane))
        self.level_last["h"].append(lane)
        if slot["sub"] % 2 == 0:
            self.level_last["n"].append(lane)
        if slot["sub"] == 0:
            self.level_last["e"].append(lane)
        return note

    def run_penalty(self, lanes, subs, pattern_name):
        """全難易度の部分列で同一レーン連続を作る候補への罰金。

        通常パターンは3連続から罰金にする。jack（縦連）はパターン自体が
        同一レーン3連なので3連までは罰金にしないが、直前のノーツとつながって
        4連以上になる候補は罰金にする。無罰金のままだと、サビの連呼セクション
        のように jack が連続する場所で同じレーンに寄り続け、生成後の修復
        （repair_runs）が連の真ん中を落とし続けて長い空白ができるため
        （NK-S003 keiyo 第1サビで easy 7.0秒の空白になった実例）。
        """
        pen = 0.0
        limit = 4 if pattern_name == "jack" else 3
        for level in ("h", "n", "e"):
            seq = list(self.level_last[level][-(limit - 1) :])
            for lane, sub in zip(lanes, subs):
                if level == "n" and sub % 2 == 1:
                    continue
                if level == "e" and sub != 0:
                    continue
                seq.append(lane)
                if len(seq) >= limit and all(x == lane for x in seq[-limit:]):
                    pen += 60.0
        return pen

    def side_penalty(self, lanes, grids):
        """両親指制約 C3a/C3b に触れる候補への罰金（check-two-thumb.py と同じ定義）。

        lanes/grids は候補フィットのノーツ列（時刻順）。直近の実績とつなげて数える。
        C3a: 間隔1ステップ以下の連なりで同側3連。C3b: 同側2レーン交互が5連以上。
        """
        seq = self.recent[-12:] + list(zip(grids, lanes))
        pen = 0.0
        run = 0
        prev = None
        for g, l in seq:
            s = l // 2
            if prev is not None and g - prev[0] <= 1 and s == prev[1]:
                run += 1
            else:
                run = 1
            if run >= 3:
                pen += 80.0
            prev = (g, s)
        if seq:
            side = seq[-1][1] // 2
            lanes_seen = set()
            length = 0
            prev = None
            for g, l in reversed(seq):
                if l // 2 != side:
                    break
                if prev is not None and (prev[0] - g > 2 or l == prev[1]):
                    break
                if l not in lanes_seen and len(lanes_seen) >= 2:
                    break
                lanes_seen.add(l)
                length += 1
                prev = (g, l)
            if length >= 5 and len(lanes_seen) == 2:
                pen += 80.0 * (length - 4)
        return pen

    def fit_cost(self, lanes, pattern_name, pitches, subs, grids, f0s=None):
        """フィット候補のコスト。小さいほど良い。3連続を作る候補は強く避ける。"""
        cost = self.run_penalty(lanes, subs, pattern_name)
        cost += self.side_penalty(lanes, grids)
        if self.prev_lanes:
            delta = abs(lanes[0] - self.prev_lanes[-1])
            cost += {0: 0.35, 1: 0.0, 2: 0.5, 3: 1.1}[delta]
        for i, lane in enumerate(lanes):
            cost += 2.0 * (self.counts[lane] / max(1, self.total))
            if i == 0:
                # 単位の頭は easy にも残るので、その分布も均す
                cost += 1.6 * (self.head_counts[lane] / max(1, sum(self.head_counts)))
        cost += 0.05 * sum(abs(l - p) for l, p in zip(lanes, pitches))  # 音高は参考程度
        if f0s:
            # v5（V5-3）: 音高コンターとレーンの動きの一致。主レイヤーが
            # melody / vocal のフレーズでのみ、呼び出し側が f0s を渡す。
            # 上昇/下降（±1半音以上）にレーンが同方向へ動く候補を優遇し、
            # 逆方向は罰金。同音（±0.5半音未満）でレーンが動く候補は軽い罰金。
            for i in range(1, len(lanes)):
                a, b = f0s[i - 1], f0s[i]
                if a is None or b is None or np.isnan(a) or np.isnan(b):
                    continue
                df, dl = b - a, lanes[i] - lanes[i - 1]
                if abs(df) >= 1.0:
                    if dl == 0:
                        cost += 0.15
                    elif (df > 0) == (dl > 0):
                        cost -= 0.20
                    else:
                        cost += 0.45
                elif abs(df) < 0.5 and dl != 0:
                    cost += 0.08
        return cost

    def realize_unit(self, unit, pattern_name, mirror_only=False, anchor_floor=0.0, contour=False):
        pat = PATTERNS[pattern_name]
        placed = []
        if not pat["rel"]:
            # sparse: 小節頭・半小節頭のアンカーだけ（強さが足りる場合）
            slot = self.slot(unit, 0)
            if slot is not None and slot["strength"] >= anchor_floor:
                lane = self._best_single_lane(slot)
                placed.append(self.add_note(slot, lane, "anchor", None, 0))
            return placed
        steps = []
        for rel, off in zip(pat["rel"], pat["off"]):
            slot = self.slot(unit, rel)
            if slot is None:
                continue
            floor_val = slot["eff"] if self.use_eff else slot["strength"]
            if floor_val < self.floor_pat:
                continue
            steps.append((rel, off, slot))
        if not steps:
            return placed
        offs = [o for _r, o, _s in steps]
        pitches = [s["pitch_lane"] for _r, _o, s in steps]
        subs = [s["sub"] for _r, _o, s in steps]
        grids = [s["beat"] * 4 + s["sub"] for _r, _o, s in steps]
        f0s = [s.get("f0") for _r, _o, s in steps] if contour else None
        best_lanes, best_cost = None, None
        for lanes in pattern_fits(offs, mirror_only=mirror_only):
            c = self.fit_cost(lanes, pattern_name, pitches, subs, grids, f0s)
            if best_cost is None or c < best_cost:
                best_lanes, best_cost = lanes, c
        for (rel, _off, slot), lane in zip(steps, best_lanes):
            placed.append(self.add_note(slot, lane, "pattern", pattern_name, rel))
        return placed

    def _best_single_lane(self, slot):
        best_lane, best_cost = 0, None
        grid = slot["beat"] * 4 + slot["sub"]
        for lane in range(4):
            cost = (
                2.0 * (self.counts[lane] / max(1, self.total))
                + 1.6 * (self.head_counts[lane] / max(1, sum(self.head_counts)))
                + 0.06 * abs(lane - slot["pitch_lane"])
                + self.side_penalty([lane], [grid])
            )
            for level in ("h", "n", "e"):
                last = self.level_last[level]
                if len(last) >= 2 and last[-1] == lane and last[-2] == lane:
                    cost += 60.0
            if self.prev_lanes:
                cost += {0: 0.35, 1: 0.0, 2: 0.5, 3: 1.1}[abs(lane - self.prev_lanes[-1])]
            if best_cost is None or cost < best_cost:
                best_lane, best_cost = lane, cost
        return best_lane


def enforce_same_lane_gap(notes, min_gap_ms):
    """同一レーンで近すぎる組は弱い方を落とす（同時押しは別レーンなので残る）。"""
    kept = []
    dropped = 0
    by_lane = {}
    for note in sorted(notes, key=lambda c: (c["time_ms"], c["lane"])):
        prev = by_lane.get(note["lane"])
        if prev is not None and note["time_ms"] - prev["time_ms"] < min_gap_ms:
            weaker = note if note["strength"] < prev["strength"] else prev
            if weaker is prev:
                kept = [k for k in kept if k is not prev]
                by_lane[note["lane"]] = note
                kept.append(note)
            dropped += 1
            continue
        by_lane[note["lane"]] = note
        kept.append(note)
    return kept, dropped


def find_runs(notes_sorted):
    """同じレーンが3つ以上続く区間 [(開始idx, 終了idx)] を返す。"""
    runs = []
    i = 0
    while i < len(notes_sorted):
        j = i
        while j + 1 < len(notes_sorted) and notes_sorted[j + 1]["lane"] == notes_sorted[i]["lane"]:
            j += 1
        if j - i + 1 >= 3:
            runs.append((i, j))
        i = j + 1
    return runs


def run_is_allowed(diff, run):
    """同一レーン連続の例外: hard の縦連（間隔 JACK_MIN_GAP_MS 以上の3連）だけ許可。"""
    return (
        diff == "hard"
        and len(run) == 3
        and run[1]["time_ms"] - run[0]["time_ms"] >= JACK_MIN_GAP_MS
        and run[2]["time_ms"] - run[1]["time_ms"] >= JACK_MIN_GAP_MS
    )


def repair_runs(id_sets, notes_by_id):
    """3連続ルールを全難易度で直す。落としたノーツは下位難易度からも落とす（入れ子を保つ）。"""
    order = ["hard", "normal", "easy"]
    for di, diff in enumerate(order):
        while True:
            seq = sorted((notes_by_id[i] for i in id_sets[diff]), key=lambda n: (n["time_ms"], n["lane"]))
            bad = None
            for i0, i1 in find_runs(seq):
                run = seq[i0 : i1 + 1]
                if not run_is_allowed(diff, run):
                    bad = run
                    break
            if bad is None:
                break
            mid = bad[len(bad) // 2]
            for lower in order[di:]:
                id_sets[lower].discard(mid["id"])
    return id_sets


def repair_side_runs(id_sets, notes_by_id, chord_ids):
    """両親指制約 C3a/C3b の違反を直す（check-two-thumb.py と同じ定義）。

    難易度ごとの部分列で数え直す必要がある（間引きで隣接関係が変わるため）。
    落としたノーツは下位難易度からも落として入れ子を保つ（repair_runs と同じ作法）。
    同時押しの片方は優先的に残し、違反の真ん中寄りを落とす。
    """

    def grid_of(n):
        return n["beat"] * 4 + n["sub"]

    order = ["hard", "normal", "easy"]
    for di, diff in enumerate(order):
        guard = 0
        while True:
            guard += 1
            assert guard <= 1000, f"{diff}: repair_side_runs が収束しない"
            seq = sorted(
                (notes_by_id[i] for i in id_sets[diff]),
                key=lambda n: (grid_of(n), n["lane"]),
            )
            target = None
            # C3a: 間隔1ステップ以下の連なりで同側3連
            run_notes = []
            prev = None
            for n in seq:
                if (
                    prev is not None
                    and grid_of(n) - grid_of(prev) <= 1
                    and n["lane"] // 2 == prev["lane"] // 2
                ):
                    run_notes.append(n)
                else:
                    run_notes = [n]
                prev = n
                if len(run_notes) >= 3:
                    target = run_notes[-3:]
                    break
            # C3b: 同側2レーン交互（間隔2ステップ以下）が5連以上
            if target is None:
                for i in range(len(seq)):
                    lanes_seen = {seq[i]["lane"]}
                    j = i
                    while j + 1 < len(seq):
                        a, b = seq[j], seq[j + 1]
                        if b["lane"] // 2 != seq[i]["lane"] // 2:
                            break
                        if grid_of(b) - grid_of(a) > 2:
                            break
                        if b["lane"] == a["lane"]:
                            break
                        if b["lane"] not in lanes_seen and len(lanes_seen) >= 2:
                            break
                        lanes_seen.add(b["lane"])
                        j += 1
                    if j - i + 1 >= 5 and len(lanes_seen) == 2:
                        target = seq[i : j + 1]
                        break
            if target is None:
                break
            pool = [n for n in target if n["id"] not in chord_ids] or list(target)
            victim = pool[len(pool) // 2]
            for lower in order[di:]:
                id_sets[lower].discard(victim["id"])
    return id_sets


def validate(name, charts, raw, duration_ms):
    """charts: {diff: [[time, lane, hold?], ...]}、raw: {diff: [note dict]}"""
    counts = {}
    prev = None
    for diff in ("easy", "normal", "hard"):
        notes = charts[diff]
        counts[diff] = len(notes)
        times = [n[0] for n in notes]
        assert times == sorted(times), f"{name}/{diff}: 時刻が昇順でない"
        assert len({(n[0], n[1]) for n in notes}) == len(notes), f"{name}/{diff}: 同刻・同レーン重複"
        assert all(0 <= n[1] <= 3 for n in notes), f"{name}/{diff}: レーン範囲外"
        assert times[0] >= START_MS, f"{name}/{diff}: 最初のノーツが早すぎる {times[0]}"
        assert times[-1] <= duration_ms - int(END_MARGIN_S * 1000), f"{name}/{diff}: 最後のノーツが遅すぎる {times[-1]}"
        lanes = [n[1] for n in notes]
        for lane in range(4):
            share = lanes.count(lane) / len(lanes)
            assert LANE_MIN_SHARE <= share <= LANE_MAX_SHARE, f"{name}/{diff}: レーン{lane}の割合 {share:.2f} が範囲外"
        # 同時押しは2つまで
        by_time = {}
        for n in notes:
            by_time.setdefault(n[0], []).append(n)
        assert all(len(v) <= 2 for v in by_time.values()), f"{name}/{diff}: 3つ以上の同時押しがある"
        # 3連続ルール（hard の縦連だけ例外）
        seq = raw[diff]
        for i0, i1 in find_runs(seq):
            run = seq[i0 : i1 + 1]
            assert run_is_allowed(diff, run), f"{name}/{diff}: 同一レーン{len(run)}連続（{run[0]['time_ms']}ms〜）"
        # 長押し: 尾の余裕・帯の中の同一レーン・同士の重なり
        holds = [n for n in notes if len(n) > 2]
        for t, lane, hold in holds:
            tail = t + hold
            assert hold >= 350, f"{name}/{diff}: 長押しが短すぎる {hold}ms"
            assert tail <= duration_ms - 500, f"{name}/{diff}: 長押しの尾が曲の終わりに近すぎる"
            for t2, lane2, *_ in notes:
                assert not (lane2 == lane and t < t2 <= tail), f"{name}/{diff}: 長押しの帯の中に同一レーンのノーツ {t2}"
            for t2, _l2, _h2 in holds:
                assert not (t < t2 < tail), f"{name}/{diff}: 長押し同士が重なっている"
        if prev is not None:
            assert prev <= len(notes), f"{name}: ノーツ数が単調増加でない {counts}"
        prev = len(notes)
    hard_set = {(n[0], n[1]) for n in charts["hard"]}
    normal_set = {(n[0], n[1]) for n in charts["normal"]}
    easy_set = {(n[0], n[1]) for n in charts["easy"]}
    assert easy_set <= normal_set <= hard_set, f"{name}: 入れ子構造が崩れている"
    return counts


# ---- 曲ごとの生成 ----


def process_song(song_id, meta, y, sr):
    import bisect

    duration = float(librosa.get_duration(y=y, sr=sr))
    duration_ms = int(round(duration * 1000))
    beats, period, bpm = smoothed_beats(y, sr)
    ext_beats = extend_beats(beats, period, duration)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    energies = bar_energies(y, sr, ext_beats)
    peaks = onset_peaks(onset_env, sr)
    fever = meta["fever"]

    # 演奏が実質終わる時刻（RMS が -25dB を切る最後の秒）
    rms = [float(np.sqrt(np.mean(y[i : i + sr] ** 2))) for i in range(0, len(y) - sr, sr)]
    loud_secs = [i for i, r in enumerate(rms) if 20 * np.log10(max(r, 1e-6)) > -25]
    eff_end = min(duration - END_MARGIN_S, (loud_secs[-1] + 1) if loud_secs else duration)

    # 節の切れ目: FEVER境界＋エネルギーの落ち際の小節頭。その直前 約半拍に休符を作る
    boundaries = set()
    for f0, f1 in fever:
        boundaries.add(float(f0))
        boundaries.add(float(f1))
    bar_list = sorted(energies)
    for a, b in zip(bar_list, bar_list[1:]):
        if energies[a] > 0.45 and energies[b] < energies[a] * 0.55:
            if b * 4 < len(ext_beats):
                boundaries.add(float(ext_beats[b * 4]))
    rest_windows = [(b - period * 0.5, b) for b in boundaries if START_MS / 1000 < b < eff_end]

    def in_rest(t):
        return any(lo <= t < hi for lo, hi in rest_windows)

    # スロット（演奏範囲・休符外）に強度・エネルギー・FEVER・音高を付ける
    playable = [
        s
        for s in build_slots(ext_beats, period)
        if START_MS / 1000 <= s["time"] < eff_end and not in_rest(s["time"])
    ]
    strengths = slot_strengths(onset_env, sr, [s["time"] for s in playable])
    pls = pitch_lanes(y, sr, [s["time"] for s in playable])
    for s, st, pl in zip(playable, strengths, pls):
        s["strength"] = float(st)
        s["pitch_lane"] = int(pl)
        s["energy"] = energies.get(s["beat"] // 4, 0.5)
        s["fever"] = any(f0 <= s["time"] < f1 for f0, f1 in fever)
    slot_map = {(s["beat"], s["sub"]): s for s in playable}
    svals = np.array([s["strength"] for s in playable])
    # 同時押しのゲートだけ、曲別に下げられるようにする（chord_gate_drop。
    # 音の強弱の差が小さい曲では、相対ゲートのままだと同時押しが極端に
    # 少なくなるため。既定 0 = 従来どおりで、他曲の譜面は変わらない）
    chord_drop = int(meta.get("chord_gate_drop", 0))
    pcts = {12, 25, 45, 50, 65, 75, 80, 84, 93} | {p - chord_drop for p in (75, 80, 84)}
    thr = {p: float(np.percentile(svals, p)) for p in sorted(pcts)}

    # v5（V5-1）: chart_v5 の曲だけ、スロットにレイヤー特徴量を付ける。
    # （主レイヤーの決定はモジュール側の assign_layer を使う）
    # lay_n = レイヤー strength を曲内95パーセンタイルで割った値（レイヤー間の
    # スコア比較用）、eff_by_layer = 全帯域 strength の分布へ順位写像した値
    # （ゲート・フロアが参照する実効 strength 用）。eff はフレーズの主レイヤーが
    # 決まるたびに差し替える（初期値は全帯域 strength）。
    v5 = bool(meta.get("chart_v5"))
    if v5:
        feat = compute_layer_features(y, sr, [s["time"] for s in playable])
        for layer in ("drums", "melody", "vocal"):
            raw = feat[layer]
            p95 = float(np.percentile(raw, 95)) or 1.0
            lay_n = np.clip(raw / p95, 0.0, 1.5)
            eff_map = _rank_map(raw, svals)
            for i, s in enumerate(playable):
                s.setdefault("lay_n", {})[layer] = float(lay_n[i])
                s.setdefault("eff_by_layer", {})[layer] = float(eff_map[i])
        for i, s in enumerate(playable):
            s["f0"] = float(feat["f0"][i])
            s["voiced"] = float(feat["voiced"][i])
            s["eff"] = s["strength"]

    def assign_layer(pslots, is_chorus, prev_layer):
        return assign_layer_for(meta, pslots, is_chorus, prev_layer)

    # フレーズ分割
    bar_start_time = {b: float(ext_beats[b * 4]) for b in energies if b * 4 < len(ext_beats)}
    playable_bars = sorted(b for b, t in bar_start_time.items() if START_MS / 1000 <= t < eff_end)
    boundary_bars = set()
    for bt in boundaries:
        if not playable_bars:
            break
        cand = min(playable_bars, key=lambda b: abs(bar_start_time[b] - bt))
        if abs(bar_start_time[cand] - bt) <= period:
            boundary_bars.add(cand)
    phrases = segment_phrases(playable_bars, boundary_bars)

    def unit_energy(unit):
        return energies.get(unit[0], 0.5)

    def unit_slots(unit):
        bar, half = unit
        base = bar * 4 + half * 2
        return [slot_map.get((base + rel // 4, rel % 4)) for rel in range(8)]

    # バースト／縦連の可否は、その曲の中での相対エネルギーで決める（曲の性格差を吸収）
    all_units = [(bar, half) for phrase in phrases for bar in phrase for half in (0, 1)]
    ue = np.array([unit_energy(u) for u in all_units]) if all_units else np.array([0.5])
    ue_p45 = float(np.percentile(ue, 45))
    ue_p60 = float(np.percentile(ue, 60))

    def unit_fever(unit):
        return any(s is not None and s["fever"] for s in unit_slots(unit))

    def unit_gate(unit, kind, layer=None, burst_basis=None):
        us = unit_slots(unit)
        # FEVER 区間はゲートのエネルギー条件も計画と同じく底上げする（強さの条件は不変）
        ge = unit_energy(unit) + (0.45 if unit_fever(unit) else 0.0)
        # v5（V5-2）: 主レイヤーが決まっているフレーズでは、その strength
        # （slot["eff"]、全帯域分布へ写像済み）をゲートの物差しにする
        key = "eff" if layer is not None else "strength"
        if kind == "burst":
            odd_slots = [s for r, s in enumerate(us) if s is not None and r % 2 == 1]
            if len(odd_slots) < 3 or ge < ue_p45:
                return False
            # burst（16分パターン）の根拠は「裏の16分に速い連打があるか」で、
            # 曲によって担うパートが違うため、根拠の取り方を曲別に選ぶ
            # （SONGS の burst_basis。v5 でない曲は従来どおり全帯域のみ）:
            #   main : 主レイヤーの eff（アルペジオなど主パートが16分を担う曲）
            #   drums: 全帯域のオンセット（v4 の物差し）か、打撃成分（ドラム＝
            #          ハットやフィルの16分）の eff
            #   main65: drums の条件に加え、主レイヤーの eff が特に強い場合も通す
            #          （リードの16分は強い場所だけ拾う）
            # 主レイヤーの持続成分は16分位置のすべてで高く出るため、main 系は
            # 担い手が明確な曲だけに使う（そうでない曲では trill/roll が過剰になる）。
            if burst_basis == "main":
                return float(np.mean([s["eff"] for s in odd_slots])) >= thr[45]
            if float(np.mean([s["strength"] for s in odd_slots])) >= thr[45]:
                return True
            if layer is not None:
                if float(np.mean([s["eff_by_layer"]["drums"] for s in odd_slots])) >= thr[45]:
                    return True
                if burst_basis == "main65":
                    return float(np.mean([s["eff"] for s in odd_slots])) >= thr[65]
                # サビでは主レイヤー（この盤の3曲ではボーカル）の16分そのものが
                # 根拠になる: 全帯域やドラムの強さで測ると、裏の音が薄い歌の16分が
                # 通らずサビに16分パターンがほぼ置けなかった（実測: 京葉線の午後は
                # サビのゲート到達11件すべてがこの根拠不足で不合格だった）。
                # サビに限って主レイヤーの eff でも通す（オーナー指示 2026-11-20）
                if unit_fever(unit) and float(np.mean([s["eff"] for s in odd_slots])) >= thr[45]:
                    return True
            return False
        if kind == "jack":
            even = [s[key] for r, s in enumerate(us) if s is not None and r in (0, 2, 4)]
            if len(even) == 3 and float(np.mean(even)) >= thr[65] and ge >= ue_p60:
                return True
            # v5（V5-3）: 主レイヤーが melody / vocal で、拍位置（rel 0,2,4）の
            # F0 がほぼ同音なら、同音反復そのものが縦連の根拠になる（C4 の
            # 間隔・回数の制限は従来どおり後段で担保される）
            if layer in ("melody", "vocal"):
                f0s = [s["f0"] for r, s in enumerate(us) if s is not None and r in (0, 2, 4)]
                if (
                    len(f0s) == 3
                    and all(not np.isnan(f) for f in f0s)
                    and max(f0s) - min(f0s) < 0.6
                ):
                    return True
            return False
        return False

    # 計画 → 実体化（サビはモチーフを再登場させる）
    # 乱数の種は曲 ID から決める（同じ曲は再生成しても同じ譜面になる。曲ごとに変える）
    rng = random.Random(SEED + sum((i + 1) * ord(c) for i, c in enumerate(song_id)))
    realizer = Realizer(slot_map, thr[12], use_eff=v5)
    motif_plan = None
    chorus_count = 0
    chorus_first_bars = set()
    unit_plan_count = {}
    phrase_is_chorus = []
    for phrase in phrases:
        fever_bars = sum(1 for b in phrase if any(f0 <= bar_start_time[b] < f1 for f0, f1 in fever))
        phrase_is_chorus.append(fever_bars >= max(1, int(len(phrase) * 0.6)))

    def phrase_slots(phrase):
        return [
            s
            for bar in phrase
            for half in (0, 1)
            for s in unit_slots((bar, half))
            if s is not None
        ]

    # v5（V5-2）: サビは連続するフレーズを1つの音楽的な単位として、グループ
    # 全体のスロットで主レイヤーを1回だけ決める（サビの中で主レイヤーが
    # 揺れないように）。通常フレーズは個別に決め、ヒステリシスは通常フレーズ
    # 同士の間でのみ働かせる（サビの入り口では切り替えを妨げない）。
    chorus_group_layer = {}
    if v5:
        gi = 0
        while gi < len(phrases):
            if not phrase_is_chorus[gi]:
                gi += 1
                continue
            gj = gi
            gsl = []
            while gj < len(phrases) and phrase_is_chorus[gj]:
                gsl += phrase_slots(phrases[gj])
                gj += 1
            g_layer, _gs = assign_layer(gsl, True, None)
            for gk in range(gi, gj):
                chorus_group_layer[gk] = g_layer
            gi = gj
    prev_layer = None
    phrase_layers = []
    for pi, phrase in enumerate(phrases):
        is_chorus = phrase_is_chorus[pi]
        # v5（V5-2）: フレーズの主レイヤーを先に決め、その strength を
        # スロットの eff に差し替えてから計画・実体化する（フレーズ途中では変えない）
        layer = None
        if v5:
            pslots = phrase_slots(phrase)
            if pi in chorus_group_layer:
                layer = chorus_group_layer[pi]
                scores = {
                    k: round(float(np.mean([s["lay_n"][k] for s in pslots])), 3) if pslots else 0.0
                    for k in ("drums", "melody", "vocal")
                }
                scores["(group)"] = layer
            else:
                layer, raw_scores = assign_layer(pslots, is_chorus, prev_layer)
                scores = {k: round(v, 3) for k, v in raw_scores.items()}
            if layer != "mixed":
                prev_layer = layer
            # mixed のフレーズはヒステリシスの基準（prev_layer）を更新しない
            for s in pslots:
                s["eff"] = s["strength"] if layer == "mixed" else s["eff_by_layer"][layer]
            phrase_layers.append(
                {
                    "bars": [phrase[0], phrase[-1]] if phrase else [],
                    "layer": layer,
                    "chorus": is_chorus,
                    "scores": scores,
                }
            )
        gate = (
            (lambda u, k, _layer=layer: unit_gate(u, k, _layer, meta.get("burst_basis", "drums")))
            if v5
            else unit_gate
        )
        if is_chorus:
            chorus_count += 1
            if phrase:
                chorus_first_bars.add(phrase[0])
            units = [(bar, half) for bar in phrase for half in (0, 1)]
            if motif_plan is None:
                units, plan = plan_phrase(rng, phrase, unit_energy, gate, unit_fever, True)
                motif_plan = plan
            else:
                plan = [motif_plan[i % len(motif_plan)] for i in range(len(units))]
        else:
            units, plan = plan_phrase(rng, phrase, unit_energy, gate, unit_fever, False)
        mirror = is_chorus and chorus_count >= 2
        contour = v5 and layer in ("melody", "vocal")
        for ui, (unit, name) in enumerate(zip(units, plan)):
            if is_chorus and chorus_count >= 3 and ui == len(units) - 1:
                name = "wave16" if gate(unit, "burst") else "wave"
            unit_plan_count[name] = unit_plan_count.get(name, 0) + 1
            realizer.realize_unit(
                unit,
                name,
                mirror_only=mirror,
                anchor_floor=thr[25] if ui == 0 else thr[45],
                contour=contour,
            )

    # 同時押し: サビの小節頭など特に強い拍に相方を足す（1小節に1組まで）
    notes = realizer.notes
    head_notes = {}
    for n in notes:
        if n["sub"] == 0 and n["beat"] % 4 == 0:
            head_notes.setdefault(n["bar"], n)
    climax_bars = {max(p, key=lambda b: energies.get(b, 0.5)) for p in phrases}
    chord_times = set()
    chord_ids = set()  # 同時押しのペアを構成するノーツ（生成後の修復で優先的に残す）
    for bar, head in sorted(head_notes.items()):
        slot = slot_map.get((head["beat"], 0))
        if slot is None:
            continue
        # v5: 同時押しのゲートも主レイヤーの strength（eff、全帯域分布へ写像済み）
        # で見る（V5-2 の物差しの切り替えを同時押しにも適用）。v4 曲は従来どおり
        # 全帯域 strength。間引き等の優先度に使う note の strength は全帯域のまま。
        gate_str = slot["eff"] if v5 else head["strength"]
        strong_fever = head["fever"] and gate_str >= thr[84 - chord_drop]
        climax = bar in climax_bars and gate_str >= thr[80 - chord_drop]
        chorus_start = bar in chorus_first_bars and head["fever"] and gate_str >= thr[75 - chord_drop]
        if not (strong_fever or climax or chorus_start):
            continue
        # C1: 相方は反対側のレーンだけ（両親指で1本ずつ押せる組み合わせにする）
        partner_lane = min(
            (l for l in range(4) if l // 2 != head["lane"] // 2),
            key=lambda l: (realizer.counts[l], -abs(l - head["lane"])),
        )
        partner = realizer.add_note(slot, partner_lane, "chord", None, 0)
        partner["strength"] = head["strength"]
        chord_times.add(head["time_ms"])
        chord_ids.add(head["id"])
        chord_ids.add(partner["id"])
    notes = realizer.notes

    # 長押し: 強いオンセットの後、次の強いオンセットまで音が持続する場所に置く
    peak_heights = [p[1] for p in peaks]
    strong_times = sorted(t for t, s in peaks if s >= np.percentile(peak_heights, 70)) if peaks else []

    def seg_rms(t0, t1):
        i0, i1 = int(t0 * sr), min(int(t1 * sr), len(y))
        if i1 <= i0:
            return 0.0
        return float(np.sqrt(np.mean(y[i0:i1] ** 2)))

    candidates = [
        n
        for n in notes
        if n["kind"] in ("pattern", "anchor")
        and n["sub"] == 0
        and n["time_ms"] not in chord_times
        and n["strength"] >= thr[50]
    ]
    candidates.sort(key=lambda n: (-(n["strength"] * (1.25 if n["fever"] else 1.0)), n["time_ms"]))
    accepted = []
    removed_ids = set()
    for n in candidates:
        if len(accepted) >= HOLD_TARGET + 2:
            break
        t = n["time_ms"] / 1000
        i = bisect.bisect_right(strong_times, t + 0.3)
        if i >= len(strong_times):
            continue
        sustain = strong_times[i] - t
        dur_beats = int(min(4, sustain / period))
        if dur_beats < 1 or sustain < period * 1.15:
            continue
        tail_beat = n["beat"] + dur_beats
        if tail_beat >= len(ext_beats):
            continue
        tail_t = float(ext_beats[tail_beat])
        if tail_t > eff_end - 0.3:
            continue
        head_rms = seg_rms(t, t + 0.2)
        mid_rms = seg_rms(t + 0.25, max(t + 0.3, tail_t - 0.05))
        if head_rms <= 0 or mid_rms < head_rms * 0.45:
            continue
        tail_ms = int(round(tail_t * 1000))
        if tail_ms - n["time_ms"] < 380:
            continue
        # C2: 帯の中に同時押しの時刻があると、ペアの片方は必ず拘束側に来るので置かない
        if any(n["time_ms"] < ct <= tail_ms for ct in chord_times):
            continue
        if any(not (tail_ms <= a0 or n["time_ms"] >= a1) for a0, a1 in accepted):
            continue
        n["hold_ms"] = tail_ms - n["time_ms"]
        n["tail_ms"] = tail_ms
        accepted.append((n["time_ms"], tail_ms))
        for m in notes:
            if m is n or not (n["time_ms"] < m["time_ms"]):
                continue
            if m["lane"] == n["lane"] and m["time_ms"] < tail_ms + period * 500:
                # 同一レーンは帯の中＋尾の直後しばらくも置かない（従来ルール）
                removed_ids.add(m["id"])
            elif m["lane"] // 2 == n["lane"] // 2 and m["time_ms"] <= tail_ms:
                # C2: 拘束されている親指の側（もう1レーン）も帯の中には置かない
                removed_ids.add(m["id"])
    notes = [n for n in notes if n["id"] not in removed_ids]

    # スナップ → 尾の再計算 → 同一レーン間隔の再検証 → 帯の中・重なりの事後修復
    n_snapped = snap_notes(notes, peaks)
    for n in notes:
        if n["hold_ms"] > 0:
            n["hold_ms"] = n["tail_ms"] - n["time_ms"]
            if n["hold_ms"] < 320:
                n["hold_ms"] = 0
    notes, n_dropped = enforce_same_lane_gap(notes, SNAP_MIN_GAP_MS)
    hold_spans = [(n["time_ms"], n["time_ms"] + n["hold_ms"], n["lane"]) for n in notes if n["hold_ms"] > 0]
    notes = [
        n
        for n in notes
        if n["hold_ms"] > 0
        # C2: スナップで帯の中に入った同側ノーツも落とす（v3 までは同一レーンだけだった）
        or not any(lane // 2 == n["lane"] // 2 and h0 < n["time_ms"] <= h1 for h0, h1, lane in hold_spans)
    ]
    last_tail = -1
    for n in sorted((n for n in notes if n["hold_ms"] > 0), key=lambda n: n["time_ms"]):
        if n["time_ms"] < last_tail:
            n["hold_ms"] = 0
        else:
            last_tail = max(last_tail, n["time_ms"] + n["hold_ms"])
    notes.sort(key=lambda n: (n["time_ms"], n["lane"]))

    # 安全弁: hard の上限を超えたら、低エネルギーのパターンノーツから間引く
    if len(notes) > HARD_CAP:
        drop = set()
        for n in sorted((n for n in notes if n["kind"] == "pattern"), key=lambda n: (n["energy"], n["strength"])):
            if len(notes) - len(drop) <= HARD_CAP:
                break
            drop.add(n["id"])
        notes = [n for n in notes if n["id"] not in drop]

    # 難易度への導出（入れ子）
    notes_by_id = {n["id"]: n for n in notes}
    hard_ids = {n["id"] for n in notes}
    normal_ids = set()
    for n in notes:
        if n["kind"] == "chord":
            if n["strength"] >= thr[93]:
                normal_ids.add(n["id"])
        elif n["pattern"] in BURST_PATTERNS:
            if n["unit_rel"] == 0:
                normal_ids.add(n["id"])
            elif n["fever"] and n["sub"] % 2 == 0:
                # サビの16分パターンは、8分位置（sub 偶数）の音も normal に
                # 残す（通常はユニット頭だけ）。サビの密度上げを hard だけでなく
                # normal／easy にも効かせるため（オーナー指示 2026-11-20）。
                # 16分位置そのものは従来どおり hard 専用のまま
                normal_ids.add(n["id"])
        elif n["sub"] % 2 == 0:
            normal_ids.add(n["id"])

    def thin(ids, cap, min_gap, fever_w=1.2):
        """レーンごとに強さ順の列を持ち、往復で均等に拾って間引く。

        候補プール自体が偏っていても分布が 18〜32% に収まるよう、総数は
        「最も候補の少ないレーンが2割を確保できる量」を上限にする。
        同時押しのペアは同刻なので間隔チェックの対象外。
        """
        by_lane = {
            # FEVER 区間のノーツは少し優先して残す（密度上げを下位難易度にも効かせる。
            # 同時押し候補の ×1.25 と同じ考え方で、こちらは ×fever_w に抑える）
            l: sorted(
                (notes_by_id[i] for i in ids if notes_by_id[i]["lane"] == l),
                key=lambda n: -(n["strength"] * (fever_w if n["fever"] else 1.0)),
            )
            for l in range(4)
        }
        scarcest = min(len(v) for v in by_lane.values())
        # v4: 後段の修復（repair_runs / repair_side_runs）が下位難易度からもノーツを
        # 落として分布が寄るため、検証範囲（18〜32%）より内側を狙う
        total_target = min(cap, int(scarcest / 0.205)) if scarcest else min(cap, sum(len(v) for v in by_lane.values()))
        ceil_q = int(total_target * 0.295)
        kept = []
        kept_times = []
        lane_kept = [0, 0, 0, 0]
        ptr = {l: 0 for l in range(4)}

        def gap_ok(n):
            return all(t == n["time_ms"] or abs(n["time_ms"] - t) >= min_gap for t in kept_times)

        progress = True
        while len(kept) < total_target and progress:
            progress = False
            for l in range(4):
                if len(kept) >= total_target or lane_kept[l] >= ceil_q:
                    continue
                while ptr[l] < len(by_lane[l]):
                    n = by_lane[l][ptr[l]]
                    ptr[l] += 1
                    if gap_ok(n):
                        kept.append(n)
                        kept_times.append(n["time_ms"])
                        lane_kept[l] += 1
                        progress = True
                        break
        return {n["id"] for n in kept}

    def fill_fever_gaps(ids, pool, cap, min_gap):
        """FEVER 区間の空白が FEVER_GAP_FILL_S を超えたら、落ちた候補を戻す。

        thin は上限まで拾い切るため、難易度の空白は主に生成後の修復
        （repair_runs 等）がノーツを落として作る。オンセットの弱いサビの
        一帯では、候補が残っていても下位難易度だけ長い空白になることがある
        （NK-S003 keiyo 第2サビ easy で 3.5秒になった実例）。そのため修復の
        後に呼ぶ。候補は確定した上位難易度の集合の中にあるものだけに限る
        ので入れ子は保たれる。戻す候補は空白の中央寄りを優先し、レーン割合が
        検証範囲（0.18〜0.32）の内側に収まるものだけにする。
        """
        ids = set(ids)
        pool = [notes_by_id[i] for i in pool if i not in ids]
        for f0, f1 in fever:
            lo_ms, hi_ms = int(f0 * 1000), int(f1 * 1000)
            for _ in range(20):
                if len(ids) >= cap:
                    break
                kept_notes = sorted((notes_by_id[i] for i in ids), key=lambda n: n["time_ms"])
                kept = [n["time_ms"] for n in kept_notes]
                inside = [t for t in kept if lo_ms <= t < hi_ms]
                pts = [lo_ms] + inside + [hi_ms]
                worst = None
                for a, b in zip(pts, pts[1:]):
                    if worst is None or b - a > worst[1] - worst[0]:
                        worst = (a, b)
                if worst is None or worst[1] - worst[0] <= FEVER_GAP_FILL_S * 1000:
                    break
                a, b = worst
                mid = (a + b) / 2
                total = len(ids)
                lane_counts = [sum(1 for n in kept_notes if n["lane"] == l) for l in range(4)]
                cands = []
                for n in pool:
                    t = n["time_ms"]
                    if not (a < t < b):
                        continue
                    if any(t != k and abs(t - k) < min_gap for k in kept):
                        continue
                    shares = [
                        (lane_counts[l] + (1 if l == n["lane"] else 0)) / (total + 1) for l in range(4)
                    ]
                    # 検証範囲（0.18〜0.32）の外に出る候補だけを避ける。以前は
                    # 内側の 0.185〜0.30 で見ていたが、既存の分布が内側を外れて
                    # いると無関係のレーンの候補まで全部落ち、サビの空白が
                    # 埋まらないことがあった（umi easy 第2サビで実例）
                    if max(shares) > 0.32 or min(shares) < 0.18:
                        continue
                    # 戻した途端に同一レーン3連になる候補は避ける。3連は
                    # 「全ノーツを時刻順に並べた列で、同レーンが3つ連続する」こと
                    # なので、挿入位置の前後2つ（レーン不問）と候補のレーンが
                    # 揃う形（末尾型・先頭型・サンドイッチ型）を見分ける
                    seq = sorted(kept_notes, key=lambda k: (k["time_ms"], k["lane"]))
                    idx = bisect.bisect_left([(k["time_ms"], k["lane"]) for k in seq], (t, n["lane"]))
                    p1 = seq[idx - 1] if idx >= 1 else None
                    p2 = seq[idx - 2] if idx >= 2 else None
                    q1 = seq[idx] if idx < len(seq) else None
                    q2 = seq[idx + 1] if idx + 1 < len(seq) else None
                    L = n["lane"]
                    if (
                        (p1 is not None and p2 is not None and p1["lane"] == L == p2["lane"])
                        or (q1 is not None and q2 is not None and q1["lane"] == L == q2["lane"])
                        or (p1 is not None and q1 is not None and p1["lane"] == L == q1["lane"])
                    ):
                        continue
                    cands.append((abs(t - mid), -n["strength"], n))
                if not cands:
                    break
                # 拍位置（sub==0）の候補を優先し、その中で空白の中央寄り・強い順
                cands.sort(key=lambda c: (0 if c[2]["sub"] == 0 else 1, c[0], c[1]))
                chosen = cands[0][2]
                ids.add(chosen["id"])
                pool.remove(chosen)
        return ids

    normal_pool = set(normal_ids)
    normal_ids = thin(normal_ids, NORMAL_CAP, 150)
    easy_ids = {i for i in normal_ids if notes_by_id[i]["sub"] == 0 and notes_by_id[i]["kind"] != "chord"}
    # easy は拍位置のみで候補が少なく、サビが16分中心になるとサビの取り分が
    # 構造的に減るため、FEVER 優先の重みを normal より強める（2026-11-20）
    easy_ids = thin(easy_ids, EASY_CAP, 260, fever_w=1.6)
    id_sets = {"hard": hard_ids, "normal": normal_ids, "easy": easy_ids}
    # 同一レーン修復と両親指修復は、片方の「落とす」が他方の違反（連の接続）を
    # 作ることがあるので、どちらも動かなくなるまで交互に回す（落とすだけなので収束する）
    for _ in range(50):
        before = {d: len(s) for d, s in id_sets.items()}
        id_sets = repair_runs(id_sets, notes_by_id)
        id_sets = repair_side_runs(id_sets, notes_by_id, chord_ids)
        if all(len(id_sets[d]) == before[d] for d in before):
            break
    else:
        raise AssertionError(f"{song_id}: 修復が収束しない")

    # FEVER 区間の空白の埋め戻し（修復で落ちた分だけ上限に余裕がある。
    # 候補は確定した上位難易度の集合の中にあるものだけ＝入れ子を保つ）
    id_sets["hard"] = fill_fever_gaps(id_sets["hard"], set(notes_by_id), HARD_CAP, 150)
    id_sets["normal"] = fill_fever_gaps(id_sets["normal"], normal_pool & id_sets["hard"], NORMAL_CAP, 150)
    # easy の埋め戻し候補: 原則は拍位置（sub==0）のみ。ただしサビの長い空白は
    # 拍位置だけでは埋まらないことがある（候補が同一レーン3連の回避に引っかかる等）
    # ため、sub==2（8分裏）も候補に入れ、fill 側で sub==0 を優先して使う
    easy_pool = {
        i
        for i in id_sets["normal"]
        if notes_by_id[i]["sub"] in (0, 2) and notes_by_id[i]["kind"] != "chord"
    }
    id_sets["easy"] = fill_fever_gaps(id_sets["easy"], easy_pool, EASY_CAP, 260)

    def final_notes(diff, ids):
        seq = sorted((notes_by_id[i] for i in ids), key=lambda n: (n["time_ms"], n["lane"]))
        out = []
        for n in seq:
            hold = n["hold_ms"]
            if hold > 0 and diff != "hard":
                tail = n["time_ms"] + hold
                others = [m for m in seq if m is not n and n["time_ms"] < m["time_ms"] < tail]
                if diff == "normal" and len(others) > 2:
                    hold = 0
                elif diff == "easy" and (others or hold > period * 2600):
                    hold = 0
            out.append({"time_ms": n["time_ms"], "lane": n["lane"], "hold_ms": hold, "src": n})
        if diff == "easy":
            hs = sorted((o for o in out if o["hold_ms"] > 0), key=lambda o: -o["src"]["strength"])
            for o in hs[6:]:
                o["hold_ms"] = 0
        return out

    finals = {d: final_notes(d, id_sets[d]) for d in ("easy", "normal", "hard")}
    raw = {d: sorted(finals[d], key=lambda o: (o["time_ms"], o["lane"])) for d in finals}

    def to_tuples(final):
        return [
            [o["time_ms"], o["lane"], o["hold_ms"]] if o["hold_ms"] > 0 else [o["time_ms"], o["lane"]]
            for o in final
        ]

    charts = {d: to_tuples(finals[d]) for d in finals}
    counts = validate(song_id, charts, raw, duration_ms)
    subdiv = subdivision_positions(ext_beats)
    drift = drift_stats(charts, subdiv, duration_ms)

    def diff_report(final):
        by_time = {}
        for o in final:
            by_time[o["time_ms"]] = by_time.get(o["time_ms"], 0) + 1
        holds = [o for o in final if o["hold_ms"] > 0]
        return {
            "total": len(final),
            "taps": len(final) - len(holds),
            "chordPairs": sum(1 for v in by_time.values() if v == 2),
            "holds": len(holds),
            "holdSeconds": round(sum(o["hold_ms"] for o in holds) / 1000, 1),
        }

    pattern_notes = {}
    for n in notes:
        if n["pattern"]:
            pattern_notes[n["pattern"]] = pattern_notes.get(n["pattern"], 0) + 1
    song_json = {
        "title": meta["title"],
        "durationMs": duration_ms,
        "bpm": int(round(bpm)),
        "beats": [int(round(t * 1000)) for t in ext_beats],
        "fever": fever,
        "charts": charts,
    }
    rep = {
        "bpm": int(round(bpm)),
        "counts": counts,
        "diffs": {d: diff_report(finals[d]) for d in finals},
        "lanes": {d: [sum(1 for n in charts[d] if n[1] == l) for l in range(4)] for d in charts},
        "snapped": n_snapped,
        "droppedAfterSnap": n_dropped,
        "patternUnits": unit_plan_count,
        "patternNotes": pattern_notes,
        "drift": drift,
        "fever": fever,
        "v5": v5,
        "layers": phrase_layers,
    }
    print(f"{song_id}: BPM={bpm:.2f} -> {int(round(bpm))} counts={counts}")
    print(f"  diffs={json.dumps(rep['diffs'], ensure_ascii=False)} lanes={rep['lanes']}")
    print(f"  patterns(units)={unit_plan_count} patterns(notes)={pattern_notes}")
    print(f"  snapped={n_snapped} droppedAfterSnap={n_dropped} drift={json.dumps(drift, ensure_ascii=False)}")
    if v5:
        print(f"  layers={json.dumps(phrase_layers, ensure_ascii=False)}")
    return song_json, rep


def main() -> int:
    out = {}
    report = {}
    with tempfile.TemporaryDirectory() as td:
        for song_id, meta in SONGS.items():
            wav = Path(td) / f"{song_id}.wav"
            to_wav(ROOT / meta["audio"], wav)
            y, sr = librosa.load(str(wav), sr=SR, mono=True)
            song_json, rep = process_song(song_id, meta, y, sr)
            out[song_id] = song_json
            report[song_id] = rep
    # 両親指制約の最終検証: 違反が残っていたら書き出さない（チェッカーが正本）
    import importlib.util

    sys.dont_write_bytecode = True  # __pycache__ を作らない
    spec = importlib.util.spec_from_file_location(
        "check_two_thumb", Path(__file__).with_name("check-two-thumb.py")
    )
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    violations = checker.check_charts(out)
    if violations:
        print(f"two-thumb check: 違反 {len(violations)} 件が残っているため書き出しません")
        for v in violations[:30]:
            print(f"  {v[0]}/{v[1]} {v[2]}: {v[3]}")
        return 1
    print("two-thumb check: OK（違反 0 件）")
    dest = ROOT / "src/game/data/charts.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
