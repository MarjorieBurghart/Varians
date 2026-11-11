# -*- coding: utf-8 -*-
"""Boîte « Nouveau document XML » : modèles de la TEI (ceux d'Oxygen),
« Même schéma que l'édition », modèles du dossier modeles/ du projet,
document vide d'élément racine choisi."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog

import document_templates
from app_context import tr
from document_dialogs import NewDocumentDialog
from project_config import load_project
from schema_resolution import detect_xml_models

TEI = "{http://www.tei-c.org/ns/1.0}"
RELEASE = "https://www.tei-c.org/release/xml/tei/custom/schema/relaxng/"


def _declared(project_path):
    return [(d.path, d.schema_mode, d.schema) for d in load_project(project_path).documents]


def _create(dialogs, kind, name="", path=None, root=None):
    """Réponse programmée à la boîte : choisir le modèle, le fichier (et
    l'élément racine), puis « OK ». Rend la liste des boîtes ouvertes."""
    opened = []

    def answer(dialog):
        opened.append(dialog)
        assert dialog.select_template(kind, name)
        if path is not None:
            dialog.path_edit.setText(str(path))
        if root is not None:
            dialog.root_edit.setText(root)
        dialog.accept()
        return dialog.result()

    dialogs.expect("dialog", answer)
    return opened


def _inspect(dialogs, check):
    """Réponse programmée : examiner la boîte, puis l'annuler."""
    def answer(dialog):
        check(dialog)
        return QDialog.DialogCode.Rejected
    dialogs.expect("dialog", answer)


def _children(dialog, group_text):
    for index in range(dialog.tree.topLevelItemCount()):
        item = dialog.tree.topLevelItem(index)
        if item.text(0) == group_text:
            return [item.child(i) for i in range(item.childCount())]
    raise AssertionError(group_text)


def test_the_tei_templates_are_listed_as_in_oxygen(open_window, example_project, dialogs):
    window = open_window(example_project)
    seen = {}

    def check(dialog):
        assert dialog.windowTitle() == tr("documents.new.title")
        tei = _children(dialog, tr("documents.new.group.tei", version="4.12.0"))
        seen["tei"] = [item.text(0) for item in tei]
        top = [dialog.tree.topLevelItem(i).text(0) for i in range(dialog.tree.topLevelItemCount())]
        seen["top"] = top

    _inspect(dialogs, check)
    assert not window.new_document_dialog()
    assert seen["tei"] == [template.name for template in document_templates.tei_templates()]
    assert len(seen["tei"]) == 21
    assert seen["top"] == [
        tr("documents.new.edition"),
        tr("documents.new.group.project", folder="modeles"),
        tr("documents.new.group.tei", version="4.12.0"),
        tr("documents.new.empty"),
    ]
    assert window.documents == [window.edition_session]


def test_a_tei_template_creates_a_declared_document_with_its_schema(open_window, example_project, dialogs):
    window = open_window(example_project)
    target = example_project.parent / "xml" / "lite.xml"
    _create(dialogs, "tei", "Lite", target)
    assert window.new_document_dialog()
    text = target.read_text(encoding="utf-8")
    assert text == document_templates.tei_template_text(document_templates.tei_template("Lite"))
    assert [m.href for m in detect_xml_models(text)] == [RELEASE + "tei_lite.rng"] * 2
    assert _declared(example_project) == [(target, "auto", None)]
    assert window.document.path == target and not window.document.modified
    assert window.editor.toPlainText() == text


def test_the_dialog_opens_on_the_edition_schema_and_a_free_file_name(open_window, example_project, dialogs):
    window = open_window(example_project)
    (example_project.parent / "xml" / "nouveau.xml").write_text("<x/>", encoding="utf-8")
    seen = {}

    def check(dialog):
        seen["template"] = dialog.selected_template()
        seen["path"] = dialog.path_edit.text()
        seen["schema"] = dialog.schema_label.text()
        seen["preview"] = dialog.preview.toPlainText()
        seen["root_enabled"] = dialog.root_edit.isEnabled()

    _inspect(dialogs, check)
    window.new_document_dialog()
    assert seen["template"].kind == "edition"
    assert seen["path"] == str(example_project.parent / "xml" / "nouveau_2.xml")
    assert seen["schema"] == tr("documents.new.schema", schema="test.rng")
    assert seen["preview"].startswith('<?xml version="1.0" encoding="UTF-8"?>\n<?xml-model href="test.rng"')
    assert not seen["root_enabled"]


def test_the_edition_schema_follows_the_new_document(open_window, example_project, dialogs):
    window = open_window(example_project)
    target = example_project.parent / "autorites" / "lieux.xml"
    _create(dialogs, "edition", path=target)
    assert window.new_document_dialog()
    text = target.read_text(encoding="utf-8")
    assert [m.href for m in detect_xml_models(text)] == ["../xml/test.rng"]
    assert ET.fromstring(text.encode("utf-8")).tag == TEI + "TEI"
    assert _declared(example_project) == [(target, "auto", None)]


def test_with_the_project_schema_the_document_is_declared_with_it(open_window, example_project, dialogs):
    schema = example_project.parent / "xml" / "test.rng"
    project_text = example_project.read_text(encoding="utf-8")
    example_project.write_text(project_text.replace(
        '<schema type="relaxng" source="xml-model" />',
        '<schema type="relaxng" source="project" file="xml/test.rng" />'), encoding="utf-8")
    assert load_project(example_project).schema_mode == "file"
    window = open_window(example_project)
    target = example_project.parent / "xml" / "lieux.xml"
    seen = []
    opened = _create(dialogs, "edition", path=target)
    assert window.new_document_dialog()
    seen.append(opened[0].schema_label.text())
    assert seen == [tr("documents.new.schema.project", schema="test.rng")]
    assert _declared(example_project) == [(target, "file", schema)]


def test_without_an_edition_schema_the_entry_is_disabled(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace(text[text.index("<?xml-model"):text.index("?>", text.index("<?xml-model")) + 2],
                                    ""), encoding="utf-8")
    window = open_window(example_project)
    seen = {}

    def check(dialog):
        item = dialog.tree.topLevelItem(0)
        seen["enabled"] = bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)
        seen["tip"] = item.toolTip(0)
        seen["template"] = dialog.selected_template()
        seen["select"] = dialog.select_template("edition")

    _inspect(dialogs, check)
    window.new_document_dialog()
    assert not seen["enabled"] and seen["tip"] == tr("documents.new.edition.none")
    assert seen["template"] == document_templates.tei_template("All")
    assert seen["select"] is False


