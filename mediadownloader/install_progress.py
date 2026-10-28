"""Tiny native Windows installer window: no Qt/Electron dependency in the helper."""
import ctypes
import os
from pathlib import Path
from ctypes import wintypes as W


class ProgressWindow:
    def __init__(self, root):
        self.hwnd = None
        self.value = -1
        self.text = ''
        if os.name != 'nt':
            return
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        comctl = ctypes.WinDLL('comctl32')
        kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]; kernel.GetModuleHandleW.restype = W.HINSTANCE
        self.user.CreateWindowExW.argtypes = [W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,
                                            ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,ctypes.c_void_p]
        self.user.CreateWindowExW.restype = W.HWND
        self.user.SendMessageW.argtypes = [W.HWND,W.UINT,W.WPARAM,W.LPARAM]
        self.user.SendMessageW.restype = W.LPARAM
        self.user.GetWindowLongW.argtypes = [W.HWND,ctypes.c_int]; self.user.GetWindowLongW.restype = W.LONG
        self.user.SetWindowLongW.argtypes = [W.HWND,ctypes.c_int,W.LONG]; self.user.SetWindowLongW.restype = W.LONG
        self.user.GetWindowTextW.argtypes = [W.HWND,W.LPWSTR,ctypes.c_int]
        self.user.SetWindowTextW.argtypes = [W.HWND,W.LPCWSTR]
        self.user.PeekMessageW.argtypes = [ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT,W.UINT]
        self.user.TranslateMessage.argtypes = [ctypes.POINTER(W.MSG)]
        self.user.DispatchMessageW.argtypes = [ctypes.POINTER(W.MSG)]
        self.user.DispatchMessageW.restype = W.LPARAM
        self.user.DestroyWindow.argtypes = [W.HWND]
        self.user.IsWindowVisible.argtypes = [W.HWND]
        self.user.GetSystemMenu.argtypes = [W.HWND,W.BOOL]; self.user.GetSystemMenu.restype = W.HMENU
        self.user.EnableMenuItem.argtypes = [W.HMENU,W.UINT,W.UINT]
        self.user.LoadImageW.argtypes = [W.HINSTANCE,W.LPCWSTR,W.UINT,ctypes.c_int,ctypes.c_int,W.UINT]
        self.user.LoadImageW.restype = W.HANDLE
        class Controls(ctypes.Structure):
            _fields_ = [('size',W.DWORD),('classes',W.DWORD)]
        comctl.InitCommonControlsEx(ctypes.byref(Controls(ctypes.sizeof(Controls), 0x20)))
        instance = kernel.GetModuleHandleW(None)
        create = self.user.CreateWindowExW
        self.hwnd = create(0, 'STATIC', 'MediaDownloader — Actualizando', 0x10C80000,
                           0x80000000-2**32, 0x80000000-2**32, 590, 185, None, None, instance, None)
        if not self.hwnd:
            raise OSError(ctypes.get_last_error(), 'No se pudo abrir el progreso de instalación')
        self.user.EnableMenuItem(self.user.GetSystemMenu(self.hwnd, False), 0xF060, 0x1)
        self.label = create(0,'STATIC','Preparando…',0x50000000,20,20,545,30,self.hwnd,None,instance,None)
        self.bar = create(0,'msctls_progress32','',0x50000008,20,60,545,24,self.hwnd,None,instance,None)
        create(0,'STATIC','No cierres el programa mientras se instala o recupera la versión.',0x50000000,
               20,102,545,24,self.hwnd,None,instance,None)
        if not self.label or not self.bar:
            self.close(); raise OSError('No se pudo crear la barra de instalación')
        icon_path = Path(root) / 'MediaDownloader.ico'
        for size, kind in [(32,1),(16,0)]:
            icon = self.user.LoadImageW(None,str(icon_path),1,size,size,0x10)
            if icon: self.user.SendMessageW(self.hwnd,0x80,kind,icon)
        self(-1, 'Preparando actualización…')

    def __call__(self, value, text):
        self.value, self.text = value, text
        if not self.hwnd: return
        self.user.SetWindowTextW(self.label, text)
        # Determinate values are per-stage. Unknown-duration phases use a marquee.
        style = self.user.GetWindowLongW(self.bar, -16)
        self.user.SetWindowLongW(self.bar, -16, style | 8 if value < 0 else style & ~8)
        if value < 0:
            self.user.SendMessageW(self.bar, 0x40A, 1, 35)
        else:
            self.user.SendMessageW(self.bar, 0x40A, 0, 0)
            self.user.SendMessageW(self.bar, 0x406, 0, 100)
            self.user.SendMessageW(self.bar, 0x402, max(0,min(100,value)), 0)
        self.pump()

    def pump(self):
        if not self.hwnd: return
        msg = W.MSG()
        while self.user.PeekMessageW(ctypes.byref(msg),None,0,0,1):
            self.user.TranslateMessage(ctypes.byref(msg)); self.user.DispatchMessageW(ctypes.byref(msg))

    def snapshot(self):
        if not self.hwnd: return {'visible':False, 'value':self.value, 'text':self.text, 'position':0}
        text = ctypes.create_unicode_buffer(2048)
        self.user.GetWindowTextW(self.label, text, len(text))
        return {'visible': bool(self.user.IsWindowVisible(self.hwnd)), 'value': self.value,
                'text':text.value, 'position':self.user.SendMessageW(self.bar,0x408,0,0)}

    def close(self):
        if self.hwnd:
            self.user.DestroyWindow(self.hwnd); self.hwnd = None


def choose_file(title, file_filter):
    """Native picker used only when the standalone repair helper is double-clicked."""
    class OpenFile(ctypes.Structure):
        _fields_ = [('size',W.DWORD),('owner',W.HWND),('instance',W.HINSTANCE),('filter',W.LPCWSTR),
                    ('custom',W.LPWSTR),('custom_size',W.DWORD),('index',W.DWORD),('file',W.LPWSTR),
                    ('max_file',W.DWORD),('file_title',W.LPWSTR),('max_title',W.DWORD),('initial',W.LPCWSTR),
                    ('title',W.LPCWSTR),('flags',W.DWORD),('offset',W.WORD),('extension',W.WORD),
                    ('default_ext',W.LPCWSTR),('data',W.LPARAM),('hook',ctypes.c_void_p),('template',W.LPCWSTR),
                    ('reserved',ctypes.c_void_p),('reserved_word',W.DWORD),('flags_ex',W.DWORD)]
    buffer = ctypes.create_unicode_buffer(32768)
    value = OpenFile(); value.size = ctypes.sizeof(OpenFile); value.filter = file_filter
    value.file = ctypes.cast(buffer,W.LPWSTR); value.max_file = len(buffer)
    value.title = title; value.flags = 0x81808
    dialog = ctypes.WinDLL('comdlg32',use_last_error=True)
    dialog.GetOpenFileNameW.argtypes = [ctypes.POINTER(OpenFile)]; dialog.GetOpenFileNameW.restype = W.BOOL
    return Path(buffer.value) if dialog.GetOpenFileNameW(ctypes.byref(value)) else None
