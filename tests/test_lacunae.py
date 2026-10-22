# -*- coding: utf-8 -*-
"""Lacunes des témoins (V0.9.1.3), sans Qt : ``<lacunaStart/>`` …
``<lacunaEnd/>``, le témoin donné par ``@wit`` ou par la leçon englobante.

Dans une édition en parties (pivot_lines), une lacune peut passer d'une partie
à l'autre (numérotation continue) ; dans un texte synchronisé à part, l'état
repart de zéro au début du texte.

Jeu « sermons » (tests/data/sermons), pivot A : s01 a les lignes 0 à 9, s03
10 à 18, s04 19 à 23 et son exemplum 24 à 26 ; s02 (pivot B) n'en a pas.
"""
from __future__ import annotations

from pathlib import Path

from document_session import LbIndex
from lacunae import lacuna_events, lacunae_at
from pivot_lines import include_spans, pivot_lb_pattern, pivot_lines

DATA = Path(__file__).resolve().parent / "data" / "sermons" / "xml"
EDITION = DATA / "edition.xml"
SERMONS = DATA / "sermons"
S01, S02, S03, S04 = (SERMONS / f"{name}.xml" for name in ("s01", "s02", "s03", "s04"))

TEXT = """<p><lb edRef="#A"/>alpha <lacunaStart wit="#B #C"/>beta
<lb edRef="#A"/>gamma <app><rdg wit="#D"><lacunaStart/></rdg><rdg wit="#B"/></app> delta
<!-- <lacunaEnd wit="#B"/> dans un commentaire -->
<lb edRef="#A"/>epsilon <lacunaEnd wit="#B"/>zeta
<lb edRef="#A"/>eta <app><lem wit="#A"/><rdg wit="#D"><lacunaEnd/></rdg></app> theta
<lacunaEnd wit="#E"/>iota</p>"""


def _state(word):
    return lacunae_at(TEXT, TEXT.index(word))


# --- Un texte --------------------------------------------------------------------

def test_a_text_without_lacuna_has_no_event():
    assert lacuna_events('<p><lb edRef="#A"/>nihil</p>') == ()
    assert lacunae_at('<p>nihil</p>', 5) == {}


def test_the_witnesses_of_a_lacuna_come_from_wit_or_from_the_enclosing_reading():
    events = lacuna_events(TEXT)
    assert [(e.start, sorted(e.witnesses)) for e in events] == [
        (True, ["B", "C"]), (True, ["D"]), (False, ["B"]), (False, ["D"]), (False, ["E"])]


def test_a_witness_is_in_lacuna_between_the_start_and_the_end():
    assert _state("alpha") == {}
    assert sorted(_state("beta")) == ["B", "C"]
    assert sorted(_state("delta")) == ["B", "C", "D"]
    assert sorted(_state("zeta")) == ["C", "D"]           # fin de B ; celle du commentaire ne compte pas
    assert sorted(_state("theta")) == ["C"]               # fin de D, dans sa leçon
    assert sorted(_state("iota")) == ["C"]                # une fin sans début est ignorée ; C n'est pas fermée


def test_the_start_of_a_lacuna_is_given_by_its_position():
    start = TEXT.index("beta")                            # juste après <lacunaStart wit="#B #C"/>
    state = _state("zeta")
    assert state["C"].position == start and state["C"].ordinal is None
    assert state["D"].position == TEXT.index("</rdg><rdg wit=\"#B\"/>")


def test_inside_the_tag_the_lacuna_has_not_started():
    tag = TEXT.index("<lacunaStart wit")
    assert lacunae_at(TEXT, tag + 3) == {}


# --- Édition assemblée ------------------------------------------------------------

PATTERN = pivot_lb_pattern("A")


def _read(path):
    return path.read_text(encoding="utf-8")


def _put(path, needle, insert, after=True):
    text = _read(path)
    at = text.index(needle) + (len(needle) if after else 0)
    return text[:at] + insert + text[at:]


def _at(lines, path, text, needle):
    position = text.index(needle)
    return lines.lacunae_at(path, position, text, include_spans(text))


def test_a_lacuna_crosses_the_parts_of_the_edition():
    s01 = _put(S01, '<lb edRef="#A"/>', '<lacunaStart wit="#C"/>')       # sur la 1re ligne de s01
    s04 = _put(S04, "<head>", '<lacunaEnd wit="#C"/>', after=False)
    lines = pivot_lines(_read(EDITION), EDITION, {S01: s01, S04: s04}, "A")
    s03 = _read(S03)
    state = _at(lines, S03, s03, '<div xml:id="s03"')
    assert list(state) == ["C"] and state["C"].ordinal == 0 and state["C"].position is None
    assert list(_at(lines, S04, s04, "<lacunaEnd")) == ["C"]
    assert _at(lines, S04, s04, "<head>Sermo") == {}
    # Dans la partie où elle commence : la position du début.
    local = _at(lines, S01, s01, "<pb")
    assert local["C"].position == s01.index('<lacunaStart wit="#C"/>') + len('<lacunaStart wit="#C"/>')


def test_the_ordinal_of_a_lacuna_is_the_pivot_line_where_it_starts():
    s03 = _put(S03, "<head>", '<lacunaStart wit="#E"/>', after=False)
    lines = pivot_lines(_read(EDITION), EDITION, {S03: s03}, "A")
    s04 = _read(S04)
    assert _at(lines, S04, s04, "<head>")["E"].ordinal == 9   # dernière ligne de s01, avant s03


def test_a_text_synchronized_apart_starts_without_lacuna():
    s01 = _put(S01, '<lb edRef="#A"/>', '<lacunaStart wit="#B"/>')
    s02 = _read(S02)
    lines = pivot_lines(_read(EDITION), EDITION, {S01: s01}, "A", text_bases={S02: "B"})
    assert _at(lines, S02, s02, "<head>") == {}               # texte à part : rien n'est hérité
    assert list(_at(lines, S03, _read(S03), "<head>")) == ["B"]   # l'édition continue
    # Une lacune ouverte dans le texte à part n'en sort pas.
    s02b = _put(S02, "<head>", '<lacunaStart wit="#D"/>', after=False)
    lines = pivot_lines(_read(EDITION), EDITION, {S02: s02b}, "A", text_bases={S02: "B"})
    assert list(_at(lines, S02, s02b, "</head>")) == ["D"]
    assert _at(lines, S03, _read(S03), "<head>") == {}


def test_without_lacuna_the_numbering_is_unchanged():
    lines = pivot_lines(_read(EDITION), EDITION, {}, "A")
    assert lines.count == 27
    text = _read(S03)
    assert lines.lacunae_at(S03, text.index("<head>"), text, include_spans(text)) == {}
    assert lines.ordinal_at(S03, text.index("<head>"), LbIndex.scan(text, PATTERN), include_spans(text)) == 9
