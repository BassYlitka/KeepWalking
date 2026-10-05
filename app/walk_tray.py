"""Background walk toggle for Helldivers 2.

Sits in the system tray. The virtual pad exists only while walk mode is on
and the game is running, so the rest of the time nothing extra is plugged in.
"""

from __future__ import annotations

import ctypes
import gc
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

MAG_MIN = 0.70
MAG_MAX = 0.85
MAG_STEP = 0.05
SPEEDS = [round(MAG_MIN + i * MAG_STEP, 2) for i in range(int(round((MAG_MAX - MAG_MIN) / MAG_STEP)) + 1)]
SPEED_SPOTS = (
    "top_left", "top", "top_right", "right",
    "bottom_right", "bottom", "bottom_left", "left",
)
MODES = ("tap", "press", "double", "long_press", "hold", "long_hold")
TAP_MAX = 0.45
LONG_AFTER = 0.40
DOUBLE_WINDOW = 0.40
HOLD_REPEAT = 0.18
ACTIONS = ("walk", "speed_up", "speed_down")
APP_NAME = "Keep Walking"
CONFIG_DIR = Path(os.environ["LOCALAPPDATA"]) / "KeepWalking"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "walk.log"
MOD_PATHS = (
    Path(os.environ["LOCALAPPDATA"]) / "CowboyBingus" / "Helldivers2" / "KeepWalking.mod",
    Path(os.environ["LOCALAPPDATA"]) / "CowboyBingus" / "Helldivers2" / "Logs" / "KeepWalking.mod",
)
MOD_STALE = 2.0
_LEGACY_CONFIG = Path(os.environ["LOCALAPPDATA"]) / "HelldiversWalk" / "config.json"
AUTOSTART_VALUE = "KeepWalking"
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# Known ViGEmBus product code; also discovered from the uninstall registry.
VIGEM_PRODUCT_FALLBACK = "{93D91F60-7C94-4A79-863F-EA713D2EB3F3}"
DEFAULT_VK = 0xA4  # Left Alt

STRINGS = {
    "en": {
        "settings": "Settings",
        "quit": "Quit",
        "language": "Language",
        "lang_en": "English",
        "lang_ru": "Русский",
        "key_label": "Walk key: {name}",
        "speed": "Walking speed",
        "hotkeys": "Hotkeys",
        "mod_control": "Controlled by the mod",
        "bind_walk": "Walk / Run: {name}",
        "bind_up": "Faster: {name}",
        "bind_down": "Slower: {name}",
        "bind_chat": "Open chat: {name}",
        "chat_hint": (
            "While walking, WASD is used for movement, so those letters do not type in chat. "
            "Set this to the key that opens chat in the game: WASD will type, and the character will stop walking.\n\n"
            "Enter is the default."
        ),
        "change_key": "Change key",
        "clear_key": "Clear",
        "unbound": "Not set",
        "key_in_use": "That key is already used.",
        "capture_cancelled": "Key change cancelled.",
        "speed_now": "Speed {mag}",
        "speed_recommended": "{mag} (Recommended)",
        "speed_notice": "Speed notice",
        "speed_notice_on": "Enabled",
        "spot_top_left": "Top left",
        "spot_top": "Top",
        "spot_top_right": "Top right",
        "spot_right": "Right",
        "spot_bottom_right": "Bottom right",
        "spot_bottom": "Bottom",
        "spot_bottom_left": "Bottom left",
        "spot_left": "Left",
        "mode_tap": "Tap",
        "mode_press": "Press",
        "mode_double": "Double Tap",
        "mode_long_press": "Long Press",
        "mode_hold": "Hold",
        "mode_long_hold": "Long Hold",
        "autostart": "Start with Windows",
        "uninstall_driver": "Uninstall completely",
        "install_driver": "Install driver",
        "status_error": "Pad error",
        "status_capture": "Press a new key",
        "status_walk": "Walking {mag}",
        "status_in_game": "In game",
        "status_waiting": "Waiting for Helldivers 2",
        "walk_on": "Walk ON",
        "walk_off": "Walk OFF",
        "start_game_first": "Start Helldivers 2 first.",
        "pad_failed": "Virtual pad failed. Install ViGEmBus, then restart this app.",
        "key_saved": "Assigned: {name}",
        "wasd_busy": "WASD is already movement. Press another key.",
        "autostart_fail": "Could not change autostart.",
        "driver_missing_installer": "Driver not found, and the installer is not bundled.",
        "driver_not_installed": "Driver not installed. Walking will not work until it is.",
        "driver_cancelled": "Driver was not installed.",
        "driver_installed": "Driver installed.",
        "driver_pad_fail": "Driver installed, but the pad failed. Restart Keep Walking.",
        "ask_install_title": APP_NAME,
        "ask_install": (
            "Walking needs the ViGEmBus virtual gamepad driver (Nefarius).\n\n"
            "It installs once and stays in Windows until you remove it yourself. "
            "Keep Walking will not put it back right after you uninstall it.\n\n"
            "If you agree, the installer opens and Windows asks for administrator rights.\n\n"
            "Install the driver now?"
        ),
        "ask_uninstall_title": APP_NAME + " — Uninstall",
        "ask_uninstall": (
            "Fully uninstall Keep Walking from this PC?\n\n"
            "This removes:\n"
            "• ViGEmBus virtual gamepad driver\n"
            "• Autostart\n"
            "• Keep Walking settings\n"
            "• Keep Walking itself\n\n"
            "A full removal does mean rebooting the PC. "
            "I think you can handle that yourself (´｡• ᵕ •｡`)"
        ),
        "driver_not_found": "Driver not found on this PC. The app and settings will still be removed.",
        "uninstall_done": (
            "Keep Walking has been fully uninstalled.\n\n"
            "The program will close and delete itself.\n"
            "For a complete driver cleanup, reboot your PC when convenient.\n"
            "Windows will not force a restart."
        ),
        "uninstall_failed": "Driver uninstall was cancelled or failed. The driver may still be installed.",
    },
    "ru": {
        "settings": "Настройки",
        "quit": "Выход",
        "language": "Язык",
        "lang_en": "English",
        "lang_ru": "Русский",
        "key_label": "Клавиша: {name}",
        "speed": "Скорость ходьбы",
        "hotkeys": "Горячие клавиши",
        "mod_control": "Управляется модом",
        "bind_walk": "Ходьба / бег: {name}",
        "bind_up": "Быстрее: {name}",
        "bind_down": "Медленнее: {name}",
        "bind_chat": "Открыть чат: {name}",
        "chat_hint": (
            "Во время ходьбы WASD заняты движением, поэтому в чате эти буквы не пишутся. "
            "Поставь сюда клавишу, которой в игре открывается чат: тогда WASD печатаются, а персонаж останавливается.\n\n"
            "По умолчанию стоит Enter."
        ),
        "change_key": "Сменить клавишу",
        "clear_key": "Сбросить",
        "unbound": "Не назначено",
        "key_in_use": "Эта клавиша уже занята.",
        "capture_cancelled": "Смена клавиши отменена.",
        "speed_now": "Скорость {mag}",
        "speed_recommended": "{mag} (Рекомендовано)",
        "speed_notice": "Оповещение о скорости",
        "speed_notice_on": "Включено",
        "spot_top_left": "Левый верхний угол",
        "spot_top": "Верх",
        "spot_top_right": "Правый верхний угол",
        "spot_right": "Справа",
        "spot_bottom_right": "Правый нижний угол",
        "spot_bottom": "Низ",
        "spot_bottom_left": "Левый нижний угол",
        "spot_left": "Слева",
        "mode_tap": "Короткое нажатие",
        "mode_press": "Нажатие",
        "mode_double": "Двойное нажатие",
        "mode_long_press": "Долгое нажатие",
        "mode_hold": "Удержание",
        "mode_long_hold": "Долгое удержание",
        "autostart": "Автозапуск",
        "uninstall_driver": "Полностью удалить",
        "install_driver": "Установить драйвер",
        "status_error": "Ошибка пада",
        "status_capture": "Нажми новую клавишу",
        "status_walk": "Ходьба {mag}",
        "status_in_game": "В игре",
        "status_waiting": "Жду Helldivers 2",
        "walk_on": "Ходьба ВКЛ",
        "walk_off": "Ходьба ВЫКЛ",
        "start_game_first": "Сначала запусти Helldivers 2.",
        "pad_failed": "Виртуальный пад не открылся. Поставь ViGEmBus и перезапусти программу.",
        "key_saved": "Назначено: {name}",
        "wasd_busy": "WASD уже занят движением. Нажми другую клавишу.",
        "autostart_fail": "Не удалось изменить автозапуск.",
        "driver_missing_installer": "Драйвер не найден, и установщика в программе нет.",
        "driver_not_installed": "Драйвер не установлен. Ходьба не заработает, пока его не поставить.",
        "driver_cancelled": "Драйвер не установлен.",
        "driver_installed": "Драйвер установлен.",
        "driver_pad_fail": "Драйвер встал, но пад не открылся. Перезапусти Keep Walking.",
        "ask_install_title": APP_NAME,
        "ask_install": (
            "Для ходьбы нужен драйвер виртуального геймпада ViGEmBus (Nefarius).\n\n"
            "Он ставится один раз и остаётся в Windows, пока ты сам его не удалишь. "
            "Сразу после удаления Keep Walking сам его не возвращает.\n\n"
            "Если согласишься, откроется установщик и Windows спросит права администратора.\n\n"
            "Поставить драйвер сейчас?"
        ),
        "ask_uninstall_title": APP_NAME + " — Удаление",
        "ask_uninstall": (
            "Полностью удалить Keep Walking с этого ПК?\n\n"
            "Будет удалено:\n"
            "• драйвер виртуального геймпада ViGEmBus\n"
            "• автозапуск\n"
            "• настройки Keep Walking\n"
            "• сам Keep Walking\n\n"
            "Для полного удаления правда придётся перезагрузить ПК, "
            "думаю ты и сам сможешь это сделать (´｡• ᵕ •｡`)"
        ),
        "driver_not_found": "Драйвер в системе не найден. Программу и настройки всё равно удалим.",
        "uninstall_done": (
            "Keep Walking полностью удалён.\n\n"
            "Программа закроется и удалит себя.\n"
            "Для полной очистки драйвера перезагрузите ПК, когда будет удобно.\n"
            "Принудительно Windows перезагружать не будет."
        ),
        "uninstall_failed": "Удаление драйвера отменено или не удалось. Драйвер, возможно, ещё установлен.",
    },
}
WASD = {0x57, 0x41, 0x53, 0x44}
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
MOUSE_VK = {0x01, 0x02, 0x04, 0x05, 0x06}

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INJECT_TAG = 0x57A17001
SCAN = {0x57: 0x11, 0x41: 0x1E, 0x53: 0x1F, 0x44: 0x20}
KEY_NAMES = {
    0xA4: "Left Alt", 0xA5: "Right Alt",
    0xA0: "Left Shift", 0xA1: "Right Shift",
    0xA2: "Left Ctrl", 0xA3: "Right Ctrl",
    0x14: "Caps Lock", 0x1B: "Esc", 0x20: "Space",
    0x09: "Tab", 0x0D: "Enter",
}

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

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
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
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
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetKeyNameTextW.argtypes = [ctypes.c_long, wintypes.LPWSTR, ctypes.c_int]
user32.GetKeyNameTextW.restype = ctypes.c_int
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.SetLastError.argtypes = [wintypes.DWORD]
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.GetUserDefaultUILanguage.restype = wintypes.LANGID
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
QS_ALLINPUT = 0x04FF
user32.MsgWaitForMultipleObjects.argtypes = [
    wintypes.DWORD, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, wintypes.DWORD,
]
user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD

