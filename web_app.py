"""
JR監視 コントロールパネル Web アプリケーション
曜日別スケジュール設定・サーバー起動停止を管理する Flask アプリ
"""

import json
import logging
import os
import secrets
import signal
import subprocess
import sys
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import auth
import schedule_manager

logger = logging.getLogger(__name__)

app = Flask(__name__)

# シークレットキー: 環境変数 > .secret_key ファイル > 自動生成して保存
_SECRET_KEY_FILE = Path(__file__).parent / ".secret_key"


def _load_secret_key() -> str:
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _SECRET_KEY_FILE.write_text(key)
    return key


app.secret_key = _load_secret_key()

bp = Blueprint("jr_monitor", __name__, url_prefix="/jr-monitor")

BASE_DIR = Path(__file__).parent
PID_FILE = BASE_DIR / "monitor.pid"


# ── 認証ヘルパー ──────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("username"):
            if request.path.startswith("/jr-monitor/api/"):
                return jsonify({"ok": False, "error": "認証が必要です"}), 401
            return redirect(url_for("jr_monitor.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


# ── プロセス管理 ──────────────────────────────────────────────

def _get_pid() -> int | None:
    """PID ファイルから PID を読み込む。存在しない場合は None"""
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def get_process_status() -> str:
    """
    モニタープロセスの状態を返す

    Returns:
        "running" または "stopped"
    """
    pid = _get_pid()
    if pid is None:
        return "stopped"
    try:
        os.kill(pid, 0)  # シグナル 0 は存在確認のみ
        return "running"
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return "stopped"
    except PermissionError:
        # プロセスは存在するがシグナル送信権限なし
        return "running"


def start_process(dry_run: bool = False) -> dict:
    """モニタープロセスを起動する"""
    if get_process_status() == "running":
        return {"ok": False, "error": "すでに起動しています"}

    cmd = [sys.executable, str(BASE_DIR / "monitor.py")]
    if dry_run:
        cmd.append("--dry-run")
    schedule = schedule_manager.load_schedule()
    if not schedule.get("notify_on_start_stop", True):
        cmd.append("--no-start-stop-notify")

    env = os.environ.copy()
    log_path = BASE_DIR / "monitor_stdout.log"

    with open(log_path, "a", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            env=env,
            stdout=log_file,
            stderr=log_file,
        )

    PID_FILE.write_text(str(proc.pid))
    logger.info("モニタープロセスを起動しました (PID=%d, dry_run=%s)", proc.pid, dry_run)
    return {"ok": True, "pid": proc.pid}


def stop_process() -> dict:
    """モニタープロセスを停止する"""
    if get_process_status() == "stopped":
        return {"ok": False, "error": "起動していません"}

    pid = _get_pid()
    if pid is None:
        return {"ok": False, "error": "PID ファイルが見つかりません"}

    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        logger.info("モニタープロセスを停止しました (PID=%d)", pid)
        return {"ok": True}
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}


# ── 認証エンドポイント ────────────────────────────────────────

@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("username"):
        return redirect(url_for("jr_monitor.index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if auth.verify_user(username, password):
            session["username"] = username
            next_url = request.args.get("next") or url_for("jr_monitor.index")
            return redirect(next_url)
        error = "ユーザー名またはパスワードが正しくありません"

    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("jr_monitor.login"))


# ── メイン画面 ────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    return render_template("index.html", username=session["username"])


# ── スケジュール API ──────────────────────────────────────────

@bp.route("/api/schedule", methods=["GET"])
@login_required
def api_get_schedule():
    """現在のスケジュール設定を返す"""
    return jsonify(schedule_manager.load_schedule())


@bp.route("/api/schedule", methods=["POST"])
@login_required
def api_set_schedule():
    """スケジュール設定を更新する"""
    data = request.get_json()
    if not data or "days" not in data:
        return jsonify({"ok": False, "error": "不正なリクエストです"}), 400
    try:
        schedule_manager.save_schedule(data)
        return jsonify({"ok": True})
    except OSError as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── プロセス制御 API ─────────────────────────────────────────

@bp.route("/api/status", methods=["GET"])
@login_required
def api_status():
    """モニタープロセスのステータスを返す"""
    status = get_process_status()
    pid = _get_pid() if status == "running" else None
    return jsonify({"status": status, "pid": pid})


@bp.route("/api/start", methods=["POST"])
@login_required
def api_start():
    """モニタープロセスを起動する"""
    data = request.get_json() or {}
    dry_run = bool(data.get("dry_run", False))
    result = start_process(dry_run=dry_run)
    return jsonify(result), 200 if result["ok"] else 400


@bp.route("/api/stop", methods=["POST"])
@login_required
def api_stop():
    """モニタープロセスを停止する"""
    result = stop_process()
    return jsonify(result), 200 if result["ok"] else 400


# ── ユーザー管理 API ─────────────────────────────────────────

@bp.route("/api/users", methods=["GET"])
@login_required
def api_list_users():
    """ユーザー一覧を返す"""
    return jsonify({"ok": True, "users": auth.list_users()})


@bp.route("/api/users", methods=["POST"])
@login_required
def api_add_user():
    """ユーザーを追加する"""
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password") or None

    if not username:
        return jsonify({"ok": False, "error": "ユーザー名を入力してください"}), 400

    if auth.add_user(username, password):
        logger.info("ユーザーを追加しました: %s (by %s)", username, session["username"])
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "同名のユーザーが既に存在します"}), 400


@bp.route("/api/users/<username>", methods=["DELETE"])
@login_required
def api_delete_user(username: str):
    """ユーザーを削除する"""
    if username == session["username"]:
        return jsonify({"ok": False, "error": "自分自身は削除できません"}), 400

    if auth.delete_user(username):
        logger.info("ユーザーを削除しました: %s (by %s)", username, session["username"])
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "ユーザーが見つかりません"}), 404


@bp.route("/api/users/<username>/password", methods=["PUT"])
@login_required
def api_set_password(username: str):
    """パスワードを設定・変更する"""
    # 自分のパスワード変更、または他ユーザーのパスワードリセット
    data = request.get_json() or {}
    new_password = data.get("new_password", "")

    if not new_password:
        return jsonify({"ok": False, "error": "新しいパスワードを入力してください"}), 400

    if not auth.user_exists(username):
        return jsonify({"ok": False, "error": "ユーザーが見つかりません"}), 404

    auth.set_password(username, new_password)
    logger.info("パスワードを変更しました: %s (by %s)", username, session["username"])
    return jsonify({"ok": True})


app.register_blueprint(bp)


# ── エントリーポイント ────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    port = int(os.environ.get("WEB_PORT", 5000))
    print(f"JR監視コントロールパネルを起動中... http://localhost:{port}/jr-monitor")
    app.run(host="0.0.0.0", port=port, debug=False)
