# -*- coding: utf-8 -*-
"""Red team (intégrité, A5 à A8) : enregistrer ne doit rien abîmer d'autre
que ce qu'on enregistre.

- A5 : project.xml était réécrit sur place ; un disque plein le laissait
  tronqué, illisible au démarrage suivant.
- A6 : Projet ▸ Paramètres… perdait le choix du texte du viewer web
  (``text``, ``textWitness``, ``highlightNonLem`` de <webViewer>).
- A7 : un fichier enregistré passait aux droits 0600 ; un fichier en lecture
  seule était remplacé sans un mot.
- A8 : les fins de ligne CRLF d'un fichier devenaient LF ; les commentaires
  de project.xml (avant l'élément racine, et partout pour la langue de
  l'interface) disparaissaient."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from corpus_data import copy_example
from project_config import load_project, update_project_language
from project_management import update_project_web_text, update_project_xpath_queries, write_project_xml
from save_io import ReadOnlyFileError, atomic_write_text_with_backup

ROOT = Path(__file__).resolve().parents[1]
posix = pytest.mark.skipif(os.name != "posix", reason="droits POSIX")


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


@posix
def test_saving_keeps_the_permissions_of_the_file(tmp_path):
    path = tmp_path / "edition.xml"
    path.write_text("<TEI/>", encoding="utf-8")
    path.chmod(0o664)
    atomic_write_text_with_backup(path, "<TEI>x</TEI>")
    assert path.read_text(encoding="utf-8") == "<TEI>x</TEI>" and _mode(path) == 0o664


@posix
def test_a_new_file_gets_the_usual_permissions(tmp_path):
    mask = os.umask(0)
    os.umask(mask)
    path = tmp_path / "nouveau.xml"
    atomic_write_text_with_backup(path, "<TEI/>")
    assert _mode(path) == 0o666 & ~mask


def test_a_read_only_file_is_not_overwritten(tmp_path):
    path = tmp_path / "edition.xml"
    path.write_text("<TEI/>", encoding="utf-8")
    path.chmod(stat.S_IREAD)
    try:
        with pytest.raises(ReadOnlyFileError):
            atomic_write_text_with_backup(path, "<TEI>x</TEI>")
        assert path.read_text(encoding="utf-8") == "<TEI/>"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["edition.xml"]
    finally:
        path.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_crlf_line_endings_are_kept(tmp_path):
    crlf, lf = tmp_path / "crlf.xml", tmp_path / "lf.xml"
    crlf.write_bytes(b"<TEI>\r\n<text/>\r\n</TEI>\r\n")
    lf.write_bytes(b"<TEI>\n<text/>\n</TEI>\n")
    atomic_write_text_with_backup(crlf, "<TEI>\n<text>x</text>\n</TEI>\n")
    atomic_write_text_with_backup(lf, "<TEI>\n<text>x</text>\n</TEI>\n")
    assert crlf.read_bytes() == b"<TEI>\r\n<text>x</text>\r\n</TEI>\r\n"
    assert lf.read_bytes() == b"<TEI>\n<text>x</text>\n</TEI>\n"


@pytest.mark.skipif(not hasattr(os, "fork") or sys.platform == "darwin", reason="RLIMIT_FSIZE (Linux)")
def test_a_full_disk_never_leaves_project_xml_truncated(tmp_path):
    project = copy_example(tmp_path / "exemple")
    before = project.read_bytes()
    script = ("import resource, signal, sys\n"
              f"sys.path[:0] = [{str(ROOT)!r}, {str(ROOT / 'tests')!r}]\n"
              "from project_config import DocumentConfig\n"
              "from project_management import update_project_documents\n"
              "signal.signal(signal.SIGXFSZ, signal.SIG_IGN)\n"
              "soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)\n"
              f"resource.setrlimit(resource.RLIMIT_FSIZE, ({len(before) + 50}, hard))\n"
              f"path = {str(project)!r}\n"
              "documents = [DocumentConfig(path.replace('project.xml', f'xml/doc{i}.xml'), f'Document {i}') for i in range(5)]\n"
              "try:\n    update_project_documents(path, documents)\nexcept OSError:\n    print('refusé')\n")
    completed = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, timeout=120)
    assert "refusé" in completed.stdout, completed.stderr
    assert project.read_bytes() == before
    load_project(project)
    assert not [p.name for p in project.parent.iterdir() if p.name.startswith(".project.xml.")]


def _with_comments(project):
    text = project.read_text(encoding="utf-8")
    text = text.replace("<teiManuscriptProject", "<!-- Projet ANR : ne pas modifier sans accord -->\n"
                                                  "<teiManuscriptProject", 1)
    text = text.replace("<witnesses", "<!-- T2 : sigle provisoire -->\n  <witnesses", 1)
    project.write_text(text + "\n<!-- fin -->\n", encoding="utf-8")


@pytest.mark.parametrize("update", [
    lambda path: update_project_language(path, "en"),
    lambda path: update_project_xpath_queries(path, []),
    lambda path: update_project_web_text(path, "witness", "T2"),
], ids=["langue", "requêtes", "viewer"])
def test_updates_of_project_xml_keep_its_comments_and_a_backup(tmp_path, update):
    project = copy_example(tmp_path / "exemple")
    _with_comments(project)
    before = project.read_bytes()
    update(project)
    text = project.read_text(encoding="utf-8")
    assert text.startswith("<?xml version='1.0' encoding='utf-8'?>\n<!-- Projet ANR : ne pas modifier sans accord -->\n"
                           "<teiManuscriptProject")
    assert "<!-- T2 : sigle provisoire -->" in text and text.endswith("</teiManuscriptProject>\n<!-- fin -->")
    assert project.with_suffix(".xml.bak").read_bytes() == before
    load_project(project)


def test_rewriting_project_xml_keeps_the_web_viewer_text_choice(tmp_path):
    from project_management import ProjectDraft
    from dataclasses import fields

    project = copy_example(tmp_path / "exemple")
    update_project_web_text(project, "witness", "T2", highlight_nonlem=True)
    config = load_project(project)
    names = {field.name for field in fields(ProjectDraft)}
    assert {"web_text_mode", "web_text_witness", "web_highlight_nonlem"} <= names
    draft = _draft_of(config)
    write_project_xml(project, draft)
    after = load_project(project)
    assert (after.web_text_mode, after.web_text_witness, after.web_highlight_nonlem) == ("witness", "T2", True)


def _draft_of(config):
    """Le brouillon d'un projet tel que l'écrit Projet ▸ Paramètres…"""
    from project_management import ProjectDraft, WitnessDraft

    witnesses = [WitnessDraft(id=w.id, label=w.label) for w in config.witnesses]
    return ProjectDraft(
        title=config.title, edition=config.edition, language=config.language,
        fallback_language=config.fallback_language, translations_dir=config.translations_dir,
        xslt=config.xslt, css=config.css, custom_elements=config.custom_elements,
        web_output_dir=config.web_output_dir, web_filename=config.web_filename,
        witnesses=witnesses, base_witness=config.base_witness,
        web_text_mode=config.web_text_mode, web_text_witness=config.web_text_witness,
        web_highlight_nonlem=config.web_highlight_nonlem)
