# 道具（TOOLS）

デジタルCDの制作で使う道具の説明です。スクリプト類はこの repo の `tools/` に同梱してあるので、別の環境でもここから用意できます。各道具について「何のためか／用意のしかた／使い方／注意点」をまとめます。

この作業 VM での現行の置き場所は末尾の一覧に併記します（そちらが実物として稼働中）。

## 1. 文字起こし環境（faster-whisper）

- **何のためか**: 歌詞の時刻付けの検証に使う。付けた開始時刻を文字起こし結果と突き合わせて、全体のずれ・字幕の遅れ・字幕の抜けを見つける（手順の正本は `docs/PRODUCTION.md` の「素材まわりの実務メモ」）。
- **用意のしかた**:
  ```bash
  python3 -m venv .asr-venv
  .asr-venv/bin/pip install faster-whisper
  ```
  現行環境の実測構成: Python 3.12.3、faster-whisper 1.2.1（ctranslate2 4.8.4、tokenizers 0.23.3、onnxruntime 1.31.0）。`tools/whisper_words.py` は PyAV（`av`）と numpy も使うので、あわせて入れる: `.asr-venv/bin/pip install av numpy`。
- **モデルの使い分け**:
  - **small**: 単語レベルの照合用（`tools/whisper_words.py` が使う）。単語ごとの開始時刻が要るため。
  - **medium**: フレーズ境界の突合用。付けた時刻を確定する前に、small の結果と medium のフレーズ境界を突き合わせる（片方だけだと全体のずれを見逃す）。
  - 初回実行時はモデルのダウンロードが走る（ネットワークと時間が必要）。一度取得すればキャッシュされる。
- **注意点**:
  - **VAD（音声区間検出）は切るのが前提**。歌ものでは VAD が歌の合間を落として時刻がずれるため、`whisper_words.py` は引数で `novad` を指定して使う。
  - small は非決定的に幻覚（歌っていない語の混入）を起こすことがある。単独で確定せず、必ず medium と突き合わせる。
  - 実行は CPU 前提（現行スクリプトは `device="cpu"`, `compute_type="int8"`）。

## 2. whisper_words.py（単語レベル照合スクリプト）

- **何のためか**: 音源ファイルから単語ごとの開始時刻を取り出し、JSON で標準出力に流す。歌詞の各行の開始時刻を、実際の歌い出しと単語単位で照合するために使う。
- **場所**: `tools/whisper_words.py`（同梱）。
- **使い方**:
  ```bash
  .asr-venv/bin/python tools/whisper_words.py ファイル.mp4:ja:novad [ファイル2.mp4:ja:novad ...]
  ```
  引数は `ファイル:言語:モード` の組を空白区切りで複数渡せる。
  - 言語: `ja`（日本語）など。
  - モード: `novad`（VAD なし。通常はこちら）／`vad`（VAD あり）。
  - 出力: ファイルごとに `WORDSJSON {...}` の行（セグメント開始・終了と、単語の開始時刻・文字数の一覧）が流れ、最後に `ALLDONE` が出る。単語の「文字数」を出しているのは、幻覚や読み違いの切り分けに使うため（歌詞文字列そのものの照合は制作側で行う）。
- **注意点**: モデルは `small` に固定されている。別モデルで回したい場合はスクリプト内の `WhisperModel("small", ...)` を書き換える。

## 3. 依存修復スクリプト群

`npm install` / `npm ci` が環境要因で壊れる（ファイルが 0 バイトになる、版がずれる等）ときに、lockfile どおりの node_modules を復旧するための道具。**通常の環境ではまず普通に `npm ci` を試し、壊れたときだけ使う。**

- **install-v4.sh（全体の復旧・標準）**
  - 使い方: `bash tools/install-v4.sh <repoのパス>`
  - lockfile に載っていて、入っていない／版が違うパッケージだけを、npm キャッシュ内の tarball（integrity でハッシュ検証）から展開して入れ直し、最後に全体を監査する。
  - **判定基準は監査の `bad: 0`**。`bad` が残ったら直っていない。
  - 補助スクリプト `tools/gen-list.cjs`（「版が違うものの一覧」を作る）を内部で使うので、2つは同じ場所に置く。
- **extract-one.cjs（単品の修復）**
  - 使い方: `node tools/extract-one.cjs <pkg>@<ver> <展開先>`
  - 特定の1パッケージだけが壊れている（0 バイト、版ずれ）ときに、npm キャッシュからその版だけを取り出して置き直す。
- **環境に合わせて直す箇所**（同梱版はこの VM の実物のコピーで、パスが環境依存のまま入っている。挙動は変えていない）:
  - `install-v4.sh` 内の `GEN="$HOME/workspace/.nk-test/gen-list.cjs"` と `dl-one.tgz` の置き場所 → 同梱版を使うときは `tools/gen-list.cjs` を指すよう直す。
  - `gen-list.cjs` 内の `CACHE = '/home/hatch/.npm/_cacache'` → 自分の環境の npm キャッシュ（通常は `~/.npm/_cacache`）に直す。
  - `extract-one.cjs` は pacote を `/opt/hatch-image/bin/npm-package/node_modules/pacote` から読み、キャッシュを `/home/hatch/.npm` に固定している → 別環境では pacote のある場所とキャッシュのパスを直す（pacote をローカルに `npm install pacote` して読み替えてもよい）。

## 4. ffmpeg / ffprobe

- **何のためか**: 素材の実測と変換全般。`docs/PRODUCTION.md` の「素材の用意」で使う。
  - ffprobe: 再生時間の実測、音声・字幕ストリームの有無の確認（素材の入力検証）。
  - ffmpeg: 動画から再生用音源の取り出し、動画末尾の音楽終了点でのカット（ロゴのアウトロ除去）、末尾無音の詰め、代表フレームの抽出（曲画像の候補）、音源形式の変換。
- **用意のしかた**: OS のパッケージ等で入れる。現行環境の実測は ffmpeg / ffprobe ともに 8.1.2。
- **注意点**: 尺の表示やカットの位置は、ファイルのメタデータではなく ffprobe の実測と波形・聴感の確認で決める（手順は PRODUCTION.md の実務メモ）。

## 5. gh（GitHub CLI）

- **何のためか**: 公開フローの実行（feature ブランチの PR 作成、CI の確認、squash マージ）。手順の正本は `docs/PRODUCTION.md` の「運用ルール」。
- **用意のしかた**: 公式配布から入れ、対象アカウントで認証する。現行環境の実測は gh 2.102.0。
- **注意点**: コミットの author は `muse <muse@localhost>` にする（運用ルール参照）。`[skip ci]` は付けない。

## この作業 VM での現行の置き場所（実物）

| 道具 | 同梱（正本） | この VM の実物 |
|---|---|---|
| 文字起こし環境 | （手順は本書） | `~/workspace/.asr-venv` |
| whisper_words.py | `tools/whisper_words.py` | `~/workspace/album-nicholas-kiso/whisper_words.py` |
| install-v4.sh / gen-list.cjs | `tools/` | `~/workspace/.nk-test/` |
| extract-one.cjs | `tools/extract-one.cjs` | `~/workspace/.nk-test/extract-one.cjs` |
| ffmpeg / ffprobe | （OS に導入） | 8.1.2 |
| gh | （公式配布から導入） | 2.102.0 |
