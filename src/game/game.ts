// ゲーム画面（Canvas 描画と入力）。判定・スコア計算は src/logic.ts の純関数を使う。
// 元ゲームからの改善:
//  (a) 音源は src/audio.ts が曲ごとに保持するので、再プレイで再デコードしない
//  (b) プレイ中にタブ/画面が隠れたら、演奏を止めてメニューに戻す（裏で進んで大量MISSになるのを防ぐ）
// 演出（粒子・輪・波紋・判定文字）はすべて経過時間ベースで進める（120Hz でも 60Hz と同じ見え方にする）。
import {
  DIFFICULTIES,
  FLICK_MIN_UP_PX,
  FLICK_TIME_LIMIT_MS,
  HOLD_COMPLETE_BONUS,
  HOLD_TICK_SCORE,
  LANE_COLORS,
  HIT_Y_RATIO,
  SPEED_DEFAULT,
  VISUALIZER_FREQ_BARS,
  groupFreqBins,
  advanceHold,
  beginHold,
  clampSpeed,
  comboAppearance,
  comboTier,
  effectiveFallSeconds,
  emptyCounts,
  findFlickHit,
  findHit,
  findKeyboardHit,
  findNearestNote,
  isComboShow,
  LIFE_MAX,
  applyLifeDelta,
  isLifeGameOver,
  lifeZone,
  lyricIndexAt,
  makePlayNotes,
  rankFor,
  accuracy,
  releaseHold,
  repressHold,
  scoreFor,
  sweepMisses,
  tierFx,
  tintColor,
  type ComboAppearance,
  type ComboZoom,
  type Difficulty,
  type HeadJudge,
  type Judge,
  type JudgementCounts,
  type PlayNote,
  type Rank,
} from './logic';
import type { SongEntry } from './charts';
import { COMBO_PATTERNS, COMBO_SHOW_CONFIG, comboPatternDef } from './presentation';
import { audioContext, loadBuffer, musicAnalyser, nowSeconds, playBuffer, recreateAudioContext, resumeAudio, stopCurrent, unlockAudio } from './audio';
import { playCompleteSound, playEmptySound, playFailSound, playFlickSound, playHitSound, playMissSound, startHoldSound, stopAllHoldSounds, stopHoldSound } from './sound';
import { vibrateHit } from './haptics';
import { setData } from '../debug';

export interface GameResult {
  songTitle: string;
  difficulty: Difficulty;
  score: number;
  counts: JudgementCounts;
  maxCombo: number;
  accuracy: number;
  rank: Rank;
  /** オートプレイで演奏したか（true の回はベストスコアに残さない） */
  autoplay: boolean;
  /** ライフが尽きてゲームオーバーになったか（true の回はベストスコアに残さない） */
  failed: boolean;
}

export interface GameCallbacks {
  onFinish(result: GameResult): void;
  /** 中断（確認カードで「メニューに戻る」を選んだ）でメニューに戻るとき */
  onAbort(): void;
  /** 中断の確認カードの開閉（開く=true。閉じるは「つづける」を押したとき） */
  onPause(open: boolean): void;
  /** コンボが30の倍数に達した（コンボ演出の登場）。appearance にパターン・ズーム・big が入る */
  onComboShow(combo: number, appearance: ComboAppearance): void;
  /** 歌詞の現在行が変わった（-1 は歌詞のない区間） */
  onLyric(index: number): void;
}

// 判定ラインの高さは H×0.74 で固定（タッチ位置「上」。logic.ts の HIT_Y_RATIO）。
// Game.hitY() を参照
const READY_SECONDS = 2;
/**
 * 左上の中断ボタン（描画とタップ判定で共有する）。v1.4.9 の上部 UI 見直し
 * （オーナー承認済みのモック）で、「❚❚ 中断」の文字付き横長ボタン（100×38）から
 * ❚❚ アイコンだけの丸ボタン（直径 40px）に変更した。中心は旧ボタンと同じ (30, 29)。
 */
const PAUSE_BTN = { cx: 30, cy: 29, r: 20 };
/** スコアのフォント（描画と、メーターの横幅を決める実測で共有する） */
const SCORE_FONT = 'bold 18px sans-serif';
/** スコアの baseline（上部1行の中心 = PAUSE_BTN.cy に文字が揃う位置） */
const SCORE_BASELINE_Y = 35;
/** 中断確認で「つづける」を押してから演奏が戻るまでの READY の時間（壁時計 ms） */
const RESUME_COUNTDOWN_MS = 1000;
const JUDGE_LABEL: Record<Judge, string> = { perfect: 'PERFECT', great: 'GREAT', good: 'GOOD', miss: 'MISS' };
const JUDGE_COLOR: Record<Judge, string> = { perfect: '#ffd166', great: '#4ecdc4', good: '#9aa8ff', miss: '#ff6b6b' };

/** ライフの帯ごとの色（十分=緑 / 注意=黄 / 危険=赤） */
const LIFE_COLORS: Record<'safe' | 'caution' | 'danger', string> = { safe: '#3ddc84', caution: '#ffd23f', danger: '#ff5252' };
/**
 * ライフメーターの置き場所（座標はステージ内）。v1.4.9 の上部 UI 見直しで、
 * 中断ボタン・スコアと同じ1行（中心 y = PAUSE_BTN.cy）に集約し、背景パネルは撤去した。
 * バーは中断ボタンの右から、右端のスコアの左に収まる幅で引く。
 */
const LIFE_METER = { meterX: 62, meterY: 25, meterH: 8, scoreGap: 10, edgeGap: 14 };

/** コンボ段階ごとのベール（暗幕）の濃さ。段階が上がるほど薄くなり、ジャケットが冴える */
const TIER_VEIL_ALPHA = [0.62, 0.57, 0.52, 0.46, 0.4] as const;

/** コンボ段階ごとの画面の縁の光（tier 0 はなし）。色は TIER_FX の comboColor と揃える */
const TIER_EDGE: ({ rgb: string; alpha: number; width: number } | null)[] = [
  null,
  { rgb: '165,243,252', alpha: 0.3, width: 3 },
  { rgb: '78,205,196', alpha: 0.42, width: 4 },
  { rgb: '255,209,102', alpha: 0.55, width: 5 },
  { rgb: '255,138,216', alpha: 0.7, width: 6 },
];

/** 粒子（ヒットで弾ける） */
interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number;
  life: number;
  c: string;
  size: number;
}
/** 広がる輪（ヒットの衝撃） */
interface Ring {
  x: number;
  y: number;
  age: number;
  life: number;
  maxR: number;
  c: string;
  /** 線の太さの倍率（コンボ tier 連動） */
  widthMul: number;
}
/** ノーツが一瞬膨らんで消える残像 */
interface Pop {
  lane: number;
  age: number;
  life: number;
  c: string;
  /** 最大の拡大率（コンボ tier 連動） */
  maxScale: number;
}
/** タップした場所に出る波紋 */
interface Ripple {
  x: number;
  y: number;
  age: number;
  life: number;
  c: string;
}
/** フリック成功時に上へ飛んで消えるシェブロン（∧） */
interface FlickChev {
  x: number;
  /** 出現位置 (y)。上昇は age から計算する */
  y: number;
  age: number;
  life: number;
}

const RING_LIFE = 0.32;
const POP_LIFE = 0.18;
const RIPPLE_LIFE = 0.38;
const JUDGE_LIFE = 0.55;
/** フリック表示は大きなブロック矢印（↑）だけ（オーナー決定 2026-11-23、確定仕様）:
 * 四角いノーツ本体（レーン色の塗り＋枠＋シェブロン）は描かず、矢印を従来ノーツの
 * 中心位置に置く。塗りはそのレーンの色、縁取りは濃紺。経緯: 案A（濃紺太枠＋水色
 * シェブロン）でも「まだ見にくい」とのオーナー指摘を受け、ノーツの上に矢印を
 * 飛び出させる案のプレビュー（マゼンタ／オレンジ／白）を経て、オーナーの
 * 「四角いのなしで矢印だけならどう？」で矢印だけ案に決まり、塗り＝レーン色・
 * 縁取り＝濃紺で確定した */
/** 矢印の高さ (px) */
const FLICK_ARROW_HEIGHT = 60;
/** 矢印の縁取り色（ほぼ黒に近い紺） */
const FLICK_ARROW_OUTLINE_COLOR = '#0a1030';
/** 矢印の縁取りの太さ (px)。脈動の位相によらず画面上でこの太さに保つ */
const FLICK_ARROW_OUTLINE_WIDTH = 5;
/** 矢印の脈動: 周期（秒）と最大拡縮率（1.0〜この値の間を sin で往復する） */
const FLICK_ARROW_PULSE_PERIOD_SEC = 0.85;
const FLICK_ARROW_PULSE_MAX = 1.15;
/** フリック成功時に飛ぶシェブロンの色（水色。演出は従来どおり） */
const FLICK_CHEVRON_COLOR = '#3fd9ff';

// ---- オーディオビジュアライザー（プレイ画面の下部スペース） ----
// タッチ位置「上」固定で空いた判定ラインの下の領域に、曲の周波数を描く。
// スタイルは周波数バー固定（オーナー決定 2026-11-23。当初は4種を設定で
// 切り替えたが、実機確認を経て固定に変更し、設定は撤去した）。
// 領域は v1.4.21 の描画領域（390×844 基準で x 12..378、y 652..834）を
// 幅・高さとも約 3/4 に縮小し、横は中央寄せ、下端は画面の下端の 6px 上まで
// 下げた（同日のオーナー調整指示）。色味も同指示でさらに抑えてある。
/** 周波数バー: 下端→上端のグラデーション（彩度・明度を落としたティール） */
const VIZ_BAR_BOTTOM = '#26525b';
const VIZ_BAR_TOP = '#4f7a82';
/** 周波数バー本体の不透明度（0..1。v1.4.21 の 215/255 から引き下げ） */
const VIZ_BAR_ALPHA = 165 / 255;
/** 周波数バーの上端キャップの不透明度（0..1。v1.4.21 の 230/255 から引き下げ） */
const VIZ_BAR_CAP_ALPHA = 180 / 255;
/** フリック成功時に飛ぶシェブロンの寿命（秒）と上昇距離 (px) */
const FLICK_CHEV_LIFE = 0.35;
const FLICK_CHEV_RISE_PX = 60;
/** コンボ演出の登場時の紙吹雪の色 */
const CONFETTI_COLORS = ['#ff6b6b', '#ffd166', '#4ecdc4', '#6c8cff', '#ff8ad8', '#ffffff'];
/** コンボ演出の絵の読み込み済み Image（パターンごとに 1 回だけ作る。素材スロットに絵があるパターンだけ） */
const comboBgImages = new Map<string, HTMLImageElement>();
function comboBgImage(pattern: string): HTMLImageElement | undefined {
  const url = comboPatternDef(pattern)?.imageUrl;
  if (!url) return undefined;
  let img = comboBgImages.get(pattern);
  if (!img) {
    img = new Image();
    img.src = url;
    comboBgImages.set(pattern, img);
  }
  return img;
}
/**
 * コンボ演出の背景の不透明度のピーク（通常・big とも 1.0）。
 * 絵はあくまで背景として描かれ、レーン・ノーツ・判定はその後にフル不透明度で
 * 描くので、背景が絵に完全に置き換わってもプレイの視認性は構造的に保たれる
 * （全面カットインのように絵がノーツの上に被る形にはしない）。
 */