def test_project_templates_come_from_the_modeles_folder(open_window, example_project, dialogs):
    folder = example_project.parent / "modeles"
    folder.mkdir()
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<?xml-model href="../xml/test.rng" type="application/xml" '
             'schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
             '<listPlace xmlns="http://www.tei-c.org/ns/1.0"><place xml:id="paris"/></listPlace>\n')
    (folder / "lieux.xml").write_text(model, encoding="utf-8")
    window = open_window(example_project)
    target = example_project.parent / "xml" / "lieux.xml"
    opened = _create(dialogs, "project", "lieux", target)
    assert window.new_document_dialog()
    names = [item.text(0) for item in _children(opened[0], tr("documents.new.group.project", folder="modeles"))]
    assert names == ["lieux"]
    assert target.read_text(encoding="utf-8") == model.replace("../xml/test.rng", "test.rng")
    assert _declared(example_project) == [(target, "auto", None)]


def test_without_project_templates_the_group_explains_the_folder(open_window, example_project, dialogs):
    window = open_window(example_project)
    seen = {}

    def check(dialog):
        children = _children(dialog, tr("documents.new.group.project", folder="modeles"))
        seen["texts"] = [item.text(0) for item in children]
        seen["enabled"] = [bool(item.flags() & Qt.ItemFlag.ItemIsEnabled) for item in children]

    _inspect(dialogs, check)
    window.new_document_dialog()
    assert seen == {"texts": [tr("documents.new.project.empty", folder="modeles")], "enabled": [False]}


