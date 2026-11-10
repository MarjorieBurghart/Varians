# -*- coding: utf-8 -*-
"""Un témoin ajouté au projet est déclaré dans la <listWit> existante de
l'édition (V0.9.2.8.2).

Son ``<witness>`` va à la fin de la première ``<listWit>`` de l'en-tête,
dans le style de celle-ci (une ligne par témoin, ou à la suite) :
``<witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>``.
Sans ``<listWit>``, Varians en crée une dans le ``<sourceDesc>`` quand la TEI
le permet (pas de ``<p>`` ni d'``<ab>`` à côté) : à la place du ``<bibl>`` de
remplissage d'une transcription sans témoin, s'il est intact, sinon à la
suite du contenu. Un témoin déjà déclaré n'est pas répété ;
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


def test_paragraphs_in_the_source_description_block_the_creation():
    """<sourceDesc> : des paragraphes, ou des éléments structurés, jamais les
    deux ; une <listWit> ne peut pas s'ajouter à côté d'un <p> ou d'un <ab>."""
    for source_desc in ("<p>Transcription en cours</p>", "<ab>Transcription</ab>"):
        source = _tei(source_desc)
        updated, report = add_witnesses_to_listwit(source, [NEW])
        assert updated == source and not report.changed
        assert report.paragraphs == ["1760"] and report.added == [] and report.no_listwit == []


def test_a_listwit_is_created_under_a_bibl():
    source = _tei("\n        <bibl>Un manuscrit</bibl>\n      ")
    updated, report = add_witnesses_to_listwit(source, [NEW, WitnessDraft("P", "Paris, BnF")])
    assert report.created and report.changed and report.added == ["1760", "P"]
    assert updated == source.replace(
        "<bibl>Un manuscrit</bibl>\n",
        "<bibl>Un manuscrit</bibl>\n"
        "        <listWit>\n"
        '          <witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>\n'
        '          <witness xml:id="P">Paris, BnF</witness>\n'
        "        </listWit>\n")
    assert list(_witnesses(updated)) == ["_1760", "P"]


def test_without_source_description_nothing_is_created():
    source = _tei("<p>x</p>").replace("<sourceDesc><p>x</p></sourceDesc>", "")
    updated, report = add_witnesses_to_listwit(source, [NEW])
    assert updated == source and report.no_listwit == ["1760"] and not report.created


def test_a_listwit_outside_the_header_is_left_alone():
    source = _tei("<p>x</p>").replace("<body><p>Lorem</p>", '<body><listWit><witness xml:id="A">A</witness></listWit><p>Lorem</p>')
    updated, report = add_witnesses_to_listwit(source, [NEW])
    # Le <sourceDesc> en paragraphes ne reçoit pas de <listWit> non plus.
    assert updated == source and report.added == [] and report.paragraphs == ["1760"]


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


def test_the_report_names_a_created_list_and_paragraphs():
    from pathlib import Path
    from i18n import I18nManager
    from tei_listwit import ListWitReport, report_notes
    tr = I18nManager(Path(__file__).resolve().parents[1] / "i18n", "fr").tr
    created = ListWitReport(added=["T1", "1760"], created=True, changed=True)
    assert report_notes(created, tr) == [tr("project.listwit.created", witnesses="T1, 1760")]
    assert "créée" in report_notes(created, tr)[0]
    added = ListWitReport(added=["T2"], changed=True)
    assert report_notes(added, tr) == [tr("project.listwit.added", witnesses="T2")]
    blocked = ListWitReport(paragraphs=["T1"], id_used=["P"])
    assert report_notes(blocked, tr) == [tr("project.listwit.id_used", witnesses="P"),
                                        tr("project.listwit.paragraphs", witnesses="T1")]


# -- Ajout bloqué, témoins non déclarés (Paramètres du projet) ---------------

def _tr_fr():
    from pathlib import Path
    from i18n import I18nManager
    return I18nManager(Path(__file__).resolve().parents[1] / "i18n", "fr").tr


def test_a_witness_that_cannot_be_declared_blocks_the_addition():
    from tei_listwit import ListWitReport, blocking_message
    tr = _tr_fr()
    assert blocking_message(ListWitReport(added=["T1"], created=True), tr, ["T1"]) is None
    assert blocking_message(ListWitReport(declared=["T1"]), tr, ["T1"]) is None
    for report, reason in ((ListWitReport(paragraphs=["T1"]), tr("project.listwit.blocked.paragraphs")),
                           (ListWitReport(no_listwit=["T1"]), tr("project.listwit.blocked.no_source_desc")),
                           (ListWitReport(malformed=["T1"]), tr("project.listwit.blocked.malformed")),
                           (ListWitReport(id_used=["T1"]), tr("project.listwit.blocked.id_used", witnesses="T1"))):
        message = blocking_message(report, tr, ["T1"])
        assert message.startswith(tr("project.listwit.blocked.intro", witnesses="T1"))
        assert reason in message and message.endswith(tr("project.listwit.blocked.outro"))


def test_undeclared_witnesses_of_the_project_are_found():
    from tei_listwit import undeclared_witnesses
    source = _tei(LISTWIT)
    t1, t2, p = WitnessDraft("T1", "x"), WitnessDraft("T2", "x"), WitnessDraft("P", "Paris")
    assert undeclared_witnesses(source, [t1, t2, p]) == [p]
    # Le <witness> d'un commentaire ne compte pas.
    commented = source.replace("</sourceDesc>", '<!-- <listWit><witness xml:id="P">P</witness></listWit> --></sourceDesc>')
    assert undeclared_witnesses(commented, [p]) == [p]
    assert undeclared_witnesses("<TEI><teiHeader>", [p]) == []      # mal formé : rien à proposer


def test_an_empty_source_description_is_enough_to_add_a_witness():
    """« Ajoutez un <sourceDesc> » : vide (donc invalide un temps), il suffit ;
    la <listWit> y est créée, et l'ajout n'est pas refusé."""
    from tei_listwit import blocking_message
    tr = _tr_fr()
    for empty in ("<sourceDesc/>", "<sourceDesc></sourceDesc>", "<sourceDesc>\n      </sourceDesc>",
                  "<sourceDesc><!-- à remplir --></sourceDesc>"):
        source = _tei("x").replace("<sourceDesc>x</sourceDesc>", empty)
        updated, report = add_witnesses_to_listwit(source, [NEW])
        assert report.created and report.added == ["1760"], empty
        assert blocking_message(report, tr, ["1760"]) is None
        root = ET.fromstring(updated.split("?>", 1)[1])
        (source_desc,) = root.iter(f"{{{TEI}}}sourceDesc")
        assert [child.tag for child in source_desc] == [f"{{{TEI}}}listWit"]
    assert "vide" in tr("project.listwit.blocked.no_source_desc")
