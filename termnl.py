#!/usr/bin/env python3
__version__ = "1.0.3"

import atexit
import os
import platform
import readline
import signal
import sys

from termnl_ai import ask_ai, create_client, setup_provider
from termnl_runtime import SessionLog, classify_input, run, translate
from termnl_system import (
    read_cfg,
    read_env,
    self_update,
    toggle_autolaunch,
    uninstall,
    write_cfg,
    write_env,
)

# --- Signal Handling ---
_interrupted = False


def _on_sigint(sig, frame):
    global _interrupted
    _interrupted = True
    print()


signal.signal(signal.SIGINT, _on_sigint)

# --- Paths & State ---
_base_dir = os.path.dirname(os.path.abspath(__file__))
_env_file = os.path.join(_base_dir, ".env")
_cfg_file = os.path.join(_base_dir, ".config")
_os_shell = "macOS/zsh" if platform.system() == "Darwin" else "Linux/bash"

# --- Readline Persistence ---
_history_file = os.path.join(_base_dir, ".readline_history")
try:
    readline.read_history_file(_history_file)
except OSError:
    pass


def _save_history():
    try:
        readline.write_history_file(_history_file)
    except OSError:
        pass


atexit.register(_save_history)

learning_mode = False
provider = "gemini"
openrouter_model = "google/gemini-2.5-flash"
client = None
session_log = SessionLog()


# --- Help & Utilities ---

def _print_help():
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


# --- Boot ---

def _boot():
    global learning_mode, provider, openrouter_model, client

    provider, openrouter_model = read_env(_env_file)
    learning_mode = read_cfg(_cfg_file)

    has_key = (
        (provider == "gemini" and os.environ.get("GEMINI_API_KEY"))
        or (provider == "openrouter" and os.environ.get("OPENROUTER_API_KEY"))
    )

    if not has_key:
        ok, provider, openrouter_model = setup_provider(
            provider,
            openrouter_model,
            lambda p, m: write_env(_env_file, p, m),
        )
        if not ok:
            sys.exit(1)
        print("\033[1mtermnl\033[0m - talk to your terminal\n")
        _print_help()

    client = create_client(provider)


_boot()


# --- REPL: Builtin Handlers ---

def _handle_cd(args: str):
    path = os.path.expanduser(args.strip()) if args.strip() else os.path.expanduser("~")
    try:
        os.chdir(path)
    except Exception as e:
        print(f"cd: {e}")


def _handle_provider():
    global provider, openrouter_model, client
    ok, new_provider, new_model = setup_provider(
        provider,
        openrouter_model,
        lambda p, m: write_env(_env_file, p, m),
        switch_mode=True,
    )
    if ok:
        provider = new_provider
        openrouter_model = new_model
        client = create_client(provider)


def _handle_model():
    global openrouter_model
    if provider == "openrouter":
        print(f"\033[2mCurrent model: {openrouter_model}\033[0m")
        new_model = input("\033[33mEnter new model:\033[0m ").strip()
        if new_model:
            openrouter_model = new_model
            write_env(_env_file, provider, openrouter_model)
            print(f"\033[32m✓ Model set to {openrouter_model}\033[0m")
    else:
        print("\033[2mModel selection is only available with OpenRouter\033[0m")
        print("\033[2mSwitch with !provider first\033[0m")


def _handle_learn():
    global learning_mode
    learning_mode = not learning_mode
    write_cfg(_cfg_file, learning_mode)
    status = "enabled" if learning_mode else "disabled"
    print(f"\033[36m💡 Learning mode {status}\033[0m")


def _handle_force_run(cmd: str):
    stdout, stderr, rc = run(cmd)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="")
    session_log.record(cmd, stdout + stderr, rc)


# --- REPL: Execution Handlers ---

def _exec_single(command: str, explanation: str | None = None):
    """Handle a single translated command — confirm and run."""
    confirm = input(f"\033[33m→ {command}\033[0m [Enter] ")
    if confirm != "":
        return

    if command.startswith("cd "):
        _handle_cd(command[3:])
        return

    stdout, stderr, rc = run(command)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="")
    session_log.record(command, stdout + stderr, rc)

    if learning_mode and explanation:
        print(f"\n\033[2m{explanation}\033[0m\n")


