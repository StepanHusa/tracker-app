# Tracker App

## About
A desktop time tracker with a popup UI showing multiple named timers. Each tracker has start/stop, reset, elapsed time display, and history.

## System & User Context
- **User**: husas, Linux Mint (kernel 6.8.0), AMD GPU, encrypted home
- **University**: Masaryk University
- **Shell**: zsh
- **Python env**: system Python 3 available; user has experience with Python desktop apps
- **Related projects**: `~/Source/Tracker` (Taxlio time tracker, Selenium-based), `~/Source/dictation_tool` (Python daemon with toggle), `~/Source/IsConnect` (connectivity checker)
- **Custom scripts**: `~/bin` — user stores launcher/toggle scripts here
- **Coding preferences**: see `~/Source/coding_preferences/` — **READ `README.md` and `Structure.md` FIRST** before writing any code, and follow the conventions described there

## Tech Stack
- Python 3 with tkinter (or GTK if preferred — to be decided)
- JSON file-based persistence (one file per tracker)
- Keyboard-driven UI with shortcuts

## Data Storage
- Data files: `~/.local/share/tracker_app/trackers/` (XDG-compliant)
- Each tracker: separate JSON file with history of sections (intervals between resets)

## Architecture
See `prompt.md` for full specification.
