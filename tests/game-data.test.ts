import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { SONGS } from '../src/game/charts';
import { validateCharts, type LyricLine } from '../src/game/logic';

// リズムゲームのデータ（譜面 charts.json / 歌詞 lyrics.json）の整合を担保する。
// 譜面は scripts/generate-charts.py の生成物、歌詞は CD 側の検証済み歌詞同期
// データ（src/album/sync.ts）から scripts/gen-game-lyrics.mjs が変換したもの。

describe('リズムゲームの曲データ', () => {
  it('収録曲は2曲で、CD 側の曲順・曲名とそろっている', () => {
    expect(SONGS.map((s) => s.id)).toEqual(['flavor', 'anata']);
    expect(SONGS.map((s) => s.data.title)).toEqual(['Flavor', 'あなた']);
  });

  it('全曲の譜面が検証を通る（昇順・レーン・長押し・難易度ごとのノーツ数）', () => {
    for (const entry of SONGS) {
      expect(validateCharts(entry.data), entry.id).toEqual([]);
    }
  });

  it('テーマ色は全曲に #rrggbb で入っている', () => {
    for (const entry of SONGS) {
      expect(entry.accent, entry.id).toMatch(/^#[0-9a-f]{6}$/);
      expect(entry.accentRgb, entry.id).toMatch(/^\d{1,3} \d{1,3} \d{1,3}$/);
      expect(typeof entry.bonus, entry.id).toBe('boolean');
    }
  });

  it('歌詞は全曲にあり、行が昇順で、尺の範囲内にある', () => {
    const raw = JSON.parse(
      readFileSync(new URL('../src/game/data/lyrics.json', import.meta.url), 'utf8'),
    ) as Record<string, LyricLine[]>;
    for (const entry of SONGS) {
      const lines = raw[entry.id];
      expect(lines, entry.id).toBeDefined();
      expect(lines.length).toBeGreaterThan(0);
      expect(entry.lyrics.length).toBe(lines.length);
      let prevStart = -1;
      for (const line of lines) {
        expect(line.text.trim()).not.toBe('');
        expect(line.startMs).toBeGreaterThan(prevStart);
        expect(line.endMs).toBeGreaterThan(line.startMs);
        expect(line.startMs).toBeLessThan(entry.data.durationMs);
        expect(line.endMs).toBeLessThanOrEqual(entry.data.durationMs);
        prevStart = line.startMs;
      }
    }
  });

  it('歌詞の行数と開始時刻が、CD 側の歌詞同期データ（sync.ts）と一致する', () => {
    const syncText = readFileSync(new URL('../src/album/sync.ts', import.meta.url), 'utf8');
    const objStart = syncText.indexOf('{', syncText.indexOf('='));
    const sync = JSON.parse(
      syncText.slice(objStart, syncText.lastIndexOf('}') + 1).replace(/,\s*([}\]])/g, '$1'),
    ) as Record<string, [number, string][]>;
    const idByTitle: Record<string, string> = {
      Flavor: 'flavor',
      あなた: 'anata',
    };
    for (const [title, lines] of Object.entries(sync)) {
      const entry = SONGS.find((s) => s.id === idByTitle[title]);
      expect(entry, title).toBeDefined();
      expect(entry?.lyrics.map((l) => [l.startMs, l.text])).toEqual(
        lines.map(([sec, text]) => [Math.round(sec * 1000), text]),
      );
    }
  });
});
