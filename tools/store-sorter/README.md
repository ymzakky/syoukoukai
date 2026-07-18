# 店舗名マッチング・画像ファイル自動振り分けツール

Excel の店舗名マスターと、フォルダ内の画像ファイル名を照合（類似検索）し、
店舗ごとにフォルダを作成して画像を自動振り分けする Windows 向けデスクトップアプリです。
表記の揺れや打ち間違いを許容し、ユーザー確認を経て確実にファイル移動を行います。

## 対応フロー

1. **Excel を開く** — 店舗名マスターの Excel（`.xlsx` / `.xlsm`）を選択します。
   選択した Excel と同じフォルダが、画像の走査・振り分け先になります。
2. **照合する列を選ぶ** — 1 行目（ヘッダー）から、店舗名が入った列を選びます。
   （複数シートがある場合はシートも選べます）
3. **解析開始** — 画像ファイル名の先頭（`_` より前）を店舗名として抽出し、
   マスターと類似度照合して「確定済み／曖昧／不明」に分類します。
   サムネイル生成・照合はバックグラウンドで実行され、進捗が表示されます。
4. **確認・修正** — 一覧で各行を確認します。
   - **確定済み（緑）**: フォルダ名を確認（必要なら修正）。
   - **曖昧（黄）**: 候補を採用するか（はい／いいえ）を選び、必要なら手入力。
   - **不明（赤）**: 正しい店舗名（フォルダ名）を入力。
   - サムネイルをクリックすると別ウィンドウで拡大表示します。
   - しきい値スライダーを変えて「再分類」で判定を調整できます。
5. **振り分け実行（OK）** — 確認ダイアログの後、店舗名フォルダを作成して画像を移動します。
   完了後に「移動／スキップ／失敗」の件数を表示します。

## 画像ファイルの命名規則

`[店舗名]_[任意の文字列].[拡張子]`（例: `たこ焼き山田_正面.jpg`）

先頭の `_` より前を店舗名として扱います。`_` が無い場合はファイル名全体（拡張子除く）を
店舗名候補とします。対応拡張子: jpg / jpeg / png / gif / bmp / webp / tif / tiff。

## 開発環境での実行

```bash
cd tools/store-sorter
pip install -r requirements.txt
python main.py
```

> 注: Tkinter は Python 標準ライブラリですが、Linux では別途 `python3-tk` の
> インストールが必要な場合があります（Windows の公式 Python には同梱）。

## テスト

コアロジック（Excel 読込・ファイル走査・照合・移動）はGUI非依存で、ユニットテスト済みです。

```bash
cd tools/store-sorter
pip install pytest
python -m pytest tests/ -v
```

## Windows 用 .exe のビルド

`.exe` の生成は **Windows 上**で行います（PyInstaller は実行 OS 向けバイナリを作るため）。

```bat
cd tools\store-sorter
pip install -r requirements.txt
pip install pyinstaller
pyinstaller build.spec
```

`dist\店舗振り分けツール.exe` が生成されます。運用時は、この exe と Excel マスター、
すべての画像ファイルを同じフォルダに置き、exe をダブルクリックして起動します。

## 構成

```
tools/store-sorter/
  main.py                エントリポイント
  build.spec             PyInstaller 設定
  requirements.txt       依存ライブラリ
  store_sorter/
    models.py            データモデル（Status / MatchRow）
    excel_loader.py      Excel 読込（openpyxl）
    file_scanner.py      画像走査・店舗名抽出・グルーピング
    matching.py          正規化・類似度計算・分類（rapidfuzz）
    file_ops.py          フォルダ作成・ファイル移動
    thumbnails.py        サムネイル生成・キャッシュ（Pillow）
    widgets.py           行ウィジェット・スクロール・プレビュー
    app.py               メインウィンドウ・非同期制御
  tests/                 ユニットテスト
```

## 技術メモ

- **類似度**: `rapidfuzz`（`WRatio`）。既定しきい値は 確定 92 / 曖昧 75（UI で調整可）。
  文字列は NFKC 正規化（全角・半角統一）＋空白除去＋小文字化してから比較します。
- **非同期**: 重い処理（走査・サムネイル生成・移動）はワーカースレッドで実行し、
  進捗を `queue` 経由でメインスレッドに渡して `after()` で描画します。GUI はフリーズしません。
- **メモリ**: サムネイルは 96px の LRU キャッシュ（既定 500 枚）で保持します。
