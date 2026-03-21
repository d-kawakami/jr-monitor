"""
scraper.py のユニットテスト
外部HTTP通信はすべてモック化する
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import scraper

# テスト用HTML: 障害情報を含む最小限のHTML
SAMPLE_HTML_WITH_DISRUPTION = """
<html><body>
<table class="trainInfoTable">
  <tr>
    <td>JR山手線</td>
    <td>遅延</td>
    <td>一部列車に遅れが出ています。</td>
  </tr>
  <tr>
    <td>JR中央線（快速）</td>
    <td>運転見合わせ</td>
    <td>〇〇駅間で運転を見合わせています。</td>
  </tr>
</table>
</body></html>
"""

# テスト用HTML: 障害なし（空テーブル）
SAMPLE_HTML_EMPTY = """
<html><body>
<table class="trainInfoTable">
</table>
</body></html>
"""


class TestFetchDisruptions:
    """fetch_disruptions 関数のテストクラス"""

    def test_正常なHTMLから障害情報を取得できる(self):
        """正常レスポンス時に障害路線の辞書が返ること"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_HTML_WITH_DISRUPTION

        with patch("scraper.requests.get", return_value=mock_response):
            result = scraper.fetch_disruptions("4")

        assert "JR山手線" in result
        assert result["JR山手線"]["state"] == "遅延"
        assert result["JR山手線"]["detail"] == "一部列車に遅れが出ています。"
        assert "JR中央線（快速）" in result

    def test_障害なしのHTMLでは空辞書が返る(self):
        """障害情報がないHTMLのとき空辞書が返ること"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_HTML_EMPTY

        with patch("scraper.requests.get", return_value=mock_response):
            result = scraper.fetch_disruptions("4")

        assert result == {}

    def test_タイムアウト時は空辞書を返しWarningログを出す(self, caplog):
        """タイムアウト発生時に空辞書を返してWarningを記録すること"""
        with patch(
            "scraper.requests.get",
            side_effect=requests.exceptions.Timeout("タイムアウト"),
        ):
            import logging
            with caplog.at_level(logging.WARNING, logger="scraper"):
                result = scraper.fetch_disruptions("4")

        assert result == {}
        assert any("タイムアウト" in r.message for r in caplog.records)

    def test_接続エラー時は空辞書を返しWarningログを出す(self, caplog):
        """接続エラー発生時に空辞書を返してWarningを記録すること"""
        with patch(
            "scraper.requests.get",
            side_effect=requests.exceptions.ConnectionError("接続失敗"),
        ):
            import logging
            with caplog.at_level(logging.WARNING, logger="scraper"):
                result = scraper.fetch_disruptions("4")

        assert result == {}
        assert any(r.levelname == "WARNING" for r in caplog.records)

    def test_HTTPエラー時は空辞書を返す(self):
        """HTTPステータスエラー時に空辞書を返すこと"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("503")

        with patch("scraper.requests.get", return_value=mock_response):
            result = scraper.fetch_disruptions("4")

        assert result == {}

    def test_正常運転の路線は結果に含まれない(self):
        """「平常運転」状態の路線は結果辞書に含まれないこと"""
        html = """
        <html><body>
        <table class="trainInfoTable">
          <tr><td>JR山手線</td><td>平常運転</td><td></td></tr>
          <tr><td>JR中央線（快速）</td><td>遅延</td><td>遅れています。</td></tr>
        </table>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        with patch("scraper.requests.get", return_value=mock_response):
            result = scraper.fetch_disruptions("4")

        assert "JR山手線" not in result
        assert "JR中央線（快速）" in result
