from pathlib import Path
from typing import Iterable, Iterator

ARCH_MAP = {
    "zip": {".zip"},
    "tar": {".tar", ".tgz", ".tar.gz", ".tbz2", ".tar.bz2"},
    "rar": {".rar"},
    "7z":  {".7z"}
}

def scan(
    root: Path,
    extensions: Iterable[str],
    recursive: bool = True,
    archives: bool = False,
    arch_types: Iterable[str] | None = None
) -> Iterator[Path]:
    exts = {e.lower().lstrip(".") for e in extensions}
    arch_exts = set().union(*[ARCH_MAP.get(a, set()) for a in arch_types or []])

    if not recursive:
        yield from _scan_dir(root, exts, archives, arch_exts)
        return

    for sub in _walk_dir(root):
        yield from _scan_dir(sub, exts, archives, arch_exts)

def _walk_dir(root: Path):
    # Caminha recursivamente, ignora erros ao entrar em subpastas
    stack = [root]
    while stack:
        curr = stack.pop()
        try:
            yield curr
            for entry in curr.iterdir():
                if entry.is_dir():
                    stack.append(entry)
        except Exception as e:
            print(f"⚠️  Erro ao entrar em {curr}: {e}")

def _scan_dir(src: Path, exts, archives, arch_exts):
    try:
        for entry in src.iterdir():
            try:
                if entry.is_file():
                    suf = entry.suffix.lower()
                    if suf.lstrip(".") in exts:
                        yield entry
                    elif archives and suf in arch_exts:
                        yield entry
            except Exception as e:
                print(f"⚠️  Erro ao processar {entry}: {e}")
    except Exception as e:
        print(f"⚠️  Erro ao listar {src}: {e}")