const COMBO_BG_PEAK_ALPHA = 1;
/**
 * コンボ演出の背景の上に敷く暗幕の濃さ（ピーク時）。明るい絵では白いレーン線
 * （不透明度 .12）が埋もれるため、表示中だけ最小限の暗幕を入れる。
 * 通常時のベール（.62）よりずっと薄く、背景が置き換わる印象は損なわない。
 * ノーツ・判定枠・判定ラインはこの後に描くので影響を受けない。
 */
const COMBO_BG_VEIL_ALPHA = 0.18;
/**
 * コンボ演出の背景の包絡（秒）: フェードイン → ピークのままキープ → フェードアウト。
 * 入り方は包絡に smoothstep をかけて「ふわっと」させる。
 */
const COMBO_BG_FADE_IN_SEC = 0.9;
const COMBO_BG_FADE_OUT_SEC = 0.8;
/**
 * コンボ演出の背景の滞在時間（秒）。main.ts の COMBO_SHOW_MS / COMBO_SHOW_BIG_MS と合わせる。
 * 通常は 0.9（イン）＋ 約2秒キープ ＋ 0.8（アウト）= 約3.7秒。
 * big はキープを長くして約4.4秒。
 */
const COMBO_BG_DURATION_SEC = 3.7;
const COMBO_BG_DURATION_BIG_SEC = 4.4;
/** 0→1 を両端でなだらかにする（ふわっとしたフェードの包絡用） */
const smoothstep = (x: number): number => {
  const c = Math.min(1, Math.max(0, x));
  return c * c * (3 - 2 * c);
};
/**
 * 背景の中での push-in（奥から近づくズーム）。種別ごとに寄る速さと幅を変える。
 * power は ease-out の強さ（大きいほど最初に速く寄る）。背景なので行き過ぎや揺れは入れない。
 */
const COMBO_BG_ZOOM: Record<ComboZoom, { from: number; to: number; power: number }> = {
  standard: { from: 0.92, to: 1.06, power: 2 },
  fast: { from: 0.9, to: 1.08, power: 3 },
  cinematic: { from: 0.96, to: 1.03, power: 1 },
};
/** 粒子の総数の上限（iPhone で 60fps を保つため。死んだ粒子はプールで再利用する） */
const MAX_PARTICLES = 300;

export class Game {
  private canvas: HTMLCanvasElement;
  private g: CanvasRenderingContext2D;
  /** ノーツ専用キャンバス（歌詞 DOM より手前に重ねるため分離。オーナー指示 2026-11-20:
   *  音符は歌詞より上に表示する。背景・ジャケット・レーン・判定枠は本体キャンバス側） */
  private notesCanvas: HTMLCanvasElement;
  private gn: CanvasRenderingContext2D;
  private cb: GameCallbacks;
  private raf = 0;
  private playing = false;
  private destroyed = false;
  /**
   * 中断確認で凍結中か（オーナー指示 2026-11-21、案1）。凍結中は音を止めて位置を
   * 覚えておき、再開時にその位置から鳴らし直す。phase は確認カード表示中が
   * 'confirm'、「つづける」後の READY 中が 'countdown'
   */
  private paused = false;
  private pausePhase: 'confirm' | 'countdown' = 'confirm';
  /** 凍結した時点の曲位置（秒。READY 中は負） */
  private pausePosSec = 0;
  /** 'countdown' が終わる壁時計時刻（ms） */
  private resumeDueWall = 0;
  /** 再開の鳴らし直しに使う、読み込み済みの曲バッファ */
  private songBuf: AudioBuffer | null = null;
  /**
   * start() の世代番号。中断（abort）や再スタートのたびに進める。
   * start() は await をまたぐため、合間にバックグラウンドへ回って中断されても、
   * 古い start() が後から演奏を始めてしまわないようにする（v1.9.1）。
   */
  private startSession = 0;
  /** 前面にいるのに AudioContext が止まっていたときの、resume 再試行の間引き（壁時計 ms） */
  private lastResumeTryWall = 0;

  private entry: SongEntry | null = null;
  private difficulty: Difficulty = 'easy';
  /** start で受け取った判定オフセット（中断確認の「はじめからやりなおす」で同じ条件で開始し直すため保持する） */
  private offsetMs = 0;
  /** オートプレイ中か（設定のデバッグモード配下。start で受け取る） */
  private autoplay = false;
  private notes: PlayNote[] = [];
  private counts: JudgementCounts = emptyCounts();
  /** ライフ（0〜LIFE_MAX）。判定の発生順に増減するので counts からは再計算しない */
  private life = LIFE_MAX;
  private score = 0;
  private combo = 0;
  private maxCombo = 0;
  /** コンボ演出の登場回数（パターンのローテーションに使う。演奏ごとに数え直す） */
  private comboShowCount = 0;
  /** 表示中のコンボ演出の背景（絵・ズーム・big と、出した時刻＝AudioContext 時刻） */
  private comboBg: { pattern: string; zoom: ComboZoom; big: boolean; shownAt: number } | null = null;
  /** 端末の「視差効果を減らす」設定（背景のズームを止めるかの判定に使う） */
  private reducedMotion = false;
  private startAt = 0; // AudioContext 時刻（秒）
  /** 音声時計の凍結検知用: 最後に時計が進んだときの値と、その壁時計時刻 */
  private clockSeenAt = 0;
  private clockAdvanceWall = 0;
  private audioFrozen = false;
  /** READY 中の凍結で開始を初期化し直したか（1回の開始につき1回まで）と、その実行中フラグ */
  private readyReinitUsed = false;
  private reiniting = false;
  private durationSec = 0;
  private bg: HTMLImageElement | null = null;
  private flash = [0, 0, 0, 0];
  /** コンボ段階（tier）の画面演出用: 前フレームの tier と、上がった瞬間のフラッシュ量 */
  private lastTier = 0;
  private tierFlash = 0;
  private particles: Particle[] = [];
  private particlePool: Particle[] = [];
  private rings: Ring[] = [];
  private pops: Pop[] = [];
  private ripples: Ripple[] = [];
  private flickChevs: FlickChev[] = [];
  private judgeText = '';
  private judgeColor = '#fff';
  private judgeTier = 0; // 判定文字を出した時点のコンボ tier（大きさ・色に使う）
  private judgeShownAt = -Infinity; // AudioContext 時刻（秒）
  private lyricIndex = -2; // 現在の歌詞行（-2 は未送信。-1 は歌詞のない区間）
  private lastFrameAt = 0; // 前フレームの AudioContext 時刻（秒）。dt の計算用
  private width = 0;
  private height = 0;
  /** 押さえ中のポインタ（pointerId → レーン）。マルチタッチで長押ししながら他レーンを叩ける */
  private pointerLanes = new Map<number, number>();
  /** フリック検出用の、ポインタごとの押し始めの記録（位置・壁時計・発火済みか） */
  private pointerGestures = new Map<number, { startY: number; startWall: number; flicked: boolean }>();
  /** 音符の落下速度の倍率（プレイヤー設定。start で受け取る） */
  private speed = SPEED_DEFAULT;
  /** 判定ラインの y 座標（px）。タッチ位置「上」固定（H×0.74） */
  private hitY(): number {
    return this.height * HIT_Y_RATIO;
  }
  // ビジュアライザーの解析データの使い回しバッファと、取得の間引きカウンタ
  // （2フレームに1回だけ取る）
  private vizFreq: Uint8Array<ArrayBuffer> | null = null;
  private vizFrame = 0;
  /** 押さえ中のキー（レーン） */
  private keyLanes = new Set<number>();
  private holdsCompleted = 0;
  private holdsFailed = 0;

  private laneAt(px: number): number {
    return Math.min(3, Math.max(0, Math.floor(px / (this.width / 4))));
  }

  private onPointerDown = (e: PointerEvent): void => {
    e.preventDefault();
    if (!this.playing || this.paused) return;
    const rect = this.canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    // 中断ボタンは丸ボタン: 中心からの距離が半径以内なら当たったことにする
    const pdx = px - PAUSE_BTN.cx;
    const pdy = py - PAUSE_BTN.cy;
    if (pdx * pdx + pdy * pdy <= PAUSE_BTN.r * PAUSE_BTN.r) {
      this.pause();
      return;
    }
    // オートプレイ中はタップ入力を受け付けない（左上の中断だけ従来どおり効く）
    if (this.autoplay) return;
    const lane = this.laneAt(px);
    this.pointerLanes.set(e.pointerId, lane);
    this.pointerGestures.set(e.pointerId, { startY: py, startWall: performance.now(), flicked: false });
    try {
      this.canvas.setPointerCapture(e.pointerId);
    } catch {
      // キャプチャできなくてもプレイは続行する
    }
    this.pressLane(lane, px, py);
  };

  private onPointerMove = (e: PointerEvent): void => {
    if (!this.playing) return;
    const prev = this.pointerLanes.get(e.pointerId);
    if (prev === undefined) return;
    const rect = this.canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    // フリック検出: 押し始めから短時間に、上へ大きく動いたらフリックとして発火する
    // （ポインタごとに1回まで）。縦の動きは基本は同じレーン内で起きる
    const gesture = this.pointerGestures.get(e.pointerId);
    if (
      gesture &&
      !gesture.flicked &&
      !this.paused &&
      gesture.startY - py >= FLICK_MIN_UP_PX &&
      performance.now() - gesture.startWall <= FLICK_TIME_LIMIT_MS
    ) {
      gesture.flicked = true;
      this.flickLane(prev, px, py);
      return;
    }
    const lane = this.laneAt(px);
    if (lane === prev) return;
    // 指がレーンをまたいだら、旧レーンは離した扱い、新レーンは押した扱いにする
    this.pointerLanes.set(e.pointerId, lane);
    this.releaseLane(prev);
    this.pressLane(lane, px, py);
  };

