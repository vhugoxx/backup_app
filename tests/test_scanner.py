from pathlib import Path

import pytest

from src.core.scanner import scan


def test_scan_recursive_filters(tmp_path):
    (tmp_path / 'a.jpg').write_text('jpg')
    (tmp_path / 'a.txt').write_text('txt')
    sub = tmp_path / 'sub'
    sub.mkdir()
    (sub / 'b.jpg').write_text('jpg')

    found = list(scan(tmp_path, extensions=['jpg'], recursive=True))
    rel = {p.relative_to(tmp_path) for p in found}
    assert rel == {Path('a.jpg'), Path('sub/b.jpg')}


def test_scan_missing_root():
    missing = Path('nao_existe')
    with pytest.raises(FileNotFoundError):
        list(scan(missing, extensions=['jpg']))

    # Com treat_missing_as_warning=True não deve lançar erro
    assert list(scan(missing, extensions=['jpg'], treat_missing_as_warning=True)) == []
