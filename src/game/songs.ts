// リズムゲームの収録曲リスト（作品データ。ここは作品ごとに書き換える場所で、
// エンジン側の部品ではない。CD 側の作品データが src/album/ にあるのと同じ考え方）。
//
// 1曲ごとに決めるもの:
// - id: 曲 ID（半角英数の短い名前。譜面・歌詞データのキーになる。公開後に変えない）
// - audioUrl / jacketUrl: 音源とジャケット。音源は制作入口で用意した唯一の
//   正規音源 MP3 192kbps（src/game/assets/track0N.mp3。CD 側プレイヤーも
//   同じ音源を src/album/assets/audio/track0N.mp3 として参照し、ビルドでは
//   内容が同一のため dist 上は1ファイルにまとまる）、ジャケットは
//   CD 側の曲ジャケット（1024×1024）のコピー。作り方はデジタルCDエンジン
//   （mmishina-art/digitalcd-engine）docs/PRODUCTION.md の
//   「リズムゲーム（任意モジュール）」参照
// - frameInset: ジャケット絵の四辺に焼き込まれた紙枠の幅（実画像ピクセル、絵は
//   1024×1024）。演奏画面の背景では、この枠を除いた内側の絵だけを敷く。
//   枠が無い絵は 0
// - slidePosition: メニューのカルーセルでジャケットを寄せる位置（CSS の
//   object-position）。絵の中の曲タイトルができるだけ収まる側へ寄せる。
//   未指定なら中央
// - accent: 曲のテーマ色（#rrggbb）。メニューの枠・光・ボタンなどのアクセント色
//   として、選曲に合わせて切り替わる（オーナー決定 2026-11-20 のパターン3）。
//   ジャケットから scripts/jacket-accent.py で抜き出すのが基本（視認性のために
//   明度・彩度を持ち上げる処理込み）
// - bonus: ボーナストラックなら true（CD 側 tracks.ts の bonus と一致させる）。
//   スライドの先頭に金色の BONUS チップが出る。本作はボーナストラックなし
// - album: 収録アルバム名（表示用） / genre: ジャンル（表示用）
//
// 本作の accent について: 2曲ともモノクロ写真のジャケットで、平均彩度が
// ほぼ 0 のため、色相はスクリプトの無彩色フォールバックでは決められない。
// ライナーノーツの言葉「温度の違うふたつの恋の歌」に沿って、Flavor は
// 朝の窓辺の温かみ（アンバー）、あなた は夜の静けさ（シルバーブルー）を
// 手で選んだ。
// テーマ方式はオーナーが本作で評価中（2026-11-20）: 本作はパターン3
// （曲ごとに切り替え）で公開し、実機の感触で固定方式と比べて決める。
//
// 譜面（data/charts.json）と歌詞（data/lyrics.json）は生成物なので、ここには
// 書かない。生成手順はデジタルCDエンジンの docs/PRODUCTION.md 参照。
// このモジュールはデジタルCDエンジン v1.2.2 のリズムゲーム（任意モジュール）を
// 取り込んだもの（2026-11-20、NK-S002・NK-S007 への適用と同じ手順）。
import track01Audio from './assets/track01.mp3';
import track01Jacket from './assets/track01.jpg';
import track02Audio from './assets/track02.mp3';
import track02Jacket from './assets/track02.jpg';

export interface GameSongDef {
  id: string;
  audioUrl: string;
  jacketUrl: string;
  frameInset: number;
  slidePosition?: string;
  accent: string;
  bonus?: boolean;
  album: string;
  genre: string;
}

export const SONG_DEFS: GameSongDef[] = [
  {
    id: 'flavor',
    audioUrl: track01Audio,
    jacketUrl: track01Jacket,
    frameInset: 0,
    // ジャケットがモノクロ（窓辺の光）で色味が無いため、ライナーノーツの
    // 「温度の違うふたつの恋の歌」に合わせて朝の光の暖色を手で決めた
    accent: '#d2ab89',
    album: 'NK-S009 Flavor',
    genre: 'Pop Ballad',
  },
  {
    id: 'anata',
    audioUrl: track02Audio,
    jacketUrl: track02Jacket,
    frameInset: 0,
    // 同じくモノクロのため、夜の静けさの冷たい銀色を手で決めた
    accent: '#a4b4cc',
    album: 'NK-S009 Flavor',
    genre: 'R&B Ballad',
  },
];
