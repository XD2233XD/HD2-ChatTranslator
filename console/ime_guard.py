"""输入法守护：游戏在前台时把游戏窗口的键盘布局切到英文（US），离开时还原。

HD2 的中文 IME 处理有 bug（组字会卡控制、甚至把焦点弹出去）。这里不修改游戏，
只在游戏窗口获得前台时向它发 WM_INPUTLANGCHANGEREQUEST，把该窗口线程的键盘布局
切到 00000409（英文）；离开游戏再切回原来的布局。中文输入请用控制台的「控制台发言」。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WM_INPUTLANGCHANGEREQUEST = 0x0050
KLF_ACTIVATE = 0x00000001
LANG_ENGLISH = 0x0409
HKL_EN_US = 0x04090409

user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetKeyboardLayout.argtypes = [wt.DWORD]
user32.GetKeyboardLayout.restype = wt.HKL
user32.LoadKeyboardLayoutW.argtypes = [wt.LPCWSTR, wt.UINT]
user32.LoadKeyboardLayoutW.restype = wt.HKL
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostMessageW.restype = wt.BOOL

kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)
]
kernel32.QueryFullProcessImageNameW.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]


def foreground_process() -> tuple[int, str]:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0, ""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return 0, ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return 0, ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return 0, ""
        return pid.value, buf.value
    finally:
        kernel32.CloseHandle(handle)


def _layout_lang(hkl: int) -> int:
    return int(hkl) & 0xFFFF


class ImeGuard:
    def __init__(self, target_exe: str = "helldivers2.exe"):
        self.target = target_exe.lower()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hwnd = 0
        self._orig_hkl = None
        self.status = {"running": False, "active": False, "hwnd": 0, "layout": "", "note": ""}
        self._lock = threading.Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.status.update({"running": True, "note": "watching"})

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._restore()
        self.status.update({"running": False, "note": "stopped"})

    def _restore(self):
        with self._lock:
            if self._hwnd and self._orig_hkl:
                try:
                    user32.PostMessageW(self._hwnd, WM_INPUTLANGCHANGEREQUEST, 0, self._orig_hkl)
                except Exception:
                    pass
            self._hwnd, self._orig_hkl = 0, None
            self.status["active"] = False
            self.status["hwnd"] = 0

    def _apply(self, hwnd: int):
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        cur = user32.GetKeyboardLayout(tid) or 0
        with self._lock:
            self._hwnd = hwnd
            self._orig_hkl = cur
        if _layout_lang(cur) == LANG_ENGLISH:
            self.status.update({
                "active": True, "hwnd": int(hwnd), "layout": "0x0409",
                "note": "game foreground, layout already English",
            })
            return
        en = user32.LoadKeyboardLayoutW("00000409", KLF_ACTIVATE) or HKL_EN_US
        user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, en)
        self.status.update({
            "active": True, "hwnd": int(hwnd), "layout": "0x0409",
            "note": "game foreground, keyboard layout -> English (US)",
        })

    def _run(self):
        while not self._stop.is_set():
            try:
                _, exe = foreground_process()
                is_game = exe.lower().endswith(self.target)
                if is_game:
                    hwnd = user32.GetForegroundWindow()
                    if hwnd and hwnd != self._hwnd:
                        self._restore()
                        self._apply(hwnd)
                elif self.status["active"]:
                    self._restore()
                    self.status["note"] = "left game, keyboard layout restored"
            except Exception as exc:
                self.status["note"] = "error: " + str(exc)
            self._stop.wait(0.5)


GUARD = ImeGuard()
