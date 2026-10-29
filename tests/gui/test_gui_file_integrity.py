# -*- coding: utf-8 -*-
"""Red team (intégrité, A6, A7) dans la fenêtre : un fichier en lecture
seule n'est pas remplacé, et le dit ; Projet ▸ Paramètres… garde le choix
du texte du viewer web."""
from __future__ import annotations

import stat

from app_context import tr
from project_config import load_project
from project_management import update_project_web_text


def test_a_read_only_edition_is_not_replaced_and_the_user_is_told(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    window = open_window(example_project)
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<body>") + len("<body>"))
    cursor.insertText("<!-- relu -->")
    before = edition.read_bytes()
    edition.chmod(stat.S_IREAD)
    messages = []
    dialogs.expect("critical", None)
    try:
        assert not window.save()
        messages = [text for kind, _title, text in dialogs.seen if kind == "critical"]
        assert edition.read_bytes() == before
    finally:
        edition.chmod(stat.S_IREAD | stat.S_IWRITE)
    expected = tr("file.save.read_only", path=edition, menu=tr("menu.file"), command=tr("toolbar.save_as"))
    assert messages == [expected] and str(edition) in expected
    assert window.modified


def test_project_settings_keep_the_web_viewer_text_choice(qapp, example_project):
    from app_context import current_i18n
    from project_dialogs import ProjectSettingsDialog

    update_project_web_text(example_project, "witness", "T2", highlight_nonlem=True)
    config = load_project(example_project)
    dialog = ProjectSettingsDialog(tr, config, [(current_i18n().language, "Langue")])
    try:
        draft = dialog.draft()
    finally:
        dialog.deleteLater()
    assert (draft.web_text_mode, draft.web_text_witness, draft.web_highlight_nonlem) == ("witness", "T2", True)
