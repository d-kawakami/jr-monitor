"""
Yahoo!路線情報スクレイパー
指定エリアの運行障害情報を取得して辞書形式で返す
"""

import logging
import re
import warnings

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# リクエストヘッダー（ブラウザを偽装してブロックを回避）
HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

BASE_URL = "https://transit.yahoo.co.jp/traininfo/area/{area_code}/"


def fetch_disruptions(area_code: str) -> dict[str, dict] | None:
    """
    Yahoo!路線情報から運行障害情報を取得する

    Args:
        area_code: エリアコード（関東=4, 東海=5, 関西=6）

    Returns:
        路線名をキー、{"state": str, "detail": str} を値とする辞書。
        障害なしの場合は空辞書。取得失敗時は None を返す
    """
    url = BASE_URL.format(area_code=area_code)
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.warning("Yahoo!路線情報へのリクエストがタイムアウトしました: %s", url)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("Yahoo!路線情報の取得に失敗しました: %s", e)
        return None

    return _parse_disruptions(response.text)


def _parse_disruptions(html: str) -> dict[str, dict] | None:
    """
    取得したHTMLをパースして全路線の運行状態を抽出する

    Args:
        html: Yahoo!路線情報のHTMLテキスト

    Returns:
        路線名をキー、{"state": str, "detail": str} を値とする辞書
        障害・遅延がある路線のみ含む（平常運転は除外）。
        パース失敗時は None を返す
    """
    result: dict[str, dict] = {}

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Yahoo!路線情報のメインテーブル（全路線を含む）
        # セレクタが変わった場合に備えてフォールバックを用意する
        rows = soup.select("div.elmTblLstLine tr")
        if not rows:
            rows = _find_disruption_rows(soup)

        for row in rows:
            line_name, state, detail = _extract_row_data(row)
            if line_name and state and state not in ("平常運転", ""):
                result[line_name] = {"state": state, "detail": detail}

    except Exception as e:
        logger.warning("HTMLのパースに失敗しました: %s", e)
        return None

    return result


def _find_disruption_rows(soup: BeautifulSoup) -> list:
    """
    複数のCSSセレクタを試して行要素を探す（フォールバック）
    Yahoo!のHTML構造変更に対応する
    """
    selectors = [
        "table.trainInfoTable tr",
        "ul.trainInfoList li",
        "table.yjMTtable tr",
        "[class*='trainInfo'] tr",
        "[class*='traininfo'] tr",
    ]

    for selector in selectors:
        rows = soup.select(selector)
        if rows:
            logger.debug("セレクタ '%s' で %d 件の行を発見", selector, len(rows))
            return rows

    logger.warning("障害情報の行要素が見つかりませんでした")
    return []


def _extract_row_data(row) -> tuple[str, str, str]:
    """
    テーブル行から路線名・状態・詳細を抽出する

    Returns:
        (路線名, 状態, 詳細) のタプル。取得失敗時は空文字列のタプル
    """
    try:
        cells = row.find_all("td")
        if len(cells) >= 2:
            line_name = cells[0].get_text(strip=True)
            state = cells[1].get_text(strip=True)
            detail = cells[2].get_text(strip=True) if len(cells) >= 3 else ""
            return line_name, state, detail

    except Exception as e:
        logger.debug("行データの抽出をスキップ: %s", e)

    return "", "", ""
