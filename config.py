"""
設定モジュール
環境変数からシークレットを読み込み、監視パラメータを定義する
"""

import os

# LINE Messaging API 認証情報（必ず環境変数から読む）
LINE_CHANNEL_TOKEN: str = os.environ.get("LINE_CHANNEL_TOKEN", "")
LINE_USER_ID: str = os.environ.get("LINE_USER_ID", "")

# 監視対象路線名
# Yahoo!路線情報 (https://transit.yahoo.co.jp/traininfo/area/4/) に
# 表示される名称と完全一致させること（「JR」プレフィックスは不要）
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

# 監視インターバル（秒）
CHECK_INTERVAL: int = 60

# エリアコード（関東=4, 東海=5, 関西=6）
AREA_CODE: str = "4"

# ログファイルパス
LOG_FILE: str = "/var/log/jr-monitor.log"

# 状態保存ファイルパス
STATE_FILE: str = "/var/lib/jr-monitor/state.json"
