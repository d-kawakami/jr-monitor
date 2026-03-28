"""
JR運行障害 LINE通知モニター
メインループ: スクレイピング→差分検知→LINE通知→状態保存→スリープ
"""

import argparse
import datetime
import logging
import logging.handlers
import signal
import sys
import time
from pathlib import Path

import config
import line_client
import schedule_manager
import scraper
import state

# ロガー設定
logger = logging.getLogger(__name__)


def setup_logging(log_file: str, dry_run: bool = False) -> None:
    """
    ファイルとコンソール両方にログを出力するよう設定する

    Args:
        log_file: ログファイルのパス
        dry_run: Trueの場合はコンソールのみ（ファイル出力なし）
    """
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # コンソールハンドラ（WindowsではUTF-8を明示してエモジ出力を可能にする）
    try:
        import io
        utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        console = logging.StreamHandler(utf8_stdout)
    except AttributeError:
        # バッファが取得できない環境（IDLE等）はそのまま使う
        console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    # ファイルハンドラ（dry-runモードではスキップ）
    if not dry_run:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except OSError as e:
            logger.warning("ログファイルを開けません (%s): %s。コンソール出力のみ継続。", log_file, e)


def is_monitoring_time() -> bool:
    """
    現在の曜日・時刻が監視時間帯内かどうかを返す（schedule.json を参照）

    Returns:
        監視時間帯内であればTrue
    """
    return schedule_manager.is_monitoring_time()


def build_disruption_message(info: dict) -> str:
    """
    障害発生通知メッセージを組み立てる

    Args:
        info: {"line": str, "state": str, "detail": str}

    Returns:
        フォーマット済み通知文字列
    """
    return (
        "⚠️ 【運行障害】\n"
        f"路線: {info['line']}\n"
        f"状態: {info['state']}\n"
        f"{info.get('detail', '')}"
    ).rstrip()


def build_recovery_message(line: str) -> str:
    """
    復旧通知メッセージを組み立てる

    Args:
        line: 復旧した路線名

    Returns:
        フォーマット済み復旧文字列
    """
    return f"✅ 【復旧】{line} の運行が正常に戻りました"


def notify(token: str, user_id: str, text: str, dry_run: bool) -> None:
    """
    LINE通知を送信する（dry-runモードではログ出力のみ）

    Args:
        token: LINE Channel Access Token
        user_id: 送信先ユーザーID
        text: 送信テキスト
        dry_run: Trueの場合はLINE送信を行わずログに出力するだけ
    """
    if dry_run:
        logger.info("[DRY-RUN] LINE通知をスキップ:\n%s", text)
    else:
        line_client.send_message(token, user_id, text)


def run(dry_run: bool = False, notify_start_stop: bool = True) -> None:
    """
    監視メインループ

    Args:
        dry_run: Trueの場合はLINE送信を行わない
        notify_start_stop: Falseの場合は起動・停止時のLINE通知を送らない
    """
    state_path = Path(config.STATE_FILE)

    # Ctrl+C (SIGINT / SIGTERM) でグレースフルシャットダウン
    shutdown_requested = False

    def _handle_signal(signum: int, frame) -> None:
        nonlocal shutdown_requested
        logger.info("シグナル %d を受信しました。監視を終了します。", signum)
        shutdown_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("JR運行障害モニター起動 (dry_run=%s, notify_start_stop=%s)", dry_run, notify_start_stop)
    if notify_start_stop and is_monitoring_time():
        notify(
            config.LINE_CHANNEL_TOKEN,
            config.LINE_USER_ID,
            "🚆 JR運行障害モニターを起動しました。監視を開始します。",
            dry_run,
        )

    prev = state.load(state_path)

    while not shutdown_requested:
        try:
            if not is_monitoring_time():
                logger.debug("監視時間帯外のためスキップ (本日: %s)", schedule_manager.current_day_summary())
                # シャットダウン要求があれば即終了
                if shutdown_requested:
                    break
                for _ in range(config.CHECK_INTERVAL):
                    if shutdown_requested:
                        break
                    time.sleep(1)
                continue

            logger.info("運行情報を取得中 (エリアコード: %s)...", config.AREA_CODE)
            current = scraper.fetch_disruptions(config.AREA_CODE)

            if current is None:
                logger.warning("運行情報の取得に失敗したため、今回のサイクルをスキップします")
            else:
                new_or_changed, recovered = state.diff(prev, current, config.TARGET_LINES)

                # 障害・変化通知
                for info in new_or_changed:
                    msg = build_disruption_message(info)
                    logger.info("障害検知: %s - %s", info["line"], info["state"])
                    notify(config.LINE_CHANNEL_TOKEN, config.LINE_USER_ID, msg, dry_run)

                # 復旧通知
                for line in recovered:
                    msg = build_recovery_message(line)
                    logger.info("復旧検知: %s", line)
                    notify(config.LINE_CHANNEL_TOKEN, config.LINE_USER_ID, msg, dry_run)

                if not new_or_changed and not recovered:
                    logger.info(
                        "変化なし (監視中の障害: %d路線)",
                        sum(1 for t in config.TARGET_LINES if t in current),
                    )

                state.save(state_path, current)
                prev = current

        except Exception as e:
            # 予期しない例外でもプロセスを継続させる
            logger.error("監視ループ内で予期しないエラーが発生しました: %s", e, exc_info=True)

        # シャットダウン要求があればスリープをスキップして即終了
        if shutdown_requested:
            break

        logger.debug("次のチェックまで %d 秒待機...", config.CHECK_INTERVAL)
        # インターバルを細かく分割してシグナルに素早く反応できるようにする
        for _ in range(config.CHECK_INTERVAL):
            if shutdown_requested:
                break
            time.sleep(1)

    # 終了通知
    logger.info("監視終了")
    if notify_start_stop and is_monitoring_time():
        notify(
            config.LINE_CHANNEL_TOKEN,
            config.LINE_USER_ID,
            "🛑 JR運行障害モニターを停止しました。",
            dry_run,
        )


def main() -> None:
    """エントリーポイント: 引数解析とロギング設定を行った後にメインループを呼び出す"""
    parser = argparse.ArgumentParser(description="JR運行障害 LINE通知モニター")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="LINE送信を行わずログ出力のみで動作確認する",
    )
    parser.add_argument(
        "--no-start-stop-notify",
        action="store_true",
        help="起動・停止時のLINE通知を送らない",
    )
    args = parser.parse_args()

    setup_logging(config.LOG_FILE, dry_run=args.dry_run)
    run(dry_run=args.dry_run, notify_start_stop=not args.no_start_stop_notify)


if __name__ == "__main__":
    main()
