// 単位F: 再生位置ウィンドウ（game-window.ts）の検証。
// 特に「頭がウィンドウ外でも尾が表示範囲内ならホールドが含まれる」ことを守る。
import { describe, expect, it } from 'vitest';
import { makePlayNotes, type NoteData } from '../src/game/logic';
import { isSortedByTime, judgeWindow, maxHoldMsOf, noteWindow } from '../src/game/game-window';

function notes(chart: NoteData[]) {
  return makePlayNotes(chart, 0);
}

describe('noteWindow', () => {
  it('未来のノーツは end の外、過去のノーツは start の外になる', () => {
    const ns = notes([
      [0, 0],
      [1000, 1],
      [2000, 2],
      [60_000, 3],
    ]);
    const win = noteWindow(ns, 2000, 2000, maxHoldMsOf(ns));
    expect(win.start).toBe(0); // 0ms のノーツは過去余裕（fall×2+1s=5s）の中
    expect(win.end).toBe(3); // 60s 先は未来余裕の外
    const win2 = noteWindow(ns, 30_000, 2000, maxHoldMsOf(ns));
    expect(win2.start).toBe(3); // 2s のノーツは過去余裕の外
    expect(win2.end).toBe(3); // 60s のノーツは未来余裕（+5s）の外なので end はその手前
  });

  it('長いホールドは頭が過去余裕の外でも、尾が範囲内なら含まれる', () => {
    // 頭 0ms・長さ 20 秒のホールド + 通常ノーツ群
    const ns = notes([
      [0, 0, 20_000],
      [5000, 1],
      [10_000, 2],
      [15_000, 3],
    ]);
    const maxHold = maxHoldMsOf(ns);
    expect(maxHold).toBe(20_000);
    // nowMs=19000: ホールドの頭は 19 秒前（過去余裕 5 秒の外）だが尾は 20s で範囲内
    const win = noteWindow(ns, 19_000, 2000, maxHold);
    expect(win.start).toBe(0);
    expect(ns[win.start].holdMs).toBe(20_000);
    // nowMs=30000: 尾（20s）も過去余裕の外に出たら除外される
    const win2 = noteWindow(ns, 30_000, 2000, maxHold);
    expect(win2.start).toBeGreaterThan(0);
  });

  it('短いノーツの後ろに隠れた長いホールドを取りこぼさない', () => {
    const ns = notes([
      [0, 1],
      [100, 0, 30_000], // 短いノーツの直後にある長いホールド
      [200, 2],
    ]);
    const win = noteWindow(ns, 25_000, 2000, maxHoldMsOf(ns));
    // 尾は 30.1s で範囲内なので、ホールド（添字1）が start 以内に残る
    expect(win.start).toBeLessThanOrEqual(1);
    expect(win.end).toBeGreaterThan(1);
  });
});

describe('judgeWindow / isSortedByTime', () => {
  it('判定窓の前後は含み、遠いノーツは含まない', () => {
    const ns = notes([
      [0, 0],
      [10_000, 1],
      [20_000, 2],
    ]);
    const win = judgeWindow(ns, 10_000);
    expect(win).toEqual({ start: 1, end: 2 });
  });

  it('昇順判定', () => {
    expect(isSortedByTime(notes([[0, 0], [100, 1]]))).toBe(true);
    expect(isSortedByTime(notes([[100, 0], [0, 1]]))).toBe(false);
  });
});
