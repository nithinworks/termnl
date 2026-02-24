import os
import sys
from typing import Callable


def validate_openrouter_key(api_key: str) -> bool:
    """Validate an OpenRouter API key. Returns True if valid or indeterminate."""
    print("\033[2mValidating key...\033[0m", end="", flush=True)
    try:
        from openai import OpenAI

        test = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        test.chat.completions.create(
            model="google/gemini-2.5-flash",
            messages=[{"role": "user", "content": "respond with just the word ok"}],
            max_tokens=5,
        )
        print("\r\033[32m✓ API key validated!\033[0m   ")
        return True
    except Exception as e:
        err = str(e).lower()
        if any(s in err for s in ("401", "invalid", "unauthorized")):
            print("\r\033[31m✗ Invalid API key\033[0m   ")
            print("\033[2mPlease check your key and try again\033[0m")
            return False
        print("\r\033[33m⚠ Could not validate (network issue?) — saving anyway\033[0m   ")
        return True


def validate_gemini_key(api_key: str) -> bool:
    """Validate a Gemini API key. Returns True if valid or indeterminate."""
    print("\033[2mValidating key...\033[0m", end="", flush=True)
    try:
        from google import genai

        test = genai.Client(api_key=api_key)
        test.models.generate_content(
            model="gemini-2.5-flash",
            contents="respond with just the word 'ok'",
        )
        print("\r\033[32m✓ API key validated!\033[0m   ")
        return True
    except Exception as e:
        err = str(e).lower()
        if any(s in err for s in ("401", "invalid", "api_key")):
            print("\r\033[31m✗ Invalid API key\033[0m   ")
            print("\033[2mPlease check your key and try again\033[0m")
            return False
        print("\r\033[33m⚠ Could not validate (network issue?) — saving anyway\033[0m   ")
        return True


def setup_provider(
    provider: str,
    openrouter_model: str,
    persist_env: Callable[[str, str], None],
    switch_mode: bool = False,
) -> tuple[bool, str, str]:
    """Interactive provider setup — called on first run or via !provider."""
    print("\n\033[1mChoose your AI provider:\033[0m")
    print("  \033[36m1.\033[0m Gemini \033[2m(free, recommended)\033[0m")
    print("  \033[36m2.\033[0m OpenRouter \033[2m(200+ models)\033[0m")
    choice = input("\n\033[33m> \033[0m").strip()

    new_provider = provider
    new_model = openrouter_model

    if choice == "2":
        new_provider = "openrouter"
        print("\n\033[36mGet your key at: https://openrouter.ai/keys\033[0m\n")
        api_key = input("\033[33mEnter your OpenRouter API key:\033[0m ").strip()
        if not api_key:
            print("No API key provided.")
            if switch_mode:
                return False, provider, openrouter_model
            sys.exit(1)

        if not validate_openrouter_key(api_key):
            if switch_mode:
                return False, provider, openrouter_model
            sys.exit(1)

        os.environ["OPENROUTER_API_KEY"] = api_key

        print()
        model_input = input(
            "\033[33mEnter model\033[0m \033[2m(default: google/gemini-2.5-flash)\033[0m\033[33m:\033[0m "
        ).strip()
        new_model = model_input or "google/gemini-2.5-flash"
    else:
        new_provider = "gemini"
        print("\n\033[36mGet your free key at: https://aistudio.google.com/apikey\033[0m\n")
        api_key = input("\033[33mEnter your Gemini API key:\033[0m ").strip()
        if not api_key:
            print("No API key provided.")
            if switch_mode:
                return False, provider, openrouter_model
            sys.exit(1)

        if not validate_gemini_key(api_key):
            if switch_mode:
                return False, provider, openrouter_model
            sys.exit(1)

        os.environ["GEMINI_API_KEY"] = api_key

    persist_env(new_provider, new_model)
    print("\033[32m✓ Provider configured!\033[0m\n")
    return True, new_provider, new_model


def create_client(provider: str):
    """Instantiate the AI client for the active provider."""
    if provider == "openrouter":
        from openai import OpenAI

        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        )

    from google import genai

    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


def ask_ai(client, provider: str, openrouter_model: str, prompt: str) -> str | None:
    """Send a prompt to the active AI provider and return the text response."""
    if provider == "openrouter":
        resp = client.chat.completions.create(
            model=openrouter_model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content if resp.choices else None
        return text.strip() if text else None

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return resp.text.strip() if resp.text else None
