#!/usr/bin/env python3
__version__ = "1.0.3"

import signal
import os
import sys
import subprocess
import readline
import shutil
from datetime import datetime

def exit_handler(sig, frame):
    print()
    raise InterruptedError()

signal.signal(signal.SIGINT, exit_handler)

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
config_path = os.path.join(script_dir, ".config")

# Feature states
learning_mode = False
provider = "gemini"  # "gemini" or "openrouter"
openrouter_model = "google/gemini-2.5-flash"
client = None

def load_env():
    global provider, openrouter_model
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value
    # Load provider settings
    provider = os.environ.get("TERMNL_PROVIDER", "gemini")
    openrouter_model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")

def load_config():
    global learning_mode
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                if "learning_mode=true" in line:
                    learning_mode = True

def save_config():
    with open(config_path, "w") as f:
        f.write(f"learning_mode={str(learning_mode).lower()}\n")

def save_env():
    """Save all env settings"""
    with open(env_path, "w") as f:
        f.write(f"TERMNL_PROVIDER={provider}\n")
        if os.environ.get("GEMINI_API_KEY"):
            f.write(f"GEMINI_API_KEY={os.environ['GEMINI_API_KEY']}\n")
        if os.environ.get("OPENROUTER_API_KEY"):
            f.write(f"OPENROUTER_API_KEY={os.environ['OPENROUTER_API_KEY']}\n")
        f.write(f"OPENROUTER_MODEL={openrouter_model}\n")

def setup_provider(switch_mode=False):
    """Set up AI provider — called on first run or via !provider"""
    global provider, openrouter_model
    
    print("\n\033[1mChoose your AI provider:\033[0m")
    print("  \033[36m1.\033[0m Gemini \033[2m(free, recommended)\033[0m")
    print("  \033[36m2.\033[0m OpenRouter \033[2m(200+ models)\033[0m")
    choice = input("\n\033[33m> \033[0m").strip()
    
    if choice == "2":
        provider = "openrouter"
        print(f"\n\033[36mGet your key at: https://openrouter.ai/keys\033[0m\n")
        api_key = input("\033[33mEnter your OpenRouter API key:\033[0m ").strip()
        if not api_key:
            print("No API key provided.")
            if not switch_mode:
                sys.exit(1)
            return False
        
        # Validate
        print("\033[2mValidating key...\033[0m", end="", flush=True)
        try:
            from openai import OpenAI
            test_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            test_client.chat.completions.create(
                model="google/gemini-2.5-flash",
                messages=[{"role": "user", "content": "respond with just the word ok"}],
                max_tokens=5
            )
            print("\r\033[32m✓ API key validated!\033[0m   ")
        except Exception as e:
            err = str(e)
            if "401" in err or "invalid" in err.lower() or "unauthorized" in err.lower():
                print(f"\r\033[31m✗ Invalid API key\033[0m   ")
                print("\033[2mPlease check your key and try again\033[0m")
                if not switch_mode:
                    sys.exit(1)
                return False
            else:
                print(f"\r\033[33m⚠ Could not validate (network issue?) — saving anyway\033[0m   ")
        
        os.environ["OPENROUTER_API_KEY"] = api_key
        
        # Ask for model
        print()
        model_input = input("\033[33mEnter model\033[0m \033[2m(default: google/gemini-2.5-flash)\033[0m\033[33m:\033[0m ").strip()
        openrouter_model = model_input if model_input else "google/gemini-2.5-flash"
        
    else:
        provider = "gemini"
        print(f"\n\033[36mGet your free key at: https://aistudio.google.com/apikey\033[0m\n")
        api_key = input("\033[33mEnter your Gemini API key:\033[0m ").strip()
        if not api_key:
            print("No API key provided.")
            if not switch_mode:
                sys.exit(1)
            return False
        
        # Validate
        print("\033[2mValidating key...\033[0m", end="", flush=True)
        try:
            from google import genai
            test_client = genai.Client(api_key=api_key)
            test_client.models.generate_content(
                model="gemini-2.5-flash",
                contents="respond with just the word 'ok'"
            )
            print("\r\033[32m✓ API key validated!\033[0m   ")
        except Exception as e:
            err = str(e)
            if "401" in err or "invalid" in err.lower() or "api_key" in err.lower():
                print(f"\r\033[31m✗ Invalid API key\033[0m   ")
                print("\033[2mPlease check your key and try again\033[0m")
                if not switch_mode:
                    sys.exit(1)
                return False
            else:
                print(f"\r\033[33m⚠ Could not validate (network issue?) — saving anyway\033[0m   ")
        
        os.environ["GEMINI_API_KEY"] = api_key
    
    save_env()
    print("\033[32m✓ Provider configured!\033[0m\n")
    return True