inject_info = ctypes.c_size_t(INJECT_TAG)
hook_handle = None
hook_proc_ref = None
pad = None
vg = None
tray_hwnd = None
tray_icon = None
nid = None
# Track WASD inside the hook. Swallowing LL keys clears GetAsyncKeyState.
wasd_held = {vk: False for vk in WASD}
# Keys held for walking. Swallow them until release so they do not spill into chat.
passthrough_block: set[int] = set()
was_driving = False
chat_down = False

def default_bindings() -> dict:
    return {
        "walk": {"vk": DEFAULT_VK, "mode": "tap"},
        "speed_up": {"vk": 0, "mode": "press"},
        "speed_down": {"vk": 0, "mode": "press"},
        "chat": {"vk": VK_RETURN, "mode": "press"},
    }


def snap_mag(value: float) -> float:
    return min(SPEEDS, key=lambda speed: abs(speed - float(value)))


state = {
    "walk": False,
    "vk": DEFAULT_VK,
    "capture": False,
    "capture_action": "walk",
    "running": True,
    "in_game": False,
    "game_pids": set(),
    "error": "",
    "driver_ok": False,
    "lang": "en",
    "mag": 0.85,
    "speed_spot": "bottom_left",
    "speed_notice": True,
    "typing": False,
    "mod_control": False,
    "bindings": default_bindings(),
}
mod_counts = {"walk": 0, "up": 0, "down": 0, "chat": 0}
mod_seen = False
edges = {
    action: {"held": False, "dirty": False, "down_at": 0.0, "fired": False, "last_tap": 0.0, "repeat_at": 0.0}
    for action in ACTIONS
}
VK_MENU = 0x12


def system_lang() -> str:
    lang_id = kernel32.GetUserDefaultUILanguage()
    return "ru" if (lang_id & 0xFF) == 0x19 else "en"


def t(key: str, **kwargs) -> str:
    table = STRINGS.get(state["lang"]) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"][key]
    return text.format(**kwargs) if kwargs else text


def set_lang(lang: str) -> None:
    if lang not in STRINGS or lang == state["lang"]:
        return
    state["lang"] = lang
    save_config()
    refresh_tray()


def log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(time.strftime("%H:%M:%S ") + message + "\n")
    except OSError:
        pass


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def key_name(vk: int) -> str:
    if vk in KEY_NAMES:
        return KEY_NAMES[vk]
    if 0x70 <= vk <= 0x87:
        return "F" + str(vk - 0x6F)
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    scan = user32.MapVirtualKeyW(vk, 0)
    if scan:
        buf = ctypes.create_unicode_buffer(64)
        if user32.GetKeyNameTextW(scan << 16, buf, 64):
            return buf.value
    return "VK " + str(vk)


def load_config() -> None:
    state["lang"] = system_lang()
    state["bindings"] = default_bindings()
    path = CONFIG_PATH if CONFIG_PATH.is_file() else _LEGACY_CONFIG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        lang = data.get("lang")
        if lang in STRINGS:
            state["lang"] = lang
        if "mag" in data:
            state["mag"] = snap_mag(data["mag"])
        raw = data.get("bindings") or {}
        if not raw and "toggle_vk" in data:
            vk = int(data["toggle_vk"])
            if vk == VK_MENU:
                vk = DEFAULT_VK
            if vk not in WASD and vk not in MOUSE_VK:
                state["bindings"]["walk"]["vk"] = vk
        for action in (*ACTIONS, "chat"):
            item = raw.get(action) or {}
            if "vk" in item:
                vk = int(item["vk"])
                if vk == VK_MENU:
                    vk = DEFAULT_VK
                if vk in WASD or vk in MOUSE_VK or not 0 <= vk <= 255:
                    vk = state["bindings"][action]["vk"]
                state["bindings"][action]["vk"] = vk
            mode = item.get("mode", state["bindings"][action]["mode"])
            if mode in MODES:
                state["bindings"][action]["mode"] = mode
        state["vk"] = state["bindings"]["walk"]["vk"]
        spot = data.get("speed_spot")
        if spot in SPEED_SPOTS:
            state["speed_spot"] = spot
        if "speed_notice" in data:
            state["speed_notice"] = bool(data["speed_notice"])
        if (
            path != CONFIG_PATH
            or "bindings" not in data
            or "mag" not in data
            or "chat" not in raw
            or "speed_spot" not in data
            or "speed_notice" not in data
        ):
            save_config()
    except (OSError, ValueError, TypeError):
        pass


def save_config() -> None:
    state["vk"] = state["bindings"]["walk"]["vk"]
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "toggle_vk": state["vk"],
                "lang": state["lang"],
                "mag": state["mag"],
                "speed_spot": state["speed_spot"],
                "speed_notice": state["speed_notice"],
                "bindings": state["bindings"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


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


def refresh_game_pids() -> set[int]:
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    found: set[int] = set()
    if not snapshot:
        state["game_pids"] = found
        return found
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            state["game_pids"] = found
            return found
        while True:
            if entry.szExeFile.lower() == "helldivers2.exe":
                found.add(int(entry.th32ProcessID))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    state["game_pids"] = found
    return found


def game_running() -> bool:
    return bool(refresh_game_pids())


def game_focused() -> bool:
    if not state["in_game"]:
        return False
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        # Fullscreen Helldivers hides its window from other programs.
        return True
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return True
    return int(pid.value) in state["game_pids"]


def driving_stick() -> bool:
    """Stick replaces WASD only while the game itself is being played."""
    return bool(
        state["walk"] and state["in_game"] and not state["typing"] and game_focused()
    )


def pause_held_wasd() -> None:
    """Drop the stick and keep a held walk key from typing until it is released."""
    for vk, held in wasd_held.items():
        if held:
            passthrough_block.add(vk)
        wasd_held[vk] = False


def sync_drive() -> None:
    global was_driving
    now = driving_stick()
    if was_driving and not now:
        pause_held_wasd()
    elif now and not was_driving:
        for vk in WASD:
            wasd_held[vk] = key_down(vk) or vk in passthrough_block
        passthrough_block.difference_update(WASD)
        release_wasd()
    was_driving = now


def wait_input() -> None:
    # The low-level hook runs on this thread. Sleep() holds every key on the PC
    # until it returns, which shows up as a late key release in the game.
    timeout = 16 if state["in_game"] else 100
    user32.MsgWaitForMultipleObjects(0, None, False, timeout, QS_ALLINPUT)


user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
user32.MessageBoxW.restype = ctypes.c_int
MB_YESNO = 0x4
MB_ICONWARNING = 0x30
MB_DEFBUTTON2 = 0x100
MB_SETFOREGROUND = 0x10000
MB_TOPMOST = 0x40000
IDYES = 6


def send_key(vk: int, up: bool) -> None:
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    event = INPUT(type=1, ki=KEYBDINPUT(0, SCAN[vk], flags, 0, inject_info.value))
    user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))


