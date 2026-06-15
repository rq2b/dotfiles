from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

from evdev import InputDevice, ecodes as e, ff, list_devices

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ffb")

WHEEL_DEVICE_PATH = "/dev/input/event16"
WHEEL_NAME_FRAGMENT = "Guillemot Force Feedback Racing Wheel"

FF_GAIN = 0x55F0  # [0x0000–0xFFFF] master strength (0–100%), scales ALL effects [0-65535]

FF_REFRESH_INTERVAL_S = (
    5.0  # >0 seconds, how often effect is retriggered (keep < replay time)
)

FF_REPLAY_MS = (
    20000  # [0–65535 ms] duration before effect expires (~16–20s typical safe)
)

SPRING_LEFT_COEFF = (
    0x6000  # [-0x8000–0x7FFF] force toward center (left side), stiffness
)
SPRING_RIGHT_COEFF = (
    0x6000  # [-0x8000–0x7FFF] force toward center (right side), stiffness
)

SPRING_LEFT_SATURATION = 0x7FFF  # [0–0x7FFF] max force when fully turned left

SPRING_RIGHT_SATURATION = 0x7FFF  # [0–0x7FFF] max force when fully turned right

SPRING_DEADBAND = 100  # [0–65535] zone around center with NO force (reduces jitter)

SPRING_CENTER = 0  # [-0x8000–0x7FFF] offset of center point (0 = physical center)

SPRING_DIRECTION = 0  # [0–0xFFFF] direction of force vector (0 = aligned axis, keep 0)


def shutdown(signum: int, frame: object | None) -> None:
    raise SystemExit(0)


def find_device_path(name_fragment: str) -> str:
    needle = name_fragment.lower()
    for path in list_devices():
        device = InputDevice(path)
        try:
            if needle in device.name.lower():
                return path
        finally:
            device.close()
    raise RuntimeError(f'Could not find input device containing "{name_fragment}"')


def resolve_wheel_path() -> str:
    if Path(WHEEL_DEVICE_PATH).exists():
        return WHEEL_DEVICE_PATH
    return find_device_path(WHEEL_NAME_FRAGMENT)


def build_condition(
    left_coeff: int, right_coeff: int, left_saturation: int, right_saturation: int
) -> ff.Condition:
    return ff.Condition(
        right_saturation=right_saturation,
        left_saturation=left_saturation,
        right_coeff=right_coeff,
        left_coeff=left_coeff,
        deadband=SPRING_DEADBAND,
        center=SPRING_CENTER,
    )


def build_spring_effect() -> ff.Effect:
    effect = ff.Effect(
        e.FF_SPRING,
        -1,
        SPRING_DIRECTION,
        ff.Trigger(0, 0),
        ff.Replay(FF_REPLAY_MS, 0),
        ff.EffectType(),
    )

    effect.u.ff_condition_effect[0] = build_condition(
        left_coeff=SPRING_LEFT_COEFF,
        right_coeff=SPRING_RIGHT_COEFF,
        left_saturation=SPRING_LEFT_SATURATION,
        right_saturation=SPRING_RIGHT_SATURATION,
    )
    effect.u.ff_condition_effect[1] = build_condition(
        left_coeff=SPRING_LEFT_COEFF,
        right_coeff=SPRING_RIGHT_COEFF,
        left_saturation=SPRING_LEFT_SATURATION,
        right_saturation=SPRING_RIGHT_SATURATION,
    )
    return effect


def play_effect(dev: InputDevice, effect_id: int) -> None:
    dev.write(e.EV_FF, effect_id, 1)


def stop_effect(dev: InputDevice, effect_id: int) -> None:
    try:
        dev.write(e.EV_FF, effect_id, 0)
    except OSError:
        pass


def main() -> None:
    wheel_path = resolve_wheel_path()
    dev = InputDevice(wheel_path)
    effect_id = -1

    try:
        log.info(f"[WHEEL] {dev.name} @ {wheel_path}")

        dev.write(e.EV_FF, e.FF_GAIN, FF_GAIN)

        effect_id = dev.upload_effect(build_spring_effect())
        log.info(f"[FFB] spring effect id={effect_id}")

        play_effect(dev, effect_id)
        log.info("[FFB] spring active")

        while True:
            time.sleep(FF_REFRESH_INTERVAL_S)
            play_effect(dev, effect_id)
            log.info("[FFB] refreshed")

    finally:
        if effect_id >= 0:
            stop_effect(dev, effect_id)
        dev.close()
        log.info("[FFB] stopped")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        main()
    except SystemExit:
        pass