def show_help():
    print("\033[1mCommands:\033[0m")
    print("\033[36m  !\033[0m<cmd>      - Force run command without AI")
    print("\033[36m  !learn\033[0m      - Toggle learning mode")
    print("\033[36m  !provider\033[0m   - Switch AI provider (Gemini/OpenRouter)")
    print("\033[36m  !model\033[0m      - Change OpenRouter model")
    print("\033[36m  !autolaunch\033[0m - Toggle auto-launch on terminal start")
    print("\033[36m  !update\033[0m     - Update to latest version")
    print("\033[36m  !uninstall\033[0m  - Remove termnl")
    print("\033[36m  !help\033[0m       - Show this help")
    print("\033[36m  exit/quit\033[0m   - Exit termnl, return to normal shell")
    print()

def toggle_autolaunch():
    """Toggle auto-launch in shell config files"""
    shell_configs = [
        os.path.expanduser("~/.zshrc"),
        os.path.expanduser("~/.bashrc"),
        os.path.expanduser("~/.zprofile"),
        os.path.expanduser("~/.bash_profile"),
    ]
    
    autolaunch_marker = "termnl # auto-launch"
    autolaunch_comment = "# termnl - auto-launch on terminal start"
    autolaunch_line = '[ -t 0 ] && [ -z "$TERMNL_RUNNING" ] && [ -x "$HOME/.local/bin/termnl" ] && export TERMNL_RUNNING=1 && termnl # auto-launch'
    
    # Check current state by looking at the primary config
    is_enabled = False
    for config in shell_configs:
        if os.path.exists(config):
            with open(config) as f:
                if autolaunch_marker in f.read():
                    is_enabled = True
                    break
    
    if is_enabled:
        # Disable: remove auto-launch lines from all configs
        for config in shell_configs:
            if not os.path.exists(config):
                continue
            with open(config) as f:
                lines = f.readlines()
            with open(config, "w") as f:
                skip_blank = False
                for line in lines:
                    if autolaunch_marker in line or autolaunch_comment in line:
                        skip_blank = True
                        continue
                    if skip_blank and line.strip() == "":
                        skip_blank = False
                        continue
                    skip_blank = False
                    f.write(line)
        print("\033[33m✗ Auto-launch disabled\033[0m")
        print("\033[2mType 'termnl' to start manually\033[0m")
    else:
        # Enable: add auto-launch lines to all configs
        for config in shell_configs:
            if not os.path.exists(config):
                continue
            with open(config) as f:
                content = f.read()
            if autolaunch_marker not in content:
                with open(config, "a") as f:
                    f.write(f"\n{autolaunch_comment}\n")
                    f.write(f"{autolaunch_line}\n")
        print("\033[32m✓ Auto-launch enabled\033[0m")
        print("\033[2mtermnl will start when you open a new terminal\033[0m")

def get_new_version(source_file: str) -> str:
    """Extract version from source file"""
    try:
        with open(source_file) as f:
            for line in f:
                if line.startswith("__version__"):
                    # Extract version from line like: __version__ = "1.0.0"
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None

