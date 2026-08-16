#!/usr/bin/env bash
# ============================================================
#  EDS Spectrum Simulator - macOS デスクトップ版ビルド
#  リポジトリのルートで実行:  bash desktop/build_macos.sh
#  出力: dist/EDS-Simulator.app
# ============================================================
set -euo pipefail

python3 -m pip install --upgrade pip
pip3 install -r requirements.txt pyinstaller pywebview
pyinstaller --noconfirm --clean desktop/eds_sim_app.spec

echo ""
echo "[OK] dist/EDS-Simulator.app が生成されました。"
echo "     初回起動は Gatekeeper 警告が出るため、右クリック→開く で許可してください。"