def release_wasd() -> None:
    for vk in WASD:
        if key_down(vk) or wasd_held.get(vk):
            wasd_held[vk] = True  # keep stick input if the key is still held
            send_key(vk, up=True)


def restore_wasd() -> None:
    """Hand movement back to the keyboard without forcing a key re-press."""
    for vk in WASD:
        if wasd_held.get(vk):
            send_key(vk, up=False)
            wasd_held[vk] = False


def stick_axes() -> tuple[float, float]:
    x = (1.0 if wasd_held[0x44] else 0.0) - (1.0 if wasd_held[0x41] else 0.0)
    y = (1.0 if wasd_held[0x57] else 0.0) - (1.0 if wasd_held[0x53] else 0.0)
    length = (x * x + y * y) ** 0.5
    if length == 0.0:
        return 0.0, 0.0
    scale = state["mag"] / length
    return x * scale, y * scale


def bundled_msi() -> Path | None:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(
            Path(sys._MEIPASS) / "vgamepad" / "win" / "vigem" / "install" / "x64" / "ViGEmBusSetup_x64.msi"
        )
    spec = importlib.util.find_spec("vgamepad")
    if spec and spec.origin:
        candidates.append(
            Path(spec.origin).resolve().parent / "win" / "vigem" / "install" / "x64" / "ViGEmBusSetup_x64.msi"
        )
    for path in candidates:
        if path.is_file():
            return path
    return None


def bus_imports() -> bool:
    import vgamepad  # Connects to ViGEmBus. Raises when the driver is missing.
    return True


def unload_vgamepad() -> None:
    for name in list(sys.modules):
        if name == "vgamepad" or name.startswith("vgamepad."):
            del sys.modules[name]


SEE_MASK_NOCLOSEPROCESS = 0x00000040


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


shell32 = ctypes.WinDLL("shell32", use_last_error=True)
shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.ShellExecuteExW.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL


def pump() -> None:
    msg = wintypes.MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def run_msiexec(parameters: str) -> int | None:
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = "msiexec.exe"
    info.lpParameters = parameters
    info.nShow = 1
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        return None
    if not info.hProcess:
        return None
    while kernel32.WaitForSingleObject(info.hProcess, 200) == 0x00000102:
        pump()
    code = wintypes.DWORD()
    kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    kernel32.CloseHandle(info.hProcess)
    return int(code.value)


def install_driver(msi: Path) -> bool:
    code = run_msiexec(f'/i "{msi}" /norestart')
    return code in (0, 3010)


def app_executable() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_VALUE)
        return bool(value)
    except OSError:
        return False


def set_autostart(enabled: bool) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, AUTOSTART_VALUE, 0, winreg.REG_SZ, app_executable())
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_VALUE)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        log(f"autostart: {exc}")
        notify(t("autostart_fail"))


def find_vigem_product() -> str | None:
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    name = winreg.EnumKey(root, index)
                    try:
                        with winreg.OpenKey(root, name) as key:
                            display, _ = winreg.QueryValueEx(key, "DisplayName")
                    except OSError:
                        continue
                    if "ViGEm" in str(display) or "Virtual Gamepad Emulation" in str(display):
                        if name.startswith("{") and name.endswith("}"):
                            return name
        except OSError:
            continue
    return VIGEM_PRODUCT_FALLBACK


def ask_install_driver() -> bool:
    answer = user32.MessageBoxW(
        None, t("ask_install"), t("ask_install_title"),
        MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_SETFOREGROUND | MB_TOPMOST,
    )
    return answer == IDYES


def ensure_driver() -> bool:
    try:
        bus_imports()
        state["error"] = ""
        state["driver_ok"] = True
        return True
    except Exception as first:
        state["driver_ok"] = False
        msi = bundled_msi()
        if msi is None:
            state["error"] = str(first)
            notify(t("driver_missing_installer"))
            return False
        unload_vgamepad()
        if not ask_install_driver():
            state["error"] = "Driver not installed"
            notify(t("driver_not_installed"))
            return False
        if not install_driver(msi):
            state["error"] = "Driver install was cancelled"
            notify(t("driver_cancelled"))
            return False
        try:
            bus_imports()
            state["error"] = ""
            state["driver_ok"] = True
            notify(t("driver_installed"))
            return True
        except Exception as exc:
            state["error"] = str(exc)
            notify(t("driver_pad_fail"))
            return False


def ensure_pad():
    global pad, vg
    if pad is not None:
        return True
    try:
        if vg is None:
            import vgamepad as imported
            vg = imported
        pad = vg.VX360Gamepad()
        state["error"] = ""
        return True
    except Exception as exc:
        state["error"] = str(exc)
        notify(t("pad_failed"))
        return False


def drop_pad() -> None:
    """Remove the virtual pad. Only when the game exits — not on walk toggle."""
    global pad
    if pad is None:
        return
    try:
        pad.reset()
        pad.update()
    except Exception:
        pass
    # Manual remove+free raced with VX360Gamepad.__del__ and killed the process.
    holder = pad
    pad = None
    try:
        del holder
        gc.collect()
    except Exception as exc:
        log(f"pad drop: {exc}")


def apply_stick(x: float, y: float) -> None:
    if pad is None:
        return
    pad.left_joystick_float(x_value_float=x, y_value_float=y)
    pad.update()


def set_walk(enabled: bool) -> None:
    global was_driving
    if enabled == state["walk"]:
        return
    if enabled:
        if not state["in_game"]:
            log("walk refused: game not detected")
            notify(t("start_game_first"))
            return
        if not ensure_pad():
            log("walk refused: pad failed " + state["error"])
            return
        for vk in WASD:
            wasd_held[vk] = key_down(vk)
        # Stick first, then pull WASD out of the game so the run→walk handoff is continuous.
        apply_stick(*stick_axes())
        state["walk"] = True
        install_hook()
        release_wasd()
        was_driving = True
        log("walk ON wasd=" + "".join(k for k, vk in (("W", 0x57), ("A", 0x41), ("S", 0x53), ("D", 0x44)) if wasd_held[vk]))
        notify(t("walk_on"))
    else:
        state["walk"] = False
        state["typing"] = False
        apply_stick(0.0, 0.0)
        for vk in WASD:
            if vk in passthrough_block:
                wasd_held[vk] = True
        passthrough_block.difference_update(WASD)
        restore_wasd()
        was_driving = False
        remove_hook()
        log("walk OFF")
        notify(t("walk_off"))
    refresh_tray()


def bind_vk_down(vk: int) -> bool:
    if vk <= 0:
        return False
    if key_down(vk):
        return True
    if vk == DEFAULT_VK and key_down(VK_MENU) and not key_down(0xA5):
        return True
    return False


def combo_keys(toggle_vk: int) -> list[int]:
    """Non-movement keys held together with a hotkey.

    WASD and the other Keep Walking keys are ignored, so a speed key
    does not cancel walk and movement does not spoil a tap.
    """
    ignore = set(WASD) | {toggle_vk, 0} | MOUSE_VK
    for bind in state["bindings"].values():
        ignore.add(int(bind["vk"]))
    if toggle_vk in (DEFAULT_VK, VK_MENU, 0xA5):
        ignore.update({DEFAULT_VK, VK_MENU, 0xA5})
    return [vk for vk in range(1, 256) if vk not in ignore and key_down(vk)]


def set_mag(value: float, announce: bool = True) -> None:
    snapped = snap_mag(value)
    changed = abs(snapped - state["mag"]) >= 0.001
    state["mag"] = snapped
    if changed:
        save_config()
        refresh_tray()
    if announce:
        show_speed_overlay(t("speed_now", mag=f"{state['mag']:.2f}"))


def set_speed_spot(spot: str) -> None:
    if spot not in SPEED_SPOTS or spot == state["speed_spot"]:
        return
    state["speed_spot"] = spot
    save_config()
    show_speed_overlay(t("speed_now", mag=f"{state['mag']:.2f}"))


def toggle_speed_notice() -> None:
    state["speed_notice"] = not state["speed_notice"]
    save_config()
    if state["speed_notice"]:
        show_speed_overlay(t("speed_now", mag=f"{state['mag']:.2f}"))
    else:
        hide_speed_overlay()


def bump_mag(delta: float) -> None:
    index = SPEEDS.index(snap_mag(state["mag"]))
    step = 1 if delta > 0 else -1
    set_mag(SPEEDS[(index + step) % len(SPEEDS)])


