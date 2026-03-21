"""
LINE Messaging API クライアント
プッシュメッセージの送信をラップする
"""

import logging

import requests

logger = logging.getLogger(__name__)

# LINE Messaging API v2 プッシュメッセージエンドポイント
LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def send_message(token: str, user_id: str, text: str) -> bool:
    """
    LINE Messaging API でプッシュメッセージを送信する

    Args:
        token: LINE Channel Access Token
        user_id: 送信先のLINEユーザーID
        text: 送信するテキストメッセージ

    Returns:
        送信成功時はTrue、失敗時はFalse
    """
    if not token or not user_id:
        logger.error("LINE_CHANNEL_TOKEN または LINE_USER_ID が未設定です")
        return False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    try:
        response = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info("LINEメッセージ送信成功")
            return True
        else:
            logger.error(
                "LINEメッセージ送信失敗: status=%d, body=%s",
                response.status_code,
                response.text,
            )
            return False

    except Exception as e:
        # 例外を握りつぶしてプロセスを継続させる
        logger.error("LINEメッセージ送信中に例外が発生しました: %s", e)
        return False
