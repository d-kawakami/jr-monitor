"""
ユーザー認証管理モジュール
users.json にユーザー情報（ハッシュ化パスワード）を保存する
"""

import json
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

USERS_FILE = Path(__file__).parent / "users.json"

# 初期ユーザー: admin / パスワード未設定 (None)
_DEFAULT_USERS: dict = {"admin": None}


def load_users() -> dict:
    """users.json を読み込む。存在しない場合はデフォルトを生成して返す"""
    if not USERS_FILE.exists():
        save_users(_DEFAULT_USERS)
        return _DEFAULT_USERS.copy()
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _DEFAULT_USERS.copy()


def save_users(users: dict) -> None:
    """users.json に保存する"""
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def verify_user(username: str, password: str) -> bool:
    """
    ユーザー認証。
    パスワードが None (未設定) の場合は空文字でのみログイン可能。
    """
    users = load_users()
    if username not in users:
        return False
    stored = users[username]
    if stored is None:
        return password == ""
    return check_password_hash(stored, password)


def set_password(username: str, new_password: str) -> bool:
    """パスワードを設定・変更する。ユーザーが存在しない場合は False"""
    users = load_users()
    if username not in users:
        return False
    users[username] = generate_password_hash(new_password)
    save_users(users)
    return True


def add_user(username: str, password: str | None = None) -> bool:
    """
    ユーザーを追加する。
    password が None または空文字の場合はパスワード未設定状態で作成。
    既に存在する場合は False。
    """
    if not username or not username.strip():
        return False
    users = load_users()
    if username in users:
        return False
    users[username] = generate_password_hash(password) if password else None
    save_users(users)
    return True


def delete_user(username: str) -> bool:
    """ユーザーを削除する。存在しない場合は False"""
    users = load_users()
    if username not in users:
        return False
    del users[username]
    save_users(users)
    return True


def list_users() -> list[dict]:
    """ユーザー一覧を返す（パスワードハッシュは含まない）"""
    users = load_users()
    return [
        {"username": u, "password_set": v is not None}
        for u, v in users.items()
    ]


def user_exists(username: str) -> bool:
    return username in load_users()
