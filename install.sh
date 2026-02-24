#!/bin/bash
set -e

# --- Theme ---
RST='\033[0m'
B='\033[1m'
DIM='\033[2m'
GRN='\033[0;32m'
CYN='\033[0;36m'
YLW='\033[1;33m'
RED='\033[0;31m'

OK="${GRN}✓${RST}"
FAIL="${RED}✗${RST}"
ARROW="${CYN}→${RST}"
SPIN_CHARS=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")

APP_DIR="$HOME/.termnl"
REPO="https://github.com/nithinworks/termnl"
STAGING="/tmp/termnl-install-$$"

# --- Helpers ---

spin() {
    local pid=$1 msg=$2 i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYN}${SPIN_CHARS[$i]}${RST} %s..." "$msg"
        i=$(( (i + 1) % ${#SPIN_CHARS[@]} ))
        sleep 0.08
    done
    wait "$pid"
    return $?
}

bail() { echo -e "  ${FAIL} $1"; exit 1; }

# --- Pre-flight Checks ---

clear
echo -e "${B}"
cat << "BANNER"
████████╗███████╗██████╗ ███╗   ███╗███╗   ██╗██╗     
╚══██╔══╝██╔════╝██╔══██╗████╗ ████║████╗  ██║██║     
   ██║   █████╗  ██████╔╝██╔████╔██║██╔██╗ ██║██║     
   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║╚██╗██║██║     
   ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║ ╚████║███████╗
   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═══╝╚══════╝
BANNER
echo -e "${RST}"
echo -e "  ${DIM}The terminal for everyone | Installation${RST}"
echo -e "  ${DIM}──────────────────────────────────────────────${RST}"

echo -e "Preflight checks..."

# OS check
case "$(uname -s)" in
    Darwin|Linux) ;;
    *) bail "Unsupported OS. termnl supports macOS and Linux." ;;
esac

# curl check
command -v curl &>/dev/null || bail "curl is required. Install it first (brew install curl / apt install curl)."

# Python check
if ! command -v python3 &>/dev/null; then
    bail "Python 3.10+ is required. Install it first."
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER##*.}"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    bail "Python 3.10+ required (found ${PY_VER})"
fi

echo -e "  ${OK} Python ${PY_VER}"
echo -e "  ${OK} curl available"
echo -e "  ${OK} $(uname -s) detected"

# --- Download ---

echo ""
echo -e "Installing termnl..."

fetch_release() {
    rm -rf "$STAGING"
    mkdir -p "$STAGING" "$APP_DIR"
    curl -sL "$REPO/archive/main.tar.gz" | tar xz -C "$STAGING" --strip-components=1
    # Preserve user config (.env, .config) if upgrading
    for keep in .env .config; do
        [ -f "$APP_DIR/$keep" ] && cp "$APP_DIR/$keep" "$STAGING/$keep.bak" 2>/dev/null || true
    done
    cp -r "$STAGING"/. "$APP_DIR/"
    # Restore user config if they existed
    for keep in .env .config; do
        [ -f "$APP_DIR/$keep.bak" ] && mv "$APP_DIR/$keep.bak" "$APP_DIR/$keep" 2>/dev/null || true
    done
    rm -rf "$STAGING"
}

if [ -d "$APP_DIR/venv" ]; then
    fetch_release &
    spin $! "Updating files"
    echo -e "\r  ${OK} Updated successfully                         "
else
    fetch_release &
    spin $! "Downloading files"
    echo -e "\r  ${OK} Files downloaded                              "
fi

# --- Python Environment ---

cd "$APP_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv &>/dev/null
fi

source venv/bin/activate
pip install --quiet --upgrade pip &>/dev/null

pip install --quiet -r requirements.txt &
spin $! "Installing dependencies"
echo -e "\r  ${OK} Dependencies installed                     "

# --- CLI Wrapper ---

echo ""
echo -e "Configuring shell..."

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/termnl" << 'WRAPPER'
#!/usr/bin/env bash
set -e
TERMNL_HOME="${TERMNL_HOME:-$HOME/.termnl}"
source "$TERMNL_HOME/venv/bin/activate"
exec python "$TERMNL_HOME/termnl.py" "$@"
WRAPPER

chmod +x "$HOME/.local/bin/termnl"

# --- Shell RC Patching ---

patch_shell_rc() {
    local rc="$1" want_autolaunch="$2"
    [ -f "$rc" ] || return 0

    # Ensure ~/.local/bin is on PATH
    if ! grep -q '.local/bin' "$rc" 2>/dev/null; then
        printf '\n# Added by termnl\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
    fi

    # Optionally add auto-launch
    if [ "$want_autolaunch" = "1" ] && ! grep -q 'termnl # auto-launch' "$rc" 2>/dev/null; then
        {
            echo ''
            echo '# termnl - auto-launch on terminal start'
            echo '[ -t 0 ] && [ -z "$TERMNL_RUNNING" ] && [ -x "$HOME/.local/bin/termnl" ] && export TERMNL_RUNNING=1 && termnl # auto-launch'
        } >> "$rc"
    fi
}

export PATH="$HOME/.local/bin:$PATH"

echo -e "  ${OK} Shell configured"

# --- Auto-launch prompt ---

echo ""
echo -ne "  ${ARROW} Auto-launch termnl when you open a terminal? ${YLW}[y/N]${RST} "
read -r autolaunch_choice < /dev/tty

want_autolaunch=0
if [[ "$autolaunch_choice" =~ ^[Yy]$ ]]; then
    want_autolaunch=1
fi

for rc in "$HOME/.zprofile" "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
    patch_shell_rc "$rc" "$want_autolaunch"
done

if [ "$want_autolaunch" = "1" ]; then
    echo -e "  ${OK} Auto-launch enabled"
    echo -e "  ${DIM}Toggle later with !autolaunch inside termnl${RST}"
else
    echo -e "  ${DIM}Skipped. Type 'termnl' to start manually.${RST}"
    echo -e "  ${DIM}Enable later with !autolaunch inside termnl${RST}"
fi

# --- Done ---

echo ""
echo -e "  ${DIM}──────────────────────────────────────────────${RST}"
echo ""
echo -e "  ${GRN}${B}✓ Installation complete!${RST}"
echo ""
if [ "$want_autolaunch" = "1" ]; then
    echo -e "  ${ARROW} Open a new terminal window to start termnl"
else
    echo -e "  ${ARROW} Run: ${CYN}${B}termnl${RST}"
fi
echo ""
