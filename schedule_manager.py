"""
曜日別監視スケジュール管理モジュール
schedule.json を読み書きし、現在時刻が監視時間帯かどうかを判定する
"""

import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
SCHEDULE_FILE = BASE_DIR / "schedule.json"

DAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"]

# デフォルトスケジュール（平日有効・土日無効）
DEFAULT_WINDOWS = [["05:30", "08:30"], ["14:30", "20:30"]]

DEFAULT_SCHEDULE: dict = {
    "days": {
        str(i): {
            "name": DAY_NAMES[i],
            "enabled": i < 5,
            "windows": DEFAULT_WINDOWS if i < 5 else [],
        }
        for i in range(7)
    }
}


def load_schedule() -> dict:
    """
    schedule.json を読み込む。存在しない・破損している場合はデフォルトを返す

    Returns:
        スケジュール辞書
    """
    try:
        if SCHEDULE_FILE.exists():
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("schedule.json の読み込みに失敗しました: %s", e)
    return DEFAULT_SCHEDULE


def save_schedule(data: dict) -> None:
    """
    スケジュールを schedule.json に保存する

    Args:
        data: 保存するスケジュール辞書
    """
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_monitoring_time() -> bool:
    """
    現在の曜日・時刻が監視時間帯内かどうかを返す

    Returns:
        監視時間帯内であれば True
    """
    now = datetime.datetime.now()
    weekday = str(now.weekday())  # 0=月曜, 6=日曜
    current_time = now.time()

    schedule = load_schedule()
    day_config = schedule.get("days", {}).get(weekday, {})

    if not day_config.get("enabled", False):
        return False

    for window in day_config.get("windows", []):
        if len(window) != 2:
            continue
        start_str, end_str = window
        h_s, m_s = map(int, start_str.split(":"))
        h_e, m_e = map(int, end_str.split(":"))
        if datetime.time(h_s, m_s) <= current_time <= datetime.time(h_e, m_e):
            return True

    return False


def current_day_summary() -> str:
    """
    現在の曜日スケジュールのサマリー文字列を返す（ログ用）

    Returns:
        例: "月 05:30〜08:30, 14:30〜20:30"
    """
    now = datetime.datetime.now()
    weekday = str(now.weekday())
    schedule = load_schedule()
    day_config = schedule.get("days", {}).get(weekday, {})

    if not day_config.get("enabled", False):
        return f"{day_config.get('name', '')} (無効)"

    windows = ", ".join(f"{w[0]}〜{w[1]}" for w in day_config.get("windows", []) if len(w) == 2)
    return f"{day_config.get('name', '')} {windows}"
