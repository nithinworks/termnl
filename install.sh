#!/bin/bash
set -e

# Color scheme
CLR_RESET='\033[0m'
CLR_BOLD='\033[1m'
CLR_DIM='\033[2m'
CLR_SUCCESS='\033[0;32m'
CLR_INFO='\033[0;36m'
CLR_WARN='\033[1;33m'
CLR_ERROR='\033[0;31m'

# UI Elements
ICON_SUCCESS="${CLR_SUCCESS}✓${CLR_RESET}"
ICON_ERROR="${CLR_ERROR}✗${CLR_RESET}"
ICON_ARROW="${CLR_INFO}→${CLR_RESET}"
ANIM_FRAMES=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")

APP_DIR="$HOME/.termnl"
REPO_URL="https://github.com/nithinworks/termnl"
TMP_DIR="/tmp/termnl-install"

# Animated spinner
show_spinner() {
    local task_pid=$1
    local status_msg=$2
    local frame_idx=0
    
    while kill -0 $task_pid 2>/dev/null; do
        printf "\r  ${CLR_INFO}${ANIM_FRAMES[$frame_idx]}${CLR_RESET} ${status_msg}..."
        frame_idx=$(( (frame_idx + 1) % 10 ))
        sleep 0.1
    done
    
    wait $task_pid
    return $?
}


# Header display
clear
echo ""
echo -e "${CLR_BOLD}"
cat << "EOF"
▗▄▄▄▖▗▄▄▄▖▗▄▄▖ ▗▖  ▗▖▗▖  ▗▖▗▖   
  █  ▐▌   ▐▌ ▐▌▐▛▚▞▜▌▐▛▚▖▐▌▐▌   
  █  ▐▛▀▀▘▐▛▀▚▖▐▌  ▐▌▐▌ ▝▜▌▐▌   
  █  ▐▙▄▄▖▐▌ ▐▌▐▌  ▐▌▐▌  ▐▌▐▙▄▄▖                                                                                                                                                                                                                                                                                                                                                        
EOF
echo -e "${CLR_RESET}"
echo -e "  ${CLR_DIM}The terminal for everyone | Installation${CLR_RESET}"
echo ""
echo -e "  ${CLR_INFO}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${CLR_RESET}"
echo ""

# Step 1: System check
echo -e "Checking system requirements..."

if ! command -v python3 &> /dev/null; then
    echo -e "  ${ICON_ERROR} Python 3 is required"
    exit 1
fi

PY_VER=$(python3 --version | cut -d' ' -f2)
echo -e "  ${ICON_SUCCESS} Python ${PY_VER} found"

echo ""
echo -e "Installing termnl..."

if [ -d "$APP_DIR" ]; then
    (rm -rf "$TMP_DIR" && mkdir -p "$TMP_DIR" && curl -sL "$REPO_URL/archive/main.tar.gz" | tar xz -C "$TMP_DIR" --strip-components=1 && rsync -a --quiet "$TMP_DIR/" "$APP_DIR/" && rm -rf "$TMP_DIR") &
    show_spinner $! "Updating files"
    echo -e "\r  ${ICON_SUCCESS} Updated successfully                         "
else
    (rm -rf "$TMP_DIR" && mkdir -p "$TMP_DIR" "$APP_DIR" && curl -sL "$REPO_URL/archive/main.tar.gz" | tar xz -C "$TMP_DIR" --strip-components=1 && rsync -a --quiet "$TMP_DIR/" "$APP_DIR/" && rm -rf "$TMP_DIR") &
    show_spinner $! "Downloading files"
    echo -e "\r  ${ICON_SUCCESS} Files downloaded successfully                "
fi

cd "$APP_DIR"

# Setup Python environment
python3 -m venv venv &> /dev/null
source venv/bin/activate
pip install --quiet --upgrade pip &> /dev/null

pip install --quiet -r requirements.txt &
show_spinner $! "Installing dependencies"
echo -e "\r  ${ICON_SUCCESS} Dependencies installed                     "

echo ""
echo -e "Configuring shell..."

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/termnl" << 'EOF'
#!/bin/bash
source "$HOME/.termnl/venv/bin/activate"
python "$HOME/.termnl/termnl.py" "$@"
EOF

chmod +x "$HOME/.local/bin/termnl"

configure_path() {
    local config_file="$1"
    
    touch "$config_file"
    
    if ! grep -q '.local/bin' "$config_file" 2>/dev/null; then
        echo '' >> "$config_file"
        echo '# termnl - PATH configuration' >> "$config_file"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$config_file"
    fi
}

configure_autolaunch() {
    local config_file="$1"
    
    if ! grep -q 'termnl # auto-launch' "$config_file" 2>/dev/null; then
        echo '' >> "$config_file"
        echo '# termnl - auto-launch on terminal start' >> "$config_file"
        echo '[ -t 0 ] && [ -z "$TERMNL_RUNNING" ] && [ -x "$HOME/.local/bin/termnl" ] && export TERMNL_RUNNING=1 && termnl # auto-launch' >> "$config_file"
    fi
}

# Always configure PATH
configure_path "$HOME/.zprofile"
configure_path "$HOME/.zshrc"
configure_path "$HOME/.bashrc"
configure_path "$HOME/.bash_profile"

export PATH="$HOME/.local/bin:$PATH"

echo -e "  ${ICON_SUCCESS} Shell configured"

# Ask about auto-launch
echo ""
echo -ne "  ${ICON_ARROW} Auto-launch termnl when you open a terminal? ${CLR_WARN}[y/N]${CLR_RESET} "
read -r autolaunch_choice

if [[ "$autolaunch_choice" =~ ^[Yy]$ ]]; then
    configure_autolaunch "$HOME/.zprofile"
    configure_autolaunch "$HOME/.zshrc"
    configure_autolaunch "$HOME/.bashrc"
    configure_autolaunch "$HOME/.bash_profile"
    echo -e "  ${ICON_SUCCESS} Auto-launch enabled"
    echo -e "  ${CLR_DIM}You can toggle this later with !autolaunch inside termnl${CLR_RESET}"
else
    echo -e "  ${CLR_DIM}Skipped. Type 'termnl' to start manually.${CLR_RESET}"
    echo -e "  ${CLR_DIM}You can enable auto-launch later with !autolaunch inside termnl${CLR_RESET}"
fi

# Completion
echo ""
echo -e "  ${CLR_INFO}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${CLR_RESET}"
echo ""
echo -e "  ${CLR_SUCCESS}${CLR_BOLD}✓ Installation complete!${CLR_RESET}"
echo ""
if [[ "$autolaunch_choice" =~ ^[Yy]$ ]]; then
    echo -e "  ${ICON_ARROW} Open a new terminal window to start termnl"
else
    echo -e "  ${ICON_ARROW} Run: ${CLR_INFO}${CLR_BOLD}termnl${CLR_RESET}"
fi
echo ""