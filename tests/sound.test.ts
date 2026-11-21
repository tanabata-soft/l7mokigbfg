import { describe, expect, it } from 'vitest';
import { resultJingleDurationMs, resultJingleNotes } from '../src/game/sound';

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
