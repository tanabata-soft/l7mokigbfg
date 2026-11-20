import { expect, test } from '@playwright/test';

// リズムゲーム（デジタルCDエンジンのモジュール）の E2E。CD 側の画面遷移（data-view）と
// リズムゲーム側の状態（data-screen / data-song / data-difficulty / data-game）の
// 両方を見て、同居が壊れていないことを確かめる。

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#view-cover')).toBeVisible();
});

test('トップの「遊ぶ」ボタンからリズムゲーム画面に入れる', async ({ page }) => {
  await expect(page.locator('#btn-open-game')).toBeVisible();
  await page.locator('#btn-open-game').click();
  await expect(page.locator('body')).toHaveAttribute('data-view', 'game');
  await expect(page.locator('#view-game')).toBeVisible();
  await expect(page.locator('#menu-screen')).toBeVisible();
  await expect(page.locator('#view-game h1')).toHaveText('リズムゲーム');
  // 操作説明はメニューには出さない（設定の中に入れた）
  await expect(page.locator('#menu-screen')).not.toContainText('ノーツが下の枠に重なったら');
  // 収録曲2曲がカルーセルに並ぶ
  await expect(page.locator('.carousel-slide')).toHaveCount(2);
  await expect(page.locator('.carousel-slide[data-song="flavor"]')).toBeVisible();
});

test('リズムゲームでは CD 側の再生が止まる', async ({ page }) => {
  // 先に CD 側で再生を始める
  await page.locator('#btn-play-all').click();
  await expect(page.locator('body')).toHaveAttribute('data-playing', '1');
  await page.locator('#btn-home').click();
  await page.locator('#btn-open-game').click();
  await expect(page.locator('body')).toHaveAttribute('data-view', 'game');
  await expect(page.locator('body')).toHaveAttribute('data-playing', '0');
});

test('曲と難易度を選べる', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await page.locator('.carousel-slide[data-song="anata"]').click();
  await expect(page.locator('body')).toHaveAttribute('data-song', 'anata');
  await page.locator('#diff-row [data-diff="hard"]').click();
  await expect(page.locator('body')).toHaveAttribute('data-difficulty', 'hard');
  await expect(page.locator('#diff-row [data-diff="hard"]')).toHaveAttribute('aria-pressed', 'true');
  // ベストスコアは曲選択画面に、選んでいる曲・難易度のラベルつきで出る
  await expect(page.locator('#menu-best-label')).toHaveText('あなた・むずかしい のベストスコア');
  // ベストのパネルは難易度の上にある専用領域で、ランク表示の枠も持つ
  const panelBox = await page.locator('#best-panel').boundingBox();
  const diffBox = await page.locator('#diff-row').boundingBox();
  expect(panelBox).not.toBeNull();
  expect(diffBox).not.toBeNull();
  expect(panelBox!.y + panelBox!.height).toBeLessThanOrEqual(diffBox!.y);
  await expect(page.locator('#menu-best-rank')).toHaveText('—');
  // 結果カードは演奏画面の中にあり、演奏画面の上に重ねて出す構造になっている
  await expect(page.locator('#game-screen #result-screen')).toHaveCount(1);
  // ドットからも選べる
  await page.locator('.carousel-dot[data-song="flavor"]').click();
  await expect(page.locator('body')).toHaveAttribute('data-song', 'flavor');
});

test('設定ダイアログが開閉できる', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await page.locator('#settings-open').click();
  await expect(page.locator('#settings-dialog')).toBeVisible();
  // 操作説明（遊び方）は設定の中にある
  await expect(page.locator('#settings-dialog')).toContainText('遊び方');
  // ベストスコアは設定には出さない（曲選択画面のパネルで出す）
  await expect(page.locator('#settings-dialog #best-panel')).toHaveCount(0);
  // オートプレイとデバッグモードも設定には出さない（デバッグパネル側に移した）
  await expect(page.locator('#settings-dialog')).not.toContainText('オートプレイ');
  await expect(page.locator('#settings-dialog')).not.toContainText('デバッグモード');
  await expect(page.locator('#settings-dialog')).toContainText('ノーツが下の枠に重なったらタップ');
  // オフセットの増減が保存・表示される
  await page.locator('#offset-plus').click();
  await expect(page.locator('#offset-value')).toHaveText('+10ms');
  await expect(page.locator('body')).toHaveAttribute('data-offset', '10');
  // 下部の「閉じる」と版数表示は廃止した（右上の × で閉じる）
  await expect(page.locator('#settings-dialog #settings-close-bottom')).toHaveCount(0);
  await expect(page.locator('#settings-dialog .dialog-version')).toHaveCount(0);
  await page.locator('#settings-close').click();
  await expect(page.locator('#settings-dialog')).toBeHidden();
});

