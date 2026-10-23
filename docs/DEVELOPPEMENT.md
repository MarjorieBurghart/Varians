# Développer Varians

## Installation

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate    —    Linux/macOS : source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python editeur_tei.py                    # ou : python editeur_tei.py chemin/vers/project.xml
```

`requirements.txt` contient les dépendances d'exécution (PySide6, lxml, et
Saxon-HE, paquet `saxonche`, pour les scénarios XSLT 3.0) ;
`requirements-dev.txt` y ajoute les outils de test (pytest, pytest-qt).

## Tests

Depuis la racine du dépôt :

```bash
python -m pytest -q
```

- `tests/test_*.py` : tests historiques (jusqu'à V0.8.5.26.2). Beaucoup
  s'exécutent sans Qt.
- `tests/gui/` : tests qui pilotent la **vraie** fenêtre Qt, sans écran.
  Ils fixent le comportement observable (ouvrir, modifier, enregistrer,
  valider, XPath, synchronisation des témoins, aperçu, parcours « une image,
  une transcription ») et servent de filet de sécurité pour les
  restructurations. Leur infrastructure (`tests/gui/conftest.py`) isole les
  réglages QSettings, coupe le réseau et impose que chaque boîte de dialogue
  soit prévue par le test.

Sous Linux sans écran, définir `QT_QPA_PLATFORM=offscreen` (fait
automatiquement par `tests/gui/conftest.py`). PySide6 requiert alors
quelques bibliothèques système (`libegl1`, `libxkbcommon0`,
`libfontconfig1`, `libdbus-1-3`).

Ces tests ne remplacent pas une vérification à l'écran : l'affichage
réel sous Windows, macOS ou Linux reste à contrôler à la main avant une
livraison.

**Viewer web** (V0.9.1.6) : les décisions du viewer sans DOM
(`web_viewer/sync_model.js`, comme `geometry.js` et `fulltext_search.js`)
sont testées avec node (`tests/test_v0916_sync_model.py`, ignoré sans
node). Son comportement est testé dans Chromium par Playwright
(`tests/test_v0916_viewer_*.py`) : ces tests sont ignorés sans Playwright ou
sans navigateur, ce qui est le cas sur GitHub ; lancez-les sur un poste de
développement (`pip install playwright`, puis `playwright install chromium`,
ou la variable `CHROMIUM` vers un Chromium déjà installé). Les scripts
`tests/manual_*_chromium.py` se lancent à la main et font des captures
d'écran.

## Tests automatiques sur GitHub

`.github/workflows/tests.yml` lance la suite complète sous Ubuntu et
Windows à chaque envoi et pull request. Les résultats sont visibles dans
l'onglet *Actions* du dépôt.

## Organisation du code de l'interface

`editeur_tei.py` lance l'application (`main()`), définit la fenêtre
d'accueil et la fenêtre principale `MainWindow`. Celle-ci est composée de
*mixins*, un par responsabilité, dont elle hérite :

| Module | Rôle |
|---|---|
| `document_io.py` | ouvrir, enregistrer, fermer le document XML |
| `validation_panel.py` | panneau et validation RELAX NG, résolution du schéma |
| `completion_ui.py` | complétion Ctrl+Espace guidée par le schéma |
| `xpath_panel.py` | recherche XPath |
| `witness_workspace.py` | disposition des panneaux de témoins |
| `witness_sync.py` | synchronisation XML ↔ témoins, folios, ressources |
| `main_menus.py` | barre d'outils, menus, projets récents, langue |
| `project_actions.py` | export web, ouverture/création/réglages de projet |
| `document_tabs.py` | documents du projet affichés : édition, ses parties (XInclude) et documents auxiliaires |
| `document_display.py` | onglets affichés et leur ordre (préférence locale du projet), fenêtre « Documents affichés », clic droit sur un onglet |
| `document_dialogs.py` | ajouter, créer, retirer un document XML auxiliaire |
| `references_ui.py` | références entre documents : identifiants proposés, F12 / Alt+←, commande « Références » |
| `apparatus_ui.py` | Aide ▸ « Débugger l'apparat… » : contrôles de l'apparat et requêtes XPath personnelles |
| `transform_ui.py` | scénarios de transformation XSLT : liste, boîte d'un scénario, bouton « Transformer ▾ », exécution |

Composants autonomes utilisés par la fenêtre :

| Module | Rôle |
|---|---|
| `document_session.py` | état d'un document ouvert (`DocumentSession`, `LbIndex`) |
| `xml_references.py` | pointeurs `#id` et identifiants des documents, sans Qt (`ReferenceResolver`) |
| `xml_assembly.py` | assemblage de l'édition par XInclude : parties, `xpointer`, fichier et ligne d'origine de chaque élément, sans Qt |
| `apparatus_xpath.py` | requêtes XPath 1.0 de contrôle de l'apparat (parallel segmentation), sans Qt |
| `relaxng_worker.py` | processus de validation RELAX NG séparé (Varians relancé avec `--relaxng-worker`), sans Qt |
| `validation_worker.py` | client de ce processus : requêtes, attente sans figer la fenêtre, repli |
| `xslt_scenarios.py` | scénarios de transformation : chemins, sources, garde-fous, requête, sans Qt |
| `xslt_engines.py` | moteurs des scénarios (lxml, Saxon), sans Qt |
| `transform_worker.py` | processus d'une transformation (Varians relancé avec `--transform-worker`), sans Qt |
| `transform_runner.py` | client de ce processus : lancer, annuler, compte rendu |
| `busy_indicator.py` | lueur animée de la barre d'état pendant une validation |
| `code_editor.py` | éditeur de la source XML (`CodeEditor`) |
| `formatted_view.py` | aperçu XSLT/CSS et édition par fragments |
| `manuscript_panel.py` | panneau d'un témoin manuscrit |
| `image_fetch.py` | téléchargement des images, cache disque |
| `help_dialogs.py` | aide, dictionnaire latin, « À propos » |
| `app_context.py` | traductions actives, réglages, projets récents, version |

