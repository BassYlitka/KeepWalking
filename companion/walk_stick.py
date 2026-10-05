"""Drive a virtual Xbox left stick at walk magnitude while Walk Toggle is on.

Requires:
  - Nefarius ViGEmBus (https://github.com/nefarius/ViGEmBus/releases)
  - pip package: vgamepad  (python -m pip install vgamepad)

The Bingus mod writes:
  %LOCALAPPDATA%\\CowboyBingus\\Helldivers2\\WalkToggle.state
with lines like: walk=1

While walk=1, WASD is mapped to the left stick at MAG (default 0.40).
While walk=0, the stick is centered.
"""

from __future__ import annotations

import ctypes
import os
import time
from pathlib import Path

try:
    import vgamepad as vg
except ImportError as exc:
    raise SystemExit(
        "vgamepad is missing. Run: python -m pip install vgamepad\n"
        "Also install Nefarius ViGEmBus from GitHub releases."
    ) from exc

MAG = float(os.environ.get("WALK_STICK_MAG", "0.40"))
POLL_HZ = 120.0
STATE_PATH = Path(os.environ.get(
    "WALK_TOGGLE_STATE",
    str(Path(os.environ["LOCALAPPDATA"]) / "CowboyBingus" / "Helldivers2" / "WalkToggle.state"),
))

VK = {"forward": 0x57, "back": 0x53, "left": 0x41, "right": 0x44}
user32 = ctypes.WinDLL("user32", use_last_error=True)


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def read_walk_enabled() -> bool:
    try:
        text = STATE_PATH.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("walk="):
            return line.split("=", 1)[1].strip() in ("1", "true", "on", "yes")
    return False


def stick_from_keys() -> tuple[float, float]:
    x = (1.0 if key_down(VK["right"]) else 0.0) - (1.0 if key_down(VK["left"]) else 0.0)
    y = (1.0 if key_down(VK["forward"]) else 0.0) - (1.0 if key_down(VK["back"]) else 0.0)
    if x == 0.0 and y == 0.0:
        return 0.0, 0.0
    # Normalize diagonals, then scale into the walk band.
    length = (x * x + y * y) ** 0.5
    x, y = x / length, y / length
    return x * MAG, y * MAG


def main() -> None:
    print(f"Walk Stick companion")
    print(f"  state: {STATE_PATH}")
    print(f"  mag:   {MAG}")
    print("Waiting for Walk Toggle (Bingus mod)...")
    gamepad = vg.VX360Gamepad()
    last_walk = None
    last_xy = (None, None)
    interval = 1.0 / POLL_HZ
    try:
        while True:
            walk = read_walk_enabled()
            if walk != last_walk:
                print("Walk ON" if walk else "Walk OFF")
                last_walk = walk
            if walk:
                x, y = stick_from_keys()
            else:
                x, y = 0.0, 0.0
            if (x, y) != last_xy:
                gamepad.left_joystick_float(x_value_float=x, y_value_float=y)
                gamepad.update()
                last_xy = (x, y)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        gamepad.reset()
        gamepad.update()


if __name__ == "__main__":
    main()