def fire_action(action: str) -> None:
    if action == "walk":
        if state["in_game"] and game_focused():
            set_walk(not state["walk"])
        else:
            log("walk ignored: game not focused or not detected")
        return
    if action == "speed_up" or action == "speed_down":
        # Only while the game is on screen and chat is closed, so typing elsewhere
        # does not change the walk speed.
        if state["in_game"] and game_focused() and not state["typing"]:
            bump_mag(MAG_STEP if action == "speed_up" else -MAG_STEP)
        return


# Helldivers stores keyboard names in EN-US, often with a space ("left ctrl").
INPUT_VK = {
    "enter": 0x0D, "return": 0x0D, "numpad enter": 0x0D,
    "escape": 0x1B, "esc": 0x1B,
    "space": 0x20, "tab": 0x09, "backspace": 0x08,
    "caps lock": 0x14, "capslock": 0x14,
    "left shift": 0xA0, "right shift": 0xA1,
    "left ctrl": 0xA2, "right ctrl": 0xA3,
    "left control": 0xA2, "right control": 0xA3,
    "left alt": 0xA4, "right alt": 0xA5,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "page up": 0x21, "page down": 0x22,
    "pause": 0x13, "print screen": 0x2C, "scroll lock": 0x91, "num lock": 0x90,
    "numpad 0": 0x60, "numpad 1": 0x61, "numpad 2": 0x62, "numpad 3": 0x63,
    "numpad 4": 0x64, "numpad 5": 0x65, "numpad 6": 0x66, "numpad 7": 0x67,
    "numpad 8": 0x68, "numpad 9": 0x69,
    "numpad +": 0x6B, "numpad -": 0x6D, "numpad *": 0x6A, "numpad /": 0x6F, "numpad .": 0x6E,
}
OEM_VK = {
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
    "minus": 0xBD, "equals": 0xBB, "comma": 0xBC, "period": 0xBE, "slash": 0xBF,
    "semicolon": 0xBA, "apostrophe": 0xDE, "grave": 0xC0, "backslash": 0xDC,
    "left bracket": 0xDB, "right bracket": 0xDD,
}
_chat_cache = {"checked": 0.0, "stamp": None, "vks": [VK_RETURN], "logged": None}


def input_name_vk(name: str) -> int | None:
    """Helldivers names the physical EN-US key, not the character it types."""
    key = " ".join(name.strip().lower().split())
    if key in INPUT_VK:
        return INPUT_VK[key]
    if key.startswith("f") and key[1:].isdigit():
        number = int(key[1:])
        if 1 <= number <= 24:
            return 0x6F + number
    if len(key) == 1 and "a" <= key <= "z":
        return ord(key.upper())
    if len(key) == 1 and "0" <= key <= "9":
        return ord(key)
    return OEM_VK.get(key)


def input_settings_path() -> Path | None:
    steam = ""
    user = 0
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = str(winreg.QueryValueEx(key, "SteamPath")[0])
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as key:
            user = int(winreg.QueryValueEx(key, "ActiveUser")[0])
    except OSError:
        steam = ""
        user = 0
    if steam and user:
        base = Path(steam) / "userdata" / str(user) / "553850"
        for path in (base / "remote" / "input_settings.config", base / "input_settings.config"):
            if path.is_file():
                return path
    found: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        saves = Path(appdata) / "Arrowhead" / "Helldivers2" / "saves"
        if saves.is_dir():
            found.extend(saves.glob("*input_settings.config"))
    if steam:
        root = Path(steam) / "userdata"
        if root.is_dir():
            found.extend(root.glob("*/553850/remote/input_settings.config"))
    files = [path for path in found if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def open_chat_vks_from_text(text: str) -> list[int] | None:
    """Keyboard VKs for Menu.OpenChat.

    None means the player never rebound it, so the game default (Enter) applies.
    An empty list means they removed the keyboard bind.
    """
    match = re.search(r"(?m)^[ \t]*OpenChat\s*=\s*\[", text)
    if not match:
        return None
    depth = 1
    index = match.end()
    while index < len(text) and depth:
        if text[index] == "[":
            depth += 1
        elif text[index] == "]":
            depth -= 1
        index += 1
    block = text[match.end():index - 1]
    vks: list[int] = []
    for obj in re.findall(r"\{([^{}]*)\}", block):
        device = re.search(r'device_type\s*=\s*"([^"]+)"', obj)
        named = re.search(r'input\s*=\s*"([^"]+)"', obj)
        if not device or not named or device.group(1) not in ("Keyboard", "SynergyKeyboard"):
            continue
        vk = input_name_vk(named.group(1))
        if vk and vk not in vks:
            vks.append(vk)
        elif not vk:
            log("game chat key unknown: " + named.group(1))
    return vks


def game_open_chat_vks() -> list[int]:
    now = time.monotonic()
    if now - _chat_cache["checked"] < 1.0:
        return _chat_cache["vks"]
    _chat_cache["checked"] = now
    path = input_settings_path()
    stamp = None
    parsed: list[int] | None = None
    if path is not None:
        try:
            stat = path.stat()
            stamp = (str(path), stat.st_mtime_ns, stat.st_size)
            if stamp == _chat_cache["stamp"]:
                return _chat_cache["vks"]
            parsed = open_chat_vks_from_text(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            parsed = None
    vks = [VK_RETURN] if parsed is None else parsed
    _chat_cache["stamp"] = stamp
    _chat_cache["vks"] = vks
    if vks != _chat_cache["logged"]:
        _chat_cache["logged"] = list(vks)
        if vks:
            log("game chat key " + ", ".join(key_name(vk) for vk in vks))
        else:
            log("game chat key unbound")
    return vks


def active_chat_vks() -> list[int]:
    """While the addon is loaded, follow the game's Open Chat. Otherwise the tray bind."""
    if state["mod_control"]:
        return game_open_chat_vks()
    vk = int(state["bindings"]["chat"]["vk"])
    return [vk] if vk else []


def read_mod_file() -> dict[str, int] | None:
    path = None
    newest = -1.0
    for candidate in MOD_PATHS:
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            continue
        if mtime > newest:
            newest = mtime
            path = candidate
    if path is None:
        return None
    try:
        age = time.time() - newest
        if age < 0 or age > MOD_STALE:
            return None
        data: dict[str, int] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in ("walk_n", "up_n", "down_n"):
                data[key] = int(float(value))
        if not data:
            return None
        return data
    except (OSError, ValueError):
        return None


def sync_mod_control() -> None:
    """Use Bingus Keep Walking binds while its heartbeat file stays fresh."""
    global mod_seen
    data = read_mod_file()
    active = data is not None
    if active != state["mod_control"]:
        state["mod_control"] = active
        if active:
            mod_seen = False
            log("mod control ON")
        else:
            state["typing"] = False
            log("mod control OFF")
        refresh_tray()
    if not active or data is None:
        return
    if not mod_seen:
        for key, field in (("walk", "walk_n"), ("up", "up_n"), ("down", "down_n")):
            mod_counts[key] = data.get(field, 0)
        mod_seen = True
        game_open_chat_vks()
        return
    mapping = (
        ("walk", "walk_n", "walk"),
        ("up", "up_n", "speed_up"),
        ("down", "down_n", "speed_down"),
    )
    for key, field, action in mapping:
        value = data.get(field, mod_counts[key])
        if value == mod_counts[key]:
            continue
        mod_counts[key] = value
        fire_action(action)


def poll_chat() -> None:
    """Track the in-game chat even while walk mode is off.

    The keyboard hook exists only during a walk, so without this a speed key
    still fires when the player is typing in chat.
    """
    global chat_down
    if state["walk"] or state["capture"]:
        return
    if not state["in_game"]:
        state["typing"] = False
        chat_down = False
        return
    if not game_focused():
        return
    vks = active_chat_vks()
    down = any(key_down(vk) for vk in vks)
    if down and not chat_down:
        state["typing"] = not state["typing"]
        log("chat " + ("on" if state["typing"] else "off"))
        if state["typing"]:
            pause_held_wasd()
    chat_down = down
    if state["typing"] and VK_ESCAPE not in vks and key_down(VK_ESCAPE):
        state["typing"] = False
        log("chat off")


def handle_bindings() -> None:
    """Helldivers-style activation for walk and the speed keys."""
    if state["mod_control"]:
        if state["typing"] and key_down(VK_ESCAPE):
            state["typing"] = False
            log("chat off")
        return
    now = time.monotonic()
    for action in ACTIONS:
        bind = state["bindings"][action]
        vk = int(bind["vk"])
        mode = bind["mode"]
        if not vk:
            continue
        edge = edges[action]
        down = bind_vk_down(vk)
        if down:
            if not edge["held"]:
                edge["held"] = True
                edge["dirty"] = bool(combo_keys(vk))
                edge["fired"] = False
                edge["down_at"] = now
                edge["repeat_at"] = now + HOLD_REPEAT
                if edge["dirty"]:
                    extra = combo_keys(vk)
                    log("combo, ignored: " + ", ".join(f"{vk_}:{key_name(vk_)}" for vk_ in extra[:8]))
                elif mode == "press":
                    fire_action(action)
                    edge["fired"] = True
                elif mode == "hold":
                    if action == "walk":
                        if state["in_game"] and game_focused():
                            set_walk(True)
                    else:
                        fire_action(action)
                    edge["fired"] = True
            elif combo_keys(vk):
                if not edge["dirty"]:
                    edge["dirty"] = True
                    if mode in ("hold", "long_hold") and action == "walk":
                        set_walk(False)
            elif not edge["dirty"]:
                held_for = now - edge["down_at"]
                if mode == "long_press" and not edge["fired"] and held_for >= LONG_AFTER:
                    fire_action(action)
                    edge["fired"] = True
                elif mode == "long_hold" and held_for >= LONG_AFTER:
                    if action == "walk":
                        if state["in_game"] and game_focused():
                            set_walk(True)
                    elif now >= edge["repeat_at"]:
                        fire_action(action)
                        edge["repeat_at"] = now + HOLD_REPEAT
                elif mode == "hold" and action != "walk" and now >= edge["repeat_at"]:
                    fire_action(action)
                    edge["repeat_at"] = now + HOLD_REPEAT
            continue
        if not edge["held"]:
            continue
        clean = not edge["dirty"]
        held_for = now - edge["down_at"]
        edge["held"] = False
        edge["dirty"] = False
        if mode in ("hold", "long_hold") and action == "walk":
            set_walk(False)
            continue
        if not clean:
            continue
        if mode == "tap" and held_for <= TAP_MAX:
            fire_action(action)
        elif mode == "double" and held_for <= TAP_MAX:
            if edge["last_tap"] and now - edge["last_tap"] <= DOUBLE_WINDOW:
                edge["last_tap"] = 0.0
                fire_action(action)
            else:
                edge["last_tap"] = now


def _pass_key(code, wparam, lparam):
    return user32.CallNextHookEx(hook_handle, code, wparam, lparam)


def hook_proc(code, wparam, lparam):
    global chat_down
    # While running, do nothing but forward the key. Any work here, or a sleep
    # in the hook thread, shows up as a late release in the game.
    if code < 0 or state["capture"] or not state["walk"]:
        return _pass_key(code, wparam, lparam)
    info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
    if info.dwExtraInfo == INJECT_TAG:
        return _pass_key(code, wparam, lparam)
    down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
    up = wparam in (WM_KEYUP, WM_SYSKEYUP)
    if not down and not up:
        return _pass_key(code, wparam, lparam)

    # While chat is open, WASD must type and the stick must stay at zero.
    # With the addon loaded this is the game's own Open Chat key. Esc closes it.
    chat_vks = active_chat_vks()
    if info.vkCode in chat_vks or (info.vkCode == VK_ESCAPE and state["typing"]):
        if game_focused():
            if info.vkCode in chat_vks and down and not chat_down:
                chat_down = True
                state["typing"] = not state["typing"]
                log("chat " + ("on" if state["typing"] else "off"))
                if state["typing"]:
                    pause_held_wasd()
            elif info.vkCode in chat_vks and up:
                chat_down = any(key_down(vk) for vk in chat_vks)
            elif info.vkCode == VK_ESCAPE and down and state["typing"] and info.vkCode not in chat_vks:
                state["typing"] = False
                log("chat off")
        return _pass_key(code, wparam, lparam)

    if info.vkCode not in WASD:
        return _pass_key(code, wparam, lparam)
    if info.vkCode in passthrough_block:
        if up:
            passthrough_block.discard(info.vkCode)
        return 1
    if driving_stick():
        wasd_held[info.vkCode] = down
        return 1
    if any(wasd_held.values()):
        pause_held_wasd()
        if info.vkCode in passthrough_block:
            if up:
                passthrough_block.discard(info.vkCode)
            return 1
    return _pass_key(code, wparam, lparam)



NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04
NIF_INFO = 0x10
NIF_SHOWTIP = 0x80
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
WM_TRAY = 0x401
WM_SHOWMENU = 0x8001
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_CONTEXTMENU = 0x007B
WM_NULL = 0
MF_STRING = 0
MF_GRAYED = 0x01
MF_CHECKED = 0x08
MF_POPUP = 0x10
MF_SEPARATOR = 0x800
TPM_LEFTALIGN = 0x0000
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
WHITENESS = 0x00FF0062
BLACK_BRUSH = 4


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = wintypes.HICON
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, wintypes.HWND, ctypes.c_void_p,
]
user32.TrackPopupMenu.restype = wintypes.UINT
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
gdi32.CreateBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.PatBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.Ellipse.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.CreatePen.restype = wintypes.HPEN
gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.GetStockObject.restype = wintypes.HGDIOBJ
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

wnd_proc_ref = None
menu_cmds = {}
menu_open = False
pending_menu = None
chat_submenu = None
hint_hwnd = None
hint_proc_ref = None
hint_text = ""
speed_hwnd = None
speed_proc_ref = None
speed_text = ""
speed_font = None

WM_MENUSELECT = 0x011F
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_TIMER = 0x0113
WS_BORDER = 0x00800000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
SW_HIDE = 0
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
DT_WORDBREAK = 0x0010
DT_NOPREFIX = 0x0800
DT_CALCRECT = 0x0400
COLOR_INFOBK = 24
COLOR_INFOTEXT = 23
TRANSPARENT = 1
HINT_WIDTH = 340
SPEED_KEY = 0x00FF00FF  # magenta color-key, drawn as transparent
SPEED_TIMER = 1
SPEED_SHOW_MS = 2200
LWA_COLORKEY = 0x1


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", wintypes.BYTE * 32),
    ]


