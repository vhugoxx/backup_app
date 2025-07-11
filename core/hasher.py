from __future__ import annotations
from pathlib import Path
import hashlib

# ---- Configuração --------------------------------------------
_BUF_SIZE = 4 * 1024 * 1024   # 4 MiB por leitura: bom equilíbrio CPU/I/O
_DEFAULT_ALGO = "sha256"
# --------------------------------------------------------------


def _hash_file(path: Path, algo_name: str) -> str:
    """Devolve o digest hexadecimal do ficheiro usando o algoritmo pedido."""
    h = hashlib.new(algo_name)
    with path.open("rb") as f:
        while True:
            chunk = f.read(_BUF_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def file_hash(path: str | Path, algo: str = _DEFAULT_ALGO) -> str:
    """
    Hash genérico: calcula o *digest* hexadecimal de `path`
    com o algoritmo indicado (sha256 por omissão).
    """
    return _hash_file(Path(path), algo)


# -- compatibilidade antiga ------------------------------------
def sha256(path: str | Path) -> str:
    """
    API antiga usada por outros módulos (core.runner, etc.).
    Equivale a `file_hash(path, "sha256")`.
    """
    return _hash_file(Path(path), "sha256")
# --------------------------------------------------------------


__all__ = ["file_hash", "sha256"]
