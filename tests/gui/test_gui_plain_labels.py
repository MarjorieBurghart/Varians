# -*- coding: utf-8 -*-
"""Red team (sécurité, C3) : l'en-tête d'un panneau de témoin montre le nom
du témoin et le libellé de la page (d'un manifeste IIIF) en texte brut. En
texte riche, « <img src="//serveur/partage/x.png"> » y faisait charger une
image, d'un partage réseau sous Windows."""
from __future__ import annotations

from PySide6.QtCore import Qt

HOSTILE = '<img src="//serveur/partage/x.png"><b>1r</b>'


def test_the_header_of_a_witness_shows_its_texts_as_plain_text(qapp, editor_module):
    from manuscript_panel import WitnessHeader

    header = WitnessHeader(HOSTILE)
    try:
        header.status.setText(HOSTILE)
        for label in (header.title, header.status):
            assert label.textFormat() == Qt.TextFormat.PlainText
            assert label.text() == HOSTILE
    finally:
        header.deleteLater()