user32.GetSubMenu.argtypes = [wintypes.HMENU, ctypes.c_int]
user32.GetSubMenu.restype = wintypes.HMENU
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = wintypes.HDC
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH]
user32.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.RECT), wintypes.UINT]
user32.DrawTextW.restype = ctypes.c_int
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetSysColor.argtypes = [ctypes.c_int]
user32.GetSysColor.restype = wintypes.DWORD
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = ctypes.c_void_p
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.KillTimer.restype = wintypes.BOOL
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.DWORD]
gdi32.CreateFontW.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR,
]
gdi32.CreateFontW.restype = wintypes.HFONT
gdi32.TextOutW.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
gdi32.TextOutW.restype = wintypes.BOOL
gdi32.GetTextExtentPoint32W.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.SIZE)]
gdi32.GetTextExtentPoint32W.restype = wintypes.BOOL


def _hint_proc(hwnd, msg, wparam, lparam):
    if msg == WM_ERASEBKGND:
        return 1
    if msg == WM_PAINT:
        paint = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(paint))
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        brush = gdi32.CreateSolidBrush(user32.GetSysColor(COLOR_INFOBK))
        user32.FillRect(hdc, ctypes.byref(rect), brush)
        gdi32.DeleteObject(brush)
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, user32.GetSysColor(COLOR_INFOTEXT))
        rect.left += 8
        rect.top += 6
        rect.right -= 8
        rect.bottom -= 6
        user32.DrawTextW(hdc, hint_text, -1, ctypes.byref(rect), DT_WORDBREAK | DT_NOPREFIX)
        user32.EndPaint(hwnd, ctypes.byref(paint))
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def ensure_hint() -> None:
    global hint_hwnd, hint_proc_ref
    if hint_hwnd:
        return
    hint_proc_ref = WNDPROC(_hint_proc)
    klass = WNDCLASSW()
    klass.lpfnWndProc = hint_proc_ref
    klass.hInstance = kernel32.GetModuleHandleW(None)
    klass.lpszClassName = "KeepWalkingHint"
    user32.RegisterClassW(ctypes.byref(klass))
    hint_hwnd = user32.CreateWindowExW(
        WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
        "KeepWalkingHint",
        None,
        0x80000000 | WS_BORDER,
        0, 0, HINT_WIDTH, 40,
        None, None, klass.hInstance, None,
    )


def show_chat_hint() -> None:
    global hint_text
    ensure_hint()
    if not hint_hwnd:
        return
    hint_text = t("chat_hint")
    hdc = user32.GetDC(hint_hwnd)
    rect = wintypes.RECT(8, 6, HINT_WIDTH - 8, 0)
    user32.DrawTextW(hdc, hint_text, -1, ctypes.byref(rect), DT_WORDBREAK | DT_NOPREFIX | DT_CALCRECT)
    user32.ReleaseDC(hint_hwnd, hdc)
    width = HINT_WIDTH
    height = max(rect.bottom + 12, 24)
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    x = point.x + 16
    y = point.y + 18
    if x + width > user32.GetSystemMetrics(0):
        x = max(0, point.x - width - 12)
    if y + height > user32.GetSystemMetrics(1):
        y = max(0, point.y - height - 8)
    user32.SetWindowPos(hint_hwnd, -1, x, y, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW)
    user32.InvalidateRect(hint_hwnd, None, True)


def hide_chat_hint() -> None:
    if hint_hwnd:
        user32.ShowWindow(hint_hwnd, SW_HIDE)


def _menu_is_chat(hmenu, flags: int, item: int) -> bool:
    if not chat_submenu:
        return False
    if flags & MF_POPUP:
        return int(user32.GetSubMenu(hmenu, item) or 0) == int(chat_submenu)
    return int(hmenu or 0) == int(chat_submenu)


