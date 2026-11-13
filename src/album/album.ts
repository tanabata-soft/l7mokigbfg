// この作品の基本情報と、裏面ノートの文章。
// エンジン（src/ のほかのファイル）は、このフォルダ（src/album/）のデータだけを差し替えれば
// 別の作品になるよう作られている。新しい作品の作り方は docs/PRODUCTION.md、
// シングルの仕様は docs/SINGLE.md を参照。
//
// デジタルCD制作サービス 無料モニター1件目（申込者: nami／自分用）。
// カタログ番号 NK-S009 は仮番号（モニター・受託作品の採番ルールが文書に無いため、
// 公開時に台帳で確定する。今回は非公開・プレビューまで）。

export const ALBUM: {
  title: string;
  catalog: string;
  format: string;
  layout: 'album' | 'single';
  /** 裏ジャケットに曲目リストが印刷済みなら true（裏面の重ねリストを表示しない。アルバム形態用） */
  printedBackList?: boolean;
} = {
  /** 題名（シングルでは表題曲と同名にするのが通例） */
  title: 'Flavor',
  /** カタログ番号（仮番号。docs/START-HERE.md の連番ルールに基づく） */
  catalog: 'NK-S009',
  /** 形式の呼び名 */
  format: 'デジタルシングルCD',
  /** 形: 'album'（正方形ジャケット＋ブックレット） / 'single'（短冊型ジャケット＋裏面ノート、ブックレットなし） */
  layout: 'single',
};

/** 裏ジャケット下部の表記（例: NK-S001 ／ デジタルシングルCD） */
export const FOOT_NOTE = `${ALBUM.catalog} ／ ${ALBUM.format}`;

/** 裏面ノートの本文（シングルではブックレットの代わりにジャケット裏面へ置く） */
export const NOTE: string[] = [
  '恋の甘さを歌う「Flavor」と、夜の静けさの中で相手の体温を覚えていたいと願う「あなた」。温度の違うふたつの恋の歌を、モノクロの窓辺の光と一緒に、1枚の短冊に閉じ込めた。',
  '表題曲「Flavor」は、閉ざしていた心をノックもしないで開けてしまった出会いの歌。完璧じゃないまま並んで歩く明日を、ふたりで淹れた特別な味に重ねている。',
  'カップリング「あなた」は、腕時計を外す小さな音から始まる夜の歌。忙しい日常に戻る前に、指先と唇と体温の記憶を、そっと胸の中に閉じ込めておく。',
];

/** ライナーノーツ（アルバム形態のブックレット冒頭。本文は NOTE と共通） */
export const LINER: readonly [string, string, string] = [NOTE[0], NOTE[1], NOTE[2]];

/** ライナーノーツの見出し（アルバム形態のブックレット冒頭2ページ） */
export const LINER_TITLES: readonly [string, string] = ['窓辺の光、ふたつの恋の歌', '聴き方について'];

/** ブックレット「聴き方について」のページに置く一文（アルバム形態用） */
export const HOWTO_EXTRA = '再生画面では歌詞が曲に合わせて流れます。ジャケットをめくると、裏面にノートがあります。';

/** 奥付（シングルでは裏面ノートの下部に置く） */
export const COLOPHON: string[] = [
  `『${ALBUM.title}』（全2曲／総再生時間 約6分22秒）`,
  `${ALBUM.catalog} ― ${ALBUM.format}`,
  'nami',
];
