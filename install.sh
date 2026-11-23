#!/usr/bin/env bash
set -euo pipefail

DEST_DIR="${HOME}/.local/share/corsair-titan-lcd"
BIN_DIR="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"

mkdir -p "${DEST_DIR}" "${BIN_DIR}" "${SYSTEMD_DIR}"

cp -f titan_lcd_llm_hud.py lcp_c64_house.py "${DEST_DIR}/"
chmod +x "${DEST_DIR}/titan_lcd_llm_hud.py" "${DEST_DIR}/lcp_c64_house.py"

ln -sf "${DEST_DIR}/titan_lcd_llm_hud.py" "${BIN_DIR}/titan-lcd"
cp -f systemd/titan-lcd.service "${SYSTEMD_DIR}/titan-lcd.service"

systemctl --user daemon-reload
systemctl --user enable --now titan-lcd.service

echo "Installed and started titan-lcd.service!"
echo "Try: titan-lcd --list-themes"
echo "     titan-lcd --set-theme c64_lcp"
