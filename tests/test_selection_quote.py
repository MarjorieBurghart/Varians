# -*- coding: utf-8 -*-
"""Retrouver une sélection d'une vue à l'autre (V0.9.4.5).

Le texte visible d'un fichier XML est lu sans balises, entités décodées,
commentaires et instructions de traitement écartés, et chaque caractère
garde sa place dans le XML (``xml_compact``). Les blancs ne comptent pas :
une feuille XSLT ajoute ou retire des espaces et des sauts de ligne. Une
sélection est décrite par sa citation exacte et son contexte (``quote``),
comme une annotation du web, et retrouvée dans l'autre vue par la
ressemblance de ce contexte (``resolve``), non par un rang d'occurrence."""
from __future__ import annotations

import time

from selection_quote import plain_compact, quote, resolve, xml_compact


def _span_in_preview(preview, selected, nth=0):
    """Indices de la ``nth`` occurrence de ``selected`` dans le texte de
    l'aperçu ``preview``."""
    start = -1
    for _ in range(nth + 1):
        start = preview.index(selected, start + 1)
    return start, start + len(selected)


def _preview_to_xml(preview, selected, xml, nth=0, **hints):
    """Sélection ``selected`` (``nth`` occurrence) de l'aperçu, retrouvée
    dans ``xml`` : le texte XML sélectionné, ou None."""
    view = plain_compact(preview)
    i, j = view.range_of(*_span_in_preview(preview, selected, nth))
    target = xml_compact(xml)
    found = resolve(target, quote(view, i, j), **hints)
    return None if found is None else xml[slice(*target.span(*found))]


# --- Le texte visible du XML ------------------------------------------------

def test_the_visible_text_leaves_out_markup_and_blanks():
    compact = xml_compact('<p n="Jean">par <persName>Jean</persName>\n  de la <hi>M</hi>aison</p>')
    assert compact.text == "parJeandelaMaison"
    assert len(compact) == len(compact.text)


def test_entities_are_decoded_and_keep_their_whole_span():
    xml = "<p>Pierre &amp; Paul, l&#8217;homme, l&#x2019;ami</p>"
    compact = xml_compact(xml)
    assert compact.text == "Pierre&Paul,l’homme,l’ami"
    i = compact.text.index("&")
    assert xml[slice(*compact.span(i, i + 1))] == "&amp;"


def test_comments_processing_instructions_and_doctype_are_not_text():
    xml = ('<?xml version="1.0"?><!DOCTYPE TEI [<!ENTITY x "y">]><?xml-model href="a.rng"?>'
           "<TEI><!-- Jean de la --><p>Jean<![CDATA[ & <b>]]></p></TEI>")
    assert xml_compact(xml).text == "Jean&<b>"


def test_a_source_selection_becomes_a_range_of_visible_characters():
    xml = "<p>par <persName>Jean</persName> de la Rochelle</p>"
    compact = xml_compact(xml)
    start = xml.index("<persName>")                    # sélection qui commence par une balise
    end = xml.index(" la") + len(" la")
    i, j = compact.range_of(start, end)
    assert compact.text[i:j] == "Jeandela"


def test_the_preview_text_leaves_out_pencils_and_word_joiners():
    preview = "✎ Jean⁠ de\nla⁠Rochelle"
    compact = plain_compact(preview)
    assert compact.text == "JeandelaRochelle"
    i = compact.text.index("R")
    assert compact.span(i, i + 1) == (preview.index("R"), preview.index("R") + 1)


# --- Une sélection de l'aperçu retrouvée dans la source ---------------------

def test_a_selection_across_an_inline_element_is_found():
    xml = "<p>par <persName>Jean</persName> de la Rochelle</p>"
    assert _preview_to_xml("par Jean de la Rochelle", "Jean de la", xml) == "Jean</persName> de la"


def test_a_word_cut_by_an_inline_element_is_found():
    assert _preview_to_xml("la Maison", "Maison", "<p>la <hi>M</hi>aison</p>") == "M</hi>aison"


def test_a_word_cut_by_a_line_break_is_found():
    xml = '<p>sim\n  <lb break="no"/>plex</p>'
    assert _preview_to_xml("simplex", "simplex", xml) == 'sim\n  <lb break="no"/>plex'


def test_entities_are_found():
    xml = "<p>Pierre &amp; Paul, l&#8217;homme</p>"
    assert _preview_to_xml("Pierre & Paul, l’homme", "Pierre & Paul", xml) == "Pierre &amp; Paul"
    assert _preview_to_xml("Pierre & Paul, l’homme", "l’homme", xml) == "l&#8217;homme"


def test_an_expanded_abbreviation_is_found():
    xml = "<p><choice><abbr>dns</abbr><expan>dominus</expan></choice> noster</p>"
    assert _preview_to_xml("dominus noster", "dominus noster", xml) == "dominus</expan></choice> noster"


def test_an_attribute_value_is_never_chosen():
    """Un mot présent seulement dans une valeur d'attribut n'est pas du
    texte (ancien test_v0912_fragment_selection)."""
    xml = '<p><hi rend="premium">uerbum</hi> premium</p>'
    view = plain_compact("uerbum premium")
    target = xml_compact(xml)
    i, j = view.range_of(len("uerbum "), len("uerbum premium"))
    assert target.span(*resolve(target, quote(view, i, j)))[0] == xml.rindex("premium")


