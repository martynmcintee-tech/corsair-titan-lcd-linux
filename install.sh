#!/usr/bin/env bash
set -euo pipefail

DEST_DIR="${HOME}/.local/share/corsair-titan-lcd"
BIN_DIR="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

mkdir -p "${DEST_DIR}" "${BIN_DIR}" "${SYSTEMD_DIR}" "${APP_DIR}" "${ICON_DIR}"

cp -f titan_lcd_llm_hud.py lcp_c64_house.py lcp_world_scenes.py lcp_desktop_app.py "${DEST_DIR}/"
chmod +x "${DEST_DIR}/titan_lcd_llm_hud.py" "${DEST_DIR}/lcp_c64_house.py" "${DEST_DIR}/lcp_desktop_app.py"
cp -f assets/lcp-2026.svg "${ICON_DIR}/lcp-2026.svg"

ln -sf "${DEST_DIR}/titan_lcd_llm_hud.py" "${BIN_DIR}/titan-lcd"
ln -sf "${DEST_DIR}/lcp_desktop_app.py" "${BIN_DIR}/lcp-2026"
cp -f systemd/titan-lcd.service "${SYSTEMD_DIR}/titan-lcd.service"

cat << DESK > "${APP_DIR}/lcp-2026.desktop"
[Desktop Entry]
Type=Application
Name=Little Computer Person 2026
GenericName=Autonomous Pixel Life Companion
Comment=LCP 2026 — Desktop Widget, Studio & Corsair AIO LCD Companion
Exec=${BIN_DIR}/lcp-2026
Icon=lcp-2026
Terminal=false
Categories=Utility;Game;Simulation;GTK;
StartupNotify=true
Actions=Widget;

[Desktop Action Widget]
Name=Open Mini Circular Desktop Widget
Exec=${BIN_DIR}/lcp-2026 --widget
DESK

update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
systemctl --user daemon-reload
systemctl --user enable --now titan-lcd.service

echo "Installed and started titan-lcd.service + Little Computer Person 2026 desktop app!"
echo "Try: titan-lcd --set-theme c64_lcp"
echo "     lcp-2026            # Open Full LCP 2026 Studio & Settings"
echo "     lcp-2026 --widget   # Open Compact Circular Desktop Widget (no cooler needed!)"
