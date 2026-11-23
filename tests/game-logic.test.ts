import { describe, expect, it } from 'vitest';
import {
  clampSpeed,
  effectiveFallSeconds,
  findFlickHit,
  findHit,
  findKeyboardHit,
  findNearestNote,
  HIT_Y_RATIO,
  LIFE_CAUTION,
  LIFE_DANGER,
  LIFE_DELTAS,
  LIFE_MAX,
  applyLifeDelta,
  isLifeGameOver,
  lifeZone,
  LATENCY_DROP_COUNT,
  LATENCY_TAP_COUNT,
  latencyStats,
  isNewBest,
  makePlayNotes,
  groupFreqBins,
  rankFor,
  RANK_THRESHOLDS,
  validateCharts,
  type NoteData,
  type SongData,
} from '../src/game/logic';

// リズムゲームのルール層（src/game/logic.ts）の単体テスト。
// 実データの整合は tests/game-data.test.ts が担当し、ここは関数の振る舞いだけを見る。

const play = (chart: NoteData[]) => makePlayNotes(chart, 0);

describe('makePlayNotes（フリックの伝播）', () => {
  it('4要素目 "flick" が PlayNote.flick になる', () => {
    const notes = play([
      [1000, 0],
      [2000, 1, 0, 'flick'],
      [3000, 2, 800],
    ]);
    expect(notes.map((n) => n.flick)).toEqual([false, true, false]);
    expect(notes[1].holdMs).toBe(0);
    expect(notes[2].holdMs).toBe(800);
  });
});

describe('findHit（タップ判定）', () => {
  it('フリックノーツはタップでは取れない', () => {
    const notes = play([[1000, 1, 0, 'flick']]);
    expect(findHit(notes, 1, 1000)).toBeNull();
  });

  it('フリックが近くにあっても、タップノーツは取れる', () => {
    const notes = play([
      [1000, 1, 0, 'flick'],
      [1090, 1],
    ]);
    const hit = findHit(notes, 1, 1000);
    expect(hit?.note.timeMs).toBe(1090);
    expect(hit?.judge).toBe('great');
  });

  it('通常ノーツと長押しの頭は従来どおり取れる', () => {
    const notes = play([
      [1000, 0],
      [2000, 2, 800],
    ]);
    expect(findHit(notes, 0, 1010)?.judge).toBe('perfect');
    expect(findHit(notes, 2, 2000)?.note.holdMs).toBe(800);
  });
});

describe('findFlickHit（フリック判定）', () => {
  it('タップノーツよりフリックノーツを優先する（タップのほうが近くても）', () => {
    const notes = play([
      [1000, 1],
      [1140, 1, 0, 'flick'],
    ]);
    const hit = findFlickHit(notes, 1, 1000);
    expect(hit?.note.flick).toBe(true);
    expect(hit?.note.timeMs).toBe(1140);
  });

  it('フリックノーツが無ければ通常のタップノーツを取る', () => {
    const notes = play([[1000, 1]]);
    const hit = findFlickHit(notes, 1, 1030);
    expect(hit?.note.timeMs).toBe(1000);
    expect(hit?.judge).toBe('perfect');
  });

  it('長押しの頭はフリックでは取らない', () => {
    const notes = play([[1000, 1, 800]]);
    expect(findFlickHit(notes, 1, 1000)).toBeNull();
  });

  it('判定窓の外は null', () => {
    const notes = play([[1000, 1, 0, 'flick']]);
    expect(findFlickHit(notes, 1, 1300)).toBeNull();
    expect(findFlickHit(notes, 0, 1000)).toBeNull();
  });

  it('判定済みのフリックノーツは対象にしない', () => {
    const notes = play([
      [1000, 1, 0, 'flick'],
      [1100, 1],
    ]);
    notes[0].state = 1;
    const hit = findFlickHit(notes, 1, 1000);
    expect(hit?.note.timeMs).toBe(1100);
  });
});