def _speed_font():
    global speed_font
    if not speed_font:
        # Small label; outline is drawn around it in paint.
        speed_font = gdi32.CreateFontW(
            -14, 0, 0, 0, 600, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI",
        )
    return speed_font


def _draw_outlined_text(hdc, text: str, x: int, y: int) -> None:
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SelectObject(hdc, _speed_font())
    gdi32.SetTextColor(hdc, 0x000000)
    for dx, dy in (
        (-1, 0), (1, 0), (0, -1), (0, 1),
        (-1, -1), (-1, 1), (1, -1), (1, 1),
    ):
        gdi32.TextOutW(hdc, x + dx, y + dy, text, len(text))
    gdi32.SetTextColor(hdc, 0x00FFFFFF)
    gdi32.TextOutW(hdc, x, y, text, len(text))


def _speed_proc(hwnd, msg, wparam, lparam):
    if msg == WM_ERASEBKGND:
        return 1
    if msg == WM_TIMER and int(wparam) == SPEED_TIMER:
        hide_speed_overlay()
        return 0
    if msg == WM_PAINT:
        paint = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(paint))
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        brush = gdi32.CreateSolidBrush(SPEED_KEY)
        user32.FillRect(hdc, ctypes.byref(rect), brush)
        gdi32.DeleteObject(brush)
        if speed_text:
            _draw_outlined_text(hdc, speed_text, 3, 2)
        user32.EndPaint(hwnd, ctypes.byref(paint))
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def ensure_speed_overlay() -> None:
    global speed_hwnd, speed_proc_ref
    if speed_hwnd:
        return
    speed_proc_ref = WNDPROC(_speed_proc)
    klass = WNDCLASSW()
    klass.lpfnWndProc = speed_proc_ref
    klass.hInstance = kernel32.GetModuleHandleW(None)
    klass.lpszClassName = "KeepWalkingSpeed"
    user32.RegisterClassW(ctypes.byref(klass))
    speed_hwnd = user32.CreateWindowExW(
        WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT,
        "KeepWalkingSpeed",
        None,
        0x80000000,
        0, 0, 200, 48,
        None, None, klass.hInstance, None,
    )
    if speed_hwnd:
        user32.SetLayeredWindowAttributes(speed_hwnd, SPEED_KEY, 0, LWA_COLORKEY)


def screen_bounds() -> tuple[int, int, int, int]:
    hwnd = user32.GetForegroundWindow()
    monitor = user32.MonitorFromWindow(hwnd, 1)  # MONITOR_DEFAULTTOPRIMARY
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        rect = info.rcMonitor
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def speed_origin(width: int, height: int) -> tuple[int, int]:
    left, top, right, bottom = screen_bounds()
    pad = 4
    cx = left + (right - left - width) // 2
    cy = top + (bottom - top - height) // 2
    spot = state["speed_spot"]
    places = {
        "top_left": (left + pad, top + pad),
        "top": (cx, top + pad),
        "top_right": (right - width - pad, top + pad),
        "right": (right - width - pad, cy),
        "bottom_right": (right - width - pad, bottom - height - pad),
        "bottom": (cx, bottom - height - pad),
        "bottom_left": (left + pad, bottom - height - pad),
        "left": (left + pad, cy),
    }
    return places.get(spot, places["bottom_left"])


def show_speed_overlay(text: str) -> None:
    global speed_text
    if not state["speed_notice"]:
        return
    ensure_speed_overlay()
    if not speed_hwnd:
        return
    speed_text = text
    hdc = user32.GetDC(speed_hwnd)
    gdi32.SelectObject(hdc, _speed_font())
    size = wintypes.SIZE()
    gdi32.GetTextExtentPoint32W(hdc, speed_text, len(speed_text), ctypes.byref(size))
    user32.ReleaseDC(speed_hwnd, hdc)
    width = size.cx + 8
    height = size.cy + 6
    x, y = speed_origin(width, height)
    user32.SetWindowPos(speed_hwnd, -1, x, y, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW)
    user32.InvalidateRect(speed_hwnd, None, True)
    user32.SetTimer(speed_hwnd, SPEED_TIMER, SPEED_SHOW_MS, None)


def hide_speed_overlay() -> None:
    if not speed_hwnd:
        return
    user32.KillTimer(speed_hwnd, SPEED_TIMER)
    user32.ShowWindow(speed_hwnd, SW_HIDE)


def destroy_speed_overlay() -> None:
    global speed_hwnd, speed_font
    if speed_hwnd:
        user32.KillTimer(speed_hwnd, SPEED_TIMER)
        user32.DestroyWindow(speed_hwnd)
        speed_hwnd = None
    if speed_font:
        gdi32.DeleteObject(speed_font)
        speed_font = None


def tray_icon_file() -> Path:
    if state["walk"]:
        name = "walk.png"
    elif state["in_game"]:
        name = "game.png"
    else:
        name = "away.png"
    base = Path(sys._MEIPASS) / "icons" if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent / "icons"
    return base / name


_gp = None
_gp_token = ctypes.c_ulong()
icon_cache: dict[tuple[str, int], int] = {}


def _gdiplus():
    global _gp
    if _gp is not None:
        return _gp
    lib = ctypes.WinDLL("gdiplus")

    class GdiplusStartupInput(ctypes.Structure):
        _fields_ = [
            ("GdiplusVersion", ctypes.c_uint),
            ("DebugEventCallback", ctypes.c_void_p),
            ("SuppressBackgroundThread", ctypes.c_int),
            ("SuppressExternalCodecs", ctypes.c_int),
        ]

    lib.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(GdiplusStartupInput), ctypes.c_void_p]
    lib.GdiplusStartup.restype = ctypes.c_int
    lib.GdipCreateBitmapFromFile.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipCreateBitmapFromFile.restype = ctypes.c_int
    lib.GdipGetImageWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    lib.GdipGetImageWidth.restype = ctypes.c_int
    lib.GdipGetImageHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    lib.GdipGetImageHeight.restype = ctypes.c_int
    lib.GdipCreateBitmapFromScan0.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
    ]
    lib.GdipCreateBitmapFromScan0.restype = ctypes.c_int
    lib.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipGetImageGraphicsContext.restype = ctypes.c_int
    lib.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipSetPixelOffsetMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipSetCompositingQuality.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipGraphicsClear.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    lib.GdipDrawImageRectI.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ]
    lib.GdipDrawImageRectI.restype = ctypes.c_int
    lib.GdipCreateHICONFromBitmap.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.HICON)]
    lib.GdipCreateHICONFromBitmap.restype = ctypes.c_int
    lib.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
    lib.GdipDisposeImage.argtypes = [ctypes.c_void_p]
    startup = GdiplusStartupInput(1, None, 0, 0)
    if lib.GdiplusStartup(ctypes.byref(_gp_token), ctypes.byref(startup), None) != 0:
        raise OSError("gdiplus")
    _gp = lib
    return lib


def png_to_icon(path: Path, size: int):
    """Scale the picture into a square icon without stretching it."""
    lib = _gdiplus()
    src = ctypes.c_void_p()
    if lib.GdipCreateBitmapFromFile(str(path), ctypes.byref(src)) != 0 or not src:
        return None
    width = ctypes.c_uint()
    height = ctypes.c_uint()
    lib.GdipGetImageWidth(src, ctypes.byref(width))
    lib.GdipGetImageHeight(src, ctypes.byref(height))
    # 32-bit premultiplied alpha so the hexagon keeps a clean edge.
    dst = ctypes.c_void_p()
    status = lib.GdipCreateBitmapFromScan0(size, size, 0, 0x000E200B, None, ctypes.byref(dst))
    graphics = ctypes.c_void_p()
    icon = None
    if status == 0 and dst:
        if lib.GdipGetImageGraphicsContext(dst, ctypes.byref(graphics)) == 0 and graphics:
            lib.GdipSetInterpolationMode(graphics, 7)  # HighQualityBicubic
            lib.GdipSetPixelOffsetMode(graphics, 4)  # Half
            lib.GdipSetCompositingQuality(graphics, 2)
            lib.GdipGraphicsClear(graphics, 0)
            pad = 1 if size <= 24 else 2
            avail = max(1, size - pad * 2)
            scale = min(avail / max(1, width.value), avail / max(1, height.value))
            draw_w = max(1, int(round(width.value * scale)))
            draw_h = max(1, int(round(height.value * scale)))
            draw_x = (size - draw_w) // 2
            draw_y = (size - draw_h) // 2
            lib.GdipDrawImageRectI(graphics, src, draw_x, draw_y, draw_w, draw_h)
            lib.GdipDeleteGraphics(graphics)
        handle = wintypes.HICON()
        if lib.GdipCreateHICONFromBitmap(dst, ctypes.byref(handle)) == 0:
            icon = handle
        lib.GdipDisposeImage(dst)
    lib.GdipDisposeImage(src)
    return icon


