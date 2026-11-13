# モニター申し込みフォーム ― 自動受付メール（Apps Script）

**【2026-11-12 実測で不採用】** コードとトリガーの設定までは進んだが、承認の段で「エラー 400: policy_enforced」によりブロックされた。オーナーの Google アカウントは「高度な保護機能プログラム」に登録されており、Google 未確認の自作アプリ（Gmail 送信スコープ）は承認できない。高度な保護機能を切るのは本末転倒なので、この方式は採らない。下のコードと手順は、将来アカウント条件が変わった場合の参考として残す。
**代替方式**: 受付メールは Muse 側で送る（フォーム回答の定期チェックで検知 → 受付メールを送信）か、フォーム標準の「回答のコピーを常に送信」で最低限の受付確認を自動化する。

申し込みと同時に、申込者へ受付メールを自動送信する仕組み。フォーム標準機能には文面つき自動返信がないため、フォームに紐づく Apps Script で実現する（2026-11-12 オーナー決定）。
スクリプトはオーナーの Google アカウントで動き、送信元はオーナーの Gmail。オーナー宛てに BCC で控えも届くので、申し込みの検知も兼ねる。

## コード（Code.gs に全文を貼る）

```javascript
// デジタルCD制作モニター 申し込みフォーム 自動受付メール
// 直すのはこの CONFIG だけ
const CONFIG = {
subject: 'お申し込みを受け付けました',
signature: 'デジタルCD制作モニター 受付担当',
ownerEmail: 'm.mishina@gmail.com', // 控え（BCC）を受け取る自分のアドレス
};

function onFormSubmit(e) {
const data = {}; // 質問タイトル -> 回答テキスト
const files = {}; // 質問タイトル -> アップロードファイル数
e.response.getItemResponses().forEach(function (ir) {
const item = ir.getItem();
const title = item.getTitle();
const resp = ir.getResponse();
if (item.getType() === FormApp.ItemType.FILE_UPLOAD) {
files[title] = Array.isArray(resp)? resp.length: 0;
} else {
data[title] = Array.isArray(resp)? resp.join('、'): String(resp);
}
});

const find = function (obj, prefix) {
for (const key in obj) {
if (key.indexOf(prefix) === 0) return obj[key];
}
return '';
};

const email = find(data, '連絡先メールアドレス');
if (!email) return; // 宛先が取れなければ送らない
const name = find(data, 'お名前') || 'お客様';
const format = find(data, '希望する形態');
const kind = find(data, '曲の種類');
const fileLine = function (prefix) {
const n = find(files, prefix);
return n? '受領しました（' + n + ' ファイル）': '未受領';
};

const body = [
name + ' 様',
'',
'このたびは「デジタルCD制作サービス」の無料モニターにお申し込みいただき、ありがとうございます。',
'以下の内容で受け付けました。',
'',
'■ お申し込み内容',
'・希望する形態: ' + format,
'・曲の種類: ' + kind,
'',
'■ 素材の受領状況',
'・表題曲のファイル: ' + fileLine('表題曲のファイル'),
'・カップリング曲のファイル: ' + fileLine('カップリング曲のファイル'),
'・ボーナストラックのファイル: ' + fileLine('ボーナストラックのファイル'),
'・ジャケットデータ: ' + fileLine('ジャケットデータ'),
'',
'内容を確認のうえ、数日以内にこのメールアドレス宛てに次のご案内をお送りします。',
'素材がまだの場合は、用意の仕方をご案内しますのでご安心ください。',
'',
'※このメールは自動送信です。お心当たりのない場合は破棄してください。',
'ご質問は、このメールへの返信でお受けしています。',
'',
CONFIG.signature,
].join('\n');

MailApp.sendEmail({
to: email,
bcc: CONFIG.ownerEmail,
subject: CONFIG.subject,
body: body,
name: CONFIG.signature,
});
}
```

## 設定手順（オーナーが1回だけ）

1. 申し込みフォームの編集画面を開く
2. 右上の「︙」（その他のオプション）→「スクリプト エディタ」
3. 最初から入っているコードを全部消し、上記のコードを貼って保存（プロジェクト名は任意。例: 受付メール）
4. 左端の時計アイコン「トリガー」→ 右下「トリガーを追加」
- 実行する関数: `onFormSubmit`
- イベントの発生源: 「フォームから」
- イベントの種類: 「送信時」
- 保存
5. 承認を求められたら進める（自分のスクリプトなので安全）: アカウント選択 →「このアプリは Google で確認されていません」と出たら「詳細」→「（プロジェクト名）に移動」→「許可」
6. テスト: 自分のメールアドレスで1回テスト申し込みをして、受付メールと BCC の控えが届けば完了

## 注意

- 送信通数の上限は Google アカウントの制限に従う（通常の Gmail で1日100通まで。モニター3〜5組なら問題なし）
- 質問のタイトルを変えると、コード側の前方一致（「連絡先メールアドレス」「お名前」など）も合わせる必要がある
- 屋号・署名を決めたら CONFIG の signature を差し替える
