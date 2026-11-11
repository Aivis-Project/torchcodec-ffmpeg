"""List the shared libraries loaded into the current process.

Used by the tests and by the app the PyInstaller test freezes.
"""

import ctypes
import sys
from pathlib import Path


def loaded_libraries() -> list[str]:
    """Paths of the shared libraries loaded into this process."""
    if sys.platform == "win32":
        psapi = ctypes.WinDLL("psapi")
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        process = kernel32.GetCurrentProcess()
        modules = (ctypes.c_void_p * 4096)()
        needed = ctypes.c_ulong()
        psapi.EnumProcessModules(
            ctypes.c_void_p(process),
            modules,
            ctypes.sizeof(modules),
            ctypes.byref(needed),
        )
        paths: list[str] = []
        for module in modules[: needed.value // ctypes.sizeof(ctypes.c_void_p)]:
            buffer = ctypes.create_unicode_buffer(32768)
            psapi.GetModuleFileNameExW(
                ctypes.c_void_p(process), ctypes.c_void_p(module), buffer, 32768
            )
            paths.append(buffer.value)
        return paths
    if sys.platform == "darwin":
        dyld = ctypes.CDLL(None)
        dyld._dyld_get_image_name.restype = ctypes.c_char_p
        return [
            dyld._dyld_get_image_name(index).decode()
            for index in range(dyld._dyld_image_count())
        ]
    maps = Path("/proc/self/maps").read_text()
    return [line.split()[-1] for line in maps.splitlines() if "/" in line]
