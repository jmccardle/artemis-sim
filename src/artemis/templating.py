"""Jinja2 templates singleton — prevents circular imports between main.py and views."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).parent

templates = Jinja2Templates(directory=APP_DIR / "templates")