Les modules de l'interface n'importent jamais `editeur_tei` (il peut être
exécuté comme script) : les services communs passent par `app_context`.
Tout nouveau module local importé par `editeur_tei.py` doit figurer dans
`_LOCAL_MODULE_NAMES` (un test le vérifie).

Un nouveau message de l'interface s'ajoute, traduit, aux sept catalogues
`i18n/*.xml` ; `CATALOG_SIZE` dans `tests/varians_source.py` donne le
nombre de messages attendu dans chacun.

## Documents auxiliaires

Un projet peut déclarer des documents XML auxiliaires (format décrit dans
`PROJECT_MANAGEMENT.md`). La fenêtre tient leur liste dans
`self.documents` : `self.edition_session` d'abord, puis une
`DocumentSession` par document, lue à son premier affichage.
`self.document` désigne toujours le document affiché, et
`show_document(session)` en change.

Règles pour le code de la fenêtre :

- ce qui vaut pour « le document » (texte, révision, état modifié,
  validation, schéma via `_schema_mode` / `_schema_file`) se lit dans
  `self.document` ou dans l'éditeur ;
- ce qui ne vaut que pour l'édition (témoins, `<lb/>` du pivot, aperçu,
  export web) vérifie `self._edition_displayed()` ou utilise
  `self.edition_session` ;
- une commande d'un panneau de témoin qui écrit dans l'édition se connecte
  via `self._edition_write(...)`, une navigation via
  `self._edition_navigation(...)` ;
