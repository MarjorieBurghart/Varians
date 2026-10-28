# -*- coding: utf-8 -*-
"""Moteur XSLT 3.0 des scénarios (xslt_engines, Saxon), sans Qt.

Jeu d'essai : « sermons » (tests/data/sermons). Saxon garde le verrou de
Python pendant une transformation : le serveur http des lectures réseau
tourne donc dans un autre processus. Tests ignorés sans Saxon, sauf celui du
message « Saxon n'est pas installé ».
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from project_config import TransformScenario, load_project
from transform_worker import run_in_process
from xslt_engines import run
from xslt_scenarios import saxon_available, scenario_request

DATA = Path(__file__).resolve().parent / "data" / "sermons"
XSL_HEAD = ('<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'
            ' xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"'
            ' exclude-result-prefixes="#all">\n')
saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    return load_project(root / "project.xml")


def _stylesheet(project, body, name="essai.xsl"):
    path = project.root_dir / "rendering" / name
    path.write_text(XSL_HEAD + body + "\n</xsl:stylesheet>\n", encoding="utf-8")
    return "rendering/" + name


def _run(project, body, output="publications/essai.html", **changes):
    # Dans le processus de transformation, comme dans Varians : sa sortie
    # d'erreur, où Saxon écrit le lieu de ses erreurs, est un fichier.
    scenario = TransformScenario("Essai", _stylesheet(project, body), output, engine="saxon", **changes)
    return run_in_process(scenario_request(scenario, project)), project.root_dir / output


def test_without_saxon_a_saxon_scenario_is_refused(project, monkeypatch):
    import xslt_engines
    monkeypatch.setitem(sys.modules, "saxonche", None)              # import saxonche → ImportError
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    scenario = TransformScenario("Essai", _stylesheet(project, '<xsl:template match="/"><r/></xsl:template>'),
                                 "publications/essai.html", engine="saxon")
    result = run(scenario_request(scenario, project))                  # dans ce processus, sans Saxon
    assert not result.ok and result.error_code == "saxon_missing"
    assert not (project.root_dir / "publications").exists()


# --- Sources ------------------------------------------------------------------------------

@saxon
def test_a_file_is_read_with_its_base_uri(project):
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:value-of select="upper-case(local-name(document(\'edition.xml\', /)/*))"/>'
                                   '</xsl:template>', source="file", file="xml/personnes.xml")
    assert result.ok, result.error
    assert result.outputs == [str(output)]
    assert output.read_text(encoding="utf-8") == "TEI"
    assert result.engine == "saxon" and result.version.startswith("SaxonC")


@saxon
def test_the_assembled_edition_keeps_the_base_uri_of_each_part(project):
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:value-of select="//tei:persName[@ref]!count(document(substring-before'
                                   '(@ref, \'#\'), .)/*)" separator=""/></xsl:template>')
    assert result.ok, result.error
    counts = output.read_text(encoding="utf-8")
    assert len(counts) >= 3 and set(counts) == {"1"}


@saxon
def test_external_entities_of_the_source_are_not_resolved(project):
    (project.root_dir / "secret.txt").write_text("SECRET", encoding="utf-8")
    (project.root_dir / "xml" / "entite.xml").write_text(
        '<!DOCTYPE a [<!ENTITY x SYSTEM "../secret.txt">]><a>&x;</a>', encoding="utf-8")
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:value-of select="."/></xsl:template>', source="file", file="xml/entite.xml")
    assert result.ok, result.error
    assert "SECRET" not in output.read_text(encoding="utf-8")


@saxon
def test_a_malformed_source_is_reported_with_its_line(project):
    (project.root_dir / "xml" / "casse.xml").write_text("<a>\n<b>\n</a>", encoding="utf-8")
    result, output = _run(project, '<xsl:template match="/"><r/></xsl:template>', source="file", file="xml/casse.xml")
    assert not result.ok and result.error_code == "source_malformed"
    assert "casse.xml:3" in result.error
    assert not output.exists()


# --- Feuille, paramètres, journal -----------------------------------------------------------

@saxon
def test_parameters_are_passed_as_strings(project):
    result, output = _run(project, '<xsl:param name="titre"/><xsl:param name="calcul"/>'
                                   '<xsl:template match="/"><r t="{$titre}" c="{$calcul}"/></xsl:template>',
                          params=(("titre", "L'index « A »"), ("calcul", "1 + 1")))
    assert result.ok, result.error
    from lxml import etree
    written = etree.fromstring(output.read_bytes())
    assert (written.get("t"), written.get("c")) == ("L'index « A »", "1 + 1")


@saxon
def test_typed_parameters_receive_untyped_values(project):
    """V0.9.2.7 : les paramètres arrivent sans type (xs:untypedAtomic),
    comme avec la ligne de commande de Saxon : « false » devient un
    booléen, « 3 » un entier, une chaîne reste une chaîne."""
    result, output = _run(project, '<xsl:param name="voir" as="xs:boolean" select="true()"/>'
                                   '<xsl:param name="n" as="xs:integer" select="0"/>'
                                   '<xsl:param name="nom" as="xs:string" select="\'\'"/>'
                                   '<xsl:template match="/"><r v="{if ($voir) then \'oui\' else \'non\'}"'
                                   ' n="{$n + 1}" nom="{$nom}"/></xsl:template>',
                          params=(("voir", "false"), ("n", "3"), ("nom", "Lettre « B »")))
    assert result.ok, result.error
    from lxml import etree
    written = etree.fromstring(output.read_bytes())
    assert (written.get("v"), written.get("n"), written.get("nom")) == ("non", "4", "Lettre « B »")


@saxon
def test_messages_are_kept_in_the_journal_even_before_a_failure(project):
    result, _output = _run(project, '<xsl:template match="/"><xsl:message>bonjour</xsl:message><r/></xsl:template>')
    assert result.ok, result.error
    assert ["message", "bonjour"] in result.journal
    result, _output = _run(project, '<xsl:template match="/"><xsl:message>avant</xsl:message>\n'
                                    '<xsl:message terminate="yes">arrêt</xsl:message></xsl:template>')
    assert not result.ok and result.error_code == "transform_failed"
    assert result.error.startswith("essai.xsl:3:")
    assert ["message", "avant"] in result.journal


@saxon
def test_an_error_of_the_stylesheet_is_reported_with_its_line(project):
    result, output = _run(project, '<xsl:template match="/">\n<xsl:value-of select="(("/>\n</xsl:template>')
    assert not result.ok and result.error_code == "xslt_invalid"
    assert result.error.startswith("essai.xsl:3: XPST0003")
    assert not output.exists()


@saxon
def test_a_runtime_error_is_reported_with_its_line(project):
    result, output = _run(project, '<xsl:template match="/">\n<r><xsl:value-of select="xs:integer(\'abc\')"/></r>\n'
                                   '</xsl:template>')
    assert not result.ok and result.error_code == "transform_failed"
    assert result.error.startswith("essai.xsl:3: FORG0001")
    assert not output.exists()


@saxon
def test_a_failed_run_keeps_the_previous_result(project):
    output = project.root_dir / "publications" / "essai.html"
    output.parent.mkdir()
    output.write_text("ancien", encoding="utf-8")
    result, _output = _run(project, '<xsl:template match="/"><xsl:message terminate="yes">arrêt</xsl:message>'
                                    '</xsl:template>')
    assert not result.ok
    assert output.read_text(encoding="utf-8") == "ancien"
    assert sorted(p.name for p in output.parent.iterdir()) == ["essai.html"]


# --- Plusieurs fichiers ------------------------------------------------------------------------

PAGES = ('<xsl:template match="/">'
         '<xsl:result-document href="pages/p1.html" method="html" html-version="5">'
         '<html><head><title>p1</title></head><body>été<br/></body></html></xsl:result-document>'
         '<xsl:result-document href="liste.txt" method="text">ligne</xsl:result-document>'
         '<html><body>sommaire</body></html></xsl:template>')


@saxon
def test_other_files_are_written_in_the_folder_of_the_result_as_the_stylesheet_says(project):
    result, output = _run(project, PAGES)
    assert result.ok, result.error
    folder = output.parent
    assert result.outputs == [str(output), str(folder / "liste.txt"), str(folder / "pages" / "p1.html")]
    page = (folder / "pages" / "p1.html").read_text(encoding="utf-8")
    assert page.startswith("<!DOCTYPE HTML>") and "<br>" in page and "été" in page      # méthode html
    assert (folder / "liste.txt").read_text(encoding="utf-8") == "ligne"
    assert sorted(p.name for p in folder.iterdir()) == ["essai.html", "liste.txt", "pages"]


@saxon
@pytest.mark.parametrize("href", ["../ailleurs.html", "{resolve-uri('/tmp/varians-ailleurs.html')}"])
def test_a_file_outside_the_folder_of_the_result_is_refused_and_nothing_is_written(project, href):
    output = project.root_dir / "publications" / "essai.html"
    output.parent.mkdir()
    output.write_text("ancien", encoding="utf-8")
    result, _output = _run(project, '<xsl:template match="/">'
                                    f'<xsl:result-document href="{href}"><x/></xsl:result-document>'
                                    '<xsl:result-document href="dedans.html"><x/></xsl:result-document>'
                                    '<r/></xsl:template>')
    assert not result.ok and result.error_code == "write_refused"
    assert "ailleurs.html" in result.error
    assert output.read_text(encoding="utf-8") == "ancien"
    assert sorted(p.name for p in output.parent.iterdir()) == ["essai.html"]
    assert not (project.root_dir / "ailleurs.html").exists()
    assert not Path("/tmp/varians-ailleurs.html").exists()


@saxon
def test_another_file_never_overwrites_a_source_of_the_project(project):
    before = (project.root_dir / "rendering" / "tei.css").read_bytes()
    result, output = _run(project, '<xsl:template match="/"><xsl:result-document href="tei.css" method="text">'
                                   'écrasé</xsl:result-document><r/></xsl:template>', output="rendering/essai.html")
    assert result.ok, result.error
    assert (project.root_dir / "rendering" / "tei.css").read_bytes() == before
    assert ["write_refused", str(project.root_dir / "rendering" / "tei.css")] in result.journal
    assert result.outputs == [str(output)]


# --- Réseau -----------------------------------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    folder = tmp_path / "www"
    folder.mkdir()
    (folder / "distant.xml").write_text("<distant>du serveur</distant>", encoding="utf-8")
    (folder / "commun.xsl").write_text(XSL_HEAD + '<xsl:template name="commun"><importe/></xsl:template>'
                                       '\n</xsl:stylesheet>', encoding="utf-8")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                                "--directory", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket() as attempt:
            if attempt.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/"
    process.terminate()
    process.wait(timeout=10)


@saxon
def test_a_stylesheet_may_read_from_the_network(project, server):
    result, output = _run(project, f'<xsl:import href="{server}commun.xsl"/><xsl:template match="/"><r>'
                                   f'<xsl:call-template name="commun"/><xsl:copy-of select="doc(\'{server}distant.xml\')"/>'
                                   '</r></xsl:template>')
    assert result.ok, result.error
    text = output.read_text(encoding="utf-8")
    assert "<importe" in text and "du serveur" in text


@saxon
def test_a_failed_network_read_stops_the_run(project, server):
    result, output = _run(project, f'<xsl:template match="/"><r n="{{count(doc(\'{server}absent.xml\'))}}"/>'
                                   '</xsl:template>')
    assert not result.ok and result.error_code == "network_failed"
    assert server + "absent.xml" in result.error
    assert not output.exists()


# --- CSS -----------------------------------------------------------------------------------------

@saxon
def test_the_css_is_copied_and_named_to_the_stylesheet_of_varians(project):
    css = project.root_dir / "rendering" / "perso.css"
    css.write_text("p { color: red }", encoding="utf-8")
    scenario = TransformScenario("Édition", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                 engine="saxon", css="rendering/perso.css")
    result = run_in_process(scenario_request(scenario, project))
    assert result.ok, result.error
    folder = project.root_dir / "publications"
    assert result.outputs == [str(folder / "edition.html"), str(folder / "perso.css")]
    assert 'href="perso.css"' in (folder / "edition.html").read_text(encoding="utf-8")


# --- Paquets DOCX, ODT, EPUB et pages HTML (V0.9.2.7) ----------------------------------------

import io
import struct
import zipfile
import zlib

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _template(path, files):
    """Une archive ``files`` (``{nom: texte}``), comme template.docx ou .odt."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return path


