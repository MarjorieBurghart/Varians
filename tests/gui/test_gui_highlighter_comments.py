# -*- coding: utf-8 -*-
"""Coloration : un commentaire sur plusieurs lignes est coloré comme un
commentaire de bout en bout, balises comprises (le mode d'emploi de la
<listWit>, dans le <sourceDesc> d'une transcription sans témoin, en
contient un exemple) ; les balises qui le suivent sont colorées comme des
balises."""
from __future__ import annotations

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QPlainTextDocumentLayout

import code_editor

TEXT = """<sourceDesc>
  <!--
    Exemple :
    <listWit>
      <witness xml:id="A">Paris</witness>
    </listWit>
  -->
  <bibl><!-- Décrivez ici la source. --></bibl>
</sourceDesc>"""


def _colors(document):
    """``{(ligne, colonne): couleur}`` des caractères colorés."""
    colors = {}
    block = document.firstBlock()
    while block.isValid():
        for fmt in block.layout().formats():
            for column in range(fmt.start, fmt.start + fmt.length):
                colors[(block.blockNumber(), column)] = fmt.format.foreground().color().name()
        block = block.next()
    return colors


def _document(qapp, text):
    document = QTextDocument()
    # Comme les documents de la fenêtre (document_tabs._load_session_text).
    document.setDocumentLayout(QPlainTextDocumentLayout(document))
    document.setPlainText(text)
    highlighter = code_editor.XMLHighlighter(document)
    highlighter.rehighlight()
    return document, highlighter


def test_a_comment_on_several_lines_is_colored_as_a_comment(qapp):
    document, highlighter = _document(qapp, TEXT)
    colors = _colors(document)
    comment, tag = highlighter.comment_fmt.foreground().color().name(), highlighter.tag_fmt.foreground().color().name()
    lines = TEXT.split("\n")
    # Dans le commentaire, une balise reste couleur de commentaire.
    assert colors[(3, lines[3].index("<listWit>"))] == comment
    assert colors[(4, lines[4].index("xml:id"))] == comment
    assert colors[(6, lines[6].index("-->"))] == comment
    # Après lui, les balises sont des balises.
    assert colors[(7, lines[7].index("<bibl>"))] == tag
    assert colors[(7, lines[7].index("<!--"))] == comment
    assert colors[(8, 0)] == tag


def test_closing_the_comment_earlier_recolors_the_following_lines(qapp):
    document, highlighter = _document(qapp, TEXT)
    tag = highlighter.tag_fmt.foreground().color().name()
    cursor = document.find("<!--")
    assert not cursor.isNull()
    cursor.insertText("<!-- -->")         # le commentaire se ferme sur sa ligne
    colors = _colors(document)
    line = document.toPlainText().split("\n")[3]
    assert colors[(3, line.index("<listWit>"))] == tag