describe('findKeyboardHit（キーボード判定）', () => {
  it('フリックノーツを通常のキー押しで取れる（タップと同じ判定）', () => {
    const notes = play([[1000, 1, 0, 'flick']]);
    const hit = findKeyboardHit(notes, 1, 1000);
    expect(hit?.note.flick).toBe(true);
    expect(hit?.judge).toBe('perfect');
    expect(findKeyboardHit(notes, 1, 1080)?.judge).toBe('great');
    expect(findKeyboardHit(notes, 1, 1150)?.judge).toBe('good');
  });

  it('種別を問わず、いちばん近いノーツを取る', () => {
    const flickFirst = play([
      [1000, 1, 0, 'flick'],
      [1090, 1],
    ]);
    expect(findKeyboardHit(flickFirst, 1, 1000)?.note.timeMs).toBe(1000);
    const tapFirst = play([
      [1000, 1],
      [1090, 1, 0, 'flick'],
    ]);
    expect(findKeyboardHit(tapFirst, 1, 1090)?.note.timeMs).toBe(1090);
  });

  it('通常ノーツと長押しの頭も従来どおり取れる', () => {
    const notes = play([
      [1000, 0],
      [2000, 2, 800],
    ]);
    expect(findKeyboardHit(notes, 0, 1010)?.judge).toBe('perfect');
    expect(findKeyboardHit(notes, 2, 2000)?.note.holdMs).toBe(800);
  });

  it('判定窓の外・別レーン・判定済みは対象にしない', () => {
    const notes = play([[1000, 1, 0, 'flick']]);
    expect(findKeyboardHit(notes, 1, 1300)).toBeNull();
    expect(findKeyboardHit(notes, 0, 1000)).toBeNull();
    notes[0].state = 1;
    expect(findKeyboardHit(notes, 1, 1000)).toBeNull();
  });
});

describe('findNearestNote（タップ無効化の判定用）', () => {
  it('最寄りがフリックノーツならそれを返す', () => {
    const notes = play([
      [1000, 1, 0, 'flick'],
      [1150, 1],
    ]);
    expect(findNearestNote(notes, 1, 1000)?.flick).toBe(true);
  });

  it('窓の外なら null', () => {
    const notes = play([[1000, 1, 0, 'flick']]);
    expect(findNearestNote(notes, 1, 2000)).toBeNull();
  });
});

const songWith = (notes: NoteData[]): SongData => ({
  title: 'テスト曲',
  durationMs: 60000,
  bpm: 120,
  fever: [],
  charts: { easy: notes, normal: notes, hard: notes },
});

describe('validateCharts（フリックの規則）', () => {
  it('長押し付きのフリックノーツはエラー', () => {
    const errors = validateCharts(
      songWith([
        [3000, 0, 500, 'flick'],
        [5000, 1],
        [7000, 2],
      ]),
    );
    expect(errors.some((e) => e.includes('フリックノーツに長押し'))).toBe(true);
  });

  it('長押しなしのフリックノーツは通る（[t, lane, 0, "flick"]）', () => {
    const errors = validateCharts(
      songWith([
        [3000, 0, 0, 'flick'],
        [5000, 1],
        [7000, 2],
      ]),
    );
    expect(errors).toEqual([]);
  });

  it('長押しの帯の中にあるフリックノーツは、通常ノーツと同じくエラー', () => {
    const errors = validateCharts(
      songWith([
        [3000, 0, 3000],
        [4000, 0, 0, 'flick'],
        [8000, 1],
      ]),
    );
    expect(errors.some((e) => e.includes('長押しの帯の中'))).toBe(true);
  });
});

