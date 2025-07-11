from __future__ import annotations
from pathlib import Path
import hashlib

BUF_SIZE = 4 * 1024 * 1024          # 4 MiB — bom equilíbrio CPU-I/O


def file_hash(path: str | Path, algo: str = "sha256") -> str:
    """
    Calcula o hash hexadecimal de `path` usando o algoritmo indicado
    (sha256 por omissão).  Lê o ficheiro em blocos para não consumir
    muita RAM com ficheiros grandes.
    """
    p = Path(path)
    h = hashlib.new(algo)

    with p.open("rb") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            h.update(data)

    return h.hexdigest()
