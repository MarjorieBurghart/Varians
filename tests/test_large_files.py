"""Fichiers trop volumineux pour l'éditeur (large_files, sans Qt).

Varians charge un fichier entier dans l'éditeur pour l'afficher et l'analyser :
un fichier de 700 Mo ne s'ouvre jamais et bloquait le démarrage. Au-delà du
seuil, Varians demande avant d'ouvrir.
"""
from pathlib import Path

import large_files


TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude">
  <text><body>{body}</body></text>
</TEI>
"""


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_threshold_is_twenty_megabytes():
    assert large_files.LARGE_FILE_BYTES == 20 * 1024 * 1024


def test_a_file_is_large_above_the_threshold_only(tmp_path):
    small = _write(tmp_path / "petit.xml", "x" * 100)
    big = _write(tmp_path / "gros.xml", "x" * 101)
    assert not large_files.is_large(small, limit=100)
    assert large_files.is_large(big, limit=100)
    assert not large_files.is_large(tmp_path / "absent.xml", limit=100)


def test_the_threshold_is_read_at_call_time(tmp_path, monkeypatch):
    path = _write(tmp_path / "edition.xml", "x" * 50)
    monkeypatch.setattr(large_files, "LARGE_FILE_BYTES", 10)
    assert large_files.is_large(path)


def test_sizes_are_shown_in_megabytes():
    assert large_files.megabytes(700 * 1024 * 1024) == 700
    assert large_files.megabytes(20 * 1024 * 1024 + 1) == 20
    # Jamais « 0 Mo » pour un fichier signalé.
    assert large_files.megabytes(10) == 1


def test_a_small_edition_without_includes_has_no_large_file(tmp_path):
    edition = _write(tmp_path / "edition.xml", TEI.format(body="<p>texte</p>"))
    assert large_files.large_edition_files(edition, limit=10_000) == []


def test_a_large_edition_is_reported_without_being_read(tmp_path, monkeypatch):
    edition = _write(tmp_path / "edition.xml", TEI.format(body="<p>" + "x" * 500 + "</p>"))
    read = []
    original = Path.read_text

    def spy(self, *args, **kwargs):
        read.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    found = large_files.large_edition_files(edition, limit=100)
    assert found == [(edition, edition.stat().st_size)]
    assert read == []


def test_a_large_included_part_is_reported(tmp_path):
    part = _write(tmp_path / "parties" / "livre1.xml",
                  '<div xmlns="http://www.tei-c.org/ns/1.0"><p>' + "x" * 500 + "</p></div>")
    small = _write(tmp_path / "parties" / "livre2.xml",
                   '<div xmlns="http://www.tei-c.org/ns/1.0"><p>x</p></div>')
    edition = _write(tmp_path / "edition.xml", TEI.format(
        body='<xi:include href="parties/livre1.xml"/><xi:include href="parties/livre2.xml"/>'))
    assert large_files.large_edition_files(edition, limit=300) == [(part, part.stat().st_size)]
    assert small.exists()


def test_parts_included_by_parts_are_checked_once(tmp_path):
    deep = _write(tmp_path / "parties" / "chapitre.xml",
                  '<div xmlns="http://www.tei-c.org/ns/1.0"><p>' + "x" * 500 + "</p></div>")
    _write(tmp_path / "parties" / "livre.xml",
           '<div xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude">'
           '<xi:include href="chapitre.xml"/><xi:include href="chapitre.xml"/></div>')
    edition = _write(tmp_path / "edition.xml", TEI.format(body='<xi:include href="parties/livre.xml"/>'))
    assert large_files.large_edition_files(edition, limit=300) == [(deep, deep.stat().st_size)]


def test_missing_remote_and_cyclic_includes_are_ignored(tmp_path):
    edition = tmp_path / "edition.xml"
    _write(edition, TEI.format(
        body='<xi:include href="absente.xml"/>'
             '<xi:include href="https://example.org/partie.xml"/>'
             '<xi:include href="edition.xml"/>'))
    assert large_files.large_edition_files(edition, limit=10_000) == []


def test_a_missing_or_malformed_edition_has_no_large_file(tmp_path):
    assert large_files.large_edition_files(tmp_path / "absente.xml", limit=10) == []
    broken = _write(tmp_path / "edition.xml", "<TEI><text>")
    assert large_files.large_edition_files(broken, limit=10_000) == []