describe('速度調整（clampSpeed / effectiveFallSeconds）', () => {
  it('0.1 刻みに丸める', () => {
    expect(clampSpeed(1.26)).toBe(1.3);
    expect(clampSpeed(1.24)).toBe(1.2);
    expect(clampSpeed(1.0)).toBe(1.0);
  });

  it('範囲（×0.8〜×2.0）に収める', () => {
    expect(clampSpeed(0.5)).toBe(0.8);
    expect(clampSpeed(2.4)).toBe(2.0);
    expect(clampSpeed(0.8)).toBe(0.8);
    expect(clampSpeed(2.0)).toBe(2.0);
  });

  it('不正な値は既定の ×1.0', () => {
    expect(clampSpeed(NaN)).toBe(1.0);
    expect(clampSpeed(Infinity)).toBe(1.0);
  });

  it('実効落下時間は fallSeconds ÷ 倍率', () => {
    expect(effectiveFallSeconds(2.0, 1.0)).toBe(2.0);
    expect(effectiveFallSeconds(2.0, 2.0)).toBe(1.0);
    expect(effectiveFallSeconds(1.6, 0.8)).toBe(2.0);
    expect(effectiveFallSeconds(1.3, 1.3)).toBe(1.0);
  });
});

describe('ビジュアライザー（groupFreqBins）', () => {
  it('無音（全ビン 0）は全グループ 0、最大（全ビン 255）は全グループ 1', () => {
    const silent = new Uint8Array(1024);
    expect(groupFreqBins(silent, 36, 44100)).toEqual(new Array(36).fill(0));
    const loud = new Uint8Array(1024).fill(255);
    expect(groupFreqBins(loud, 36, 44100)).toEqual(new Array(36).fill(1));
    expect(groupFreqBins(loud, 48, 48000)).toEqual(new Array(48).fill(1));
  });

  it('低域だけ鳴らすと先頭のグループだけが立ち、高域だけだと後ろが立つ', () => {
    const low = new Uint8Array(1024);
    low.fill(255, 1, 8); // 約43〜345Hz
    const lowVals = groupFreqBins(low, 36, 44100);
    expect(lowVals[0]).toBeGreaterThan(0);
    expect(lowVals[35]).toBe(0);
    const high = new Uint8Array(1024);
    high.fill(255, 600, 700); // 約12.9k〜15.1kHz（上限 13kHz の内側が効く）
    const highVals = groupFreqBins(high, 36, 44100);
    expect(highVals[0]).toBe(0);
    expect(highVals[35]).toBeGreaterThan(0);
  });
});

describe('判定ラインの高さ（HIT_Y_RATIO）', () => {
  it('タッチ位置は「上」固定で、比率は 0.74（旧「標準」0.82 の約8%上）', () => {
    expect(HIT_Y_RATIO).toBe(0.74);
  });
});

describe('rankFor / RANK_THRESHOLDS（ランクの境目）', () => {
  it('境目は S=95 / A=85 / B=70 で、ちょうど境目なら上のランク', () => {
    expect(RANK_THRESHOLDS).toEqual({ S: 95, A: 85, B: 70 });
    expect(rankFor(95)).toBe('S');
    expect(rankFor(85)).toBe('A');
    expect(rankFor(70)).toBe('B');
    expect(rankFor(69.9)).toBe('C');
    expect(rankFor(0)).toBe('C');
  });
});

describe('isNewBest（ハイスコア更新の判定）', () => {
  it('保存済みベストを上回ったら更新', () => {
    expect(isNewBest(5000, 5001)).toBe(true);
    expect(isNewBest(5000, 6000)).toBe(true);
  });

  it('同点・下回ったら更新ではない', () => {
    expect(isNewBest(5000, 5000)).toBe(false);
    expect(isNewBest(5000, 4999)).toBe(false);
  });

  it('初回プレイ（ベスト未保存）は、ベストが作られる回として更新に含める', () => {
    expect(isNewBest(undefined, 1000)).toBe(true);
  });

  it('スコア 0 は更新にしない（何も叩かずに終わった回）', () => {
    expect(isNewBest(undefined, 0)).toBe(false);
    expect(isNewBest(0, 0)).toBe(false);
  });
});

