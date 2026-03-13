from pathlib import Path
from typing import Iterable, Iterator, Tuple
import io, zipfile, tarfile
import os


class PathTraversalError(Exception):
    """Exceção levantada quando um caminho de arquivo tenta escapar do diretório de destino."""
    pass


def _validate_archive_member_path(member_name: str, archive_path: Path) -> str:
    """Valida se o caminho de um membro do arquivo é seguro contra Path Traversal.
    
    Args:
        member_name: Nome/caminho do arquivo dentro do arquivo comprimido
        archive_path: Caminho do arquivo comprimido (para mensagens de erro)
        
    Returns:
        Nome do arquivo sanitizado (sem componentes perigosos)
        
    Raises:
        PathTraversalError: Se o caminho tentar escapar do diretório de destino
    """
    # Normaliza separadores para o sistema atual
    normalized = member_name.replace('\\', '/').replace('//', '/')
    
    # Verifica caminhos absolutos
    if os.path.isabs(normalized) or normalized.startswith('/'):
        raise PathTraversalError(
            f"Caminho absoluto detectado no arquivo '{archive_path}': {member_name!r}"
        )
    
    # Verifica componentes ".." que tentam subir na hierarquia
    parts = normalized.split('/')
    for part in parts:
        if part == '..':
            raise PathTraversalError(
                f"Path traversal detectado no arquivo '{archive_path}': {member_name!r}"
            )
        # Verifica também variações com espaços ou caracteres especiais
        if part.strip() == '..' or part.strip('.').strip() == '':
            if part not in ('.', ''):
                raise PathTraversalError(
                    f"Componente de caminho suspeito no arquivo '{archive_path}': {member_name!r}"
                )
    
    # Verifica se o caminho resolvido escapa da raiz
    # Usa um diretório virtual para testar
    test_base = Path('/safe_root')
    try:
        resolved = (test_base / normalized).resolve()
        if not str(resolved).startswith(str(test_base)):
            raise PathTraversalError(
                f"Caminho resolvido escapa do diretório base no arquivo '{archive_path}': {member_name!r}"
            )
    except (ValueError, OSError) as e:
        raise PathTraversalError(
            f"Erro ao validar caminho no arquivo '{archive_path}': {member_name!r} - {e}"
        )
    
    # Remove componentes de caminho perigosos e retorna caminho limpo
    safe_parts = [p for p in parts if p and p not in ('.', '..')]
    return '/'.join(safe_parts) if safe_parts else member_name


def is_archive(path: Path, tipos: Iterable[str] | None = None) -> bool:
    """Verifica se ``path`` aponta para um arquivo suportado."""
    nome = path.name.lower()
    suportadas = {
        "zip",
        "rar",
        "7z",
        "tar",
        "tgz",
        "tar.gz",
        "tbz2",
        "tar.bz2",
    }
    if tipos:
        suportadas |= {t.lower().lstrip(".") for t in tipos}
    return any(nome.endswith(f".{ext}") for ext in suportadas)

def iterate_archive(path: Path, extensions: Iterable[str]) -> Iterator[Tuple[str, io.BufferedReader]]:
    """Gera (nome_relativo, stream) para cada ficheiro interno pretendido.
    
    SEGURANÇA: Valida todos os caminhos internos para prevenir Path Traversal.
    
    Raises:
        PathTraversalError: Se algum arquivo interno tiver caminho malicioso
    """
    want = {e.lower().lstrip(".") for e in extensions}
    suf  = path.suffix.lower()

    if suf == ".zip":
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                # SEGURANÇA: Validar caminho antes de processar
                safe_name = _validate_archive_member_path(info.filename, path)
                if Path(safe_name).suffix.lower().lstrip(".") in want:
                    with z.open(info) as f:
                        yield safe_name, io.BytesIO(f.read())

    elif suf in {".tar", ".tgz", ".tar.gz", ".tbz2", ".tar.bz2"}:
        with tarfile.open(path, "r:*") as t:
            for m in t.getmembers():
                if not m.isfile(): continue
                # SEGURANÇA: Validar caminho antes de processar
                safe_name = _validate_archive_member_path(m.name, path)
                if Path(safe_name).suffix.lower().lstrip(".") in want:
                    f = t.extractfile(m)
                    if f:
                        yield safe_name, io.BytesIO(f.read())

    elif suf == ".rar":
        import rarfile            # pip install rarfile
        with rarfile.RarFile(path) as r:
            for info in r.infolist():
                # SEGURANÇA: Validar caminho antes de processar
                safe_name = _validate_archive_member_path(info.filename, path)
                if Path(safe_name).suffix.lower().lstrip(".") in want:
                    with r.open(info) as f:
                        yield safe_name, io.BytesIO(f.read())

    # -------- 7-Zip --------------------------------------------------
    elif suf == ".7z":
        try:
            import py7zr            # pip install py7zr
        except ImportError:
            return                  # lib ausente → ignora este arquivo

        with py7zr.SevenZipFile(path, mode="r") as z:
            try:                                # versões < 1.0
                for name, bio in z.readall().items():
                    # SEGURANÇA: Validar caminho antes de processar
                    safe_name = _validate_archive_member_path(name, path)
                    if Path(safe_name).suffix.lower().lstrip(".") in want:
                        yield safe_name, bio
            except AttributeError:              # versões ≥ 1.0
                for name in z.getnames():
                    # SEGURANÇA: Validar caminho antes de processar
                    safe_name = _validate_archive_member_path(name, path)
                    if Path(safe_name).suffix.lower().lstrip(".") not in want:
                        continue
                    # read() devolve dict {nome: BytesIO}
                    bio = z.read([name])[name]
                    yield safe_name, bio

