"""Windows user-scoped encrypted storage for the Firebase refresh token."""
import ctypes
from ctypes import wintypes


class DataBlob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.c_void_p)]


def protect(data, decrypt=False):
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32')
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                          wintypes.DWORD, ctypes.POINTER(DataBlob)]
    operation.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    source = DataBlob(len(data), ctypes.addressof(buffer))
    result = DataBlob()
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


class AccountStore:
    def __init__(self, path):
        self.path = path

    def load(self):
        with self.path.open('rb') as file:
            encrypted = file.read(65537)
        if not encrypted or len(encrypted) > 65536:
            raise ValueError('Invalid saved session')
        return protect(encrypted, decrypt=True).decode('utf-8')

    def save(self, token):
        encrypted = protect(token.encode('utf-8'))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_suffix('.tmp')
        try:
            pending.write_bytes(encrypted)
            pending.replace(self.path)
        finally:
            pending.unlink(missing_ok=True)

    def clear(self):
        self.path.unlink(missing_ok=True)
