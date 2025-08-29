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
