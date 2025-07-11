"""
Copier
======

Responsável por copiar um ficheiro (src) para o destino base,
preservando a sub-estrutura relativa que já vem calculada
(rel_path).  Reporta cada sucesso/erro ao BackupLog.
"""

from __future__ import annotations
from pathlib import Path
import shutil


class Copier:
    def __init__(self, dest_root: Path, log) -> None:
        self.dest_root = Path(dest_root)
        self.dest_root.mkdir(parents=True, exist_ok=True)
        self.log = log

    # ------------------------------------------------------------------ copy
    def copy(self, src: Path, rel_path: Path) -> tuple[bool, int, Path]:
        """
        Parameters
        ----------
        src       : Path   ficheiro original
        rel_path  : Path   caminho relativo calculado pelo Scanner

        Returns
        -------
        ok        : bool          True se copiado com sucesso
        size      : int           bytes copiados (0 se falha)
        dst_path  : Path | None   caminho final de destino
        """
        dst_path = self.dest_root / rel_path
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst_path)
            size = src.stat().st_size
            # registo
            if self.log:
                self.log.add_copied(str(src), str(dst_path), size)
            return True, size, dst_path
        except Exception as exc:  # noqa: BLE001
            if self.log:
                self.log.add_error(str(src), str(dst_path), str(exc))
            return False, 0, dst_path
