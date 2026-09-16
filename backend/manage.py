#!/usr/bin/env python
import os
import sys
from pathlib import Path


def _settings_from_env_file() -> str | None:
    """DJANGO_SETTINGS_MODULE from backend/.env, which the settings package
    only reads once a module is already chosen. On the server that file says
    config.settings.prod (the systemd units load it too); without this, a
    hand-typed `manage.py` command there silently ran with development
    settings (found 2026-09-16)."""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "DJANGO_SETTINGS_MODULE":
            return value.strip().strip('"').strip("'") or None
    return None


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", _settings_from_env_file() or "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
