#!/bin/bash
set -e

RST='\033[0m'
B='\033[1m'
DIM='\033[2m'
GRN='\033[0;32m'
CYN='\033[0;36m'
YLW='\033[1;33m'
RED='\033[0;31m'

OK="${GRN}✓${RST}"
FAIL="${RED}✗${RST}"

APP_DIR="$HOME/.termnl"
BIN="$HOME/.local/bin/termnl"

echo ""
echo -e "${B}Uninstall termnl${RST}"
echo -e "${DIM}──────────────────────────────────${RST}"
echo ""

# Check if installed
if [ ! -d "$APP_DIR" ] && [ ! -f "$BIN" ]; then
    echo -e "  ${DIM}termnl is not installed.${RST}"
    exit 0
fi

# Confirmation
echo -ne "  ${YLW}Remove termnl and all data? [y/N]${RST} "
read -r confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo -e "  ${DIM}Cancelled.${RST}"
    exit 0
fi

echo ""

# Remove app directory
if [ -d "$APP_DIR" ]; then
    rm -rf "$APP_DIR"
    echo -e "  ${OK} Removed ${DIM}${APP_DIR}${RST}"
fi

# Remove binary
if [ -f "$BIN" ]; then
    rm -f "$BIN"
    echo -e "  ${OK} Removed ${DIM}${BIN}${RST}"
fi

# Clean shell configs
cleaned=0
for rc in "$HOME/.zprofile" "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
    [ -f "$rc" ] || continue

    if grep -q 'termnl' "$rc" 2>/dev/null; then
        # Use compatible sed — macOS needs '' after -i, Linux doesn't
        if [[ "$(uname -s)" == "Darwin" ]]; then
            sed -i '' '/termnl/d' "$rc"
        else
            sed -i '/termnl/d' "$rc"
        fi
        cleaned=1
    fi
done

if [ "$cleaned" = "1" ]; then
    echo -e "  ${OK} Cleaned shell configs"
fi

echo ""
echo -e "  ${GRN}${B}✓ termnl uninstalled${RST}"
echo -e "  ${DIM}Restart your terminal to apply changes.${RST}"
echo ""