def _package(project, body, package, output, template=None, source_text=None, params=()):
    """Exécute la feuille ``body`` en paquet ``package`` ; ``template`` :
    l'archive du modèle, à la place de celle des TEI Stylesheets."""
    if source_text is not None:
        (project.root_dir / "xml" / "source.xml").write_text(source_text, encoding="utf-8")
    scenario = TransformScenario("Essai", _stylesheet(project, body), output, engine="saxon", package=package,
                                 params=params, **({"source": "file", "file": "xml/source.xml"}
                                                   if source_text is not None else {}))
    request = scenario_request(scenario, project)
    request["package_fixstyle"] = None
    if template is not None:
        request["package_template"] = str(template)
    return run_in_process(request), project.root_dir / output


DOCX_TEMPLATE = {
    "[Content_Types].xml": "<Types/>", "_rels/.rels": "<Relationships/>",
    "word/styles.xml": "<styles>modèle</styles>", "word/footnotes.xml": "<ancien/>",
    "word/header1.xml": "<ancien/>", "word/webSettings.xml": "<webSettings/>",
    "docProps/core.xml": "<core>ancien</core>", "docProps/app.xml": "<app/>", "docProps/custom.xml": "<ancien/>",
}
DOCX = (f'<xsl:param name="word-directory"/>'
        f'<xsl:template match="/">'
        f'<xsl:result-document href="{{$word-directory}}/word/footnotes.xml"><notes/></xsl:result-document>'
        f'<xsl:result-document href="{{$word-directory}}/docProps/newcore.xml"><core>nouveau</core>'
        f'</xsl:result-document>'
        f'<w:document xmlns:w="{W}" styles="{{doc($word-directory || \'/word/styles.xml\')}}"/>'
        f'</xsl:template>')