  private onPointerUp = (e: PointerEvent): void => {
    const lane = this.pointerLanes.get(e.pointerId);
    this.pointerGestures.delete(e.pointerId);
    if (lane === undefined) return;
    this.pointerLanes.delete(e.pointerId);
    if (this.playing) this.releaseLane(lane);
  };

  private onLostPointerCapture = (e: PointerEvent): void => {
    // ポインタ捕捉が強制的に外れたとき（バックグラウンド遷移など）は、
    // pointerup が来ないことがある。捕捉を失った時点で「離した」扱いにする
    const lane = this.pointerLanes.get(e.pointerId);
    this.pointerGestures.delete(e.pointerId);
    if (lane === undefined) return;
    this.pointerLanes.delete(e.pointerId);
    if (this.playing) this.releaseLane(lane);
  };

  private onKeyDown = (e: KeyboardEvent): void => {
    if (e.key === 'Escape' && this.playing && !this.paused) {
      this.pause();
      return;
    }
    if (!this.playing || this.paused || e.repeat || this.autoplay) return;
    const lane = 'dfjk'.indexOf(e.key.toLowerCase());
    if (lane < 0) return;
    this.keyLanes.add(lane);
    this.pressLane(lane, undefined, undefined, true);
  };

  private onKeyUp = (e: KeyboardEvent): void => {
    const lane = 'dfjk'.indexOf(e.key.toLowerCase());
    if (lane < 0) return;
    this.keyLanes.delete(lane);
    if (this.playing) this.releaseLane(lane);
  };

  private onVisibility = (): void => {
    if (document.visibilityState === 'hidden') {
      // プレイ中に画面が隠れたら、演奏を凍結して中断確認を出しておく（オーナー指示
      // 2026-11-21、案1。旧仕様はその場で中断してメニューへ戻していた）。戻ってきたら
      // カードが開いたままなので、「つづける」で止めた位置から再開できる。
      // pause() の中で押下状態もリセットする: 裏にいる間に pointerup / keyup を
      // 取りこぼすと、押されたままの状態が残り復帰後にタッチが効かないように
      // 見える（v1.9.1 の不具合対応）
      this.pause();
    } else {
      // 前面に戻ったら、止まっている AudioContext を起こす。ゲームの時計は
      // AudioContext 基準なので、止まったままだと READY 表示のまま凍って見える
      void resumeAudio();
    }
  };

  private onPageHide = (): void => {
    // 画面ロックなど、visibilitychange が届かない経路でも演奏を凍結する
    this.pause();
  };

  private onBlur = (): void => {
    // フォーカスを失ったら押下状態だけリセットする（演奏の中断は visibility / pagehide に任せる）
    this.resetInput();
  };

  private onFocus = (): void => {
    // 復帰時に AudioContext の resume を確実に行う
    void resumeAudio();
  };

  /**
   * 押下状態（ポインタ・キー）をすべてリセットする。バックグラウンド遷移や
   * フォーカス喪失で pointerup / keyup を取りこぼしたときに、押されたままの
   * 状態が残って入力が固まったように見えるのを防ぐ。
   * 保持中の長押しは「離した」扱いにして猶予（grace）へ移すので、
   * リセット自体でいきなり失敗にはならない（中断が続けば、そのまま演奏ごと終わる）。
   */
  private resetInput(): void {
    this.pointerLanes.clear();
    this.pointerGestures.clear();
    this.keyLanes.clear();
    if (!this.playing) return;
    const nowMs = (nowSeconds() - this.startAt) * 1000;
    for (const n of this.notes) {
      if (n.holdPhase === 'holding') {
        releaseHold(n, nowMs);
        stopHoldSound(n);
      }
    }
  }

  constructor(canvas: HTMLCanvasElement, notesCanvas: HTMLCanvasElement, cb: GameCallbacks) {
    this.canvas = canvas;
    const g = canvas.getContext('2d');
    if (!g) throw new Error('Canvas が使えません');
    this.g = g;
    this.notesCanvas = notesCanvas;
    const gn = notesCanvas.getContext('2d');
    if (!gn) throw new Error('Canvas が使えません');
    this.gn = gn;
    this.cb = cb;
    canvas.addEventListener('pointerdown', this.onPointerDown);
    canvas.addEventListener('pointermove', this.onPointerMove);
    canvas.addEventListener('pointerup', this.onPointerUp);
    canvas.addEventListener('pointercancel', this.onPointerUp);
    canvas.addEventListener('lostpointercapture', this.onLostPointerCapture);
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
    document.addEventListener('visibilitychange', this.onVisibility);
    window.addEventListener('pagehide', this.onPageHide);
    window.addEventListener('blur', this.onBlur);
    window.addEventListener('focus', this.onFocus);
    // コンボ演出の絵は、初回の登場で読み込み待ちにならないよう先読みしておく
    for (const def of COMBO_PATTERNS) if (def.imageUrl) comboBgImage(def.id);
  }

  destroy(): void {
    this.destroyed = true;
    this.playing = false;
    cancelAnimationFrame(this.raf);
    stopCurrent();
    stopAllHoldSounds();
    this.canvas.removeEventListener('pointerdown', this.onPointerDown);
    this.canvas.removeEventListener('pointermove', this.onPointerMove);
    this.canvas.removeEventListener('pointerup', this.onPointerUp);
    this.canvas.removeEventListener('pointercancel', this.onPointerUp);
    this.canvas.removeEventListener('lostpointercapture', this.onLostPointerCapture);
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    document.removeEventListener('visibilitychange', this.onVisibility);
    window.removeEventListener('pagehide', this.onPageHide);
    window.removeEventListener('blur', this.onBlur);
    window.removeEventListener('focus', this.onFocus);
  }

  get isPlaying(): boolean {
    return this.playing;
  }

  /** 今の演奏がオートプレイか */
  get isAutoplay(): boolean {
    return this.autoplay;
  }

  /** テスト用の入口向け: 現在のライフ（0〜LIFE_MAX） */
  get lifeValue(): number {
    return this.life;
  }

  /** テスト用の入口向け: 曲の現在位置（ms。READY 中は負、演奏中でなければ -1） */
  songPositionMs(): number {
    if (!this.playing) return -1;
    if (this.paused) return this.pausePosSec * 1000;
    return (nowSeconds() - this.startAt) * 1000;
  }

  /** 曲を読み込んで演奏を始める。読み込み済みなら即座に始まる。autoplay は設定のデバッグモード配下のオートプレイ。speed は音符の落下速度の倍率（プレイヤー設定） */
  async start(
    entry: SongEntry,
    difficulty: Difficulty,
    offsetMs: number,
    autoplay = false,
    speed = SPEED_DEFAULT,
  ): Promise<void> {
    // スタート操作のジェスチャの中で呼ばれる前提で、まず音声を unlock する
    unlockAudio();
    const session = ++this.startSession;
    // 前の演奏の最終フレーム（前の曲のジャケット背景）が、音の読み込み中に
    // そのまま見えてしまうのを防ぐ。ゲーム画面への切替と同じ同期処理の中で
    // 両キャンバスを地の色へ戻し、背景の参照も外しておく（オーナー指摘
    // 2026-11-21: リズムゲーム開始直後に前の曲の背景が一瞬残る）
    this.bg = null;
    this.clearCanvases();
    // 歌詞表示（DOM）も前の曲のものが残るため、読み込み前に「歌詞なし」を通知して
    // 消しておく（オーナー指摘 2026-11-21: 背景は消えたが歌詞が残っていた）
    this.cb.onLyric(-1);
    const buf = await loadBuffer(entry.audioUrl);
    if (this.destroyed || session !== this.startSession) return;
    this.songBuf = buf;
    this.paused = false;
    this.entry = entry;
    this.difficulty = difficulty;
    this.offsetMs = offsetMs;
    this.autoplay = autoplay;
    this.speed = clampSpeed(speed);
    setData('autoplay', autoplay ? 'on' : 'off');
    this.notes = makePlayNotes(entry.data.charts[difficulty], offsetMs);
    this.counts = emptyCounts();
    this.life = LIFE_MAX;
    this.score = 0;
    this.combo = 0;
    this.maxCombo = 0;
    this.comboShowCount = 0;
    this.comboBg = null;
    this.particles = [];
    this.rings = [];
    this.pops = [];
    this.ripples = [];
    this.flickChevs = [];
    this.flash = [0, 0, 0, 0];
    this.pointerLanes.clear();
    this.pointerGestures.clear();
    this.keyLanes.clear();
    stopAllHoldSounds();
    this.holdsCompleted = 0;
    this.holdsFailed = 0;
    setData('holdsCompleted', 0);
    setData('holdsFailed', 0);
    setData('combo', 0);
    setData('comboTier', 0);
    this.lastTier = 0;
    this.tierFlash = 0;
    this.judgeText = '';
    this.judgeTier = 0;
    this.judgeShownAt = -Infinity;
    this.lyricIndex = -2;
    setData('comboShow', 0);
    setData('lyricIndex', -1);
    this.durationSec = buf.duration;
    this.bg = new Image();
    this.bg.src = entry.jacketUrl;
    // 再生開始の直前にもう一度 resume する（suspended のままだと currentTime が進まず、
    // その場合は復帰した時点でスケジュールどおり鳴り始める）
    await resumeAudio();
    if (this.destroyed) return;
    if (session !== this.startSession || document.visibilityState === 'hidden') {
      // 読み込みの合間にバックグラウンドへ回って中断されていた（または今も裏にいる）。
      // このまま演奏を始めると、止まった時計のまま READY で凍ったように見えるので、
      // 演奏は作らずメニューへ戻す（v1.9.1 の不具合対応）
      setData('game', 'menu');
      this.cb.onAbort();
      return;
    }
    // バックグラウンド復帰などで AudioContext が壊れたまま（resume しても running に
    // 戻らない）ことがある。その状態で始めると時計が凍って READY のまま固まるため、
    // 開始の時点で作り直しておく（2026-11-20 実機で「背景に戻して再スタートすると
    // 毎回固まる」と再現性のある報告）
    if (audioContext().state !== 'running') {
      recreateAudioContext();
      unlockAudio();
    }
    this.startAt = nowSeconds() + READY_SECONDS;
    this.lastFrameAt = nowSeconds();
    this.clockSeenAt = nowSeconds();
    this.clockAdvanceWall = performance.now();
    this.audioFrozen = false;
    this.readyReinitUsed = false;
    setData('audioFrozen', 'off');
    playBuffer(buf, this.startAt);
    this.playing = true;
    setData('game', 'playing');
    setData('score', 0);
    cancelAnimationFrame(this.raf);
    this.raf = requestAnimationFrame(this.loop);
  }

