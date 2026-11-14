# -*- coding: utf-8 -*-
"""Vue XSLT / CSS : aperçu mis en forme du document affiché (l'édition ou un
document XML du projet), synchronisé avec la source, et édition par
fragments. Chaque document a la vue du projet et ses vues nommées
(project.xml, ``<view>``), choisies dans une liste (V0.9.4.4)."""
from __future__ import annotations

import hashlib
import html as html_lib
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMenu, QMessageBox, QPushButton, QSizePolicy, QSplitter, QToolButton,
    QVBoxLayout, QWidget,
)
from app_context import _settings, call_later, tr as _t
from code_editor import CodeEditor, find_in_plain_editor
from completion_ui import CompletionDialog
from custom_completion import load_custom_completion
from text_search import SearchError
from code_editor import replace_all_in_plain_editor, replace_in_plain_editor
from fragment_units import (
    edit_stylesheet, edit_stylesheet_url, mark_units, place_edit_markers, stylesheet_needs_saxon,
)
from formatted_views import ViewsMixin
from fragment_editor import FragmentEditorMixin
from preview_browser import ClickablePreview, find_in_rich_editor
from preview_css import PREVIEW_BASE_CSS, resolve_css_variables, resolve_style_variables
from replace_bar import search_error_text
from xslt_engines import xslt_error_text as _xslt_error_text


def _selection_xml_to_visible_text(fragment):
    """Convertit une sélection brute de la source XML en texte visible approché.

    Cette fonction sert uniquement au transfert de sélection XML -> aperçu.
    Les ``lb break="no"`` ne produisent aucun espace ; les autres ``lb``
    produisent un espace, comme dans la XSLT de l'éditeur. Les autres balises
    sont retirées.
    """
    text = (fragment or "").replace("\u2029", "\n").replace("\u2028", "\n")
    lb = r"<(?:[A-Za-z_][\w.-]*:)?lb\b[^>]*?/?>"
    break_no = r"<(?:[A-Za-z_][\w.-]*:)?lb\b(?=[^>]*\bbreak\s*=\s*[\"']no[\"'])[^>]*?/?>"
    # Un saut de ligne d'indentation autour d'un break=no ne doit pas devenir
    # un espace visible. On absorbe donc le blanc immédiatement adjacent.
    text = re.sub(r"\s*" + break_no + r"\s*", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\s*" + lb + r"\s*", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text, flags=re.DOTALL)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def xml_selection_structure(xml_text, selection_start, selection_end, units, words=3):
    """Repère structurel d'une sélection de la source (V0.9.3.0), pour
    l'aperçu, quand son texte n'y apparaît pas tel quel (élément entier choisi
    par une recherche XPath, leçons d'un apparat, note…). ``units`` : les
    éléments modifiables de la source, ``(rang dans l'aperçu, début, fin)``.

    Renvoie le premier et le dernier élément touchés (``first``, ``last``),
    si la sélection couvre le début du premier et la fin du dernier
    (``from_start``, ``to_end``), ses premiers et derniers mots visibles
    (``head``, ``tail``) et leur décalage visible dans leur élément
    (``head_relative``, ``tail_relative``) ; None si elle ne touche aucun
    élément modifiable ou n'a pas de texte."""
    start, end = int(selection_start), int(selection_end)
    touched = [(index, a, b) for index, a, b in units if a < end and b > start]
    visible = _selection_xml_to_visible_text(xml_text[start:end]).split()
    if not touched or not visible:
        return None
    first, fa, fb = touched[0]
    last, la, lb = touched[-1]
    return {
        "first": first, "last": last, "from_start": start <= fa, "to_end": end >= lb,
        "head": " ".join(visible[:words]), "tail": " ".join(visible[-words:]),
        "head_relative": len(_selection_xml_to_visible_text(xml_text[fa:max(fa, start)])),
        "tail_relative": len(_selection_xml_to_visible_text(xml_text[la:min(end, lb)])),
    }


LINE_MARKER_RE = re.compile(
    r'(<a\b(?=[^>]*\bclass=["\'][^"\']*\btei-line-marker\b[^"\']*["\'])'
    r'(?=[^>]*\bhref=["\']tei-line://base/(\d+)["\'])[^>]*>)(?:\s|\u2060|&#8288;)*</a>',
    re.IGNORECASE,
)


def make_line_segments_clickable(html_text):
    """Numérote puis préserve les repères du témoin pivot invisibles en temps linéaire.

    La XSLT écrit volontairement ``tei-line://base/INDEX`` au lieu de calculer
    ``count(preceding::tei:lb...)`` pour chaque ligne. Ce dernier calcul rendait
    la transformation presque quadratique. Ici, Python numérote les marqueurs
    0,1,2... en un seul passage, puis le QTextDocument les utilise comme repères
    invisibles pour les clics et la synchronisation des trois manuscrits.
    """
    counter = 0

    def number_placeholder(m):
        nonlocal counter
        n = counter
        counter += 1
        quote = m.group(1)
        return f'href={quote}tei-line://base/{n}{quote}'

    html_text = re.sub(
        r'href=(["\'])tei-line://base/INDEX\1',
        number_placeholder,
        html_text,
        flags=re.IGNORECASE,
    )

    lines = set()

    def repl(m):
        lines.add(int(m.group(2)))
        return m.group(1) + '&#8288;</a>'

    out = LINE_MARKER_RE.sub(repl, html_text)
    return out, len(lines), 0


_LXML_TRANSFORM_CACHE = {}

def lxml_available():
    """True si lxml s'importe. Sans lui, l'aperçu passe par PowerShell/.NET
    (``_transform_without_lxml``) et l'actualisation automatique attend plus longtemps."""
    try:
        import lxml.etree  # noqa: F401
        return True
    except Exception:
        return False


def publication_params():
    """Langue de l'interface et catalogues i18n, où la feuille de Varians
    lit ses textes (V0.9.3.1)."""
    from app_context import current_i18n
    from xslt_scenarios import catalogs_uri
    i18n = current_i18n()
    language = i18n.language if i18n is not None else "fr"
    return {"langue": language, "catalogues": catalogs_uri(language)}


def transform_with_xslt(xml_text, xsl_path, params=None, edit_markers=False, cache=None):
    """Transformation XSLT 1.0 optimisée.

    Avec lxml, la feuille XSLT compilée est mise en cache tant que le fichier
    n'a pas changé ; une erreur de la feuille ou de la transformation est
    signalée telle quelle. Le moteur .NET/PowerShell ne sert que de secours si
    lxml n'est pas installé.

    Avec ``edit_markers`` (V0.9.2.9), la feuille est importée par l'enveloppe
    de ``fragment_units.edit_stylesheet`` : les éléments numérotés par
    ``mark_units`` reçoivent leur crayon ✎, quelle que soit la feuille.

    *cache* : les feuilles compilées, propres à un fil (red team 2, A8) ; par
    défaut, celles du fil de la fenêtre. Un document très imbriqué est lu
    (huge_tree, red team 2, A10).
    """
    cache = _LXML_TRANSFORM_CACHE if cache is None else cache
    try:
        from lxml import etree as LET
    except ImportError as exc:
        return _transform_without_lxml(xml_text, xsl_path, params, exc, edit_markers)
    try:
        parser = LET.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=True)
        xml_doc = LET.fromstring(xml_text.encode("utf-8"), parser=parser)
        xp = Path(xsl_path).resolve()
        st = xp.stat()
        cache_key = (str(xp), st.st_mtime_ns, st.st_size, bool(edit_markers))
        transform = cache.get(cache_key)
        if transform is None:
            # Une seule version compilée par chemin (avec ou sans crayons)
            # suffit ; jeter les anciennes si la feuille a été modifiée sur
            # disque.
            for k in list(cache):
                if k[0] == str(xp) and k[3] == cache_key[3]:
                    cache.pop(k, None)
            if edit_markers:
                xsl_doc = LET.fromstring(edit_stylesheet(xp).encode("utf-8"), parser=parser,
                                         base_url=edit_stylesheet_url(xp))
            else:
                xsl_doc = LET.parse(str(xp), parser=parser)
            # Une feuille peut lire des fichiers locaux (document(), import),
            # mais jamais écrire de fichier, créer de dossier ni accéder au
            # réseau.
            access = LET.XSLTAccessControl(
                read_file=True, write_file=False, create_dir=False,
                read_network=False, write_network=False,
            )
            transform = LET.XSLT(xsl_doc, access_control=access)
            cache[cache_key] = transform
        xslt_params = {str(k): LET.XSLT.strparam(str(v)) for k, v in (params or {}).items()}
        return str(transform(xml_doc, **xslt_params)), "lxml"
    except Exception as exc:
        # Seules les erreurs XSLT ont un journal propre à la transformation ;
        # celui d'une erreur de syntaxe XML est global et contient aussi les
        # erreurs antérieures.
        log = exc.error_log if isinstance(exc, LET.XSLTError) else ()
        raise RuntimeError(_xslt_error_text(exc, xsl_path, log)) from exc


