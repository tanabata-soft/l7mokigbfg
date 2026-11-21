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

test('ゲームが始まり、Canvas が表示され、中断ボタンで確認カードが出て中断できる', async ({ page }) => {
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
  // 左上の中断ボタンをタップすると、即座には戻らず確認カードが出る（案1）
  await page.locator('#game-canvas').dispatchEvent('pointerdown', { clientX: 30, clientY: 29 });
  await expect(page.locator('#pause-screen')).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'paused');
  // 「メニューに戻る」でメニューに戻る
  await page.locator('#pause-abort-button').click();
  await expect(page.locator('#menu-screen')).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'menu');
});

test('次の曲の読み込み中に、前の曲の画面（背景）が残らない', async ({ page }) => {
  await page.goto('/?debug=1');
  await expect(page.locator('#view-cover')).toBeVisible();
  await page.locator('#btn-open-game').click();
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  await page.evaluate(() => {
    const api = (window as unknown as { __pwaTest?: { finishNow?: () => void } }).__pwaTest;
    api?.finishNow?.();
  });
  await expect(page.locator('#result-screen')).toBeVisible();
  // キャンバス右上（スコア表示域）の最大輝度。前の演奏の最終フレームには白いスコアが残る
  const stripMax = (): Promise<number> =>
    page.evaluate(() => {
      const c = document.getElementById('game-canvas') as HTMLCanvasElement;
      const t = document.createElement('canvas');
      t.width = c.width;
      t.height = c.height;
      const ctx = t.getContext('2d')!;
      ctx.drawImage(c, 0, 0);
      const x0 = Math.floor(c.width * 0.72);
      const y0 = Math.floor(c.height * 0.015);
      const d = ctx.getImageData(x0, y0, c.width - x0, Math.floor(c.height * 0.05)).data;
      let max = 0;
      for (let i = 0; i < d.length; i += 4) max = Math.max(max, d[i], d[i + 1], d[i + 2]);
      return max;
    });
  expect(await stripMax()).toBeGreaterThan(200);
  // 次の曲の音声読み込みを遅らせて、読み込み中の画面を見る
  await page.route('**/*.mp3', async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await page.locator('#next-button').click();
  await page.waitForTimeout(400);
  // 読み込み中は地の色で消えていて、前の曲の画面は残っていない
  expect(await stripMax()).toBeLessThan(64);
  // 読み込みが終われば通常どおり始まる
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
});

test('演奏が終わるとジングルが鳴ってから結果が出る', async ({ page }) => {
  await page.goto('/?debug=1');
  await expect(page.locator('#view-cover')).toBeVisible();
  await page.locator('#btn-open-game').click();
  await page.evaluate(() => {
    const w = window as unknown as { __jingleRank: string };
    w.__jingleRank = '';
    document.addEventListener('app:sound', (e) => {
      const d = (e as CustomEvent).detail as { kind?: string; rank?: string };
      if (d?.kind === 'jingle') w.__jingleRank = d.rank ?? '?';
    });
  });
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  await page.evaluate(() => {
    const api = (window as unknown as { __pwaTest?: { finishNow?: () => void } }).__pwaTest;
    api?.finishNow?.();
  });
  // ジングルが鳴っている間は、結果はまだ出ない（何も叩いていないのでランクは C）
  await page.waitForTimeout(350);
  await expect(page.locator('#result-screen')).toBeHidden();
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __jingleRank: string }).__jingleRank))
    .toBe('C');
  // ジングルが終わると結果が出る
  await expect(page.locator('#result-screen')).toBeVisible({ timeout: 5_000 });
});

