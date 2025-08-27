from pathlib import Path
import hashlib

def file_hash(path: Path, algo: str = "sha256") -> str:
    """Calcula o hash de um ficheiro (default SHA-256)."""
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
