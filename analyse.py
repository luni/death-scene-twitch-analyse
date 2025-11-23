#!/usr/bin/python3
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import streamlink
from twitchio.ext import commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TEMPLATE_FILES = {"death_scene_1": Path("kritischer_fehler.png")}
TEMPLATE_THRESHOLDS = {"death_scene_1": 0.65}
TEMPLATE_SIZE = (640, 360)
FRAME_LOG_INTERVAL = 1_000
DETECTION_OUTPUT_DIR = Path("detections")
DETECTION_OUTPUT_DIR.mkdir(exist_ok=True)


def load_config(path: Path = Path("config.json")) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open() as config_file:
        config: dict[str, Any] = json.load(config_file)

    bot_cfg = config.get("bot")
    if not isinstance(bot_cfg, dict):
        raise ValueError("Config must contain a 'bot' section.")

    required_bot_keys = ["token", "client_id", "client_secret", "bot_id", "nick"]
    missing = [key for key in required_bot_keys if not bot_cfg.get(key)]
    if missing:
        raise ValueError(f"Missing bot config values: {', '.join(missing)}")

    channels = config.get("channels")
    if not channels:
        raise ValueError("Config must include at least one channel entry in 'channels'.")

    return config


def load_templates(template_files: dict[str, Path], size: tuple[int, int]) -> dict[str, Any]:
    templates: dict[str, Any] = {}
    for name, file_path in template_files.items():
        if not file_path.exists():
            raise FileNotFoundError(f"Template '{name}' not found at {file_path}")

        template = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            raise ValueError(f"Unable to read template '{name}' from {file_path}")

        templates[name] = cv2.resize(template, size)

    return templates


def stream_to_url(url: str, quality: str = "best") -> str:
    streams = streamlink.streams(url)
    if not streams:
        raise ValueError(f"No streams available for {url}")

    if quality not in streams:
        available = ", ".join(streams.keys())
        raise ValueError(
            f"Quality '{quality}' not available for {url}. Available qualities: {available}"
        )

    return streams[quality].to_url()


class Bot(commands.Bot):
    def __init__(self, message_queue: asyncio.Queue[str], config: dict[str, Any]) -> None:
        bot_cfg = config["bot"]
        super().__init__(
            token=bot_cfg["token"],
            client_id=bot_cfg["client_id"],
            client_secret=bot_cfg["client_secret"],
            bot_id=bot_cfg["bot_id"],
            owner_id=bot_cfg.get("owner_id"),
            nick=bot_cfg["nick"],
            prefix=bot_cfg.get("prefix", "!"),
            initial_channels=config["channels"],
        )
        self.message_queue = message_queue

    async def event_ready(self) -> None:
        logging.info(f"Logged in as | {self.nick}")
        logging.info(f"User id is | {self.user_id}")

    async def send_from_queue(self) -> None:
        while True:
            try:
                # Attempt to get a message without blocking
                message = self.message_queue.get_nowait()
                # Send the message to all connected channels
                for channel in self.connected_channels:
                    await channel.send(message)
                await asyncio.sleep(10)
            except asyncio.QueueEmpty:
                # No messages in the queue, continue
                pass
            # Wait briefly before checking again
            await asyncio.sleep(0.1)


def opencv_task(
    message_queue: asyncio.Queue[str],
    url: str,
    templates: dict[str, Any],
    thresholds: dict[str, float],
    quality: str = "360p30",
) -> None:
    logger.info("Connecting to %s", url)
    stream_url = stream_to_url(url, quality)
    video_stream = cv2.VideoCapture(stream_url)

    death_counter = 0
    frame_skip = 0
    cooldown_frames = 30 * 30  # Skip the next 30 seconds after a detection
    cooldown = -1
    still_screen_present = False
    skip_start = 0
    frame_count = 0
    since_log = 0

    while True:
        ret, frame = video_stream.read()
        if not ret:
            logger.error("Stream ended or no frames received.")
            time.sleep(5)
            try:
                stream_url = stream_to_url(url, quality)
                video_stream = cv2.VideoCapture(stream_url)
            except Exception as exc:  # pragma: no cover - best effort reconnect
                logger.error("Failed to reconnect to %s: %s", url, exc)
            continue

        frame_count += 1
        if cooldown > 0 and not still_screen_present:
            cooldown -= 1

        since_log += 1
        if (frame_skip > 0 and frame_count % frame_skip != 0) or frame_count <= skip_start:
            continue

        if since_log >= FRAME_LOG_INTERVAL:
            logger.info("Processing frame %s", frame_count)
            since_log = 0

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for name, template in templates.items():
            result = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            threshold = thresholds.get(name, 0.8)
            if max_val < threshold:
                still_screen_present = False
                continue

            logger.info("Detected %s (match=%.3f, threshold=%.2f)", name, max_val, threshold)
            if cooldown > 0:
                continue

            cooldown = cooldown_frames
            death_counter += 1
            logger.info("Death Counter: %s", death_counter)

            detection_file = DETECTION_OUTPUT_DIR / f"{death_counter}_{name}_{frame_count}.png"
            cv2.imwrite(str(detection_file), frame)
            still_screen_present = True

            if not message_queue.empty():
                # Allow future enhancements that enqueue chat messages without blocking
                break


async def main() -> None:
    config = load_config()
    templates = load_templates(TEMPLATE_FILES, TEMPLATE_SIZE)

    message_queue: asyncio.Queue[str] = asyncio.Queue()
    bot = Bot(message_queue=message_queue, config=config)
    asyncio.create_task(bot.send_from_queue())

    loop = asyncio.get_running_loop()
    channel_url = f"https://www.twitch.tv/{config['channels'][0]}"
    loop.run_in_executor(
        None,
        opencv_task,
        message_queue,
        channel_url,
        templates,
        TEMPLATE_THRESHOLDS,
    )

    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
