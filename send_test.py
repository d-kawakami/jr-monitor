"""
LINE通知の疎通確認スクリプト
環境変数にトークンをセットして実行するだけでテストメッセージを送信する
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import config
import line_client

if not config.LINE_CHANNEL_TOKEN:
    print("エラー: LINE_CHANNEL_TOKEN が未設定です")
    print("  export LINE_CHANNEL_TOKEN='your_token'")
    sys.exit(1)

if not config.LINE_USER_ID:
    print("エラー: LINE_USER_ID が未設定です")
    print("  export LINE_USER_ID='Uxxxxxxxxx'")
    sys.exit(1)

print(f"送信先 User ID : {config.LINE_USER_ID[:6]}...")
print("LINEにテストメッセージを送信中...")

ok = line_client.send_message(
    config.LINE_CHANNEL_TOKEN,
    config.LINE_USER_ID,
    "✅ JR運行障害モニター\nLINE通知の疎通確認です。\nこのメッセージが届いていれば設定は完了です。",
)

if ok:
    print("✅ 送信成功！LINEを確認してください。")
else:
    print("❌ 送信失敗。トークンとユーザーIDを再確認してください。")
    sys.exit(1)
