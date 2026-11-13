# -*- coding: utf-8 -*-
"""Diagnostic macOS (temporaire, V0.9.4.6), chargé par le workflow
« Diagnostic macOS » seulement (``-p varians_macos_probe``).

Après chaque test : un QProcess de contrôle doit annoncer sa fin (comme
celui de la vérification F8), et le gestionnaire de SIGCHLD est relevé
(bibliothèque et fonction, par ``sigaction`` et ``dladdr``). Au premier test
après lequel la fin n'arrive plus, la passe s'arrête en disant ce qu'elle a
vu. Il sera retiré avec le workflow."""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys

import pytest

_last = {"owner": None}


class _Sigaction(ctypes.Structure):
    # Le gestionnaire est en tête sous macOS comme sous Linux ; la réserve
    # couvre la structure plus grande de Linux.
    _fields_ = [("handler", ctypes.c_void_p), ("mask", ctypes.c_uint32), ("flags", ctypes.c_int),
                ("reserve", ctypes.c_char * 256)]


class _DlInfo(ctypes.Structure):
    _fields_ = [("fname", ctypes.c_char_p), ("fbase", ctypes.c_void_p),
                ("sname", ctypes.c_char_p), ("saddr", ctypes.c_void_p)]


def _sigchld_owner():
    libc = ctypes.CDLL(None)
    action = _Sigaction()
    if libc.sigaction(signal.SIGCHLD, None, ctypes.byref(action)) != 0:
        return "sigaction: échec"
    handler = action.handler or 0
    if handler in (0, 1):
        return ("SIG_DFL", "SIG_IGN")[handler]
    info = _DlInfo()
    libc.dladdr.argtypes = [ctypes.c_void_p, ctypes.POINTER(_DlInfo)]
    if libc.dladdr(ctypes.c_void_p(handler), ctypes.byref(info)):
        library = os.path.basename((info.fname or b"?").decode(errors="replace"))
        return f"{library}:{(info.sname or b'?').decode(errors='replace')} flags={action.flags:#x}"
    return hex(handler)


def _process_finishes():
    """Vrai si un QProcess de contrôle annonce sa fin dans les 15 s."""
    from PySide6.QtCore import QCoreApplication, QEventLoop, QProcess, QTimer
    if QCoreApplication.instance() is None:
        return True, "pas d'application"
    process = QProcess()
    loop = QEventLoop()
    seen = []
    process.finished.connect(lambda *args: (seen.append(("finished", args)), loop.quit()))
    process.errorOccurred.connect(lambda error: (seen.append(("error", error)), loop.quit()))
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(15_000)
    process.start(sys.executable, ["-c", "pass"])
    if not seen:
        loop.exec()
    timer.stop()
    if seen:
        return True, repr(seen[0])
    state = process.state()
    waited = process.waitForFinished(3000)
    return False, f"état {state}, waitForFinished(3 s) {waited}, état ensuite {process.state()}"


def _situation():
    lines = [f"SIGCHLD : {_sigchld_owner()}"]
    try:
        import resource
        lines.append(f"RLIMIT_NOFILE : {resource.getrlimit(resource.RLIMIT_NOFILE)}, "
                     f"RLIMIT_NPROC : {resource.getrlimit(resource.RLIMIT_NPROC)}")
    except (ImportError, ValueError, OSError) as exc:
        lines.append(f"limites : {exc}")
    try:
        lines.append(f"descripteurs ouverts : {len(os.listdir('/dev/fd'))}")
    except OSError as exc:
        lines.append(f"descripteurs : {exc}")
    try:
        listing = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,pgid=,stat=,etime=,command="],
                                 capture_output=True, text=True, timeout=10).stdout
        mine = [line for line in listing.splitlines()
                if len(line.split()) > 2 and (line.split()[1] == str(os.getpid())
                                              or line.split()[2] == str(os.getpgrp()))]
        lines.append(f"processus enfants ou du groupe ({len(mine)}) :\n" + "\n".join(line[:220] for line in mine))
    except (OSError, subprocess.SubprocessError) as exc:
        lines.append(f"processus : {exc}")
    return "\n".join(lines)


def pytest_sessionstart(session):
    print(f"\n[sonde] début : SIGCHLD {_sigchld_owner()}", flush=True)


def pytest_runtest_logfinish(nodeid, location):
    owner = _sigchld_owner()
    if owner != _last["owner"]:
        print(f"\n[sonde] après {nodeid} : SIGCHLD {owner}", flush=True)
        _last["owner"] = owner
    ok, detail = _process_finishes()
    if not ok:
        print(f"\n[sonde] LA FIN D'UN QPROCESS N'ARRIVE PLUS après {nodeid}\n{detail}\n{_situation()}", flush=True)
        pytest.exit(f"QProcess.finished n'arrive plus après {nodeid}", returncode=3)
