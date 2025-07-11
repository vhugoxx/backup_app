"""
BackupLog
=========

• Cria um ficheiro JSON (nome inclui timestamp UTC) dentro da pasta de
  destino do backup.  
• Guarda estatísticas globais + listas de ficheiros copiados e com erro.  
• `close()` actualiza campos finais, grava no disco e devolve o caminho.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import json


class BackupLog:
    # -------------------------------------------------------------- construtor
    def __init__(self, src: Path, dest: Path, types: list[str]) -> None:
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)

        stamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        self.path = dest / f"backup_log_{stamp}.json"

        self.data: dict = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
            "source": str(src),
            "dest": str(dest),
            "types": types,
            "copied_ok": 0,
            "failed": 0,
            "bytes_copied": 0,
            "bytes_total": 0,
            "duration_sec": 0.0,
            "duration": "0:00:00",
            # listas p/ registar cada ficheiro
            "copied": [],          # [{"src": "...", "dst": "...", "size": 1234}]
            "errors": [],          # [{"src": "...", "dst": "...", "error": "..."}]
        }

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _human_bytes(n: int) -> str:
        return f"{n / (1<<30):.1f} GB" if n >= 1 << 30 else f"{n / (1<<20):.1f} MB"

    # -------------------------------------------------------------- API p/ Copier
    def add_copied(self, src: str, dst: str, size: int) -> None:
        self.data["copied"].append({"src": src, "dst": dst, "size": size})
        self.data["copied_ok"] += 1
        self.data["bytes_copied"] += size

    def add_error(self, src: str, dst: str, error_msg: str) -> None:
        self.data["errors"].append({"src": src, "dst": dst, "error": error_msg})
        self.data["failed"] += 1

    # permitir que o runner actualize o total previsto
    def set_bytes_total(self, total: int) -> None:
        self.data["bytes_total"] = total

    # -------------------------------------------------------------- fechar / gravar
    def close(
        self,
        copied_ok: int,
        failed: int,
        bytes_total: int,
        duration_sec: float,
    ) -> Path:
        self.data.update(
            copied_ok=copied_ok,
            failed=failed,
            bytes_total=bytes_total,
            duration_sec=round(duration_sec, 2),
            duration=str(timedelta(seconds=int(duration_sec))),
            copied_mb=self._human_bytes(self.data["bytes_copied"]),
            total_mb=self._human_bytes(bytes_total),
        )

        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, ensure_ascii=False)

        return self.path