test('次の曲の読み込み中に、前の曲の歌詞が残らない', async ({ page }) => {
  await page.goto('/?debug=1');
  await expect(page.locator('#view-cover')).toBeVisible();
  await page.locator('#btn-open-game').click();
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  // 歌詞が出るまで待つ
  await expect(page.locator('#lyric-current')).not.toHaveText('', { timeout: 25_000 });
  await page.evaluate(() => {
    const api = (window as unknown as { __pwaTest?: { finishNow?: () => void } }).__pwaTest;
    api?.finishNow?.();
  });
  await expect(page.locator('#result-screen')).toBeVisible({ timeout: 10_000 });
  // 次の曲の読み込みを遅らせて、読み込み中の歌詞表示を確かめる
  await page.route('**/*.mp3', async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await page.locator('#next-button').click();
  await page.waitForTimeout(400);
  await expect(page.locator('#lyric-prev')).toHaveText('');
  await expect(page.locator('#lyric-current')).toHaveText('');
  await expect(page.locator('#lyric-next')).toHaveText('');
});

test('曲を変えるとメニューの背景ジャケットも即座に切り替わる', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await expect(page.locator('#menu-screen')).toBeVisible();
  const bgImage = (): Promise<string> =>
    page.evaluate(() => getComputedStyle(document.getElementById('menu-bg')!).backgroundImage);
  const slideFile = (song: string): Promise<string> =>
    page.evaluate(
      (s) =>
        document
          .querySelector(`.carousel-slide[data-song="${s}"] img`)!
          .getAttribute('src')!
          .split('/')
          .pop()!,
      song,
    );
  // 初期表示の背景は選択中の曲（先頭）のジャケット
  await expect.poll(async () => (await bgImage()).includes(await slideFile('flavor'))).toBe(true);
  // ドットで別の曲へ: 背景も遅延なくその曲のジャケットになる（前の曲が残らない）
  await page.locator('.carousel-dot[data-song="anata"]').click();
  await expect(page.locator('body')).toHaveAttribute('data-song', 'anata');
  await expect
    .poll(async () => (await bgImage()).includes(await slideFile('anata')), { timeout: 1_000 })
    .toBe(true);
});

test('中断確認の「つづける」で、止めた位置から再開する', async ({ page }) => {
  await page.goto('/?debug=1');
  await expect(page.locator('#view-cover')).toBeVisible();
  await page.locator('#btn-open-game').click();
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  const songMs = (): Promise<number> =>
    page.evaluate(
      () =>
        (window as unknown as { __pwaTest: { getGameState: () => { songMs: number } } }).__pwaTest.getGameState()
          .songMs,
    );
  // 曲が少し進んでから止める
  await expect.poll(songMs, { timeout: 30_000 }).toBeGreaterThan(300);
  await page.locator('#game-canvas').dispatchEvent('pointerdown', { clientX: 30, clientY: 29 });
  await expect(page.locator('body')).toHaveAttribute('data-game', 'paused');
  const frozen = await songMs();
  expect(frozen).toBeGreaterThan(300);
  // 凍結中は位置が進まない
  await page.waitForTimeout(400);
  expect(await songMs()).toBe(frozen);
  // 「つづける」→ READY（約1秒）をはさんで再開し、止めた位置から進む
  await page.locator('#pause-resume-button').click();
  await expect(page.locator('#pause-screen')).toBeHidden();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 5_000 });
  await expect.poll(songMs, { timeout: 5_000 }).toBeGreaterThan(frozen);
});

test('アプリ切替（画面が隠れる）と中断確認が出て、演奏は進まない', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(page.locator('#pause-screen')).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'paused');
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  // 戻ってきてもカードは開いたまま。ここでは中断してメニューへ
  await expect(page.locator('#pause-screen')).toBeVisible();
  await page.locator('#pause-abort-button').click();
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

