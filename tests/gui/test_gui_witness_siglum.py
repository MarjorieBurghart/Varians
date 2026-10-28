# -*- coding: utf-8 -*-
"""Sigle d'un témoin dans les paramètres du projet (V0.9.2.8.2).

Le champ « Sigle » accepte un sigle qui n'est pas un identifiant XML
(« 1760 », « T 2 ») : la boîte montre l'identifiant XML qui en est tiré, le
témoin reçoit cet identifiant et garde son sigle. Le tableau des témoins
montre les sigles ; deux sigles qui donnent le même identifiant sont
refusés."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


@pytest.fixture
def tr(editor_module):
    from app_context import tr as translate
    return translate


def _dialog(qtbot, tr, witness=None):
    from project_dialogs import WitnessEditDialog
    dialog = WitnessEditDialog(tr, witness)
    qtbot.addWidget(dialog)
    return dialog


def test_a_siglum_that_is_not_an_identifier_gets_one(qtbot, tr):
    dialog = _dialog(qtbot, tr)
    assert dialog.xml_id_hint.isHidden()
    dialog.id_edit.setText("1760")
    assert not dialog.xml_id_hint.isHidden()
    assert dialog.xml_id_hint.text() == tr("project.witness.xml_id", id="_1760")
    dialog._accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    witness = dialog.witness()
    assert (witness.id, witness.siglum, witness.label) == ("_1760", "1760", "1760")


def test_a_valid_siglum_is_the_identifier(qtbot, tr):
    dialog = _dialog(qtbot, tr)
    dialog.id_edit.setText("T2")
    dialog.label_edit.setText("Troyes 1760")
    assert dialog.xml_id_hint.isHidden()
    dialog._accept()
    witness = dialog.witness()
    assert (witness.id, witness.siglum, witness.label) == ("T2", "", "Troyes 1760")


def test_spaces_are_accepted_but_not_an_empty_siglum(qtbot, tr, dialogs):
    dialog = _dialog(qtbot, tr)
    dialog.id_edit.setText("T 2")
    dialog._accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.witness().id == "T_2"
    dialog = _dialog(qtbot, tr)
    dialog.id_edit.setText("   ")
    dialogs.expect("warning")
    dialog._accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialogs.seen[-1][2] == tr("project.validation.witness_id")


def test_an_unchanged_siglum_keeps_the_identifier(qtbot, tr):
    from project_management import WitnessDraft
    dialog = _dialog(qtbot, tr, WitnessDraft("Troyes1760", "Troyes 1760", siglum="1760"))
    assert dialog.id_edit.text() == "1760"
    assert dialog.xml_id_hint.text() == tr("project.witness.xml_id", id="Troyes1760")
    dialog._accept()
    witness = dialog.witness()
    assert (witness.id, witness.siglum) == ("Troyes1760", "1760")
    dialog.id_edit.setText("1761")
    assert dialog.witness().id == "_1761"


def _table(qtbot, tr, witnesses, base="T1"):
    from project_dialogs import WitnessTable
    table = WitnessTable(tr, witnesses, base)
    qtbot.addWidget(table)
    return table


def _accept_with(siglum):
    def answer(dialog):
        dialog.id_edit.setText(siglum)
        dialog._accept()
        return dialog.result()
    return answer


def test_the_table_shows_the_sigla(qtbot, tr):
    from project_management import WitnessDraft
    table = _table(qtbot, tr, [WitnessDraft("T1", "Troyes 816"),
                               WitnessDraft("_1760", "Troyes 1760", siglum="1760")])
    cells = [table.table.item(row, 0) for row in range(2)]
    assert [cell.text() for cell in cells] == ["T1", "1760"]
    assert cells[0].toolTip() == ""
    assert cells[1].toolTip() == tr("project.witness.xml_id", id="_1760")
    witnesses = table.witnesses()
    assert [(w.id, w.siglum) for w in witnesses] == [("T1", ""), ("_1760", "1760")]
    assert table.base_witness() == "T1"
    table.table.selectRow(1)
    table.set_base()
    assert table.base_witness() == "_1760"


def test_two_sigla_giving_the_same_identifier_are_refused(qtbot, tr, dialogs):
    from project_management import WitnessDraft
    table = _table(qtbot, tr, [WitnessDraft("T1", "Troyes 816"),
                               WitnessDraft("T_2", "Troyes 1760", siglum="T 2")])
    dialogs.expect("dialog", _accept_with("T/2"))
    dialogs.expect("warning")
    table.add_witness()
    assert table.table.rowCount() == 2
    assert dialogs.seen[-1][2] == tr("project.validation.witness_id_collision",
                                      siglum="T/2", id="T_2", other="T 2")
    dialogs.expect("dialog", _accept_with("T 2"))
    dialogs.expect("warning")
    table.add_witness()
    assert dialogs.seen[-1][2] == tr("project.validation.duplicate_witness", id="T 2")
    dialogs.expect("dialog", _accept_with("1760"))
    table.add_witness()
    assert table.table.rowCount() == 3
    assert table.witnesses()[2].id == "_1760"


def test_editing_a_witness_keeps_the_sigla_unique(qtbot, tr, dialogs):
    from project_management import WitnessDraft
    table = _table(qtbot, tr, [WitnessDraft("T1", "Troyes 816"),
                               WitnessDraft("_1760", "Troyes 1760", siglum="1760")])
    table.table.selectRow(1)
    dialogs.expect("dialog", _accept_with("T1"))
    dialogs.expect("warning")
    table.edit_witness()
    assert table.table.item(1, 0).text() == "1760"
    dialogs.expect("dialog", _accept_with("1760 bis"))
    table.edit_witness()
    assert table.table.item(1, 0).text() == "1760 bis"
    assert table.table.item(1, 0).toolTip() == tr("project.witness.xml_id", id="_1760_bis")
    assert table.witnesses()[1].id == "_1760_bis"
    assert table.table.item(1, 0).data(Qt.ItemDataRole.UserRole) is False


def test_default_surface_ids_use_the_xml_identifier(qtbot, tr, tmp_path):
    """Les surfaces proposées pour des images locales partent de
    l'identifiant XML, comme à l'enregistrement du projet."""
    from PySide6.QtGui import QImage
    image = tmp_path / "f1.png"
    picture = QImage(20, 30, QImage.Format.Format_RGB32)
    picture.fill(0xFFFFFF)
    assert picture.save(str(image))
    dialog = _dialog(qtbot, tr)
    dialog.id_edit.setText("1760")
    dialog._append_local_image(image)
    assert dialog.local_table.item(0, 1).text() == "_1760-p0001"
    dialog.id_edit.setText("Σ")
    dialog._append_local_image(image)
    assert dialog.local_table.item(1, 1).text() == "Σ-p0002"
