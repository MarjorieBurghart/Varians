from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rng_completion import XmlContextCache, analyze_xml_context


def _large_xml(count=1200):
    body = "".join(f"<p><seg>{i}</seg><note>n{i}</note></p>" for i in range(count))
    return f"<TEI><text><body>{body}</body></text></TEI>"


def test_cached_context_matches_stateless_scanner():
    text = _large_xml()
    cache = XmlContextCache(stride=4096)
    positions = [len(text) // 3, len(text) // 2, int(len(text) * 0.85)]
    for pos in positions:
        assert cache.analyze(text, pos) == analyze_xml_context(text, pos)
    # Après un premier parcours, une requête plus loin doit reprendre depuis
    # un point mémorisé et non depuis le caractère zéro.
    cache.analyze(text, int(len(text) * 0.92))
    assert cache.last_scan_start > 0


def test_cached_context_survives_edit_with_partial_invalidation():
    text = _large_xml()
    cache = XmlContextCache(stride=4096)
    first_pos = int(len(text) * 0.8)
    cache.analyze(text, first_pos)

    needle = "<note>n900</note>"
    change = text.index(needle)
    edited = text[:change] + "<note><hi>corr</hi></note>" + text[change + len(needle):]
    cache.invalidate_from(change)
    pos = edited.index("corr") + len("corr")
    cached = cache.analyze(edited, pos)
    plain = analyze_xml_context(edited, pos)
    assert cached == plain
    assert cached.parent_element == "hi"
    # Les checkpoints situés avant l'édition doivent avoir été conservés.
    assert cache.last_scan_start > 0
