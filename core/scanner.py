"""
Scanner
-------

Percorre recursivamente (ou não) a árvore de *root* e devolve apenas os
ficheiros cujo sufixo (extensão) esteja na lista `exts`.

Parameters
----------
root : pathlib.Path | str
    Pasta ou drive de origem.
exts : list[str]
    Extensões sem ponto – ex.: ["jpg", "pdf"].
recursive : bool, default True
    Se False, não desce a sub-pastas.
ignore_long_paths : bool, default True
    Se True, descarta caminhos ≥ 260 caracteres (Windows).  Se False,
    deixa que o sistema de ficheiros lance a excepção.

Yields
------
pathlib.Path
    Caminhos absolutos dos ficheiros correspondentes.
"""

from __future__ import annotations
from pathlib import Path
from typing import Iterator


class Scanner:
    def __init__(
        self,
        root: str | Path,
        exts: list[str],
        recursive: bool = True,
        ignore_long_paths: bool = True,
    ) -> None:
        self.root             = Path(root).expanduser().resolve()
        self.exts             = {e.lower().lstrip(".") for e in exts}
        self.recursive        = recursive
        self.ignore_long_paths = ignore_long_paths

    # --------------------------------------------------------------------- helpers
    @staticmethod
    def _is_long(path: Path) -> bool:
        return len(str(path)) >= 260  # limite tradicional Win32

    # --------------------------------------------------------------------- API
    def scan(self) -> Iterator[Path]:
        """
        Gera os ficheiros que passam nos filtros, lidando com erros de
        permissão de forma segura (ignora e continua).
        """
        pattern = "**/*" if self.recursive else "*"

        # glob gera‐nos tanto ficheiros como directorias
        iterator = self.root.rglob("*") if self.recursive else self.root.glob("*")

        for p in iterator:
            try:
                if not p.is_file():
                    continue

                # extensão
                if p.suffix.lower().lstrip(".") not in self.exts:
                    continue

                # caminhos longos
                if self.ignore_long_paths and self._is_long(p):
                    # simplesmente ignora; quem chama decide se regista
                    continue

                yield p

            except PermissionError:
                # sem acesso – ignorar e seguir
                continue