test('結果画面の「次の曲」で、難易度そのまま次の曲が始まる', async ({ page }) => {
  // 結果へすぐ進めるよう、デバッグ API（finishNow）を使うため ?debug=1 で開き直す
  await page.goto('/?debug=1');
  await expect(page.locator('#view-cover')).toBeVisible();
  await page.locator('#btn-open-game').click();
  // 1曲目（flavor）を難易度「むずかしい」で演奏する
  await page.locator('.carousel-slide[data-song="flavor"]').click();
  await expect(page.locator('body')).toHaveAttribute('data-song', 'flavor');
  await page.locator('#diff-row [data-diff="hard"]').click();
  await expect(page.locator('body')).toHaveAttribute('data-difficulty', 'hard');
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  await page.evaluate(() => {
    const api = (window as unknown as { __pwaTest?: { finishNow?: () => void } }).__pwaTest;
    api?.finishNow?.();
  });
  await expect(page.locator('body')).toHaveAttribute('data-screen', 'result');
  await expect(page.locator('#result-screen')).toBeVisible();
  await expect(page.locator('#next-button')).toBeVisible();
  // 「次の曲」: メニューを経由せず、2曲目（anata）が同じ難易度で始まる
  await page.locator('#next-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  await expect(page.locator('body')).toHaveAttribute('data-screen', 'game');
  await expect(page.locator('body')).toHaveAttribute('data-song', 'anata');
  await expect(page.locator('body')).toHaveAttribute('data-difficulty', 'hard');
  await expect(page.locator('#result-screen')).toBeHidden();
});

test('最後の曲の結果で「次の曲」を押すと先頭の曲に戻る', async ({ page }) => {
  await page.goto('/?debug=1');
  await expect(page.locator('#view-cover')).toBeVisible();
  await page.locator('#btn-open-game').click();
  // 最後の曲（anata）を選んで演奏する
  await page.locator('.carousel-dot[data-song="anata"]').click();
  await expect(page.locator('body')).toHaveAttribute('data-song', 'anata');
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  await page.evaluate(() => {
    const api = (window as unknown as { __pwaTest?: { finishNow?: () => void } }).__pwaTest;
    api?.finishNow?.();
  });
  await expect(page.locator('body')).toHaveAttribute('data-screen', 'result');
  // 「次の曲」: 先頭の曲（flavor）に回って演奏が始まる
  await page.locator('#next-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  await expect(page.locator('body')).toHaveAttribute('data-song', 'flavor');
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

test('プレイ中の「戻る」（端スワイプ）では閉じずに中断確認が出て、退出後は履歴が掃除される', async ({ page }) => {
  await page.locator('#btn-open-game').click();
  await expect(page.locator('#menu-screen')).toBeVisible();
  // ゲームモード中は、端スワイプ対策の履歴ガードが積まれている
  await expect
    .poll(() => page.evaluate(() => (history.state as { rhythmGameGuard?: boolean } | null)?.rhythmGameGuard))
    .toBe(true);
  await page.locator('#start-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  // ブラウザの「戻る」＝ Android の端スワイプ「戻る」
  await page.goBack();
  // アプリは閉じず、ゲーム画面に留まって、中断の確認カードが出る（案1で統一）
  await expect(page.locator('body')).toHaveAttribute('data-view', 'game');
  await expect(page.locator('body')).toHaveAttribute('data-game', 'paused');
  await expect(page.locator('#pause-screen')).toBeVisible();
  // 「メニューに戻る」でメニューに戻る
  await page.locator('#pause-abort-button').click();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'menu');
  await expect(page.locator('#menu-screen')).toBeVisible();
  // ガードは積み直されているので、もう一度「戻る」を押しても閉じない
  await expect
    .poll(() => page.evaluate(() => (history.state as { rhythmGameGuard?: boolean } | null)?.rhythmGameGuard))
    .toBe(true);
  await page.goBack();
  await expect(page.locator('body')).toHaveAttribute('data-view', 'game');
  await expect(page.locator('#menu-screen')).toBeVisible();
  // 本当にやめる（メニュー下部の「戻る」ボタン）とトップへ戻り、履歴ガードは掃除される
  await page.locator('.game-back').click();
  await expect(page.locator('body')).toHaveAttribute('data-view', 'cover');
  await expect.poll(() => page.evaluate(() => history.state)).toBeNull();
});

test('広い画面ではプレイ画面がスマホ比率のステージになる（案B）', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.locator('#btn-open-game').click();
  await page.locator('#start-button').click();
  await expect(page.locator('#game-screen')).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-game', 'playing', { timeout: 30_000 });
  const box = await page.locator('#game-screen').boundingBox();
  expect(box).not.toBeNull();
  // ステージは高さいっぱい、幅は高さ × 390/844、左右中央に置かれる
  expect(Math.abs(box!.height - 800)).toBeLessThanOrEqual(1);
  expect(Math.abs(box!.width - (800 * 390) / 844)).toBeLessThanOrEqual(2);
  expect(Math.abs(box!.x - (1280 - box!.width) / 2)).toBeLessThanOrEqual(2);
  expect(Math.abs(box!.y)).toBeLessThanOrEqual(1);
  // 歌詞はステージ内のジャケット（ステージ幅の正方形）のすぐ下に出る
  const lyric = await page.locator('#lyrics').evaluate((el) => {
    const stage = document.querySelector('#game-screen')!.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    return { relTop: r.top - stage.top, stageWidth: stage.width, stageHeight: stage.height };
  });
  expect(lyric.relTop).toBeGreaterThanOrEqual(lyric.stageWidth);
  expect(lyric.relTop).toBeLessThan(lyric.stageHeight * 0.82);
});