def render_preview(xml_text, xsl_path, params, marker_title, cache=None, check=False, base=""):
    """La partie lourde de l'aperçu, sans Qt ni état de la fenêtre :
    ``(html, lignes cliquables, crayons, moteur)``. Avec *check*, le XML est
    d'abord vérifié (ET.ParseError). Peut se faire hors du fil de la
    fenêtre, avec son propre *cache* de feuilles compilées (red team 2, A8).

    Une feuille 2.0 ou 3.0 (V0.9.4.4) est confiée au processus d'aperçu
    Saxon (``saxon_preview``) : appel bloquant, à faire hors du fil de la
    fenêtre ; ``base`` est l'adresse du document, pour un ``doc()``
    relatif. Une erreur de Saxon lève ``saxon_preview.PreviewError``."""
    if check:
        ET.fromstring(xml_text)
    if stylesheet_needs_saxon(xsl_path):
        import saxon_preview
        result = saxon_preview.client().transform(xml_text, xsl_path, params, base=base,
                                                 timeout=saxon_preview.PREVIEW_TIMEOUT_SEC)
        html_text, engine = result.html, result.engine
    else:
        html_text, engine = transform_with_xslt(xml_text, xsl_path, params, edit_markers=True, cache=cache)
    html_text, clickable_lines, _text_links = make_line_segments_clickable(html_text)
    html_text, marked = place_edit_markers(html_text, marker_title)
    return resolve_style_variables(html_text), clickable_lines, marked, engine


def _transform_without_lxml(xml_text, xsl_path, params, first_error, edit_markers=False):
    """Secours sans lxml : moteur .NET via PowerShell (Windows)."""
    ps = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    if ps:
        try:
            with tempfile.TemporaryDirectory(prefix="tei_xslt_") as td:
                td = Path(td)
                if edit_markers:
                    wrapper = td / "varians-edit.xsl"
                    wrapper.write_text(edit_stylesheet(xsl_path), encoding="utf-8")
                    xsl_path = wrapper
                xmlf = td / "edition.xml"
                outf = td / "edition.html"
                psf = td / "transform.ps1"
                xmlf.write_text(xml_text, encoding="utf-8")
                psf.write_text(
                    'param([string]$xml,[string]$xsl,[string]$out,[string]$baseWitness,[string]$tocTitle)\n'
                    '$tr = New-Object System.Xml.Xsl.XslCompiledTransform\n'
                    '$settings = New-Object System.Xml.Xsl.XsltSettings($false,$false)\n'
                    '$resolver = New-Object System.Xml.XmlUrlResolver\n'
                    '$tr.Load($xsl,$settings,$resolver)\n'
                    '$args = New-Object System.Xml.Xsl.XsltArgumentList\n'
                    'if ($baseWitness) { $args.AddParam("baseWitness", "", $baseWitness) }\n'
                    'if ($tocTitle) { $args.AddParam("tocTitle", "", $tocTitle) }\n'
                    '$writer = [System.Xml.XmlWriter]::Create($out, $tr.OutputSettings)\n'
                    'try { $tr.Transform($xml,$args,$writer,$resolver) } finally { $writer.Close() }\n',
                    encoding="utf-8",
                )
                proc = subprocess.run(
                    [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(psf),
                     str(xmlf), str(xsl_path), str(outf), str((params or {}).get("baseWitness", "")), str((params or {}).get("tocTitle", ""))],
                    capture_output=True, text=True, timeout=30,
                )
                if proc.returncode != 0 or not outf.exists():
                    raise RuntimeError((proc.stderr or proc.stdout or _t("xslt.error.powershell")).strip())
                return outf.read_text(encoding="utf-8", errors="replace"), "PowerShell/.NET"
        except Exception as exc:
            raise RuntimeError(
                _t("xslt.error.generic", lxml=first_error, powershell=exc)
            ) from exc

    raise RuntimeError(
        _t("xslt.error.install", error=first_error)
    )


