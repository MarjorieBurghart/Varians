# -*- coding: utf-8 -*-
"""Red team (sécurité, D2, D3) : ce qu'un fichier reçu ou un manifeste IIIF
désigne ne fait pas sortir de fichier de l'ordinateur, ni n'ouvre de partage
réseau.

- D2 : l'export du viewer web copiait dans web_output/images tout fichier
  qu'un JSON d'alignement désignait comme image, même hors du projet (notes,
  clés…) : seules les images y vont désormais.
- D3 : un manifeste IIIF pouvait désigner une image « file:// », lue sur
  l'ordinateur, ou sur un partage réseau (sous Windows, avec les
  identifiants de la session) : seules les adresses web sont gardées."""
from __future__ import annotations

import json

from corpus_data import copy_example
from iiif_manifest import parse_manifest
from web_viewer.generator import generate

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")


def test_the_web_export_copies_only_images(tmp_path):
    project = copy_example(tmp_path / "exemple")
    secret = tmp_path / "ailleurs" / "notes.txt"
    secret.parent.mkdir()
    secret.write_bytes(b"SECRET 1234\n")
    picture = tmp_path / "ailleurs" / "photo.png"
    picture.write_bytes(PNG)
    alignment = project.parent / "alignments" / "T1.json"
    data = json.loads(alignment.read_text(encoding="utf-8"))
    data["pages"][0]["image"] = {"type": "file", "path": str(secret), "label": "p1"}
    data["pages"][1]["image"] = {"type": "file", "path": str(picture), "label": "p2"}
    alignment.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    _output, _missing, dataset = generate(project)
    copied = [path for path in (project.parent / "web_output").rglob("*") if path.is_file()]
    assert not [path for path in copied if path.read_bytes().startswith(b"SECRET")]
    assert [path for path in copied if path.read_bytes() == PNG]
    problems = [(w["problem"], w["filename"]) for w in dataset["meta"]["export_warnings"]]
    assert ("local_image_not_image", "notes.txt") in problems


def _manifest(image):
    url = "https://bibliotheque.example.org/iiif/ms/manifest.json"
    return {"@context": "http://iiif.io/api/presentation/2/context.json", "@id": url, "label": "Ms",
            "sequences": [{"canvases": [
                {"@id": url + "/c1", "label": "1r", "width": 10, "height": 10,
                 "images": [{"resource": {"@id": image, "width": 10, "height": 10}}]},
                {"@id": url + "/c2", "label": "1v", "width": 10, "height": 10,
                 "images": [{"resource": {"@id": "https://bibliotheque.example.org/2.jpg"}}]}]}]}


def test_a_manifest_keeps_only_web_images():
    for image in ("file:///etc/passwd", "file://serveur/partage/x.jpg", "FILE:////serveur/partage/x.jpg",
                  "ftp://serveur/x.jpg", "data:image/png;base64,AAAA"):
        manifest = parse_manifest(_manifest(image), "https://bibliotheque.example.org/iiif/ms/manifest.json")
        assert [page["label"] for page in manifest.pages] == ["1v"], image
    manifest = parse_manifest(_manifest("https://bibliotheque.example.org/1.jpg"), "")
    assert [page["label"] for page in manifest.pages] == ["1r", "1v"]
