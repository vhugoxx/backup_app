from __future__ import annotations

import io
import os
import shutil
from pathlib import Path
from typing import Callable, Iterable, Optional

from .windows_vss import create_snapshot, delete_snapshot, VssSnapshot, check_vss_status
from .extractor import is_archive, iterate_archive
from .scanner import scan
from .hasher import file_hash


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


def _resolve_conflict(path: Path) -> Path:
    """Gera um caminho único caso o destino já exista."""
    base = path.stem
    suffix = path.suffix
    counter = 1
    new_path = path
    while new_path.exists():
        new_path = path.with_name(f"{base}_{counter}{suffix}")
        counter += 1
    return new_path


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
        ext_counts={},
        ext_sizes={},

        vss={"usado": False, "motivo": "não solicitado"},

        vss={"requested": use_vss, "success": False, "reason": None},

    )

    if stop_flag is None:
        stop_flag = lambda: False  # noqa: E731

    # --- Tentar VSS (Windows) ---
    snap: Optional[VssSnapshot] = None

    if use_vss:
        if os.name == "nt":
            drive = base_src.drive or (str(base_src)[:2] if ":" in str(base_src) else "")
            ok, msg = check_vss_status(drive)
            if not ok:
                _emit(log_cb, f"⚠️ VSS indisponível: {msg}")
                stats["vss"] = {"usado": False, "motivo": msg}
            else:
                snap = create_snapshot(drive, log_cb=log_cb)
                if snap:
                    stats["vss"] = {"usado": True, "motivo": ""}
                else:
                    stats["vss"] = {"usado": False, "motivo": "Falha ao criar snapshot"}
                    _emit(log_cb, "➡️  A continuar sem VSS.")
        else:
            msg = "VSS não disponível neste sistema"
            _emit(log_cb, f"ℹ️ {msg}; a continuar sem VSS.")
            stats["vss"] = {"usado": False, "motivo": msg}

    if use_vss and os.name == "nt":
        # extrai letra da drive, p.ex. 'D:'
        drive = base_src.drive or (str(base_src)[:2] if ":" in str(base_src) else "")
        snap, err = create_snapshot(drive, log_cb=log_cb)
        stats["vss"]["success"] = snap is not None
        stats["vss"]["reason"] = err
        if not snap:
            _emit(log_cb, "➡️  A continuar sem VSS.")
    else:
        if use_vss:
            stats["vss"]["reason"] = "VSS não disponível neste sistema"
            _emit(log_cb, "ℹ️ VSS não disponível neste sistema; a continuar sem VSS.")


    def scan_source() -> Iterable[Path]:
        return scan(root=base_src, extensions=extensions, recursive=recursive, log_cb=log_cb)

    try:
        processed = 0
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
                copy_this = True
                if dst_path.exists():
                    try:
                        if file_hash(path) == file_hash(dst_path):
                            _emit(log_cb, f"⚖️  Já existe igual: {dst_path}")
                            copy_this = False
                        else:
                            dst_path = _resolve_conflict(dst_path)
                            _emit(log_cb, f"➕  Ficheiro semelhante, a guardar como {dst_path.name}")
                    except Exception as e:
                        _emit(log_cb, f"❌ Erro ao comparar {path} com {dst_path}: {e}")
                        dst_path = _resolve_conflict(dst_path)

                if copy_this:
                    _ensure_dir(dst_path)
                    shutil.copy2(path, dst_path)
                    try:
                        with open(dst_path, "rb") as fh:
                            fh.flush()
                            os.fsync(fh.fileno())
                    except Exception:
                        pass
                    stats["files_copied"] += 1
                    copied_mb = 0.0
                    try:
                        copied_mb = (dst_path.stat().st_size or 0) / (1024 * 1024)
                        stats["mb_copied"] += copied_mb
                    except Exception:
                        pass
                    stats["ext_counts"][ext_folder] = stats["ext_counts"].get(ext_folder, 0) + 1
                    stats["ext_sizes"][ext_folder] = stats["ext_sizes"].get(ext_folder, 0.0) + copied_mb
                    _emit(log_cb, f"✔ Copiado: {path} -> {dst_path}")
            except PermissionError as e:
                stats["files_denied"] += 1
                _emit(log_cb, f"⚠️  Sem acesso: {path} ({e})")
            except Exception as e:
                _emit(log_cb, f"❌ Erro ao copiar {path}: {e}")

            processed += 1
            _progress(progress_cb, processed)

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
                            try:
                                fh.flush()
                                os.fsync(fh.fileno())
                            except Exception:
                                pass
                        stats["files_copied"] += 1
                        copied_mb = 0.0
                        try:
                            copied_mb = (dst_path.stat().st_size or 0) / (1024 * 1024)
                            stats["mb_copied"] += copied_mb
                        except Exception:
                            pass
                        stats["ext_counts"][inner_ext] = stats["ext_counts"].get(inner_ext, 0) + 1
                        stats["ext_sizes"][inner_ext] = stats["ext_sizes"].get(inner_ext, 0.0) + copied_mb
                        stats["ext_from_archives"][inner_ext] = (
                            stats["ext_from_archives"].get(inner_ext, 0) + 1
                        )
                        _emit(log_cb, f"✔ Extraído: {path}!{inner_name} -> {dst_path}")
                        processed += 1
                        _progress(progress_cb, processed)
                except Exception as e:
                    _emit(log_cb, f"❌ Erro ao extrair {path}: {e}")
    finally:
        delete_snapshot(snap, log_cb=log_cb)
