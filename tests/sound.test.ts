import { describe, expect, it } from 'vitest';
import { FLICK_SAMPLE, FLICK_SAMPLE_DURATION_SEC, GAME_OVER_WAIT_MS, MISS_MIN_INTERVAL_MS, flickSampleToneFor, missSoundDue, missToneFor, resultJingleDurationMs } from '../src/game/sound';
import { hitPitchMultiplier } from '../src/game/logic';

describe('結果発表ジングル（素材ファイルへの差し替え後）', () => {
  it('結果カードを出すまでの待ち時間は、差し替え前の合成ジングルと同じ', () => {
    // 旧合成ジングルの長さ: 通常は最後の和音が 0.56+0.62=1.18 秒で消え +80ms、
    // S ランクはきらめき分だけ和音が遅れて 0.78+0.62=1.40 秒 +80ms
    expect(resultJingleDurationMs('A')).toBe(1260);
    expect(resultJingleDurationMs('B')).toBe(1260);
    expect(resultJingleDurationMs('C')).toBe(1260);
    expect(resultJingleDurationMs('S')).toBe(1480);
  });

  it('S ランクだけ待ち時間が長い（旧合成できらめきが入っていた名残）', () => {
    expect(resultJingleDurationMs('S')).toBeGreaterThan(resultJingleDurationMs('A'));
  });
});

describe('ゲームオーバー音（素材ファイル）', () => {
  it('結果カードを出すまでの待ち時間は、素材（3.0秒）の頭が聞き取れる長さ', () => {
    expect(GAME_OVER_WAIT_MS).toBe(1500);
    expect(GAME_OVER_WAIT_MS).toBeGreaterThan(0);
    expect(GAME_OVER_WAIT_MS).toBeLessThan(3000);
  });
});

describe('フリック音（H2 サンプル）', () => {
  it('素材は 0.35 秒で、PERFECT はレート 1（素材そのままの音）', () => {
    expect(FLICK_SAMPLE_DURATION_SEC).toBe(0.35);
    expect(FLICK_SAMPLE.perfect.rate).toBe(1);
    expect(flickSampleToneFor('perfect', 0).rate).toBe(1);
  });

  it('GREAT は −1 半音、GOOD は −2 半音が基準（PERFECT が原音に一番近い）', () => {
    expect(flickSampleToneFor('great', 0).rate).toBeCloseTo(Math.pow(2, -1 / 12));
    expect(flickSampleToneFor('good', 0).rate).toBeCloseTo(Math.pow(2, -2 / 12));
    const perfect = flickSampleToneFor('perfect', 0).rate;
    const great = flickSampleToneFor('great', 0).rate;
    const good = flickSampleToneFor('good', 0).rate;
    expect(perfect).toBeGreaterThan(great);
    expect(great).toBeGreaterThan(good);
  });

  it('PERFECT が最も大きく、GOOD が最も小さい（音量は素材ピーク 0.7 に対するゲイン）', () => {
    const perfect = flickSampleToneFor('perfect', 0);
    const great = flickSampleToneFor('great', 0);
    const good = flickSampleToneFor('good', 0);
    expect(perfect.peak).toBeGreaterThan(great.peak);
    expect(great.peak).toBeGreaterThan(good.peak);
    for (const tone of [perfect, great, good]) {
      expect(tone.peak).toBeGreaterThan(0);
      expect(tone.peak).toBeLessThanOrEqual(1);
    }
  });

  it('tier でレートが hitPitchMultiplier の規則どおり上がる（音量は不変）', () => {
    const base = flickSampleToneFor('perfect', 0);
    const tier2 = flickSampleToneFor('perfect', 2);
    expect(tier2.rate).toBeCloseTo(base.rate * hitPitchMultiplier(2));
    expect(tier2.peak).toBe(base.peak);
    // GOOD でも tier の倍率は基準レートにそのまま重なる
    expect(flickSampleToneFor('good', 2).rate).toBeCloseTo(FLICK_SAMPLE.good.rate * hitPitchMultiplier(2));
    expect(flickSampleToneFor('good', 2).peak).toBe(FLICK_SAMPLE.good.peak);
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
