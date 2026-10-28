# -*- coding: utf-8 -*-
"""Aide du logiciel, dictionnaire latin, carte et boîte « À propos » de Varians."""
from __future__ import annotations

import re

from urllib.parse import quote_plus

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QKeySequence, QPixmap, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSplitter, QTextBrowser, QTextEdit, QVBoxLayout,
)
from app_context import APP_VERSION, current_i18n, HERE, tr as _t
from help_search import Section, search
from text_search import Utf16Positions


class SoftwareHelpDialog(QDialog):
    """Aide intégrée, localisée, sans navigateur embarqué pour les ressources externes.

    V0.9.2.8 : recherche dans l'aide (``help_search``). Un champ en haut
    (Ctrl+F) ; la liste des sections qui contiennent tous les mots, avec un
    extrait ; les occurrences surlignées, parcourues par ◀ ▶ (F3, Maj+F3).
    Le sommaire, fait de liens, n'est pas une section.
    """

    # Au-delà, seule l'occurrence courante est surlignée (une lettre seule
    # en donnerait des milliers).
    MAX_HIGHLIGHTS = 1000

    def __init__(self, parent=None):
        I18N = current_i18n()
        super().__init__(parent)
        self.setWindowTitle(_t("help.software"))
        self.resize(1000, 720)
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.search_box = QLineEdit(self)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setPlaceholderText(_t("help.search.placeholder"))
        self.search_prev = QPushButton("◀", self)
        self.search_next = QPushButton("▶", self)
        self.search_prev.setToolTip(_t("fragment.search.prev.tip"))
        self.search_next.setToolTip(_t("fragment.search.next.tip"))
        self.search_status = QLabel("", self)
        bar.addWidget(self.search_box, 1)
        bar.addWidget(self.search_prev)
        bar.addWidget(self.search_next)
        bar.addWidget(self.search_status)
        layout.addLayout(bar)

        self.results = QListWidget(self)
        self.results.setWordWrap(True)
        self.results.setVisible(False)
        self.browser = browser = QTextBrowser(self)
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
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.results)
        splitter.addWidget(browser)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        # Entrée dans le champ passe à l'occurrence suivante : aucun bouton
        # par défaut ne doit fermer l'aide.
        for button in (*buttons.buttons(), self.search_prev, self.search_next):
            button.setAutoDefault(False)
            button.setDefault(False)

        self.occurrences = []          # (début, fin) dans le texte de l'aide
        self.current = -1
        self._hits = []
        self._sections = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.run_search)
        self.search_box.textChanged.connect(lambda _text: self._timer.start())
        self.search_box.returnPressed.connect(self.next_occurrence)
        self.search_next.clicked.connect(self.next_occurrence)
        self.search_prev.clicked.connect(self.previous_occurrence)
        self.results.currentRowChanged.connect(self._show_section)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("F3"), self, self.next_occurrence)
        QShortcut(QKeySequence("Shift+F3"), self, self.previous_occurrence)

    def _focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _help_sections(self):
        """Les sections de l'aide : chaque titre et le texte qui le suit,
        sauf celles qui ne sont faites que de liens (le sommaire)."""
        if self._sections is None:
            document = self.browser.document()
            positions = Utf16Positions(self.browser.toPlainText())
            heads = []
            block = document.begin()
            while block.isValid():
                if block.blockFormat().headingLevel():
                    heads.append(block)
                block = block.next()
            end_of_text = document.characterCount() - 1
            sections = []
            if not heads or heads[0].position() > 0:
                sections.append(Section(self.windowTitle(), 0,
                                        positions.python(heads[0].position() if heads else end_of_text)))
            for index, head in enumerate(heads):
                end = heads[index + 1].position() if index + 1 < len(heads) else end_of_text
                if not self._links_only(head, end):
                    sections.append(Section(head.text().strip(), positions.python(head.position()),
                                            positions.python(end)))
            self._sections = sections
        return self._sections

    @staticmethod
    def _links_only(head, end):
        block = head.next()
        while block.isValid() and block.position() < end:
            fragments = block.begin()
            while not fragments.atEnd():
                fragment = fragments.fragment()
                # Un lien a une adresse ; le texte d'un élément à identifiant
                # (<section id="…">) est aussi une « ancre », mais sans adresse.
                if fragment.isValid() and fragment.text().strip() and not fragment.charFormat().anchorHref():
                    return False
                fragments += 1
            block = block.next()
        return True

    def run_search(self):
        self._timer.stop()
        query = self.search_box.text()
        text = self.browser.toPlainText()
        self._hits = search(text, self._help_sections(), query) if query.strip() else []
        self.results.blockSignals(True)
        self.results.clear()
        for hit in self._hits:
            item = QListWidgetItem(f"{hit.section.title} ({len(hit.spans)})\n{hit.excerpt}")
            item.setData(Qt.ItemDataRole.UserRole, hit.section.title)
            item.setToolTip(hit.excerpt)
            self.results.addItem(item)
        self.results.blockSignals(False)
        self.results.setVisible(bool(query.strip()))
        self.occurrences = sorted(span for hit in self._hits for span in hit.spans)
        positions = Utf16Positions(text)
        self._positions = [(positions.qt(start), positions.qt(end)) for start, end in self.occurrences]
        if not query.strip():
            self.search_status.setText("")
        elif not self._hits:
            self.search_status.setText(_t("help.search.none"))
        else:
            self.search_status.setText(_t("help.search.summary", sections=len(self._hits),
                                          count=len(self.occurrences)))
        self.current = 0 if self.occurrences else -1
        self._show_current()

    def next_occurrence(self):
        if self._timer.isActive():
            self.run_search()
            return
        if self.occurrences:
            self.current = (self.current + 1) % len(self.occurrences)
            self._show_current()

    def previous_occurrence(self):
        if self._timer.isActive():
            self.run_search()
        if self.occurrences:
            self.current = (self.current - 1) % len(self.occurrences)
            self._show_current()

    def _show_section(self, row):
        if 0 <= row < len(self._hits):
            self.current = self.occurrences.index(self._hits[row].spans[0])
            self._show_current()

    def _show_current(self):
        """Surligne les occurrences (la courante plus vivement), montre la
        courante et sélectionne sa section dans la liste."""
        document = self.browser.document()
        selections = []
        shown = range(len(self._positions)) if len(self._positions) <= self.MAX_HIGHLIGHTS else \
            ([self.current] if self.current >= 0 else [])
        for index in shown:
            start, end = self._positions[index]
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#ff9632" if index == self.current else "#fff000"))
            selection.format.setForeground(QColor("#17120b"))
            selection.cursor = QTextCursor(document)
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            selections.append(selection)
        self.browser.setExtraSelections(selections)
        if self.current < 0:
            return
        cursor = QTextCursor(document)
        cursor.setPosition(self._positions[self.current][0])
        self.browser.setTextCursor(cursor)
        self.browser.ensureCursorVisible()
        start = self.occurrences[self.current][0]
        row = next((row for row, hit in enumerate(self._hits)
                    if hit.section.start <= start < hit.section.end), -1)
        self.results.blockSignals(True)
        self.results.setCurrentRow(row)
        self.results.blockSignals(False)


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

