# -*- coding: utf-8 -*-
"""Recherches de la vue XSLT / CSS (V0.9.4.7, extrait de formatted_view) :
rechercher dans l'aperçu (Ctrl+F, F3), rechercher et remplacer dans le
fragment, avec les options de la fenêtre (casse, expression régulière)."""
from __future__ import annotations

from PySide6.QtWidgets import QToolButton

from app_context import tr as _t
from code_editor import find_in_plain_editor, replace_all_in_plain_editor, replace_in_plain_editor
from text_search import SearchError
from preview_browser import find_in_rich_editor
from replace_bar import search_error_text


class PreviewFindMixin:
    """Recherches de ``FormattedEditionWidget`` (dont elle hérite)."""

    def show_preview_find(self):
        """Montre la barre « Rechercher dans l’aperçu : » et y met le focus (Ctrl+F dans l'onglet
        de l'aperçu). Une sélection courte de l'aperçu (une ligne, 120 caractères au plus)
        devient le texte cherché."""
        self.preview_find_bar.setVisible(True)
        selected = self.preview.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.preview_find_box.setText(selected)
        self.preview_find_box.setFocus()
        self.preview_find_box.selectAll()

    def hide_preview_find(self):
        """Bouton « ✕ » : cache la barre de recherche de l'aperçu, efface le surlignage de
        l'occurrence et rend le focus à l'aperçu."""
        self.preview_find_bar.setVisible(False)
        self.preview_find_status.setText("")
        self.preview.clearSearchMatch()
        self.preview.setFocus()

    def _find_preview(self, backwards=False):
        q = self.preview_find_box.text()
        if not q:
            self.show_preview_find()
            return
        found, n, total = find_in_rich_editor(self.preview, q, backwards=backwards)
        if found:
            self.preview_find_status.setText(f"{n}/{total}")
            self.preview_find_status.setStyleSheet("color:#5f574f")
            match = getattr(self.preview, "_search_match", None)
            pos = match[0] if match else self.preview.textCursor().position()
            line = self.preview.line_for_position(pos)
            if line is not None:
                self.preview.active_line_ordinal = line
                # Rester dans l'onglet XSLT tout en synchronisant XML et images.
                self._activate_line(line, move_xml_cursor=True)
            self.info.setText(_t("preview.search.found", n=n, total=total, query=q))
            self.info.setStyleSheet("color:#376b3c")
        else:
            self.preview_find_status.setText("0/0")
            self.preview_find_status.setStyleSheet("color:#a13d32;font-weight:600")
            self.info.setText(_t("preview.search.none", query=q))
            self.info.setStyleSheet("color:#a13d32")
        # Éviter que le bouton Suivant/Précédent conserve le focus clavier.
        self.preview_find_box.setFocus()

    def find_preview_next(self):
        """Occurrence suivante dans l'aperçu (Entrée, « ▶ », F3) : la source et les témoins vont à
        sa ligne, l'onglet de l'aperçu restant affiché. Sans texte cherché, montre la barre."""
        self._find_preview(False)

    def find_preview_previous(self):
        """Comme ``find_preview_next``, vers l'arrière (« ◀ », Maj+F3)."""
        self._find_preview(True)

    def show_fragment_find(self, replace=False):
        """Montre la ligne « Rechercher dans le fragment : » (Ctrl+F) et, avec ``replace``
        (Ctrl+H), la ligne « Remplacer par : », cachée sinon. Une sélection courte du fragment
        (une ligne, 120 caractères au plus) devient le texte cherché ; le focus va à la
        recherche."""
        # Ctrl+F : la recherche seule ; Ctrl+H (replace) : avec « Remplacer par ».
        self.fragment_find_bar.setVisible(True)
        self.fragment_replace_row.setVisible(bool(replace))
        # Si du texte est sélectionné, il devient naturellement la recherche.
        selected = self.fragment_editor.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.fragment_find_box.setText(selected)
        self.fragment_find_box.setFocus()
        self.fragment_find_box.selectAll()

    def add_fragment_find_options(self, actions):
        """Boutons des options de recherche de la fenêtre (« Aa », « .* »),
        après le champ de recherche du fragment (V0.9.2.8)."""
        layout = self._fragment_find_layout
        index = layout.indexOf(self.fragment_find_box) + 1
        for offset, action in enumerate(actions):
            button = QToolButton(self.fragment_find_bar)
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            layout.insertWidget(index + offset, button)

    def hide_fragment_find(self):
        """Bouton « × » : cache la recherche et le remplacement du fragment et rend le focus à
        l'éditeur de fragment. Le surlignage de l'occurrence trouvée, lui, reste affiché."""
        self.fragment_find_bar.setVisible(False)
        self.fragment_replace_row.setVisible(False)
        self.fragment_find_status.setText("")
        self.fragment_editor.setFocus()

    def _find_fragment(self, backwards=False):
        q = self.fragment_find_box.text()
        if not q:
            self.show_fragment_find()
            return
        try:
            # Avec la ligne « Remplacer par », le texte cherché est pris tel quel.
            found, n, total = find_in_plain_editor(self.fragment_editor, q, backwards=backwards,
                                                   options=self.main.search_options(),
                                                   exact=not self.fragment_replace_row.isHidden())
        except SearchError as error:
            self._fragment_search_error(error)
            self.fragment_find_box.setFocus()
            return
        if found:
            self.fragment_find_status.setText(f"{n}/{total}")
            self.fragment_find_status.setStyleSheet("color:#5f574f")
        else:
            self.fragment_find_status.setText("0/0")
            self.fragment_find_status.setStyleSheet("color:#a13d32;font-weight:600")
        # Même protection pour l'éditeur de fragment (il est lui aussi éditable).
        self.fragment_find_box.setFocus()

    def find_fragment_next(self):
        """Occurrence suivante dans le fragment (Entrée, « ▶ », F3), avec les options de recherche
        de la fenêtre (« Aa », « .* ») ; sans texte cherché, montre la barre. Quand la ligne
        « Remplacer par : » est visible, le texte cherché garde ses blancs du début et de la fin."""
        self._find_fragment(False)

    def replace_fragment_next(self):
        """« Remplacer » : remplace dans le fragment l'occurrence surlignée par le texte de
        « Remplacer par : », si elle correspond toujours à la recherche, puis cherche la
        suivante. Seul l'éditeur de fragment change : le XML attend « Appliquer au XML »."""
        query = self.fragment_find_box.text()
        if not query:
            self.fragment_find_box.setFocus()
            return
        try:
            _replaced, (found, n, total) = replace_in_plain_editor(
                self.fragment_editor, query, self.fragment_replace_box.text(), self.main.search_options())
        except SearchError as error:
            self._fragment_search_error(error)
            return
        self.fragment_find_status.setText(f"{n}/{total}" if found else "0/0")

    def replace_fragment_all(self):
        """« Tout remplacer » dans le fragment, en une seule étape d'annulation ; le nombre de
        remplacements s'affiche dans la barre d'état. Le XML attend « Appliquer au XML »."""
        query = self.fragment_find_box.text()
        if not query:
            self.fragment_find_box.setFocus()
            return
        try:
            count = replace_all_in_plain_editor(
                self.fragment_editor, query, self.fragment_replace_box.text(), self.main.search_options())
        except SearchError as error:
            self._fragment_search_error(error)
            return
        self.fragment_find_status.setText("")
        self.main.statusBar().showMessage(_t("replace.done", count=count), 5000)

    def _fragment_search_error(self, error):
        self.fragment_find_status.setText("!")
        self.fragment_find_status.setStyleSheet("color:#a13d32;font-weight:600")
        self.main.statusBar().showMessage(search_error_text(error), 5000)

    def find_fragment_previous(self):
        """Comme ``find_fragment_next``, vers l'arrière (« ◀ », Maj+F3)."""
        self._find_fragment(True)
