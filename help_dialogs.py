# -*- coding: utf-8 -*-
"""Aide du logiciel, dictionnaire latin, carte et boîte « À propos » de Varians."""
from __future__ import annotations

import re

from urllib.parse import quote_plus

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QTextBrowser,
    QVBoxLayout,
)
from app_context import APP_VERSION, current_i18n, HERE, tr as _t


class SoftwareHelpDialog(QDialog):
    """Aide intégrée, localisée, sans navigateur embarqué pour les ressources externes."""

    def __init__(self, parent=None):
        I18N = current_i18n()
        super().__init__(parent)
        self.setWindowTitle(_t("help.software"))
        self.resize(900, 720)
        layout = QVBoxLayout(self)
        browser = QTextBrowser(self)
        language = I18N.language
        path = HERE / "help" / f"{language}.html"
        if not path.is_file():
            fallback = I18N.fallback if (HERE / "help" / f"{I18N.fallback}.html").is_file() else "fr"
            path = HERE / "help" / f"{fallback}.html"
        try:
            browser.setHtml(path.read_text(encoding="utf-8"))
        except Exception as exc:
            browser.setPlainText(str(exc))
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def _selected_text_for_dictionary(window) -> str:
    """Retourne la sélection textuelle active, ou le mot sous le curseur."""
    widget = QApplication.focusWidget()
    candidates = []
    while widget is not None:
        candidates.append(widget)
        widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None
    for name in ("editor",):
        candidate = getattr(window, name, None)
        if candidate is not None:
            candidates.append(candidate)
    formatted = getattr(window, "formatted_view", None)
    if formatted is not None:
        for name in ("fragment_editor", "preview"):
            candidate = getattr(formatted, name, None)
            if candidate is not None:
                candidates.append(candidate)
    seen = set()
    for candidate in candidates:
        if id(candidate) in seen or not hasattr(candidate, "textCursor"):
            continue
        seen.add(id(candidate))
        try:
            cursor = candidate.textCursor()
            text = cursor.selectedText()
            if not text:
                probe = QTextCursor(cursor)
                probe.select(QTextCursor.SelectionType.WordUnderCursor)
                text = probe.selectedText()
            text = re.sub(r"\s+", " ", (text or "").replace("\u2029", " ")).strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def _open_external(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def _open_latin_dictionary(window) -> None:
    query = _selected_text_for_dictionary(window)
    url = "https://www.vocabula.lat/?q=" + quote_plus(query)
    _open_external(url)


def _show_software_help(window) -> None:
    SoftwareHelpDialog(window).exec()


def _varians_font(point_size: int) -> QFont:
    """Police de marque : Cormorant Garamond SemiBold si disponible.

    Qt choisit automatiquement une police de repli si la famille n'est pas
    installée ; aucun fichier de police n'est embarqué dans Varians.
    """
    font = QFont("Cormorant Garamond", int(point_size))
    font.setStyleName("SemiBold")
    font.setWeight(QFont.Weight.DemiBold)
    return font


def _scaled_logo_label(parent, filename: str, max_w: int, max_h: int) -> QLabel:
    label = QLabel(parent)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pix = QPixmap(str(HERE / "resources" / filename))
    if not pix.isNull():
        label.setPixmap(pix.scaled(
            max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
    return label


def _build_varians_card(parent, include_dismiss_hint=False) -> QFrame:
    """Carte de marque commune à l'accueil et à « À propos… »."""
    frame = QFrame(parent)
    frame.setObjectName("variansWelcomeCard")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    frame.setStyleSheet(
        "QFrame#variansWelcomeCard { background: palette(base); "
        "border: 1px solid palette(mid); border-radius: 10px; }"
    )
    frame.setMaximumWidth(760)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(42, 32, 42, 32)
    layout.setSpacing(13)

    # Logo propre à Varians, au-dessus du nom.
    layout.addWidget(_scaled_logo_label(frame, "varians_logo.png", 300, 145),
                     0, Qt.AlignmentFlag.AlignHCenter)

    title = QLabel("Varians", frame)
    title.setFont(_varians_font(38))
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    subtitle = QLabel(_t("welcome.subtitle"), frame)
    f = subtitle.font(); f.setPointSize(15); subtitle.setFont(f)
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    layout.addWidget(subtitle)

    pi = QLabel(_t("welcome.pi"), frame)
    f = pi.font(); f.setPointSize(12); pi.setFont(f)
    pi.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(pi)

    version = QLabel(_t("welcome.version", version=APP_VERSION), frame)
    f = version.font(); f.setPointSize(11); version.setFont(f)
    version.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(version)

    institutions = QHBoxLayout()
    institutions.setSpacing(32)
    institutions.addStretch(1)
    institutions.addWidget(_scaled_logo_label(frame, "ciham.png", 190, 95))
    institutions.addWidget(_scaled_logo_label(frame, "cnrs.png", 90, 90))
    institutions.addStretch(1)
    layout.addLayout(institutions)

    if include_dismiss_hint:
        hint = QLabel(_t("welcome.dismiss"), frame)
        f = hint.font(); f.setItalic(True); f.setPointSize(9); hint.setFont(f)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
    return frame


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("help.about"))
        self.resize(790, 650)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.addStretch(1)
        root.addWidget(_build_varians_card(self, False), 0, Qt.AlignmentFlag.AlignCenter)
        root.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


def _show_about(window) -> None:
    AboutDialog(window).exec()