def state_icon():
    path = tray_icon_file()
    size = int(user32.GetSystemMetrics(49) or 32)
    if size < 16:
        size = 16
    key = (path.name, size)
    cached = icon_cache.get(key)
    if cached:
        return cached
    icon = png_to_icon(path, size) if path.is_file() else None
    if not icon:
        log("icon load failed " + str(path))
        colors = {"walk.png": (46, 160, 67), "game.png": (240, 200, 30), "away.png": (220, 40, 40)}
        icon = make_icon(*colors.get(path.name, (120, 120, 120)))
    icon_cache[key] = icon
    return icon


def _rgb(r: int, g: int, b: int) -> int:
    return r | (g << 8) | (b << 16)


def make_icon(r: int, g: int, b: int):
    size = 32
    screen = user32.GetDC(None)
    color_dc = gdi32.CreateCompatibleDC(screen)
    mask_dc = gdi32.CreateCompatibleDC(screen)
    color = gdi32.CreateCompatibleBitmap(screen, size, size)
    mask = gdi32.CreateBitmap(size, size, 1, 1, None)
    gdi32.SelectObject(color_dc, color)
    gdi32.SelectObject(mask_dc, mask)
    gdi32.PatBlt(mask_dc, 0, 0, size, size, WHITENESS)
    gdi32.SelectObject(mask_dc, gdi32.GetStockObject(BLACK_BRUSH))
    gdi32.Ellipse(mask_dc, 1, 1, 31, 31)
    brush = gdi32.CreateSolidBrush(_rgb(r, g, b))
    pen = gdi32.CreatePen(0, 1, _rgb(r, g, b))
    gdi32.SelectObject(color_dc, brush)
    gdi32.SelectObject(color_dc, pen)
    gdi32.Ellipse(color_dc, 1, 1, 31, 31)
    white = gdi32.CreateSolidBrush(_rgb(255, 255, 255))
    white_pen = gdi32.CreatePen(0, 1, _rgb(255, 255, 255))
    gdi32.SelectObject(color_dc, white)
    gdi32.SelectObject(color_dc, white_pen)
    gdi32.Ellipse(color_dc, 11, 11, 21, 21)
    info = ICONINFO(True, 0, 0, mask, color)
    icon = user32.CreateIconIndirect(ctypes.byref(info))
    gdi32.DeleteObject(brush)
    gdi32.DeleteObject(pen)
    gdi32.DeleteObject(white)
    gdi32.DeleteObject(white_pen)
    gdi32.DeleteObject(color)
    gdi32.DeleteObject(mask)
    gdi32.DeleteDC(color_dc)
    gdi32.DeleteDC(mask_dc)
    user32.ReleaseDC(None, screen)
    return icon


def tray_color() -> tuple[int, int, int]:
    if state["walk"]:
        return 46, 160, 67
    if state["in_game"]:
        return 47, 111, 178
    if state["error"]:
        return 180, 60, 50
    return 120, 120, 120


def _wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_MENUSELECT:
        word = int(wparam) & 0xFFFFFFFF
        flags = (word >> 16) & 0xFFFF
        if flags == 0xFFFF or not lparam:
            hide_chat_hint()
        elif _menu_is_chat(lparam, flags, word & 0xFFFF):
            show_chat_hint()
        else:
            hide_chat_hint()
        return 0
    if msg == WM_TRAY:
        click = int(lparam) & 0xFFFF
        # Open menu outside this handler — TrackPopupMenu from WM_TRAY is flaky.
        if click in (WM_LBUTTONUP, WM_RBUTTONUP, WM_CONTEXTMENU, WM_LBUTTONDBLCLK):
            user32.PostMessageW(hwnd, WM_SHOWMENU, 0, 0)
            return 0
    elif msg == WM_SHOWMENU:
        show_menu()
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def force_foreground(hwnd) -> None:
    fg = user32.GetForegroundWindow()
    this = kernel32.GetCurrentThreadId()
    other = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    if other and other != this:
        user32.AttachThreadInput(this, other, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if other and other != this:
        user32.AttachThreadInput(this, other, False)


def status_line() -> str:
    if state["error"]:
        return t("status_error")
    if state["capture"]:
        return t("status_capture")
    if state["walk"]:
        return t("status_walk", mag=f"{state['mag']:.2f}")
    if state["in_game"]:
        return t("status_in_game")
    return t("status_waiting")


def setup_tray() -> None:
    global tray_hwnd, tray_icon, nid, wnd_proc_ref
    wnd_proc_ref = WNDPROC(_wnd_proc)
    klass = WNDCLASSW()
    klass.lpfnWndProc = wnd_proc_ref
    klass.hInstance = kernel32.GetModuleHandleW(None)
    klass.lpszClassName = "KeepWalkingTray"
    atom = user32.RegisterClassW(ctypes.byref(klass))
    # A real hidden window. Message-only windows (HWND_MESSAGE) show the icon
    # but never receive its clicks.
    tray_hwnd = user32.CreateWindowExW(
        0, "KeepWalkingTray", APP_NAME, 0x80000000,
        0, 0, 0, 0, None, None, klass.hInstance, None,
    )
    if not tray_hwnd:
        log(f"tray window failed err={ctypes.get_last_error()} class={atom}")
        return
    tray_icon = state_icon()
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = tray_hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP
    nid.uCallbackMessage = WM_TRAY
    nid.hIcon = tray_icon
    nid.szTip = (APP_NAME + " — " + status_line())[:127]
    if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
        log("tray icon failed err=" + str(ctypes.get_last_error()))
    else:
        log(f"tray hwnd={int(tray_hwnd)}")


def refresh_tray() -> None:
    global tray_icon
    if nid is None:
        return
    tray_icon = state_icon()
    nid.hIcon = tray_icon
    nid.szTip = (APP_NAME + " — " + status_line())[:127]
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP
    nid.szInfo = ""
    shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))


def balloon(message: str) -> None:
    # No Windows toast — status stays in the tray tip and on-screen overlays.
    return


def notify(message: str) -> None:
    return


def _item(menu, text: str, callback=None, checked: bool = False, enabled: bool = True) -> None:
    flags = MF_STRING
    if checked:
        flags |= MF_CHECKED
    if not enabled:
        flags |= MF_GRAYED
    cmd = 0
    if callback is not None and enabled:
        cmd = len(menu_cmds) + 1
        menu_cmds[cmd] = callback
    user32.AppendMenuW(menu, flags, cmd, text)


def _popup(parent, text: str):
    menu = user32.CreatePopupMenu()
    user32.AppendMenuW(parent, MF_POPUP | MF_STRING, menu, text)
    return menu


def _sep(menu) -> None:
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)