@saxon
def test_a_docx_package_is_built_from_its_template(project, tmp_path):
    template = _template(tmp_path / "template.docx", DOCX_TEMPLATE)
    result, output = _package(project, DOCX, "docx", "publications/edition.docx", template)
    assert result.ok, result.error
    assert result.outputs == [str(output)]
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names[0] == "[Content_Types].xml"
        # Le résultat principal, avec ce qu'il a lu du modèle déballé.
        document = archive.read("word/document.xml").decode("utf-8")
        assert "w:document" in document and 'styles="modèle"' in document
        assert archive.read("word/footnotes.xml").decode("utf-8").endswith("<notes/>")
        assert "nouveau" in archive.read("docProps/core.xml").decode("utf-8")
        assert "comments.xml" in " ".join(names) and "webSettings.xml" in " ".join(names)
        for absent in ("word/header1.xml", "docProps/custom.xml", "docProps/newcore.xml", "image-size-info.xml"):
            assert absent not in names
        assert all(info.compress_type == zipfile.ZIP_DEFLATED for info in archive.infolist())
    assert sorted(p.name for p in output.parent.iterdir()) == ["edition.docx"]


ODT = ('<xsl:param name="outputDir"/>'
       '<xsl:template match="/">'
       '<xsl:result-document href="{$outputDir}/meta.xml"><meta/></xsl:result-document>'
       '<content ancien="{doc($outputDir || \'/content.xml\')/*/@n}"/>'
       '</xsl:template>')


