from pathlib import Path
import zipfile

from src.core.extractor import is_archive, iterate_archive


def test_is_archive_detects_zip():
    assert is_archive(Path('ficheiro.zip'))
    assert not is_archive(Path('ficheiro.txt'))


def test_iterate_archive_reads_files(tmp_path):
    zip_path = tmp_path / 'dados.zip'
    with zipfile.ZipFile(zip_path, 'w') as z:
        z.writestr('a.jpg', 'abc')
        z.writestr('b.txt', 'xyz')

    items = list(iterate_archive(zip_path, extensions=['jpg']))
    assert len(items) == 1
    nome, bio = items[0]
    assert nome == 'a.jpg'
    assert bio.read() == b'abc'
