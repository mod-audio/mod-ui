# SPDX-FileCopyrightText: 2026 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""What "Report a problem" can say about the computer mod-ui runs on.

Only used where mod-ui runs on a user's own computer (MOD Desktop): a MOD device
has a hardware descriptor, a release file and a controller, a computer has none
of them. Standard library only, every probe is best effort and returns None when
it cannot answer. Nothing here identifies the user: no hostname, no serial, and
the home folder is replaced by "~" in anything copied from a log.
"""

import os
import platform
import re
import subprocess
import sys

LOG_LINES = 12
JACKD_LINE = re.compile(r'Starting jackd using:\s*(.*)$')
PROBLEM_LINE = re.compile(r'error|fail|invalid|unable|cannot|can\'t|xrun|warning|critical', re.I)


def _run(args):
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=3).stdout
        return out.strip() or None
    except Exception:
        return None


def _read(path):
    try:
        with open(path, 'r') as fh:
            return fh.read()
    except (IOError, OSError):
        return None


def os_name():
    system = platform.system()
    if system == 'Darwin':
        return "macOS %s (%s)" % (platform.mac_ver()[0] or '?', platform.machine())
    if system == 'Windows':
        # platform.release() says "10" on Windows 11; the build number tells them apart
        build = 0
        try:
            build = int(platform.version().split('.')[2])
        except (IndexError, ValueError):
            pass
        return "Windows %s (build %s, %s)" % ('11' if build >= 22000 else platform.release(),
                                              platform.version(), platform.machine())
    if system == 'Linux':
        name = None
        for line in (_read('/etc/os-release') or '').splitlines():
            if line.startswith('PRETTY_NAME='):
                name = line.split('=', 1)[1].strip().strip('"')
        return "%s (kernel %s, %s)" % (name or 'Linux', platform.release(), platform.machine())
    return "%s %s (%s)" % (system, platform.release(), platform.machine())


def cpu_name():
    system = platform.system()
    name = None
    if system == 'Windows':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
        except Exception:
            name = None
    elif system == 'Darwin':
        name = _run(['sysctl', '-n', 'machdep.cpu.brand_string'])
    elif system == 'Linux':
        for line in (_read('/proc/cpuinfo') or '').splitlines():
            if line.startswith('model name'):
                name = line.split(':', 1)[1].strip()
                break
    name = re.sub(r'\s+', ' ', name or platform.processor() or '').strip()
    cores = os.cpu_count()
    if not name:
        return None
    return "%s, %s threads" % (name, cores) if cores else name


def memory_gb():
    total = None
    system = platform.system()
    try:
        if system == 'Windows':
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = stat.ullTotalPhys
        elif system == 'Darwin':
            total = int(_run(['sysctl', '-n', 'hw.memsize']) or 0) or None
        elif system == 'Linux':
            for line in (_read('/proc/meminfo') or '').splitlines():
                if line.startswith('MemTotal:'):
                    total = int(line.split()[1]) * 1024
                    break
    except Exception:
        total = None
    return round(total / (1024 ** 3), 1) if total else None


def uptime_seconds():
    system = platform.system()
    try:
        if system == 'Windows':
            import ctypes
            return int(ctypes.windll.kernel32.GetTickCount64() / 1000)
        if system == 'Darwin':
            m = re.search(r'sec = (\d+)', _run(['sysctl', '-n', 'kern.boottime']) or '')
            if m:
                import time
                return int(time.time()) - int(m.group(1))
        if system == 'Linux':
            return int(float((_read('/proc/uptime') or '').split()[0]))
    except Exception:
        pass
    return None


def _scrub(text, home):
    if home:
        text = text.replace(home, '~').replace(home.replace('\\', '/'), '~')
    return text


def launcher_log(directories, home):
    """The audio setup the launcher started and its latest problem lines.

    directories: folders that may hold launcher.log. Returns None when there is none.
    """
    for directory in directories:
        content = _read(os.path.join(directory, 'launcher.log'))
        if content:
            break
    else:
        return None

    lines = content.splitlines()
    jackd = None
    for line in lines:
        m = JACKD_LINE.search(line)
        if m:
            jackd = m.group(1).strip()
    # only what happened since the last start, so an old session cannot mislead
    start = max([i for i, line in enumerate(lines) if JACKD_LINE.search(line)] or [0])
    problems = [l for l in lines[start:] if PROBLEM_LINE.search(l)][-LOG_LINES:]
    return {
        "jackd": _scrub(jackd, home) if jackd else None,
        "problems": [_scrub(re.sub(r'\x1b\[[0-9;]*m', '', l), home) for l in problems],
        "path": _scrub(os.path.join(directory, 'launcher.log'), home),
    }


def collect(log_directories, home=None):
    home = home or os.path.expanduser('~')
    return {
        "os": os_name(),
        "cpu": cpu_name(),
        "memory_gb": memory_gb(),
        "uptime": uptime_seconds(),
        "python": sys.version.split()[0],
        "launcher": launcher_log(log_directories, home),
    }