@saxon
def test_an_odt_package_has_its_mimetype_first_and_stored(project, tmp_path):
    template = _template(tmp_path / "template.odt", {
        "mimetype": "application/vnd.oasis.opendocument.text", "content.xml": '<content n="modèle"/>',
        "styles.xml": "<styles/>", "META-INF/manifest.xml": "<manifest/>"})
    result, output = _package(project, ODT, "odt", "publications/edition.odt", template)
    assert result.ok, result.error
    with zipfile.ZipFile(output) as archive:
        first = archive.infolist()[0]
        assert (first.filename, first.compress_type, first.extra) == ("mimetype", zipfile.ZIP_STORED, b"")
        assert archive.read("mimetype") == b"application/vnd.oasis.opendocument.text"
        assert 'ancien="modèle"' in archive.read("content.xml").decode("utf-8")
        assert archive.read("meta.xml").decode("utf-8").endswith("<meta/>")
        assert "styles.xml" in archive.namelist()


EPUB = ('<xsl:param name="directory"/>'
        '<xsl:template match="/">'
        '<xsl:result-document href="{$directory}/mimetype" method="text">application/epub+zip</xsl:result-document>'
        '<xsl:result-document href="{$directory}/META-INF/container.xml"><container/></xsl:result-document>'
        '<xsl:result-document href="{$directory}/OPS/index.html" method="html"><html><body>été</body></html>'
        '</xsl:result-document>'
        '<xsl:result-document href="{$directory}/copy.xml"><travail/></xsl:result-document>'
        '</xsl:template>')