test('選択を変えると確認音が鳴る', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await page.evaluate(() => {
    const w = window as unknown as { __uiSounds: number; __swipeSounds: number };
    w.__uiSounds = 0;
    w.__swipeSounds = 0;
    document.addEventListener('app:sound', (e) => {
      const kind = (e as CustomEvent).detail?.kind;
      if (kind === 'ui') w.__uiSounds += 1;
      if (kind === 'swipe') w.__swipeSounds += 1;
    });
  });
  // 難易度を変えるとクリック音（ui）
  await page.locator('#diff-row [data-diff="hard"]').click();
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __uiSounds: number }).__uiSounds))
    .toBeGreaterThanOrEqual(1);
  // 曲を変えるとスワイプ音（swipe）で、クリック音は増えない
  await page.locator('.carousel-dot[data-song="anata"]').click();
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __swipeSounds: number }).__swipeSounds))
    .toBeGreaterThanOrEqual(1);
  await expect(page.evaluate(() => (window as unknown as { __uiSounds: number }).__uiSounds)).resolves.toBe(1);
});

test('ゲームが始まり、Canvas が表示され、左上タップでメニューに戻る', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await page.locator('#start-button').click();
  await expect(page.locator('#game-screen')).toBeVisible();
  await expect(page.locator('#game-canvas')).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  // 歌詞はジャケット（画面幅いっぱいの正方形）のすぐ下に出る（判定ラインより上）
  const lyricBox = await page.locator('#lyrics').evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { top: r.top, width: window.innerWidth, height: window.innerHeight };
  });
  expect(lyricBox.top).toBeGreaterThanOrEqual(lyricBox.width);
  expect(lyricBox.top).toBeLessThan(lyricBox.height * 0.82);
  // 左上の ✕ の場所をタップして中断する
  await page.locator('#game-canvas').dispatchEvent('pointerdown', { clientX: 20, clientY: 20 });
  await expect(page.locator('#menu-screen')).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'menu');
});

test('結果は演奏画面の上に重なって出て、コンボ段階がコンボ数で上がる', async ({ page }) => {
  // デバッグ API（finishNow / setCombo）を使うため ?debug=1 で開き直す
  await page.goto('/?debug=1');
  await expect(page.locator('#view-cover')).toBeVisible();
  await page.locator('#btn-open-game').click();
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  // コンボ 120 で演出段階は最上段（tier 4）
  await page.evaluate(() => {
    const api = (window as unknown as { __pwaTest?: { setCombo?: (n: number) => void } }).__pwaTest;
    api?.setCombo?.(120);
  });
  await expect(page.locator('body')).toHaveAttribute('data-combo-tier', '4');
  // いまの成績で結果へ進む: 演奏画面は出したまま、結果カードが上に重なる
  await page.evaluate(() => {
    const api = (window as unknown as { __pwaTest?: { finishNow?: () => void } }).__pwaTest;
    api?.finishNow?.();
  });
  await expect(page.locator('body')).toHaveAttribute('data-screen', 'result');
  await expect(page.locator('#game-screen')).toBeVisible();
  await expect(page.locator('#result-screen')).toBeVisible();
  await expect(page.locator('#menu-screen')).toBeHidden();
  // メニューに戻ると、ベストのパネルに今回のランクが残っている
  await page.locator('#back-button').click();
  await expect(page.locator('#menu-screen')).toBeVisible();
  await expect(page.locator('#menu-best-rank')).toHaveText(/^[SABC]$/);
});

test('リズムゲーム画面からトップへ戻れる（設定の横の「戻る」ボタン）', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await expect(page.locator('#view-game')).toBeVisible();
  await page.locator('.game-back').click();
  await expect(page.locator('body')).toHaveAttribute('data-view', 'cover');
  await expect(page.locator('#view-cover')).toBeVisible();
  // もう一度入っても、メニュー画面から始まる
  await page.locator('#btn-open-game').click();
  await expect(page.locator('#menu-screen')).toBeVisible();
});