def update_termnl():
    """Update termnl to latest version"""
    print(f"\n\033[36mChecking for updates...\033[0m")
    print(f"\033[2mCurrent version: v{__version__}\033[0m")
    
    app_dir = os.path.expanduser("~/.termnl")
    repo_url = "https://github.com/nithinworks/termnl"
    tmp_dir = "/tmp/termnl-update"
    
    # Create backup directory
    backup_dir = os.path.join(app_dir, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"termnl_{timestamp}.py")
    current_file = os.path.join(app_dir, "termnl.py")
    
    try:
        # Check latest version from GitHub
        result = subprocess.run(
            ["curl", "-sL", f"{repo_url}/raw/main/termnl.py"],
            capture_output=True, text=True
        )
        
        new_version = None
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("__version__"):
                    new_version = line.split("=")[1].strip().strip('"').strip("'")
                    break
        
        if new_version:
            print(f"\033[2mLatest version: v{new_version}\033[0m")
            if new_version == __version__:
                print("\n\033[32m✓ Already up to date!\033[0m\n")
                return
        
        # Backup current version
        if os.path.exists(current_file):
            shutil.copy2(current_file, backup_file)
            print(f"\033[2m✓ Backed up current version\033[0m")
        
        # Download and extract from GitHub
        print("\033[36mDownloading update...\033[0m")
        
        # Clean tmp, download tarball, extract
        subprocess.run(["rm", "-rf", tmp_dir], capture_output=True)
        os.makedirs(tmp_dir, exist_ok=True)
        
        dl_result = subprocess.run(
            f"curl -sL {repo_url}/archive/main.tar.gz | tar xz -C {tmp_dir} --strip-components=1",
            shell=True, capture_output=True, text=True
        )
        
        if dl_result.returncode != 0:
            print("\033[31m✗ Download failed — check your internet connection\033[0m")
            return
        
        # Copy files
        for filename in ["termnl.py", "requirements.txt"]:
            src = os.path.join(tmp_dir, filename)
            dst = os.path.join(app_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
        
        # Clean up tmp
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("\033[32m✓ Files updated\033[0m")
        
        # Update dependencies
        print("\033[36mUpdating dependencies...\033[0m")
        venv_pip = os.path.join(app_dir, "venv", "bin", "pip")
        req_file = os.path.join(app_dir, "requirements.txt")
        
        if os.path.exists(req_file):
            result = subprocess.run(
                [venv_pip, "install", "-q", "--upgrade", "-r", req_file],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("\033[32m✓ Dependencies updated\033[0m")
            else:
                print("\033[33m⚠ Some dependencies may not have updated\033[0m")
        
        # Cleanup old backups (keep last 5)
        backups = sorted([f for f in os.listdir(backup_dir) if f.startswith("termnl_")])
        if len(backups) > 5:
            for old_backup in backups[:-5]:
                os.remove(os.path.join(backup_dir, old_backup))
        
        print("\n\033[32m✓ Update complete!\033[0m")
        if new_version and new_version != __version__:
            print(f"\033[2mUpdated to v{new_version}\033[0m")
        print("\033[2mRestart termnl to use the new version\033[0m\n")
        
        # Ask if user wants to restart
        restart = input("\033[33mRestart now? [y/N]\033[0m ").strip().lower()
        if restart == "y":
            print("\033[2mRestarting...\033[0m\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        
    except Exception as e:
        print(f"\n\033[31m✗ Update failed: {e}\033[0m")
        
        # Restore from backup if update failed
        if os.path.exists(backup_file):
            restore = input("\033[33mRestore from backup? [y/N]\033[0m ").strip().lower()
            if restore == "y":
                shutil.copy2(backup_file, current_file)
                print("\033[32m✓ Restored from backup\033[0m")

load_env()
load_config()

def init_client():
    """Initialize the appropriate AI client based on provider"""
    global client
    if provider == "openrouter":
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY", "")
        )
    else:
        from google import genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

def ai_generate(prompt: str) -> str:
    """Generate text from AI — works with both providers"""
    if provider == "openrouter":
        response = client.chat.completions.create(
            model=openrouter_model,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content if response.choices else None
        return text.strip() if text else None
    else:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip() if response.text else None

# First run or missing key for current provider
has_key = (
    (provider == "gemini" and os.environ.get("GEMINI_API_KEY")) or
    (provider == "openrouter" and os.environ.get("OPENROUTER_API_KEY"))
)
if not has_key:
    setup_provider()
    print("\033[1mtermnl\033[0m - talk to your terminal\n")
    show_help()

init_client()

command_history = []
MAX_HISTORY = 10
MAX_CONTEXT_CHARS = 4000

def get_context_size() -> int:
    return sum(len(e["command"]) + len(e["output"]) for e in command_history)

def add_to_history(command: str, output: str = ""):
    command_history.append({
        "command": command,
        "output": output[:500] if output else ""
    })
    while len(command_history) > MAX_HISTORY:
        command_history.pop(0)
    while get_context_size() > MAX_CONTEXT_CHARS and len(command_history) > 1:
        command_history.pop(0)

def format_history() -> str:
    if not command_history:
        return "No previous commands."
    
    lines = []
    for i, entry in enumerate(command_history[-5:], 1):
        lines.append(f"{i}. $ {entry['command']}")
        if entry['output']:
            output_lines = entry['output'].strip().split('\n')[:2]
            for line in output_lines:
                lines.append(f"   {line}")
    return "\n".join(lines)


def get_command(user_input: str, cwd: str) -> dict:
    """Returns dict with 'commands' (list) and optionally 'explanation'"""
    history_context = format_history()
    prompt = f"""You are a shell command translator. Convert the user's request into shell commands for macOS/zsh.
Current directory: {cwd}

Recent command history:
{history_context}

Rules:
- If the request requires multiple steps, output commands on separate lines
- Each line should be a single command
- No explanations, no markdown, no backticks, no numbering
- If unclear, make a reasonable assumption
- Prefer simple, common commands
- Use the command history for context (e.g., "do that again", "delete the file I just created")

User request: {user_input}"""

    response_text = ai_generate(prompt)
    
    if not response_text:
        return {"commands": []}
    
    commands = [cmd.strip() for cmd in response_text.split('\n') if cmd.strip()]
    
    result = {"commands": commands}
    
    # If learning mode, get explanation
    if learning_mode and commands:
        explain_prompt = f"""Briefly explain what this command does in 1-2 lines for a beginner.
Command: {commands[0] if len(commands) == 1 else 'Multi-step: ' + ' && '.join(commands)}

Give a concise tip about the command or its flags. Start with 💡"""
        
        try:
            explanation = ai_generate(explain_prompt)
            if explanation:
                result["explanation"] = explanation
        except Exception:
            pass
    
    return result

def is_natural_language(text: str) -> bool:
    if text.startswith("!"):
        return False
    shell_commands = ["ls", "pwd", "clear", "whoami", "date", "cal", 
                      "top", "htop", "which", "man", "touch", "head", "tail",
                      "grep", "find", "sort", "wc", "diff", "tar", "zip", "unzip"]
    shell_starters = ["cd ", "ls ", "echo ", "cat ", "mkdir ", "rm ", "cp ", "mv ", 
                      "git ", "npm ", "node ", "npx ", "python", "pip ", "brew ", "curl ", 
                      "wget ", "chmod ", "chown ", "sudo ", "vi ", "vim ", "nano ", "code ", 
                      "open ", "export ", "source ", "docker ", "kubectl ", "aws ", "gcloud ",
                      "./", "/", "~", "$", ">", ">>", "|", "&&"]
    if text in shell_commands:
        return False
    return not any(text.startswith(s) for s in shell_starters)

# Commands that need direct terminal access (interactive/TUI)
INTERACTIVE_COMMANDS = {"clear", "top", "htop", "vim", "vi", "nano", "less", "more", "man", "ssh", "tmux", "screen"}

def is_interactive(cmd: str) -> bool:
    """Check if command needs direct terminal access"""
    base = cmd.split()[0] if cmd.split() else ""
    return base in INTERACTIVE_COMMANDS

def execute_command(cmd: str) -> tuple:
    """Execute command and return (stdout, stderr, returncode)"""
    if is_interactive(cmd):
        r = subprocess.run(cmd, shell=True)
        return "", "", r.returncode
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def main():
    global learning_mode, client, provider, openrouter_model
    
    while True:
        try:
            cwd = os.getcwd()
            prompt_prefix = f"\033[32m{os.path.basename(cwd)}\033[0m"
            
            # Show mode indicators
            if learning_mode:
                prompt_prefix += " \033[2m[learn]\033[0m"
            if provider == "openrouter" and openrouter_model != "google/gemini-2.5-flash":
                model_short = openrouter_model.split("/")[-1] if "/" in openrouter_model else openrouter_model
                prompt_prefix += f" \033[2m[{model_short}]\033[0m"
            
            prompt_prefix += " > "
            
            user_input = input(prompt_prefix).strip()
            
            if not user_input:
                continue
            
            # Exit commands
            if user_input in ("exit", "quit"):
                print("\033[2mbye 👋\033[0m")
                break
            
            # Handle cd commands
            if user_input.startswith("cd "):
                path = os.path.expanduser(user_input[3:].strip())
                try:
                    os.chdir(path)
                except Exception as e:
                    print(f"cd: {e}")
                continue
            elif user_input == "cd":
                os.chdir(os.path.expanduser("~"))
                continue
            
            # Special commands
            if user_input == "!provider":
                if setup_provider(switch_mode=True):
                    init_client()
                continue
            
            if user_input == "!model":
                if provider == "openrouter":
                    print(f"\033[2mCurrent model: {openrouter_model}\033[0m")
                    new_model = input("\033[33mEnter new model:\033[0m ").strip()
                    if new_model:
                        openrouter_model = new_model
                        save_env()
                        print(f"\033[32m✓ Model set to {openrouter_model}\033[0m")
                else:
                    print("\033[2mModel selection is only available with OpenRouter\033[0m")
                    print("\033[2mSwitch with !provider first\033[0m")
                continue
            
            if user_input == "!learn":
                learning_mode = not learning_mode
                save_config()
                status = "enabled" if learning_mode else "disabled"
                print(f"\033[36m💡 Learning mode {status}\033[0m")
                continue
            

            
            if user_input == "!autolaunch":
                toggle_autolaunch()
                continue
            
            if user_input == "!update":
                update_termnl()
                continue
            
            if user_input == "!uninstall":
                confirm = input("\033[33mRemove termnl? [y/N]\033[0m ")
                if confirm.lower() == "y":
                    install_dir = os.path.expanduser("~/.termnl")
                    bin_path = os.path.expanduser("~/.local/bin/termnl")
                    if os.path.exists(install_dir):
                        shutil.rmtree(install_dir)
                    if os.path.exists(bin_path):
                        os.remove(bin_path)
                    # Clean up shell configs
                    for rc in ["~/.zshrc", "~/.bashrc", "~/.zprofile", "~/.bash_profile"]:
                        rc_path = os.path.expanduser(rc)
                        if not os.path.exists(rc_path):
                            continue
                        with open(rc_path) as f:
                            lines = f.readlines()
                        with open(rc_path, "w") as f:
                            for line in lines:
                                if "termnl" not in line:
                                    f.write(line)
                    print("\033[32m✓ termnl uninstalled\033[0m")
                    sys.exit(0)
                continue
            
            if user_input == "!help":
                show_help()
                continue
            
            # Force command execution with !
            if user_input.startswith("!"):
                cmd = user_input[1:]
                if not cmd:
                    continue
                stdout, stderr, _ = execute_command(cmd)
                print(stdout, end="")
                if stderr:
                    print(stderr, end="")
                add_to_history(cmd, stdout + stderr)
                continue
            
            # Direct shell commands
            if not is_natural_language(user_input):
                stdout, stderr, _ = execute_command(user_input)
                print(stdout, end="")
                if stderr:
                    print(stderr, end="")
                add_to_history(user_input, stdout + stderr)
                continue
            
            # Natural language → AI translation
            result = get_command(user_input, cwd)
            commands = result["commands"]
            explanation = result.get("explanation")
            
            if not commands:
                print("\033[31mcouldn't translate that - try rephrasing or use !<cmd>\033[0m")
                continue
            
            if len(commands) == 1:
                # Single command
                command = commands[0]
                confirm = input(f"\033[33m→ {command}\033[0m [Enter] ")
                
                if confirm == "":
                    if command.startswith("cd "):
                        path = os.path.expanduser(command[3:].strip())
                        try:
                            os.chdir(path)
                        except Exception as e:
                            print(f"cd: {e}")
                    else:
                        stdout, stderr, _ = execute_command(command)
                        print(stdout, end="")
                        if stderr:
                            print(stderr, end="")
                        add_to_history(command, stdout + stderr)
                        
                        # Show learning tip
                        if learning_mode and explanation:
                            print(f"\n\033[2m{explanation}\033[0m\n")
            else:
                # Multi-step commands
                print(f"\033[33mMulti-step workflow ({len(commands)} commands):\033[0m")
                for i, cmd in enumerate(commands, 1):
                    print(f"  {i}. {cmd}")
                
                confirm = input(f"\n\033[33mRun all?\033[0m [y/n/step] ").strip().lower()
                
                if confirm in ["y", "yes", ""]:
                    # Run all commands
                    for i, cmd in enumerate(commands, 1):
                        print(f"\033[2m[{i}/{len(commands)}]\033[0m {cmd}")
                        
                        if cmd.startswith("cd "):
                            path = os.path.expanduser(cmd[3:].strip())
                            try:
                                os.chdir(path)
                                print("\033[32m✓\033[0m")
                            except Exception as e:
                                print(f"\033[31m✗ cd: {e}\033[0m")
                                break
                        else:
                            stdout, stderr, rc = execute_command(cmd)
                            if stdout:
                                print(stdout, end="")
                            if stderr:
                                print(f"\033[31m{stderr}\033[0m", end="")
                            add_to_history(cmd, stdout + stderr)
                            
                            if rc == 0:
                                print("\033[32m✓\033[0m")
                            else:
                                print("\033[31m✗\033[0m")
                                break
                    
                    if learning_mode and explanation:
                        print(f"\n\033[2m{explanation}\033[0m\n")
                
                elif confirm == "n":
                    # IMPROVEMENT #1: Cancellation message
                    print("\033[2mCancelled\033[0m")
                
                elif confirm == "step":
                    # Step-by-step execution
                    for i, cmd in enumerate(commands, 1):
                        step_confirm = input(f"\033[33m[{i}/{len(commands)}] {cmd}\033[0m [y/n/q] ").strip().lower()
                        
                        if step_confirm in ["y", "yes", ""]:
                            if cmd.startswith("cd "):
                                path = os.path.expanduser(cmd[3:].strip())
                                try:
                                    os.chdir(path)
                                    print("\033[32m✓\033[0m")
                                except Exception as e:
                                    print(f"\033[31m✗ cd: {e}\033[0m")
                            else:
                                stdout, stderr, _ = execute_command(cmd)
                                print(stdout, end="")
                                if stderr:
                                    print(f"\033[31m{stderr}\033[0m", end="")
                                add_to_history(cmd, stdout + stderr)
                        elif step_confirm == "q":
                            print("\033[2mStopped\033[0m")
                            break
            
        except EOFError:
            print("\n\033[2mbye 👋\033[0m")
            break
        except (InterruptedError, KeyboardInterrupt):
            continue
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print("\033[31mrate limit hit - wait a moment and try again\033[0m")
            elif "InterruptedError" not in err and "KeyboardInterrupt" not in err:
                print(f"\033[31merror: {err[:100]}\033[0m")

if __name__ == "__main__":
    main()
