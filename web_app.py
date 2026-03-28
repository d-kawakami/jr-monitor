"""
JR監視 コントロールパネル Web アプリケーション
曜日別スケジュール設定・サーバー起動停止を管理する Flask アプリ
"""

import json
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, Flask, jsonify, render_template, request

import schedule_manager

logger = logging.getLogger(__name__)

app = Flask(__name__)
bp = Blueprint("jr_monitor", __name__, url_prefix="/jr-monitor")

BASE_DIR = Path(__file__).parent
PID_FILE = BASE_DIR / "monitor.pid"


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


# ── API エンドポイント ────────────────────────────────────────

@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/schedule", methods=["GET"])
def api_get_schedule():
    """現在のスケジュール設定を返す"""
    return jsonify(schedule_manager.load_schedule())


@bp.route("/api/schedule", methods=["POST"])
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


@bp.route("/api/status", methods=["GET"])
def api_status():
    """モニタープロセスのステータスを返す"""
    status = get_process_status()
    pid = _get_pid() if status == "running" else None
    return jsonify({"status": status, "pid": pid})


@bp.route("/api/start", methods=["POST"])
def api_start():
    """モニタープロセスを起動する"""
    data = request.get_json() or {}
    dry_run = bool(data.get("dry_run", False))
    result = start_process(dry_run=dry_run)
    return jsonify(result), 200 if result["ok"] else 400


@bp.route("/api/stop", methods=["POST"])
def api_stop():
    """モニタープロセスを停止する"""
    result = stop_process()
    return jsonify(result), 200 if result["ok"] else 400


app.register_blueprint(bp)


# ── エントリーポイント ────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    port = int(os.environ.get("WEB_PORT", 5000))
    print(f"JR監視コントロールパネルを起動中... http://localhost:{port}/jr-monitor")
    app.run(host="0.0.0.0", port=port, debug=False)