- un résultat calculé en différé (minuterie, fil d'exécution) vérifie qu'il
  concerne encore le document affiché : les numéros de révision sont
  propres à chaque `QTextDocument`.

## Références entre documents

Un pointeur `#id` ou `fichier.xml#id` dans un attribut de
`xml_references.REFERENCE_ATTRIBUTES` (`ref`, `corresp`, `wit`, `edRef`…)
désigne un `xml:id`. Tout le calcul est dans `xml_references.py`, testé
sans Qt : `collect_ids`, `collect_references` et `ReferenceResolver`, qui
suit le sens standard des URI, comme les autres outils XML : `#id` désigne
le document lui-même, `fichier.xml#id` un autre fichier. Un `#id` dont la
cible n'existe que dans un autre document est un problème
(`other_document`) ; `explicit_pointer` donne la forme à écrire.
`target_elements` donne les éléments attendus (`persName/@ref` →
`person`…). Le mixin `references_ui.py` lui fournit les textes
(`_session_text` : l'éditeur pour le document affiché, puis le texte en
mémoire, puis le fichier).

Règles :

- la liste des identifiants (frappe de `#`, Ctrl+Espace) relit à chaque
  frappe un index mis en cache par document (`_session_ids`), recalculé
  seulement quand la liste des `xml:id` change : ses positions peuvent être
  périmées, la navigation et la vérification recalculent les leurs ;
- `CodeEditor` ne connaît pas la fenêtre : il reçoit des rappels facultatifs
  (`attribute_completion_provider`, `value_completion_provider`,
  `reference_click_provider`, `context_menu_provider`). L'éditeur de
  fragment de l'aperçu ne reçoit que ceux de la complétion ; l'éditeur de
  `custom-elements.xml` aucun ;
- les panneaux du bas (validation, XPath, références) forment la liste
  `self._bottom_panels` : un seul est visible à la fois
  (`_show_bottom_panel`, `_hide_bottom_panel`) ;
- la vérification des références n'est qu'une aide : elle n'empêche jamais
  d'enregistrer et ne modifie aucun fichier.

## Éditions assemblées (XInclude)

Depuis V0.9.0.0, l'édition peut inclure ses parties par `xi:include` (voir
`docs/DECISIONS_ASSEMBLAGE.md`). Le calcul est sans Qt :
`xml_assembly.assemble` (copie de chaque élément inclus, fichier d'origine
de chaque copie, `visible_ids`), `relaxng_validation.validate_assembled`
(erreurs ramenées à leur fichier, `ValidationIssue.file`),
`ReferenceResolver(documents, groups)` et `apparatus_xpath.part_witnesses`.

Règles :

- une partie est une `DocumentSession` de rôle `part` (`is_part`,
  `in_edition`) ; la liste des parties suit les `xi:include` de l'édition
  enregistrée (`_init_documents`, `_refresh_parts` après chaque
  enregistrement de l'édition ou d'une partie) ;
- `_assembly_context()` vaut l'édition si le document affiché en fait partie
  et qu'elle a des parties : la validation porte alors sur l'édition
  assemblée, avec le schéma de l'édition. Le résultat est rangé sur
  l'édition et ses parties (`_share_assembled_result`) ; `_assembly_changed`
  (relié à `contentsChanged`, comme `_text_changed`) le rend périmé pour
  les autres documents ;
- la Vue XSLT / CSS transforme `_assembled_preview_text()` (l'édition
  assemblée) : sans marqueurs d'édition ni de ligne, `load_fragment` refusé,
  pas de report de position entre la source et l'aperçu ;
