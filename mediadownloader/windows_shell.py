"""Explicit Windows taskbar identity and pin/relaunch metadata for the native window.

The running Qt icon and the icon of a pinned Shell shortcut are separate things.
Set relaunch properties before the window AppUserModelID, as required by Shell.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
import uuid
from pathlib import Path

APP_ID = "Neyen.MediaDownloader.Desktop"
PROPERTY_IDS = {"command": 2, "icon": 3, "name": 4, "id": 5}


class GUID(ctypes.Structure):
    _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16),
                ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8)]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_uint32)]


class _Value(ctypes.Union):
    _fields_ = [("pointer", ctypes.c_void_p),
                ("storage", ctypes.c_ubyte * (16 if ctypes.sizeof(ctypes.c_void_p) == 8 else 8))]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_uint16), ("reserved", ctypes.c_uint16 * 3),
                ("value", _Value)]


def guid(value):
    return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def key(pid):
    return PROPERTYKEY(guid("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3"), pid)


def check_hresult(result):
    if result < 0:
        raise OSError(f"Windows Shell HRESULT 0x{result & 0xffffffff:08x}")


class WindowStore:
    """Minimal, typed IPropertyStore binding; all COM references stay on this thread."""
    def __init__(self, hwnd):
        self.ptr = ctypes.c_void_p()
        self.ole = ctypes.WinDLL("ole32")
        self.ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.ole.CoInitializeEx.restype = ctypes.c_int32
        initialized = self.ole.CoInitializeEx(None, 2)
        # RPC_E_CHANGED_MODE means the Qt thread already initialized another COM model.
        self.uninitialize = initialized >= 0
        if initialized < 0 and initialized != -2147417850:
            check_hresult(initialized)
        shell = ctypes.WinDLL("shell32")
        get_store = shell.SHGetPropertyStoreForWindow
        get_store.argtypes = [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        get_store.restype = ctypes.c_int32
        try:
            iid = guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")
            check_hresult(get_store(hwnd, ctypes.byref(iid), ctypes.byref(self.ptr)))
            self.vtable = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        except Exception:
            self.close()
            raise

    def set(self, pid, text=None):
        variant = PROPVARIANT()
        # A Python-owned string stays alive until SetValue has copied it. VT_EMPTY clears.
        if text is not None:
            text_buffer = ctypes.create_unicode_buffer(text)
            variant.vt = 31  # VT_LPWSTR
            variant.value.pointer = ctypes.cast(text_buffer, ctypes.c_void_p).value
        method = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p,
                    ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(self.vtable[6])
        prop = key(pid)
        check_hresult(method(self.ptr, ctypes.byref(prop), ctypes.byref(variant)))

    def get(self, pid):
        variant = PROPVARIANT()
        method = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p,
                    ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(self.vtable[5])
        prop = key(pid)
        check_hresult(method(self.ptr, ctypes.byref(prop), ctypes.byref(variant)))
        try:
            return ctypes.wstring_at(variant.value.pointer) if variant.vt == 31 else None
        finally:
            self.ole.PropVariantClear.argtypes = [ctypes.POINTER(PROPVARIANT)]
            self.ole.PropVariantClear.restype = ctypes.c_int32
            check_hresult(self.ole.PropVariantClear(ctypes.byref(variant)))

    def close(self):
        if self.ptr.value:
            table = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            ctypes.WINFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)(table[2])(self.ptr)
            self.ptr = ctypes.c_void_p()
        if self.uninitialize:
            self.ole.CoUninitialize()
            self.uninitialize = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def configure_window(hwnd, executable):
    if sys.platform != "win32":
        return {}
    executable = Path(executable).resolve()
    icon = executable.with_name("MediaDownloader.ico")
    if not icon.is_file():
        raise OSError("Falta el icono de Windows del paquete")
    expected = {"command": subprocess.list2cmdline([str(executable)]),
                "icon": f"{icon},0", "name": "MediaDownloader", "id": APP_ID}
    with WindowStore(hwnd) as store:
        for name, value in expected.items():
            store.set(PROPERTY_IDS[name], value)
        observed = {name: store.get(pid) for name, pid in PROPERTY_IDS.items()}
    if observed != expected:
        raise OSError("Windows no conservó la identidad de MediaDownloader")
    return observed


def clear_window(hwnd):
    if sys.platform == "win32":
        with WindowStore(hwnd) as store:
            for pid in PROPERTY_IDS.values():
                store.set(pid)