@saxon
def test_an_epub_package_is_built_from_the_files_of_the_stylesheet(project):
    result, output = _package(project, EPUB, "epub", "publications/edition.epub")
    assert result.ok, result.error
    with zipfile.ZipFile(output) as archive:
        first = archive.infolist()[0]
        assert (first.filename, first.compress_type) == ("mimetype", zipfile.ZIP_STORED)
        assert archive.read("mimetype") == b"application/epub+zip"
        assert sorted(archive.namelist()) == ["META-INF/container.xml", "OPS/index.html", "mimetype"]
        assert "été" in archive.read("OPS/index.html").decode("utf-8")


@saxon
def test_a_package_may_not_write_outside_its_folder(project):
    output = project.root_dir / "publications" / "edition.epub"
    result, _output = _package(project, '<xsl:param name="directory"/><xsl:template match="/">'
                                        '<xsl:result-document href="{$directory}/../ailleurs.txt" method="text">x'
                                        '</xsl:result-document></xsl:template>', "epub", "publications/edition.epub")
    assert not result.ok and result.error_code == "write_refused" and "ailleurs.txt" in result.error
    assert not output.exists()


@saxon
def test_a_protected_file_is_never_replaced_by_a_package(project):
    edition = project.edition
    before = edition.read_bytes()
    result, _output = _package(project, EPUB, "epub", "xml/edition.xml")
    assert not result.ok and result.error_code == "write_refused"
    assert edition.read_bytes() == before


SPLIT = ('<xsl:param name="STDOUT"/><xsl:param name="splitLevel"/>'
         '<xsl:template match="/">'
         '<xsl:result-document href="index.html" method="html"><html><body>sommaire '
         '<xsl:value-of select="$STDOUT, $splitLevel"/></body></html></xsl:result-document>'
         '<xsl:result-document href="s1.html" method="html"><html><body>un</body></html></xsl:result-document>'
         '</xsl:template>')