  /**
   * READY 中に音声時計が凍ったときの、開始の初期化し直し。AudioContext を
   * 作り直し、READY の残り時間を新しい時計へ引き継いで曲の開始を予約し直す。
   * 曲はまだ始まっていないので、続きからの再開ではなく開始のやり直しになる。
   * 作り直した context がまだ止まっている場合は、次のタップ（pressLane の
   * unlock）で動き出す。それでも直らなければ凍結検知がメニューへ戻す。
   */
  private async reinitStart(): Promise<void> {
    if (this.reiniting || !this.playing || !this.entry) return;
    this.reiniting = true;
    this.readyReinitUsed = true;
    const session = this.startSession;
    try {
      const remaining = Math.max(0, this.startAt - nowSeconds());
      recreateAudioContext();
      unlockAudio();
      const buf = await loadBuffer(this.entry.audioUrl);
      if (this.destroyed || !this.playing || session !== this.startSession) return;
      const now = nowSeconds();
      this.startAt = now + remaining;
      playBuffer(buf, this.startAt, 0);
      this.lastFrameAt = now;
      this.clockSeenAt = now;
      this.clockAdvanceWall = performance.now();
    } catch {
      // 直らなければ次の凍結検知でメニューへ戻す
    } finally {
      this.reiniting = false;
    }
  }

  /** 両キャンバスを地の色に戻す（start の冒頭で、前の演奏の残像を消すため）。
   * 変換行列を外して実ピクセル全面を塗る: CSS 単位で塗ると、端数で右端・下端の
   * 1ピクセルに前のフレームが残ることがあるため */
  private clearCanvases(): void {
    const { g, gn } = this;
    g.save();
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.fillStyle = '#0e1018';
    g.fillRect(0, 0, this.canvas.width, this.canvas.height);
    g.restore();
    gn.save();
    gn.setTransform(1, 0, 0, 1, 0, 0);
    gn.clearRect(0, 0, this.notesCanvas.width, this.notesCanvas.height);
    gn.restore();
  }

  /** 演奏を止めてメニューに戻る（結果は残さない） */
  abort(): void {
    // 進行中の start() があれば取り消す（await の合間に中断されても、
    // 後から演奏が始まってしまわないように。演奏中でなければ世代を進めるだけ）
    this.startSession++;
    if (!this.playing) return;
    this.playing = false;
    this.paused = false;
    cancelAnimationFrame(this.raf);
    stopCurrent();
    stopAllHoldSounds();
    this.audioFrozen = false;
    setData('audioFrozen', 'off');
    setData('game', 'menu');
    this.cb.onAbort();
  }

  /**
   * 演奏を凍結して中断の確認カードを出す（オーナー指示 2026-11-21、案1）。
   * 音はその場で止め、曲位置を覚えておく。再開は resume() → READY をはさんで
   * finishResume() が止めた位置から鳴らし直す（READY 中の初期化し直しと同じ流儀）。
   * 中断ボタン・端スワイプの「戻る」・アプリ切替のどれからも、ここへ統一する
   */
  pause(): void {
    if (!this.playing || this.paused) return;
    this.pausePosSec = nowSeconds() - this.startAt;
    this.resetInput();
    stopCurrent();
    stopAllHoldSounds();
    this.paused = true;
    this.pausePhase = 'confirm';
    setData('game', 'paused');
    this.cb.onPause(true);
  }

  /**
   * 確認カードの「はじめからやりなおす」（オーナー指示 2026-11-22）。確認は挟まず、
   * カードを閉じて同じ曲・難易度・設定（オフセット／オートプレイ／速度）の
   * まま start し直す。スコア・コンボ・ライフ・判定カウントは start 側でリセットされ、
   * 曲は頭から鳴る
   */
  restart(): void {
    if (!this.playing || !this.paused || this.pausePhase !== 'confirm' || !this.entry) return;
    const entry = this.entry;
    this.cb.onPause(false);
    void this.start(entry, this.difficulty, this.offsetMs, this.autoplay, this.speed);
  }

  /** 確認カードの「つづける」。カードを閉じ、READY（1秒）をはさんで再開する */
  resume(): void {
    if (!this.playing || !this.paused || this.pausePhase !== 'confirm') return;
    this.pausePhase = 'countdown';
    this.resumeDueWall = performance.now() + RESUME_COUNTDOWN_MS;
    this.cb.onPause(false);
  }

  /** READY が明けたら、凍結した位置から曲を鳴らし直して時計を引き継ぐ */
  private finishResume(): void {
    const buf = this.songBuf;
    if (!buf || !this.entry) {
      this.abort();
      return;
    }
    const now = nowSeconds();
    const pos = this.pausePosSec;
    this.startAt = now - pos;
    playBuffer(buf, Math.max(now, this.startAt), Math.max(0, pos));
    this.lastFrameAt = now;
    this.clockSeenAt = now;
    this.clockAdvanceWall = performance.now();
    this.audioFrozen = false;
    setData('audioFrozen', 'off');
    this.paused = false;
    setData('game', 'playing');
  }

  /** 中断確認で凍結中か */
  get isPaused(): boolean {
    return this.paused;
  }

  /** デバッグ用: いまの成績で結果画面へ進む */
  finishNow(): void {
    if (this.playing && !this.paused) this.finish();
  }

  /** レーンが今も押されているか（ポインタ・キーのどちらか） */
  private lanePressed(lane: number): boolean {
    if (this.keyLanes.has(lane)) return true;
    for (const l of this.pointerLanes.values()) if (l === lane) return true;
    return false;
  }

  /** レーンを叩いたときの共通の見た目（フラッシュ＋波紋）。タップとフリックで共用する */
  private laneTapFx(lane: number, rippleX?: number, rippleY?: number): void {
    this.flash[lane] = 1;
    // 押した場所に波紋を出す（キーボードのときはレーンの判定ライン中央）
    const lw = this.width / 4;
    this.ripples.push({
      x: rippleX ?? lane * lw + lw / 2,
      y: rippleY ?? this.hitY(),
      age: 0,
      life: RIPPLE_LIFE,
      c: LANE_COLORS[lane],
    });
    if (this.ripples.length > 24) this.ripples.shift();
  }

  private pressLane(lane: number, rippleX?: number, rippleY?: number, viaKeyboard = false): void {
    // 保険: 再生中に AudioContext が止まっていたら（iOS の interrupted など）、タップのついでに戻す。
    // resume だけでは戻らないことがあるため、ジェスチャの中で効く強い unlock（resume＋
    // 音声セッション再設定＋無音バッファ）を使う（2026-11-20 実機で「READY のまま
    // タッチできない」症状が出たための強化）
    if (audioContext().state !== 'running' || this.audioFrozen) unlockAudio();
    this.laneTapFx(lane, rippleX, rippleY);
    const nowMs = (nowSeconds() - this.startAt) * 1000;
    // 猶予（grace）中の長押しがあれば、新しいノーツより先に押し直しとして扱う
    for (const n of this.notes) {
      if (n.lane === lane && n.holdPhase === 'grace' && repressHold(n, nowMs)) {
        // 連打を再開する（ピッチの上がり具合は経過分の progress で引き継ぐ）
        const progress = Math.min(1, Math.max(0, (nowMs - n.timeMs) / Math.max(1, n.holdMs)));
        startHoldSound(n, comboTier(this.combo), n.timeMs + n.holdMs - nowMs, progress, this.entry?.data.bpm ?? 120);
        return;
      }
    }
    // いちばん近い未判定ノーツがフリックノーツなら、この押しはフリック操作の
    // 始まりとして扱い、タップ判定も空振り音も出さない（フリック必須。
    // 指を離すだけでは取れず、窓を過ぎれば通常のミスになる）。
    // キーボードだけは例外: フリックのジェスチャが無いので、フリックノーツも
    // 通常のタップと同じキー押しでそのまま取る（オーナー指示 2026-11-22）
    if (!viaKeyboard && findNearestNote(this.notes, lane, nowMs)?.flick) return;
    const hit = viaKeyboard ? findKeyboardHit(this.notes, lane, nowMs) : findHit(this.notes, lane, nowMs);
    if (!hit) {
      // ノーツのないレーンを押したときも、ヒット音とは別の小さな音で「触れた」ことを返す
      playEmptySound();
      return;
    }
    this.hitNote(hit.note, hit.judge, nowMs);
  }

  /** フリック入力: フリックノーツ優先、無ければ通常のタップノーツを取る（findFlickHit） */
  private flickLane(lane: number, rippleX?: number, rippleY?: number): void {
    if (audioContext().state !== 'running' || this.audioFrozen) unlockAudio();
    this.laneTapFx(lane, rippleX, rippleY);
    const nowMs = (nowSeconds() - this.startAt) * 1000;
    const hit = findFlickHit(this.notes, lane, nowMs);
    if (!hit) {
      playEmptySound();
      return;
    }
    this.hitNote(hit.note, hit.judge, nowMs);
  }

  /** ノーツ1つをヒットとして処理する（タップ入力とオートプレイで共用）。スコア・コンボ・演出・音まで通常タップと同じ */
  private hitNote(note: PlayNote, judge: HeadJudge, nowMs: number): void {
    note.state = 1;
    const lane = note.lane;
    this.score += scoreFor(judge);
    this.combo++;
    this.maxCombo = Math.max(this.maxCombo, this.combo);
    // コンボ tier で演出とヒット音が派手になる
    const tier = comboTier(this.combo);
    this.showJudge(judge, tier);
    const level: 0 | 1 | 2 = judge === 'perfect' ? 0 : judge === 'great' ? 1 : 2;
    this.burst(lane, level, tier);
    if (note.flick) {
      // フリックノーツは専用の音と演出にする（通常ノーツをフリックで叩いた
      // 場合は note.flick が false なので、従来のタップ音・演出のまま）
      playFlickSound(judge, tier);
      this.flickBurst(lane, level, tier);
    } else {
      playHitSound(judge, tier);
    }
    vibrateHit(judge);
    this.syncCombo();
    if (isComboShow(this.combo)) this.triggerComboShow(this.combo);
    if (note.holdMs > 0) {
      // 長押し: 集計（PERFECT等への加算）は押し切ったときに頭の判定で行う。コンボは頭で増やす
      beginHold(note, judge, 60000 / (this.entry?.data.bpm ?? 120));
      // ヒット音の連打を頭のヒットと同時に鳴らし始める（間隔は曲の BPM の16分音符）
      const progress = Math.min(1, Math.max(0, (nowMs - note.timeMs) / Math.max(1, note.holdMs)));
      startHoldSound(note, tier, note.timeMs + note.holdMs - nowMs, progress, this.entry?.data.bpm ?? 120);
    } else {
      this.counts[judge]++;
      this.life = applyLifeDelta(this.life, judge);
    }
    setData('score', this.score);
    // ライフが尽きたらゲームオーバー
    this.checkGameOver();
  }

