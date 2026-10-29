# -*- coding: utf-8 -*-
"""Liste automatique des pointeurs : taper « # » dans un attribut de référence
(@ref, @wit…) ouvre la liste des identifiants, sans Ctrl+Espace."""
from __future__ import annotations

from PySide6.QtCore import Qt


def _cursor_inside(window, markup, inside):
    text = window.editor.toPlainText()
    position = text.index("<body>") + len("<body>")
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(markup)
    cursor = window.editor.textCursor()
    cursor.setPosition(position + markup.index(inside) + len(inside))
    window.editor.setTextCursor(cursor)
    window.editor.setFocus()


def _popup_values(window):
    model = window.editor._value_completer.completionModel()
    return [model.index(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(model.rowCount())]


def _popup_texts(window):
    model = window.editor._value_completer.completionModel()
    return [model.index(row, 0).data() for row in range(model.rowCount())]


def _popup_visible(window):
    return window.editor._value_completer.popup().isVisible()


def test_typing_a_hash_in_a_reference_opens_the_identifier_list(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    _cursor_inside(window, '<persName ref=""></persName>', 'ref="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_visible(window)
    assert _popup_values(window) == ["personnes.xml#bernard", "personnes.xml#petrus"]
    assert any("Bernardus" in text for text in _popup_texts(window))

    qtbot.keyClicks(window.editor, "be")                     # « #be » trouve « personnes.xml#bernard »
    assert _popup_values(window) == ["personnes.xml#bernard"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert not _popup_visible(window)
    assert '<persName ref="personnes.xml#bernard"></persName>' in window.editor.toPlainText()


def test_typing_a_hash_in_rdg_wit_lists_the_witnesses(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, '<app><rdg wit=""></rdg></app>', 'wit="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_values(window) == ["#T1", "#T2", "#P"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Tab)
    assert '<rdg wit="#T1">' in window.editor.toPlainText()

    qtbot.keyClicks(window.editor, " #")                     # second pointeur de la liste
    assert _popup_values(window) == ["#T2", "#P"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert '<rdg wit="#T1 #T2">' in window.editor.toPlainText()


def test_escape_closes_the_list(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, '<lem wit=""></lem>', 'wit="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_visible(window)
    qtbot.keyClick(window.editor, Qt.Key.Key_Escape)
    assert not _popup_visible(window)
    assert '<lem wit="#">' in window.editor.toPlainText()


def test_other_attributes_open_nothing(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, '<hi rend=""></hi>', 'rend="')
    qtbot.keyClicks(window.editor, "#i")
    assert not _popup_visible(window)


def test_attribute_name_popup_is_not_disturbed(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, "<varianstest ></varianstest>", "<varianstest ")
    qtbot.keyClicks(window.editor, "k")
    assert window.editor._attribute_completer.popup().isVisible()
    assert not _popup_visible(window)


def test_identifiers_present_in_two_documents_name_their_file(open_window, project_with_documents, qtbot):
    from project_config import DocumentConfig, load_project
    from project_management import update_project_documents

    lieux = project_with_documents.parent / "xml" / "lieux.xml"
    lieux.write_text('<listPlace><place xml:id="petrus"/></listPlace>', encoding="utf-8")
    documents = list(load_project(project_with_documents).documents) + [DocumentConfig(lieux, "Lieux")]
    update_project_documents(project_with_documents, documents)
    window = open_window(project_with_documents)
    _cursor_inside(window, '<persName ref=""></persName>', 'ref="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_values(window) == ["personnes.xml#bernard", "personnes.xml#petrus"]
    qtbot.keyClicks(window.editor, "pe")
    assert _popup_values(window) == ["personnes.xml#petrus"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert '<persName ref="personnes.xml#petrus"></persName>' in window.editor.toPlainText()


def _choose_with_arrows(qtbot, popup, downs, key=Qt.Key.Key_Return):
    """Comme au clavier : la liste ouverte reçoit les flèches, puis Entrée (ou Tab)."""
    for _ in range(downs):
        qtbot.keyClick(popup, Qt.Key.Key_Down)
    qtbot.keyClick(popup, key)


def test_the_witness_chosen_with_the_arrows_is_the_one_inserted(open_window, example_project, qtbot):
    """V0.9.3.1 : Entrée insérait le premier témoin de la liste, quel que soit
    celui que les flèches avaient choisi (une erreur silencieuse dans @wit)."""
    window = open_window(example_project)
    _cursor_inside(window, '<app><rdg wit=""></rdg></app>', 'wit="')
    qtbot.keyClicks(window.editor, "#")
    popup = window.editor._value_completer.popup()
    assert _popup_values(window) == ["#T1", "#T2", "#P"]
    _choose_with_arrows(qtbot, popup, 3)
    assert not _popup_visible(window)
    assert '<rdg wit="#P">' in window.editor.toPlainText()

    qtbot.keyClicks(window.editor, " #")                     # second pointeur : #T1 et #T2 restent
    assert _popup_values(window) == ["#T1", "#T2"]
    _choose_with_arrows(qtbot, popup, 2, Qt.Key.Key_Tab)
    assert '<rdg wit="#P #T2">' in window.editor.toPlainText()


def test_the_attribute_chosen_with_the_arrows_is_the_one_inserted(qtbot):
    """Même défaut pour la liste des noms d'attributs (le schéma de test n'en
    déclare qu'un : fournisseur de noms factice)."""
    from types import SimpleNamespace
    from code_editor import CodeEditor

    names = ("wit", "witDetail", "wordCount")

    def provider(editor):
        text, position = editor.toPlainText(), editor.textCursor().position()
        start = text.rfind(" ", 0, position) + 1
        prefix = text[start:position]
        return (tuple(name for name in names if name.startswith(prefix)),
                SimpleNamespace(kind="attribute", prefix=prefix, replace_start=start, replace_end=position))

    editor = CodeEditor()
    qtbot.addWidget(editor)
    editor.attribute_completion_provider = provider
    editor.setPlainText("<rdg ></rdg>")
    cursor = editor.textCursor()
    cursor.setPosition(len("<rdg "))
    editor.setTextCursor(cursor)
    editor.show()
    editor.setFocus()
    qtbot.keyClicks(editor, "w")
    assert editor._attribute_completer.popup().isVisible()
    _choose_with_arrows(qtbot, editor._attribute_completer.popup(), 2)
    assert editor.toPlainText() == '<rdg witDetail=""></rdg>'
