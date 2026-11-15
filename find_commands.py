# -*- coding: utf-8 -*-
"""Ctrl+F, F3 et Maj+F3 selon l'endroit, recherche dans le XML source (V0.9.4.7).

Mixin de ``MainWindow`` (editeur_tei.py) : les commandes de recherche
visent l'éditeur de fragment s'il a le focus, l'aperçu si son onglet est
affiché, sinon le XML source (``code_editor.find_in_plain_editor``), avec
le champ de la barre d'outils ou celui de la barre de remplacement."""
from __future__ import annotations

from app_context import tr as _t
from code_editor import find_in_plain_editor
from text_search import SearchError


class FindCommandsMixin:
    """Commandes de recherche de la fenêtre (voir le module)."""

    def focus_find(self):
        """Ctrl+F (« Recherche simple ») selon l'endroit : la barre de recherche de
        l'éditeur de fragment s'il a le focus, celle de l'aperçu si son onglet est affiché ;
        sinon le champ de recherche de la barre d'outils reçoit le focus, et
        reprend la sélection de l'éditeur XML si elle tient sur une ligne (120
        caractères au plus)."""
        # Ctrl+F est contextuel aux trois espaces d'édition/lecture.
        if self.formatted_view.focus_is_in_fragment():
            self.formatted_view.show_fragment_find()
            return
        if self.left_tabs.currentWidget() is self.formatted_view:
            self.formatted_view.show_preview_find()
            return
        selected = self.editor.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.find_box.setText(selected)
        self.find_box.setFocus()
        self.find_box.selectAll()

    def _find_source(self, backwards=False, field=None):
        # *field* : le champ de la recherche, celui de la barre d'outils ou
        # celui de la barre de remplacement (V0.9.2.8), qui garde le focus.
        box = field or self.find_box
        q = box.text()
        if not q:
            box.setFocus()
            return
        try:
            found, n, total = find_in_plain_editor(self.editor, q, backwards=backwards,
                                                   options=self.search_options(), exact=field is not None)
        except SearchError as error:
            self.statusBar().showMessage(_t("search.error.pattern", detail=error.detail), 5000)
            self.replace_status.setText("!")
            box.setFocus()
            return
        if found:
            self.left_tabs.setCurrentIndex(0)
            self.statusBar().showMessage(_t("status.search.xml.found", n=n, total=total, query=q), 2500)
        else:
            self.statusBar().showMessage(_t("status.search.xml.none", query=q), 3000)
        self.replace_status.setText(f"{n}/{total}" if found else "0/0")
        self.search_results_follow()
        # Entrée reste associée à la recherche suivante, jamais à l'édition XML.
        # La mise en évidence fluo demeure visible dans l'éditeur sans focus.
        if field is None:
            self.find_box.setFocus()
        else:
            field.setFocus()

    def find_source_next(self):
        """Occurrence suivante, dans le XML source, du texte du champ de recherche
        de la barre d'outils (touche Entrée de ce champ)."""
        self._find_source(False)

    def find_source_previous(self):
        """Occurrence précédente, dans le XML source, du texte du champ de
        recherche de la barre d'outils."""
        self._find_source(True)

    def find_next(self):
        """F3 (« Occurrence suivante ») selon l'endroit : dans l'éditeur de fragment
        s'il a le focus et que sa barre de recherche est ouverte ; dans l'aperçu si son
        onglet est affiché (sa barre de recherche fermée, elle s'ouvre seulement) ;
        sinon dans le XML source."""
        if self.formatted_view.fragment_find_bar.isVisible() and self.formatted_view.focus_is_in_fragment():
            self.formatted_view.find_fragment_next()
        elif self.left_tabs.currentWidget() is self.formatted_view:
            if not self.formatted_view.preview_find_bar.isVisible():
                self.formatted_view.show_preview_find()
            else:
                self.formatted_view.find_preview_next()
        else:
            self._find_source(False)

    def find_previous(self):
        """Shift+F3 (« Occurrence précédente ») : comme ``find_next``, en remontant."""
        if self.formatted_view.fragment_find_bar.isVisible() and self.formatted_view.focus_is_in_fragment():
            self.formatted_view.find_fragment_previous()
        elif self.left_tabs.currentWidget() is self.formatted_view:
            if not self.formatted_view.preview_find_bar.isVisible():
                self.formatted_view.show_preview_find()
            else:
                self.formatted_view.find_preview_previous()
        else:
            self._find_source(True)
