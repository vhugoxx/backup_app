from __future__ import annotations

# Tenta ativar privilégios de backup/restauro (SeBackupPrivilege/SeRestorePrivilege)
# Isto é opcional e requer pywin32; se não existir, a função devolve False silenciosamente.

try:
    import win32con, win32api, win32security  # type: ignore
    _HAVE = True
except Exception:
    _HAVE = False

def try_enable_backup_privileges() -> bool:
    if not _HAVE:
        return False
    try:
        hProcess = win32api.GetCurrentProcess()
        hToken = win32security.OpenProcessToken(
            hProcess,
            win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
        )
        for name in ("SeBackupPrivilege", "SeRestorePrivilege"):
            luid = win32security.LookupPrivilegeValue(None, name)
            win32security.AdjustTokenPrivileges(
                hToken, False, [(luid, win32con.SE_PRIVILEGE_ENABLED)]
            )
        return True
    except Exception:
        return False
