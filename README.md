# JR運行障害 LINE通知モニタリングシステム

JR（東日本・西日本）の運行障害・遅延・運休情報をYahoo!路線情報から定期監視し、
異常検知時（運行障害・運休等）にLINE Messaging APIで即時プッシュ通知するシステムです。
Rasberry Pi 5上で運用する場合の例を示しています。
LINE公式アカウントを先に作成しないとDevelopers Consoleが開けません。アカウント設定とキー取得に一時間、システム構築にclaude codeで一時間程度の開発時間目安です。

<br>
<img src=doc/images/sample1.jpg width="300">

---

## 構成

```
jr-monitor/
├── config.py              # 設定（トークン・路線名・インターバル）
├── monitor.py             # メインループ
├── line_client.py         # LINE Messaging API ラッパー
├── scraper.py             # Yahoo!路線情報スクレイパー
├── state.py               # 状態管理（JSON永続化）
├── requirements.txt       # 依存ライブラリ
├── jr-monitor.service     # systemd ユニットファイル
├── .env.example           # 環境変数テンプレート
└── tests/
    ├── test_scraper.py
    ├── test_line.py
    └── test_state.py
```

---

## セットアップ

### 1. LINE Developers 設定
0. LINE公式アカウント作成
1. [LINE Developers Console](https://developers.line.biz/) にログイン
2. プロバイダーを作成 → 「Messaging API」チャネルを作成
3. **Channel Access Token**（長期トークン）を発行して控える
4. LINE公式アカウントを自分のLINEで友達追加する
5. チャネルの「Webhook設定」から **Your User ID** を確認する（`U` で始まる文字列）

### 2. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定

```bash
cp .env.example .env
# .env を編集してトークンとユーザーIDを入力する
```

**ローカル実行時:**
```bash
export LINE_CHANNEL_TOKEN="your_token"
export LINE_USER_ID="U..."
# または
source .env   # dotenv 形式の場合は python-dotenv を利用
```

### 4. 監視路線の設定

`config.py` の `TARGET_LINES` を編集して監視したい路線名を設定します。
路線名はYahoo!路線情報に表示される名称と完全一致する必要があります（`JR` プレフィックス不要）。

```python
TARGET_LINES: list[str] = [
    "東海道本線[東京～熱海]",
    "横須賀線",
    "湘南新宿ライン",
]
```

### 5. 監視時間帯の設定

`config.py` の `MONITORING_WINDOWS` を編集して、通知を行う時間帯を指定します。
リスト内に複数の `(開始時刻, 終了時刻)` タプルを `"HH:MM"` 形式で記述します。
指定した時間帯以外はスクレイピング・通知ともに行いません。

```python
MONITORING_WINDOWS: list[tuple[str, str]] = [
    ("05:30", "08:30"),   # 朝の通勤時間帯
    ("14:30", "20:30"),   # 夕方〜夜の帰宅時間帯
]
```

### 6. 監視インターバルの設定

`config.py` の `CHECK_INTERVAL` でチェック間隔を秒単位で指定します（デフォルト: 60秒）。

```python
CHECK_INTERVAL: int = 60  # 60秒ごとに運行情報を取得
```

---

## テスト実行

```bash
pytest tests/ -v
```

カバレッジレポート付きで実行:

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## 動作確認（dry-run）

LINE送信を行わずログ出力のみで動作確認できます:

```bash
python monitor.py --dry-run
```

正常起動後、`CHECK_INTERVAL` で設定した間隔（デフォルト60秒）ごとにチェックログが出力されます。
`Ctrl+C` で停止できます。

---

## 本番実行

```bash
python monitor.py
```

---

## Raspberry Pi へのデプロイ手順

### 前提条件

- Raspberry Pi OS (Bullseye 以降) / Python 3.10+
- インターネット接続
- systemd が利用可能

### 手順

#### 1. ファイルの配置

```bash
# Raspberry Pi 上で実行
sudo mkdir -p /opt/jr-monitor /var/lib/jr-monitor
sudo chown pi:pi /opt/jr-monitor /var/lib/jr-monitor

# ローカルからファイルをコピー（例: scp / rsync）
rsync -av jr-monitor/ pi@raspberrypi.local:/opt/jr-monitor/
```

#### 2. Python 仮想環境の作成と依存インストール

```bash
cd /opt/jr-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. 環境変数ファイルの作成

```bash
sudo nano /etc/jr-monitor.env
```

内容:
```
LINE_CHANNEL_TOKEN=your_channel_access_token
LINE_USER_ID=Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```bash
sudo chmod 600 /etc/jr-monitor.env
```

#### 4. ログディレクトリの作成

```bash
sudo mkdir -p /var/log
# config.py の LOG_FILE パスを /home/pi/jr-monitor.log などに変更することも可
```

#### 5. systemd サービスのインストール

```bash
sudo cp /opt/jr-monitor/jr-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jr-monitor
sudo systemctl start jr-monitor
```

#### 6. 動作確認

```bash
# ステータス確認
sudo systemctl status jr-monitor

# リアルタイムログ確認
sudo journalctl -u jr-monitor -f

# 停止
sudo systemctl stop jr-monitor

# 無効化
sudo systemctl disable jr-monitor
```

#### 7. 自動再起動の設定（オプション）

`jr-monitor.service` の `[Service]` セクションに以下が含まれていることを確認:

```ini
Restart=on-failure
RestartSec=30s
```

これにより、クラッシュ時に30秒後に自動再起動されます。

---

## ログの確認

```bash
# systemd ジャーナル
sudo journalctl -u jr-monitor -n 100

# ログファイル直接確認
tail -f /var/log/jr-monitor.log
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| LINEが届かない | トークン・ユーザーIDが間違い | `--dry-run` で動作確認後、LINE API ダッシュボードを確認 |
| 障害が検知されない | 路線名の不一致 | Yahoo!路線情報の実際の表示名と `TARGET_LINES` を照合 |
| `ModuleNotFoundError` | 仮想環境が有効でない | `source venv/bin/activate` で有効化 |
| PermissionError | ログ/状態ファイルへの書き込み権限なし | `config.py` のパスを書き込み可能な場所に変更 |

---

## エリアコードの変更（関西・東海）

`config.py` の `AREA_CODE` を変更することで関西・東海も監視できます:

| 地域 | AREA_CODE |
|------|-----------|
| 関東 | `"4"` |
| 東海 | `"5"` |
| 関西 | `"6"` |