@saxon
def test_pages_write_the_index_and_one_file_per_division(project):
    result, output = _package(project, SPLIT, "pages", "publications/pages/index.html")
    assert result.ok, result.error
    folder = output.parent
    assert result.outputs == [str(output), str(folder / "s1.html")]
    assert "sommaire false 0" in output.read_text(encoding="utf-8")         # STDOUT=false, splitLevel=0
    assert sorted(p.name for p in folder.iterdir()) == ["index.html", "s1.html"]
    # Un niveau de découpe choisi dans le scénario.
    result, output = _package(project, SPLIT, "pages", "publications/pages/index.html", params=(("splitLevel", "1"),))
    assert "sommaire false 1" in output.read_text(encoding="utf-8")


def _png(width, height):
    """Un PNG minimal (en-tête IHDR, une image vide) de ``width``×``height``."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\0" + b"\0" * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@saxon
def test_the_images_of_the_source_are_copied_with_their_size(project, tmp_path):
    (project.root_dir / "xml" / "figures").mkdir()
    (project.root_dir / "xml" / "figures" / "carte.png").write_bytes(_png(40, 25))
    source = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>'
              '<graphic url="figures/carte.png"/><graphic url="https://exemple.org/loin.jpg"/>'
              '</p></body></text></TEI>')
    body = (f'<xsl:param name="word-directory"/><xsl:template match="/">'
            f'<w:document xmlns:w="{W}" taille="{{doc($word-directory || \'/image-size-info.xml\')'
            f'//image[@url=\'media/resource1.png\']/(width || \'x\' || height)}}"/></xsl:template>')
    template = _template(tmp_path / "template.docx", DOCX_TEMPLATE)
    result, output = _package(project, body, "docx", "publications/edition.docx", template, source_text=source)
    assert result.ok, result.error
    with zipfile.ZipFile(output) as archive:
        assert archive.read("word/media/resource1.png") == (project.root_dir / "xml" / "figures" / "carte.png").read_bytes()
        assert 'taille="40x25"' in archive.read("word/document.xml").decode("utf-8")
    # Une image distante n'est pas téléchargée : le journal le dit.
    assert ["image_skipped", "https://exemple.org/loin.jpg"] in result.journal


# --- Pré-passage (V0.9.2.7) ---------------------------------------------------------------------

PREPARE = ('<xsl:param name="marque"/><xsl:mode on-no-match="shallow-copy"/>'
           '<xsl:template match="tei:p" xmlns:tei="http://www.tei-c.org/ns/1.0">'
           '<ab xmlns="http://www.tei-c.org/ns/1.0" n="{$marque}"><xsl:apply-templates/></ab></xsl:template>')
COUNT = ('<xsl:param name="marque"/><xsl:template match="/" xmlns:tei="http://www.tei-c.org/ns/1.0">'
         '<r p="{count(//tei:p)}" ab="{count(//tei:ab)}" n="{(//tei:ab/@n)[1]}" marque="{$marque}"'
         ' base="{base-uri(/)}"/></xsl:template>')


@saxon
def test_the_prepass_transforms_the_source_before_the_stylesheet(project):
    source = (project.root_dir / "xml" / "source.xml")
    source.write_text('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>un</p><p>deux</p></body></text></TEI>',
                      encoding="utf-8")
    result, output = _run(project, COUNT, output="publications/compte.xml", source="file", file="xml/source.xml",
                          prepare=_stylesheet(project, PREPARE, "avant.xsl"), params=(("marque", "M"),))
    assert result.ok, result.error
    text = output.read_text(encoding="utf-8")
    # Les mêmes paramètres pour les deux feuilles ; l'URI de base de la source est gardée.
    assert 'p="0" ab="2" n="M" marque="M"' in text and f'base="{source.as_uri()}"' in text


@saxon
def test_an_error_of_the_prepass_names_its_stylesheet(project):
    result, output = _run(project, COUNT, output="publications/compte.xml",
                          prepare=_stylesheet(project, '<xsl:template match="/"><xsl:value-of select="1 div 0"/>'
                                                       '</xsl:template>', "avant.xsl"))
    assert not result.ok and result.error_code == "transform_failed" and "avant.xsl" in result.error
    assert not output.exists()
