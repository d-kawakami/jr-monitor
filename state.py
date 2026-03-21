"""
状態管理モジュール
前回チェック時の障害状態をJSONファイルで永続化し、差分を検出する
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load(path: Path) -> dict:
    """
    状態ファイルを読み込む

    Args:
        path: 状態JSONファイルのパス

    Returns:
        前回保存した状態辞書。ファイルが存在しない・破損している場合は空辞書
    """
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("状態ファイルの読み込みに失敗しました (%s): %s", path, e)

    return {}


def save(path: Path, data: dict) -> None:
    """
    状態をJSONファイルに書き込む

    Args:
        path: 書き込み先のパス（親ディレクトリが存在しない場合は作成）
        data: 保存する状態辞書
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("状態ファイルの書き込みに失敗しました (%s): %s", path, e)


def diff(
    prev: dict, current: dict, targets: list[str]
) -> tuple[list[dict], list[str]]:
    """
    前回状態と今回状態を比較して、監視対象路線の変化を検出する

    Args:
        prev: 前回のスクレイピング結果（路線名 -> {"state": str, "detail": str}）
        current: 今回のスクレイピング結果（同形式）
        targets: 監視対象路線名のリスト

    Returns:
        - new_or_changed: 新規発生・状態変化した障害情報のリスト
          各要素: {"line": str, "state": str, "detail": str}
        - recovered: 正常に復旧した路線名のリスト
    """
    new_or_changed: list[dict] = []
    recovered: list[str] = []

    for line in targets:
        prev_info = prev.get(line)
        curr_info = current.get(line)

        if curr_info is not None:
            # 障害あり
            if prev_info is None:
                # 新規障害
                new_or_changed.append({"line": line, **curr_info})
            elif prev_info.get("state") != curr_info.get("state"):
                # 状態変化（例: 遅延→運転見合わせ）
                new_or_changed.append({"line": line, **curr_info})
        else:
            # 障害なし
            if prev_info is not None:
                # 復旧
                recovered.append(line)

    return new_or_changed, recovered