@pytest.mark.parametrize("root, tag", [
    ("listPlace", "listPlace"),
    ("TEI", TEI + "TEI"),
])
def test_an_empty_document_has_the_root_given(open_window, example_project, dialogs, root, tag):
    window = open_window(example_project)
    target = example_project.parent / "xml" / "lieux.xml"
    _create(dialogs, "empty", path=target, root=root)
    assert window.new_document_dialog()
    assert ET.parse(target).getroot().tag == tag
    assert _declared(example_project) == [(target, "auto", None)]
    assert window.document.path == target and not window.document.modified


def test_an_invalid_root_name_keeps_the_dialog_open(open_window, example_project, dialogs):
    window = open_window(example_project)
    target = example_project.parent / "xml" / "lieux.xml"
    opened = _create(dialogs, "empty", path=target, root="1 lieu")
    dialogs.expect("warning")
    assert not window.new_document_dialog()
    assert dialogs.seen[-1][2] == tr("documents.new.root_invalid", name="1 lieu")
    assert opened[0].result() != QDialog.DialogCode.Accepted
    assert not target.exists()
    assert _declared(example_project) == []


def test_an_existing_file_is_never_replaced(open_window, project_with_documents, dialogs):
    existing = project_with_documents.parent / "xml" / "personnes.xml"
    before = existing.read_text(encoding="utf-8")
    window = open_window(project_with_documents)
    _create(dialogs, "tei", "Lite", existing)
    dialogs.expect("warning")
    assert not window.new_document_dialog()
    assert existing.read_text(encoding="utf-8") == before


def test_a_name_without_extension_gets_xml(open_window, example_project, dialogs):
    window = open_window(example_project)
    _create(dialogs, "tei", "Bare", example_project.parent / "xml" / "nu")
    assert window.new_document_dialog()
    assert (example_project.parent / "xml" / "nu.xml").is_file()


def test_the_browse_button_chooses_the_file(open_window, example_project, dialogs, monkeypatch):
    window = open_window(example_project)
    chosen = example_project.parent / "xml" / "choisi.xml"
    asked = []

    def answer(*args, **kwargs):
        asked.append(args)
        return str(chosen), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(answer))
    seen = {}

    def check(dialog):
        dialog.browse_button.click()
        seen["path"] = dialog.path_edit.text()

    _inspect(dialogs, check)
    window.new_document_dialog()
    assert seen["path"] == str(chosen)
    assert asked and asked[0][1] == tr("documents.new.title")


def test_choosing_a_template_shows_its_schema_and_contents(open_window, example_project, dialogs):
    window = open_window(example_project)
    seen = {}

    def check(dialog):
        dialog.select_template("tei", "Manuscript description")
        seen["schema"] = dialog.schema_label.text()
        seen["preview"] = dialog.preview.toPlainText()
        seen["root"] = dialog.root_edit.isEnabled()
        dialog.select_template("empty")
        seen["empty_root"] = dialog.root_edit.isEnabled()
        seen["empty_schema"] = dialog.schema_label.text()

    _inspect(dialogs, check)
    window.new_document_dialog()
    assert seen["schema"] == tr("documents.new.schema", schema="tei_ms.rng")
    assert "<msIdentifier>" in seen["preview"] and RELEASE + "tei_ms.rng" in seen["preview"]
    assert not seen["root"] and seen["empty_root"]
    assert seen["empty_schema"] == tr("documents.new.schema.none")


def test_the_dialog_class_is_the_one_shown(open_window, example_project, dialogs):
    window = open_window(example_project)
    _inspect(dialogs, lambda dialog: None)
    window.new_document_dialog()
    assert dialogs.seen[-1][2] == NewDocumentDialog.__name__
