from pathlib import Path
from typing import Iterable, Callable, List
from .copier import copy_selected

def cli_run(
    src: str,
    dst: str,
    types: Iterable[str],
    recursive: bool,
    preserve: bool,
    archives: bool = False,
    arch_types: List[str] | None = None,
    progress: Callable[[int], None] | None = None,
    log: Callable[[str], None] | None = None
) -> None:
    copy_selected(
        Path(src), Path(dst), types,
        recursive, preserve,
        archives, arch_types,
        progress_cb=progress, log_cb=log
    )
