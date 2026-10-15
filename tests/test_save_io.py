from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from save_io import atomic_write_text_with_backup


def test_atomic_write_and_backup_rotation():
    with TemporaryDirectory() as td:
        p = Path(td) / 'edition.xml'
        p.write_text('ancien', encoding='utf-8')
        bak = atomic_write_text_with_backup(p, 'nouveau')
        assert p.read_text(encoding='utf-8') == 'nouveau'
        assert bak.read_text(encoding='utf-8') == 'ancien'
        assert not list(Path(td).glob('*.tmp'))

        atomic_write_text_with_backup(p, 'encore')
        assert p.read_text(encoding='utf-8') == 'encore'
        assert bak.read_text(encoding='utf-8') == 'nouveau'
        assert not list(Path(td).glob('*.tmp'))