def show_menu(page: str | None = None) -> None:
    global menu_open, chat_submenu
    if menu_open or not tray_hwnd:
        return
    menu_open = True
    log("menu open")
    menu_cmds.clear()
    try:
        root = user32.CreatePopupMenu()
        _item(root, status_line(), enabled=False)
        settings = _popup(root, t("settings"))
        speeds = _popup(settings, t("speed"))
        for mag in SPEEDS:
            label = t("speed_recommended", mag=f"{mag:.2f}") if abs(mag - 0.85) < 0.001 else f"{mag:.2f}"
            _item(
                speeds, label,
                (lambda value: (lambda: set_mag(value)))(mag),
                checked=abs(state["mag"] - mag) < 0.001,
            )
        notice = _popup(settings, t("speed_notice"))
        _item(notice, t("speed_notice_on"), toggle_speed_notice, checked=state["speed_notice"])
        _sep(notice)
        for spot in SPEED_SPOTS:
            _item(
                notice, t("spot_" + spot),
                (lambda name: (lambda: set_speed_spot(name)))(spot),
                checked=state["speed_spot"] == spot,
            )
        hotkeys = _popup(settings, t("hotkeys"))
        if state["mod_control"]:
            _item(hotkeys, t("mod_control"), enabled=False)
        else:
            for action, label in (("walk", "bind_walk"), ("speed_up", "bind_up"), ("speed_down", "bind_down")):
                branch = _popup(hotkeys, t(label, name=bind_label(action)))
                _item(branch, t("change_key"), (lambda act: (lambda: begin_capture(act)))(action))
                if int(state["bindings"][action]["vk"]) > 0:
                    _item(branch, t("clear_key"), (lambda act: (lambda: clear_bind(act)))(action))
                _sep(branch)
                for mode in MODES:
                    _item(
                        branch, t("mode_" + mode),
                        (lambda act, m: (lambda: set_mode(act, m)))(action, mode),
                        checked=state["bindings"][action]["mode"] == mode,
                    )
            chat_submenu = _popup(hotkeys, t("bind_chat", name=bind_label("chat")))
            _item(chat_submenu, t("change_key"), lambda: begin_capture("chat"))
        language = _popup(settings, t("language"))
        _item(language, t("lang_en"), lambda: set_lang("en"), checked=state["lang"] == "en")
        _item(language, t("lang_ru"), lambda: set_lang("ru"), checked=state["lang"] == "ru")
        _item(settings, t("autostart"), toggle_autostart, checked=autostart_enabled())
        _sep(settings)
        if state["driver_ok"]:
            _item(settings, t("uninstall_driver"), uninstall_driver_from_menu)
        else:
            _item(settings, t("install_driver"), install_driver_from_menu)
        _item(root, t("quit"), quit_app)
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        force_foreground(tray_hwnd)
        flags = TPM_LEFTALIGN | TPM_RIGHTBUTTON | TPM_RETURNCMD
        shown = hotkeys if page == "hotkeys" else root
        chosen = user32.TrackPopupMenu(
            shown, flags, point.x, point.y, 0, tray_hwnd, None,
        )
        user32.PostMessageW(tray_hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(root)
        log(f"menu chosen={int(chosen or 0)}")
        callback = menu_cmds.get(int(chosen or 0))
        if callback:
            callback()
    except Exception as exc:
        log(f"menu error: {exc}")
    finally:
        hide_chat_hint()
        chat_submenu = None
        menu_open = False


def remove_tray() -> None:
    global tray_icon, nid
    destroy_speed_overlay()
    for icon in icon_cache.values():
        if icon:
            user32.DestroyIcon(icon)
    icon_cache.clear()
    tray_icon = None
    if nid is not None:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        nid = None
    if tray_icon:
        user32.DestroyIcon(tray_icon)
        tray_icon = None


def bind_label(action: str) -> str:
    vk = int(state["bindings"][action]["vk"])
    return t("unbound") if vk <= 0 else key_name(vk)


def begin_capture(action: str = "walk") -> None:
    global pending_menu
    state["capture"] = True
    state["capture_action"] = action
    pending_menu = "hotkeys"
    refresh_tray()


def set_mode(action: str, mode: str) -> None:
    if mode not in MODES or state["bindings"][action]["mode"] == mode:
        return
    state["bindings"][action]["mode"] = mode
    edges[action]["held"] = False
    edges[action]["dirty"] = False
    save_config()
    refresh_tray()


def clear_bind(action: str) -> None:
    state["bindings"][action]["vk"] = 0
    if action == "walk":
        state["vk"] = 0
    edges[action]["held"] = False
    save_config()
    refresh_tray()


def quit_app(_icon=None, _item=None) -> None:
    state["running"] = False
    state["walk"] = False
    drop_pad()
    remove_tray()


def pressed_key() -> int | None:
    # Prefer Left/Right variants over generic Alt/Shift/Ctrl (VK 16-18).
    for vk in (0xA0, 0xA1, 0xA2, 0xA3, DEFAULT_VK, 0xA5):
        if key_down(vk):
            return vk
    for vk in range(1, 256):
        if vk in MOUSE_VK or vk in (0x10, 0x11, VK_MENU):
            continue
        if key_down(vk):
            return vk
    return None


def take_captured_key(vk: int) -> None:
    action = state["capture_action"]
    if vk == 0x1B:
        state["capture"] = False
        refresh_tray()
        notify(t("capture_cancelled"))
        return
    if vk in WASD:
        refresh_tray()
        balloon(t("wasd_busy"))
        return
    if vk == VK_MENU:
        vk = DEFAULT_VK
    for other, bind in state["bindings"].items():
        if other != action and int(bind["vk"]) == vk:
            balloon(t("key_in_use"))
            return
    state["bindings"][action]["vk"] = vk
    state["vk"] = state["bindings"]["walk"]["vk"]
    state["capture"] = False
    save_config()
    refresh_tray()
    notify(t("key_saved", name=key_name(vk)))


def install_driver_from_menu(_icon=None, _item=None) -> None:
    ensure_driver()
    refresh_tray()


def toggle_autostart(_icon=None, _item=None) -> None:
    set_autostart(not autostart_enabled())
    refresh_tray()


def choose_lang_en(_icon=None, _item=None) -> None:
    set_lang("en")


def choose_lang_ru(_icon=None, _item=None) -> None:
    set_lang("ru")


def clear_app_data() -> None:
    set_autostart(False)
    for path in (CONFIG_PATH, LOG_PATH, _LEGACY_CONFIG):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    for folder in (CONFIG_DIR, _LEGACY_CONFIG.parent):
        try:
            folder.rmdir()
        except OSError:
            pass


def schedule_self_delete() -> None:
    """Delete KeepWalking.exe after this process exits. No-op when running from source."""
    if not getattr(sys, "frozen", False):
        log("self-delete skipped: not a frozen build")
        return
    exe = str(Path(sys.executable).resolve())
    # ping delay lets this process exit and unlock the file, then del removes it.
    command = f'ping -n 3 127.0.0.1 >nul & del /f /q "{exe}"'
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", command],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        log(f"self-delete scheduled: {exe}")
    except OSError as exc:
        log(f"self-delete failed: {exc}")


def uninstall_driver_from_menu(_icon=None, _item=None) -> None:
    answer = user32.MessageBoxW(
        None, t("ask_uninstall"), t("ask_uninstall_title"),
        MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_SETFOREGROUND | MB_TOPMOST,
    )
    if answer != IDYES:
        return

    set_walk(False)
    drop_pad()
    unload_vgamepad()

    product = find_vigem_product()
    driver_gone = False
    if product:
        # /norestart — no forced reboot; 3010 means reboot recommended.
        code = run_msiexec(f'/x "{product}" /norestart')
        log(f"uninstall vigem code={code} product={product}")
        driver_gone = code in (0, 3010)
    else:
        driver_gone = True
        log("uninstall: no ViGEm product found")

    clear_app_data()
    state["driver_ok"] = False
    state["error"] = ""

    if driver_gone:
        user32.MessageBoxW(
            None, t("uninstall_done"), APP_NAME,
            0x40 | MB_SETFOREGROUND | MB_TOPMOST,  # MB_ICONINFORMATION
        )
        schedule_self_delete()
        quit_app()
        return

    user32.MessageBoxW(
        None, t("uninstall_failed"), APP_NAME,
        MB_ICONWARNING | MB_SETFOREGROUND | MB_TOPMOST,
    )
    refresh_tray()


def install_hook() -> None:
    global hook_handle, hook_proc_ref
    if hook_handle:
        return
    hook_proc_ref = HOOKPROC(hook_proc)
    hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_proc_ref, None, 0)
    err = ctypes.get_last_error()
    log("hook " + (f"ok handle={int(hook_handle)}" if hook_handle else f"FAILED err={err}"))


def remove_hook() -> None:
    global hook_handle
    if not hook_handle:
        return
    user32.UnhookWindowsHookEx(hook_handle)
    hook_handle = None
    log("hook off")


def main() -> None:
    global hook_handle, hook_proc_ref, pending_menu
    mutex = kernel32.CreateMutexW(None, False, "Local\\KeepWalkingToggle")
    if ctypes.get_last_error() == 183:
        log("second copy ignored")
        return

    load_config()
    log(
        f"started pid={os.getpid()} walk_key={state['vk']} ({key_name(state['vk'])}) "
        f"mode={state['bindings']['walk']['mode']} mag={state['mag']:.2f}"
    )
    setup_tray()
    refresh_tray()

    log("driver " + ("ok" if ensure_driver() else "FAILED " + state["error"]))
    refresh_tray()

    last_xy = (0.0, 0.0)
    last_game = 0.0
    capture_wait = True
    msg = wintypes.MSG()
    try:
        while state["running"]:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            now = time.monotonic()
            if now - last_game >= 0.5:
                last_game = now
                running = game_running()
                if running != state["in_game"]:
                    state["in_game"] = running
                    log(f"game {'found' if running else 'gone'} pids={sorted(state['game_pids'])}")
                    if running:
                        if ensure_pad():
                            apply_stick(0.0, 0.0)
                            log("pad ready (kept while game runs)")
                        else:
                            log("pad failed " + state["error"])
                    else:
                        state["typing"] = False
                        set_walk(False)
                        drop_pad()
                    refresh_tray()
                elif running and pad is None:
                    ensure_pad()

            if state["capture"]:
                vk = pressed_key()
                if vk is None:
                    capture_wait = False
                elif not capture_wait:
                    take_captured_key(vk)
                    capture_wait = True
            elif pending_menu:
                # The menu closed so the new key could be read. Open Hotkeys
                # again once that key is up, so the next bind is one click away.
                if pressed_key() is None and not menu_open:
                    page = pending_menu
                    pending_menu = None
                    show_menu(page=page)
            else:
                sync_mod_control()
                poll_chat()
                handle_bindings()

            sync_drive()
            if driving_stick() and pad is not None:
                xy = stick_axes()
            else:
                xy = (0.0, 0.0)
            if xy != last_xy and pad is not None:
                apply_stick(*xy)
                last_xy = xy
            elif xy == (0.0, 0.0) and last_xy != xy and pad is not None:
                apply_stick(0.0, 0.0)
                last_xy = xy
            elif xy == (0.0, 0.0):
                last_xy = xy
            wait_input()
    finally:
        log("stopped")
        state["walk"] = False
        drop_pad()
        remove_tray()
        if hook_handle:
            user32.UnhookWindowsHookEx(hook_handle)
            hook_handle = None
        if mutex:
            kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
