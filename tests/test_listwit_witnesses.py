# -*- coding: utf-8 -*-
"""Un témoin ajouté au projet est déclaré dans la <listWit> existante de
l'édition (V0.9.2.8.2).

Son ``<witness>`` va à la fin de la première ``<listWit>`` de l'en-tête,
dans le style de celle-ci (une ligne par témoin, ou à la suite) :
``<witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>``.
Varians ne crée jamais de ``<listWit>`` : sans elle, l'édition reste telle
quelle et le témoin est signalé. Un témoin déjà déclaré n'est pas répété ;
un identifiant déjà porté par un autre élément n'est pas employé. Le reste
du fichier ne change pas."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from project_management import WitnessDraft
from tei_listwit import add_witnesses_to_listwit, add_witnesses_to_listwit_file

TEI = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
NEW = WitnessDraft("_1760", "Troyes 1760", siglum="1760")


def _tei(source_desc, ns=f' xmlns="{TEI}"', prefix=""):
    p = prefix
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<{p}TEI{ns}>\n  <{p}teiHeader>\n    <{p}fileDesc>\n'
            f'      <{p}titleStmt><{p}title>T</{p}title></{p}titleStmt>\n'
            f'      <{p}publicationStmt><{p}p>x</{p}p></{p}publicationStmt>\n'
            f'      <{p}sourceDesc>{source_desc}</{p}sourceDesc>\n'
            f'    </{p}fileDesc>\n  </{p}teiHeader>\n  <{p}text><{p}body><{p}p>Lorem</{p}p></{p}body></{p}text>\n</{p}TEI>\n')


LISTWIT = ('\n        <listWit>\n          <witness xml:id="T1">Troyes 816</witness>\n'
           '          <witness xml:id="T2">Troyes 1760</witness>\n        </listWit>\n      ')


def _witnesses(text):
    return {el.get(XML_ID): el for el in ET.fromstring(text.split("?>", 1)[1]).iter(f"{{{TEI}}}witness")}


def test_the_witness_goes_at_the_end_of_the_listwit_on_its_own_line():
    source = _tei(LISTWIT)
    updated, report = add_witnesses_to_listwit(source, [NEW])
    assert report.added == ["1760"] and report.changed
    assert updated == source.replace(
        '<witness xml:id="T2">Troyes 1760</witness>\n',
        '<witness xml:id="T2">Troyes 1760</witness>\n'
        '          <witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>\n')
    assert list(_witnesses(updated)) == ["T1", "T2", "_1760"]


def test_a_listwit_written_on_one_line_stays_on_one_line():
    source = _tei('<listWit><witness xml:id="T1">Troyes 816</witness></listWit>')
    updated, report = add_witnesses_to_listwit(source, [NEW, WitnessDraft("P", "Paris, BnF")])
    assert report.added == ["1760", "P"]
    assert ('<listWit><witness xml:id="T1">Troyes 816</witness>'
            '<witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>'
            '<witness xml:id="P">Paris, BnF</witness></listWit>') in updated


def test_a_declared_witness_or_a_used_identifier_is_not_added():
    source = _tei(LISTWIT).replace("<p>Lorem</p>", '<p>Lorem <persName xml:id="P">Petrus</persName></p>')
    updated, report = add_witnesses_to_listwit(source, [WitnessDraft("T2", "Troyes 1760"), WitnessDraft("P", "Paris")])
    assert updated == source and not report.changed
    assert report.declared == ["T2"] and report.id_used == ["P"] and report.added == []


def test_no_listwit_is_ever_created():
    for source_desc in ("<p>Transcription en cours</p>", "<bibl>Un manuscrit</bibl>"):
        source = _tei(source_desc)
        updated, report = add_witnesses_to_listwit(source, [NEW])
        assert updated == source and not report.changed
        assert report.no_listwit == ["1760"] and report.added == []


def test_a_listwit_outside_the_header_is_left_alone():
    source = _tei("<p>x</p>").replace("<body><p>Lorem</p>", '<body><listWit><witness xml:id="A">A</witness></listWit><p>Lorem</p>')
    updated, report = add_witnesses_to_listwit(source, [NEW])
    assert updated == source and report.no_listwit == ["1760"]


def test_the_outer_listwit_receives_the_witness():
    source = _tei('<listWit><listWit xml:id="g"><witness xml:id="A">A</witness></listWit>'
                  '<witness xml:id="B">B</witness></listWit>')
    updated, _report = add_witnesses_to_listwit(source, [NEW])
    assert ('<witness xml:id="B">B</witness><witness xml:id="_1760"><idno type="siglum">1760</idno>'
            'Troyes 1760</witness></listWit>') in updated


def test_a_prefixed_tei_gets_prefixed_elements():
    source = _tei('<tei:listWit><tei:witness xml:id="T1">T</tei:witness></tei:listWit>',
                  ns=f' xmlns:tei="{TEI}"', prefix="tei:")
    updated, report = add_witnesses_to_listwit(source, [NEW])
    assert report.added == ["1760"]
    assert '<tei:witness xml:id="_1760"><tei:idno type="siglum">1760</tei:idno>Troyes 1760</tei:witness></tei:listWit>' in updated
    assert "_1760" in _witnesses(updated)


def test_labels_are_escaped_and_the_siglum_is_the_default_label():
    source = _tei(LISTWIT)
    updated, _report = add_witnesses_to_listwit(source, [WitnessDraft("Q", "Q & <R>"), WitnessDraft("_1761", "", siglum="1761")])
    witnesses = _witnesses(updated)
    assert "".join(witnesses["Q"].itertext()) == "Q & <R>"
    assert witnesses["_1761"].find(f"{{{TEI}}}idno").tail == "1761"


def test_a_malformed_edition_is_left_alone():
    source = _tei(LISTWIT).replace("</body>", "")
    updated, report = add_witnesses_to_listwit(source, [NEW])
    assert updated == source and report.malformed == ["1760"] and report.added == []


def test_the_file_is_written_with_a_backup_only_when_it_changes(tmp_path):
    path = tmp_path / "edition.xml"
    path.write_text(_tei(LISTWIT), encoding="utf-8")
    report = add_witnesses_to_listwit_file(path, [WitnessDraft("T1", "Troyes 816")])
    assert not report.changed and not (tmp_path / "edition.xml.bak").exists()
    report = add_witnesses_to_listwit_file(path, [NEW])
    assert report.changed and (tmp_path / "edition.xml.bak").read_text(encoding="utf-8") == _tei(LISTWIT)
    assert "_1760" in _witnesses(path.read_text(encoding="utf-8"))


def test_the_line_endings_of_the_file_are_kept(tmp_path):
    path = tmp_path / "edition.xml"
    path.write_bytes(_tei(LISTWIT).replace("\n", "\r\n").encode("utf-8"))
    add_witnesses_to_listwit_file(path, [NEW])
    data = path.read_bytes().decode("utf-8")
    assert data.count("\n") == data.count("\r\n") and "_1760" in data
    assert '</witness>\r\n          <witness xml:id="_1760">' in data
