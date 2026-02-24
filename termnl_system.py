import atexit
import os
import shutil
import subprocess
import sys
from datetime import datetime


def read_env(env_file: str) -> tuple[str, str]:
    """Load environment variables from .env and return provider settings."""
    if os.path.exists(env_file):
        with open(env_file) as f:
            for raw in f:
                raw = raw.strip()
                if raw and not raw.startswith("#") and "=" in raw:
                    k, v = raw.split("=", 1)
                    os.environ[k] = v

    provider = os.environ.get("TERMNL_PROVIDER", "gemini")
    openrouter_model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    return provider, openrouter_model


def read_cfg(cfg_file: str) -> bool:
    """Load feature toggle state from config file."""
    learning_mode = False
    if os.path.exists(cfg_file):
        with open(cfg_file) as f:
            for raw in f:
                if "learning_mode=true" in raw:
                    learning_mode = True
                    break
    return learning_mode


def write_cfg(cfg_file: str, learning_mode: bool) -> None:
    with open(cfg_file, "w") as f:
        f.write(f"learning_mode={str(learning_mode).lower()}\n")


def write_env(env_file: str, provider: str, openrouter_model: str) -> None:
    """Persist all provider/env settings."""
    with open(env_file, "w") as f:
        f.write(f"TERMNL_PROVIDER={provider}\n")

        gemini_key = os.environ.get("GEMINI_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        if gemini_key:
            f.write(f"GEMINI_API_KEY={gemini_key}\n")
        if openrouter_key:
            f.write(f"OPENROUTER_API_KEY={openrouter_key}\n")

        f.write(f"OPENROUTER_MODEL={openrouter_model}\n")


def toggle_autolaunch() -> None:
    """Toggle auto-launch in shell config files."""
    shell_configs = [
        os.path.expanduser("~/.zshrc"),
        os.path.expanduser("~/.bashrc"),
        os.path.expanduser("~/.zprofile"),
        os.path.expanduser("~/.bash_profile"),
    ]

    marker = "termnl # auto-launch"
    comment = "# termnl - auto-launch on terminal start"
    launch_line = (
        '[ -t 0 ] && [ -z "$TERMNL_RUNNING" ] && [ -x "$HOME/.local/bin/termnl" ]'
        ' && export TERMNL_RUNNING=1 && termnl # auto-launch'
    )

    is_enabled = False
    for cfg in shell_configs:
        if os.path.exists(cfg):
            with open(cfg) as f:
                if marker in f.read():
                    is_enabled = True
                    break

    if is_enabled:
        for cfg in shell_configs:
            if not os.path.exists(cfg):
                continue
            with open(cfg) as f:
                lines = f.readlines()
            with open(cfg, "w") as f:
                skip_next_blank = False
                for line in lines:
                    if marker in line or comment in line:
                        skip_next_blank = True
                        continue
                    if skip_next_blank and line.strip() == "":
                        skip_next_blank = False
                        continue
                    skip_next_blank = False
                    f.write(line)
        print("\033[33m✗ Auto-launch disabled\033[0m")
        print("\033[2mType 'termnl' to start manually\033[0m")
        return

    for cfg in shell_configs:
        if not os.path.exists(cfg):
            continue
        with open(cfg) as f:
            content = f.read()
        if marker not in content:
            with open(cfg, "a") as f:
                f.write(f"\n{comment}\n{launch_line}\n")

    print("\033[32m✓ Auto-launch enabled\033[0m")
    print("\033[2mtermnl will start when you open a new terminal\033[0m")


def _update_file_targets(path: str) -> list[str]:
    files: list[str] = []
    if not os.path.exists(path):
        return files

    for name in os.listdir(path):
        full = os.path.join(path, name)
        if not os.path.isfile(full):
            continue
        if name.endswith(".py") or name == "requirements.txt":
            files.append(name)
    return sorted(files)


def self_update(current_version: str) -> None:
    """Check for and apply updates from GitHub."""
    print("\n\033[36mChecking for updates...\033[0m")
    print(f"\033[2mCurrent version: v{current_version}\033[0m")

    app_dir = os.path.expanduser("~/.termnl")
    repo_url = "https://github.com/nithinworks/termnl"
    tmp_dir = "/tmp/termnl-update"

    backup_dir = os.path.join(app_dir, "backup")
    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_snapshot = os.path.join(backup_dir, f"snapshot_{ts}")
    os.makedirs(backup_snapshot, exist_ok=True)

    try:
        result = subprocess.run(
            ["curl", "-sL", f"{repo_url}/raw/main/termnl.py"],
            capture_output=True,
            text=True,
        )

        new_version = None
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("__version__"):
                    new_version = line.split("=")[1].strip().strip('"').strip("'")
                    break

        if new_version:
            print(f"\033[2mLatest version: v{new_version}\033[0m")
            if new_version == current_version:
                print("\n\033[32m✓ Already up to date!\033[0m\n")
                return

        for fname in _update_file_targets(app_dir):
            shutil.copy2(os.path.join(app_dir, fname), os.path.join(backup_snapshot, fname))
        print("\033[2m✓ Backed up current version\033[0m")

        print("\033[36mDownloading update...\033[0m")
        subprocess.run(["rm", "-rf", tmp_dir], capture_output=True)
        os.makedirs(tmp_dir, exist_ok=True)

        dl = subprocess.run(
            f"curl -sL {repo_url}/archive/main.tar.gz | tar xz -C {tmp_dir} --strip-components=1",
            shell=True,
            capture_output=True,
            text=True,
        )
        if dl.returncode != 0:
            print("\033[31m✗ Download failed — check your internet connection\033[0m")
            return

        updated = 0
        for fname in _update_file_targets(tmp_dir):
            src = os.path.join(tmp_dir, fname)
            dst = os.path.join(app_dir, fname)
            shutil.copy2(src, dst)
            updated += 1

        shutil.rmtree(tmp_dir, ignore_errors=True)
        if updated:
            print(f"\033[32m✓ Files updated ({updated})\033[0m")
        else:
            print("\033[33m⚠ No updatable files found\033[0m")

        print("\033[36mUpdating dependencies...\033[0m")
        venv_pip = os.path.join(app_dir, "venv", "bin", "pip")
        req_file = os.path.join(app_dir, "requirements.txt")

        if os.path.exists(req_file):
            dep_result = subprocess.run(
                [venv_pip, "install", "-q", "--upgrade", "-r", req_file],
                capture_output=True,
                text=True,
            )
            if dep_result.returncode == 0:
                print("\033[32m✓ Dependencies updated\033[0m")
            else:
                print("\033[33m⚠ Some dependencies may not have updated\033[0m")

        snapshots = sorted(f for f in os.listdir(backup_dir) if f.startswith("snapshot_"))
        for stale in snapshots[:-5]:
            stale_path = os.path.join(backup_dir, stale)
            if os.path.isdir(stale_path):
                shutil.rmtree(stale_path, ignore_errors=True)

        print("\n\033[32m✓ Update complete!\033[0m")
        if new_version and new_version != current_version:
            print(f"\033[2mUpdated to v{new_version}\033[0m")
        print("\033[2mRestart termnl to use the new version\033[0m\n")

        if input("\033[33mRestart now? [y/N]\033[0m ").strip().lower() == "y":
            print("\033[2mRestarting...\033[0m\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        print(f"\n\033[31m✗ Update failed: {e}\033[0m")
        if os.path.exists(backup_snapshot):
            if input("\033[33mRestore from backup? [y/N]\033[0m ").strip().lower() == "y":
                for fname in _update_file_targets(backup_snapshot):
                    src = os.path.join(backup_snapshot, fname)
                    dst = os.path.join(app_dir, fname)
                    shutil.copy2(src, dst)
                print("\033[32m✓ Restored from backup\033[0m")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def uninstall(save_history_callback) -> None:
    confirm = input("\033[33mRemove termnl? [y/N]\033[0m ")
    if confirm.lower() != "y":
        return

    try:
        atexit.unregister(save_history_callback)
    except Exception:
        pass

    install_dir = os.path.expanduser("~/.termnl")
    bin_path = os.path.expanduser("~/.local/bin/termnl")

    if os.path.exists(install_dir):
        shutil.rmtree(install_dir)
    if os.path.exists(bin_path):
        os.remove(bin_path)

    for rc in ("~/.zshrc", "~/.bashrc", "~/.zprofile", "~/.bash_profile"):
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
