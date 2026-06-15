from __future__ import annotations

import logging
import select
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast, Dict, Sequence

from evdev import InputDevice, UInput, ecodes as e, AbsInfo, list_devices, ff

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fh4")

WHEEL_DEVICE_PATH = "/dev/input/event16"
WHEEL_NAME_FRAGMENT = "Guillemot Force Feedback Racing Wheel"
PEDAL_DEVICE_PATH: Optional[str] = None
PEDAL_NAME_FRAGMENT = "FANATEC CSL Elite Pedals LC"
DEBUG = True

FF_ENABLE = True
FF_GAIN = 0x55F0
FF_REFRESH_INTERVAL_S = 5.0
FF_REPLAY_MS = 20000

SPRING_LEFT_COEFF = 0x6000
SPRING_RIGHT_COEFF = 0x6000
SPRING_LEFT_SATURATION = 0x7FFF
SPRING_RIGHT_SATURATION = 0x7FFF
SPRING_DEADBAND = 100
SPRING_CENTER = 0
SPRING_DIRECTION = 0


def clamp(value: int, lo: int, hi: int) -> int:
    return lo if value < lo else hi if value > hi else value


def scale(value: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    return int((value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


def deadzone(value: int, dz: int) -> int:
    return 0 if abs(value) < dz else value


def compensate_and_compress(
    value: int, full: int = 32767, expo: float = 0.55, blend: float = 0.3
) -> int:
    if value == 0:
        return 0

    sign = 1 if value > 0 else -1
    magnitude = abs(value) / full
    curved = magnitude**expo
    mixed = (1.0 - blend) * curved + blend * magnitude

    active_min = 10240
    active_max = 27000
    remapped = active_min + mixed * (active_max - active_min)
    return int(sign * remapped)


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


def resolve_device_path(preferred_path: str, name_fragment: str) -> str:
    if Path(preferred_path).exists():
        return preferred_path
    return find_device_path(name_fragment)


@dataclass(frozen=True)
class SteeringConfig:
    raw_min: int = -1920
    raw_max: int = 1920
    deadzone_raw: int = 40
    output_min: int = -27000
    output_max: int = 27000
    expo: float = 0.55
    blend: float = 0.3


@dataclass(frozen=True)
class PedalBinding:
    target_axis: int
    raw_min: int = 0
    raw_max: int = 4000
    expo: float = 1.0
    invert: bool = False


STEERING = SteeringConfig()
PEDAL_BINDINGS: dict[int, PedalBinding] = {
    e.ABS_Z: PedalBinding(target_axis=e.ABS_RZ, raw_max=4095),  # brake (NEW)
    e.ABS_X: PedalBinding(target_axis=e.ABS_Z, raw_max=4095),   # gas
}


class VirtualController:
    def __init__(self) -> None:
        events = cast(
            Dict[int, Sequence[int]],
            {
                e.EV_ABS: [
                    (e.ABS_X, AbsInfo(0, -32768, 32767, 0, 0, 0)),
                    (e.ABS_Y, AbsInfo(0, -32768, 32767, 0, 0, 0)),
                    (e.ABS_RX, AbsInfo(0, -32768, 32767, 0, 0, 0)),
                    (e.ABS_RY, AbsInfo(0, -32768, 32767, 0, 0, 0)),
                    (e.ABS_Z, AbsInfo(0, 0, 65535, 0, 0, 0)),
                    (e.ABS_RZ, AbsInfo(0, 0, 65535, 0, 0, 0)),
                ],
                e.EV_KEY: [
                    e.BTN_SOUTH,
                    e.BTN_EAST,
                    e.BTN_NORTH,
                    e.BTN_WEST,
                    e.BTN_TL,
                    e.BTN_TR,
                    e.BTN_GAMEPAD,
                    e.BTN_START,
                    e.BTN_SELECT,
                ],
            },
        )

        self.ui = UInput(events, name="fh4-axis")

    def abs(self, code: int, value: int) -> None:
        self.ui.write(e.EV_ABS, code, value)

    def key(self, code: int, value: int) -> None:
        self.ui.write(e.EV_KEY, code, value)

    def stabilize(self) -> None:
        self.abs(e.ABS_X, 0)
        self.abs(e.ABS_Y, 0)
        self.abs(e.ABS_RY, 0)

    def sync(self) -> None:
        self.ui.syn()

    def close(self) -> None:
        self.ui.close()


class ForceFeedbackController:
    def __init__(self, device: InputDevice) -> None:
        self.device = device
        self.effect_id = -1
        self.next_refresh = 0.0
        self.enabled = False

    def _build_condition(self) -> ff.Condition:
        return ff.Condition(
            right_saturation=SPRING_RIGHT_SATURATION,
            left_saturation=SPRING_LEFT_SATURATION,
            right_coeff=SPRING_RIGHT_COEFF,
            left_coeff=SPRING_LEFT_COEFF,
            deadband=SPRING_DEADBAND,
            center=SPRING_CENTER,
        )

    def _build_spring_effect(self) -> ff.Effect:
        effect = ff.Effect(
            e.FF_SPRING,
            -1,
            SPRING_DIRECTION,
            ff.Trigger(0, 0),
            ff.Replay(FF_REPLAY_MS, 0),
            ff.EffectType(),
        )

        effect.u.ff_condition_effect[0] = self._build_condition()
        effect.u.ff_condition_effect[1] = self._build_condition()
        return effect

    def start(self) -> None:
        if not FF_ENABLE:
            return

        self.device.write(e.EV_FF, e.FF_GAIN, FF_GAIN)
        self.effect_id = self.device.upload_effect(self._build_spring_effect())
        log.info(f"[FFB] spring effect id={self.effect_id}")

        self.play()
        self.enabled = True
        self.next_refresh = time.monotonic() + FF_REFRESH_INTERVAL_S
        log.info("[FFB] spring active")

    def play(self) -> None:
        if self.effect_id >= 0:
            self.device.write(e.EV_FF, self.effect_id, 1)

    def refresh_if_due(self) -> None:
        if not self.enabled or self.effect_id < 0:
            return

        now = time.monotonic()
        if now >= self.next_refresh:
            self.play()
            self.next_refresh = now + FF_REFRESH_INTERVAL_S
            log.info("[FFB] refreshed")

    def stop(self) -> None:
        if self.effect_id >= 0:
            try:
                self.device.write(e.EV_FF, self.effect_id, 0)
            except OSError:
                pass

    def close(self) -> None:
        self.stop()


def pedal_deadzone(val: int, dz: int, max_val: int = 65535) -> int:
    if val <= dz:
        return 0
    return int((val - dz) * max_val / (max_val - dz))


def map_steering(raw_value: int, cfg: SteeringConfig = STEERING) -> int:
    raw = clamp(raw_value, cfg.raw_min, cfg.raw_max)
    raw = deadzone(raw, cfg.deadzone_raw)
    scaled = scale(raw, cfg.raw_min, cfg.raw_max, -32768, 32767)
    processed = compensate_and_compress(scaled, expo=cfg.expo, blend=cfg.blend)
    return clamp(processed, cfg.output_min, cfg.output_max)


def map_pedal(raw_value: int, binding: PedalBinding) -> int:
    value = clamp(raw_value, binding.raw_min, binding.raw_max)
    if binding.invert:
        value = binding.raw_max - (value - binding.raw_min)

    denom = binding.raw_max - binding.raw_min
    if denom <= 0:
        return 0

    norm = (value - binding.raw_min) / denom
    if binding.expo != 1.0:
        norm = norm**binding.expo

    return clamp(int(norm * 65535), 0, 65535)


def handle_wheel_event(event, controller: VirtualController) -> None:
    if event.type == e.EV_ABS and event.code == e.ABS_WHEEL:
        final = map_steering(event.value)
        controller.abs(e.ABS_RX, final)
        if DEBUG:
            log.info(f"[STEER] raw={event.value} final={final}")

    elif event.type == e.EV_KEY:
        if DEBUG:
            log.info(f"[BUTTON] code={event.code} value={event.value}")

        if event.code == e.BTN_BASE:
            controller.key(e.BTN_SOUTH, event.value)
        elif event.code == e.BTN_BASE2:
            controller.key(e.BTN_EAST, event.value)
        elif event.code == e.BTN_BASE4:
            controller.key(e.BTN_WEST, event.value)
        elif event.code == e.BTN_BASE3:
            controller.key(e.BTN_NORTH, event.value)
        elif event.code == e.BTN_GEAR_DOWN:
            controller.key(e.BTN_TL, event.value)
        elif event.code == e.BTN_GEAR_UP:
            controller.key(e.BTN_TR, event.value)


def handle_pedal_event(event, controller: VirtualController) -> None:
    if event.type != e.EV_ABS:
        return

    binding = PEDAL_BINDINGS.get(event.code)
    if binding is None:
        return

    raw = event.value
    val = pedal_deadzone(raw, dz=300)
    final = map_pedal(val, binding)

    controller.abs(binding.target_axis, final)

    if DEBUG:
        log.info(f"[PEDAL] code={event.code} raw={event.value} final={final}")


def shutdown(signum, frame) -> None:
    raise SystemExit(0)


def main() -> None:
    wheel_path = resolve_device_path(WHEEL_DEVICE_PATH, WHEEL_NAME_FRAGMENT)
    pedal_path = PEDAL_DEVICE_PATH or find_device_path(PEDAL_NAME_FRAGMENT)

    wheel_dev = InputDevice(wheel_path)
    pedal_dev = InputDevice(pedal_path)
    controller = VirtualController()
    ffb = ForceFeedbackController(wheel_dev)

    try:
        log.info(f"[WHEEL] {wheel_dev.name} @ {wheel_path}")
        log.info(f"[PEDAL] {pedal_dev.name} @ {pedal_path}")

        ffb.start()

        devices = {
            wheel_dev.fd: ("wheel", wheel_dev),
            pedal_dev.fd: ("pedal", pedal_dev),
        }

        while True:
            timeout = 1.0
            if ffb.enabled and ffb.effect_id >= 0:
                timeout = max(0.0, ffb.next_refresh - time.monotonic())

            ready_fds, _, _ = select.select(list(devices.keys()), [], [], timeout)

            for fd in ready_fds:
                kind, device = devices[fd]
                for event in device.read():
                    if kind == "wheel":
                        handle_wheel_event(event, controller)
                    else:
                        handle_pedal_event(event, controller)

            controller.stabilize()
            controller.sync()
            ffb.refresh_if_due()

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        ffb.close()
        wheel_dev.close()
        pedal_dev.close()
        controller.close()
        log.info("[STOP] clean exit")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        main()
    except SystemExit:
        pass
