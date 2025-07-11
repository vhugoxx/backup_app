"""
runner.py  –  Função de alto-nível cli_run()
===========================================

• Coordena Scanner → Copier → BackupLog  
• Pode ser usado pela CLI ou pela GUI (através de callbacks).  
• Devolve tuplo (ok: bool, log_path: pathlib.Path)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Any

from .scanner import Scanner
from .copier  import Copier
from .logger  import BackupLog


# --------------------------------------------------------------------------- #
#                               TIPO DE CALLBACKS                             #
# --------------------------------------------------------------------------- #
ProgressCb = Callable[[int, int], Any]   # current, total
LogCb      = Callable[[str], Any]        # linha texto


# --------------------------------------------------------------------------- #
#                                 FUNÇÃO PÚBLICA                              #
# --------------------------------------------------------------------------- #
def cli_run(
    src: str | Path,
    dst: str | Path,
    exts: list[str],
    recursive: bool = True,
    preserve_tree: bool = True,
    callbacks: dict[str, Callable] | None = None,
) -> tuple[bool, Path | None]:
    """
    Parameters
    ----------
    src            : origem
    dst            : destino
    exts           : lista de extensões (sem ponto) a copiar
    recursive      : percorre sub-pastas?
    preserve_tree  : mantém estrutura relativa?
    callbacks      : {"progress": ProgressCb, "log": LogCb}

    Returns
    -------
    (ok, log_path)
    """
    src = Path(src)
    dst = Path(dst)
    cb_progress: ProgressCb | None = None
    cb_log:      LogCb | None      = None
    if callbacks:
        cb_progress = callbacks.get("progress")
        cb_log      = callbacks.get("log")

    t0 = time.time()
    try:
        # ---------------------------------------------------- enumerar ficheiros
        scanner   = Scanner(src, exts, recursive)
        file_list = list(scanner.scan())
        total     = len(file_list)
        if cb_log:
            cb_log(f"Encontrados {total} ficheiro(s). A copiar…")

        bytes_total = sum(f.stat().st_size for f in file_list)
        copied_ok   = 0
        failed      = 0
        bytes_done  = 0

        # ---------------------------------------------------- preparar log/copier
        log = BackupLog(src, dst, exts)
        log.set_bytes_total(bytes_total)
        copier = Copier(dst, log)

        # ---------------------------------------------------- ciclo de cópia
        for idx, f in enumerate(file_list, 1):
            # construir caminho relativo DEST/EXT/…  (ex.: dst/jpg/…)
            rel = f.relative_to(src) if preserve_tree else f.name
            rel = Path(rel)
            rel = Path(f.suffix.lstrip(".").lower()) / rel

            ok, sz, _ = copier.copy(f, rel)
            if ok:
                copied_ok += 1
                bytes_done += sz
            else:
                failed += 1

            if cb_progress:
                cb_progress(idx, total)

        # ---------------------------------------------------- finalizar
        duration_sec = time.time() - t0
        log_path     = log.close(copied_ok, failed, bytes_total, duration_sec)
        ok_final     = failed == 0
        if cb_log:
            cb_log("[green]Backup concluído![/green]" if ok_final
                   else f"[yellow]Concluído com {failed} erro(s)[/yellow]")

        return ok_final, log_path

    except Exception as exc:  # noqa: BLE001
        # erro fatal
        if cb_log:
            cb_log(f"[red]ERRO FATAL: {exc}[/red]")
        return False, None
