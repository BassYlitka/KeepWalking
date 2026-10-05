"""Walk stick for the Bingus Walk Toggle mod.

The in-game MODS binding writes WalkToggle.state. This process reads it,
holds the virtual left stick at the walk magnitude, and hides WASD from the
game while walk mode is on.
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path

import vgamepad as vg

MAG = float(os.environ.get("WALK_STICK_MAG", "0.85"))
STATE_PATH = Path(os.environ["LOCALAPPDATA"]) / "CowboyBingus" / "Helldivers2" / "WalkToggle.state"
PID_PATH = STATE_PATH.with_name("WalkToggle.companion.pid")
WASD = {0x57: "forward", 0x41: "left", 0x53: "back", 0x44: "right"}

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INJECT_TAG = 0x57A17001
# Set-1 scan codes so the game sees a real key-up when walk mode takes over.
SCAN = {0x57: 0x11, 0x41: 0x1E, 0x53: 0x1F, 0x44: 0x20}

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = wintypes.SHORT
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.Process32NextW.restype = wintypes.BOOL

walk_on = False
hook_handle = None
hook_proc_ref = None
pad: vg.VX360Gamepad | None = None
inject_info = ctypes.c_size_t(INJECT_TAG)


def already_running() -> bool:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def read_walk() -> tuple[bool, float]:
    try:
        text = STATE_PATH.read_text(encoding="utf-8")
    except OSError:
        return False, MAG
    enabled = False
    mag = MAG
    for line in text.splitlines():
        if line.startswith("walk="):
            enabled = line.split("=", 1)[1].strip() in ("1", "true", "on")
        elif line.startswith("mag="):
            try:
                mag = float(line.split("=", 1)[1])
            except ValueError:
                mag = MAG
    return enabled, mag


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def game_running() -> bool:
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return True
    try:
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return False
        while True:
            if entry.szExeFile.lower() == "helldivers2.exe":
                return True
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                return False
    finally:
        kernel32.CloseHandle(snapshot)


def game_focused() -> bool:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False
    process = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
    if not process:
        return False
    try:
        size = wintypes.DWORD(512)
        buf = ctypes.create_unicode_buffer(512)
        if not kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
            return False
        return buf.value.lower().endswith("helldivers2.exe")
    finally:
        kernel32.CloseHandle(process)


def stick_from_wasd(mag: float) -> tuple[float, float]:
    x = (1.0 if key_down(0x44) else 0.0) - (1.0 if key_down(0x41) else 0.0)
    y = (1.0 if key_down(0x57) else 0.0) - (1.0 if key_down(0x53) else 0.0)
    length = (x * x + y * y) ** 0.5
    if length == 0.0:
        return 0.0, 0.0
    scale = mag / length
    return x * scale, y * scale


def send_key(vk: int, up: bool) -> None:
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    event = INPUT(type=1, ki=KEYBDINPUT(0, SCAN[vk], flags, 0, inject_info.value))
    user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))


def release_wasd_to_game() -> None:
    """Drop keys the game already saw, so a held W does not keep the full run."""
    for vk in WASD:
        if key_down(vk):
            send_key(vk, up=True)
            time.sleep(0.01)


def apply_stick(x: float, y: float) -> None:
    if pad is None:
        return
    pad.left_joystick_float(x_value_float=x, y_value_float=y)
    pad.update()


def set_walk(enabled: bool, mag: float) -> None:
    global walk_on
    if enabled == walk_on:
        return
    if enabled:
        release_wasd_to_game()
        walk_on = True
        print(f"Walk ON  (stick {mag:.2f})", flush=True)
    else:
        walk_on = False
        apply_stick(0.0, 0.0)
        print("Walk OFF", flush=True)


def hook_proc(code, wparam, lparam):
    if code >= 0 and walk_on and game_focused():
        info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if info.dwExtraInfo != INJECT_TAG and info.vkCode in WASD and wparam in (
            WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP,
        ):
            return 1
    return user32.CallNextHookEx(hook_handle, code, wparam, lparam)


def main() -> None:
    global pad, hook_handle, hook_proc_ref
    if already_running():
        print("Companion already running.")
        return
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    print("Walk companion ready. Toggle Walk on the in-game MODS tab.", flush=True)
    pad = vg.VX360Gamepad()
    hook_proc_ref = HOOKPROC(hook_proc)
    hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_proc_ref, kernel32.GetModuleHandleW(None), 0)
    if not hook_handle:
        raise SystemExit(f"Keyboard hook failed ({ctypes.get_last_error()})")

    last_xy = (0.0, 0.0)
    missing_game = 0.0
    msg = wintypes.MSG()
    try:
        while True:
            if game_running():
                missing_game = 0.0
            else:
                missing_game += 1.0 / 120.0
                if missing_game > 3.0:
                    print("Game closed, releasing virtual pad.", flush=True)
                    break
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            enabled, mag = read_walk()
            set_walk(enabled, mag)
            if walk_on and game_focused():
                xy = stick_from_wasd(mag)
            else:
                xy = (0.0, 0.0)
            if xy != last_xy:
                apply_stick(*xy)
                last_xy = xy
            time.sleep(1.0 / 120.0)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        walk_on = False
        if pad is not None:
            pad.reset()
            pad.update()
        if hook_handle:
            user32.UnhookWindowsHookEx(hook_handle)
        try:
            if PID_PATH.read_text(encoding="utf-8").strip() == str(os.getpid()):
                PID_PATH.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
