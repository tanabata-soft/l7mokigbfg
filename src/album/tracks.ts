// 曲目と解説（この作品のデータ）。src は歌詞データ（src/album/sync.ts）のキー。
// 並びが曲順。シングルでは1曲目が表題曲、2曲目がカップリング（docs/SINGLE.md）。
// time は支給音源の実測（末尾の無音を詰めた後の長さ）に合わせた。
import type { TrackMeta } from '../logic';

export const TRACKS: TrackMeta[] = [
  { src: 'Flavor', title: 'Flavor', genre: 'Pop Ballad', time: '2:49', note: '甘くて、少しだけ切ない。閉ざしていた心を開けた出会いを、ふたりで淹れた特別な味に重ねた表題曲。' },
  { src: 'あなた', title: 'あなた', genre: 'R&B Ballad', time: '3:33', note: '腕時計を外す小さな音から始まる、静かな夜の歌。朝が来る前に、指先と体温の記憶を閉じ込めるカップリング。' },
];
