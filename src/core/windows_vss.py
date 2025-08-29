from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class VssSnapshot:
    shadow_id: str
    shadow_volume: str  # ex: r"\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy12"


_VSS_ID_RE = re.compile(r"Shadow Copy ID:\s*({[0-9A-Fa-f\-]+})")
_VSS_VOL_RE = re.compile(r"Shadow Copy Volume:\s*(.+)")


def _run(cmd: list[str]) -> str:
    # Devolve stdout como string (mesmo em erro, devolve o que houver)
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, shell=False)
        return out
    except subprocess.CalledProcessError as exc:
        return exc.output or ""


def check_vss_status(drive_letter: str = "D:") -> tuple[bool, str]:
    """Verifica pré-requisitos do VSS para um dado volume.

    Devolve um par (ok, mensagem).
    """
    # 1) Privilégios de administrador
    try:
        import ctypes
        if not bool(ctypes.windll.shell32.IsUserAnAdmin()):
            return False, "Sem privilégios de administrador."
    except Exception:
        return False, "Não foi possível verificar privilégios (provável: não é Windows/sem ctypes)."

    # 2) Serviço VSS
    r = subprocess.run(["sc", "query", "vss"], capture_output=True, text=True, shell=False)
    out = (r.stdout or "") + (r.stderr or "")
    if "STATE" not in out:
        return False, "Serviço VSS indisponível."
    if "STOPPED" in out:
        return False, "Serviço VSS desativado."
    if "RUNNING" not in out:
        return False, "Serviço VSS em estado desconhecido."

    # 3) Volume elegível
    r = subprocess.run(["vssadmin", "list", "volumes"], capture_output=True, text=True, shell=False)
    if drive_letter.rstrip("\\") not in (r.stdout or ""):
        return False, f"Volume {drive_letter} não elegível para VSS."

    # 4) Sistema de ficheiros NTFS?
    r = subprocess.run(["fsutil", "fsinfo", "volumeinfo", drive_letter], capture_output=True, text=True, shell=False)
    if "File System Name" in (r.stdout or ""):
        for line in r.stdout.splitlines():
            if "File System Name" in line:
                fs = line.split(":", 1)[1].strip()
                if fs.upper() != "NTFS":
                    return False, f"Volume {drive_letter} não suportado por VSS (FS={fs})."
                break

    return True, "VSS OK (admin, serviço ativo, volume elegível NTFS)."


def create_snapshot(drive_letter: str, log_cb=None) -> Optional[VssSnapshot]:
    """
    Tenta criar um snapshot VSS do volume indicado (ex: 'D:').
    Em sucesso, devolve VssSnapshot. Em falha, devolve None (sem levantar exceção).
    """
    if os.name != "nt":
        if log_cb:
            log_cb("ℹ️ VSS só está disponível no Windows; a continuar sem snapshot.")
        return None

    drive = drive_letter.rstrip("\\/")
    if not drive.endswith(":"):
        drive = drive + ":"

    # Criação
    if log_cb:
        log_cb(f"A criar snapshot VSS para {drive} ...")

    out = _run(["vssadmin", "create", "shadow", f"/for={drive}"])
    # Sucesso típico contém “Shadow Copy ID:” e “Shadow Copy Volume:”
    m_id = _VSS_ID_RE.search(out or "")
    m_vol = _VSS_VOL_RE.search(out or "")

    if not (m_id and m_vol):
        if log_cb:
            log_cb("⚠️  Não foi possível criar snapshot VSS (sem privilégios de admin, serviço VSS desativado, "
                   "ou volume não suportado). A continuar sem VSS.")
            if out:
                log_cb(out.strip())
        return None

    snap = VssSnapshot(shadow_id=m_id.group(1), shadow_volume=m_vol.group(1).strip())
    if log_cb:
        log_cb(f"Snapshot criado: {snap.shadow_id} em {snap.shadow_volume}")
    return snap


def delete_snapshot(snap: Optional[VssSnapshot], log_cb=None) -> None:
    """Apaga o snapshot se existir. Ignora erros."""
    if not snap:
        return
    if os.name != "nt":
        return
    if log_cb:
        log_cb(f"A apagar snapshot VSS {snap.shadow_id} ...")
    _run(["vssadmin", "delete", "shadows", f"/shadow={snap.shadow_id}", "/quiet"])