  /**
   * オートプレイ: 時刻の来たノーツを PERFECT で自動処理する。
   * 長押しは頭を押したまま（離す処理が入らない）ので、advanceHold が尾で完走させる。
   * レーンのフラッシュと波紋も出して、通常タップと同じ見た目にする。
   */
  private autoPlay(nowMs: number): void {
    const lw = this.width / 4;
    for (const n of this.notes) {
      if (n.timeMs - nowMs > 0) break;
      if (n.state !== 0) continue;
      this.flash[n.lane] = 1;
      this.ripples.push({
        x: n.lane * lw + lw / 2,
        y: this.hitY(),
        age: 0,
        life: RIPPLE_LIFE,
        c: LANE_COLORS[n.lane],
      });
      if (this.ripples.length > 24) this.ripples.shift();
      this.hitNote(n, 'perfect', nowMs);
    }
  }

  /** レーンを離した。まだ他の入力で押されていなければ、長押しを猶予に入れる */
  private releaseLane(lane: number): void {
    if (this.lanePressed(lane)) return;
    const nowMs = (nowSeconds() - this.startAt) * 1000;
    for (const n of this.notes) {
      if (n.lane === lane && n.holdPhase === 'holding') {
        releaseHold(n, nowMs);
        // 離したら連打は即座に止める（押し直せば再開する）
        stopHoldSound(n);
      }
    }
  }

  private showJudge(judge: Judge, tier = 0): void {
    this.judgeText = JUDGE_LABEL[judge];
    this.judgeTier = tier;
    // tier が高いほど判定文字の色を金色寄りに寄せる（MISS はそのまま）
    this.judgeColor =
      judge === 'miss' ? JUDGE_COLOR.miss : tintColor(JUDGE_COLOR[judge], '#ffedb0', tierFx(tier).judgeTint);
    this.judgeShownAt = nowSeconds();
  }

  /**
   * コンボ演出の登場（30コンボごと）。パターンとズームは logic の comboAppearance が、
   * 素材スロット（presentation.ts）の設定を受けて決める。パターンが未設定
   * （素材スロットが空）なら、演出自体を出さない。
   * 絵は Canvas の背景として敷き（描画は loop 側。ピーク不透明度 1.0 で
   * 背景が完全に置き換わる）、紙吹雪も Canvas 側で画面中央から出す。
   * セリフの表示だけ main.ts 側（onComboShow）に任せる。
   */
  private triggerComboShow(combo: number): void {
    const appearance = comboAppearance(combo, this.comboShowCount, COMBO_SHOW_CONFIG);
    if (!appearance) return;
    this.comboShowCount++;
    setData('comboShow', combo);
    setData('comboPattern', appearance.pattern);
    setData('comboZoom', appearance.zoom);
    this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.comboBg = { pattern: appearance.pattern, zoom: appearance.zoom, big: appearance.big, shownAt: nowSeconds() };
    // 初回の登場で読み込み待ちにならないよう、絵はここでも先読みしておく
    comboBgImage(appearance.pattern);
    const big = appearance.big;
    const n = big ? 70 : 26;
    for (let i = 0; i < n; i++) {
      const an = Math.random() * Math.PI * 2; // 中央から全方向へ
      const sp = 140 + Math.random() * (big ? 380 : 260);
      this.spawnParticle(
        this.width / 2,
        this.height * 0.42,
        Math.cos(an) * sp,
        Math.sin(an) * sp,
        0.7 + Math.random() * 0.5,
        CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        5,
      );
    }
    this.cb.onComboShow(combo, appearance);
  }

  /** コンボと tier をテスト用の入口（data 属性）へ出す */
  private syncCombo(): void {
    setData('combo', this.combo);
    setData('comboTier', comboTier(this.combo));
  }

  /** テスト/撮影用: コンボ数を直接セットする（30の倍数ならコンボ演出も登場する） */
  debugSetCombo(n: number): void {
    this.combo = Math.max(0, Math.floor(n));
    this.maxCombo = Math.max(this.maxCombo, this.combo);
    this.syncCombo();
    if (isComboShow(this.combo)) this.triggerComboShow(this.combo);
  }

  /** 粒子を1つ出す。上限に達していたら出さない。死んだ粒子はプールから再利用する */
  private spawnParticle(x: number, y: number, vx: number, vy: number, life: number, c: string, size: number): void {
    if (this.particles.length >= MAX_PARTICLES) return;
    const p = this.particlePool.pop() ?? { x: 0, y: 0, vx: 0, vy: 0, age: 0, life: 0, c: '', size: 4 };
    p.x = x;
    p.y = y;
    p.vx = vx;
    p.vy = vy;
    p.age = 0;
    p.life = life;
    p.c = c;
    p.size = size;
    this.particles.push(p);
  }

  /** ヒット演出: ノーツの膨らむ残像＋広がる輪＋粒子。コンボ tier が高いほど派手 */
  private burst(lane: number, level: 0 | 1 | 2, tier: number): void {
    const fx = tierFx(tier);
    const lw = this.width / 4;
    const cx = lane * lw + lw / 2;
    const cy = this.hitY();
    const c = LANE_COLORS[lane];
    this.pops.push({ lane, age: 0, life: POP_LIFE, c, maxScale: 1.5 * fx.popMul });
    this.rings.push({
      x: cx,
      y: cy,
      age: 0,
      life: RING_LIFE,
      maxR: 46 * fx.ringMul,
      c,
      widthMul: fx.ringWidthMul,
    });
    if (this.rings.length > 24) this.rings.shift();
    const n = Math.round((level === 0 ? 22 : level === 1 ? 14 : 8) * fx.particleMul);
    for (let i = 0; i < n; i++) {
      const an = Math.random() * Math.PI * 2;
      const sp = (140 + Math.random() * (level === 0 ? 380 : 260)) * (0.9 + 0.1 * tier);
      this.spawnParticle(cx, cy, Math.cos(an) * sp, Math.sin(an) * sp - 70, 0.35 + Math.random() * 0.2, c, fx.particleSize);
    }
  }

  /**
   * フリック成功時だけの追加演出（burst の残像・輪・粒子に重ねる）:
   * 上方向へ噴き上がる粒子と、上へ飛んで消えるシェブロン（∧）。
   * 粒子は初速を上向きに揃えるので、全方向に弾ける通常 burst と動きで区別できる
   * （粒子の更新側の重力で、噴き上がってから落ちてくる放物線になる）。
   * 色はレーン色を主に、白を混ぜて「抜けた」明るさを出す。
   */
  private flickBurst(lane: number, level: 0 | 1 | 2, tier: number): void {
    const fx = tierFx(tier);
    const lw = this.width / 4;
    const cx = lane * lw + lw / 2;
    const cy = this.hitY();
    const c = LANE_COLORS[lane];
    const n = Math.round((level === 0 ? 14 : level === 1 ? 10 : 7) * fx.particleMul);
    for (let i = 0; i < n; i++) {
      const vx = (Math.random() - 0.5) * 130;
      const vy = -(260 + Math.random() * 260) * (0.9 + 0.1 * tier);
      const color = i % 3 === 0 ? '#ffffff' : c;
      this.spawnParticle(cx, cy, vx, vy, 0.4 + Math.random() * 0.2, color, fx.particleSize);
    }
    this.flickChevs.push({ x: cx, y: cy, age: 0, life: FLICK_CHEV_LIFE });
    if (this.flickChevs.length > 12) this.flickChevs.shift();
  }

  /**
   * 通常背景（ジャケット）の描画（オーナー決定 2026-11-20 の形）。
   * 背景の要素はジャケットと歌詞だけにする:
   * - ジャケットは、絵に焼き込まれた紙枠（charts.ts の frameInset）を除いた
   *   内側の絵だけを、画面幅いっぱいの正方形として上部に敷く。枠がないので
   *   「額縁に入った絵」ではなく背景そのものとして見える
   * - 正方形の下端は下地色（#0e1018）へグラデーションで溶かし、境目を消す
   * - ノーツはジャケットの上からそのまま流れ落ちる（描画順は従来どおり
   *   背景→ベール→レーン→ノーツ）。歌詞は DOM 側でジャケットのすぐ下に出る
   * 横長画面では正方形の一辺を画面の高さに合わせ、横は中央に置く。
   * コンボ演出の背景はこの方式の対象外（従来どおり全面 cover で置き換わる）。
   */
  private drawJacketBackground(W: number, H: number): void {
    const img = this.bg;
    if (!img) return;
    const { g } = this;
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    const inset = Math.min(this.entry?.frameInset ?? 0, iw / 4, ih / 4);
    const side = Math.min(W, H);
    const dx = (W - side) / 2;
    g.drawImage(img, inset, inset, iw - inset * 2, ih - inset * 2, dx, 0, side, side);
    // 下端を下地へ溶かす
    const fadeH = side * 0.18;
    const grad = g.createLinearGradient(0, side - fadeH, 0, side);
    grad.addColorStop(0, 'rgba(14,16,24,0)');
    grad.addColorStop(1, 'rgba(14,16,24,1)');
    g.fillStyle = grad;
    g.fillRect(dx, side - fadeH, side, fadeH);
  }


  private finish(failed = false): void {
    this.playing = false;
    cancelAnimationFrame(this.raf);
    stopCurrent();
    stopAllHoldSounds();
    const acc = accuracy(this.counts);
    setData('game', 'result');
    this.cb.onFinish({
      songTitle: this.entry?.data.title ?? '',
      difficulty: this.difficulty,
      score: this.score,
      counts: { ...this.counts },
      maxCombo: this.maxCombo,
      accuracy: acc,
      rank: rankFor(acc),
      autoplay: this.autoplay,
      failed,
    });
  }

