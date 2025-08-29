from src.core.copier import copy_selected


def test_copy_selected_copies_only_requested(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.mkdir()
    (src / 'doc.txt').write_text('x')
    sub = src / 'sub'
    sub.mkdir()
    (sub / 'foto.jpg').write_text('img')

    progress = []
    stats = {}
    copy_selected(
        src=src,
        dst=dst,
        extensions={'jpg'},
        recursive=True,
        preserve_structure=True,
        progress_cb=progress.append,
        stats=stats,
    )

    copied = dst / 'jpg' / 'sub' / 'foto.jpg'
    assert copied.exists()
    assert not (dst / 'txt').exists()
    assert stats['files_copied'] == 1
    assert progress[-1] == 1


def test_copy_skips_if_identical(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.mkdir()
    (src / 'foto.jpg').write_text('img')
    (dst / 'jpg').mkdir(parents=True)
    (dst / 'jpg' / 'foto.jpg').write_text('img')

    stats = {}
    copy_selected(
        src=src,
        dst=dst,
        extensions={'jpg'},
        recursive=True,
        preserve_structure=True,
        stats=stats,
    )

    folder = dst / 'jpg'
    assert list(folder.iterdir()) == [folder / 'foto.jpg']
    assert stats['files_copied'] == 0


def test_copy_adds_if_different(tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.mkdir()
    (src / 'foto.jpg').write_text('new')
    (dst / 'jpg').mkdir(parents=True)
    (dst / 'jpg' / 'foto.jpg').write_text('old')

    stats = {}
    copy_selected(
        src=src,
        dst=dst,
        extensions={'jpg'},
        recursive=True,
        preserve_structure=True,
        stats=stats,
    )

    folder = dst / 'jpg'
    files = sorted(p.name for p in folder.iterdir())
    assert files == ['foto.jpg', 'foto_1.jpg']
    assert (folder / 'foto.jpg').read_text() == 'old'
    assert (folder / 'foto_1.jpg').read_text() == 'new'
    assert stats['files_copied'] == 1