def test_a_comment_is_never_chosen():
    xml = "<TEI><!-- Jean de la --><p>Jean de la Rochelle</p></TEI>"
    view = plain_compact("Jean de la Rochelle")
    target = xml_compact(xml)
    i, j = view.range_of(0, len("Jean de la"))
    assert target.span(*resolve(target, quote(view, i, j)))[0] == xml.index("<p>") + 3


def test_repeated_text_is_found_by_its_context_without_line_breaks_or_pencils():
    """Sans <lb/> ni élément modifiable : la deuxième occurrence de l'aperçu
    est la deuxième de la source, reconnue à ce qui l'entoure."""
    xml = ("<div><p>Primo dixit Petrus ad populum.</p><p>Deinde dixit Paulus ad fratres.</p>"
           "<p>Tandem dixit Iohannes ad omnes.</p></div>")
    preview = "Primo dixit Petrus ad populum.\nDeinde dixit Paulus ad fratres.\nTandem dixit Iohannes ad omnes."
    found = _preview_to_xml(preview, "dixit", xml, nth=1)
    view = plain_compact(preview)
    target = xml_compact(xml)
    i, j = view.range_of(*_span_in_preview(preview, "dixit", 1))
    start, _end = target.span(*resolve(target, quote(view, i, j)))
    assert found == "dixit" and start == xml.index("dixit Paulus")


def test_a_note_rendered_elsewhere_does_not_shift_the_occurrence():
    """La note du paragraphe contient aussi « et dixit » ; l'aperçu la rend en
    fin de page : un décompte des occurrences se tromperait."""
    xml = "<p>Ille et dixit<note>et dixit : sic B</note> mox et dixit iterum.</p>"
    preview = "Ille et dixit1 mox et dixit iterum.\n1 et dixit : sic B"
    view = plain_compact(preview)
    target = xml_compact(xml)
    i, j = view.range_of(*_span_in_preview(preview, "et dixit", 1))    # « mox et dixit iterum »
    start, _end = target.span(*resolve(target, quote(view, i, j)))
    assert start == xml.index("et dixit iterum")


def test_text_added_by_the_stylesheet_next_to_the_selection_does_not_mislead():
    """Un appel de note ajouté juste après la sélection : le contexte qui
    précède suffit."""
    xml = "<p>Petrus ait. Paulus ait<note>sic</note> et abiit. Iohannes ait.</p>"
    preview = "Petrus ait. Paulus ait[1] et abiit. Iohannes ait."
    view = plain_compact(preview)
    target = xml_compact(xml)
    i, j = view.range_of(*_span_in_preview(preview, "ait", 1))
    start, _end = target.span(*resolve(target, quote(view, i, j)))
    assert start == xml.index("ait<note>")


def test_a_scope_keeps_the_search_in_one_element():
    xml = "<p>alpha beta</p><p>alpha beta</p>"
    target = xml_compact(xml)
    view = plain_compact("alpha beta")
    i, j = view.range_of(0, 5)
    second = target.range_of(xml.rindex("<p>"), len(xml))
    found = resolve(target, quote(view, i, j), scope=second)
    assert target.span(*found)[0] == xml.rindex("alpha")


def test_a_hint_breaks_a_tie_between_identical_passages():
    xml = "<p>idem idem idem</p>"
    target = xml_compact(xml)
    view = plain_compact("idem")
    q = quote(view, 0, 4)
    third = xml.rindex("idem")
    assert target.span(*resolve(target, q, hint=target.range_of(third, third + 1)[0]))[0] == third


def test_a_text_absent_from_the_source_is_not_found():
    assert _preview_to_xml("Notice 12 : Jean", "Notice 12", "<p>Jean</p>") is None


# --- Une sélection de la source retrouvée dans l'aperçu ---------------------

def test_a_source_selection_is_found_in_the_preview_by_its_context():
    xml = "<p>Primo <hi>dixit</hi> Petrus.</p><p>Deinde dixit Paulus.</p>"
    preview = "Primo dixit Petrus.\nDeinde dixit Paulus."
    source = xml_compact(xml)
    start = xml.index("dixit Paulus")
    i, j = source.range_of(start, start + len("dixit"))
    view = plain_compact(preview)
    found = resolve(view, quote(source, i, j))
    assert view.span(*found) == (preview.index("dixit Paulus"), preview.index("dixit Paulus") + 5)


# --- Vitesse ----------------------------------------------------------------

def test_a_large_file_is_read_and_searched_quickly():
    """Garde-fou large (quelques dizaines de millisecondes attendues) : une
    source de plus d'un mégaoctet, une sélection très courte et très
    fréquente."""
    paragraph = ('<p n="{n}">Item <persName ref="#p{n}">Iohannes</persName> de &amp; '
                 '<hi rend="italic">sermones</hi> dixit<lb/> et iterum dixit.</p>\n')
    xml = "<body>" + "".join(paragraph.format(n=n) for n in range(12000)) + "</body>"
    assert len(xml) > 1_000_000
    began = time.perf_counter()
    target = xml_compact(xml)
    preview = "\n".join(f"Item Iohannes de & sermones dixit et iterum dixit. {n}" for n in range(12000))
    view = plain_compact(preview)
    i, j = view.range_of(*_span_in_preview(preview, "di", 9000))
    found = resolve(target, quote(view, i, j))
    elapsed = time.perf_counter() - began
    assert found is not None and elapsed < 2.0, elapsed
