#!/usr/bin/env python3
"""譜面生成 v6-1.2 / v6-1.1 / v6-1 / v5 / v4: src/game/assets/*.mp3 を解析して src/game/data/charts.json を作る。

v6-1.2 の変更点（v6-1.1 の残差への上流対策）:
- 8分位置のレーン配分を上流で均す: Realizer が 8分位置（sub 偶数）だけの
  レーン別カウント（eighth_counts）を別に持ち、フィットのコストにその分布
  均衡（EIGHTH_BALANCE_W=2.0。全体分布の重み 6.0 の 1/3）を加えた。
  normal の候補プールは hard の8分位置
  サブセットなので、全体分布が検証範囲内にあっても8分位置だけレーンが
  偏ると、thin の最少レーン律速で normal 全体が削れる（umi normal の
  レーン0候補 87→66 の実例）。下流の密度下限ガード（v6-1.1）に頼る前に、
  プールの最少レーン自体を保つのが狙い。ガードは安全網として残す。
- sustain 閾値の曲別上書き口: sustain_mode 判定の閾値（従来は絶対定数
  SUSTAIN_HI=0.50 / SUSTAIN_LO=0.30）を、SONGS メタデータの sustain_hi /
  sustain_lo で曲別に上書きできるようにした。未指定なら従来値で挙動不変。
  sustain は曲内95パーセンタイル正規化なので、持続成分の分布が極端な曲では
  閾値の効きが変わるための調整口。

v6-1.1 の変更点（NK-S003 実曲トライアルの所見から）:
- モチーフ最小長: 非サビモチーフ再利用の対象を「2小節以上のフレーズ同士」に
  限定した。1小節だけのフレーズはシグネチャが短すぎて、無関係でも類似度が
  高く出て組になってしまうため（umi で bars 31 ↔ 63 の1小節組、類似度
  0.883 が発火した実例）。閾値（絶対下限・相対下限）は従来どおり。
- normal／easy の密度下限ガード: thin の目標総数は「最も候補の少ない
  レーンが2割を確保できる量」で決まるため、パターン配分の変化で1レーンの
  候補だけが減ると、プール総数がほぼ変わらなくても全体が大きく割り込む
  （umi normal: プール 401→381 なのにレーン0候補 87→66 が目標 410→321 を
  招き、最終 375→293 の −22% になった実例）。そこで、thin の目標が cap
  でなく最少レーン由来で決まった難易度に限って、間引き後に候補プールの
  DENSITY_FLOOR_RATIO 倍を下限とし、割り込んだ分は落ちた候補を強さ順に
  戻すガード（fill_density_floor）を入れた。cap 律速の曲（プールが cap を
  大きく上回り、保持率が低く出るのが従来どおりの曲）には発動しない。
  戻す候補は上位難易度の確定集合の中だけ（入れ子維持）、レーン割合・
  最小間隔・同一レーン3連・両親指の同側連なりを見て安全なものだけにし、
  戻した後は修復を回し直す。

v6-1 の変更点:
- V6-1a 持続/打撃によるパターン分岐（旧称 V5-4）: スロットに持続度
  （harm_rms を曲内95パーセンタイルで正規化した sustain）を格納し、フレーズの
  主レイヤーと組み合わせて sustain_mode（sustained / percussive / None）を決め、
  plan_phrase のパターン確率（jack・burst・sparse の比率）と長押し候補の
  優先度・可否に反映する。持続的（melody/vocal かつ持続度高）→ stair/wave と
  長押しを優遇。打撃的（drums または持続度低）→ jack を優遇し長押しを抑える。
- V6-1b 非サビ反復セクションのモチーフ再利用: FEVER 外のフレーズ同士の類似度
  （strength 列・energy・F0 コンターのシグネチャのコサイン類似度）を曲内相対の
  閾値で判定し、再登場フレーズは初出のパターン計画を再利用する。2回目は鏡像、
  3回目以降は末尾変化（サビの従来扱いに倣う）。サビは従来のモチーフ処理のまま。
- V6-2 フリックの生成器統合（曲別メタデータ flick: True の曲だけ。既定 OFF）:
  NK-S006 v1.4.2 の確定方針（rework-chorus-patterns.py）を生成器ルール化した。
  割合ありきの機械変換はしない。フリックは音楽的な「決め」だけに置く:
  サビ内は第1サビで決めた相対位置（サビ入り・フレーズ頭・強拍アクセント・
  F0 跳躍・フレーズ末）を全サビへ同じ相対位置で適用し、サビ外はフレーズ頭の
  強アクセント／クライマックス頭／サビ直前の一打だけに絞る。適格性と難易度別
  最小間隔（easy 4500ms / normal 2400ms / hard 1400ms、下限 1200ms）は
  NK-S006 の実績どおり。出力形式は NK-S006 と同じ [time, lane, 0, "flick"]。
  標準化改訂（テンプレート v1.7.0、NK-S006 試作のオーナー暫定OKを受けて）:
  サビ内位置の伝播を、FEVER 開始点からの絶対拍オフセットから「サビ内の
  フレーズ構造上の位置（サビ内フレーズ順＋フレーズ先頭拍からのオフセット）」
  へ変更した。絶対オフセット方式は、サビの長さや入り拍が違うと位置がずれる
  ／落ちる欠陥が NK-S003 トライアルで実証された（一致 yoru 4/4・keiyo 3/5・
  umi 1/9）ため。あわせてサビ外ゲートを厳格化: サビ外の総数はサビ内総数を
  超えない、1フレーズに1つまで、クライマックス頭も phrase-head と同じ
  thr93 の最強クラスのみ、曲頭 5 秒はフリックを置かない（同トライアルで
  umi のサビ外過多と yoru のイントロ直後 2.995 秒の例への対策）。
  ラスサビ全滅対策の改訂（NK-S006 試作の診断から）: 構造アンカー方式でも
  写像適用率は 60〜70% にとどまり、『きずだらけのまま』ではラスサビの
  フリックが全難易度 0 件になった（5アンカー中4つが「位置にノーツ無し」、
  残る1つもサビ直前の一打との間隔競合で間引かれた）。対策として (1) 構造
  位置に写らなかったアンカーを、同じフレーズ内の最も近い対象可ノーツへ
  寄せて写すフォールバック（通常の寄せ幅は1拍＝16分×4まで、ノーツは
  作らない。そのサビにフリックが1つも残らない場合に限り、フレーズ内の
  最も近いノーツまで広げる救済つき）、(2) 間隔フィルタの優先順位化
  （正確に写ったサビ内 ＞ 寄せたサビ内 ＞ サビ外）、を入れた。写像の
  内訳はレポートの flickAnchorStats（サビごとに exact/fallback/rescue/
  dropped）に出る。
- V6-3 フリック先決め＋流れ整形・流れ検証（flick: True の曲だけ。OFF は無変更）:
  オーナー指摘「フリックのある場所が気持ちよくない」への対策。従来は通常譜面を
  作り切ってから既存ノーツを変換するだけだったため、フリック周りの配置が
  タップ前提のままだった。v6-3 では (1) アンカーを難易度導出より前に確定し、
  候補プールにピン留めして間引き・修復で落とさない、(2) 生成後にフリック
  直前の窓（easy 2拍／normal 1.5拍／hard 1拍）のパターンノーツを間引いて
  溜めを作り、直後の同レーンに回復ウィンドウ（300ms）を空ける整形、
  (3) 届く難易度すべてで流れ（直前500msの密度・直後の同レーン間隔・
  フリック間隔）を検査し、違反したフリックは ±1拍以内の落ち着いた適格
  ノーツへずらす／無理なら落とす検証、を行う。フリック総数は SONGS の
  flick_budget（任意の曲別メタ。未設定なら上限なし）を上限とし、超過分は優先度の低いものから
  rank を上げて収める。移動・削除はレポートの flickFlowLog に理由付きで残る。

v6-4 の変更点（ボーカル被覆。根拠は docs/CHART-DESIGN.md の「譜面 v6-4」節）:
- 歌詞アクティブ区間（歌詞行の時間帯）全体で、ノーツの空白が難易度別の上限
  （easy 2.5秒／normal 2.0秒／hard 1.5秒、定数 VOCAL_COVER_GAP_S）を超えない
  よう保証する。従来の fill_fever_gaps は FEVER 区間限定・閾値2.9秒だったため、
  サビ外の空白（実測では空白の67%）と、間引き以外で生じた空白を拾えなかった。
- 歌詞タイミングの入力: 曲別メタデータ lyrics（区間の列／ファイルパス）または
  lyrics_file、無ければ既定で src/game/data/lyrics.json（gen-game-lyrics.mjs が
  CD 側 sync.ts から作る生成物）を曲 ID で引く。CLI の --lyrics <path> でも
  差し替えられる。歌詞入力が無い曲は従来動作（FEVER 区間の fill_fever_gaps
  のみ）にフォールバックする。
- 補填の優先順: (1) 間引き・修復で落ちた候補プールから戻す（候補は確定した
  上位難易度の集合の中だけ＝入れ子 easy⊆normal⊆hard を維持）。
  (2) プールが空の区間は、拍グリッド（sub==0）位置のうちボーカルレイヤー
  強度（v5 曲は eff_by_layer["vocal"]、それ以外は全帯域 strength）が相対的に
  高いスロットへノーツを合成する。合成位置は sub==0 に限るため、hard 用に
  合成したノーツを normal／easy の補填候補にもそのまま使える。
- フリックとの兼ね合い: 補填は v6-3 の整形・流れ検証の後に行い、フリック
  アンカーの手前窓（easy 2.0拍／normal 1.5拍／hard 1.0拍）とフリック後
  300ms の回復区間には入れない。フリック候補そのものも戻さないため、
  フリックの位置・個数・flick_budget は変わらない。flick OFF の曲でも効く。
- 総数キャップとの兼ね合い: 被覆補填はキャップ超過を許す（保証を優先）。
  超過は生成レポートの vocalCoverage（capExceeded／countsBefore／countsAfter）
  と標準出力のログで分かるようにする。
- 補填ノーツはタップのみ（長押し・同時押しの相方は作らない）。補填のたびに
  安全条件（同レーン最小間隔・レーン割合 18〜32%・同一レーン3連・両親指
  C2／C3a／C3b の先回り回避）を見て、補填後は修復（repair_runs／
  repair_side_runs）を回し直し、空白が再発したら戻し→修復を最大3回繰り返す。
  最終検証は従来どおり validate() と check-two-thumb.py（違反0で書き出し）。

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
#   flick: True で v6-2 のフリック配置を有効にする（既定 OFF。テンプレート
#     ランタイムは v1.7.0 からフリック標準対応）
#   flick_budget: v6-3 のフリック総数の上限（{"easy": n, "normal": n, "hard": n}。
#     任意の曲別メタで、未設定なら上限なし。実績のある曲は現行実績を入れる）
#   layer_bias: 主レイヤー選択の曲別バイアス（drums / melody / vocal への加算）
#   chorus_layer: サビ（FEVER）で優先する主レイヤー
#   chorus_bonus: サビの chorus_layer へのボーナス（既定 0.30）
#   burst_basis: 16分パターンのゲートの根拠（main / drums / main65）
#   chord_gate_drop: 同時押しの強さゲートだけを下げる曲別調整（強弱が均一な曲用。既定 0）
#   lyrics: v6-4 の歌詞タイミング入力（任意）。区間の列 [[開始秒, 終了秒], ...]、
#     歌詞ファイルへのパス（src/game/data/lyrics.json 形式＝曲 ID をキーに
#     {startMs, endMs} の列）、またはその JSON をパースした dict を渡せる。
#     lyrics_file でも同じ指定ができる。未指定なら既定で
#     src/game/data/lyrics.json を曲 ID で引き、無ければ歌詞なし（従来動作）。
#   sustain_hi / sustain_lo: v6-1a の sustain_mode 判定の閾値の曲別上書き
#     （sustain_hi: 主レイヤー melody/vocal かつフレーズ持続度がこれ以上で
#     「持続的」。既定 0.50。sustain_lo: 持続度がこれ以下で「打撃的」。既定 0.30）
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
        "flick": True,
        "chorus_layer": "vocal",
        "chorus_bonus": 0.5,
        "flick_budget": {"easy": 11, "normal": 15, "hard": 28},
    },
    "anata": {
        "title": "あなた",
        "audio": "src/game/assets/track02.mp3",
        # サビは「あなたの指先も 唇も 体温も」の反復ブロック（3回）:
        # 45.4〜51.7 / 107.7〜114.5 / 162.9〜169.7 の行の歌唱終わり
        "fever": [[45.0, 58.0], [107.0, 120.0], [162.0, 176.0]],
        "chart_v5": True,
        "flick": True,
        "chorus_layer": "vocal",
        "chorus_bonus": 0.5,
        "flick_budget": {"easy": 16, "normal": 23, "hard": 30},
    },
}

START_MS = 2000  # 最初のノーツはイントロ後
END_MARGIN_S = 1.2  # 最後のノーツは曲終了のこれ以上前に置く
HARD_CAP = 820  # hard の総ノーツ数の上限（安全弁。パターン＋同時押し＋長押し込み）
NORMAL_CAP = 410  # normal の総ノーツ数の上限（8分の骨格を強さ順に間引く）
EASY_CAP = 210  # easy の総ノーツ数の上限（拍位置のみを強さ順に間引く）
FEVER_GAP_FILL_S = 2.9  # FEVER 区間でこの秒数を超える空白は、間引きで落ちた候補を戻して埋める
VOCAL_COVER_GAP_S = {"easy": 2.5, "normal": 2.0, "hard": 1.5}  # v6-4: 歌詞アクティブ区間で許す空白の上限（秒、難易度別）
VOCAL_COVER_FLICK_PRE_BEATS = {"easy": 2.0, "normal": 1.5, "hard": 1.0}  # v6-4: フリック手前窓（拍）。補填を入れない範囲（v6-3 と同じ値）
VOCAL_COVER_FLICK_RECOVERY_MS = 300  # v6-4: フリック後の回復区間（ms）。補填を入れない範囲（v6-3 と同じ値）
DEFAULT_LYRICS_FILE = "src/game/data/lyrics.json"  # v6-4: 歌詞タイミングの既定の入力先（gen-game-lyrics.mjs の生成物）
DENSITY_FLOOR_RATIO = 0.92  # v6-1.1: 密度下限ガードの下限（候補プール比。thin 目標が最少レーン律速のときだけ発動）
EIGHTH_BALANCE_W = 2.0  # v6-1.2: フィット時の8分位置だけのレーン分布均衡の重み（全体分布 6.0 の 1/3。normal プールの偏り対策。3.0 では track-b hard のレーン下限を割ったため 2.0）
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


# ---- v6-1a: 持続度（V5-4 として併記されていた harm_rms の実用化） ----
# 閾値は既定値。v6-1.2: SONGS メタデータの sustain_hi / sustain_lo で曲別に
# 上書きできる（未指定の曲はこの値のままで挙動不変）
SUSTAIN_HI = 0.50  # フレーズ持続度がこれ以上＋主レイヤー melody/vocal で「持続的」
SUSTAIN_LO = 0.30  # フレーズ持続度がこれ以下なら主レイヤー不問で「打撃的」


def phrase_sustain(pslots):
    """フレーズの持続度（スロット sustain の平均。sustain は harm_rms を曲内
    95パーセンタイルで割って 1.5 で頭打ちにした値なので、曲間の絶対比較ではなく
    曲内での相対的な持続の物差し）。"""
    if not pslots:
        return 0.0
    return float(np.mean([s.get("sustain", 0.0) for s in pslots]))


# ---- v6-1b: 非サビ反復セクションのモチーフ再利用 ----
MOTIF_SIM_MIN = 0.86  # コサイン類似度の絶対下限（これ未満は別フレーズとして扱う）
MOTIF_SIM_REL = 0.92  # 曲内の非サビフレーズ間類似度の最大値に対する相対下限（両方満たす場合のみ再利用）
MOTIF_MIN_BARS = 2  # v6-1.1: 再利用対象は2小節以上のフレーズ同士だけ（1小節組の誤検出防止）


def phrase_signature(pslots):
    """フレーズの類似判定用シグネチャ（長さ不変のベクトル）。

    スロット順の3チャンネル（strength をフレーズ内最大で正規化したもの、
    energy、F0 のフレーズ中央値からの相対コンター）を各24点にリサンプルして
    並べる。フレーズの小節数が違っても比較できる。F0 が無いスロットは中央値で埋める。
    """
    if not pslots:
        return np.zeros(72)
    strength = np.array([s["strength"] for s in pslots], dtype=float)
    strength = strength / (strength.max() or 1.0)
    energy = np.array([s["energy"] for s in pslots], dtype=float)
    f0 = np.array([s.get("f0", np.nan) for s in pslots], dtype=float)
    valid = f0[~np.isnan(f0)]
    med = float(np.median(valid)) if len(valid) else 60.0
    f0 = np.where(np.isnan(f0), med, f0)
    contour = np.clip((f0 - med) / 12.0, -1.0, 1.0)
    x_old = np.linspace(0.0, 1.0, len(pslots))
    x_new = np.linspace(0.0, 1.0, 24)
    return np.concatenate(
        [
            np.interp(x_new, x_old, strength),
            np.interp(x_new, x_old, energy) * 0.5,
            np.interp(x_new, x_old, contour) * 0.5,
        ]
    )


def _cosine(a, b):
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


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


def plan_phrase(rng, phrase, unit_energy, unit_gate, unit_fever, is_chorus, sustain_mode=None):
    """フレーズ内の各半小節にパターン名を割り当てる計画を返す。

    unit_energy(unit) -> 0..1、unit_gate(unit, kind) -> bool（burst/jack を置ける強さか）、
    unit_fever(unit) -> bool（FEVER 区間のユニットか）。
    unit は (bar, half) のタプル。
    sustain_mode（v6-1a）: フレーズの持続性。"sustained" は流れるパターン
    （stair/wave）を厚くし jack・burst を抑え、"percussive" は jack を厚くし
    burst も少し増やす。None は従来どおり。ゲート自体は変えない。

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
            sparse_p = 0.45
            if sustain_mode == "sustained":
                sparse_p = 0.25  # 持続的な低エネルギー部は休ませすぎず流れを残す
            elif sustain_mode == "percussive":
                sparse_p = 0.55  # 打撃的な低エネルギー部は単発の間を広めに取る
            name = "sparse" if r < sparse_p else rng.choice(["wave", "stair"])
        elif pe < 0.62:
            sparse_p = 0.03 if fever else 0.08
            jack_p = 0.065 if fever else 0.115
            if sustain_mode == "sustained":
                jack_p *= 0.4  # 持続音に縦連は合わないので絞る
            elif sustain_mode == "percussive":
                jack_p = min(0.30, jack_p * 2.0)  # 区切れたアタックは縦連で受ける
            if r < sparse_p:
                name = "sparse"
            elif r < jack_p and unit_gate(unit, "jack"):
                name = "jack"
            else:
                name = rng.choice(["stair", "wave", "alt", "cross", "wave", "stair"])
        else:
            burst_p = 0.75 if fever else 0.42
            if sustain_mode == "sustained":
                burst_p *= 0.9  # 持続的な高エネルギー部は16分連打を少しだけ抑えて流れで押す
            elif sustain_mode == "percussive":
                burst_p = min(0.85, burst_p + 0.15)
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
        # v6-1.2: 8分位置（sub 偶数）だけの分布。normal の候補プールは hard の
        # 8分位置サブセットなので、全体と別に数えてフィットで均す
        self.eighth_counts = [0, 0, 0, 0]
        self.eighth_total = 0
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
            "sustain": slot.get("sustain", 0.0),  # v6-1a: 長押し候補の根拠（v5 曲のみ）
            "f0": slot.get("f0", float("nan")),  # v6-2: フリックの音高跳躍判定の根拠（v5 曲のみ）
            "pitch_lane": slot["pitch_lane"],
            "fever": slot["fever"],
            "energy": slot["energy"],
        }
        self.next_id += 1
        self.notes.append(note)
        self.counts[lane] += 1
        if unit_rel == 0:
            self.head_counts[lane] += 1
        if slot["sub"] % 2 == 0:
            self.eighth_counts[lane] += 1
            self.eighth_total += 1
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
            # v6-1: パターン分岐で型の偏りが変わってもレーン分布の検証範囲
            # （18〜32%）に収まるよう、分布の均衡コストを v5 の 2.0/1.6 から強化
            cost += 6.0 * (self.counts[lane] / max(1, self.total))
            if subs[i] % 2 == 0:
                # v6-1.2: 8分位置のノーツには8分位置だけの分布も均す。
                # normal プール（hard の8分位置サブセット）の最少レーンが
                # 薄くなると thin の律速で normal 全体が削れるため
                cost += EIGHTH_BALANCE_W * (self.eighth_counts[lane] / max(1, self.eighth_total))
            if i == 0:
                # 単位の頭は easy にも残るので、その分布も均す
                cost += 4.8 * (self.head_counts[lane] / max(1, sum(self.head_counts)))
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
            # アンカーは単位の頭（sub==0）＝必ず8分位置なので、8分位置だけの
            # 分布均衡（v6-1.2）も全体分布と同じ重みで効かせる
            cost = (
                6.0 * (self.counts[lane] / max(1, self.total))
                + EIGHTH_BALANCE_W * (self.eighth_counts[lane] / max(1, self.eighth_total))
                + 4.8 * (self.head_counts[lane] / max(1, sum(self.head_counts)))
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


def repair_runs(id_sets, notes_by_id, protected=frozenset()):
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
            pool = [n for n in bad if n["id"] not in protected] or list(bad)
            mid = pool[len(pool) // 2]
            for lower in order[di:]:
                id_sets[lower].discard(mid["id"])
    return id_sets


def repair_side_runs(id_sets, notes_by_id, chord_ids, protected=frozenset()):
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
            pool = [
                n for n in target if n["id"] not in chord_ids and n["id"] not in protected
            ] or list(target)
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
        # v6-2: フリック [t, lane, 0, "flick"] は長押しではないので除外する
        holds = [n for n in notes if len(n) > 2 and n[2]]
        for t, lane, hold in (h[:3] for h in holds):
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



# ---- v6-4: 歌詞タイミング入力 ----


def normalize_lyric_intervals(raw, song_id=None):
    """歌詞タイミングの入力を [(開始秒, 終了秒), ...] に正規化する（決定的）。

    受け付ける形:
      - {曲ID: [...]} の dict（lyrics.json 形式）。song_id で引く
      - [{"startMs": n, "endMs": n}, ...]（lyrics.json の行形式。ms）
      - [{"start": 秒, "end": 秒}, ...]
      - [[開始秒, 終了秒], ...]
      - [[開始秒, "歌詞テキスト"], ...]（CD 側 sync.ts の行形式。
        終了は次の行の開始、最終行は開始+4秒）
    どれにも当てはまらない／空なら [] を返す（＝歌詞なしとして扱う）。
    """
    if raw is None:
        return []
    if isinstance(raw, dict):
        if song_id is not None and song_id in raw:
            return normalize_lyric_intervals(raw[song_id], song_id)
        if "startMs" in raw or "start" in raw:
            raw = [raw]
        else:
            return []
    out = []
    items = list(raw)
    for i, it in enumerate(items):
        if isinstance(it, dict):
            if "startMs" in it:
                start = float(it["startMs"]) / 1000
                end = float(it["endMs"]) / 1000 if "endMs" in it else start + 4.0
            elif "start" in it:
                start = float(it["start"])
                end = float(it["end"]) if "end" in it else start + 4.0
            else:
                continue
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            start = float(it[0])
            if isinstance(it[1], str):
                # sync.ts 形式 [開始秒, テキスト]: 終了は次の行の開始（無ければ +4秒）
                nxt = items[i + 1] if i + 1 < len(items) else None
                end = float(nxt[0]) if nxt is not None else start + 4.0
            else:
                end = float(it[1])
        else:
            continue
        if end > start:
            out.append((start, end))
    out.sort()
    return out


def load_lyrics_for_song(meta, song_id):
    """曲の歌詞タイミングを解決する。優先順: メタデータ lyrics／lyrics_file
    → 既定ファイル（src/game/data/lyrics.json）。無い曲は []（従来動作）。"""
    src = meta.get("lyrics", meta.get("lyrics_file"))
    if src is not None:
        if isinstance(src, (str, Path)):
            path = Path(src)
            if not path.is_absolute():
                path = ROOT / path
            if path.exists():
                return normalize_lyric_intervals(
                    json.loads(path.read_text(encoding="utf-8")), song_id
                )
            return []
        return normalize_lyric_intervals(src, song_id)
    default = ROOT / DEFAULT_LYRICS_FILE
    if default.exists():
        try:
            data = json.loads(default.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return normalize_lyric_intervals(data, song_id)
    return []


# ---- 曲ごとの生成 ----


def process_song(song_id, meta, y, sr, lyric_intervals=None):
    import bisect

    duration = float(librosa.get_duration(y=y, sr=sr))
    duration_ms = int(round(duration * 1000))
    beats, period, bpm = smoothed_beats(y, sr)
    ext_beats = extend_beats(beats, period, duration)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    energies = bar_energies(y, sr, ext_beats)
    peaks = onset_peaks(onset_env, sr)
    fever = meta["fever"]
    # v6-4: 歌詞タイミング（None ならメタデータ／既定ファイルから解決する。
    # [] ＝歌詞入力なし＝従来動作にフォールバック）
    if lyric_intervals is None:
        lyric_intervals = load_lyrics_for_song(meta, song_id)

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
    # v6-1.2: sustain_mode 判定の閾値（曲別上書き口。未指定は従来の絶対定数）
    sustain_hi = float(meta.get("sustain_hi", SUSTAIN_HI))
    sustain_lo = float(meta.get("sustain_lo", SUSTAIN_LO))
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
        # v6-1a: 持続度 sustain = harm_rms を曲内95パーセンタイルで正規化した値
        harm = np.asarray(feat["harm_rms"], dtype=float)
        harm_p95 = float(np.percentile(harm, 95)) or 1.0
        for i, s in enumerate(playable):
            s["f0"] = float(feat["f0"][i])
            s["voiced"] = float(feat["voiced"][i])
            s["eff"] = s["strength"]
            s["sustain"] = float(min(1.5, harm[i] / harm_p95))

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
    # v6-1b: 非サビフレーズ同士の類似度を先に測り、モチーフ再利用の閾値を
    # 曲内相対で決める（絶対下限と、曲内の最大類似度に対する相対下限の両方を
    # 満たす組だけを再利用対象にする。無関係なフレーズを誤って固定しないため）
    pair_sims = {}
    motif_sim_thr = 2.0  # 到達不能値（v5 でない曲・組が無い曲では再利用しない）
    if v5:
        sigs = [
            None
            if phrase_is_chorus[i] or len(p) < MOTIF_MIN_BARS
            else phrase_signature(phrase_slots(p))
            for i, p in enumerate(phrases)
        ]
        sim_vals = []
        for i in range(len(phrases)):
            if sigs[i] is None:
                continue
            for j in range(i):
                if sigs[j] is None:
                    continue
                s = _cosine(sigs[j], sigs[i])
                pair_sims[(j, i)] = s
                sim_vals.append(s)
        if sim_vals:
            motif_sim_thr = max(MOTIF_SIM_MIN, MOTIF_SIM_REL * max(sim_vals))
    motif_owner = {}  # 初出フレーズ番号 -> {"plan", "count", "bars"}
    motif_report = []

    prev_layer = None
    phrase_layers = []
    for pi, phrase in enumerate(phrases):
        is_chorus = phrase_is_chorus[pi]
        motif_mirror = False  # v6-1b: 非サビモチーフ再利用（2回目）の鏡像フラグ
        motif_vary = False  # v6-1b: 非サビモチーフ再利用（3回目以降）の末尾変化フラグ
        sustain_mode = None  # v6-1a
        sus_val = None
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
            # v6-1a: フレーズの持続性モードを主レイヤーと持続度で決める
            sus_val = phrase_sustain(pslots)
            if layer in ("melody", "vocal") and sus_val >= sustain_hi:
                sustain_mode = "sustained"
            elif layer == "drums" or sus_val <= sustain_lo:
                sustain_mode = "percussive"
            phrase_layers.append(
                {
                    "bars": [phrase[0], phrase[-1]] if phrase else [],
                    "layer": layer,
                    "chorus": is_chorus,
                    "scores": scores,
                    "sustain": round(sus_val, 3),
                    "sustainMode": sustain_mode,
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
                units, plan = plan_phrase(rng, phrase, unit_energy, gate, unit_fever, True, sustain_mode)
                motif_plan = plan
            else:
                plan = [motif_plan[i % len(motif_plan)] for i in range(len(units))]
        else:
            units = [(bar, half) for bar in phrase for half in (0, 1)]
            # v6-1b: 類似した非サビフレーズの再登場なら初出の計画（モチーフ）を
            # 再利用する。2回目は鏡像、3回目以降は末尾変化（サビの扱いに倣う）。
            # 再利用しなかったフレーズは初出として登録する。
            reuse = None
            if v5:
                for (j, i), sim in sorted(pair_sims.items()):
                    if i == pi and sim >= motif_sim_thr and j in motif_owner:
                        reuse = (motif_owner[j], sim)
                        break
            if reuse is not None:
                entry, sim = reuse
                entry["count"] += 1
                plan = [entry["plan"][k % len(entry["plan"])] for k in range(len(units))]
                motif_mirror = entry["count"] == 2
                motif_vary = entry["count"] >= 3
                motif_report.append(
                    {
                        "bars": [phrase[0], phrase[-1]] if phrase else [],
                        "sourceBars": entry["bars"],
                        "count": entry["count"],
                        "sim": round(sim, 3),
                    }
                )
            else:
                _units, plan = plan_phrase(
                    rng, phrase, unit_energy, gate, unit_fever, False, sustain_mode
                )
                if v5 and len(phrase) >= MOTIF_MIN_BARS:
                    motif_owner[pi] = {
                        "plan": list(plan),
                        "count": 1,
                        "bars": [phrase[0], phrase[-1]] if phrase else [],
                    }
        mirror = (is_chorus and chorus_count >= 2) or motif_mirror
        contour = v5 and layer in ("melody", "vocal")
        for ui, (unit, name) in enumerate(zip(units, plan)):
            if ((is_chorus and chorus_count >= 3) or motif_vary) and ui == len(units) - 1:
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
    # v6-1a: 長押しの優先度にも持続度を根拠として使う（持続的な音ほど長押しに
    # 向く。打撃的な場所の候補は相対的に後ろへ回り、結果として抑えられる）
    candidates.sort(
        key=lambda n: (
            -(n["strength"] * (1.25 if n["fever"] else 1.0) * (1.0 + 0.6 * n.get("sustain", 0.0))),
            n["time_ms"],
        )
    )
    accepted = []
    removed_ids = set()
    for n in candidates:
        if len(accepted) >= HOLD_TARGET + 2:
            break
        # v6-1a: 持続成分がほぼ無い場所（打撃音の頭）には長押しを置かない
        # （FEVER 区間は従来どおり許可する）
        if v5 and not n["fever"] and n.get("sustain", 0.0) < 0.12:
            continue
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

    # v6-2: フリック配置（曲別メタデータ flick: True の曲だけ。既定 OFF）
    # 置き場所は音楽的な「決め」だけ（割合ありきの変換はしない）:
    #   サビ内: 第1サビで決めた「サビ内のフレーズ構造上の位置」を、全サビへ
    #     各サビ自身のフレーズ構造に写像して適用する（標準化改訂で絶対拍
    #     オフセット方式から変更）。位置の根拠は サビ入り／フレーズ頭／
    #     強拍アクセント（sub==0 かつ strength 上位）／F0 の大きな跳躍
    #     （5半音以上）／フレーズ末。
    #   サビ外: フレーズ頭の強アクセント／クライマックス頭／サビ直前の一打
    #     のみ。総数はサビ内を超えず、1フレーズ1つまで、曲頭5秒は置かない。
    # 適格性（単独ノーツ・長押しでない・同レーン前後 250ms 以上）と難易度別の
    # 最小間隔は NK-S006 v1.4.2 の実績どおり。難易度は間隔の厳しい順に
    # easy ⊂ normal ⊂ hard の入れ子で割り当てる（rank 0=easyから / 1=normalから /
    # 2=hardのみ）。
    # ラスサビ全滅対策の改訂（NK-S006 試作の診断から）:
    #   - フォールバック写像: 構造位置にノーツが無い／対象外で写らなかった
    #     アンカーは、同じフレーズ内（サビ内フレーズ順が一致するフレーズ）の
    #     最も近い対象可ノーツへ寄せて写す。通常の寄せ幅は
    #     FLICK_FALLBACK_MAX_SUB（16分単位、4=1拍）まで。ただし、その
    #     サビにフリックが1つも残らない場合は救済として、フレーズ内の
    #     最も近いノーツまで範囲を広げる（ラスサビ全滅の再発防止）。
    #     ノーツ自体は作らない。
    #   - 間隔フィルタの優先順位: 正確に写ったサビ内フリックを最優先に
    #     確定し、寄せたサビ内、サビ外の順に、確定済みの全体に対して
    #     間隔を満たすものだけを通す。サビ直前の一打がラスサビの決めを
    #     間隔競合で潰す事故を防ぐ。
    flick_report = []
    anchor_stats = []
    if meta.get("flick"):
        FLICK_GAP_MS = {"easy": 4500, "normal": 2400, "hard": 1400}
        FLICK_FLOOR_MS = 1200
        FLICK_FALLBACK_MAX_SUB = 4
        time_count = {}
        for n in notes:
            time_count[n["time_ms"]] = time_count.get(n["time_ms"], 0) + 1
        lane_times = {}
        for n in notes:
            lane_times.setdefault(n["lane"], []).append(n["time_ms"])
        for v in lane_times.values():
            v.sort()

        def flick_eligible(n):
            if n["hold_ms"] > 0 or time_count[n["time_ms"]] > 1:
                return False
            ts = lane_times[n["lane"]]
            k = bisect.bisect_left(ts, n["time_ms"])
            if k > 0 and n["time_ms"] - ts[k - 1] < 250:
                return False
            if k < len(ts) - 1 and ts[k + 1] - n["time_ms"] < 250:
                return False
            return True

        def seg_idx(t_ms):
            for i, (a, b) in enumerate(fever):
                if a * 1000 <= t_ms < b * 1000:
                    return i
            return -1

        phrase_head_bars = {p[0] for p in phrases if p}
        phrase_of_bar = {}
        for p in phrases:
            for b in p:
                phrase_of_bar[b] = p
        selected = {}  # id -> (note, reason, kind)  kind: exact/fallback/outside

        # サビ内: 第1サビで「サビ内のフレーズ構造上の位置」を決め、全サビへ
        # 各サビ自身のフレーズ構造に写像して適用する（標準化改訂）。
        # キー = (サビ内フレーズ順, フレーズ先頭拍からの拍オフセット, sub)。
        # 旧方式（FEVER 開始点からの絶対拍オフセット）は、後続サビの長さや
        # 入り拍が違うと対応位置がずれる／落ちる欠陥があった。
        seg_notes = {}
        for n in notes:
            si = seg_idx(n["time_ms"])
            if si >= 0:
                seg_notes.setdefault(si, []).append(n)
        phrase_start_beat = {id(p): min(p) * 4 for p in phrases if p}
        seg_phrase_order = {}  # seg idx -> {phrase id: サビ内フレーズ順}
        for si, lst in seg_notes.items():
            starts = {}
            for n in lst:
                p = phrase_of_bar.get(n["bar"])
                if p is not None:
                    starts[id(p)] = phrase_start_beat[id(p)]
            seg_phrase_order[si] = {
                pid: i for i, (pid, _s) in enumerate(sorted(starts.items(), key=lambda kv: kv[1]))
            }

        def struct_key(si, n):
            p = phrase_of_bar.get(n["bar"])
            if p is None or id(p) not in seg_phrase_order.get(si, {}):
                return None
            return (
                seg_phrase_order[si][id(p)],
                n["beat"] - phrase_start_beat[id(p)],
                n["sub"],
            )

        if seg_notes.get(0):
            s0 = sorted(seg_notes[0], key=lambda n: (n["time_ms"], n["lane"]))
            # フレーズ末の決め判定用: 第1サビにかかるフレーズごとの最終ノーツ
            last_note_id = {}
            for n in s0:
                p = phrase_of_bar.get(n["bar"])
                if p is not None:
                    k = id(p)
                    if k not in last_note_id or n["time_ms"] > last_note_id[k][0]:
                        last_note_id[k] = (n["time_ms"], n["id"])
            last_ids = {v[1] for v in last_note_id.values()}
            anchors = {}
            prev = None
            for n in s0:
                reason = None
                if prev is None:
                    reason = "chorus-entry"
                elif n["bar"] in phrase_head_bars and n["sub"] == 0:
                    reason = "phrase-head"
                elif n["sub"] == 0 and n["strength"] >= thr[84]:
                    reason = "accent"
                elif (
                    n["sub"] == 0
                    and prev is not None
                    and not np.isnan(n["f0"])
                    and not np.isnan(prev["f0"])
                    and abs(n["f0"] - prev["f0"]) >= 5.0
                ):
                    reason = "f0-jump"
                elif n["id"] in last_ids and n["strength"] >= thr[65]:
                    reason = "phrase-final"
                if reason is not None and flick_eligible(n):
                    k = struct_key(0, n)
                    if k is not None:
                        anchors.setdefault(k, reason)
                prev = n
            # 全サビへ構造位置で適用（レーンは各サビの実体化どおり＝モチーフ連動）
            # selected の値は (note, reason, kind)。kind は間隔フィルタの
            # 優先順位用: "exact"（構造位置どおり）＞ "fallback"（寄せ）＞
            # "outside"（サビ外）。
            # 第1段: 構造位置そのものに一致する対象可ノーツへ写す。
            satisfied = {si: set() for si in seg_notes}
            for si, lst in seg_notes.items():
                for n in lst:
                    k = struct_key(si, n)
                    if k is not None and k in anchors and flick_eligible(n):
                        selected[n["id"]] = (n, anchors[k], "exact")
                        satisfied[si].add(k)
            # 第2段（フォールバック）: 写らなかったアンカーは、同じフレーズ内
            # （そのサビでのフレーズ順がアンカーと一致するフレーズ）で最も
            # 近い対象可ノーツへ寄せる。処理順はアンカーの目標位置順で
            # 決定的にし、1つのノーツは1つのアンカーにしか使わない。
            def fallback_note(si, k, max_sub):
                target_sub = k[1] * 4 + k[2]
                best = None
                for n in seg_notes[si]:
                    if n["id"] in selected:
                        continue
                    p = phrase_of_bar.get(n["bar"])
                    if p is None or seg_phrase_order.get(si, {}).get(id(p)) != k[0]:
                        continue
                    if not flick_eligible(n):
                        continue
                    off_sub = (n["beat"] - phrase_start_beat[id(p)]) * 4 + n["sub"]
                    d = abs(off_sub - target_sub)
                    if max_sub is not None and d > max_sub:
                        continue
                    cand = (d, n["time_ms"], n["lane"])
                    if best is None or cand < best[0]:
                        best = (cand, n)
                return best

            for si in sorted(seg_notes):
                if si == 0:
                    continue
                exact_n = len(satisfied[si])
                fb_dists, rescue_dists = [], []
                missing = [k for k in anchors if k not in satisfied[si]]
                order = lambda k: (k[0], k[1] * 4 + k[2])
                for k in sorted(missing, key=order):
                    best = fallback_note(si, k, FLICK_FALLBACK_MAX_SUB)
                    if best is not None:
                        selected[best[1]["id"]] = (best[1], anchors[k], "fallback")
                        satisfied[si].add(k)
                        fb_dists.append(best[0][0])
                # 救済: このサビにフリックが1つも残らない場合だけ、寄せ幅の
                # 上限を外して（フレーズ内は維持）残りのアンカーも寄せる。
                if not any(si == seg_idx(n["time_ms"]) for n, _r, _k in selected.values()):
                    for k in sorted(
                        (k for k in anchors if k not in satisfied[si]), key=order
                    ):
                        best = fallback_note(si, k, None)
                        if best is not None:
                            selected[best[1]["id"]] = (best[1], anchors[k], "fallback")
                            satisfied[si].add(k)
                            rescue_dists.append(best[0][0])
                anchor_stats.append(
                    {
                        "seg": si,
                        "targets": len(anchors),
                        "exact": exact_n,
                        "fallback": len(fb_dists),
                        "fallbackDistsSub": fb_dists,
                        "rescue": len(rescue_dists),
                        "rescueDistsSub": rescue_dists,
                        "dropped": len(anchors) - len(satisfied[si]),
                    }
                )
        # サビ外の決め: フレーズ頭の強アクセント／クライマックス頭／サビ直前。
        # 厳格化（標準化改訂）: 曲頭 FLICK_HEAD_GRACE_MS は置かない、ゲートは
        # すべて最強クラス（thr93）、1フレーズに1つまで、総数はサビ内を超えない。
        FLICK_HEAD_GRACE_MS = 5000
        inside_count = len(selected)
        outside_cands = []
        used_phrases = set()
        for n in sorted(notes, key=lambda n: (n["time_ms"], n["lane"])):
            if seg_idx(n["time_ms"]) >= 0 or n["id"] in selected:
                continue
            if n["time_ms"] < FLICK_HEAD_GRACE_MS:
                continue
            reason = None
            if n["bar"] in phrase_head_bars and n["sub"] == 0 and n["strength"] >= thr[93]:
                reason = "accent"
            elif n["bar"] in climax_bars and n["sub"] == 0 and n["strength"] >= thr[93]:
                reason = "accent"
            else:
                # サビ直前の一打: そのノーツの直後（次のノーツまで）に FEVER が始まる
                nxt = min((m["time_ms"] for m in notes if m["time_ms"] > n["time_ms"]), default=None)
                if (
                    n["strength"] >= thr[75]
                    and any(a * 1000 >= n["time_ms"] and (nxt is None or a * 1000 <= nxt) for a, _b in fever)
                ):
                    reason = "pre-chorus"
            if reason is not None and flick_eligible(n):
                p = phrase_of_bar.get(n["bar"])
                pk = id(p) if p is not None else None
                if pk in used_phrases:
                    continue
                used_phrases.add(pk)
                outside_cands.append((n, reason))
        # サビ外はサビ内総数を超えない（強い順に残す）
        if len(outside_cands) > inside_count:
            outside_cands.sort(key=lambda nr: (-nr[0]["strength"], nr[0]["time_ms"]))
            outside_cands = outside_cands[:inside_count]
        for n, reason in outside_cands:
            selected[n["id"]] = (n, reason, "outside")
        # 難易度別の最小間隔で入れ子に絞る（時刻順の貪欲。easy→normal→hard の順に
        # 厳しい間隔で間引くので、部分集合関係が保たれる）
        chosen = sorted(selected.values(), key=lambda nr: (nr[0]["time_ms"], nr[0]["lane"]))

        def gap_filter(items, gap_ms):
            # 優先順位つきフィルタ: kind の格（exact ＞ fallback ＞ outside）
            # の順に確定していく。最上位の exact は同格どうし時刻順の貪欲、
            # それ以外は確定済みの全フリック（前後両方向）に対して間隔を
            # 満たすものだけを通す。時刻順の一括貪欲だと、先に現れる
            # サビ外（サビ直前の一打など）が後のサビ内の決めを潰すし、
            # 寄せたフリックが正確に写った決めを潰すこともある。
            gap = max(gap_ms, FLICK_FLOOR_MS)
            by_time = lambda nr: (nr[0]["time_ms"], nr[0]["lane"])
            tiers = [
                sorted((it for it in items if it[2] == kind), key=by_time)
                for kind in ("exact", "fallback", "outside")
            ]
            out, times, last = [], [], None
            for it in tiers[0]:
                t = it[0]["time_ms"]
                if last is None or t - last >= gap:
                    out.append(it)
                    times.append(t)
                    last = t
            for tier in tiers[1:]:
                for it in tier:
                    t = it[0]["time_ms"]
                    k = bisect.bisect_left(times, t)
                    if (k == 0 or t - times[k - 1] >= gap) and (
                        k == len(times) or times[k] - t >= gap
                    ):
                        out.append(it)
                        times.insert(k, t)
            return sorted(out, key=by_time)

        hard_sel = gap_filter(chosen, FLICK_GAP_MS["hard"])
        normal_sel = gap_filter(hard_sel, FLICK_GAP_MS["normal"])
        easy_sel = gap_filter(normal_sel, FLICK_GAP_MS["easy"])
        rank_of = {}
        for item in hard_sel:
            rank_of[item[0]["id"]] = 2
        for item in normal_sel:
            rank_of[item[0]["id"]] = 1
        for item in easy_sel:
            rank_of[item[0]["id"]] = 0
        for nid, rank in rank_of.items():
            n, reason, _kind = selected[nid]
            n["flick_rank"] = rank
            flick_report.append(
                {"time": n["time_ms"], "lane": n["lane"], "reason": reason, "rank": rank}
            )
        flick_report.sort(key=lambda r: (r["time"], r["lane"]))

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

    def thin(ids, cap, min_gap, fever_w=1.2, pinned=frozenset()):
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
        # v6-3: ピン留めノーツ（フリックのアンカー）は間引きで落とさず先に確定する
        for n in sorted(
            (notes_by_id[i] for i in ids if i in pinned),
            key=lambda n: (n["time_ms"], n["lane"]),
        ):
            kept.append(n)
            kept_times.append(n["time_ms"])
            lane_kept[n["lane"]] += 1
        kept_ids = {n["id"] for n in kept}

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
                    if n["id"] in kept_ids:
                        continue
                    if gap_ok(n):
                        kept.append(n)
                        kept_times.append(n["time_ms"])
                        kept_ids.add(n["id"])
                        lane_kept[l] += 1
                        progress = True
                        break
        return {n["id"] for n in kept}, total_target

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

    def fill_density_floor(ids, pool, cap, min_gap, floor_count):
        """密度下限ガード（v6-1.1）: 保持数が floor_count 未満なら候補を戻す。

        thin の目標総数は最少レーンの候補数から決まるため、1レーンの候補が
        減っただけで難易度全体が大きく割り込むことがある（umi normal の
        −22% の実例）。プール（間引き前の候補集合）に対する保持率で下限を
        決め、割り込んだ分だけ、落ちた候補を強さ順（FEVER は thin と同じ
        ×1.2 優先）に戻す。戻すのは pool の中だけ＝呼び出し側で上位難易度の
        確定集合と積を取って渡すので入れ子は保たれる。安全条件は
        fill_fever_gaps と同じ物差し: 最小間隔、戻した後のレーン割合が
        検証範囲（0.18〜0.32）の内側、同一レーン3連を作らないこと。
        戻した後に修復が落とす分は呼び出し側の再修復ループで扱う。
        """
        ids = set(ids)
        if len(ids) >= floor_count:
            return ids
        rest = sorted(
            (notes_by_id[i] for i in pool if i not in ids),
            key=lambda n: -(n["strength"] * (1.2 if n["fever"] else 1.0)),
        )
        for n in rest:
            if len(ids) >= floor_count or len(ids) >= cap:
                break
            kept_notes = sorted((notes_by_id[i] for i in ids), key=lambda k: (k["time_ms"], k["lane"]))
            kept = [k["time_ms"] for k in kept_notes]
            t = n["time_ms"]
            if any(t != k and abs(t - k) < min_gap for k in kept):
                continue
            total = len(ids)
            lane_counts = [sum(1 for k in kept_notes if k["lane"] == l) for l in range(4)]
            shares = [
                (lane_counts[l] + (1 if l == n["lane"] else 0)) / (total + 1) for l in range(4)
            ]
            if max(shares) > LANE_MAX_SHARE or min(shares) < LANE_MIN_SHARE:
                continue
            seq = kept_notes
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
            # 両親指制約 C3a／C3b（check-two-thumb.py と同じ定義）を挿入位置の
            # 周辺でも先回りで避ける。戻した直後の修復で落とされ直すのを防ぐため
            gseq = sorted(
                [(k["beat"] * 4 + k["sub"], k["lane"]) for k in kept_notes]
                + [(n["beat"] * 4 + n["sub"], L)]
            )
            gi = gseq.index((n["beat"] * 4 + n["sub"], L))
            side = L // 2
            run = 1
            k = gi
            while (
                k - 1 >= 0
                and gseq[k - 1][1] // 2 == side
                and gseq[k][0] - gseq[k - 1][0] <= 1
            ):
                run += 1
                k -= 1
            k = gi
            while (
                k + 1 < len(gseq)
                and gseq[k + 1][1] // 2 == side
                and gseq[k + 1][0] - gseq[k][0] <= 1
            ):
                run += 1
                k += 1
            if run >= 3:
                continue
            bad_side = False
            for s0 in range(max(0, gi - 4), gi + 1):
                lanes_seen = set()
                prev_g = None
                prev_lane = None
                length = 0
                for g2, l2 in gseq[s0 : gi + 5]:
                    if l2 // 2 != side:
                        break
                    if prev_g is not None and g2 - prev_g > 2:
                        break
                    if prev_lane is not None and l2 == prev_lane:
                        break
                    if l2 not in lanes_seen and len(lanes_seen) >= 2:
                        break
                    lanes_seen.add(l2)
                    prev_g = g2
                    prev_lane = l2
                    length += 1
                if length >= 5 and len(lanes_seen) == 2:
                    bad_side = True
                    break
            if bad_side:
                continue
            ids.add(n["id"])
        return ids


    # ---- v6-4: ボーカル被覆（fill_fever_gaps の一般化） ----
    # 適用範囲を FEVER 区間から歌詞アクティブ区間全体へ広げ、上限を難易度別
    # （VOCAL_COVER_GAP_S）にする。呼び出しはフリック整形・検証の後（後段）。
    # ここでは関数と状態だけを用意する。
    vocal_coverage_stats = {
        d: {"fromPool": 0, "synthesized": 0, "unfilledGaps": 0} for d in ("easy", "normal", "hard")
    }
    synth_next_id = [max((n["id"] for n in notes), default=-1) + 1]

    def n_sort_key(k):
        return (k["time_ms"], k["lane"])

    def vocal_score(slot):
        """合成位置の根拠: ボーカルレイヤー強度（v5 曲は vocal の eff、
        それ以外は全帯域 strength）。"""
        if v5 and "eff_by_layer" in slot:
            return float(slot["eff_by_layer"].get("vocal", slot["strength"]))
        return float(slot["strength"])

    def coverage_flick_times(diff):
        rank_max = {"easy": 0, "normal": 1, "hard": 2}[diff]
        return sorted(
            notes_by_id[i]["time_ms"]
            for i in id_sets[diff]
            if notes_by_id[i].get("flick_rank") is not None
            and notes_by_id[i]["flick_rank"] <= rank_max
        )

    def in_flick_exclusion(t, diff):
        """フリック手前窓と直後300ms回復区間（補填を入れない範囲）。"""
        pre_ms = VOCAL_COVER_FLICK_PRE_BEATS[diff] * period * 1000
        for ft in coverage_flick_times(diff):
            if ft - pre_ms <= t < ft:
                return True
            if ft < t <= ft + VOCAL_COVER_FLICK_RECOVERY_MS:
                return True
        return False

    def coverage_cand_safe(n, kept_notes, min_gap, diff):
        """補填候補の安全条件（fill_density_floor と同じ物差し＋フリック回避
        ＋両親指 C2 の先回り）。補填ノーツはタップのみとする。"""
        if n["hold_ms"] > 0 or n.get("flick_rank") is not None:
            return False
        t = n["time_ms"]
        if in_flick_exclusion(t, diff):
            return False
        kept = [k["time_ms"] for k in kept_notes]
        # 同レーン最小間隔（全体の最小間隔で見る。同刻は同時押しとして別扱い）
        if any(t != k and abs(t - k) < min_gap for k in kept):
            return False
        same_time = [k for k in kept_notes if k["time_ms"] == t]
        if same_time:
            # 同時押しは2つまで・左右に分かれるペアだけ（C1）
            if len(same_time) >= 2 or same_time[0]["lane"] // 2 == n["lane"] // 2:
                return False
        # C2: 長押しの帯の中は拘束側に置かない
        for k in kept_notes:
            if k["hold_ms"] > 0 and k["time_ms"] < t <= k["time_ms"] + k["hold_ms"] and k["lane"] // 2 == n["lane"] // 2:
                return False
        # レーン割合が検証範囲（0.18〜0.32）の外に出る候補は避ける
        total = len(kept_notes)
        lane_counts = [sum(1 for k in kept_notes if k["lane"] == l) for l in range(4)]
        shares = [(lane_counts[l] + (1 if l == n["lane"] else 0)) / (total + 1) for l in range(4)]
        if max(shares) > LANE_MAX_SHARE or min(shares) < LANE_MIN_SHARE:
            return False
        # 同一レーン3連の先回り回避（fill_fever_gaps と同じ見分け方）
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
            return False
        # C3a／C3b の先回り回避（fill_density_floor と同じ見方）
        gseq = sorted(
            [(k["beat"] * 4 + k["sub"], k["lane"]) for k in kept_notes]
            + [(n["beat"] * 4 + n["sub"], L)]
        )
        gi = gseq.index((n["beat"] * 4 + n["sub"], L))
        side = L // 2
        run = 1
        k = gi
        while k - 1 >= 0 and gseq[k - 1][1] // 2 == side and gseq[k][0] - gseq[k - 1][0] <= 1:
            run += 1
            k -= 1
        k = gi
        while k + 1 < len(gseq) and gseq[k + 1][1] // 2 == side and gseq[k + 1][0] - gseq[k][0] <= 1:
            run += 1
            k += 1
        if run >= 3:
            return False
        for s0 in range(max(0, gi - 4), gi + 1):
            lanes_seen = set()
            prev_g = None
            prev_lane = None
            length = 0
            for g2, l2 in gseq[s0 : gi + 5]:
                if l2 // 2 != side:
                    break
                if prev_g is not None and g2 - prev_g > 2:
                    break
                if prev_lane is not None and l2 == prev_lane:
                    break
                if l2 not in lanes_seen and len(lanes_seen) >= 2:
                    break
                lanes_seen.add(l2)
                prev_g = g2
                prev_lane = l2
                length += 1
            if length >= 5 and len(lanes_seen) == 2:
                return False
        return True

    def lyric_spans_ms():
        """歌詞アクティブ区間（ms、クリップ済み・隣接行は連結）。

        lyrics.json の行は endMs＝次の行の startMs で連なっているため、
        隣接する行を連結しないと、行をまたぐ空白を過小に測ってしまう。
        行間に実際に無音がある区間（end < 次の start）は連結しない。"""
        spans = []
        for lo_s, hi_s in lyric_intervals:
            lo = max(int(lo_s * 1000), START_MS)
            hi = min(int(hi_s * 1000), duration_ms - int(END_MARGIN_S * 1000))
            if hi <= lo:
                continue
            if spans and lo <= spans[-1][1] + 1:
                spans[-1] = (spans[-1][0], max(spans[-1][1], hi))
            else:
                spans.append((lo, hi))
        return spans

    def coverage_max_gap_ms(diff):
        """歌詞アクティブ区間内の最大空白（ms）。歌詞が無ければ 0。"""
        if not lyric_intervals:
            return 0
        kept = sorted(notes_by_id[i]["time_ms"] for i in id_sets[diff])
        worst = 0
        for lo, hi in lyric_spans_ms():
            pts = [lo] + [t for t in kept if lo <= t < hi] + [hi]
            for a, b in zip(pts, pts[1:]):
                worst = max(worst, b - a)
        return worst

    def fill_vocal_coverage(diff, ids, pool_ids, min_gap, upper=()):
        """歌詞アクティブ区間の空白を上限以下まで埋める（v6-4）。

        優先順: (1) 落ちた候補プール（pool_ids。呼び出し側で上位難易度の
        確定集合に限る＝入れ子維持）から戻す。(2) プールが空なら拍グリッド
        （sub==0）でボーカル強度が相対的に高いスロットへ合成する。
        キャップは見ない（被覆保証を優先し、超過はレポートで明示する）。
        upper は [(難易度名, その確定集合, 最小間隔), ...]（上位難易度）。
        合成ノーツは上位難易度にも安全な場合に限り作り、上位の集合にも
        同時に加える（合成ノーツが下位だけに存在すると入れ子が崩れるため。
        上位で先に作られた合成ノーツは pool 経由で下位の候補にもなる）。
        """
        ids = set(ids)
        cap_ms = VOCAL_COVER_GAP_S[diff] * 1000
        pool = [notes_by_id[i] for i in pool_ids if i not in ids]
        for lo, hi in lyric_spans_ms():
            for _ in range(60):
                kept_notes = sorted((notes_by_id[i] for i in ids), key=lambda n: n["time_ms"])
                kept = [n["time_ms"] for n in kept_notes]
                inside = [t for t in kept if lo <= t < hi]
                pts = [lo] + inside + [hi]
                worst = None
                for a, b in zip(pts, pts[1:]):
                    if worst is None or b - a > worst[1] - worst[0]:
                        worst = (a, b)
                if worst is None or worst[1] - worst[0] <= cap_ms:
                    break
                a, b = worst
                mid = (a + b) / 2
                cands = [
                    n
                    for n in pool
                    if a < n["time_ms"] < b and coverage_cand_safe(n, kept_notes, min_gap, diff)
                ]
                if cands:
                    cands.sort(key=lambda n: (0 if n["sub"] == 0 else 1, abs(n["time_ms"] - mid), -n["strength"]))
                    chosen = cands[0]
                    ids.add(chosen["id"])
                    pool.remove(chosen)
                    vocal_coverage_stats[diff]["fromPool"] += 1
                    continue
                # プールが空: 拍グリッド位置へ合成する。位置は sub==0 に限る
                # ため、合成ノーツは全難易度の補填候補になり得る（入れ子維持は
                # 呼び出し側のプール制限で担保する）
                kept_times = set(kept)
                slots = [
                    sl
                    for sl in playable
                    if sl["sub"] == 0
                    and a < int(round(sl["time"] * 1000)) < b
                    and int(round(sl["time"] * 1000)) not in kept_times
                ]
                slots.sort(key=lambda sl: (-vocal_score(sl), sl["time"]))
                placed = False
                lane_counts = [sum(1 for k in kept_notes if k["lane"] == l) for l in range(4)]
                for sl in slots:
                    t = int(round(sl["time"] * 1000))
                    for lane in sorted(range(4), key=lambda l: (lane_counts[l], l)):
                        cand = {
                            "id": synth_next_id[0],
                            "time_ms": t,
                            "lane": lane,
                            "hold_ms": 0,
                            "tail_ms": 0,
                            "kind": "synth",
                            "pattern": None,
                            "unit_rel": 0,
                            "sub": sl["sub"],
                            "beat": sl["beat"],
                            "bar": sl["beat"] // 4,
                            "strength": float(sl["strength"]),
                            "sustain": sl.get("sustain", 0.0),
                            "f0": sl.get("f0", float("nan")),
                            "pitch_lane": sl["pitch_lane"],
                            "fever": sl["fever"],
                            "energy": sl["energy"],
                        }
                        if coverage_cand_safe(cand, kept_notes, min_gap, diff) and all(
                            coverage_cand_safe(
                                cand,
                                sorted(
                                    (notes_by_id[i] for i in uset),
                                    key=lambda k: n_sort_key(k),
                                ),
                                ugap,
                                udiff,
                            )
                            for udiff, uset, ugap in upper
                        ):
                            notes_by_id[cand["id"]] = cand
                            notes.append(cand)
                            synth_next_id[0] += 1
                            ids.add(cand["id"])
                            for _udiff, uset, _ugap in upper:
                                uset.add(cand["id"])
                            vocal_coverage_stats[diff]["synthesized"] += 1
                            placed = True
                            break
                    if placed:
                        break
                if not placed:
                    vocal_coverage_stats[diff]["unfilledGaps"] += 1
                    break
        return ids

    # v6-3: フリックのアンカーは難易度導出でピン留めし、修復でも優先的に残す
    flick_pin = {"normal": set(), "easy": set()}
    flick_protected = set()
    if meta.get("flick"):
        for n in notes:
            r = n.get("flick_rank")
            if r is not None:
                flick_protected.add(n["id"])
                if r <= 1:
                    flick_pin["normal"].add(n["id"])
                if r <= 0:
                    flick_pin["easy"].add(n["id"])
    normal_pool = set(normal_ids)
    normal_ids, normal_target = thin(normal_ids, NORMAL_CAP, 150, pinned=flick_pin["normal"])
    easy_pre_thin = {i for i in normal_ids if notes_by_id[i]["sub"] == 0 and notes_by_id[i]["kind"] != "chord"}
    easy_ids = set(easy_pre_thin)
    # easy は拍位置のみで候補が少なく、サビが16分中心になるとサビの取り分が
    # 構造的に減るため、FEVER 優先の重みを normal より強める（2026-11-20）
    easy_ids, easy_target = thin(easy_ids, EASY_CAP, 260, fever_w=1.6, pinned=flick_pin["easy"])
    id_sets = {"hard": hard_ids, "normal": normal_ids, "easy": easy_ids}
    # 同一レーン修復と両親指修復は、片方の「落とす」が他方の違反（連の接続）を
    # 作ることがあるので、どちらも動かなくなるまで交互に回す（落とすだけなので収束する）
    for _ in range(50):
        before = {d: len(s) for d, s in id_sets.items()}
        id_sets = repair_runs(id_sets, notes_by_id, protected=flick_protected)
        id_sets = repair_side_runs(id_sets, notes_by_id, chord_ids, protected=flick_protected)
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

    # v6-1.1 密度下限ガード: thin の目標が cap でなく最少レーン由来で決まった
    # 難易度だけを対象に、候補プールの DENSITY_FLOOR_RATIO 倍を下限として、
    # 割り込んだ分は落ちた候補を強さ順に戻す。戻すと修復対象が増えるため、
    # 戻し→修復を下限到達か変化なしまで繰り返す（落とすだけの修復と安全条件
    # 付きの戻しなので、数回で収束する）。cap 律速の難易度は下限 0 ＝無発動。
    import math

    normal_floor = (
        min(NORMAL_CAP, math.ceil(DENSITY_FLOOR_RATIO * len(normal_pool)))
        if normal_target < NORMAL_CAP
        else 0
    )
    easy_floor = (
        min(EASY_CAP, math.ceil(DENSITY_FLOOR_RATIO * len(easy_pre_thin)))
        if easy_target < EASY_CAP
        else 0
    )
    for _ in range(3):
        if len(id_sets["normal"]) >= normal_floor and len(id_sets["easy"]) >= easy_floor:
            break
        before = {d: len(s) for d, s in id_sets.items()}
        id_sets["normal"] = fill_density_floor(
            id_sets["normal"], normal_pool & id_sets["hard"], NORMAL_CAP, 150, normal_floor
        )
        id_sets["easy"] = fill_density_floor(
            id_sets["easy"],
            {
                i
                for i in id_sets["normal"]
                if notes_by_id[i]["sub"] in (0, 2) and notes_by_id[i]["kind"] != "chord"
            },
            EASY_CAP,
            260,
            easy_floor,
        )
        if all(len(id_sets[d]) == before[d] for d in before):
            break
        for _ in range(50):
            before_r = {d: len(s) for d, s in id_sets.items()}
            id_sets = repair_runs(id_sets, notes_by_id, protected=flick_protected)
            id_sets = repair_side_runs(id_sets, notes_by_id, chord_ids, protected=flick_protected)
            if all(len(id_sets[d]) == before_r[d] for d in before_r):
                break
        else:
            raise AssertionError(f"{song_id}: 密度下限ガード後の修復が収束しない")

    # v6-3: フリックの流れ整形と流れ検証（flick: True の曲だけ。OFF の曲は無変更）
    # 整形: フリック直前の窓ではパターンノーツを間引いて「溜め」を作り、
    #   フリック直後の同レーンには回復ウィンドウを空ける。落とす集合は
    #   hard ⊆ normal ⊆ easy の順に積み増し、入れ子を保つ。
    # 検証: 届く難易度すべてで流れを検査し、引っかかったフリックは
    #   ±1拍以内の落ち着いた適格ノーツへずらす。無理なら落とす。
    # 上限: SONGS の flick_budget（任意の曲別メタ）を超える場合は、
    #   優先度の低いフリックから rank を上げて（最終的には外して）収める。
    flick_final_report = []
    flow_log = []
    shape_stats = {"preDropped": 0, "postDropped": 0}
    if meta.get("flick"):
        FLICK_PRE_WINDOW_BEATS = {"easy": 2.0, "normal": 1.5, "hard": 1.0}
        FLICK_PRE_DENSITY_MS = 500
        FLICK_PRE_DENSITY_MAX = {"easy": 1, "normal": 2, "hard": 3}
        FLICK_RECOVERY_MS = 300
        FLICK_SAME_LANE_MS = 250
        rank_max_of = {"easy": 0, "normal": 1, "hard": 2}
        flick_meta = {nid: (rs, kd) for nid, (_n, rs, kd) in selected.items()}
        flick_notes = {n["id"]: n for n in notes if n.get("flick_rank") is not None}

        def delivered(diff):
            rm = rank_max_of[diff]
            return sorted(
                (
                    notes_by_id[i]
                    for i in id_sets[diff]
                    if notes_by_id[i].get("flick_rank") is not None
                    and notes_by_id[i]["flick_rank"] <= rm
                ),
                key=lambda n: (n["time_ms"], n["lane"]),
            )

        # ---- 整形（入れ子を保つ階層落とし） ----
        # テンプレート標準化時の追加ガード: 落としでレーン割合が検証範囲
        # （LANE_MIN_SHARE〜LANE_MAX_SHARE）から外れる場合はそのノーツを落とさない。
        # ノーツ総数の少ない小さい譜面では、数個の落としでも割合が跳ねるため
        # （NK-S006 の実曲では発動しなかったが、テンプレートの仮曲で再現した）。
        lane_counts = {}
        lane_totals = {}
        for d in ("easy", "normal", "hard"):
            c = [0, 0, 0, 0]
            for i in id_sets[d]:
                c[notes_by_id[i]["lane"]] += 1
            lane_counts[d] = c
            lane_totals[d] = len(id_sets[d])

        def drop_keeps_lane_balance(n):
            for d in ("easy", "normal", "hard"):
                if n["id"] not in id_sets[d]:
                    continue
                total = lane_totals[d] - 1
                if total <= 0:
                    return False
                for lane in range(4):
                    cnt = lane_counts[d][lane] - (1 if lane == n["lane"] else 0)
                    share = cnt / total
                    if share < LANE_MIN_SHARE or share > LANE_MAX_SHARE:
                        return False
            return True

        def apply_drop(n):
            for d in ("easy", "normal", "hard"):
                if n["id"] in id_sets[d]:
                    lane_counts[d][n["lane"]] -= 1
                    lane_totals[d] -= 1

        drop_acc = set()
        for diff in ("hard", "normal", "easy"):
            win_ms = FLICK_PRE_WINDOW_BEATS[diff] * period * 1000
            for fn in delivered(diff):
                t = fn["time_ms"]
                for n in notes:
                    nid = n["id"]
                    if nid not in id_sets[diff] or nid in flick_notes or nid in drop_acc:
                        continue
                    if (
                        t - win_ms <= n["time_ms"] < t
                        and n["kind"] == "pattern"
                        and n["hold_ms"] == 0
                    ):
                        if not drop_keeps_lane_balance(n):
                            continue
                        drop_acc.add(nid)
                        apply_drop(n)
                        shape_stats["preDropped"] += 1
                    elif n["lane"] == fn["lane"] and t < n["time_ms"] <= t + FLICK_RECOVERY_MS:
                        if not drop_keeps_lane_balance(n):
                            continue
                        drop_acc.add(nid)
                        apply_drop(n)
                        shape_stats["postDropped"] += 1
            id_sets[diff] -= drop_acc

        # 整形の落としで生じた同一レーン連・両親指違反を修復し直す
        # （ノーツを落とすと同レーンが隣接して連ができるため。落とすだけ
        # なので収束する。フリックは protected で優先的に残す）
        for _ in range(50):
            before = {d: len(s) for d, s in id_sets.items()}
            id_sets = repair_runs(id_sets, notes_by_id, protected=flick_protected)
            id_sets = repair_side_runs(
                id_sets, notes_by_id, chord_ids, protected=flick_protected
            )
            if all(len(id_sets[d]) == before[d] for d in before):
                break
        else:
            raise AssertionError(f"{song_id}: 整形後の修復が収束しない")

        # ---- 流れ検証 ----
        def flick_times_in(diff, exclude_id=None):
            rm = rank_max_of[diff]
            return sorted(
                notes_by_id[i]["time_ms"]
                for i in id_sets[diff]
                if i != exclude_id
                and notes_by_id[i].get("flick_rank") is not None
                and notes_by_id[i]["flick_rank"] <= rm
            )

        def flow_problems(diff, cand, other_times):
            ids = id_sets[diff]
            t = cand["time_ms"]
            probs = []
            pre = sum(
                1
                for i in ids
                if t - FLICK_PRE_DENSITY_MS <= notes_by_id[i]["time_ms"] < t
            )
            if pre > FLICK_PRE_DENSITY_MAX[diff]:
                probs.append(f"pre-density:{pre}>{FLICK_PRE_DENSITY_MAX[diff]}")
            lane_after = [
                notes_by_id[i]["time_ms"]
                for i in ids
                if notes_by_id[i]["lane"] == cand["lane"] and notes_by_id[i]["time_ms"] > t
            ]
            if lane_after and min(lane_after) - t < FLICK_RECOVERY_MS:
                probs.append(f"post-lane:{min(lane_after) - t}<{FLICK_RECOVERY_MS}")
            for ot in other_times:
                if abs(ot - t) < FLICK_GAP_MS[diff]:
                    probs.append(f"flick-gap:{abs(ot - t)}<{FLICK_GAP_MS[diff]}")
                    break
            return probs

        def shift_candidates(fn, rank):
            t0 = fn["time_ms"]
            hard_ids = id_sets["hard"]
            time_count_h = {}
            for i in hard_ids:
                tt = notes_by_id[i]["time_ms"]
                time_count_h[tt] = time_count_h.get(tt, 0) + 1
            lane_times_h = {}
            for i in hard_ids:
                lane_times_h.setdefault(notes_by_id[i]["lane"], []).append(
                    notes_by_id[i]["time_ms"]
                )
            out = []
            for cn in notes:
                if cn["id"] == fn["id"] or cn.get("flick_rank") is not None:
                    continue
                if cn["id"] not in hard_ids or cn["hold_ms"] > 0:
                    continue
                if abs(cn["time_ms"] - t0) > period * 1000:
                    continue
                if time_count_h[cn["time_ms"]] > 1:
                    continue
                near = [
                    x
                    for x in lane_times_h[cn["lane"]]
                    if abs(x - cn["time_ms"]) < FLICK_SAME_LANE_MS
                ]
                if len(near) > 1:
                    continue
                saved = fn["flick_rank"]
                fn["flick_rank"] = None
                ok = True
                score = 0
                for diff in ("easy", "normal", "hard"):
                    if rank > rank_max_of[diff] or cn["id"] not in id_sets[diff]:
                        continue
                    pr = flow_problems(diff, cn, flick_times_in(diff, exclude_id=fn["id"]))
                    if pr:
                        ok = False
                        break
                    score += sum(
                        1
                        for i in id_sets[diff]
                        if cn["time_ms"] - FLICK_PRE_DENSITY_MS
                        <= notes_by_id[i]["time_ms"]
                        < cn["time_ms"]
                    )
                fn["flick_rank"] = saved
                if ok:
                    out.append((score, abs(cn["time_ms"] - t0), cn["time_ms"], cn["lane"], cn))
            out.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
            return out

        for fn in sorted(flick_notes.values(), key=lambda n: (n["time_ms"], n["lane"])):
            rank = fn.get("flick_rank")
            if rank is None:
                continue
            diffs_in = [
                d
                for d in ("easy", "normal", "hard")
                if rank <= rank_max_of[d] and fn["id"] in id_sets[d]
            ]
            problems = {}
            for d in diffs_in:
                pr = flow_problems(d, fn, flick_times_in(d, exclude_id=fn["id"]))
                if pr:
                    problems[d] = pr
            if diffs_in and not problems:
                continue
            reason0 = flick_meta.get(fn["id"], ("?", "?"))[0]
            cands = shift_candidates(fn, rank)
            if cands:
                cn = cands[0][4]
                fn["flick_rank"] = None
                cn["flick_rank"] = rank
                flick_meta[cn["id"]] = flick_meta.get(fn["id"], ("?", "?"))
                flick_notes[cn["id"]] = cn
                del flick_notes[fn["id"]]
                flow_log.append(
                    {
                        "action": "replace" if not diffs_in else "shift",
                        "from": fn["time_ms"],
                        "fromLane": fn["lane"],
                        "to": cn["time_ms"],
                        "toLane": cn["lane"],
                        "rank": rank,
                        "reason": reason0,
                        "problems": problems,
                    }
                )
            else:
                fn["flick_rank"] = None
                del flick_notes[fn["id"]]
                flow_log.append(
                    {
                        "action": "lost" if not diffs_in else "drop",
                        "from": fn["time_ms"],
                        "fromLane": fn["lane"],
                        "rank": rank,
                        "reason": reason0,
                        "problems": problems,
                    }
                )

        # ---- 上限（flick_budget）への収納: rank を上げる／外す ----
        budget = meta.get("flick_budget") or {}
        kind_rank = {"exact": 2, "fallback": 1, "outside": 0}
        reason_rank = {
            "chorus-entry": 5,
            "phrase-head": 4,
            "accent": 3,
            "f0-jump": 2,
            "phrase-final": 1,
            "pre-chorus": 0,
        }

        def keep_key(n):
            rs, kd = flick_meta.get(n["id"], ("?", "?"))
            return (
                kind_rank.get(kd, 0),
                reason_rank.get(rs, 0),
                n["strength"],
                -n["time_ms"],
            )

        for diff in ("easy", "normal", "hard"):
            cap = budget.get(diff)
            if cap is None:
                continue
            rm = rank_max_of[diff]
            while True:
                cur = [
                    n
                    for n in flick_notes.values()
                    if n.get("flick_rank") is not None
                    and n["flick_rank"] <= rm
                    and n["id"] in id_sets[diff]
                ]
                if len(cur) <= cap:
                    break
                cur.sort(key=keep_key)
                victim = cur[0]
                if diff == "hard":
                    victim["flick_rank"] = None
                    del flick_notes[victim["id"]]
                    flow_log.append(
                        {
                            "action": "budget-remove",
                            "from": victim["time_ms"],
                            "fromLane": victim["lane"],
                            "rank": rm,
                            "reason": flick_meta.get(victim["id"], ("?", "?"))[0],
                            "problems": {"budget": diff},
                        }
                    )
                else:
                    old_rank = victim["flick_rank"]
                    victim["flick_rank"] = rm + 1
                    flow_log.append(
                        {
                            "action": "budget-raise",
                            "from": victim["time_ms"],
                            "fromLane": victim["lane"],
                            "rank": old_rank,
                            "reason": flick_meta.get(victim["id"], ("?", "?"))[0],
                            "problems": {"budget": diff},
                        }
                    )
        flick_final_report = sorted(
            (
                {
                    "time": n["time_ms"],
                    "lane": n["lane"],
                    "reason": flick_meta.get(n["id"], ("?", "?"))[0],
                    "rank": n["flick_rank"],
                }
                for n in flick_notes.values()
                if n.get("flick_rank") is not None
            ),
            key=lambda r: (r["time"], r["lane"]),
        )


    # ---- v6-4: ボーカル被覆の適用（フリック整形・流れ検証・budget の後） ----
    # フリックの位置・個数を変えないため、フリック処理が全て終わってから行う。
    # 補填→修復を繰り返し、修復で空白が再発しても上限以下に収める。
    # 歌詞入力が無い曲では従来動作（上の fill_fever_gaps まで）で終わる。
    vocal_coverage_report = {"lyrics": bool(lyric_intervals), "diffs": {}}
    if lyric_intervals:
        caps_by_diff = {"easy": EASY_CAP, "normal": NORMAL_CAP, "hard": HARD_CAP}
        min_gap_by_diff = {"easy": 260, "normal": 150, "hard": 150}
        counts_before = {d: len(id_sets[d]) for d in ("easy", "normal", "hard")}
        for _ in range(3):
            id_sets["hard"] = fill_vocal_coverage(
                "hard", id_sets["hard"], set(notes_by_id), min_gap_by_diff["hard"]
            )
            id_sets["normal"] = fill_vocal_coverage(
                "normal",
                id_sets["normal"],
                set(id_sets["hard"]),
                min_gap_by_diff["normal"],
                upper=(("hard", id_sets["hard"], min_gap_by_diff["hard"]),),
            )
            id_sets["easy"] = fill_vocal_coverage(
                "easy",
                id_sets["easy"],
                {
                    i
                    for i in id_sets["normal"]
                    if notes_by_id[i]["sub"] in (0, 2) and notes_by_id[i]["kind"] != "chord"
                },
                min_gap_by_diff["easy"],
                upper=(
                    ("normal", id_sets["normal"], min_gap_by_diff["normal"]),
                    ("hard", id_sets["hard"], min_gap_by_diff["hard"]),
                ),
            )
            # 補填で生じた同一レーン連・両親指違反を修復し直す（落とすだけ
            # なので収束する。フリックは protected で残す）
            for _ in range(50):
                before_r = {d: len(s2) for d, s2 in id_sets.items()}
                id_sets = repair_runs(id_sets, notes_by_id, protected=flick_protected)
                id_sets = repair_side_runs(id_sets, notes_by_id, chord_ids, protected=flick_protected)
                if all(len(id_sets[d]) == before_r[d] for d in before_r):
                    break
            else:
                raise AssertionError(f"{song_id}: 被覆後の修復が収束しない")
            if all(
                coverage_max_gap_ms(d) <= VOCAL_COVER_GAP_S[d] * 1000
                for d in ("easy", "normal", "hard")
            ):
                break
        for d in ("easy", "normal", "hard"):
            after = len(id_sets[d])
            vocal_coverage_report["diffs"][d] = {
                "gapCapMs": int(VOCAL_COVER_GAP_S[d] * 1000),
                "maxGapMsAfter": coverage_max_gap_ms(d),
                "fromPool": vocal_coverage_stats[d]["fromPool"],
                "synthesized": vocal_coverage_stats[d]["synthesized"],
                "unfilledGaps": vocal_coverage_stats[d]["unfilledGaps"],
                "countsBefore": counts_before[d],
                "countsAfter": after,
                "cap": caps_by_diff[d],
                "capExceeded": after > caps_by_diff[d],
            }
            if after > caps_by_diff[d]:
                print(
                    f"  v6-4 {song_id}/{d}: 被覆補填で総数キャップ超過"
                    f" {after} > {caps_by_diff[d]}（保証優先で許容）"
                )
        print(
            f"  v6-4 {song_id}: vocalCoverage="
            f"{json.dumps(vocal_coverage_report['diffs'], ensure_ascii=False)}"
        )

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

    def to_tuples(diff, final):
        # v6-2: フリックは NK-S006 と同じ [time, lane, 0, "flick"] 形式で出す
        rank_max = {"easy": 0, "normal": 1, "hard": 2}[diff]
        out = []
        for o in final:
            fr = o["src"].get("flick_rank")
            if fr is not None and fr <= rank_max and o["hold_ms"] == 0:
                out.append([o["time_ms"], o["lane"], 0, "flick"])
            elif o["hold_ms"] > 0:
                out.append([o["time_ms"], o["lane"], o["hold_ms"]])
            else:
                out.append([o["time_ms"], o["lane"]])
        return out

    charts = {d: to_tuples(d, finals[d]) for d in finals}
    counts = validate(song_id, charts, raw, duration_ms)
    subdiv = subdivision_positions(ext_beats)
    drift = drift_stats(charts, subdiv, duration_ms)

    def diff_report(diff, final):
        by_time = {}
        for o in final:
            by_time[o["time_ms"]] = by_time.get(o["time_ms"], 0) + 1
        holds = [o for o in final if o["hold_ms"] > 0]
        rank_max = {"easy": 0, "normal": 1, "hard": 2}[diff]
        flicks = [
            o
            for o in final
            if o["hold_ms"] == 0
            and o["src"].get("flick_rank") is not None
            and o["src"]["flick_rank"] <= rank_max
        ]
        return {
            "total": len(final),
            "taps": len(final) - len(holds) - len(flicks),
            "chordPairs": sum(1 for v in by_time.values() if v == 2),
            "holds": len(holds),
            "holdSeconds": round(sum(o["hold_ms"] for o in holds) / 1000, 1),
            "flicks": len(flicks),
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
        "diffs": {d: diff_report(d, finals[d]) for d in finals},
        "lanes": {d: [sum(1 for n in charts[d] if n[1] == l) for l in range(4)] for d in charts},
        "snapped": n_snapped,
        "droppedAfterSnap": n_dropped,
        "patternUnits": unit_plan_count,
        "patternNotes": pattern_notes,
        "drift": drift,
        "fever": fever,
        "v5": v5,
        "layers": phrase_layers,
        "motifReuse": motif_report,
        "motifSimThr": round(motif_sim_thr, 3) if v5 else None,
        "flickPositions": flick_report,
        "flickAnchorStats": anchor_stats,
        "flickPositionsFinal": flick_final_report,
        "flickFlowLog": flow_log,
        "flickShapeStats": shape_stats,
        "vocalCoverage": vocal_coverage_report,
    }
    print(f"{song_id}: BPM={bpm:.2f} -> {int(round(bpm))} counts={counts}")
    print(f"  diffs={json.dumps(rep['diffs'], ensure_ascii=False)} lanes={rep['lanes']}")
    print(f"  patterns(units)={unit_plan_count} patterns(notes)={pattern_notes}")
    print(f"  snapped={n_snapped} droppedAfterSnap={n_dropped} drift={json.dumps(drift, ensure_ascii=False)}")
    if v5:
        print(f"  layers={json.dumps(phrase_layers, ensure_ascii=False)}")
        print(f"  motifReuse={json.dumps(motif_report, ensure_ascii=False)} thr={motif_sim_thr:.3f}")
    return song_json, rep


def main() -> int:
    # v6-4: --lyrics <path> で歌詞タイミングの入力ファイルを差し替えられる
    # （形式は normalize_lyric_intervals 参照。未指定なら曲別メタデータ／
    # 既定ファイル src/game/data/lyrics.json から解決する）
    argv = sys.argv[1:]
    explicit_lyrics = None
    if "--lyrics" in argv:
        lp = Path(argv[argv.index("--lyrics") + 1])
        if not lp.is_absolute():
            lp = ROOT / lp
        explicit_lyrics = json.loads(lp.read_text(encoding="utf-8"))
    out = {}
    report = {}
    with tempfile.TemporaryDirectory() as td:
        for song_id, meta in SONGS.items():
            wav = Path(td) / f"{song_id}.wav"
            to_wav(ROOT / meta["audio"], wav)
            y, sr = librosa.load(str(wav), sr=SR, mono=True)
            song_lyrics = (
                normalize_lyric_intervals(explicit_lyrics, song_id)
                if explicit_lyrics is not None
                else None
            )
            song_json, rep = process_song(song_id, meta, y, sr, lyric_intervals=song_lyrics)
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
