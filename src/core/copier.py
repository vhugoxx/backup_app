from __future__ import annotations

import io
import os
import shutil
from pathlib import Path
from typing import Callable, Iterable, Optional

from .windows_vss import create_snapshot, delete_snapshot, VssSnapshot
from .extractor import is_archive, iterate_archive
from .scanner import scan


def _emit(cb: Optional[Callable[[str], None]], msg: str) -> None:
    try:
        if cb:
            cb(msg)
    except Exception:
        pass


def _progress(cb: Optional[Callable[[int], None]], val: int) -> None:
    try:
        if cb:
            cb(val)
    except Exception:
        pass


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _dst_from_src(src: Path, base_src: Path, base_dst: Path, preserve_structure: bool, ext_folder: str) -> Path:
    """
    Calcula destino final. Se preserve_structure=True, mantém subpastas a partir de base_src,
    mas sempre dentro de uma pasta de extensão (ex: 'jpg', 'pdf').
    """
    rel = src.relative_to(base_src) if preserve_structure else src.name
    if isinstance(rel, str):
        rel_parts = [rel]
    else:
        rel_parts = list(rel.parts)
    # Garante a pasta da extensão como primeiro nível
    path = base_dst / ext_folder
    for part in rel_parts[:-1]:
        path = path / part
    filename = rel_parts[-1] if rel_parts else src.name
    return path / filename


def copy_selected(
    src: str | os.PathLike,
    dst: str | os.PathLike,
    extensions: set[str],
    recursive: bool = True,
    preserve_structure: bool = True,
    include_archives: bool = False,
    archive_types: set[str] | None = None,
    use_vss: bool = False,
    progress_cb: Optional[Callable[[int], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    stop_flag: Optional[Callable[[], bool]] = None,
    stats: Optional[dict] = None,
) -> None:
    """
    Executa o backup seletivo. Se VSS falhar, continua sem VSS.
    """
    base_src = Path(src)
    base_dst = Path(dst)
    base_dst.mkdir(parents=True, exist_ok=True)

    if stats is None:
        stats = {}
    stats.update(
        files_scanned=0,
        files_found=0,
        files_copied=0,
        files_denied=0,
        mb_scanned=0.0,
        mb_copied=0.0,
    )

    if stop_flag is None:
        stop_flag = lambda: False  # noqa: E731

    # --- Tentar VSS (Windows) ---
    snap: Optional[VssSnapshot] = None
    if use_vss and os.name == "nt":
        # extrai letra da drive, p.ex. 'D:'
        drive = base_src.drive or (str(base_src)[:2] if ":" in str(base_src) else "")
        snap = create_snapshot(drive, log_cb=log_cb)
        if not snap:
            _emit(log_cb, "➡️  A continuar sem VSS.")
    else:
        if use_vss:
            _emit(log_cb, "ℹ️ VSS não disponível neste sistema; a continuar sem VSS.")

    def scan_source() -> Iterable[Path]:
        return scan(root=base_src, extensions=extensions, recursive=recursive, log_cb=log_cb)

    try:
        # --- Fase 1: scan + cópia de ficheiros normais ---
        for path in scan_source():
            if stop_flag():
                _emit(log_cb, "⏹️  Operação cancelada.")
                break

            stats["files_scanned"] += 1
            try:
                size_mb = (path.stat().st_size or 0) / (1024 * 1024)
                stats["mb_scanned"] += size_mb
            except Exception:
                pass

            # Encontrado ficheiro com extensão pretendida
            stats["files_found"] += 1
            ext_folder = path.suffix.lstrip(".").lower() or "_sem_ext"
            dst_path = _dst_from_src(path, base_src, base_dst, preserve_structure, ext_folder)
            try:
                _ensure_dir(dst_path)
                shutil.copy2(path, dst_path)
                stats["files_copied"] += 1
                try:
                    stats["mb_copied"] += (dst_path.stat().st_size or 0) / (1024 * 1024)
                except Exception:
                    pass
                _emit(log_cb, f"✔ Copiado: {path} -> {dst_path}")
            except PermissionError as e:
                stats["files_denied"] += 1
                _emit(log_cb, f"⚠️  Sem acesso: {path} ({e})")
            except Exception as e:
                _emit(log_cb, f"❌ Erro ao copiar {path}: {e}")

            _progress(progress_cb, 1)

        # --- Fase 2: processar arquivos (zip/rar/7z/tar) se pedido ---
        if include_archives:
            _emit(log_cb, "— A procurar dentro de ficheiros compactados…")
            for path in scan(
                root=base_src,
                extensions=archive_types or set(),
                recursive=recursive,
                log_cb=log_cb,
                treat_missing_as_warning=True,
            ):
                if stop_flag():
                    break
                if not is_archive(path, archive_types):
                    continue
                try:
                    for inner_name, stream in iterate_archive(path, extensions):
                        # Monta destino: pasta = extensão do ficheiro interno
                        inner_ext = Path(inner_name).suffix.lstrip(".").lower() or "_sem_ext"
                        dst_path = _dst_from_src(
                            path.parent / inner_name,
                            base_src,
                            base_dst,
                            preserve_structure,
                            inner_ext,
                        )
                        _ensure_dir(dst_path)
                        with open(dst_path, "wb") as fh:
                            shutil.copyfileobj(stream, fh)
                        stats["files_copied"] += 1
                        try:
                            stats["mb_copied"] += (dst_path.stat().st_size or 0) / (1024 * 1024)
                        except Exception:
                            pass
                        _emit(log_cb, f"✔ Extraído: {path}!{inner_name} -> {dst_path}")
                        _progress(progress_cb, 1)
                except Exception as e:
                    _emit(log_cb, f"❌ Erro ao extrair {path}: {e}")
    finally:
        delete_snapshot(snap, log_cb=log_cb)
