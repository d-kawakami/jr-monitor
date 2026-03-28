# JR運行障害 LINE通知モニタリングシステム

[English version here](README.md)

JR（東日本・西日本）の運行障害・遅延・運休情報をYahoo!路線情報から定期監視し、
異常検知時（運行障害・運休等）にLINE Messaging APIで即時プッシュ通知するシステムです。

**Webコントロールパネル**から、ブラウザだけでモニターの起動・停止や曜日別監視スケジュールを設定できます。

Raspberry Pi 5上で運用する場合の例を示しています。
LINE公式アカウントを先に作成しないとDevelopers Consoleが開けません。

<br>
<img src=doc/images/sample1.jpg width="300">

---

## 構成

```
jr-monitor/
├── config.py              # 設定（トークン・路線名・インターバル）
├── monitor.py             # メインループ
├── schedule_manager.py    # 曜日別スケジュール管理
├── web_app.py             # Webコントロールパネル（Flask）
├── line_client.py         # LINE Messaging API ラッパー
├── scraper.py             # Yahoo!路線情報スクレイパー
├── state.py               # 状態管理（JSON永続化）
├── schedule.json          # 曜日別スケジュール設定（自動生成）
├── requirements.txt       # 依存ライブラリ
├── jr-monitor.service     # systemd ユニットファイル
├── deploy.sh              # デプロイスクリプト（~/jr-monitor → /opt/jr-monitor）
├── .env.example           # 環境変数テンプレート
├── templates/
│   └── index.html         # Webコントロールパネル UI
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
路線名はYahoo!路線情報に表示される名称と完全一致する必要があります（`JR` プレフィックス不要）。不要な路線はコメントアウトしてください。

```python
TARGET_LINES: list[str] = [
#    "山手線",
#    "中央線(快速)[東京～高尾]",
#    "京浜東北根岸線",
    "東海道本線[東京～熱海]",
    "横須賀線",
    "湘南新宿ライン",
#    "埼京川越線[羽沢横浜国大～川越]",
#    "上野東京ライン",
#    "常磐線(快速)[品川～取手]",
#    "総武線(快速)[東京～千葉]",
]
```

### 5. 監視スケジュールの設定

監視時間帯は **Webコントロールパネル**（後述）から曜日ごとに設定します。
`schedule.json` が存在しない場合は、`config.py` の `MONITORING_WINDOWS` をもとにしたデフォルトが使われます。

| 曜日 | 有効 | 時間帯 |
|------|------|--------|
| 月〜金 | 有効 | 05:30–08:30、14:30–20:30 |
| 土・日 | 無効 | — |

### 6. 監視インターバルの設定

`config.py` の `CHECK_INTERVAL` でチェック間隔を秒単位で指定します（デフォルト: 60秒）。

```python
CHECK_INTERVAL: int = 60  # 60秒ごとに運行情報を取得
```

---

## Webコントロールパネル

```bash
python web_app.py
```

起動後、ブラウザで `http://localhost:5000/jr-monitor` を開きます。

### 機能一覧

| 機能 | 説明 |
|------|------|
| **起動 / 停止** | ボタン1つでモニタープロセスを制御 |
| **ドライランモード** | LINE送信なしで動作確認（起動時に選択） |
| **起動・停止通知** | モニター起動・停止時のLINE通知をON/OFF切り替え |
| **リアルタイムステータス** | 稼働中/停止中を表示、30秒ごとに自動更新 |
| **曜日別スケジュール** | 月〜日それぞれ個別に有効/無効を切り替え |
| **時間帯管理** | 各曜日に複数の時間帯を追加・編集・削除 |
| **保存** | `schedule.json` に書き込み、次のサイクルから反映 |

ポートは `WEB_PORT` 環境変数で変更できます:

```bash
WEB_PORT=8080 python web_app.py
# http://localhost:8080/jr-monitor でアクセス
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

コマンドラインからLINE送信なしで動作確認することもできます:

```bash
python monitor.py --dry-run
```

正常起動後、`CHECK_INTERVAL` で設定した間隔（デフォルト60秒）ごとにチェックログが出力されます。
`Ctrl+C` で停止できます。

---

## 本番実行（CLI）

```bash
python monitor.py
```

本番環境では Webコントロールパネルまたは systemd サービス（後述）の利用を推奨します。

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

> **継続的な開発には:** `~/jr-monitor` にリポジトリをクローンし、`deploy.sh` で `/opt/jr-monitor` へ同期するのを推奨します:
> ```bash
> cd ~/jr-monitor && git pull && bash deploy.sh
> ```

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

サービスは `web_app.py` を起動し、`web_app.py` が子プロセスとして `monitor.py` を管理します。これによりブラウザだけでモニターを制御できます。

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

# Webコントロールパネルから起動した場合の標準出力ログ
tail -f monitor_stdout.log
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| LINEが届かない | トークン・ユーザーIDが間違い | `--dry-run` で動作確認後、LINE API ダッシュボードを確認 |
| 障害が検知されない | 路線名の不一致 | Yahoo!路線情報の実際の表示名と `TARGET_LINES` を照合 |
| `ModuleNotFoundError` | 仮想環境が有効でない | `source venv/bin/activate` で有効化 |
| `PermissionError` | ログ/状態ファイルへの書き込み権限なし | `config.py` のパスを書き込み可能な場所に変更 |
| Webパネルから起動できない | PID ファイルが残存 | `monitor.pid` を削除して再試行 |

---

## エリアコードの変更（関西・東海）

`config.py` の `AREA_CODE` を変更することで関西・東海も監視できます:

| 地域 | AREA_CODE |
|------|-----------|
| 関東 | `"4"` |
| 東海 | `"5"` |
| 関西 | `"6"` |
