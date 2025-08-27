from pathlib import Path
from typing import Iterable, Iterator, Tuple
import io, zipfile, tarfile

def iterate_archive(path: Path, extensions: Iterable[str]) -> Iterator[Tuple[str, io.BufferedReader]]:
    """Gera (nome_relativo, stream) para cada ficheiro interno pretendido."""
    want = {e.lower().lstrip(".") for e in extensions}
    suf  = path.suffix.lower()

    if suf == ".zip":
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                if Path(info.filename).suffix.lower().lstrip(".") in want:
                    with z.open(info) as f:
                        yield info.filename, io.BytesIO(f.read())

    elif suf in {".tar", ".tgz", ".tar.gz", ".tbz2", ".tar.bz2"}:
        with tarfile.open(path, "r:*") as t:
            for m in t.getmembers():
                if not m.isfile(): continue
                if Path(m.name).suffix.lower().lstrip(".") in want:
                    f = t.extractfile(m)
                    if f:
                        yield m.name, io.BytesIO(f.read())

    elif suf == ".rar":
        import rarfile            # pip install rarfile
        with rarfile.RarFile(path) as r:
            for info in r.infolist():
                if Path(info.filename).suffix.lower().lstrip(".") in want:
                    with r.open(info) as f:
                        yield info.filename, io.BytesIO(f.read())

    # -------- 7-Zip --------------------------------------------------
    elif suf == ".7z":
        try:
            import py7zr            # pip install py7zr
        except ImportError:
            return                  # lib ausente → ignora este arquivo

        with py7zr.SevenZipFile(path, mode="r") as z:
            try:                                # versões < 1.0
                for name, bio in z.readall().items():
                    if Path(name).suffix.lower().lstrip(".") in want:
                        yield name, bio
            except AttributeError:              # versões ≥ 1.0
                for name in z.getnames():
                    if Path(name).suffix.lower().lstrip(".") not in want:
                        continue
                    # read() devolve dict {nome: BytesIO}
                    bio = z.read([name])[name]
                    yield name, bio