  /**
   * ゲームオーバーの発動チェック（案1：ライフ制。オーナー指示 2026-11-22 で
   * 累計精度方式から作り替え）。ライフが 0 になったらその場で演奏を終了する。
   * 判定が更新される経路（ヒット・ミス掃除・長押しの成否）の直後から呼び、
   * 発動して終了させたときだけ true を返す
   * （ループ内から呼ばれた場合は、そのフレームの残りを打ち切るために使う）。
   * オートプレイでは発動しない。中断中は判定が動かないので対象にしない。
   */
  private checkGameOver(): boolean {
    if (this.autoplay || this.paused || !this.playing) return false;
    if (!isLifeGameOver(this.life)) return false;
    this.finish(true);
    return true;
  }

  /**
   * ライフメーター（演奏画面の上部に常時表示）。沿革：v1.4.4 で精度ベースの
   * ランクメーターとして新設 → v1.4.7 で細いバー＋tick＋% の簡素形 → v1.4.9 で
   * 上部1行に集約 → v1.4.12 で案1（ライフ制）に作り替え（オーナー指示 2026-11-22）。
   * 残すのは細いバー1本だけ：fill の長さ = 現在のライフ、色 = ライフの帯
   * （十分=緑／注意=黄／危険=赤）。危険域では fill を点滅させて危険が読めるようにする。
   * 精度 % 表示と旧ゲームオーバーライン（50% tick）は廃止（精度とランクは結果画面のみ）。
   * バーは中断ボタンの右から、右端のスコアの手前までに引く（スコアの幅は実測する）。
   */
  private drawLifeMeter(g: CanvasRenderingContext2D, W: number): void {
    const M = LIFE_METER;
    // バーの右端は、右端のスコアに重ならない位置まで。
    // スコアは右端 (W - edgeGap) に右寄せで出るので、その実測幅の分を空ける
    g.font = SCORE_FONT;
    const scoreW = g.measureText(String(this.score).padStart(7, '0')).width;
    const barRight = W - M.edgeGap - scoreW - M.scoreGap;
    const mx = M.meterX;
    const mw = Math.max(0, barRight - mx);
    const zone = lifeZone(this.life);
    // バー: 暗いトラックの上に、現在のライフまでの fill を帯の色で引く
    g.beginPath();
    g.roundRect(mx, M.meterY, mw, M.meterH, M.meterH / 2);
    g.fillStyle = '#2a2f3a';
    g.fill();
    if (this.life > 0) {
      g.save();
      g.beginPath();
      g.roundRect(mx, M.meterY, mw, M.meterH, M.meterH / 2);
      g.clip();
      // 危険域は点滅させて「やばい」が読めるようにする（約0.35秒周期で明滅）
      if (zone === 'danger') g.globalAlpha = 0.55 + 0.45 * Math.sin(performance.now() / 110);
      g.fillStyle = LIFE_COLORS[zone];
      g.fillRect(mx, M.meterY, (mw * this.life) / LIFE_MAX, M.meterH);
      g.restore();
    }
  }

  /**
   * オーディオビジュアライザー: 判定枠の下の空き領域に、再生中の曲の周波数を
   * バーで描く（周波数バー固定）。データは audio.ts の曲専用アナライザから取る
   * （効果音は混ざらない）。取得は2フレームに1回（約30Hz）に間引く。
   * アナライザが無い（音声が未生成の）ときは何も描かない。曲が始まる前
   * （READY 中）は無音データで静かな形になる。
   * 領域は 390×844 基準で x 58..332（中央寄せ）、y 702..838。v1.4.21 の領域
   * （x 12..378、y 652..834）を幅・高さとも約 3/4 に縮小し、少し下げたもの
   * （オーナー調整指示 2026-11-23）。
   */
  private drawVisualizer(g: CanvasRenderingContext2D, W: number, H: number): void {
    const analyser = musicAnalyser();
    if (!analyser) return;
    const x0 = (W * 58) / 390;
    const x1 = (W * 332) / 390;
    const y1 = H - (H * 6) / 844;
    const y0 = y1 - (H * 136) / 844;
    const bandH = y1 - y0;
    if (bandH < 40 || x1 - x0 < 80) return;

    if (!this.vizFreq || this.vizFreq.length !== analyser.frequencyBinCount) {
      this.vizFreq = new Uint8Array(analyser.frequencyBinCount);
    }
    const freq = this.vizFreq;
    if (!freq) return;
    this.vizFrame++;
    if (this.vizFrame % 2 === 1) {
      analyser.getByteFrequencyData(freq);
    }
    const sampleRate = analyser.context.sampleRate;


    // 周波数バー: 下端から伸びる。下→上のグラデーション＋上端のキャップ
    const vals = groupFreqBins(freq, VISUALIZER_FREQ_BARS, sampleRate);
    const slot = (x1 - x0) / vals.length;
    const bw = slot * 0.62;
    const grad = g.createLinearGradient(0, y1, 0, y0);
    grad.addColorStop(0, VIZ_BAR_BOTTOM);
    grad.addColorStop(1, VIZ_BAR_TOP);
    for (let i = 0; i < vals.length; i++) {
      const h = Math.max(2, vals[i] * bandH * 0.92);
      const x = x0 + i * slot + (slot - bw) / 2;
      g.globalAlpha = VIZ_BAR_ALPHA;
      g.fillStyle = grad;
      g.fillRect(x, y1 - h, bw, h);
      g.globalAlpha = VIZ_BAR_CAP_ALPHA;
      g.fillStyle = VIZ_BAR_TOP;
      g.beginPath();
      g.roundRect(x, y1 - h, bw, 4, 2);
      g.fill();
    }
    g.globalAlpha = 1;
  }

  private fit(): void {
    const d = window.devicePixelRatio || 1;
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (w !== this.width || h !== this.height || this.canvas.width !== Math.round(w * d)) {
      this.width = w;
      this.height = h;
      this.canvas.width = Math.round(w * d);
      this.canvas.height = Math.round(h * d);
      this.g.setTransform(d, 0, 0, d, 0, 0);
      this.notesCanvas.width = Math.round(w * d);
      this.notesCanvas.height = Math.round(h * d);
      this.gn.setTransform(d, 0, 0, d, 0, 0);
    }
  }

