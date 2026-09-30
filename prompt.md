# Tracker App — Specification

## Purpose
A desktop popup-window app with multiple time trackers visible at once. Designed for quick keyboard-driven time tracking.

## UI
- A popup window showing a list of trackers
- Each tracker row displays:
  - **Name** (set on creation via "New" button, renamable by double-clicking)
  - **Elapsed time** (formatted HH:MM:SS or similar)
  - **Start/Stop button**
  - **Reset button**
  - **Date of last reset** (in small text)

## Keyboard Shortcuts
- `Esc` — close the UI window
- `1`–`9` or arrow keys — select a tracker
- `Space` — start/stop the selected tracker
- `r` — reset the selected tracker
- `e` — edit (adjust) the elapsed time of the selected tracker
- `n` — create a new tracker
- `Delete` / `d` — delete the selected tracker (with confirmation)
- `F2` or double-click — rename the selected tracker

## Data Model
Storage location (XDG-compliant):
- **Data** (tracker JSON files): `~/.local/share/tracker_app/trackers/` — one JSON file per tracker
- **Config** (if needed): `~/.config/tracker_app/`

Each tracker file contains a JSON object:

```json
{
  "name": "Tracker Name",
  "created": "2026-03-20T10:00:00",
  "sections": [
    {
      "id": "",
      "finished": true,
      "intervals": [
        {
          "start": "2026-03-20T10:00:00",
          "end": "2026-03-20T10:30:00"
        },
        {
          "start": "2026-03-20T11:00:00",
          "end": "2026-03-20T11:45:00"
        }
      ],
      "last_start": null,
      "adjustments": [
        {
          "seconds": 420,
          "created": "2026-03-20T11:50:00",
          "reason": ""
        }
      ]
    },
    {
      "id": "",
      "finished": false,
      "intervals": [
        {
          "start": "2026-03-20T12:00:00",
          "end": "2026-03-20T12:20:00"
        }
      ],
      "last_start": "2026-03-20T13:00:00"
    }
  ]
}
```

### Data Logic
- **Sections**: Each section represents a period between resets. When a tracker is reset, the current section is marked `finished: true` and a new section is created.
- **Intervals**: Each interval has a `start` and `end` timestamp, representing a continuous running period within a section.
- **`last_start`**: Set to the current timestamp when the timer starts. Set to `null` when the timer stops (at which point a completed interval is added). If `last_start` is not null, the timer is currently running.
- **`finished`**: All sections before the current one have `finished: true`. The active section has `finished: false`.
- **Adjustments**: Manual corrections of the elapsed time, recorded as their own events with a signed `seconds` value and a timestamp. They never modify intervals, so a running timer is unaffected. Entered as `+7m`, `-30s`, `1h 15m`, `0:45` or a bare number of minutes.
- **Elapsed time** = sum of all interval durations in the current (non-finished) section + sum of its adjustments + (now - last_start) if running, clamped at 0.

## Open Questions (to discuss before implementation)
- UI toolkit: tkinter vs GTK vs Qt?
- Should the app run as a background daemon with a toggle shortcut (like dictation_tool)?
- Tray icon?
- Should there be a global hotkey to open/toggle the window?
- Export/reporting features?
- Maximum number of trackers?
- Sound or notification on any event?