class FormattedEditionWidget(ViewsMixin, FragmentEditorMixin, QWidget):
    """Vue XSLT/CSS + édition sûre du fragment TEI correspondant au paragraphe choisi."""

    # Résultat d'une actualisation faite dans un autre fil (red team 2, A8),
    # reçu dans celui de la fenêtre.
    preview_job_done = Signal(object)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main = main_window
        # Vue choisie (V0.9.4.4) : None pour la vue du projet (feuille et CSS
        # de <rendering>), sinon une vue nommée (ViewConfig) du document
        # affiché. _view_key : le document dont la liste montre les vues
        # (l'édition, pour elle et ses parties) ; _views : ses vues nommées.
        self._current_view = None
        self._view_key = None
        self._views = ()
        self.current_paragraph = None
        self.fragment_original = ""
        # Document (édition ou partie) dont vient le fragment ouvert, et
        # nombre de paragraphes de l'aperçu à son ouverture.
        self.fragment_session = None
        self._fragment_total = 0
        self.dirty_preview = True
        self._last_preview_key = None
        # Édition en parties (V0.9.1.5) : fichier et place de chaque
        # paragraphe et repère de ligne de l'aperçu (preview_sources).
        self.sources = None
        # Noms des éléments modifiables de l'aperçu affiché (V0.9.2.9),
        # relevés à son actualisation : le crayon, F2, le fragment et les
        # reports de sélection s'y tiennent jusqu'à la suivante.
        self.unit_names = None
        self._cached_css_key = None
        self._cached_css_text = None
        self._last_preview_engine = None

        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(5)

        top = QHBoxLayout()
        # Liste des vues du document affiché : la vue du projet, puis ses
        # vues nommées. Elle remplace les boutons « XSLT… » et « CSS… », dont
        # le choix ne valait que pour la session.
        self.view_combo = QComboBox()
        self.view_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.view_combo.setMinimumContentsLength(12)
        # Menu « Vues » : créer, modifier, retirer une vue nommée du document
        # affiché, ouvrir sa feuille XSLT.
        self.views_button = QToolButton()
        self.views_button.setText(_t("views.menu"))
        self.views_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        views_menu = QMenu(self.views_button)
        self.new_view_action = views_menu.addAction(_t("views.new"))
        self.edit_view_action = views_menu.addAction(_t("views.edit"))
        self.remove_view_action = views_menu.addAction(_t("views.remove"))
        views_menu.addSeparator()
        self.open_view_stylesheet_action = views_menu.addAction(_t("views.open_xslt"))
        self.views_button.setMenu(views_menu)
        self.new_view_action.triggered.connect(self.new_view)
        self.edit_view_action.triggered.connect(self.edit_view)
        self.remove_view_action.triggered.connect(self.remove_view)
        self.open_view_stylesheet_action.triggered.connect(self.open_view_stylesheet)
        self.refresh_btn = QPushButton(_t("preview.refresh"))
        self.auto_check = QCheckBox(_t("preview.auto"))
        self.auto_check.setChecked(True)
        self.font_minus_btn = QPushButton("A−")
        self.font_reset_btn = QPushButton("100 %")
        self.font_plus_btn = QPushButton("A+")
        self.font_minus_btn.setToolTip(_t("preview.font_minus.tip"))
        self.font_reset_btn.setToolTip(_t("preview.font_reset.tip"))
        self.font_plus_btn.setToolTip(_t("preview.font_plus.tip"))
        self.formatting_label = QLabel(_t("preview.formatting"))
        top.addWidget(self.formatting_label)
        top.addWidget(self.view_combo)
        top.addWidget(self.views_button)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.auto_check)
        top.addSpacing(8)
        self.preview_size_label = QLabel(_t("preview.size"))
        top.addWidget(self.preview_size_label)
        top.addWidget(self.font_minus_btn)
        top.addWidget(self.font_reset_btn)
        top.addWidget(self.font_plus_btn)
        top.addStretch(1)
        root.addLayout(top)

        # Recherche contextuelle dans l'aperçu XSLT/CSS. Ctrl+F depuis cet
        # onglet ouvre cette barre au lieu de basculer vers la source XML.
        self.preview_find_bar = QWidget()
        pf = QHBoxLayout(self.preview_find_bar)
        pf.setContentsMargins(0, 0, 0, 2)
        pf.setSpacing(5)
        self.preview_find_label = QLabel(_t("preview.search.label"))
        pf.addWidget(self.preview_find_label)
        self.preview_find_box = QLineEdit()
        self.preview_find_box.setClearButtonEnabled(True)
        self.preview_find_box.setPlaceholderText(_t("preview.search.placeholder"))
        self.preview_find_status = QLabel("")
        self.preview_find_status.setMinimumWidth(54)
        self.preview_find_prev_btn = QPushButton("◀")
        self.preview_find_next_btn = QPushButton("▶")
        self.preview_find_close_btn = QPushButton("✕")
        self.preview_find_prev_btn.clicked.connect(self.find_preview_previous)
        self.preview_find_next_btn.clicked.connect(self.find_preview_next)
        self.preview_find_close_btn.clicked.connect(self.hide_preview_find)
        self.preview_find_box.returnPressed.connect(self.find_preview_next)
        pf.addWidget(self.preview_find_box, 1)
        pf.addWidget(self.preview_find_status)
        pf.addWidget(self.preview_find_prev_btn)
        pf.addWidget(self.preview_find_next_btn)
        pf.addWidget(self.preview_find_close_btn)
        self.preview_find_bar.setVisible(False)
        root.addWidget(self.preview_find_bar)

        # preview_zoom_steps = taille souhaitée par l’utilisateur ;
        # _preview_applied_zoom_steps = zoom effectivement appliqué au QTextBrowser.
        # Les séparer évite les doubles applications lors d’un setHtml().
        self.preview_zoom_steps = 0
        self._preview_applied_zoom_steps = 0
        self.preview = ClickablePreview()
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.preview.setMinimumHeight(300)
        self.preview.anchorClicked.connect(self._anchor_clicked)
        self.preview.lineActivated.connect(self._line_clicked)
        self.preview.textSelected.connect(self._preview_selection_to_fragment)
        # F2 : ouvre dans l'éditeur de fragment le paragraphe de la sélection
        # (ou du curseur) de l'aperçu, la sélection reportée.
        self.edit_paragraph_action = QAction(_t("preview.edit_paragraph"), self.preview)
        self.edit_paragraph_action.setShortcut(QKeySequence(Qt.Key.Key_F2))
        self.edit_paragraph_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.edit_paragraph_action.triggered.connect(self.edit_selected_paragraph)
        self.preview.addAction(self.edit_paragraph_action)

        frag_box = QWidget()
        self.frag_box = frag_box
        frag_layout = QVBoxLayout(frag_box)
        frag_layout.setContentsMargins(0, 4, 0, 0)
        frag_head = QHBoxLayout()
        self.frag_label = QLabel(_t("fragment.initial"))
        # L'étiquette nomme l'élément ouvert (« <p> ») : jamais du HTML.
        self.frag_label.setTextFormat(Qt.TextFormat.PlainText)
        self.fragment_visual_wrap = QCheckBox(_t("source.visual_wrap"), frag_box)
        self.fragment_visual_wrap.setToolTip(_t("source.visual_wrap"))     # texte entier, la case pouvant être réduite
        _fragment_wrap_setting = _settings().value(
            "fragmentVisualWrap", _settings().value("sourceVisualWrap", False)
        )
        if isinstance(_fragment_wrap_setting, str):
            _fragment_wrap_setting = _fragment_wrap_setting.strip().lower() in {"1", "true", "yes", "on"}
        self.fragment_visual_wrap.setChecked(bool(_fragment_wrap_setting))
        self.apply_btn = QPushButton(_t("fragment.apply_xml"))
        self.reload_btn = QPushButton(_t("fragment.reload"))
        self.close_fragment_btn = QPushButton(_t("fragment.close"))
        self.close_fragment_btn.setToolTip(_t("fragment.close.tip"))
        self.apply_btn.setEnabled(False)
        self.reload_btn.setEnabled(False)
        frag_head.addWidget(self.frag_label)
        frag_head.addSpacing(12)
        # Faute de place, la case cède la sienne : l'étiquette du fragment
        # (paragraphe, fichier d'une partie) reste lisible en entier.
        self.fragment_visual_wrap.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.fragment_visual_wrap.setMinimumWidth(24)
        frag_head.addWidget(self.fragment_visual_wrap, 1)
        frag_head.addWidget(self.reload_btn)
        frag_head.addWidget(self.apply_btn)
        frag_head.addWidget(self.close_fragment_btn)
        frag_layout.addLayout(frag_head)

        # Barre de recherche locale au fragment. Elle apparaît avec Ctrl+F
        # lorsque le focus est dans l’éditeur de paragraphe.
        self.fragment_find_bar = QWidget()
        ff = QHBoxLayout(self.fragment_find_bar)
        self._fragment_find_layout = ff
        ff.setContentsMargins(0, 0, 0, 2)
        ff.setSpacing(5)
        self.fragment_find_label = QLabel(_t("fragment.search.label"))
        ff.addWidget(self.fragment_find_label)
        self.fragment_find_box = QLineEdit()
        self.fragment_find_box.setClearButtonEnabled(True)
        self.fragment_find_box.setPlaceholderText(_t("fragment.search.placeholder"))
        self.fragment_find_box.returnPressed.connect(self.find_fragment_next)
        self.fragment_find_prev_btn = QPushButton("◀")
        self.fragment_find_next_btn = QPushButton("▶")
        self.fragment_find_close_btn = QPushButton("×")
        self.fragment_find_prev_btn.setToolTip(_t("fragment.search.prev.tip"))
        self.fragment_find_next_btn.setToolTip(_t("fragment.search.next.tip"))
        self.fragment_find_close_btn.setToolTip(_t("fragment.search.close.tip"))
        self.fragment_find_prev_btn.clicked.connect(self.find_fragment_previous)
        self.fragment_find_next_btn.clicked.connect(self.find_fragment_next)
        self.fragment_find_close_btn.clicked.connect(self.hide_fragment_find)
        self.fragment_find_status = QLabel("")
        self.fragment_find_status.setMinimumWidth(54)
        ff.addWidget(self.fragment_find_box, 1)
        ff.addWidget(self.fragment_find_status)
        ff.addWidget(self.fragment_find_prev_btn)
        ff.addWidget(self.fragment_find_next_btn)
        ff.addWidget(self.fragment_find_close_btn)
        self.fragment_find_bar.setVisible(False)
        frag_layout.addWidget(self.fragment_find_bar)
        # Ligne « Remplacer par » (Ctrl+H, V0.9.2.8), sous la recherche.
        self.fragment_replace_row = QWidget()
        fr = QHBoxLayout(self.fragment_replace_row)
        fr.setContentsMargins(0, 0, 0, 2)
        fr.setSpacing(5)
        self.fragment_replace_label = QLabel(_t("replace.with.label"))
        self.fragment_replace_box = QLineEdit()
        self.fragment_replace_box.setClearButtonEnabled(True)
        self.fragment_replace_box.returnPressed.connect(self.replace_fragment_next)
        self.fragment_replace_one_button = QPushButton(_t("replace.one"))
        self.fragment_replace_all_button = QPushButton(_t("replace.all"))
        self.fragment_replace_one_button.clicked.connect(self.replace_fragment_next)
        self.fragment_replace_all_button.clicked.connect(self.replace_fragment_all)
        fr.addWidget(self.fragment_replace_label)
        fr.addWidget(self.fragment_replace_box, 1)
        fr.addWidget(self.fragment_replace_one_button)
        fr.addWidget(self.fragment_replace_all_button)
        self.fragment_replace_row.setVisible(False)
        frag_layout.addWidget(self.fragment_replace_row)

        self.fragment_editor = CodeEditor()
        self.fragment_editor.setMaximumHeight(235)
        self.fragment_editor.setPlaceholderText(_t("fragment.placeholder"))
        # Même retour à la ligne purement visuel que dans XML source. Le choix
        # du fragment est mémorisé séparément ; lors de la première utilisation,
        # il hérite de la préférence de la source XML.
        self.fragment_editor.set_visual_wrap(bool(_fragment_wrap_setting))
        self.fragment_visual_wrap.toggled.connect(self._set_fragment_visual_wrap)

        # Ctrl+E entoure la sélection (en la conservant) ou insère un élément
        # vide si aucune sélection n'est active. Le raccourci est attaché
        # uniquement à l'éditeur de fragment pour ne pas interférer avec les
        # autres vues de l'application.
        self.wrap_element_action = QAction(_t("fragment.wrap"), self.fragment_editor)
        self.wrap_element_action.setShortcut(QKeySequence("Ctrl+E"))
        self.wrap_element_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.wrap_element_action.triggered.connect(lambda: self.wrap_selection_with_element(self.fragment_editor, _t("ctrl_e.where.fragment")))
        self.fragment_editor.addAction(self.wrap_element_action)

        # Ctrl+Espace : complétion contextuelle pilotée par le RNG actif.
        self.fragment_completion_action = QAction(_t("completion.action"), self.fragment_editor)
        self.fragment_completion_action.setShortcut(QKeySequence("Ctrl+Space"))
        self.fragment_completion_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.fragment_completion_action.triggered.connect(
            lambda: self.main.show_rng_completion(self.fragment_editor)
        )
        self.fragment_editor.addAction(self.fragment_completion_action)

        # Une sélection faite dans le fragment est aussi sélectionnée dans
        # l'aperçu, après une courte pause (pas à chaque pas d'un glisser).
        self._fragment_selection_timer = QTimer(self)
        self._fragment_selection_timer.setSingleShot(True)
        self._fragment_selection_timer.setInterval(150)
        self._fragment_selection_timer.timeout.connect(self._fragment_selection_to_preview)
        self.fragment_editor.selectionChanged.connect(self._fragment_selection_timer.start)

        frag_layout.addWidget(self.fragment_editor)

        # L’éditeur de fragment reste masqué tant qu’aucun paragraphe n’est ouvert.
        frag_box.setVisible(False)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.preview)
        split.addWidget(frag_box)
        split.setSizes([620, 260])
        root.addWidget(split, 1)

        self.info = QLabel(_t("preview.info.default"))
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color:#746b61")
        root.addWidget(self.info)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        # Évite une retransformation de toute l'édition après chaque petite pause
        # de frappe. Le moteur PowerShell de secours est plus coûteux que lxml.
        self.preview_timer.setInterval(1800 if lxml_available() else 3200)
        self.preview_timer.timeout.connect(self._refresh_preview_in_background)
        # Actualisation automatique hors du fil de la fenêtre (red team 2, A8).
        self._preview_generation = 0
        # Génération de l'aperçu en cours dans un autre fil (None : aucun), et
        # ce qui attend qu'il soit affiché (when_ready, V0.9.4.4).
        self._pending_job = None
        self._ready_callbacks = []
        self._preview_executor = None
        self._background_xslt_cache = {}
        self.preview_job_done.connect(self._background_preview_done)
        self.view_combo.currentIndexChanged.connect(self._view_chosen)
        self.context_changed()
        self.refresh_btn.clicked.connect(self.refresh_preview)
        self.apply_btn.clicked.connect(self.apply_fragment)
        self.reload_btn.clicked.connect(self.reload_fragment)
        self.close_fragment_btn.clicked.connect(self.close_fragment_editor)
        self.auto_check.toggled.connect(self._auto_toggled)
        self.font_minus_btn.clicked.connect(lambda: self._change_preview_zoom(-1))
        self.font_reset_btn.clicked.connect(self._reset_preview_zoom)
        self.font_plus_btn.clicked.connect(lambda: self._change_preview_zoom(1))

    # -- Vues (V0.9.4.4) ----------------------------------------------------------

    def retranslate_ui(self):
        """Remet les textes de la vue dans la langue de l'interface, puis retransforme l'aperçu
        (``force=True``) : la feuille XSLT y écrit aussi des textes traduits (titre de la table
        des matières…)."""
        self.view_combo.setItemText(0, _t("preview.view.project"))
        self._update_view_tip()
        self.views_button.setText(_t("views.menu"))
        self.new_view_action.setText(_t("views.new"))
        self.edit_view_action.setText(_t("views.edit"))
        self.remove_view_action.setText(_t("views.remove"))
        self.open_view_stylesheet_action.setText(_t("views.open_xslt"))
        self.edit_paragraph_action.setText(_t("preview.edit_paragraph"))
        self.refresh_btn.setText(_t("preview.refresh"))
        self.auto_check.setText(_t("preview.auto"))
        self.font_minus_btn.setToolTip(_t("preview.font_minus.tip"))
        self.font_reset_btn.setToolTip(_t("preview.font_reset.tip"))
        self.font_plus_btn.setToolTip(_t("preview.font_plus.tip"))
        self.formatting_label.setText(_t("preview.formatting"))
        self.preview_size_label.setText(_t("preview.size"))
        self.preview_find_label.setText(_t("preview.search.label"))
        self.preview_find_box.setPlaceholderText(_t("preview.search.placeholder"))
        self.apply_btn.setText(_t("fragment.apply_xml"))
        self.reload_btn.setText(_t("fragment.reload"))
        self.close_fragment_btn.setText(_t("fragment.close"))
        self.close_fragment_btn.setToolTip(_t("fragment.close.tip"))
        self.fragment_find_label.setText(_t("fragment.search.label"))
        self.fragment_find_box.setPlaceholderText(_t("fragment.search.placeholder"))
        self.fragment_find_prev_btn.setToolTip(_t("fragment.search.prev.tip"))
        self.fragment_find_next_btn.setToolTip(_t("fragment.search.next.tip"))
        self.fragment_find_close_btn.setToolTip(_t("fragment.search.close.tip"))
        self.fragment_replace_label.setText(_t("replace.with.label"))
        self.fragment_replace_one_button.setText(_t("replace.one"))
        self.fragment_replace_all_button.setText(_t("replace.all"))
        self.fragment_editor.setPlaceholderText(_t("fragment.placeholder"))
        self.fragment_visual_wrap.setText(_t("source.visual_wrap"))
        self.fragment_visual_wrap.setToolTip(_t("source.visual_wrap"))
        self.wrap_element_action.setText(_t("fragment.wrap"))
        self.fragment_completion_action.setText(_t("completion.action"))
        self._update_fragment_label()
        self.info.setText(_t("preview.info.default"))
        # The transformed preview contains localized XSLT chrome (e.g. Contents).
        self.dirty_preview = True
        self._last_preview_key = None
        self.refresh_preview(force=True)

    def focus_is_in_preview(self):
        """True si le focus clavier est dans l'aperçu ou dans sa barre de recherche."""
        focus = QApplication.focusWidget()
        return bool(
            focus is self.preview
            or (focus is not None and self.preview.isAncestorOf(focus))
            or focus is self.preview_find_box
            or (focus is not None and self.preview_find_bar.isAncestorOf(focus))
        )

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

    def current_preview_line(self):
        """Ligne du témoin pivot où en est la lecture de l'aperçu : le repère au centre de la zone
        visible, sinon la dernière ligne active ; None si l'aperçu n'en a pas. Sert au retour
        vers la source et à garder la place quand la taille du texte change."""
        # Pour une transition d'onglet, la ligne au centre de la fenêtre reflète
        # mieux la position de lecture qu'une ancienne sélection.
        line = self.preview.line_at_viewport_center()
        return line if line is not None else self.preview.active_line_ordinal

    def scroll_to_t1_line(self, ordinal):
        """Fait défiler l'aperçu jusqu'au repère de ligne ``ordinal`` du témoin pivot, centré.
        L'aperçu est d'abord actualisé s'il est en retard sur la source ; le défilement attend
        le tour suivant de la boucle d'événements. Rien si ``ordinal`` est None."""
        if ordinal is None:
            return
        if self.dirty_preview:
            self.refresh_preview()
        call_later(0, self, lambda n=int(ordinal): self.preview.scroll_to_line(n, center=True))

    @staticmethod
    def _is_simple_xml_qname(name):
        """Valide le sous-ensemble de QName accepté par Ctrl+E/configuration."""
        name_part = r"[A-Za-z_][A-Za-z0-9_.-]*"
        return bool(name and re.fullmatch(rf"{name_part}(?::{name_part})?", name))

    def _custom_attributes_for_element(self, element):
        """Relit custom-elements.xml et renvoie les attributs configurés.

        Le fichier est volontairement relu à chaque Ctrl+E afin qu'une
        modification prenne effet sans redémarrage. La configuration décrit
        une aide de saisie : elle n'altère jamais la validation RELAX NG.
        """
        custom_file = self.main.project.custom_elements
        if not custom_file.exists():
            return []
        try:
            config = load_custom_completion(custom_file)
        except Exception as exc:
            if str(exc) == "ROOT_NOT_CUSTOM_ELEMENTS":
                raise ValueError(_t("ctrl_e.config.root_error", file=custom_file.name)) from exc
            raise ValueError(
                _t("ctrl_e.config.read_error", file=custom_file.name, error=exc)
            ) from exc

        attrs = []
        for attr in config.attributes_for(element):
            if not self._is_simple_xml_qname(attr.name):
                raise ValueError(
                    _t("ctrl_e.config.attr_error", file=custom_file.name, name=repr(attr.name))
                )
            attrs.append((attr.name, attr.default_value, attr.has_default))
        return attrs

    def wrap_selection_with_element(self, target_editor=None, editor_label="fragment TEI"):
        """Ctrl+E : entourer la sélection ou insérer un élément au point d'insertion.

        Avec sélection, seul le CONTENU d'origine demeure sélectionné, sans
        les balises ajoutées : Ctrl+E répété insère donc le deuxième élément
        à l'intérieur du premier (comportement de type Oxygen).
        Sans sélection, on crée une paire de balises avec le curseur à
        l'intérieur. Le suffixe « / » (ex. « lb/ ») crée une balise vide.
        Si un attribut de custom-elements.xml n'a pas de defaultValue,
        le point d'insertion sans sélection reste dans le premier attribut vide.
        La commande est commune à la source XML et à l'éditeur de fragment.
        """
        target_editor = target_editor or self.fragment_editor
        cursor = target_editor.textCursor()
        has_selection = cursor.hasSelection()

        # V0.6.0 : Ctrl+E fusionne le contexte RNG et les aides du projet ;
        # d'abord les éléments réellement admissibles à cette position. Le champ
        # reste éditable : la personnalisation de saisie et les documents en cours
        # de correction ne sont donc pas bloqués par le sélecteur.
        suggestion_pos = target_editor.positions().python(cursor.selectionStart() if has_selection
                                                          else cursor.position())
        suggestion_provider = getattr(self.main, "rng_element_suggestions", None)
        suggestions = (
            suggestion_provider(target_editor, suggestion_pos)
            if callable(suggestion_provider) else ()
        )
        if suggestions:
            dlg = CompletionDialog(
                _t("ctrl_e.dialog.title"),
                _t("ctrl_e.suggestions.label"),
                suggestions,
                "",
                self,
                allow_custom=True,
            )
            try:
                point = target_editor.viewport().mapToGlobal(target_editor.cursorRect().bottomLeft())
                dlg.move(point)
            except Exception:
                pass
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_value:
                return
            element = dlg.selected_value.strip()
        else:
            element, ok = QInputDialog.getText(
                self,
                _t("ctrl_e.dialog.title"),
                _t("ctrl_e.dialog.label"),
                QLineEdit.EchoMode.Normal,
                "",
            )
            if not ok:
                return
            element = element.strip()
        self_closing = element.endswith("/")
        if self_closing:
            element = element[:-1].strip()

        if not self._is_simple_xml_qname(element):
            QMessageBox.warning(
                self,
                _t("ctrl_e.invalid_element.title"),
                _t("ctrl_e.invalid_element.text"),
            )
            return
        if self_closing and has_selection:
            QMessageBox.warning(
                self,
                _t("ctrl_e.invalid_element.title"),
                _t("ctrl_e.self_closing_requires_empty"),
            )
            return

        try:
            custom_attrs = self._custom_attributes_for_element(element)
        except ValueError as exc:
            QMessageBox.warning(
                self,
                _t("ctrl_e.invalid_config.title"),
                str(exc) + _t("ctrl_e.invalid_config.suffix"),
            )
            return

        # Le QTextCursor capture la sélection avant l'ouverture du dialogue.
        # Qt y sépare les lignes par U+2029 : les restituer en LF conserve
        # exactement le XML multiligne sélectionné. Un U+2028 du texte reste
        # tel quel (red team, A1).
        selected = cursor.selectedText().replace("\u2029", "\n")
        selection_start = cursor.selectionStart()
        # Préserver aussi le sens de la sélection : Qt place position() à
        # gauche pour une sélection faite de droite à gauche.
        selection_reversed = has_selection and cursor.position() == selection_start

        opening_tag = f"<{element}"
        empty_attr_cursor_offset = None
        for name, value, has_default in custom_attrs:
            opening_tag += f' {name}="'
            if not has_default and empty_attr_cursor_offset is None:
                empty_attr_cursor_offset = len(opening_tag)
            opening_tag += html_lib.escape(str(value), quote=True) + '"'
        opening_tag += "/>" if self_closing else ">"

        replacement = (opening_tag if self_closing
                       else opening_tag + selected + f"</{element}>")
        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()

        new_cursor = QTextCursor(target_editor.document())
        # QTextCursor utilise des offsets UTF-16 et non la longueur Python :
        # des caractères non-BMP (emoji, etc.) doivent compter pour 2 unités.
        utf16_length = lambda text: len(text.encode("utf-16-le")) // 2
        if has_selection:
            # Garder précisément le texte initial sélectionné, PAS les balises.
            # Exemple : <app>[uerbum]</app> puis Ctrl+E « rdg » produit
            # <app><rdg>[uerbum]</rdg></app>, dans le bon ordre d'imbrication.
            content_start = selection_start + utf16_length(opening_tag)
            content_end = content_start + utf16_length(selected)
            if selection_reversed:
                new_cursor.setPosition(content_end)
                new_cursor.setPosition(content_start, QTextCursor.MoveMode.KeepAnchor)
            else:
                new_cursor.setPosition(content_start)
                new_cursor.setPosition(content_end, QTextCursor.MoveMode.KeepAnchor)
        elif empty_attr_cursor_offset is not None:
            # Aucun texte sélectionné : compléter d'abord le 1er attribut vide.
            new_cursor.setPosition(selection_start + utf16_length(opening_tag[:empty_attr_cursor_offset]))
        elif self_closing:
            # <lb/> : point d'insertion immédiatement après la balise vide.
            new_cursor.setPosition(selection_start + utf16_length(replacement))
        else:
            # <note>|</note> : prêt à saisir le contenu de l'élément.
            new_cursor.setPosition(selection_start + utf16_length(opening_tag))
        target_editor.setTextCursor(new_cursor)
        target_editor.setFocus()

        if custom_attrs:
            attrs_msg = ", ".join(name for name, _, _ in custom_attrs)
            msg = _t("ctrl_e.inserted_attrs", element=element, attrs=attrs_msg, file=self.main.project.custom_elements.name)
        elif self_closing:
            msg = _t("ctrl_e.inserted_self_closing", element=element)
        elif not has_selection:
            msg = _t("ctrl_e.inserted_empty", element=element)
        else:
            msg = _t("ctrl_e.inserted", element=element)
        self.main.statusBar().showMessage(msg, 2600)

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

    def _preview_zoom_label(self):
        # L’API Qt travaille en crans typographiques, pas en vrais pourcentages.
        # On conserve une échelle utilisateur simple de 10 % par cran, mais l’état
        # appliqué est désormais absolu et non cumulatif.
        return f"{100 + self.preview_zoom_steps * 10} %"

    def _apply_preview_zoom_state(self):
        """Applique uniquement l’écart entre le zoom désiré et le zoom réel."""
        diff = self.preview_zoom_steps - self._preview_applied_zoom_steps
        if diff > 0:
            self.preview.zoomIn(diff)
        elif diff < 0:
            self.preview.zoomOut(-diff)
        self._preview_applied_zoom_steps = self.preview_zoom_steps
        self.font_reset_btn.setText(self._preview_zoom_label())

    def _normalize_preview_zoom_before_reload(self):
        """Ramène réellement le QTextBrowser à sa base avant de remplacer son HTML."""
        applied = self._preview_applied_zoom_steps
        if applied > 0:
            self.preview.zoomOut(applied)
        elif applied < 0:
            self.preview.zoomIn(-applied)
        self._preview_applied_zoom_steps = 0

    def _change_preview_zoom(self, delta):
        anchor_line = self.current_preview_line()
        self.preview_zoom_steps = max(-6, min(12, self.preview_zoom_steps + delta))
        self._apply_preview_zoom_state()
        if anchor_line is not None:
            call_later(0, self, lambda n=int(anchor_line): self.preview.scroll_to_line(n, center=True))

    def _reset_preview_zoom(self):
        anchor_line = self.current_preview_line()
        self.preview_zoom_steps = 0
        self._apply_preview_zoom_state()
        if anchor_line is not None:
            call_later(0, self, lambda n=int(anchor_line): self.preview.scroll_to_line(n, center=True))

    def _reapply_preview_zoom(self):
        self._apply_preview_zoom_state()

    def _auto_toggled(self, checked):
        if checked and self.dirty_preview:
            self.preview_timer.start()

    def source_changed(self):
        """À chaque modification de la source : l'aperçu est marqué en retard et une actualisation
        en cours dans un autre fil est rendue caduque. Avec « Aperçu auto » et la vue affichée,
        l'actualisation est reportée à la fin d'une pause de la frappe (``preview_timer``)."""
        self.dirty_preview = True
        # Un aperçu en cours dans un autre fil ne montre plus le texte.
        self._preview_generation += 1
        # start() redémarre le timer : une saisie continue ne déclenche donc pas
        # de transformation intermédiaire. On attend une vraie pause de frappe.
        if self.auto_check.isChecked() and self.isVisible():
            self.preview_timer.start()

    def became_visible(self):
        """À l'affichage de l'onglet de l'aperçu : l'actualise s'il est en retard sur la source."""
        if self.dirty_preview:
            self.refresh_preview()

    def _file_signature(self, path):
        try:
            st = Path(path).stat()
            return (str(Path(path).resolve()), st.st_mtime_ns, st.st_size)
        except OSError:
            return (str(path), None, None)

    def _resolved_css_cached(self):
        key = self._file_signature(self.css_path)
        if key != self._cached_css_key or self._cached_css_text is None:
            css = PREVIEW_BASE_CSS + resolve_css_variables(self.css_path.read_text(encoding="utf-8"))
            self._cached_css_key = key
            self._cached_css_text = css
        return self._cached_css_text

    def _preview_inputs(self):
        """Ce que l'aperçu transforme : ``(sources, texte, plages, noms)``.
        Édition en parties (XInclude) : l'édition assemblée, quel que soit le
        document affiché ; ses éléments modifiables et ses lignes restent
        rattachés à leur fichier (V0.9.1.5). Chaque élément modifiable porte
        son rang (vx:edit), celui de son crayon ✎. Un document auxiliaire,
        ou une édition sans parties : le document affiché."""
        names = self.view_unit_names()
        if self.main._preview_shows_assembly():
            sources = self.main._assembled_preview_sources(names)
            xml_text = (sources.text if sources is not None
                        else self.main.edition_session.text_document.toPlainText())
            spans = sources.paragraphs if sources is not None else ()
        else:
            sources = None
            xml_text, spans = mark_units(self.main.editor.toPlainText(), names)
        return sources, xml_text, spans, names

    def _preview_files_missing(self):
        if self.xsl_path.exists() and (self._css_mode() == "never" or self.css_path.exists()):
            return False
        self.info.setText(_t("preview.files_missing"))
        self.info.setStyleSheet("color:#a14b2f")
        return True

    def _preview_key(self, xml_text, names):
        # Empreinte légère : évite de reconstruire le gros QTextDocument quand
        # rien n'a changé (clic sur Actualiser, changement d'onglet, etc.).
        xml_digest = hashlib.blake2b(xml_text.encode("utf-8"), digest_size=12).hexdigest()
        return (xml_digest, self._file_signature(self.xsl_path), self._file_signature(self.css_path), names)

    def _preview_up_to_date(self):
        self.dirty_preview = False
        engine = self._last_preview_engine or "cache"
        self.info.setText(_t("preview.up_to_date", engine=engine))
        self.info.setStyleSheet("color:#376b3c")

    def _preview_params(self):
        """Paramètres de la feuille de l'aperçu : le témoin pivot
        (``baseWitness`` pour la feuille de Varians, ``temoin-de-base`` pour
        « Édition critique »), le titre du sommaire, la langue et les
        catalogues ; ``reperes-lignes`` (V0.9.4.4) demande à « Édition
        critique » les repères de ligne, qu'une publication n'a pas. Une
        feuille ignore ceux qu'elle ne déclare pas."""
        return {"baseWitness": self.main.base_id, "temoin-de-base": self.main.base_id, "reperes-lignes": "true",
                "tocTitle": _t("preview.toc"), **publication_params()}

    def _preview_base(self):
        """Adresse du document transformé (pour un ``doc()`` relatif d'une
        feuille 3.0) : l'édition quand l'aperçu la montre assemblée, sinon
        le document affiché."""
        main = self.main
        if main._preview_shows_assembly():
            return str(getattr(main.edition_session, "path", "") or main.project.edition)
        return str(getattr(main.document, "path", "") or "")

    def _expected_line_count(self):
        """Nombre de lignes du témoin pivot auxquelles vont les repères de
        l'aperçu de l'édition (V0.9.4.4) : celles de l'édition assemblée,
        sinon les <lb/> du pivot du document affiché ; None hors de
        l'édition ou sans pivot."""
        main = self.main
        document = getattr(main, "document", None)
        if document is None or not document.in_edition or not getattr(main, "base_id", ""):
            return None
        if self.sources is not None:
            return len(self.sources.lines)
        return len(main.lb_spans())

    def _preview_error_text(self, exc):
        """Texte d'un échec de l'aperçu : délai dépassé, Saxon absent ou
        arrêté (V0.9.4.4), sinon l'erreur de la feuille, avec son lieu."""
        from saxon_preview import PreviewError
        if isinstance(exc, PreviewError):
            if exc.code == "timeout":
                return _t("preview.saxon.timeout", seconds=exc.detail)
            if exc.code == "saxon_missing":
                return _t("preview.saxon.missing")
            if exc.code == "worker_failed":
                return _t("preview.saxon.failed", error=exc.detail)
            return _t("preview.transform_error", error=exc.detail or exc.code)
        return _t("preview.transform_error", error=exc)

    def refresh_preview(self, force=False):
        """Transforme la source par la feuille XSLT, dans le fil de la fenêtre, et affiche le
        résultat avec la CSS ; pour une édition en parties, c'est l'édition assemblée qui est
        transformée. Sans ``force`` (bouton « Actualiser »), rien n'est refait si le texte, les
        feuilles et les éléments modifiables n'ont pas changé. Un XML mal formé ou une erreur de
        transformation est signalé sous l'aperçu, qui garde son contenu."""
        sources, xml_text, spans, names = self._preview_inputs()
        self.sources = sources
        if self._preview_files_missing():
            return
        preview_key = self._preview_key(xml_text, names)
        if not force and preview_key == self._last_preview_key:
            self._preview_up_to_date()
            return
        # Un aperçu en cours dans un autre fil est dépassé.
        self._preview_generation += 1
        try:
            ET.fromstring(xml_text)
        except ET.ParseError as exc:
            self.info.setText(_t("preview.xml_invalid", error=exc))
            self.info.setStyleSheet("color:#a14b2f")
            return
        if stylesheet_needs_saxon(self.xsl_path):
            # Saxon (V0.9.4.4) : hors du fil de la fenêtre, même à la demande.
            self.info.setText(_t("preview.refreshing"))
            self.info.setStyleSheet("color:#746b61")
            self._refresh_preview_in_background(force=True)
            return
        started = time.perf_counter()
        try:
            rendered = render_preview(xml_text, self.xsl_path, self._preview_params(), _t("preview.edit_paragraph"),
                                      base=self._preview_base())
            self._show_preview(rendered, preview_key, names, spans, started)
        except Exception as exc:
            self.info.setText(self._preview_error_text(exc))
            self.info.setStyleSheet("color:#a13d32")

    def _refresh_preview_in_background(self, force=False):
        """Actualisation automatique, après une pause de la frappe (red team
        2, A8) : la transformation (0,85 s par Mo) se fait hors du fil de la
        fenêtre, qui reste libre ; seul l'affichage du résultat s'y fait. Un
        résultat dépassé (le texte a changé depuis, ou l'aperçu a été
        actualisé autrement) est jeté. Avec ``force``, l'aperçu est refait
        même s'il semble à jour (actualisation demandée, feuille 3.0)."""
        sources, xml_text, spans, names = self._preview_inputs()
        if self._preview_files_missing():
            return
        preview_key = self._preview_key(xml_text, names)
        if not force and preview_key == self._last_preview_key:
            self._preview_up_to_date()
            return
        self._preview_generation += 1
        generation = self._preview_generation
        xsl_path, params, title = self.xsl_path, self._preview_params(), _t("preview.edit_paragraph")
        base = self._preview_base()
        started = time.perf_counter()
        cache = self._background_xslt_cache

        def job():
            try:
                return "ok", render_preview(xml_text, xsl_path, params, title, cache=cache, check=True, base=base)
            except ET.ParseError as exc:
                return "xml", exc
            except Exception as exc:
                return "error", exc

        def finished(future):
            try:
                self.preview_job_done.emit((generation, future.result(), sources, spans, names, preview_key, started))
            except RuntimeError:
                pass        # la vue a été fermée entre-temps

        if self._preview_executor is None:
            self._preview_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="varians-preview")
        self._pending_job = generation
        self._preview_executor.submit(job).add_done_callback(finished)

    def when_ready(self, callback):
        """Appelle ``callback`` quand l'aperçu affiché est à jour : tout de
        suite (au tour suivant de la boucle d'événements) s'il l'est, sinon
        après l'affichage de l'aperçu en cours dans un autre fil (feuille
        3.0, V0.9.4.4). Sert à y reporter la sélection de la source. Rien
        n'est appelé si cet aperçu échoue."""
        if self._pending_job is not None and self._pending_job == self._preview_generation:
            self._ready_callbacks.append(callback)
        else:
            call_later(20, self, callback)

    def _run_ready_callbacks(self, shown):
        callbacks, self._ready_callbacks = self._ready_callbacks, []
        if shown:
            for callback in callbacks:
                call_later(20, self, callback)

    def _background_preview_done(self, payload):
        generation, (status, value), sources, spans, names, preview_key, started = payload
        if generation != self._preview_generation:
            return
        self._pending_job = None
        if status == "xml":
            self.info.setText(_t("preview.xml_invalid", error=value))
            self.info.setStyleSheet("color:#a14b2f")
            self._run_ready_callbacks(False)
        elif status == "error":
            self.info.setText(self._preview_error_text(value))
            self.info.setStyleSheet("color:#a13d32")
            self._run_ready_callbacks(False)
        else:
            self.sources = sources
            try:
                self._show_preview(value, preview_key, names, spans, started)
            except Exception as exc:
                self.info.setText(_t("preview.transform_error", error=exc))
                self.info.setStyleSheet("color:#a13d32")
                self._run_ready_callbacks(False)

    def _show_preview(self, rendered, preview_key, names, spans, started):
        """Affiche le résultat de ``render_preview``, à la même place."""
        html_text, clickable_lines, marked, engine = rendered
        # Conserver une ancre sémantique plutôt qu’une simple valeur de scrollbar.
        # Une modification de fragment peut changer la hauteur/recomposition du HTML :
        # restaurer le même nombre de pixels ne ramène alors plus au même passage.
        old_anchor_line = self.preview.line_at_viewport_center()
        if old_anchor_line is None:
            old_anchor_line = self.preview.active_line_ordinal
        old_bar = self.preview.verticalScrollBar()
        old_ratio = (old_bar.value() / old_bar.maximum()) if old_bar.maximum() > 0 else 0.0
        css = self._preview_css(html_text)

        # setHtml() et zoomIn()/zoomOut() n’ont pas des sémantiques identiques
        # selon la nature des tailles CSS. Remettre explicitement le widget à
        # sa base avant reconstruction rend le résultat déterministe.
        self._normalize_preview_zoom_before_reload()
        self.preview.document().setDefaultStyleSheet(css)
        self.preview.setHtml(html_text)
        self.preview.rebuild_line_markers()
        self.unit_names = names
        self._preview_applied_zoom_steps = 0
        self._reapply_preview_zoom()

        def restore_preview_position(line=old_anchor_line, ratio=old_ratio):
            if line is not None and self.preview.scroll_to_line(int(line), center=True):
                return
            bar = self.preview.verticalScrollBar()
            if bar.maximum() > 0:
                bar.setValue(int(round(ratio * bar.maximum())))

        call_later(0, self, restore_preview_position)
        self.dirty_preview = False
        self._last_preview_key = preview_key
        self._last_preview_engine = engine
        elapsed = time.perf_counter() - started
        document = getattr(self.main, "document", None)
        if document is not None and not document.in_edition:
            # Un document sans témoin (V0.9.4.4) : rien à dire des lignes du pivot.
            self.info.setText(_t("preview.updated.timed.document", elapsed=f"{elapsed:.2f}", engine=engine,
                                 marked=marked, paragraphs=len(spans)))
            self.info.setStyleSheet("color:#376b3c")
        elif clickable_lines:
            text = _t("preview.updated.timed.lines", elapsed=f"{elapsed:.2f}", engine=engine, marked=marked,
                      paragraphs=len(spans), lines=clickable_lines)
            expected = self._expected_line_count()
            if expected is not None and expected != clickable_lines:
                # V0.9.4.4 : le n-ième repère va à la n-ième ligne du pivot ;
                # un repère omis ou répété décale tout ce qui suit.
                self.info.setText(text + " " + _t("preview.lines_mismatch", lines=clickable_lines, expected=expected))
                self.info.setStyleSheet("color:#9a6a2f")
            else:
                self.info.setText(text)
                self.info.setStyleSheet("color:#376b3c")
        else:
            self.info.setText(_t("preview.updated.timed.no_lines", elapsed=f"{elapsed:.2f}", engine=engine, marked=marked, paragraphs=len(spans)))
            self.info.setStyleSheet("color:#9a6a2f")
        self._run_ready_callbacks(True)

    def _activate_line(self, idx, move_xml_cursor=True):
        """Repère de ligne ``idx`` de l'aperçu : le curseur de la source et les
        témoins y vont. Dans une édition assemblée, par la place de ce
        repère dans son fichier (V0.9.1.5) : la numérotation des textes
        synchronisés à part est ainsi respectée."""
        if self.sources is not None:
            self.main.navigate_to_preview_line(int(idx))
        else:
            self.main.navigate_to_base_ordinal(idx, move_xml_cursor=move_xml_cursor)

    def _line_clicked(self, idx):
        self.preview.active_line_ordinal = int(idx)
        self._activate_line(idx, move_xml_cursor=True)
        self.info.setText(_t("preview.base_selected", line=idx+1))
        self.info.setStyleSheet("color:#376b3c")

    def _anchor_clicked(self, url):
        if url.scheme() == "tei-line":
            try:
                idx = int(url.path().strip("/"))
            except Exception:
                return
            self._line_clicked(idx)
            return
        if url.scheme() == "tei-toc":
            anchor = url.path().strip("/") or url.host()
            if not anchor:
                return
            self.preview.scrollToAnchor(anchor)

            # Après le saut, synchroniser aussi les trois manuscrits sur la
            # ligne du témoin pivot située au centre du passage atteint, sans quitter l’aperçu.
            def sync_after_toc():
                line = self.preview.line_at_viewport_center()
                if line is not None:
                    self.preview.active_line_ordinal = int(line)
                    self._activate_line(int(line), move_xml_cursor=False)
            call_later(0, self, sync_after_toc)
            return
        if url.scheme() != "tei-edit":
            return
        try:
            idx = int(url.path().strip("/"))
        except Exception:
            return
        # Le crayon ouvre seulement le paragraphe : la source et les témoins
        # restent où ils sont (seul un clic sur le texte les déplace). La
        # sélection en cours, effacée par le clic, est rétablie.
        self._edit_paragraph(idx, self.preview.take_selection_before_pencil())