  private loop = (): void => {
    if (!this.playing) return;
    this.fit();
    const { g, gn } = this;
    const W = this.width;
    const H = this.height;
    const frameAt = nowSeconds();
    // 中断確認の「つづける」後の READY が明けたら、このフレームから再開する
    if (this.paused && this.pausePhase === 'countdown' && performance.now() >= this.resumeDueWall) {
      this.finishResume();
    }
    const isPaused = this.paused;
    // 前面にいるのに AudioContext が止まっている（iOS の割り込み＝着信等）と、
    // ゲームの時計が凍って READY や譜面が止まったままになる。1秒に1回だけ
    // resume を試みて復帰させる（間引きは時計自身が止まっているので壁時計で数える）
    if (audioContext().state !== 'running') {
      const wall = performance.now();
      if (wall - this.lastResumeTryWall > 1000) {
        this.lastResumeTryWall = wall;
        void resumeAudio();
      }
    }
    // 時計の凍結検知: 音声時計が壁時計で 1.5 秒以上進んでいなければ「止まっている」と
    // みなす。判定は状態（state）ではなく時計の進み具合そのもので行う。メニュー画面で
    // バックグラウンドへ行き復帰してから始めた場合、state は running と出るのに
    // currentTime だけが止まったままになることが実機で確認されたため（2026-11-20）。
    // 凍ったまま無言だと「タッチできない」ように見える
    if (frameAt > this.clockSeenAt + 0.001) {
      this.clockSeenAt = frameAt;
      this.clockAdvanceWall = performance.now();
    }
    const frozen = performance.now() - this.clockAdvanceWall > 1500;
    if (frozen !== this.audioFrozen) {
      this.audioFrozen = frozen;
      setData('audioFrozen', frozen ? 'on' : 'off');
    }
    if (frozen) {
      const posSec = frameAt - this.startAt;
      if (posSec > 0.1 || this.readyReinitUsed) {
        // 演奏が始まった後の凍結は、無理に再開せず初期化してメニューへ戻す
        // （オーナー指示 2026-11-20: 続きからの再開ではなく初期化再スタートで
        // よい）。音声の仕組みも作り直して、次のスタートがまっさらな状態から
        // 始まるようにする。READY の初期化し直しでも直らなかった場合もここへ来る
        this.resetInput();
        recreateAudioContext();
        this.abort();
        return;
      }
      // READY 中の凍結は、開始そのものを初期化し直す（曲はまだ始まっていない）
      void this.reinitStart();
    }
    // 経過時間（秒）。タブ復帰などで大きく飛んだときは 50ms に丸める。
    // 凍結中は時刻を止めた位置に固定し、演出の経過時間も進めない
    const dt = isPaused ? 0 : Math.min(0.05, Math.max(0, frameAt - this.lastFrameAt));
    this.lastFrameAt = frameAt;
    const nowSec = isPaused ? this.pausePosSec : frameAt - this.startAt;
    const nowMs = nowSec * 1000;
    // このフレームのコンボ段階。上がった瞬間は tierFlash を立てて縁の光を強める
    const tier = comboTier(this.combo);
    if (tier > this.lastTier) this.tierFlash = 1;
    this.lastTier = tier;
    this.tierFlash = Math.max(0, this.tierFlash - dt * 1.6);
    // 実効の落下時間は、難易度の基準値にプレイヤー設定の速度倍率を重ねたもの
    const fall = effectiveFallSeconds(DIFFICULTIES[this.difficulty].fallSeconds, this.speed);

    // 歌詞の現在行が変わったら通知する（表示は main.ts 側の DOM）
    const li = lyricIndexAt(this.entry?.lyrics ?? [], nowMs);
    if (!isPaused && li !== this.lyricIndex) {
      this.lyricIndex = li;
      setData('lyricIndex', li);
      this.cb.onLyric(li);
    }

    // オートプレイ中は、ミス掃除より先に時刻の来たノーツを PERFECT で処理する
    if (this.autoplay && !isPaused) this.autoPlay(nowMs);

    const missed = isPaused ? 0 : sweepMisses(this.notes, nowMs);
    if (missed > 0) {
      this.counts.miss += missed;
      this.life = applyLifeDelta(this.life, 'miss', missed);
      this.combo = 0; // コンボが切れたら tier も 0 に戻り、演出は素に戻る
      this.showJudge('miss');
      this.syncCombo();
      // ミス音はこの掃除で1回だけ（複数ノーツ同時ミスでも重ねない。連続フレームの抑制は playMissSound 側）
      playMissSound();
      // ライフが尽きたら、そのフレームでゲームオーバーにして打ち切る
      if (this.checkGameOver()) return;
    }

    // 長押しの進行: tick スコア（拍ごと。音はヒット音の連打が担当し、tick 自体は鳴らさない）、
    // 押し切ったら頭の判定で集計＋ボーナス＋完走音、失敗はミス＋失敗音
    for (const n of this.notes) {
      if (isPaused) break;
      if (n.holdPhase !== 'holding' && n.holdPhase !== 'grace') continue;
      const ev = advanceHold(n, nowMs);
      if (ev.ticks > 0) {
        this.score += ev.ticks * HOLD_TICK_SCORE;
        setData('score', this.score);
      }
      if (ev.completed && n.headJudge) {
        this.counts[n.headJudge]++;
        this.life = applyLifeDelta(this.life, n.headJudge);
        this.score += HOLD_COMPLETE_BONUS[n.headJudge];
        this.holdsCompleted++;
        setData('holdsCompleted', this.holdsCompleted);
        setData('score', this.score);
        // 連打は尾の時刻ちょうどで止め、完走音へつなぐ
        stopHoldSound(n);
        playCompleteSound(n.headJudge, comboTier(this.combo));
        this.burst(
          n.lane,
          n.headJudge === 'perfect' ? 0 : n.headJudge === 'great' ? 1 : 2,
          comboTier(this.combo),
        );
      }
      if (ev.failed) {
        this.counts.miss++;
        this.life = applyLifeDelta(this.life, 'miss');
        this.combo = 0;
        this.showJudge('miss');
        this.syncCombo();
        this.holdsFailed++;
        setData('holdsFailed', this.holdsFailed);
        stopHoldSound(n);
        // MISS の合図としてミス音も鳴らす（失敗音と役割が違うので両方鳴る）
        playMissSound();
        playFailSound();
      }
    }
    // 長押しの成否でライフが動いた直後にも、ゲームオーバーのチェックをする
    if (this.checkGameOver()) return;

    g.fillStyle = '#0e1018';
    g.fillRect(0, 0, W, H);
    if (this.bg?.complete && this.bg.naturalWidth) {
      this.drawJacketBackground(W, H);
    }
    // ベール（暗幕）はコンボ段階が上がるほど薄くし、ジャケットが冴えてくる
    g.fillStyle = `rgba(6,8,16,${TIER_VEIL_ALPHA[tier].toFixed(2)})`;
    g.fillRect(0, 0, W, H);
    // コンボ演出の登場中は、絵を背景として敷く。レーン・ノーツはこの後に描くので、
    // ノーツは常にはっきり手前に見える（全面カットインのように絵がノーツへ被る形にはしない）。
    // ピーク不透明度 1.0 で背景（ジャケット絵＋ベール）が完全に置き換わり、
    // 数秒そのままになる。出現・消滅は不透明度のフェード（イン 0.9秒 →
    // キープ → アウト 0.8秒、smoothstep でふわっとさせる）、
    // 動きは背景の中でのゆっくりした push-in（奥から近づく）。
    // 表示中に次の登場が来た場合は、triggerComboShow が comboBg を新しいパターン・時刻で
    // 上書きするので、包絡は新しい登場の頭から再生される（重なって破綻はしない）。
    // パターンに絵が無い場合は、背景の置き換えなし（セリフと紙吹雪だけ）で成立する。
    if (this.comboBg) {
      const img = comboBgImage(this.comboBg.pattern);
      const dur = this.comboBg.big ? COMBO_BG_DURATION_BIG_SEC : COMBO_BG_DURATION_SEC;
      const elapsed = frameAt - this.comboBg.shownAt;
      const t = elapsed / dur;
      if (t >= 1) {
        this.comboBg = null;
      } else if (img && img.complete && img.naturalWidth) {
        // 包絡は smoothstep で両端をなだらかにし、ふわっと出入りする
        const env = Math.max(
          0,
          Math.min(smoothstep(elapsed / COMBO_BG_FADE_IN_SEC), smoothstep((dur - elapsed) / COMBO_BG_FADE_OUT_SEC), 1),
        );
        const zp = COMBO_BG_ZOOM[this.comboBg.zoom];
        const eased = 1 - Math.pow(1 - t, zp.power);
        const zoom = this.reducedMotion ? 1 : zp.from + (zp.to - zp.from) * eased;
        const s = Math.max(W / img.naturalWidth, H / img.naturalHeight) * zoom;
        const w = img.naturalWidth * s;
        const hh = img.naturalHeight * s;
        g.globalAlpha = COMBO_BG_PEAK_ALPHA * env;
        g.drawImage(img, (W - w) / 2, (H - hh) / 2, w, hh);
        g.globalAlpha = 1;
        // 明るい絵の上でレーン線が埋もれないよう、表示中だけ薄い暗幕を敷く（包絡に連動）
        g.fillStyle = `rgba(5,6,12,${(COMBO_BG_VEIL_ALPHA * env).toFixed(3)})`;
        g.fillRect(0, 0, W, H);
      }
    }
    // ビジュアライザー（判定枠の下の空き領域。ノーツ専用キャンバスより下に描くので、
    // 下まで落ちてくるノーツが模様の手前に重なる）
    this.drawVisualizer(g, W, H);
    // 画面の縁の光（FEVER の枠の光に代わるコンボ演出）: 段位が上がるほど
    // 強く・太くなる。上がった瞬間は tierFlash でひときわ光り、ミスで消える
    const edge = TIER_EDGE[tier];
    if (edge) {
      const boost = this.tierFlash * 0.3;
      g.strokeStyle = `rgba(${edge.rgb},${(edge.alpha * 0.35 + boost * 0.4).toFixed(3)})`;
      g.lineWidth = edge.width * 2.4;
      g.strokeRect(edge.width * 1.2, edge.width * 1.2, W - edge.width * 2.4, H - edge.width * 2.4);
      g.strokeStyle = `rgba(${edge.rgb},${Math.min(1, edge.alpha + boost).toFixed(3)})`;
      g.lineWidth = edge.width;
      g.strokeRect(edge.width / 2 + 1, edge.width / 2 + 1, W - edge.width - 2, H - edge.width - 2);
    }
    const lw = W / 4;
    const hy = H * HIT_Y_RATIO;
    // このフレームの演出段階（コンボのみで決まる）。フラッシュとコンボ表示に使う
    const frameFx = tierFx(tier);
    for (let i = 0; i < 4; i++) {
      if (this.flash[i] > 0) {
        const alpha = Math.min(200, Math.round(this.flash[i] * 70 * frameFx.flashMul));
        g.fillStyle = LANE_COLORS[i] + alpha.toString(16).padStart(2, '0');
        g.fillRect(i * lw, 0, lw, H);
        this.flash[i] = Math.max(0, this.flash[i] - dt * 3.6);
      }
      if (i) {
        g.fillStyle = 'rgba(255,255,255,.12)';
        g.fillRect(i * lw - 0.5, 0, 1, H);
      }
    }
    g.fillStyle = 'rgba(255,255,255,.85)';
    g.fillRect(0, hy - 2, W, 4);
    const holdingLane = [false, false, false, false];
    for (const n of this.notes) if (n.holdPhase === 'holding') holdingLane[n.lane] = true;
    for (let i = 0; i < 4; i++) {
      g.strokeStyle = LANE_COLORS[i];
      g.lineWidth = 3;
      g.strokeRect(i * lw + 8, hy - 14, lw - 16, 28);
      if (holdingLane[i]) {
        // 長押し中は判定枠を明るく太くして「押せている」ことを示す
        g.globalAlpha = 0.65 + 0.35 * Math.sin(frameAt * 9);
        g.strokeStyle = '#ffffff';
        g.lineWidth = 2;
        g.strokeRect(i * lw + 5, hy - 17, lw - 10, 34);
        g.globalAlpha = 1;
      }
    }
    // ノーツ専用キャンバスは透明なので、毎フレーム消してから描く（ここから先の
    // ノーツ・長押し・ヒット演出は gn 側。歌詞 DOM より手前に重なる）
    gn.clearRect(0, 0, W, H);
    // 長押しの帯（タップノーツより先に描く）。頭がラインに届いたら帯の下端はラインに吸着する
    for (const n of this.notes) {
      if (n.holdMs <= 0 || n.state === 2) continue;
      if (n.holdPhase === 'done' || n.holdPhase === 'failed') continue;
      const headY = hy - ((n.timeMs - nowMs) / 1000 / fall) * hy;
      const tailMs = n.timeMs + n.holdMs;
      const tailY = hy - ((tailMs - nowMs) / 1000 / fall) * hy;
      // 描く範囲は「帯そのもの」が見える間で決める。頭の仮想位置は消費された後も
      // 下がり続けるので、それで打ち切ると尾がラインに届く前に帯が消えてしまう
      // （v1.7.0 までの不具合。実測: 891ms の長押しで最後の約344ms が見えなかった）。
      // 尾が画面の下端を過ぎるまでは描き続ける。
      if (tailY > H + 40 || headY < -40) continue;
      const c = LANE_COLORS[n.lane];
      const cx = n.lane * lw + lw / 2;
      const bw = lw - 36;
      const bottom = n.state === 1 ? hy : headY;
      const bodyTop = tailY + 7;
      if (bottom > bodyTop) {
        if (n.holdPhase === 'holding') {
          gn.globalAlpha = 0.3;
          gn.fillStyle = c;
          gn.beginPath();
          gn.roundRect(cx - bw / 2 - 6, bodyTop, bw + 12, bottom - bodyTop, 12);
          gn.fill();
        }
        gn.globalAlpha =
          n.holdPhase === 'holding' ? 0.95 : n.holdPhase === 'grace' ? 0.5 + 0.25 * Math.sin(frameAt * 28) : 0.55;
        gn.fillStyle = c;
        gn.beginPath();
        gn.roundRect(cx - bw / 2, bodyTop, bw, bottom - bodyTop, 9);
        gn.fill();
        if (n.holdPhase === 'holding') {
          gn.globalAlpha = 0.55;
          gn.fillStyle = '#fff';
          gn.fillRect(cx - 2, bodyTop + 4, 4, Math.max(0, bottom - bodyTop - 8));
          gn.globalAlpha = 1;
        } else {
          gn.globalAlpha = 1;
        }
      }
      // 尾のキャップ
      gn.fillStyle = c;
      gn.beginPath();
      gn.roundRect(n.lane * lw + 10, tailY - 7, lw - 20, 14, 7);
      gn.fill();
      // 頭のキャップ（未ヒットのときだけ。ヒット後はライン側に吸着する）
      if (n.state === 0) {
        gn.beginPath();
        gn.roundRect(n.lane * lw + 8, headY - 14, lw - 16, 28, 8);
        gn.fill();
      }
    }
    for (const n of this.notes) {
      if (n.state !== 0 || n.holdMs > 0) continue;
      const y = hy - ((n.timeMs - nowMs) / 1000 / fall) * hy;
      // フリック矢印は高さ 60px を脈動させるため、通常ノーツより広い余白で間引く
      if (n.flick ? y < -80 || y > H + 80 : y < -30 || y > H + 30) continue;
      if (n.flick) {
        // フリックの印は大きなブロック矢印（↑）だけ（オーナー決定 2026-11-23、確定仕様）。
        // 四角いノーツ本体は描かず、矢印を従来ノーツの中心位置に置く。
        // 塗りはそのレーンの色、縁取りは濃紺。矢印の中心を支点に脈動させる
        const cx = n.lane * lw + lw / 2;
        const pulse =
          1 +
          (FLICK_ARROW_PULSE_MAX - 1) *
            (0.5 + 0.5 * Math.sin((frameAt / FLICK_ARROW_PULSE_PERIOD_SEC) * Math.PI * 2));
        const ah = FLICK_ARROW_HEIGHT;
        const aw = lw - 10;
        gn.save();
        gn.translate(cx, y);
        gn.scale(pulse, pulse);
        gn.beginPath();
        gn.moveTo(0, -ah / 2);
        gn.lineTo(aw / 2, ah * 0.05);
        gn.lineTo(aw * 0.22, ah * 0.05);
        gn.lineTo(aw * 0.22, ah / 2);
        gn.lineTo(-aw * 0.22, ah / 2);
        gn.lineTo(-aw * 0.22, ah * 0.05);
        gn.lineTo(-aw / 2, ah * 0.05);
        gn.closePath();
        gn.fillStyle = LANE_COLORS[n.lane];
        gn.fill();
        gn.strokeStyle = FLICK_ARROW_OUTLINE_COLOR;
        // 縁取りの太さが脈動で拡縮されないよう、拡大率で割って画面上 5px 一定にする
        gn.lineWidth = FLICK_ARROW_OUTLINE_WIDTH / pulse;
        gn.lineJoin = 'round';
        gn.stroke();
        gn.restore();
        continue;
      }
      const nx = n.lane * lw + 8;
      const nw = lw - 16;
      const nh = 28;
      gn.fillStyle = LANE_COLORS[n.lane];
      gn.beginPath();
      gn.roundRect(nx, y - nh / 2, nw, nh, 8);
      gn.fill();
    }

    // ---- ヒット演出（時間ベースで更新） ----
    for (const p of this.pops) {
      p.age += dt;
      const k = p.age / p.life;
      if (k >= 1) continue;
      const scale = 1 + (p.maxScale - 1) * k;
      const w = (lw - 16) * scale;
      const h = 28 * scale;
      gn.globalAlpha = 0.75 * (1 - k);
      gn.fillStyle = p.c;
      gn.beginPath();
      gn.roundRect(p.lane * lw + lw / 2 - w / 2, hy - h / 2, w, h, 8);
      gn.fill();
    }
    this.pops = this.pops.filter((p) => p.age < p.life);
    gn.globalAlpha = 1;

    for (const r of this.rings) {
      r.age += dt;
      const k = r.age / r.life;
      if (k >= 1) continue;
      const ease = 1 - (1 - k) * (1 - k);
      gn.globalAlpha = 0.9 * (1 - k);
      gn.strokeStyle = r.c;
      gn.lineWidth = (1 + 3.5 * (1 - k)) * r.widthMul;
      gn.beginPath();
      gn.arc(r.x, r.y, 10 + (r.maxR - 10) * ease, 0, 7);
      gn.stroke();
    }
    this.rings = this.rings.filter((r) => r.age < r.life);
    gn.globalAlpha = 1;

    // 粒子は上限つき。死んだものはプールへ戻して再利用する（毎フレームの確保を避ける）
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.age += dt;
      if (p.age >= p.life) {
        this.particles[i] = this.particles[this.particles.length - 1];
        this.particles.pop();
        if (this.particlePool.length < MAX_PARTICLES) this.particlePool.push(p);
        continue;
      }
      p.vy += 900 * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      gn.globalAlpha = 1 - p.age / p.life;
      gn.fillStyle = p.c;
      gn.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
    }
    gn.globalAlpha = 1;

