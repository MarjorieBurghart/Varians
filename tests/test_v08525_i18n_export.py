"""The remote-resource warning belongs to every supported publication locale."""
from pathlib import Path
import xml.etree.ElementTree as ET

from varians_source import CATALOG_SIZE


def test_seven_iiif_dependency_translations_are_nonempty_and_unique():
    root = Path(__file__).resolve().parents[1]
    for lang in ('fr', 'en', 'de', 'ja', 'cs', 'it', 'ru'):
        nodes = ET.parse(root / 'i18n' / (lang + '.xml')).getroot().findall('string')
        keys = [node.attrib['key'] for node in nodes]
        assert len(keys) == len(set(keys)) == CATALOG_SIZE
        translated = {node.attrib['key']: node.text for node in nodes}
        assert '{count}' in translated['viewer.external_iiif_notice']
        text = (root / 'help' / (lang + '.html')).read_text(encoding='utf8')
        assert 'IIIF' in text[text.index('<h2 id="viewer">'):]   # V0.9.3.1 : l'aide sans versions
        assert text.count('</body></html>') == 1