- synchronisation des témoins (V0.9.1.0, cas 1 : numérotation continue) :
  `pivot_lines.pivot_lines` assemble l'édition et numérote les
  `<lb edRef="#pivot"/>` dans l'ordre du document assemblé ; chaque numéro
  est rattaché, dans son fichier, au `<lb/>` que trouve `lb_base_re` (même
  ligne, même rang dans la ligne), et chaque `xi:include` reçoit le dernier
  numéro atteint à la fin de son contenu (`Assembly.site` donne la ligne du
  `xi:include` de chaque copie). Côté fenêtre, `_pivot_lines()` (en cache
  selon les révisions ; gardé pendant la saisie tant que le document
  affiché garde ses `<lb/>` et ses `xi:include`), `_base_ordinal_at` /
  `_base_ordinal_at_cursor` (curseur → ligne du pivot), `_show_base_ordinal`
  (ligne → curseur, en affichant la partie) et `_base_line_count` (état de
  structure, avertissement à l'enregistrement). Sans parties, ces méthodes
  reviennent à l'index du document affiché, comme avant ;
- mode page : `PivotLines.page_at` cherche le dernier `<pb>` d'un témoin
  dans l'ordre assemblé (règle commune `folio_navigation.pb_folio`) ; les
  folios sont lus dans le `<facsimile>` de l'édition (`_edition_text`).
  « Marquer la page » et « Couper le folio » écrivent dans l'édition non
  affichée par `_write_edition_text` (correctif `_patch_text_document`) ;
- `_apply_edition_ui` distingue deux groupes : l'aperçu et « Enregistrer
  l'édition sous… » (édition seule) ; les témoins, l'état de structure et
  leurs commandes (édition et parties, `document.in_edition`) ;
- textes synchronisés à part (V0.9.1.1, cas 2) : `text_alignments.text_syncs`
  trouve les parties qui ont leur dossier `alignments/<nom>/` (pivot :
  `ProjectConfig.parts`, sinon celui du projet) ; `text_project` réduit le
  projet à un texte pour `assemble_resources`. `pivot_lines(...,
  text_bases=...)` fait de chacun un segment (`FileLines.segment`,
  `segment_count`, `location(ordinal, segment)`). Côté fenêtre, le mixin
  `text_segments.TextSegmentsMixin` : `_document_segment`, `_switch_segment`
  (appelé par `_attach_document` via `_update_segment`), `_segment_state`
  (état d'un texte lu à sa première visite), `_apply_runtime_state`
  (commun avec « Actualiser les synchronisations » : pivot, panneaux,
  `ManuscriptPanel.set_base` et `set_absent`). `base_id`, `lb_base_re` et
  `base_panel` suivent donc le segment affiché ; `_pivot_lines` compte
  toujours avec le pivot du projet et `pivot_lb_pattern` ;
- sélections partagées de la Vue XSLT / CSS (V0.9.1.2) :
  `formatted_view.xml_occurrences`, `xml_selection_descriptor` et
  `pick_xml_occurrence` retrouvent dans un texte XML (la source ou le
  fragment ouvert) l'occurrence d'un texte visible de l'aperçu, par son rang
  dans le paragraphe, sinon par sa position ; les méthodes de `MainWindow`
  qui reportent la sélection entre Source et XSLT / CSS les utilisent.
  `ClickablePreview.textSelected` (relâchement de la souris sur une
  sélection, hors liens) mène à `_preview_selection_to_fragment` ;
  `fragment_editor.selectionChanged`, après 150 ms, à
  `_fragment_selection_to_preview`, qui appelle
  `select_visible_text_in_paragraph(..., focus=False)`. Le crayon ✎ appelle
  `load_fragment(idx)` sans toucher à la source ni aux témoins. Tests :
  `tests/gui/test_gui_selection_transfer.py` ;
- lacunes et témoins par pages des textes à part (V0.9.1.3) :
  `lacunae.lacuna_events` / `lacunae_at` (relevé lexical, sans Qt) ;
  `pivot_lines` relève aussi les lacunes et les `<pb>` par segment
  (`PivotLines.lacunae_at`, `page_witnesses`, `first_page` ; `page_at` ne
  remonte, dans un texte à part, qu'aux `<pb>` de ce texte). Côté fenêtre :
  `_lacunae_at_cursor` (relevé gardé par révision), `_follow_base_line`
  (commun au curseur, à l'aperçu et aux flèches du pivot ; l'état des
  lacunes entre dans le test « rien n'a changé »), `ManuscriptPanel.
  set_lacuna` (bandeau). `folio_navigation.witness_loci`, `page_folios`,
  `text_start_folio` ; `text_alignments.text_project(..., page_witnesses)` ;
  `TextSegmentsMixin._text_page_witnesses` (relu à chaque visite d'un
  texte) et `_text_start_folio`. Les objets factices des tests historiques
  fournissent `_lacunae_at_cursor` et `set_lacuna` ;
- parcours d'un témoin dans son propre ordre (V0.9.1.4) : `witness_route`
  (sans Qt : `Source`, `PageMark`, `Stop`, `WitnessRoute.step`, `on_page`,
  `first`, `last` ; rangs des pages par `declared`, fusion des listes de
  pages, `<locus from>` ou foliotation, sinon ordre de l'édition) ; côté
  fenêtre, `TextSegmentsMixin._witness_route` et
  `_witness_panel_navigate` ;
- Vue XSLT / CSS de l'édition assemblée (V0.9.1.5) : `preview_sources.py`
  (fichier et place de chaque `<p>` et de chaque `<lb>` du pivot),
  `navigate_to_preview_line`, `_write_session_text` (fragment écrit dans
  sa partie), `paragraph_at` et `line_before` ;
- export web de l'édition assemblée (V0.9.1.6) : `segment_model.py` (règles
  des textes à part et du parcours, communes à la fenêtre et à l'export),
  `web_viewer/assembled_document.py`, `build_segment_lb_index`, les
  extracteurs de `legacy_v11_core` selon le texte, `generator._add_text_views`
  et `_add_routes`, `web_viewer/segment_views.py` et `web_viewer/sync_model.js`
  (voir `WEB_VIEWER_ASSEMBLED.md`). Une édition en un seul fichier est
  exportée comme avant : `tests/test_v0916_single_file_export.py` fige
  l'empreinte de ses données.
  `PivotLines.pb_marks` et `anchor`, `folio_navigation.folio_marks`. Côté
  fenêtre : `ManuscriptPanel.navigate` émet `witnessNavigate` (`browse`
  feuillette) ; `_witness_panel_navigate`, `_go_to_witness_stop`,
  `_lead_to_page`, `_present_stop` (`witness_sync`) ;
  `_show_segment_ordinal` (`document_tabs`) ; `_witness_route`,
  `_route_sources`, `_route_runs` (`text_segments`, parcours gardé tant que
  la numérotation et les états des textes ne changent pas). Tests :
  `tests/test_witness_route.py`, `tests/gui/test_gui_witness_route.py`,
  `tests/gui/test_gui_witness_pages_route.py` ;
- Vue XSLT / CSS d'une édition assemblée (V0.9.1.5) : `preview_sources`
  (sans Qt : `PreviewSources.paragraphs`, `lines`, `paragraph_at`,
  `line_before`) ; `_assembled_preview_sources`, `_edition_file_session`,
  `_show_file_position`, `navigate_to_preview_line` (`document_tabs`) ;
  `FormattedEditionWidget.sources` (calculées à chaque rendu),
  `_activate_line`, `_fragment_source`, `fragment_session`,
  `dirty_fragment_session` ; `_write_session_text` (`witness_sync`,
  écriture dans un document non affiché) ; dans `_left_tab_changed`, le
  report passe par `navigate_to_preview_line` et par les paragraphes des
  sources. Une édition sans parties garde le chemin d'avant
  (`paragraph_spans`, rang des `<lb/>`). Tests :
  `tests/test_preview_sources.py`, `tests/gui/test_gui_assembled_preview.py`,
  `tests/gui/test_gui_assembled_fragment.py`,
  `tests/gui/test_gui_assembled_selection.py` ;
- minuteries : un appel différé qui touche la fenêtre ou l'un de ses
  widgets passe par `app_context.call_later(msec, objet, ...)`, jamais par
  un `QTimer.singleShot` nu : les tests GUI détruisent leurs fenêtres, et
  un appel qui survit à la sienne échoue au démontage du test ;
- des tests anciens exécutent le corps de certaines méthodes avec des objets
  factices (`_text_changed`, `_auto_refresh_rng`, `show_validation_panel`,
  `_validate_relaxng_document_impl`, `sync_panels_to_cursor`,
  `_sync_page_panels_to_cursor`, `_mark_page_in_tei`,
  `_split_double_folio`, `refresh_witness_synchronizations` et
  `_apply_runtime_state`…) : une nouvelle méthode appelée par ces corps doit
  être ajoutée à ces objets ;
- jeux de données : `tests/corpus_data.py` (le jeu sermons avec des
  alignements fabriqués, et `split_alignments`, qui découpe les vrais JSON
  du projet exemple pour un texte : fixtures `corpus_project` et
  `example_with_text`) ; `tests/data/sermons` (copie du projet d'essai « Essai
  sermons Varians »), copié dans `tmp_path` par les fixtures
  `sermons_project` et `collection_project` de `tests/gui/conftest.py`. La
  seconde réduit l'édition à trois courts sermons, avec un schéma explicite
  qui situe chaque erreur sans erreurs en cascade.

## Transformations XSLT de l'aperçu

`formatted_view.transform_with_xslt` emploie lxml (XSLT 1.0). Une feuille
peut lire des fichiers locaux (`document()`, `xsl:import`), mais ne peut ni
écrire de fichier (`exsl:document`), ni créer de dossier, ni accéder au
réseau. Une erreur de la feuille est signalée telle quelle, au format
`fichier:ligne: message` (`xslt_engines.xslt_error_text`, commun aux
scénarios). Le moteur .NET via PowerShell ne sert de secours que si lxml
n'est pas installé.

Les scénarios de transformation (V0.9.2.0) ont leurs propres règles :
lecture locale et réseau, écriture du seul résultat, processus à part,
moteurs lxml et Saxon ; voir `XSLT_SCENARIOS.md`. Une version autonome
(PyInstaller, Nuitka) devra embarquer `saxonche`.

## Feuilles XSLT éditées dans Varians

Depuis V0.9.2.1, une feuille XSLT affichée est vérifiée par compilation
(`xslt_check_ui`, requête `op: "check"` du processus de transformation) au
lieu d'être validée par RELAX NG, et complétée d'après le schéma XSLT 3.0 du
W3C (`xslt_completion`) ; voir `XSLT_SCENARIOS.md`. `_displayed_stylesheet`
est appelée par `_validate_relaxng_document_impl` : les objets factices des
tests anciens qui exécutent ce corps la fournissent (elle rend None).

Le schéma livré, `resources/schemas/xslt30/schema-for-xslt30.rng`, est tiré
du RNC du W3C par `rnc2rng` (outil de développement, `pip install rnc2rng`,
non installé avec Varians) : la marche à suivre pour le refaire est dans
`resources/schemas/xslt30/LISEZMOI.md`. Une version autonome devra embarquer
le dossier `resources/schemas`.

## TEI Stylesheets

Depuis V0.9.2.2, Varians livre les TEI Stylesheets du TEI Consortium
(`resources/tei-stylesheets/tei-xsl-7.61.0.zip`) et les installe dans le
dossier de données de l'utilisateur (`tei_stylesheets.library_dir`) ; voir
`XSLT_SCENARIOS.md`. Pour livrer une nouvelle version, suivre
`resources/tei-stylesheets/LISEZMOI.md` : télécharger l'archive publiée, ne
garder que `xml/tei/stylesheet/` et `doc/tei-xsl/LICENCE` (script donné),
remplacer l'archive du dossier (il n'en contient qu'une), mettre à jour le
LISEZMOI, puis lancer les tests : `tests/test_tei_stylesheets.py` contrôle
l'archive livrée, `tests/test_tei_scenarios_saxon.py` les quatre scénarios
et la feuille de personnalisation.

Pendant les tests, la bibliothèque est un dossier temporaire commun à la
session (variable `VARIANS_TEI_STYLESHEETS`, posée par `tests/conftest.py`
et `tests/gui/conftest.py`) : rien n'est écrit dans le dossier de
l'utilisateur. Le réseau est bloqué dans les tests de l'interface
(`_no_network` couvre `tei_stylesheets.urlopen`) ; les tests de
`tei_stylesheets` emploient un petit serveur http local, et ceux de la
fenêtre un faux TEI-C (`FakeTeiC`). Une version autonome devra embarquer le
dossier `resources/tei-stylesheets`.

## Historique et versions

Depuis V0.8.6.0, l'historique est porté par Git. Les rapports de test et
addenda de passation produits version par version, ainsi que le manifeste
SHA-256, ne sont plus générés ; les anciens sont archivés dans
`docs/historique/`. Le dossier de passation majeure de V0.8.5.26.2 se
trouve dans `docs/passation_V0.8.5.26.2/` : ses invariants scientifiques
restent la référence.

La version affichée par l'application est `APP_VERSION` dans
`app_context.py`. Pour une nouvelle version : modifier `APP_VERSION`,
`CURRENT_VERSION` dans `tests/varians_source.py`, l'en-tête de
`editeur_tei.py`, ajouter une section en tête de `README.txt` et une section
`<section id="vXYZ">` dans chacune des sept aides (`help/*.html`) ;
`tests/test_version.py` vérifie l'ensemble.

Les décisions arrêtées pour les versions suivantes (éditions assemblées par
XInclude, choix des onglets affichés) sont consignées dans
`docs/DECISIONS_ASSEMBLAGE.md`.

## Défauts connus

Aucun défaut hérité de V0.8.5.26.2 n'est actuellement connu. Corrigés en
V0.8.6.0 :

- la lenteur à la frappe d'une balise ouvrante dans un long document
  (recherche de la balise fermante de coût quadratique dans
  `xml_tag_pairs`) — voir `tests/test_xml_tag_pairs_performance.py` ;
- l'index des `<lb/>` momentanément périmé lorsqu'on modifiait l'intérieur
  d'une balise sans saisir `<` ni `>` (ex. `edRef="#T"` → `"#T1"`) — voir
  `tests/test_document_session.py` ;
- l'erreur `Signal source has been deleted` affichée si une fenêtre était
  fermée pendant un téléchargement d'image — voir
  `tests/gui/test_gui_image_fetch.py` ;
- les erreurs affichées si une fenêtre était détruite peu après
  l'ouverture d'un document (appels différés) — voir
  `tests/gui/test_gui_delayed_calls.py`. Pour programmer un appel différé
  visant une fenêtre ou un widget, utiliser `app_context.call_later`.
