# INFRASTRUCTURE
import sqlite3
import ctypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from Foundation import NSBundle

from probe03_bridge import _LIBPROC

_TCC_DB = Path('~/Library/Application Support/com.apple.TCC/TCC.db').expanduser()

# FUNCTIONS

def _collect_context_diagnostics() -> Dict[str, Any]:
    own_pid    = os.getpid()
    parent_pid = os.getppid()
    rp = subprocess.run(['ps', '-p', str(parent_pid), '-o', 'comm='],
                        capture_output=True, text=True, timeout=3)
    parent_name = rp.stdout.strip() if rp.returncode == 0 else 'unknown'
    env_tcc = {k: os.environ.get(k)
               for k in ['__CFBundleIdentifier', 'XPC_SERVICE_NAME', 'LAUNCHD_SOCKET']}
    cs = subprocess.run(['codesign', '-dvvv', sys.executable],
                        capture_output=True, text=True, timeout=8)
    codesign_raw = (cs.stdout + cs.stderr).strip()
    codesign_id  = next(
        (l.split('=', 1)[1] for l in codesign_raw.splitlines() if l.startswith('Identifier=')),
        'unknown')
    bundle_id = NSBundle.mainBundle().bundleIdentifier()
    pv       = ctypes.c_int32(0)
    resp_pid = int(pv.value) if _LIBPROC.proc_pidinfo(
        own_pid, 58, 0, ctypes.byref(pv), ctypes.sizeof(pv)) > 0 else None
    resp_name = None
    if resp_pid is not None:
        r2 = subprocess.run(['ps', '-p', str(resp_pid), '-o', 'comm='],
                             capture_output=True, text=True, timeout=3)
        resp_name = r2.stdout.strip() if r2.returncode == 0 else 'unknown'
    return {
        'own_pid': own_pid, 'executable_path': sys.executable,
        'parent_pid': parent_pid, 'parent_name': parent_name,
        'env_tcc_relevant': env_tcc,
        'codesign_identity': codesign_id, 'codesign_raw': codesign_raw,
        'bundle_id_nsbundle': bundle_id,
        'responsible_pid': resp_pid, 'responsible_name': resp_name,
    }

def _collect_tcc_state() -> Dict[str, Any]:
    db_path = str(_TCC_DB)
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT service, client, auth_value FROM access "
            "WHERE service='kTCCServiceScreenCapture'"
        ).fetchall()
        conn.close()
        return {
            'db_path': db_path, 'readable': True,
            'screen_capture_rows': [{'service': r[0], 'client': r[1], 'auth_value': r[2]}
                                     for r in rows],
            'note': f'{len(rows)} rows found',
        }
    except Exception as e:
        return {'db_path': db_path, 'readable': False, 'screen_capture_rows': [],
                'note': f'unreadable: {e}'}