describe('ライフ制（案1：メーターとゲームオーバー）', () => {
  it('増減の初期値：MISS −4 / GOOD −1 / GREAT ＋0.2 / PERFECT ＋0.4、最大 100', () => {
    expect(LIFE_MAX).toBe(100);
    expect(LIFE_DELTAS).toEqual({ perfect: 0.4, great: 0.2, good: -1, miss: -4 });
  });

  it('満タンから MISS 25 連続でちょうど 0 になり、ゲームオーバーになる', () => {
    let life = LIFE_MAX;
    for (let i = 0; i < 24; i++) life = applyLifeDelta(life, 'miss');
    expect(life).toBeCloseTo(4);
    expect(isLifeGameOver(life)).toBe(false);
    life = applyLifeDelta(life, 'miss');
    expect(life).toBe(0);
    expect(isLifeGameOver(life)).toBe(true);
  });

  it('猶予はない：序盤でもライフが尽きれば即ゲームオーバー（満タン開始が緩衝）', () => {
    // 最初の25ノーツを全部ミスしたら、その時点で終わる（旧方式の20ノーツ猶予は廃止）
    let life = LIFE_MAX;
    for (let i = 0; i < 25; i++) life = applyLifeDelta(life, 'miss');
    expect(isLifeGameOver(life)).toBe(true);
  });

  it('良い判定で少しずつ回復するが、上限 100 を超えない', () => {
    expect(applyLifeDelta(50, 'perfect')).toBeCloseTo(50.4);
    expect(applyLifeDelta(50, 'great')).toBeCloseTo(50.2);
    expect(applyLifeDelta(99.9, 'perfect')).toBe(100);
    expect(applyLifeDelta(100, 'perfect')).toBe(100);
  });

  it('GOOD でも少し減り、0 未満にはならない', () => {
    expect(applyLifeDelta(50, 'good')).toBe(49);
    expect(applyLifeDelta(2, 'miss')).toBe(0);
  });

  it('同時ミスは times でまとめて引ける（ミス掃除の経路）', () => {
    expect(applyLifeDelta(100, 'miss', 3)).toBe(88);
  });

  it('並び順で結果が変わる：満タン付近の回復は頭打ちになる', () => {
    // 同じ内訳（PERFECT 10 / MISS 1）でも、ミスが先なら回復が全部効き、
    // ミスが後なら満タンで溢れた回復分だけ損をする
    let missFirst = LIFE_MAX;
    missFirst = applyLifeDelta(missFirst, 'miss');
    for (let i = 0; i < 10; i++) missFirst = applyLifeDelta(missFirst, 'perfect');
    let missLast = LIFE_MAX;
    for (let i = 0; i < 10; i++) missLast = applyLifeDelta(missLast, 'perfect');
    missLast = applyLifeDelta(missLast, 'miss');
    expect(missFirst).toBe(100);
    expect(missLast).toBe(96);
  });

  it('帯：50 超は safe、50 以下は caution、30 以下は danger', () => {
    expect(LIFE_CAUTION).toBe(50);
    expect(LIFE_DANGER).toBe(30);
    expect(lifeZone(100)).toBe('safe');
    expect(lifeZone(51)).toBe('safe');
    expect(lifeZone(50)).toBe('caution');
    expect(lifeZone(31)).toBe('caution');
    expect(lifeZone(30)).toBe('danger');
    expect(lifeZone(0)).toBe('danger');
  });

  it('結果ランクの定義は変えない（精度 50% 未満でも rankFor は C）', () => {
    expect(rankFor(49.9)).toBe('C');
    expect(rankFor(0)).toBe('C');
  });
});

describe('遅延チェック（簡略化：6タップ・自動反映の前提）', () => {
  it('必要タップ数は 6、練習として捨てるのは最初の 1 回', () => {
    expect(LATENCY_TAP_COUNT).toBe(6);
    expect(LATENCY_DROP_COUNT).toBe(1);
  });

  it('6タップ分のズレから、最初を捨てた残り5回の平均を出す', () => {
    // 最初の 999 は練習として捨てられる
    const stats = latencyStats([999, 30, 40, 50, 60, 70]);
    expect(stats).not.toBeNull();
    expect(stats!.usedCount).toBe(5);
    expect(stats!.meanMs).toBe(50);
  });

  it('タップが練習分しかなければ null（反映しない）', () => {
    expect(latencyStats([10])).toBeNull();
    expect(latencyStats([])).toBeNull();
  });
});
