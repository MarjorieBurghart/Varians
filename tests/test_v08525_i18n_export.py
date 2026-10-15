"""The remote-resource warning belongs to every supported publication locale."""
from pathlib import Path
import xml.etree.ElementTree as ET


def test_seven_iiif_dependency_translations_are_nonempty_and_unique():
    root = Path(__file__).resolve().parents[1]
    for lang in ('fr', 'en', 'de', 'ja', 'cs', 'it', 'ru'):
        nodes = ET.parse(root / 'i18n' / (lang + '.xml')).getroot().findall('string')
        keys = [node.attrib['key'] for node in nodes]
        assert len(keys) == len(set(keys)) == 629
        translated = {node.attrib['key']: node.text for node in nodes}
        assert '{count}' in translated['viewer.external_iiif_notice']
        text = (root / 'help' / (lang + '.html')).read_text(encoding='utf8')
        assert '<section id="web-iiif-v08525">' in text
        assert text.count('</body></html>') == 1
