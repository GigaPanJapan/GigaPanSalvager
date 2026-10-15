# GigaPan Salvager

GigaPan の公開パノラマを ID または URL で指定し、全解像度の画像タイルと公開資料を手元に保存するツールです。

**[ウェブ画面を開く](https://mapconcierge.github.io/GigaPanSalvager/)** · [救出ジョブ](https://github.com/mapconcierge/GigaPanSalvager/actions/workflows/salvage.yml)

GitHub Pages が画面を配信し、GitHub Actions が画像を取得します。追加サーバーやブラウザへのアクセストークン入力は不要です。配信元が応答しない間は救出できません。欠損を記録し、再実行で続きを取得できます。

## ウェブから使う

1. GigaPan ID（例：`76564`）または URL を入力します。
2. 「GitHub で救出依頼を作成」で依頼内容を確認し、GitHub の **Create new issue** を押します。
3. Issue に届く結果、または「最近の救出ジョブ」から実行ページを開きます。
4. **Artifacts** をダウンロードし、中の `gigapan_ID.tar.gz` を展開します。保存期限は **30日** です。
5. `viewer.html` をブラウザで開きます。Google Earth 用 KML と `ge_tiles/` は一緒に保管してください。

実行できるのは、そのリポジトリの所有者と書き込み権限のある共同編集者です。GitHub へのログインが必要です。一般の訪問者は自分のリポジトリへ Fork して利用できます。依頼・実行ログ・保存成果物は公開リポジトリ上の公開情報として扱ってください。

Actions の **Salvage GigaPan → Run workflow** から直接実行することもできます。

- `full`: 全階層の画像と取得可能な公開資料を保存。
- `probe`: 公開資料と最小解像度のタイル1枚だけで通信確認。全画像の保存ではありません。
- `width` / `height`: API 停止時の補助寸法。通常は空欄で構いません。ウェブ画面では KML から寸法を読み取れます。**ウェブでは KML 本文は送信しません**。元 KML を確実に引き継ぐにはローカル版の `--kml` を使用してください。

## 保存するもの

| ファイル | 内容 |
| --- | --- |
| `tiles/` | 公開されている各解像度の JPEG。配信元の四分木構造を保持 |
| `ge_tiles/` | Google Earth 用の level/y/x 構造。同じ画像へのハードリンク |
| `metadata/` | API JSON、HTML、KML、スナップショット一覧・コメントなどの取得できた原本と正規化版 |
| `thumbnails/` | パノラマとスナップショットの公開サムネイル |
| `gigapan_ID_offline.kml` | オフライン画像を参照する KML。原本があれば画像参照だけ差し替え、CDATA・日本語・名前空間を保持 |
| `viewer.html` / `preview.jpg` | 外部ライブラリ不要の拡大ビューア・完全に取得できた低解像度層のプレビュー |
| `tile_manifest.csv` | 全タイルの座標、取得 URL、バイト数、SHA-256、検証結果 |
| `missing_tiles.json` / `audit.json` | 未取得一覧と検証結果 |
| `metadata/retrieval_log.json` | 取得元・取得時刻・失敗の履歴 |

`complete` は **計算上必要な全タイルの JPEG 検証が通った状態**です。メタデータ・スナップショット・コメントの完全性までは保証しません。取得できない資料はログに残します。画像寸法は公開 JSON または KML から読み、全階層の必要座標を列挙します。保存済み画像も全画素の読み取りと、前回記録がある場合は SHA-256 を確認します。

KML は取得できた原本を優先します。原本がなくても API の位置・画角が得られれば生成します。必要情報がなければ生成せず、警告を記録します。元の撮影素材、非公開画像、アカウント限定の内容は対象外です。HTML 原本は閲覧用に書き換えないため、外部サイト参照を含みます。

## ローカルで使う

Python 3.10 以降。専用の仮想環境を推奨します。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install git+https://github.com/mapconcierge/GigaPanSalvager.git
gigapan-salvage 76564
```

```sh
# URL で指定
gigapan-salvage https://gigapan.com/gigapans/76564

# KML を引き継ぐ（文字・CDATA・名前空間を保持）
gigapan-salvage 76564 --kml original.kml

# 途中再開：同じ保存先で、同じコマンドを再実行
gigapan-salvage 76564 --output archives

# 保存済みファイルをネット接続なしで再検証・再梱包
gigapan-salvage 76564 --output archives --offline

# 通信確認
gigapan-salvage 76564 --probe
```

終了コードは `0` が全タイル検証完了（または通信確認1枚成功）、`2` が一部未取得、`1` が寸法取得不能などです。`--probe` の状態は常に `probe` で、全画像保存完了とは区別されます。レポートとアーカイブは可能な範囲で失敗時にも残します。

### 再実行・制限

- 1回あたり既定で最大 **250,000 タイル**、新規タイル転送 **8 GiB**、同時取得 **6**。ローカルでは `--max-tiles`、`--max-bytes`、`--workers` で変更できます。
- Actions は **120分**。配信元の応答速度・ランナーの空き容量によって先に終了することがあります。
- 429 / 503 応答は Retry-After を考慮し、通信失敗は上限付きで再試行。30回連続のタイル失敗で新規取得を止めます。
- HTTPS を優先し、旧配信元の HTTP も試します。記録された SHA-256 は保存後の破損検出用であり、配信元の真正性の証明ではありません。
- Actions はタイルが **4 GiB 未満**ならキャッシュに途中経過を保存します。キャッシュは GitHub の容量制限や期限で削除されるため、再開を保証しません。手元へダウンロードして保管してください。
- 大きなパノラマの継続保存にはローカル版が向いています。中断時点やディスク不足によってはアーカイブ作成前に終了しますが、タイルは個別に保存されます。
- 同じ出力フォルダのメタデータは再利用します。更新されたコメントなどを取得し直す場合は新しい出力フォルダを指定してください。

## 自分の GitHub Pages に設置

1. このリポジトリを Fork し、Actions を有効にします。
2. `web/config.json` の `repository` を `所有者/リポジトリ名` に変更します。
3. Settings → Pages → Build and deployment → Source を **GitHub Actions** にします。
4. **Publish Pages** ワークフローを実行します。
5. 公開画面から依頼を作るか、**Salvage GigaPan** を手動実行します。

ジョブの入力はデータとして検証し、シェルのコードには埋め込みません。取得先は GigaPan の既知の公開ホストに限定しています。Issue の投稿者について、実行開始前に所有者・書き込み権限を確認します。

## 開発・検証

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
node --test tests/web.test.mjs
python -m http.server 8080 --directory web
```

小さな仮想パノラマを使い、完全取得・欠損・再開・通信停止・改変検出・KML のバイト保持・依頼権限を検証しています。ID 76564 の保存済み 12,053 タイルでもオフライン検証・梱包を確認しています。テスト用の大きな画像群はリポジトリに含めていません。

## 権利・出典

コードは [MIT License](LICENSE)。GigaPan 非公式のツールです。保存した写真・説明・コメントの権利は各著作者に帰属します。公開されていることは自由な再配布を意味しません。元資料のライセンス表記を確認してください。

画面の保存例は [GigaPan 76564](https://gigapan.com/gigapans/76564)、Taichi FURUHASHI 撮影。元資料の表記は **CC-by-SA 2.1 by Taichi** です。この表記をそのまま保存しています。ソフトウェアの MIT ライセンスは写真には適用されません。
