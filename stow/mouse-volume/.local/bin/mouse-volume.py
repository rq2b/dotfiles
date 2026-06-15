#!/usr/bin/env python3

from evdev import InputDevice, ecodes
import asyncio
import subprocess
import time

KEYBOARD = "/dev/input/event4"
MOUSE = "/dev/input/event5"

OSDCLIENT = "/usr/bin/swayosd-client"

left_held = False
right_held = False
last_action = 0.0


def volume_up():
    subprocess.Popen(
        [
            "/usr/bin/swayosd-client",
            "--output-volume",
            "raise",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def volume_down():
    subprocess.Popen(
        [
            "/usr/bin/swayosd-client",
            "--output-volume",
            "lower",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

async def keyboard_loop():
    global left_held
    global right_held

    keyboard = InputDevice(KEYBOARD)

    async for event in keyboard.async_read_loop():
        if event.type != ecodes.EV_KEY:
            continue

        # Ignore autorepeat events.
        if event.value == 2:
            continue

        if event.code == ecodes.KEY_LEFTBRACE:
            if event.value == 1:
                left_held = True
                print("[ held")
            elif event.value == 0:
                left_held = False
                print("[ released")

        elif event.code == ecodes.KEY_RIGHTBRACE:
            if event.value == 1:
                right_held = True
                print("] held")
            elif event.value == 0:
                right_held = False
                print("] released")


async def mouse_loop():
    global last_action

    mouse = InputDevice(MOUSE)

    async for event in mouse.async_read_loop():
        if event.type != ecodes.EV_REL:
            continue

        if event.code != ecodes.REL_WHEEL:
            continue

        now = time.monotonic()

        # Prevent absurd process spam from very fast wheel movement.
        if now - last_action < 0.03:
            continue

        last_action = now

        if left_held or right_held:
            print(f"volume {event.value}")

            if event.value > 0:
                volume_up()
            elif event.value < 0:
                volume_down()

async def main():
    print(f"keyboard: {KEYBOARD}")
    print(f"mouse:    {MOUSE}")

    await asyncio.gather(
        keyboard_loop(),
        mouse_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