    for (const r of this.ripples) {
      r.age += dt;
      const k = r.age / r.life;
      if (k >= 1) continue;
      gn.globalAlpha = 0.7 * (1 - k);
      gn.strokeStyle = r.c;
      gn.lineWidth = 2;
      gn.beginPath();
      gn.arc(r.x, r.y, 6 + 34 * k, 0, 7);
      gn.stroke();
    }
    this.ripples = this.ripples.filter((r) => r.age < r.life);
    gn.globalAlpha = 1;

    // フリック成功時に飛ぶシェブロン: その場から上へ進みながら少し広がり、消える
    for (const f of this.flickChevs) {
      f.age += dt;
      const k = f.age / f.life;
      if (k >= 1) continue;
      const rise = FLICK_CHEV_RISE_PX * (1 - (1 - k) * (1 - k));
      const s = 11 + 3 * k;
      gn.globalAlpha = 0.95 * (1 - k);
      // 成功シェブロンの色は水色のまま維持（見た目改善の案A、2026-11-23。演出自体は従来どおり）
      gn.strokeStyle = FLICK_CHEVRON_COLOR;
      gn.lineWidth = 4;
      gn.lineJoin = 'round';
      gn.beginPath();
      gn.moveTo(f.x - s, f.y - rise + s * 0.55);
      gn.lineTo(f.x, f.y - rise - s * 0.55);
      gn.lineTo(f.x + s, f.y - rise + s * 0.55);
      gn.stroke();
    }
    this.flickChevs = this.flickChevs.filter((f) => f.age < f.life);
    gn.globalAlpha = 1;

    g.textAlign = 'center';
    if (nowSec < 0) {
      g.fillStyle = '#fff';
      g.font = 'bold 48px sans-serif';
      g.fillText('READY', W / 2, H * 0.4);
    }
    if (isPaused && this.pausePhase === 'countdown') {
      // 再開前の READY（確認カードが閉じた後、演奏が戻るまでの1秒）
      g.fillStyle = '#fff';
      g.font = 'bold 48px sans-serif';
      g.fillText('READY', W / 2, H * 0.4);
    }
    if (this.audioFrozen) {
      // 音声が止まって時計が凍っている間の案内。タップで復帰できることを伝える
      g.fillStyle = '#fff';
      g.font = 'bold 19px sans-serif';
      g.shadowColor = 'rgb(0 0 0 / 0.9)';
      g.shadowBlur = 6;
      g.fillText('音声が止まっています', W / 2, H * 0.52);
      g.font = '16px sans-serif';
      g.fillText('画面をタップすると再開します', W / 2, H * 0.52 + 26);
      g.shadowBlur = 0;
    }
    if (this.combo > 1) {
      // コンボ表示も tier で色・大きさが変わる（高 tier では光る）。
      // 数字の基準サイズは 54px（オーナー指示 2026-11-20「表示物は全体的にもう少し大きく」）
      const comboPx = Math.round(54 * frameFx.comboScale);
      if (tier >= 3) {
        g.shadowColor = frameFx.comboColor;
        g.shadowBlur = 16;
      }
      g.fillStyle = frameFx.comboColor;
      g.font = `bold ${comboPx}px sans-serif`;
      g.fillText(String(this.combo), W / 2, H * 0.3);
      g.shadowBlur = 0;
      g.font = '17px sans-serif';
      g.fillText('COMBO', W / 2, H * 0.3 + 26 + (comboPx - 54));
    }
    // 判定文字: 出た瞬間に大きく、縮みながらフェードする（経過時間ベース）。
    // 出た時点の tier で拡大し、高 tier では光る
    const judgeAge = frameAt - this.judgeShownAt;
    if (this.judgeText && judgeAge < JUDGE_LIFE) {
      const popK = Math.min(1, judgeAge / 0.12);
      const scale = (1.35 - 0.35 * popK) * tierFx(this.judgeTier).judgeMul;
      const alpha = judgeAge < 0.35 ? 1 : 1 - (judgeAge - 0.35) / (JUDGE_LIFE - 0.35);
      g.globalAlpha = Math.max(0, alpha);
      if (this.judgeTier >= 3) {
        g.shadowColor = this.judgeColor;
        g.shadowBlur = 18;
      }
      g.fillStyle = this.judgeColor;
      g.font = `bold ${Math.round(34 * scale)}px sans-serif`;
      // 位置は歌詞（5行）のブロックと近づきすぎないよう、画面半分より少し上に置く
      // （オーナー指示 2026-11-20「ヒット判定から少しスペースを開けたい」）
      g.fillText(this.judgeText, W / 2, H * 0.46);
      g.shadowBlur = 0;
      g.globalAlpha = 1;
    }
    g.textAlign = 'left';
    // 中断ボタン: 丸ボタンに ❚❚ アイコンだけ（v1.4.9 の上部 UI 見直しで文字は消した）
    g.fillStyle = 'rgba(6,8,16,.45)';
    g.beginPath();
    g.arc(PAUSE_BTN.cx, PAUSE_BTN.cy, PAUSE_BTN.r, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#fff';
    g.fillRect(PAUSE_BTN.cx - 7, PAUSE_BTN.cy - 8, 5, 16);
    g.fillRect(PAUSE_BTN.cx + 2, PAUSE_BTN.cy - 8, 5, 16);
    g.font = SCORE_FONT;
    g.textAlign = 'right';
    g.fillText(String(this.score).padStart(7, '0'), W - 14, SCORE_BASELINE_Y);
    // 曲の進行バー（最上端 3px）。経過分の色は金から白に変えた
    // （金色のランクメーターと並ぶと紛らわしいため、v1.4.9 の見直し）
    g.fillStyle = 'rgba(255,255,255,.2)';
    g.fillRect(0, 0, W, 3);
    g.fillStyle = '#fff';
    g.fillRect(0, 0, W * Math.max(0, Math.min(1, nowSec / this.durationSec)), 3);
    this.drawLifeMeter(g, W);

    if ((nowMs > this.durationSec * 1000 + 500 && this.notes.every((n) => n.state !== 0)) || nowMs > this.durationSec * 1000 + 2000) {
      this.finish();
      return;
    }
    this.raf = requestAnimationFrame(this.loop);
  };
}
