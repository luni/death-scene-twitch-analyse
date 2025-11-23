# Live Deathcount / Death Scene Twitch Analyse

This project watches a live Twitch stream, looks for a specific "death scene" frame using OpenCV template matching, and pushes alerts through a minimal Twitch chat bot. When the template is detected, frames are saved to disk and the internal death counter is incremented. The long‑term goal is to automate death counters for streamers who play punishing games.

## Features

- Connects to any public Twitch channel via [streamlink](https://streamlink.github.io/) and converts it to a raw video stream URL.
- Performs grayscale template matching with OpenCV against one or more reference images.
- Maintains a cooldown to reduce duplicate detections and persists matching frames as PNG files for later review.
- Ships with an asynchronous Twitch chat bot (powered by [twitchio](https://twitchio.dev/)) that can be extended to announce detections.

## Requirements

- Python 3.11+ (the `uv` tool auto‑creates a virtual environment pinned to this version).
- [uv](https://docs.astral.sh/uv/) for dependency management (recommended) or any other PEP 621 compatible workflow.
- A Twitch OAuth token, Client ID, and bot nickname with chat access permissions.
- Reference template image(s) placed in the repository (see `kritischer_fehler.png`).

## Getting started

1. **Install dependencies** (this will create/refresh `.venv` automatically):
   ```bash
   uv sync
   ```
2. **Configure secrets** by copying `config.json` and filling in the placeholders:
   ```json
   {
       "bot": {
           "token": "oauth:REPLACE_ME",
           "client_id": "YOUR_CLIENT_ID",
           "nick": "your_bot_username"
       },
       "channels": ["channel_to_monitor"]
   }
   ```
3. **Run the analyser**:
   ```bash
   uv run python analyse.py
   ```

The script loads the first channel from `config.json`, starts the Twitch bot, and launches the OpenCV worker in an executor thread. Matching frames are written as `<death_count>_<template_name>_<frame_number>.png` in the project root.

## Customising detection

- Add or replace template files in the `templates` dictionary inside `analyse.py` and adjust `thresholds` accordingly.
- Tune `quality` in `opencv_task` (e.g., `"720p60"`) when better fidelity is required.
- Experiment with `frame_skip`, `cooldown_frames`, and other counters to balance accuracy vs. CPU usage.

## Development workflow

Common quality checks are already wired via `pyproject.toml`:

```bash
uv run python -m py_compile analyse.py   # syntax errors
uv run ruff check analyse.py            # linting (UP, ANN, etc.)
```

Feel free to add pytest suites under `tests/` and extend `pyproject.toml` tooling as the project grows.

## License

This repository is licensed under the terms of the MIT License. See [LICENSE](./LICENSE) for details.
