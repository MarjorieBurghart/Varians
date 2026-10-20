# -*- coding: utf-8 -*-
"""Un project.xml dont le témoin pivot est inconnu : le message s'affiche dans
la langue de l'interface."""
from __future__ import annotations

from app_context import tr


def _bad_project(example_project):
    bad = example_project.parent / "pivot_inconnu.xml"
    bad.write_text(example_project.read_text(encoding="utf-8").replace(
        '<witnesses base="T1">', '<witnesses base="Z">'), encoding="utf-8")
    return bad


def test_unknown_pivot_is_reported_in_the_interface_language(open_window, example_project, dialogs,
                                                             editor_module, qtbot):
    window = open_window(example_project)
    bad = _bad_project(example_project)

    dialogs.expect("critical")
    assert window._replace_with_project(bad) is False
    expected = tr("project.error.unknown_pivot", witness="Z", witnesses="T1, T2, P")
    assert dialogs.seen[-1] == ("critical", tr("project.open_error"), expected)
    assert expected.startswith("Témoin pivot inconnu")

    window._set_language_code("en")
    welcome = editor_module.WelcomeWindow()                  # « Ouvrir un projet… » de l'accueil
    qtbot.addWidget(welcome)
    dialogs.expect("critical")
    assert welcome._open_project_path(bad) is False
    assert dialogs.seen[-1][2].startswith("Unknown pivot witness")
