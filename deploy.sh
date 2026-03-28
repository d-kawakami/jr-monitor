#!/bin/bash
# deploy.sh — ~/jr-monitor から /opt/jr-monitor へデプロイ
set -euo pipefail

DEPLOY_DIR="/opt/jr-monitor"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE="jr-monitor.service"

echo "==> デプロイ開始: ${SCRIPT_DIR} → ${DEPLOY_DIR}"

# ── ファイル同期 ────────────────────────────────────────────────
rsync -av \
  --exclude='.git/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='venv/' \
  --exclude='*.pid' \
  --exclude='*.log' \
  --exclude='schedule.json' \
  --exclude='tests/' \
  --exclude='doc/' \
  --exclude='deploy.sh' \
  "${SCRIPT_DIR}/" "${DEPLOY_DIR}/"

# ── systemd リロード＆再起動 ────────────────────────────────────
echo "==> systemd をリロードしてサービスを再起動します"
sudo systemctl daemon-reload
sudo systemctl restart "${SERVICE}"

# ── 結果確認 ───────────────────────────────────────────────────
sleep 1
STATUS=$(systemctl is-active "${SERVICE}" || true)
if [ "${STATUS}" = "active" ]; then
  echo "==> デプロイ完了 (${SERVICE} is ${STATUS})"
else
  echo "!! サービスの起動に失敗しました (status: ${STATUS})"
  echo "   journalctl -u ${SERVICE} -n 20 で確認してください"
  exit 1
fi