def _run_sequence(commands: list[str]):
    """Run all commands sequentially, stopping on failure."""
    for i, cmd in enumerate(commands, 1):
        print(f"\033[2m[{i}/{len(commands)}]\033[0m {cmd}")
        if cmd.startswith("cd "):
            try:
                os.chdir(os.path.expanduser(cmd[3:].strip()))
                print("\033[32m✓\033[0m")
            except Exception as e:
                print(f"\033[31m✗ cd: {e}\033[0m")
                break
            continue

        stdout, stderr, rc = run(cmd)
        if stdout:
            print(stdout, end="")
        if stderr:
            print(f"\033[31m{stderr}\033[0m", end="")
        session_log.record(cmd, stdout + stderr, rc)
        print("\033[32m✓\033[0m" if rc == 0 else "\033[31m✗\033[0m")
        if rc != 0:
            break


def _run_stepping(commands: list[str]):
    """Run commands one at a time, asking before each."""
    for i, cmd in enumerate(commands, 1):
        choice = input(f"\033[33m[{i}/{len(commands)}] {cmd}\033[0m [y/n/q] ").strip().lower()
        if choice in ("y", "yes", ""):
            if cmd.startswith("cd "):
                try:
                    os.chdir(os.path.expanduser(cmd[3:].strip()))
                    print("\033[32m✓\033[0m")
                except Exception as e:
                    print(f"\033[31m✗ cd: {e}\033[0m")
            else:
                stdout, stderr, _ = run(cmd)
                if stdout:
                    print(stdout, end="")
                if stderr:
                    print(f"\033[31m{stderr}\033[0m", end="")
                session_log.record(cmd, stdout + stderr)
        elif choice == "q":
            print("\033[2mStopped\033[0m")
            break


def _exec_multi(commands: list[str], explanation: str | None = None):
    """Handle a multi-step workflow — confirm strategy and run."""
    print(f"\033[33mMulti-step workflow ({len(commands)} commands):\033[0m")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")

    confirm = input("\n\033[33mRun all?\033[0m [y/n/step] ").strip().lower()

    if confirm in ("y", "yes", ""):
        _run_sequence(commands)
        if learning_mode and explanation:
            print(f"\n\033[2m{explanation}\033[0m\n")
        return

    if confirm == "step":
        _run_stepping(commands)
        return

    print("\033[2mCancelled\033[0m")


# Dispatch table for builtin commands
_BUILTINS = {
    "!provider": _handle_provider,
    "!model": _handle_model,
    "!learn": _handle_learn,
    "!autolaunch": toggle_autolaunch,
    "!update": lambda: self_update(__version__),
    "!uninstall": lambda: uninstall(_save_history),
    "!help": _print_help,
}


# --- Main REPL ---

def main():
    global _interrupted

    while True:
        if _interrupted:
            _interrupted = False
            continue

        try:
            cwd = os.getcwd()
            prompt_prefix = f"\001\033[32m\002{os.path.basename(cwd)}\001\033[0m\002"

            if learning_mode:
                prompt_prefix += " \001\033[2m\002[learn]\001\033[0m\002"
            if provider == "openrouter" and openrouter_model != "google/gemini-2.5-flash":
                short_model = openrouter_model.rsplit("/", 1)[-1]
                prompt_prefix += f" \001\033[2m\002[{short_model}]\001\033[0m\002"

            prompt_prefix += " > "
            user_input = input(prompt_prefix).strip()

            if not user_input:
                continue

            if user_input in ("exit", "quit"):
                print("\033[2mbye 👋\033[0m")
                break

            if user_input == "cd" or user_input.startswith("cd "):
                _handle_cd(user_input[3:])
                continue

            if user_input in _BUILTINS:
                _BUILTINS[user_input]()
                continue

            if user_input.startswith("!"):
                cmd = user_input[1:]
                if cmd:
                    _handle_force_run(cmd)
                continue

            kind = classify_input(user_input)

            if kind == "shell":
                stdout, stderr, rc = run(user_input)
                if stdout:
                    print(stdout, end="")
                if stderr:
                    print(stderr, end="")
                session_log.record(user_input, stdout + stderr, rc)
                continue

            result = translate(
                user_input,
                cwd,
                _os_shell,
                learning_mode,
                session_log.render_context(),
                lambda prompt: ask_ai(client, provider, openrouter_model, prompt),
            )
            commands = result["commands"]
            explanation = result.get("explanation")

            if not commands:
                print("\033[31mcouldn't translate that - try rephrasing or use !<cmd>\033[0m")
                continue

            if len(commands) == 1:
                _exec_single(commands[0], explanation)
            else:
                _exec_multi(commands, explanation)

        except EOFError:
            print("\n\033[2mbye 👋\033[0m")
            break
        except KeyboardInterrupt:
            _interrupted = False
            continue
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print("\033[31mrate limit hit - wait a moment and try again\033[0m")
            elif "Interrupt" not in err:
                print(f"\033[31merror: {err[:100]}\033[0m")


if __name__ == "__main__":
    main()
