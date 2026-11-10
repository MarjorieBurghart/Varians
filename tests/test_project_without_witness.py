# -*- coding: utf-8 -*-
"""Projet sans témoin : on peut créer un projet (édition, validation,
aperçu, transformations) et n'ajouter ses témoins que plus tard, par
« Paramètres du projet »."""
from __future__ import annotations

from project_config import load_project

PROJECT = ('<teiManuscriptProject version="1"><title>Essai</title>'
           '<edition file="xml/edition.xml"/><rendering xsltMode="builtin"/>'
           '{witnesses}</teiManuscriptProject>')


def _project(tmp_path, witnesses):
    path = tmp_path / "project.xml"
    path.write_text(PROJECT.format(witnesses=witnesses), encoding="utf-8")
    return path


def test_a_project_without_witness_is_read(tmp_path):
    for witnesses in ("<witnesses/>", '<witnesses base=""/>', "<witnesses></witnesses>"):
        project = load_project(_project(tmp_path, witnesses))
        assert list(project.witnesses) == []
        assert project.base_witness == ""
        assert project.witness_by_id == {}


# -- Création d'une transcription vierge sans témoin -------------------------

from pathlib import Path

from lxml import etree

from project_management import WitnessDraft, create_new_transcription_project, minimal_tei_text

ROOT = Path(__file__).resolve().parents[1]
TEI = "{http://www.tei-c.org/ns/1.0}"
BIBL_FR = "<bibl><!-- Décrivez ici la source de votre document. --></bibl>"
BIBL_EN = "<bibl><!-- Describe the source of your document here. --></bibl>"


def _source_desc(text):
    root = etree.fromstring(text.encode("utf-8"))
    return root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}sourceDesc")


def test_a_blank_transcription_without_witness_explains_the_list_of_witnesses():
    text = minimal_tei_text("Essai", [], "", language="fr", schema_mode="none")
    source_desc = _source_desc(text)
    children = list(source_desc)
    assert [etree.QName(c).localname if isinstance(c.tag, str) else "comment" for c in children] == [
        "comment", "bibl"]
    guide = children[0].text
    for words in ("scholarly digital edition", "<listWit>", "<witness>", "@xml:id", '<rdg wit="#A">',
                  '<pb edRef="#A"/>', '<idno type="siglum">', "Fichier > Paramètres du projet…",
                  "reste inconnu du projet", '<witness xml:id="_1520"><idno type="siglum">1520</idno>'):
        assert words in guide, words
    # Le paragraphe « vous pouvez aussi l'écrire vous-même » n'y est plus.
    assert "vous-même" not in guide
    # Le <bibl> de remplissage : son seul contenu est un commentaire.
    assert BIBL_FR in text
    bibl = children[1]
    assert (bibl.text or "").strip() == "" and len(bibl) == 1 and not isinstance(bibl[0].tag, str)
    assert source_desc.find(f"{TEI}listWit") is None
    assert source_desc.find(f"{TEI}p") is None


def test_the_guide_is_in_english_in_an_english_project():
    text = minimal_tei_text("Essay", [], "", language="en", schema_mode="none")
    guide = list(_source_desc(text))[0].text
    assert "scholarly digital edition" in guide and "File > Project settings…" in guide
    assert BIBL_EN in text


def test_a_blank_transcription_with_witnesses_is_unchanged():
    text = minimal_tei_text("Essai", [WitnessDraft("A", "Manuscrit A", None, "base")], "A",
                            language="fr", schema_mode="none")
    source_desc = _source_desc(text)
    assert [c.get("{http://www.w3.org/XML/1998/namespace}id") for c in source_desc.find(f"{TEI}listWit")] == ["A"]
    assert "<bibl>" not in text and "scholarly" not in text


def test_a_new_transcription_project_can_have_no_witness(tmp_path):
    project_xml = create_new_transcription_project(
        target_dir=tmp_path / "projet", title="Essai", witnesses=[], base_witness="",
        template_root=ROOT, language="fr", fallback_language="en", xslt_mode="builtin", schema_mode="none")
    project = load_project(project_xml)
    assert list(project.witnesses) == [] and project.base_witness == ""
    assert BIBL_FR in project.edition.read_text(encoding="utf-8")
    assert 'base=' not in project_xml.read_text(encoding="utf-8")


# -- Premier témoin : la <listWit> créée ----------------------------------------

from tei_listwit import add_witnesses_to_listwit

T1 = WitnessDraft("T1", "Paris, Bibliothèque nationale de France, latin 1234")
T2 = WitnessDraft("T2", "Troyes, Médiathèque, ms. 567")
LISTWIT_T1 = ("<listWit>\n"
              '          <witness xml:id="T1">Paris, Bibliothèque nationale de France, latin 1234</witness>\n'
              "        </listWit>")


def _blank(language="fr"):
    return minimal_tei_text("Essai", [], "", language=language, schema_mode="none")


def test_the_first_witness_replaces_the_untouched_bibl():
    for language, bibl in (("fr", BIBL_FR), ("en", BIBL_EN)):
        source = _blank(language)
        updated, report = add_witnesses_to_listwit(source, [T1])
        assert report.created and report.added == ["T1"]
        assert updated == source.replace(bibl, LISTWIT_T1)
        # Le mode d'emploi reste, à titre pédagogique.
        assert "scholarly digital edition" in updated
        source_desc = _source_desc(updated)
        assert [etree.QName(c).localname for c in source_desc if isinstance(c.tag, str)] == ["listWit"]


def test_a_modified_bibl_stays_and_the_listwit_goes_under_it():
    for modified in ("<bibl>Paris, BnF, latin 1234</bibl>",
                     "<bibl><!-- Ma propre note. --></bibl>",
                     "<bibl><!-- Décrivez ici la source de votre document. -->Paris</bibl>"):
        source = _blank().replace(BIBL_FR, modified)
        updated, report = add_witnesses_to_listwit(source, [T1])
        assert report.created and report.added == ["T1"]
        assert updated == source.replace(modified, modified + "\n        " + LISTWIT_T1)


def test_the_example_in_the_guide_is_never_taken_for_the_list():
    source = _blank()
    updated, _ = add_witnesses_to_listwit(source, [T1])
    updated, report = add_witnesses_to_listwit(updated, [T2])
    assert report.added == ["T2"] and not report.created
    source_desc = _source_desc(updated)
    (list_wit,) = source_desc.findall(f"{TEI}listWit")
    assert [w.get("{http://www.w3.org/XML/1998/namespace}id") for w in list_wit] == ["T1", "T2"]
    # Le commentaire n'a pas bougé : son exemple garde ses trois témoins.
    guide = list(source_desc)[0].text
    assert guide == list(_source_desc(source))[0].text


def test_paragraphs_written_in_place_of_the_bibl_are_not_mixed_with_a_listwit():
    source = _blank().replace(BIBL_FR, "<p>Manuscrit de Paris.</p>")
    updated, report = add_witnesses_to_listwit(source, [T1])
    assert updated == source and report.paragraphs == ["T1"] and not report.changed


def test_the_new_project_box_says_witnesses_can_come_later():
    import xml.etree.ElementTree as ET
    for language in ("fr", "en", "de", "cs", "it", "ru", "ja"):
        catalog = {s.get("key"): s.text for s in ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()}
        info = catalog["project.new.info.blank"]
        assert catalog["menu.project_settings"] in info, language
        assert "project.validation.no_witness" not in catalog
