"""Fine capture around the walk band the user already felt (~0.70).

Stand on foot in an open area. Focus the game. Do not touch WASD.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import vgamepad as vg

PHASE_PATH = Path(os.environ["LOCALAPPDATA"]) / "CowboyBingus" / "Helldivers2" / "WalkToggle.phase"
STEPS = (
    ("wake", 0.20, 2.0),
    ("walk", 0.70, 6.0),
    ("walk", 0.75, 6.0),
    ("walk", 0.80, 6.0),
    ("walk", 0.85, 6.0),
    ("run", 1.00, 4.0),
    ("idle", 0.0, 1.5),
    ("done", 0.0, 0.3),
)


def write_phase(name: str, mag: float) -> None:
    PHASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = f"phase={name}\nmag={mag:.2f}\n"
    tmp = PHASE_PATH.with_suffix(".phase.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(PHASE_PATH)


def hold_stick(pad: vg.VX360Gamepad, mag: float, seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pad.left_joystick_float(x_value_float=0.0, y_value_float=mag)
        pad.update()
        time.sleep(1.0 / 120.0)


def wake_controller(pad: vg.VX360Gamepad) -> None:
    print("Waking virtual pad...")
    write_phase("wake", 0.0)
    pad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    pad.update()
    time.sleep(0.05)
    pad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    pad.update()
    hold_stick(pad, 0.20, 1.5)
    hold_stick(pad, 0.0, 0.4)


def main() -> None:
    print("Walk fine capture: 0.70 / 0.75 / 0.80 / 0.85 / 1.00")
    print("Watch the gait yourself — say which mag still walks and which starts jogging.")
    print("Starting in 6 seconds...")
    for left in range(6, 0, -1):
        print(f"  {left}")
        time.sleep(1)

    pad = vg.VX360Gamepad()
    try:
        wake_controller(pad)
        for name, mag, seconds in STEPS:
            if name == "wake":
                continue
            print(f">>> phase={name} mag={mag:.2f} ({seconds:.0f}s)")
            write_phase(name, mag)
            hold_stick(pad, mag, seconds)
        print("done")
    finally:
        pad.reset()
        pad.update()
        write_phase("done", 0.0)


if __name__ == "__main__":
    main()
