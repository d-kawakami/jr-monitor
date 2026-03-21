"""
line_client.py のユニットテスト
LINE Messaging API への HTTP通信はすべてモック化する
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import line_client


class TestSendMessage:
    """send_message 関数のテストクラス"""

    def test_送信成功時にTrueを返す(self):
        """APIが200を返したとき True が返ること"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("line_client.requests.post", return_value=mock_response) as mock_post:
            result = line_client.send_message(
                token="dummy_token",
                user_id="U12345",
                text="テストメッセージ",
            )

        assert result is True
        mock_post.assert_called_once()
        # Authorizationヘッダーに Bearer トークンが含まれているか確認
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer dummy_token"

    def test_APIエラー時にFalseを返す(self):
        """APIが400を返したとき False が返ること"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"message": "Invalid reply token"}'

        with patch("line_client.requests.post", return_value=mock_response):
            result = line_client.send_message(
                token="dummy_token",
                user_id="U12345",
                text="テストメッセージ",
            )

        assert result is False

    def test_例外発生時にFalseを返しログを記録する(self, caplog):
        """ネットワーク例外が発生しても False を返してプロセスが継続すること"""
        with patch(
            "line_client.requests.post",
            side_effect=Exception("接続タイムアウト"),
        ):
            import logging
            with caplog.at_level(logging.ERROR, logger="line_client"):
                result = line_client.send_message(
                    token="dummy_token",
                    user_id="U12345",
                    text="テストメッセージ",
                )

        assert result is False
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_トークン未設定時にFalseを返す(self, caplog):
        """トークンが空文字のとき API呼び出しをせず False を返すこと"""
        with patch("line_client.requests.post") as mock_post:
            import logging
            with caplog.at_level(logging.ERROR, logger="line_client"):
                result = line_client.send_message(
                    token="",
                    user_id="U12345",
                    text="テストメッセージ",
                )

        assert result is False
        mock_post.assert_not_called()

    def test_ユーザーID未設定時にFalseを返す(self):
        """user_idが空文字のとき API呼び出しをせず False を返すこと"""
        with patch("line_client.requests.post") as mock_post:
            result = line_client.send_message(
                token="dummy_token",
                user_id="",
                text="テストメッセージ",
            )

        assert result is False
        mock_post.assert_not_called()

    def test_ペイロードの形式が正しい(self):
        """送信ペイロードがLINE API仕様に準拠していること"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("line_client.requests.post", return_value=mock_response) as mock_post:
            line_client.send_message("token", "user123", "hello")

        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["to"] == "user123"
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["type"] == "text"
        assert payload["messages"][0]["text"] == "hello"
