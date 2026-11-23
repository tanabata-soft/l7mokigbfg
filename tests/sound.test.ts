import { describe, expect, it } from 'vitest';
import { GAME_OVER_NOTES, GAME_OVER_WAIT_MS, MISS_MIN_INTERVAL_MS, missSoundDue, missToneFor, resultJingleDurationMs, resultJingleNotes } from '../src/game/sound';

describe('結果発表ジングル', () => {
  it('通常ランクは上行4音→終止和音（4音が同じ時刻）で終わる', () => {
    const notes = resultJingleNotes('C');
    const lastAt = Math.max(...notes.map((n) => n.atSec));
    const chord = notes.filter((n) => n.atSec === lastAt);
    expect(chord).toHaveLength(4);
    // 上行4音は単調に高くなる
    const up = notes.slice(0, 4).map((n) => n.freq);
    expect(up).toEqual([...up].sort((a, b) => a - b));
  });

  it('S ランクはきらめき（高音2音）が増えて、通常より長い', () => {
    const base = resultJingleNotes('A');
    const s = resultJingleNotes('S');
    expect(s.length).toBe(base.length + 2);
    expect(s.some((n) => n.freq > 1300)).toBe(true);
    expect(resultJingleDurationMs('S')).toBeGreaterThan(resultJingleDurationMs('A'));
  });

  it('長さは最後の音が消える時刻＋80ms', () => {
    const notes = resultJingleNotes('B');
    const endMs = Math.max(...notes.map((n) => (n.atSec + n.durSec) * 1000));
    expect(resultJingleDurationMs('B')).toBe(Math.round(endMs) + 80);
  });
});

describe('ゲームオーバー音（アプリ内合成）', () => {
  it('結果カードを出すまでの待ち時間は 1500ms', () => {
    expect(GAME_OVER_WAIT_MS).toBe(1500);
  });

  it('短調の下行4音で、最後の音がいちばん低い', () => {
    const freqs = GAME_OVER_NOTES.map((n) => n.freq);
    expect(freqs).toHaveLength(4);
    expect(freqs).toEqual([...freqs].sort((a, b) => b - a));
  });
});

describe('ミス音（ポッ）', () => {
  it('下降サイン音（終わりの周波数が始まりより低い）で、音量は控えめ', () => {
    const tone = missToneFor();
    expect(tone.toHz).toBeLessThan(tone.fromHz);
    expect(tone.fromHz).toBe(320);
    expect(tone.toHz).toBe(180);
    // ヒット音（サンプル peak 0.32〜0.5）より小さい
    expect(tone.peak).toBeLessThan(0.32);
    expect(tone.peak).toBeGreaterThan(0);
  });

  it('最小間隔未満の連続ミスでは鳴らさない', () => {
    expect(MISS_MIN_INTERVAL_MS).toBe(60);
    expect(missSoundDue(1000, 1000 + MISS_MIN_INTERVAL_MS - 1)).toBe(false);
    expect(missSoundDue(1000, 1000 + MISS_MIN_INTERVAL_MS)).toBe(true);
    expect(missSoundDue(Number.NEGATIVE_INFINITY, 0)).toBe(true);
  });
});
