#!/usr/bin/python3
import cv2
import streamlink
import asyncio
from twitchio.ext import commands
import logging
import json
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class Bot(commands.Bot):
    def __init__(self, message_queue: asyncio.Queue, config: dict):
        super().__init__(
            token=config["bot"]["token"],  # Replace with your OAuth token
            client_id=config["bot"]["client_id"],      # Replace with your Client ID
            nick=config["bot"]["nick"],     # Replace with your Twitch username
            prefix='!',                      # Command prefix (optional)
            initial_channels=config["channels"]  # Replace with the channel you want to join
        )
        self.message_queue = message_queue

    async def event_ready(self):
        logging.info(f"Logged in as | {self.nick}")
        logging.info(f"User id is | {self.user_id}")

    async def send_from_queue(self):
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


# Load all template images
templates = {
    #"death_scene_1": cv2.resize(cv2.imread("death1.png", cv2.IMREAD_GRAYSCALE), (640, 360)),
    "death_scene_1": cv2.resize(cv2.imread("kritischer_fehler.png", cv2.IMREAD_GRAYSCALE), (640, 360)),
    # "death_scene_2": cv2.imread("death_scene_2.jpg", cv2.IMREAD_GRAYSCALE),
    # "death_scene_3": cv2.imread("death_scene_3.jpg", cv2.IMREAD_GRAYSCALE),
}

# Define thresholds for each template (if needed, otherwise use a default)
thresholds = {
    "death_scene_1": 0.65,
    # "death_scene_2": 0.75,
    # "death_scene_3": 0.85,
}


def stream_to_url(url, quality='best'):
    streams = streamlink.streams(url)
    if streams:
        return streams[quality].to_url()

    raise ValueError("No steams were available")


def opencv_task(message_queue, url, quality='360p30'):
    logging.info(f"Connecting to {url}")
    stream_url = stream_to_url(url, quality)
    # Open the video stream
    video_stream = cv2.VideoCapture(stream_url)  # Replace with your live stream or video file
    # foo
    # video_stream = cv2.VideoCapture('Gammel of War ｜ !socials !spotify !podcast !merch 2024-12-30 15_28 [v2339748646].mp4')  # Replace with your live stream or video file

    # Death counter
    death_counter = 0
    frame_skip = 0
    cooldown_frames = 30 * 30  # Skip the next 30 seconds after a detection
    cooldown = -1
    still_screen_present = False
    skip_start = 0
    frame_count = 0
    z = 0
    while True:
        ret, frame = video_stream.read()
        if not ret:
            logging.error("Stream ended or no frames received.")
            time.sleep(5)
            try:
                stream_url = stream_to_url(url, quality)
                # Open the video stream
                video_stream = cv2.VideoCapture(stream_url)  # Replace with your live stream or video file
            except Exception as e:
                logging.error(e)

            continue

        frame_count += 1
        if cooldown > 0 and not still_screen_present:
            cooldown -= 1

        z += 1
        if (frame_skip > 0 and frame_count % frame_skip != 0) or frame_count <= skip_start:
            continue

        if z >= 1000:
            logging.info("frame %s", frame_count)
            z = 0

        # Convert the frame to grayscale
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Loop through all templates
        for name, template in templates.items():
            # template_width, template_height = template.shape[::-1]

            # Perform template matching
            result = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Check if the best match exceeds the threshold
            if max_val >= thresholds.get(name, 0.8):  # Default threshold 0.8 if not specified
                logging.info(f"Detected: {name} with match value {max_val}")
                if cooldown > 0:
                    continue

                cooldown = cooldown_frames  # Reset cooldown

                # message_queue.put_nowait(f"Detected: {name} with match value {max_val}")
                # Increment death counter
                death_counter += 1
                logging.info(f"Death Counter: {death_counter}")
                # message_queue.put_nowait("!rip")
                cv2.imwrite("%d_%s_%s.png" % (death_counter, name, frame_count), frame)  # Save the frame", frame)
                still_screen_present = True
            else:
                still_screen_present = False

    video_stream.release()


async def main():
    with open("config.json", "r") as f:
        config = json.load(f)

    loop = asyncio.get_event_loop()
    message_queue = asyncio.Queue()

    # Run the Twitch bot
    bot = Bot(message_queue=message_queue, config=config)
    asyncio.create_task(bot.send_from_queue())

    # Run OpenCV in a separate thread with arguments
    loop.run_in_executor(None, opencv_task, message_queue, "https://www.twitch.tv/" + config["channels"][0])

    # Start the bot
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
