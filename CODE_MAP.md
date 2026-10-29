# Varians — carte rapide du code (V0.8.5.0)

Ce fichier complète `DEVELOPER_HANDOFF.md`. Il sert de repère rapide pendant une intervention.

| Besoin | Fichier principal | Tests représentatifs |
|---|---|---|
| Lire `project.xml` | `project_config.py` | `test_v063_project_layout.py`, `test_v070_image_sources.py` |
| Créer/modifier un projet | `project_management.py`, `project_dialogs.py` | `test_v071_new_transcription.py` à `test_v076_optional_sync.py` |
| Images locales / IIIF | `image_sources.py`, `iiif_manifest.py`, `iiif_local.py` | `test_v073_local_images.py`, `test_v074_iiif_manifest.py`, `test_v085_page_iiif_local.py` |
| Import ALTO/PAGE, polygones | `alto_import.py` | `test_v075_alto_import.py`, `test_v085_page_iiif_local.py` |
| Décider page vs ligne | `resource_state.py` | `test_v084_consolidation.py` |
| `<facsimile>` / `<pb>` | `tei_facsimile.py` | `test_v079_facsimile_pages.py`, `test_v082_page_sync.py` |
| Validation RELAX NG | `relaxng_validation.py`, `schema_resolution.py` | `test_relaxng_validation.py` |
| Complétion RNG | `rng_completion.py` | `test_rng_completion.py`, `test_rng_context_cache.py` |
| Suggestions projet | `custom_completion.py` | `test_custom_completion.py` |
| Paires XML | `xml_tag_pairs.py` | `test_v080_xml_tag_pairs.py` |
| Indentation sûre | `tei_formatter.py` | `test_v081_tei_formatter.py` |
| XPath | `xpath_search.py` | `test_xpath_search.py`, `test_v0841_xpath_help.py` |
| Rechercher et remplacer (V0.9.2.8) | `text_search.py`, `code_editor.py`, `replace_bar.py`, `main_menus.py` | `test_text_search.py`, `gui/test_gui_search_replace.py`, `gui/test_gui_search_options.py`, `gui/test_gui_replace_bar.py`, `gui/test_gui_menus_edit_search.py` |
| Recherche dans l'aide (V0.9.2.8) | `help_search.py`, `help_dialogs.py` | `test_help_search.py`, `gui/test_gui_help_search.py` |
| Tout lister : occurrences en contexte (V0.9.2.8) | `text_search.py` (`kwic`), `search_results.py` | `test_text_search.py`, `gui/test_gui_search_results.py` |
| Menu ▾ de tous les onglets (V0.9.2.8) | `document_tabs.py` | `gui/test_gui_document_tabs_menu.py` |
| Bouton au livre : mener l'édition ou feuilleter (V0.9.2.8.1) | `manuscript_panel.py`, `witness_workspace.py`, `resources/icons/feuilleter.svg` | `gui/test_gui_witness_lead.py` |
| Choix de l'élément de Ctrl+E (V0.9.2.8.1) | `completion_ui.CompletionDialog` | `gui/test_gui_ctrl_e_choice.py` |
| Sigle et identifiant d'un témoin (V0.9.2.8.2) | `witness_ids.py`, `project_config.py`, `project_management.py`, `project_dialogs.py` | `test_witness_siglum.py`, `test_witness_siglum_outputs.py`, `gui/test_gui_witness_siglum.py`, `gui/test_gui_witness_siglum_display.py` |
| Témoin ajouté déclaré dans la `<listWit>` (V0.9.2.8.2) | `tei_listwit.py`, `project_actions.project_settings_dialog` | `test_listwit_witnesses.py`, `gui/test_gui_listwit_on_add.py` |
| Marquer la page : tout identifiant XML (V0.9.2.8.2) | `tei_facsimile.valid_xml_id`, `safe_id_component`, `apparatus_xpath` | `test_mark_page_xml_ids.py` |
| Crayon ✎ et F2 de la vue XSLT / CSS (V0.9.2.8.2) | `formatted_view.py` | `gui/test_gui_pencil_selection.py` |
| Contenu des publications (V0.9.2.8.2) | `.gitattributes`, `tests/data/exemple`, `web_viewer/generator.py` | `test_release_contents.py` |
| Éléments modifiables comme fragment (V0.9.2.9) | `fragment_units.py`, `formatted_view.py`, `preview_sources.py`, `document_tabs.fragment_unit_names` | `test_fragment_units.py`, `test_edit_markers.py`, `test_preview_sources.py`, `gui/test_gui_fragment_units.py`, `gui/test_gui_xslt_transform.py` |
| Rendu des vers, titres, listes, figures (V0.9.2.9) | `rendering/tei-to-html.xsl`, `rendering/tei.css` | `test_tei_to_html_rendering.py` |
| Texte de lecture du viewer web (V0.9.3.0) | `web_viewer/legacy_v11_core.py` (`extract_reading_document`, `RENDERED_BLOCKS`), `web_viewer/generator.py` (`renderDocument`), `web_viewer/sync_model.js`, `web_viewer/fulltext_search.js`, `web_viewer/segment_views.py` | `test_web_reading_blocks.py`, `test_v0916_sync_model.py` (node), `test_viewer_reading_layout.py` (Chromium) |
| Théâtre : répliques, locuteurs, didascalies entre parenthèses (V0.9.3.1) | `web_viewer/legacy_v11_core.py` (`walk_speech`, `open_parenthesis`, `close_parenthesis`), `web_viewer/generator.py`, `rendering/tei-to-html.xsl`, `rendering/edition-critique.xsl`, `rendering/apparat-commun.xsl` (`f:texte-net`) | `test_web_reading_blocks.py`, `test_viewer_reading_layout.py` (Chromium), `test_tei_to_html_rendering.py`, `test_edition_critique_saxon.py` |
| Leçons hors `<lem>` surlignées (V0.9.3.1) | `web_viewer/legacy_v11_core.py` (`nonlem`), `web_viewer/generator.py` (`showNonLem`), `project_config.py`, `project_management.update_project_web_text`, `web_text_dialog.py`, `rendering/edition-critique.xsl`, `xslt_scenarios.BOOLEAN_PARAMS`, `transform_ui.py` | `test_web_text_choice.py`, `test_viewer_nonlem_highlight.py` (Chromium), `gui/test_gui_web_text_dialog.py`, `test_edition_critique_saxon.py`, `gui/test_gui_transform_scenarios.py` |
| Textes des feuilles livrées dans la langue de l'interface (V0.9.3.1) | `rendering/apparat-commun.xsl` (`f:libelle`, `f:textes-fr`), `rendering/edition-critique.xsl`, `rendering/apparat-en-notes.xsl`, `rendering/tei-to-html.xsl` (modèles `texte`, `texte-fr`, `texte-avec`, `detail`), `i18n/*.xml` (`publication.*`), `xslt_scenarios.py` (`catalogs_uri`, `LANGUAGE_PARAM`, `CATALOGS_PARAM`, `${langue}`), `formatted_view.publication_params`, `transform_ui._language_combo` | `test_publication_texts.py`, `test_xslt_scenarios.py`, `test_edition_critique_saxon.py`, `test_apparatus_notes_saxon.py`, `test_tei_to_html_rendering.py`, `gui/test_gui_transform_scenarios.py` |
| Aide (V0.9.3.1) : un chapitre par tâche, sept langues | `help/*.html`, `main_menus.py` (`TEI_GUIDE_URL`) | `test_help_structure.py`, `test_i18n_keys.py`, `gui/test_gui_apparatus_debug.py` |
| Frappe rapide avec des fac-similés (V0.9.3.2) | `witness_sync._refresh_folio_navigation`, `image_sources.surface_labels`, `folio_navigation` (`facsimile_markup`, `facsimile_surfaces`, `folio_marks`, `_pb_tags`, `_TextMemo`) | `test_folio_refresh_performance.py` |
| Tableaux dans les feuilles livrées (V0.9.3.0) | `rendering/tei-to-html.xsl`, `rendering/tei.css`, `rendering/edition-critique.xsl`, `fragment_units._DIVE_RE` | `test_tei_to_html_rendering.py`, `test_edition_critique_saxon.py`, `test_edit_markers.py` |
| Sync sélection XML/XSLT | `selection_sync.py`, `editeur_tei.py` | `test_selection_onglets_sans_qt.py`, `test_v083_display_navigation.py` |
| UI desktop | `editeur_tei.py` | tests statiques versionnés + tests manuels Qt |
| Viewer web | `web_viewer/generator.py` | `test_v082_page_sync.py`, `test_v084_consolidation.py` |
| Viewer web d'une édition assemblée (V0.9.1.6) | `web_viewer/assembled_document.py`, `web_viewer/segment_views.py`, `web_viewer/sync_model.js`, `segment_model.py` | `test_v0916_export_*.py`, `test_v0916_sync_model.py` (node), `test_v0916_viewer_*.py` (Chromium) |
| Internationalisation | `i18n.py`, `i18n/*.xml` | `test_v0842_i18n_handoff.py` |
| Sauvegarde atomique | `save_io.py` | `test_save_io.py` |

## Invariants à vérifier avant commit

- ALTO ≠ synchronisation.
- JSON présent ≠ synchronisation exploitable.
- Pas de réécriture destructive du `<facsimile>`.
- Pas d'insertion « Marquer la page » dans une balise.
- Pas de blanc ajouté autour de `<lb/>`.
- `custom-elements.xml` n'altère pas la validité RNG.
- `base_keys` est le champ moderne ; `keys816` lecture seulement.
- Préférences de vue dans `QSettings`, données scientifiques dans `project.xml`.
- Tout changement page/ligne doit être examiné aussi dans le viewer web.


## Extension Varians 0.8.5 — PAGE XML et copies IIIF

Voir **PAGE_IIIF_LOCAL.md** pour les procédures, les formats ALTO/PAGE mixtes, les copies locales IIIF, les deux cases indépendantes par témoin (éditeur / export), les chemins, le protocole de cache et les limites. Les anciens projets restent lisibles sans migration.


## V0.8.5.2 — fichiers IIIF

- `iiif_selection.py` : rapprochement conservateur ALTO/PAGE ↔ pages de manifeste, rejet explicite des cas ambigus, aucune association ordinale.
- `iiif_local.py` : `plan_witness_copy` sans réseau ; `download_witness_copy` avec portée `all` / `ocr`, reprise, signaux d'arrêt/pause et index atomique.
- `iiif_download_manager.py` : interface PySide6, QThread de téléchargement, file de témoins, états et commandes.
- `project_config.py`, `project_management.py`, `project_dialogs.py` : sérialisation du `downloadScope` et choix par témoin.
- `editeur_tei.py` : lancement non modal et actualisation des images des panneaux sans toucher au TEI.
- `tests/test_v0852_iiif_manager.py` : sélection/ambiguïtés/reprise/compatibilité anciennes configurations.


> **Varians 0.8.5.3** : la sélection explicite des canvases IIIF et leur association aux OCR indépendamment du nom de fichier sont documentées en détail dans [IIIF_CANVAS_SELECTION.md](IIIF_CANVAS_SELECTION.md). Les projets antérieurs conservent le mode implicite `all`. Ne pas confondre le manifeste (catalogue) avec les pages sélectionnées de l’édition.


## 0.8.5.5 — Association JSON synchronisé ↔ IIIF

Voir [IIIF_SYNC_RESOLUTION.md](IIIF_SYNC_RESOLUTION.md). Le moteur commun `iiif_resolution.py` associe les identifiants de pages des JSON Varians-Synchro à des Canvas IIIF v2/v3 sans appariement positionnel, en conservant les `base_keys`, les copies de travail et les choix éditoriaux. Les associations manuelles `pageLink` sont sauvegardées dans `project.xml`.


## 0.8.5.6 — Initialisation TEI depuis le témoin pivot

Module `tei_pivot_scaffold.py` (indépendant de Qt) : identification stable des pages éditoriales depuis `project_facsimile_pages`, association sans indice positional aux ALTO/PAGE/JSON, décompte des lignes et génération non destructive des jalons `<pb edRef facs>` et `<lb edRef>` sans zones.

Les dialogues `NewProjectDialog` et `ProjectSettingsDialog` présentent une case de préparation volontaire, la case `<lb/>` activée lorsque la préparation est choisie, et un aperçu avec confirmation et sauvegarde datée. `editeur_tei.py` intervient après la création/sauvegarde des surfaces existantes. Aucune donnée de synchronisation n'est modifiée. Pour des invariants et scénarios détaillés, consulter `TEI_PIVOT_SCAFFOLD.md` et `tests/test_v0856_pivot_scaffold.py`.


## Correctif 0.8.5.9

`image_sources.py::display_window_indices()` : limitation du contexte de
recadrage à la page et à la colonne physiques courantes, sans modification des
liaisons JSON. Tests : `tests/test_v0859_column_crop.py`.


## V0.8.5.11 — Navigation mixte
`MainWindow.sync_panels_to_cursor()` orchestre séparément les panneaux page (`_sync_page_panels_to_cursor` / `facsimile_ref_at_position`) et ligne (`set_primary`). Les panneaux page ne reçoivent jamais `set_primary`. `web_viewer/generator.py` applique les jalons de page propres à chaque témoin lors de `selectLine()`. Voir `MIXED_NAVIGATION.md`.

- **V0.8.5.13** : complétion des balises fermantes `</...` : moteur lexical dans `xml_tag_pairs.py`, suggestion `QCompleter` dans `CodeEditor` (`editeur_tei.py`), Ctrl+Espace compatible avec RNG. Voir `XML_EDITING.md`.


## V0.8.5.14 — ALTO/PAGE indépendant et conservation des images IIIF

Cas corrigé : un témoin L sans JSON s'affichait via le manifeste IIIF et ses
copies locales. Après ajout de fichiers ALTO/PAGE, le cache OCR nouvellement
peuplé prenait implicitement la place du catalogue d'images ; faute de
correspondance sûre entre ses noms et les Canvas, la couche IIIF pouvait
attribuer `image.type=none` à toutes les pages et ne plus afficher les images.

Pour les caches de type `varians-layout-cache` (sans alignement éditorial),
`iiif_resolution._layout_only_manifest_pages()` garde désormais la sélection
IIIF comme source canonique et y superpose seulement la géométrie résolue :
  - `@id` de Canvas, service et image IIIF ;
  - `ocrLink` explicite ;
  - libellé de folio exact et unique ;
  - nom exact du fichier image téléchargé, vérifié par l'index local IIIF.
L'index local est lu une seule fois ; tous les contrôles sont hors ligne.
Les identifiants de page et de surface issus du manifeste restent stables.
Les identifiants de page répétés dans plusieurs ALTO/PAGE ne sont jamais une
preuve de correspondance ; des identifiants temporaires ne servent qu'à rendre
l'analyse du contexte non ambiguë.

Les ressources non identifiées sont conservées en mémoire dans
`cache['unassociated_layout_pages']` et dénombrées dans
`cache['meta']['iiif_unassociated_layout_count']`. Elles ne deviennent pas des
pseudo-pages vides et ne remplacent jamais une image IIIF. Une infobulle
multilingue dans l'en-tête du panneau informe l'utilisateur qu'il faut
associer les fichiers OCR aux Canvas dans les paramètres du témoin.
Cette distinction ne touche pas au traitement des synchronisations JSON
`tei-manuscript-alignment`, dont les `base_keys` et identifiants demeurent
strictement protégés. L'éditeur et le viewer web utilisent le même correctif.

Tests : `tests/test_v08514_iiif_alto_independence.py` (manifeste complet ou
sélection, import ALTO avant/après, copies locales avec/sans association,
liens OCR manuels, conflits, IDs ALTO répétés, export web, intégrité des JSON).

## V0.8.5.15 — Cadres et image IIIF réduite ; diagnostic des JSON secondaires

Une image IIIF peut être représentée par une ressource de dimensions inférieures
à celles du Canvas (ex. aperçu 490 px pour un Canvas de 3924 px). Avant 0.8.5.15,
le mode page utilisait les dimensions de ce bitmap comme coordonnées physiques
pour dessiner les contours ALTO/PAGE calculés dans les dimensions du Canvas.
Les contours pouvaient alors étendre les bornes de la scène et rendre le zoom
« 100 % » anormalement petit. `image_scene_reference_crop` dans
`image_sources.py` restitue le repère d'origine à `ManuscriptPanel._redraw_scene` ;
les coordonnées source et les fichiers sont conservés. Pour les demandes IIIF
sans crop, l'URL de service Image API pleine résolution est prioritaire,
avec le champ `image` du manifest en repli.

Un JSON configuré sans `base_keys` demeure volontairement en mode page. Une
alerte localisée dans `ManuscriptPanel.sync_issue` l'explique ; une autre alerte
signale des liens ne correspondant à aucune clé du pivot. Les cadres ALTO
sont indépendants de ce diagnostic. Sans le fichier de synchronisation L.json
réel, on ne doit pas affirmer que ses liens sont présents ou corrects.


## V0.8.5.17 — Diagnostic / actualisation

Voir `WITNESS_DIAGNOSTICS.md`. Le module `witness_resource_refresh.py` centralise le rapport indépendant de Qt et la préparation transactionnelle des ressources. L’éditeur conserve sa TEI, sa pile d’annulation et ses panneaux ; il ne commet le rechargement qu’après validation. La synchronisation n’est jamais déduite des seules données ALTO/PAGE.


Varians V0.8.5.18 — Navigation par folios et images doubles
Voir FOLIO_NAVIGATION.md. Une surface peut contenir deux zones de folio ; aucun changement des JSON/ALTO ou des images source.


## Varians V0.8.5.20 — Correction du dialogue « Double page… »

Le bouton `ManuscriptPanel.split_folio_btn` reste actif en mode lignes ; `_request_split_folio` émet même une surface absente afin que le contrôleur affiche un avertissement. `_split_double_folio` contrôle la surface TEI puis ouvre `QDialog`, et ne navigue vers le folio gauche que pour un panneau en mode page.


## Varians V0.8.5.20 — Navigation en image double, ergonomie et sécurité TEI

Consulter `DOUBLE_PAGE_PARTS.md`. `editeur_tei.py` intègre `SplitImagePreview` (QWidget), `SplitPreviewLoader` (QObject slot GUI), les données pixellaires de séparation et l’utilisation de la géométrie des lignes dans « Marquer la page ». `folio_navigation.py` expose `markable_part_for_line`, `inspect_surface_part_split` et `configure_surface_parts`. On refuse tout écrasement des zones TEI non créées par Varians et tout changement de libellé d’une zone déjà référencée par <pb/>. Le séparateur en pixels exacts est un paramètre optionnel, et l’ancienne API split_percent reste disponible. Vérifier l’affichage réel sous Windows/PySide6 (non installé en CI).


## Extension 0.8.5.21 : dispositions de travail

Voir [`WORKSPACE_LAYOUT.md`](WORKSPACE_LAYOUT.md). Les vues verticale, horizontale, grille, les fenêtres individuelles et le mode « Toujours au premier plan » ne changent que les préférences d’affichage `QSettings`. Le même `ManuscriptPanel` est transféré entre parents Qt ; `workspace_layout.py` ne contient pas de logique de synchronisation. Le ratio XML/manuscrits est librement redimensionnable, y compris vers 20 % XML.

## V0.8.5.22 — XML folding

`xml_folding.py` calcule les régions lexicalement fiables ; `CodeEditor` masque/rétablit les blocs QTextBlock sans toucher au XML. Documentation : `XML_FOLDING.md`.

## V0.8.5.23 — XML bidirectional highlighting

- `xml_tag_pairs.py` : `closing_pair_at_context` et `pair_at_context` pour détecter une paire sans supposer une fermeture incorrecte.
- `editeur_tei.py`, `CodeEditor.highlightCurrentLine()` : deux `ExtraSelection` de même couleur, balise ouvrante et fermante ; aucune écriture dans `QTextDocument`.
- `tests/test_v08523_bidirectional_tag_highlight.py` : sécurité XML, imbrication, namespaces, autofermantes et branchement statique.

## V0.8.5.24 — Visualiseur web
`web_viewer/geometry.js` est le noyau géométrique JavaScript sans DOM, incorporé dans le HTML autonome à la génération. Sa parité avec les fonctions Python `image_sources.py` et `editeur_tei.py` est testée dans `tests/test_v08524_web_geometry.py`. Les transformations et la synchronisation scientifique restent indépendantes.

### V0.8.5.25.1 — `web_viewer/page_resolver.py`

Résolution sans inférence des liens TEI `pb/@facs` / `surface` / `zone` vers les IDs physiques JSON, partage du même résolveur entre la construction des lignes du pivot et la vue de lecture web. Diagnostic intégré aux données exportées. Voir `WEB_VIEWER_LINE_SYNC_FIX.md`.

## Ajouts V0.8.5.26
`editeur_tei.py` : relance temporisée des diagnostics RNG et menu de complétion des attributs dans `CodeEditor`. `web_viewer/fulltext_search.js` : indexation/équivalences graphiques/offsets. `web_viewer/generator.py` : commandes de recherche, balisage des occurrences et synchronisation sur clic. `tests/test_v08526_interim_features.py` : contrat non-Qt des fonctions.

V0.8.5.26.1 : `web_viewer/generator.py` prend un `display_witness_ids` optionnel. Depuis `MainWindow.generate_web_viewer`, ce paramètre est dérivé de `_witness_display_order` et `_visible_witness_ids` (QSettings) ; il n’est jamais inscrit dans `project.xml`. Le pivot reste un index interne masqué quand nécessaire.

## V0.8.5.26.2 — rafraîchissement RELAX NG

Dans `editeur_tei.py`, regarder `show_validation_panel`, `_text_changed`, `_auto_refresh_rng`, `validate_relaxng_document` et `_validate_relaxng_document_impl`. Les tests de cycle isolés `tests/test_v085262_rng_panel_refresh.py` exercent les vraies méthodes Qt sans dépendre de PySide6 à la compilation. Le cache lxml reste dans `relaxng_validation.py` ; ni les schémas ni le viewer web n'ont été modifiés.

## V0.9.1.6 — export web d'une édition assemblée

Format des données et fonctionnement : `WEB_VIEWER_ASSEMBLED.md`.

- `segment_model.py` : règles des textes à part et du parcours, sans Qt, communes à la fenêtre (`text_segments.py`, `witness_sync.py`) et à l'export.
- `web_viewer/assembled_document.py` : `load_assembled(project)` lit l'édition assemblée (None sans `xi:include`) ; chaque élément est rattaché à son texte (`segment`, `target`).
- `web_viewer/tei_line_anchors.py` : `build_segment_lb_index` compte les `<lb>` du pivot de chaque texte.
- `web_viewer/legacy_v11_core.py` : extracteurs selon le texte (`root`, `line_anchors`, `segment_of`, `target_of`), repères de lacune, `pb_line_keys`.
- `web_viewer/generator.py` : `_text_caches`, `_add_text_views`, `_add_routes` ; le gabarit (`buildState`, `activateSegment`, `updateLacunae`, `leadFrom`, `goToStop`, `leadToPage`).
- `web_viewer/segment_views.py` : `doc_positions`, `page_marks`, `export_route`, `page_leads`, `locus_leads`.
- `web_viewer/sync_model.js` (`VariansSync`, sans DOM) : `docIndex`, `segAt`, `lastLinked`, `segOfKey`, `lacunaStarts`, `lacunaeAt`, `lineStops`, `pageStops`, `routeIndex`, `step`, `panelStop`, `presentStop`.
- `project_actions.py` : `_save_edition_for_export` (édition, parties modifiées, fragment non appliqué).

## V0.9.2.0 — scénarios de transformation XSLT

Fonctionnement, format et sécurité : `XSLT_SCENARIOS.md`.

- `project_config.py` : `TransformScenario`, `ProjectConfig.transformations`, `_parse_transformations` ; `project_management.py` : `transformations_element`, `update_project_transformations`.
- `xslt_scenarios.py` : `resolve_path`, `scenario_path`, `stylesheet_path`, `predefined_scenarios`, `project_sources`, `scenario_source`, `scenario_problems`, `scenario_request`.
- `xslt_engines.py` : `run`, `TransformResult`, `_run_lxml` (résolveur réseau), `_run_saxon` (deux passages pour `xsl:result-document`), `_write_outputs`.
- `transform_worker.py` (`--transform-worker`) et `transform_runner.py` (`TransformRunner`).
- `transform_ui.py` : `ScenarioListDialog`, `ScenarioDialog`, `TransformScenariosMixin` (`run_transform_scenario`, `_save_for_transform`, `_transform_finished`).

## V0.9.2.1 — feuilles XSLT éditées dans Varians

Fonctionnement : `XSLT_SCENARIOS.md` (« Feuilles éditées dans Varians »).

- `document_dialogs.py` : `document_target_path` (feuille hors du projet → `xslt/`), `free_path`, `new_stylesheet_text`, `new_stylesheet_dialog` (« Nouvelle feuille XSLT… ») ; `project_management.create_portable_project` crée `xslt/`. `main_menus.py` : le sous-menu Fichier ▸ « Documents XML / XSLT du projet… » (`documents_menu`) suit « Paramètres du projet… ».
- `transform_ui.py` : « Ouvrir la feuille » (`ScenarioListDialog.open_stylesheet`, `ScenarioDialog._accept_and_open`, `TransformScenariosMixin.open_scenario_stylesheet`, `_show_stylesheet`).
- `xslt_scenarios.py` : `stylesheet_info` (`StylesheetInfo` : préfixe XSLT, version), `check_engines`.
- `xslt_engines.py` : `check` (`_check_lxml`, `_lxml_issues`, `_check_saxon`, `_saxon_issue`), `TransformResult.issues` ; `transform_worker` : `op: "check"`.
- `xslt_check_ui.py` : `StylesheetCheckMixin` (`_displayed_stylesheet`, `_update_check_labels`, `_check_stylesheet`, `_check_now`, `_check_in_background`, `_apply_check_results`), `check_validation_result` ; branché dans `validation_panel._validate_relaxng_document_impl` et `document_io._write_to`.
- `xslt_completion.py` : `XSLT_SCHEMA` (`resources/schemas/xslt30`), `XSLT10_ATTRIBUTES`, `LITERAL_RESULT_ATTRIBUTES`, `element_names`, `attribute_names`, `attribute_values`, `StylesheetCompletionModel` ; `completion_ui._stylesheet_completion`.
- `rng_completion._analyze_xml_context_from` : un nom tapé devant une autre balise (`<h|</p>`) reste un nom d'élément.

## V0.9.2.2 — TEI Stylesheets

Fonctionnement : `XSLT_SCENARIOS.md` (« TEI Stylesheets »).

- `tei_stylesheets.py` (sans Qt) : `library_dir`, `parse_version`, `is_newer`, `Installed` (`catalog`, `licence`), `installed`, `active`, `install_zip` (`_destination`, `_extract`), `remove_old_versions`, `bundled_zip`, `ensure_installed`, `latest_version`, `download`, `LibraryError` ; archive livrée `resources/tei-stylesheets/` (LISEZMOI).
- `xslt_scenarios.py` : `TEI_PREFIX` (`${tei}/`), `tei_library`, `TEI_SCENARIOS` et `predefined_scenarios(translate, language)`, problème `tei_missing`, `catalogs` et `library` dans `scenario_request` (`_employs`), `check_request`, `customization_name`, `customization_text` (`_wrap`).
- `xslt_engines.py` : `_saxon_catalogs` (exécution et vérification), journal `library`.
- `transform_ui.py` : `TransformScenariosMixin._customize` (« Ouvrir la feuille » d'un scénario TEI), `_use_stylesheet`, `tei_stylesheets_dialog` ; `ScenarioListDialog.tei_stylesheets` (bouton « TEI Stylesheets… ») ; `predefined()` passe la langue de l'interface. `xslt_check_ui._check_stylesheet` emploie `check_request`.
- `tei_stylesheets_ui.py` : `TeiStylesheetsDialog`, `at_launch` (appelée par `editeur_tei.main`), `check_for_update`, `install`, `_Task` (fil à part, résultat par signal), `busy`, `progress_dialog`, réglage `teiStylesheets/lastCheck`. `main_menus.py` : `action_tei_stylesheets`, après « Scénarios de transformation… ».
- `app_context.apply_qt_language` : traductions de Qt (`qtbase_<langue>.qm`, textes standard des boîtes et des boutons) dans la langue de l'interface ; appelée par `editeur_tei.main`, `MainWindow.__init__` et `MainMenusMixin._set_language_code`. Compte rendu d'une transformation : « Ouvrir le dossier » (`TransformScenariosMixin._transform_finished`).

## V0.9.2.3 — règles Schematron

Fonctionnement : `RELAXNG_VALIDATION.md` (« V0.9.2.3 — règles Schematron »).

- `schematron.py` (sans Qt) : `rules_text` (fichier `.sch`, ou règles intégrées à un RNG et aux RNG inclus), `compiled` (`_compile`, cache selon `_schema_dependency_signature`, `_transpiler` : `resources/schxslt2/transpile.xsl` compilé une fois avec ses paramètres statiques), `validate` → `SchematronReport` (`issues`, `rules`, `errors`, `error`), `_element_at` (emplacement SVRL → élément lxml), `_level`, `_saxon_text` et `_expression_site` (règle incorrecte : fichier et ligne), sortie d'erreur du processus (`relaxng_validation.STDERR_LOG`). SchXslt2 livré : `resources/schxslt2/` (LISEZMOI).
- `schema_resolution.py` : `SchemaResolution.schematron_sources`, `schematron_errors`, `_with_schematron_sources`, `_resolve_rng`.
- `relaxng_validation.py` : `validate_document(…, schematron=…)`, `_checked`, `_checked_assembled`, champs `schematron_rules`, `schematron_errors`, `schematron_error` de `ValidationResult` ; `relaxng_worker` (champ `schematron`), `validation_worker` (`schematron=`, `stderr_log`).
- `validation_panel.py` : colonne Origine (`_issue_origin`), `_is_error`, `_update_schematron_status`, `_show_schematron_result`, `_schematron_summary`, `_validation_token` ; `document_tabs` (état de l'étiquette Schematron de chaque document), `document_io._write_to` (question d'enregistrement, jeton).
- `project_management.minimal_tei_text` : déclaration Schematron de TEI All.


## V0.9.2.4 — phases et fichiers Schematron

Fonctionnement : `RELAXNG_VALIDATION.md` (« V0.9.2.4 — phases, règles incorrectes, fichiers `.sch` »).

- `schema_resolution.py` : `SchematronSource(path, phase)`, `_with_schematron_sources` (la phase d'une déclaration remplace celle de la même source).
- `schematron.py` : `compiled(path, phase)` (cache par couple), `_phases`, `_phase_error`, `_rule_error` (erreurs `SCHEMATRON_RULES`), `_saxon_error` (remplace `_saxon_text`), `_rules_trees` (fichier et inclusions, éventuellement d'après le texte de l'éditeur), `_transpiler(check)`, `check_compilation`, `_assembly_errors`, `_ASSEMBLY_SITES`.
- `schematron_check.py` (sans Qt) : `check(text, path)` → `ValidationResult` (bonne formation, structure d'après `resources/schemas/schematron/iso-schematron.rng` — `_structure_errors`, `_REQUIRED`, libxml2 en repli —, inclusions, compilation) ; `relaxng_worker` (`op: "check_schematron"`), `validation_worker` (`check_schematron`, `check_schematron_async`).
- `schematron_check_ui.py` : `SchematronCheckMixin` (`_displayed_schematron`, `_check_schematron`, `_apply_schematron_check`) ; branchements dans `xslt_check_ui._update_check_labels`, `validation_panel._validate_relaxng_document_impl`, `document_io._write_to`.
- `schematron_completion.py` (sans Qt) : `SchematronCompletionModel`, `SUGGESTED_VALUES` ; `completion_ui._vocabulary_completion` (feuille XSLT ou fichier Schematron).
- `xml_roots.py` : `root_tag` (racine lue sans analyser, partagée avec `xslt_scenarios.stylesheet_info`), `schematron_info`.
- `validation_panel.py` : lignes des règles incorrectes (`RULES_DOMAIN`, `_rules_message`, `_rules_located`, `_resolution_rules_errors`), `_open_rules_file` (double-clic), `_validation_outdated` (appelée par `document_tabs._restore_document_view`), phase dans l'info-bulle.
- `document_dialogs.py` : `SCHEMATRON_SUFFIXES`, `is_schematron_file`, `new_schematron_text`, `new_schematron_dialog` ; `main_menus.action_new_schematron`.

## V0.9.2.5 — règles non enregistrées, boîte des déclarations, norme 2020/2025, XSD

Fonctionnement : `RELAXNG_VALIDATION.md` (« V0.9.2.5 »).

- `schematron.py` : `compiled(path, phase, text)`, `validate(…, texts=…)`, `rules_text(path, text)`, `_phases(path, text)`.
- `relaxng_validation.py` : `validate_document(…, rules=…)`, `dependency_reference` (`href`, `schemaLocation`), `XSD_NS` ; `relaxng_worker` (champ `rules`, `_texts`), `validation_worker` (`rules=`).
- `validation_panel.py` : `_rules_texts`, `_validation_token` (méthode, révisions des textes non enregistrés), info-bulle (`schematron.tip.unsaved`, `schematron.tip.click`), bouton `validation_rules`.
- `schematron_rules_dialog.py` : `SchematronRulesDialog`, `SchematronRulesMixin` (`schematron_rules_dialog`, `_rules_target`, `_declared_phases`, `_declaration_path`), `ClickableLabel` (étiquette Schematron de `editeur_tei`), `relative_href`, `replace_text`.
- `xml_model_edit.py` (sans Qt) : `schematron_declarations`, `set_phase`, `add_declaration`, `remove_declaration`, `declaration_text`.
- `schema_resolution._fetch_remote_rng` : suit `schemaLocation`.
- `resources/schemas/schematron/` : ajouts « edited (Varians, 2020/2025) ».

## V0.9.2.6 — fichiers inclus non enregistrés

Fonctionnement : `RELAXNG_VALIDATION.md` (« V0.9.2.6 »).

- `schematron.py` : `rules_files(path, texts)`, `_with_unsaved_inclusions` (copies temporaires, `xml:base`), `_unsaved_malformed`, `compiled(…, texts=…)`, `check_compilation(text, path, texts)` ; `_rules_trees`, `rules_text`, `_phases` reçoivent `texts`.
- `relaxng_validation.dependency_reference` : suit `sch:extends/@href`.
- `schematron_check.check(text, path, texts)` ; `relaxng_worker` (champ `texts` de `check_schematron`), `validation_worker` (`check_schematron(…, texts)`).
- `validation_panel.py` : `_open_unsaved_texts`, `_unsaved_rules_texts`, `_source_tip_name` (`schematron.tip.unsaved_included`), `_validation_outdated` (fichier Schematron).
- `schematron_check_ui.py` : `_schematron_inclusions` (textes et jeton de la vérification).
- `schematron_rules_dialog._declared_phases` : phases des fichiers inclus non enregistrés.
- `code_editor.CodeEditor.set_text_document` : défilement remis en haut avant `setDocument` (correction : la position d'un long document défilé, appliquée un instant à un document court, faisait osciller les barres de défilement sans fin).

## V0.9.2.7 — DOCX, ODT, EPUB, HTML en plusieurs fichiers, édition critique

Fonctionnement : `XSLT_SCENARIOS.md` (« V0.9.2.7 »).

- `project_config.TransformScenario` : `package`, `prepare` ; `project_management.transformations_element` les écrit.
- `xslt_scenarios.py` : `PIVOT`, `substitute` (`${pivot}`, `${tei}/`), `TEI_SCENARIOS` (8), scénario `edition-critique`, problèmes `package_invalid` et `prepare_invalid`, requête (`package`, `package_template`, `package_fixstyle`, `prepare`), `included_stylesheets`, `_html_output` (EPUB 3).
- `xslt_packages.py` (sans Qt, nouveau) : `PACKAGES`, `FOLDER_PARAMS`, `DEFAULT_PARAMS`, `prepare`, `copy_images`, `image_size`, `finish`, `PackageError`.
- `xslt_engines._run_saxon` : paramètres sans type, dossier de travail, pré-passage, deux passes selon le format ; journal `image_skipped`.
- `transform_ui.py` : sous-groupe `tei_group` (clé `(groupe, rang)` en `UserRole`, `item_for`), sous-menu TEI du bouton Transformer, champs « Format du résultat » et « Pré-passage » de la boîte d'un scénario, copie des feuilles incluses.
- `rendering/apparat-commun.xsl`, `rendering/apparat-en-notes.xsl`, `rendering/edition-critique.xsl` (nouveaux).
- `xslt_scenarios.witness_choices`, `WITNESS_PARAM`, `NO_WITNESS` ; `transform_ui.ScenarioDialog._update_value_widget` : liste du paramètre `temoin-de-base`.

## V0.9.2.8 — menus Éditer et Rechercher, chercher et remplacer

Fonctionnement : aide, section « Rechercher et remplacer » (`search-replace`).

- `text_search.py` (sans Qt, nouveau) : `SearchOptions`, `find_spans` (littérale avec chevauchements, ou expression régulière `MULTILINE` sans correspondance vide), `match_at`, `replacements`, `replacement_for`, `SearchError` (`pattern_invalid`, `template_invalid`), `Utf16Positions` (positions Python ↔ Qt).
- `code_editor.py` : `find_in_plain_editor(…, options, exact)`, `replace_in_plain_editor`, `replace_all_in_plain_editor`, `_replace_spans` (une étape d'annulation, sous `_pair_edit_guard` : pas d'automatisme de paires).
- `main_menus.py` : `_build_edit_menu` (commandes sur le champ qui a le focus, `_edit_target`, `_update_edit_actions`, raccourcis en `WidgetShortcut`), `_build_search_menu` (`action_replace` Ctrl+H, options cochables `action_search_case` / `action_search_regex`, `search_options`, réglages `search/caseSensitive` et `search/regex`) ; libellés courts de la barre d'outils en `iconText`.
- `replace_bar.py` (nouveau) : `ReplaceBarMixin` (barre sous l'éditeur XML, `show_replace`, `replace_source_next`, `replace_source_all`), `search_error_text`.
- `formatted_view.py` : boutons des options dans la barre de recherche du fragment (`add_fragment_find_options`), ligne « Remplacer par » (`fragment_replace_row`, `show_fragment_find(replace=True)`, `replace_fragment_next`, `replace_fragment_all`).
- `editeur_tei._find_source(backwards, field)` : options, champ de la barre de remplacement, expression incorrecte.
- `main_menus._build_edit_menu` : « Indenter le XML » et « Références » (`action_check_references`) à la fin du menu Éditer, plus dans la barre d'outils.
- `help_search.py` (sans Qt, nouveau) : `fold` (sans accents, casse ni signes typographiques, avec les positions d'origine), `query_terms` (mots, expressions entre guillemets), `search` (sections qui contiennent tous les termes, occurrences, extrait), `Section`, `Hit`.
- `help_dialogs.SoftwareHelpDialog` : champ de recherche (Ctrl+F), liste des sections (`results`), occurrences surlignées (`occurrences`, `current`, ◀ ▶, F3) ; sections tirées des titres du `QTextDocument`, sommaire écarté (`_links_only`).
- `text_search.kwic` / `Kwic` : chaque occurrence avec sa ligne et ses contextes avant et après, sur une ligne (blancs réduits à une espace).
- `search_results.py` (nouveau) : `SearchResultsMixin`, panneau du bas « Tout lister » (`action_search_list` Ctrl+Maj+L, `list_search_results`, `refresh_search_results`, case `search_results_project`, `goto_search_result`, au plus `MAX_RESULTS` lignes) ; suivi par `search_results_follow` (`_find_source`), `search_results_document_changed` (`_attach_document`), les options et le texte (minuterie de 400 ms).
- `document_tabs.py` : rangée `document_tab_row` (barre et flèche `document_tabs_button`), `DocumentTabBar.layoutChanged`, `_update_document_tabs_button` (flèche visible quand la somme des `tabSizeHint` dépasse la rangée), `_fill_document_tabs_menu`.

## V0.9.2.8.1 — feuilleter un manuscrit, débugger l'apparat, Ctrl+E

Fonctionnement : aide, sections « Suivre un manuscrit dans son propre ordre » (`lead-witness`), « Débugger l'apparat » (`app-without-lem`) et la description de Ctrl+E.

- `manuscript_panel.ManuscriptPanel` : bouton à bascule `lead_btn` (icône `resources/icons/feuilleter.svg`, `LEAD_ICON` ; enfoncé, style discret `_LEAD_BUTTON_QSS`), après ← → ⤺ ; `leads_edition`, `set_leads_edition`, signal `leadsEditionChanged` ; relâché, `navigate` ne fait que `browse` et le choix du folio n'émet pas `witnessNavigate`.
- `witness_workspace` : `_load_leading_witnesses`, `_witness_lead_changed` (réglage local `projectView/…/witnessLeadsEdition`, état de chaque témoin) ; `editeur_tei` applique l'état à la création des panneaux, par défaut enfoncé pour le pivot seul. Les tests du parcours des témoins (`test_gui_witness_route.py`, `test_gui_witness_pages_route.py`) enfoncent le bouton de tous les panneaux.
- `apparatus_xpath.app_without_lem_xpath` ; `apparatus_ui.ApparatusDebugDialog.no_lem_radio`, troisième choix, disponible sans `<listWit>`.
- `completion_ui.CompletionDialog` (mode `allow_custom`, Ctrl+E) : pas de présélection ; `eventFilter` (Tab, ↓ : première entrée) ; `_accept_current` insère l'entrée sélectionnée, sinon le texte saisi. Ctrl+Espace (présélection de la première entrée) ne change pas.

## V0.9.2.8.2 — sigles des témoins, crayon et F2, projet de test

Fonctionnement : aide, « Sigle et identifiant d'un témoin » (`witness-siglum`, fin de la section Projets), paragraphe « Sélections partagées avec l'éditeur de fragment » (`fragment-selection`), raccourci F2.

- `witness_ids.py` (nouveau, sans Qt) : `is_xml_id` (NCName, XML 1.0 5e éd.), `witness_id_for_siglum` (caractère interdit → « _ », « _ » devant un sigle qui ne commence pas par une lettre).
- `WitnessConfig.siglum`, `WitnessDraft.siglum` (vides si le sigle est l'identifiant), `display_siglum` ; attribut facultatif `siglum` de `<witness>` dans `project.xml` ; `<idno type="siglum">` dans le `<listWit>` de `minimal_tei_text`.
- `project_dialogs.WitnessEditDialog` : `witness_id()` (identifiant d'origine tant que le sigle n'a pas changé), `xml_id_hint` ; `WitnessTable` : sigle en colonne 0, identifiant et sigle en données (`UserRole + 1`, `UserRole + 2`), `_identity_conflict`.
- Affichage : `MainWindow.witness_sigla`, `witness_siglum()` (barre d'état, structure, diagnostic, témoin détaché, menus, `transform_ui`, `apparatus_ui` avec `sigla`) ; `WitnessDiagnostic.siglum`.
- Sorties : `f:sigle` dans `rendering/apparat-commun.xsl` (Édition critique, apparat en notes), modèle `sigles` dans `rendering/tei-to-html.xsl` ; `legacy_v11_core.extract_witness_labels` laisse l'`<idno>` de côté ; viewer : `siglum` dans les données d'un témoin s'il diffère, `siglumOf` dans les messages. `diagnostic_rows` accepte le sigle dans `meta.witness` et `meta.base_witness`.
- `formatted_view` : `ClickablePreview.mousePressEvent` retient la sélection au clic sur le crayon (`take_selection_before_pencil`) ; `edit_paragraph_action` (F2, `WidgetShortcut` sur l'aperçu), `edit_selected_paragraph`, `_edit_paragraph` (ne recharge pas un fragment modifié).
- `tei_listwit.py` (nouveau, sans Qt) : `add_witnesses_to_listwit` (insertion textuelle à la fin de la première `<listWit>` de l'en-tête, style et préfixe conservés ; compte rendu `ListWitReport` : `added`, `declared`, `id_used`, `no_listwit`, `malformed`), `add_witnesses_to_listwit_file` (octets, `.bak`) ; appelé par `project_settings_dialog` pour les témoins nouveaux, messages `project.listwit.*`.
- `tei_facsimile.valid_xml_id` = `witness_ids.is_xml_id` (NCName, toutes écritures) ; `safe_id_component` garde les caractères permis (« Σ-p0001 ») ; `apparatus_xpath._cites` suit la même règle.
- Projet de test dans `tests/data/exemple` (`corpus_data.copy_example`) ; `.gitattributes` : `/tests export-ignore` ; `MainWindow(project_path)` sans projet par défaut ; `web_viewer.generator.main([])` rend 2.

## V0.9.2.9 — éléments modifiables comme fragment

Fonctionnement : aide, paragraphe « Éléments modifiables » (`fragment-units`, après `fragment-selection`).

- `fragment_units.py` (nouveau, sans Qt) : la règle (élément de `model.divPart`, de `model.inter`, `<head>`, `<figure>`, `<note>`, du `<body>` ou de tout le document s'il n'en a pas, sauf dans un autre élément de l'ensemble) sur le texte (`unit_spans`, balayage des balises hors commentaires, CDATA, instructions de traitement, DOCTYPE) et sur un arbre lxml (`unit_elements`) ; `TEI_UNIT_NAMES` (TEI P5 4.10.2, 57 noms) ; `unit_names_from_schema` (classes et sous-classes développées par `rng_completion._GrammarIndex`, noms des `<element>`, cache par fichier ; None sans ces classes).
- Numérotation : `mark_units` (attribut `vx:edit`, espace de noms `EDIT_NS`, dans le texte donné à la XSLT) ; `mark_unit_elements` (arbre de l'édition assemblée, `preview_sources`).
- Crayons : `edit_stylesheet` (feuille enveloppe, `xsl:import` de la feuille de la vue, modèle `*[@vx:edit]` : crayon devant ce qu'elle produit, rien si elle ne produit rien), `edit_stylesheet_url` (base distincte : une feuille ne peut s'importer elle-même), `place_edit_markers` (crayon au début du premier bloc qui suit, infobulle) ; `formatted_view.transform_with_xslt(..., edit_markers=True)` (cache distinct, secours PowerShell compris).
- `document_tabs.fragment_unit_names` (schéma de `last_schema_resolution` de l'édition, sinon `TEI_UNIT_NAMES`), `_preview_unit_names` (noms de la dernière actualisation, `FormattedEditionWidget.unit_names`, aussi dans la clé du cache de l'aperçu) ; `preview_sources(..., names)` (éléments retrouvés dans leur fichier parmi tous les éléments des mêmes noms : `_element_spans`).
- `formatted_view` : `unit_spans` remplace `paragraph_spans` (fragment, F2, application) ; `editeur_tei._source_selection_descriptor` / `_select_xml_text_in_paragraph` aussi ; étiquette du fragment en texte brut avec le nom de l'élément (`{element}`).
- `rendering/tei-to-html.xsl` : `lg`, `l`, `head`, `list`/`item`, `figure`/`figDesc` ; styles dans `rendering/tei.css`.
- Listes, `tei-to-html.xsl` et `edition-critique.xsl` : numérotées si `@rend` contient `numbered` ou si `@type` vaut `ordered` ou `numbered` ; le `<head>` d'une liste avant elle.
- `tei-to-html.xsl` : division titrée par son premier `<head>`, sinon `@n` (jamais `@xml:id`) ; sommaire par niveaux (mode `toc`, libellé `toc-label` sans notes ni leçons), ancre `@xml:id` ou `generate-id()` ; en-tête réduit au titre ; `lang` d'après `@xml:lang`.

## V0.9.3.0 — texte de lecture du viewer web

Fonctionnement : aide, paragraphe « Texte de lecture » (`viewer-text`, à la fin de la section Viewer web).

- `web_viewer/legacy_v11_core.py` : `reading_texts` (tous les `<text>` les plus externes, ceux d'un `<teiCorpus>` compris ; à défaut le premier `<body>`), lus par les deux extracteurs. `extract_reading_document` : bloc `div` (attributs `id` : `@xml:id` ou identifiant produit libre ; `level` ; `part` : `front`/`back` ; `label` : texte du premier `<head>`, sinon `@n` ; `title` : `@n` sans `<head>`), remplace le bloc `sermon`. Blocs rendus `RENDERED_BLOCKS` : `head` (`div_title`, `table`), `p` (`<p>`, `<ab>`, contenu de phrase entre deux blocs : `PHRASE_TAGS`, `_phrase_only`), `l` (`n`, `group`), `item` (`list`, `numbered` : `list_is_numbered`, `depth`, `label`, `cont`), `cell` (`table`, `row`, `label`, `cols`, `rows` : `_span`), `caption` (`<figDesc>`), `note` (note entre deux blocs). `SPLIT_TAGS` : une liste, un tableau, une figure ou une strophe sortent d'un paragraphe ou d'une entrée (suite marquée `cont`). Conteneurs « collants » (strophe, liste, tableau, figure) : un `<pb/>` ou une lacune entre deux blocs reste dans le précédent ; `ensure_block` n'écrit jamais dans un bloc déjà suivi d'autres. Un `<lb/>` entre deux blocs est lu. `<app>` dont la leçon contient des blocs : `walk_structural_app`.
- Phénomènes éditoriaux : `choose_choice_form` (`CHOICE_ORDER`), autres formes dans `alt` du segment ; styles `del` (`<del>`, `<surplus>`), `add`, `supplied` (crochets), `gap` (« […] », `alt` = raison · étendue), `sup`, `sub`, `underline` ; `<space>` ; `app_readings`, `choose_reading`, `describe_readings` (`<rdgGrp>` compris), communs aux deux extracteurs ; `document.lang`.
- Positions : `VariansSync.RENDERED` (`sync_model.js`), `VariansFullText.RENDERED` (`fulltext_search.js`), `segment_views.RENDERED_BLOCKS` : mêmes blocs, mêmes positions que `renderDocument`.
- `web_viewer/generator.py` : `renderDocument` (`renderLines`, `renderList`, `renderTable`, `renderToc`, `partTitle`), `styles` (`STYLE_CLASSES`), `altTitle` (`FORM_KEYS`, `viewer.form.detail`), CSS (`div-start`, `div-title`, `tei-head`, `tei-lg`, `verse-n`, `tei-list`, `tei-table`, `tei-caption`, `tei-note-block`…), `lang` du texte ; messages `viewer.part.*`, `viewer.form.*` (×7).
- Retiré de `legacy_v11_core.py` : configuration du corpus de Troyes, alignement HTR/ALTO, manifestes, témoins secondaires, `build_dataset_fast`, ancien `make_html`, `main`.
- `tei-to-html.xsl`, phénomènes éditoriaux comme « Édition critique » : `choice` (modèle `nom-de-forme`), `sic`, `del`/`surplus` (`.rature`), `add` (`.ajout`), `supplied` (`.restitution`), `gap` (`.lacune`), `space` ; `hi` par couches d'éléments HTML (modèle `hi-couches`, `.petites-capitales`) ; `emph`, `title`, `foreign` en `<i>`.
- Références des citations : `tei-to-html.xsl` (`cit` rend tout son contenu, `cit/ref` en `span.ref` entre chevrons) ; `edition-critique.xsl` (`f:biblique`, `f:ref-en-note` : référence d'une `<cit>` non biblique dans `f:appels-de-section`, série des notes) ; `legacy_v11_core.cit_is_biblical`, `reference_notes` (repère de note, annotation de type `ref`).
- Aperçu : `formatted_view.PREVIEW_BASE_CSS` porte aussi les règles du crayon ✎, des repères de ligne et de `.ref` ; report d'une sélection de la source par la structure en dernier recours (`xml_selection_structure`, `ClickablePreview.select_structure`, `MainWindow._source_selection_structure`).
- Strophes de `tei-to-html.xsl` : un `<lg>` est un seul bloc, ses `<l>` des `<span class="l">` séparés par `<br/>` (Qt ne regroupe pas des blocs imbriqués) ; `tei.css` : `.lg br` masqué et `.l` en bloc dans un navigateur ; `formatted_view.PREVIEW_BASE_CSS`, placée avant la CSS du projet (Qt ignore toute règle après un `@media`).
- Feuilles : tableaux dans `tei-to-html.xsl` (`table`, `row`, `cell`, modèle `cell-span`) et `edition-critique.xsl` (légende, `th`, `colspan`, `rowspan`) ; `fragment_units._DIVE_RE` accepte `caption`.
- Apparat : texte de l'éditeur en italique, `edition-critique.xsl` (`i.editeur` : om., add., lacunes, leçon non disponible) et `apparat-en-notes.xsl` (`hi rend="italic"`, commentaires compris). Leçons en romain : paramètre tunnel `dans-apparat` (`sic`, `quote`, `hi`/`emph`, `title`/`foreign`) ; `apparat-en-notes.xsl`, mode `note` (`hi` italique sans son élément, `sic` suivi de « sic »).
- Libellé d'un témoin sans son sigle : `edition-critique.xsl` (« Sigles des témoins » : `$marques`, `<idno type="siglum">` et tout élément qui ne contient que le sigle ou l'identifiant) ; `legacy_v11_core.extract_witness_labels`, même règle.
- Aller-retour Source → XSLT / CSS → Source : `MainWindow._preview_round_trip` (document, révision, sélections de la source et de l'aperçu), `_select_source_span`.
- Choix du texte du viewer : `legacy_v11_core.choose_reading_status` (modes `established` / `witness`, `reading_witnesses` : @wit d'un `<rdgGrp>`), `extract_reading_document(text_mode, text_witness)` ; témoin sans leçon : segment `missing` (texte de repli, ou repère « ∅ »), annotation `missing`, `missing_readings` ; lignes du pivot d'une leçon non affichée : `pivot_marks_in`, `spread_lines` (réparties dans le texte affiché), segment `line-anchor` si le témoin omet le passage (`sync_model.js`, `segment_views`). `generator.build_dataset(text_mode, text_witness)` → `meta.text` ; JS `textChoice`, `missingTitle`, classes `no-reading`, `no-reading-empty`. Réglage : `ProjectConfig.web_text_mode`, `web_text_witness` (`<webViewer text textWitness>`), `project_management.update_project_web_text`. Boîte : `web_text_dialog.WebTextDialog`, `MainWindow._ask_web_text`.

## V0.9.3.3 — red team : intégrité et sécurité

Compte rendu : `docs/RED_TEAM.md` (identifiants A1–A8, B1–B5, C1–C3, D1–D3).

- Texte exact (A1, A2) : `code_editor.raw_text` (`toRawText`, U+2029 → `\n`), `TextDocument` (document de l'éditeur, de l'édition et des sessions), `CodeEditor.toPlainText` et `positions()` ; `text_positions(document, text)` (raccourci quand `characterCount() == len(text) + 1`), `python_change` (changement Qt → indices Python, passé à `CodeEditor.text_change_listener`). Conversions Python ↔ Qt (`text_search.Utf16Positions.qt` / `.python`) dans le formatage, Ctrl+E, la complétion, le repliage, les paires de balises, la recherche, la synchronisation des témoins (`witness_sync`), les références, la validation et la boîte des règles Schematron.
- Fichiers (A3–A8) : `save_io.atomic_write_text_with_backup` (droits gardés, `ReadOnlyFileError`, CRLF gardé, `fsync`), `save_io.XmlFile` (prologue, épilogue, écriture atomique de `project.xml`), `declared_encoding`, `is_utf8` ; `document_session.file_stamp`, `DocumentSession.disk_stamp` (posée par `mark_loaded` et `mark_saved`) ; `document_io._confirm_external_change` (Écraser / Recharger / Annuler) et `_confirm_utf8_declaration`, appelées en tête de `_write_to`.
- Saxon (B3–B5) : `xslt_engines._serialized_results` (`fn:transform`, `delivery-format: serialized`), `_refuse_result_documents`, `saxon_without_network` (`allowedProtocols=file`, collant pour tout le processus : seulement dans les processus `transform_worker` et `relaxng_worker`), `CHECKS_LOCAL_ONLY`, `_catalog_rewrites` ; `schematron.LOCAL_ONLY` ; `schematron.validate` capture les documents résultats. `relaxng_worker.serve` et `transform_worker.serve` rendent le réglage précédent quand un test les appelle dans son processus.
- Schémas et règles (B1, B2) : `schema_resolution._url_cache_path` (confiné au cache), `trusted_schema_site` (`tei-c.org`), `resolve_schema(may_fetch=…)`, `RemoteSchemaRefused`, `_CheckedRedirects` (redirections, avant la requête), `SchemaResolution.refused_sites`, `rng_refused_site`, `schematron_refused` ; `rules_outside` (hors du projet, du cache, de `resources/` et du schéma du projet). Interface : `validation_panel._schema_site_policy` (une question par site et par résolution ; `ask=False` pour la complétion), `_ask_site`, `_rules_to_confirm`, `_allowed_rules` (sans question ; aussi dans `_validation_token`), `_approved_rules`, `_ask_rules` ; `validate_relaxng_document(ask_rules=True)` pour F8 et l'actualisation du schéma. Réponses mémorisées : `app_context.site_choice` / `remember_site_choice` (`schemas/allowedSites`, `schemas/refusedSites`), `rules_choice` / `remember_rules_choice` (`schematron/allowedRules`, `schematron/refusedRules`).
- Sorties (C1–C3, D2, D3) : `web_viewer/generator.py` (données JSON insérées sans injection, `_IMAGE_SIGNATURES`, `_is_image`, problème `local_image_not_image`), `edition-critique.xsl` (`f:lien`), `manuscript_panel.WitnessHeader` (texte brut), `iiif_manifest._web`.

## V0.9.3.2 — frappe rapide avec des fac-similés

- Chaque frappe déplace le curseur : `sync_timer` (55 ms) lance `sync_panels_to_cursor`, puis `_sync_page_panels_to_cursor`, qui appelle `_refresh_folio_navigation`.
- `_refresh_folio_navigation` ne relit les folios d'un panneau que si sa clé change : `(facsimile_markup(texte), surfaces du panneau, libellés)`. Le `<facsimile>` est analysé une fois pour tous les témoins (`facsimile_surfaces`) : seul, sinon le document entier (préfixe déclaré plus haut) ; un `<facsimile>` mal formé donne None, les folios reviennent aux surfaces, et la clé n'est pas gardée. `set_folios` seulement si la liste change, ou avec `force`.
- `image_sources.surface_labels(panel, racine)` : libellés gardés sur le panneau (`_surface_labels`) tant que `panel.items` est la même liste ; un rechargement des pages remplace la liste.
- `folio_navigation.folio_marks` : pb du texte lus une fois (`_pb_tags` : fin, pointeurs de @facs et de @edRef, @n normalisé, hors commentaires, CDATA et instructions), puis pb de chaque témoin (`_scan_folio_marks`, `_folio_of_pb`), gardés pour les derniers textes (`_TextMemo`, quatre textes). `pb_folio` garde sa signature.

## V0.9.3.1 — théâtre, leçons hors `<lem>`, guide TEI, aide

Fonctionnement : aide, chapitres « Vue XSLT / CSS » (`preview-rendering`), « Viewer web » (`viewer-text`, `viewer-text-choice`), « Publier avec XSLT » (`critical-edition`), « Référence » (`menus`).

- Répliques : `legacy_v11_core.walk_speech` (rang `attrs.sp` des blocs d'une réplique, `state["sps"]`), blocs `speaker` et `stage` dans `RENDERED_BLOCKS` (`sync_model.js`, `fulltext_search.js` aussi) ; `generator.renderDocument` enveloppe une réplique (`.tei-sp`), classes `.tei-speaker`, `.tei-stage`, `.tei-stage-inline` (`STYLE_CLASSES.stage`). `tei-to-html.xsl` : `div.sp`, `div.speaker`, `span.stage` / `div.stage` ; `tei.css`, `formatted_view.PREVIEW_BASE_CSS`. `edition-critique.xsl` : `div.didascalie`.
- Parenthèses d'une didascalie : `open_parenthesis` et `close_parenthesis` (`state["hug"]` : pas de blanc après « ( », ni avant « ) ») ; `apparat-commun.f:texte-net` ôte les blancs au bord du premier et du dernier texte d'un `<stage>` ; `tei-to-html.xsl`, modèle `text()` (`afterBreakNo`, `beforeBreakNo`).
- Leçons hors `<lem>` : `walk_shown` (texte établi, leçon retenue qui n'est pas un `<lem>` : `state["nonlem"]`, segments `nonlem`, `nonlem_readings`) ; `unflag_edges` détache les blancs au bord de la leçon. `generator.build_dataset(highlight_nonlem)` → `meta.text.nonlem`, `meta.text.highlight` ; case `showNonLem` (`applyMarkerVisibility`, `updateMarkerToggleAvailability`, classe `show-nonlem` du `<body>`, `.non-lem`). Réglage `ProjectConfig.web_highlight_nonlem` (`<webViewer highlightNonLem="true">`), `update_project_web_text(highlight_nonlem)` ; `WebTextDialog.highlight_box`, `highlight()` ; `MainWindow._ask_web_text` rend `(mode, témoin, surlignage)`.
- `edition-critique.xsl` : paramètre `surligner-hors-lemme`, variable `$hors-lemme`, modèle `text()[ancestor::tei:rdg[ancestor::tei:app]]` (mode `base`, `span.hors-lemme`), case `#surligner` (`p.surlignage`, script), classe `surligner` du `<body>`. Boîte d'un scénario : `xslt_scenarios.BOOLEAN_PARAMS`, `transform_ui._widget_value`, `ScenarioDialog._update_value_widget` (case à cocher).
- Textes des feuilles livrées : les catalogues `i18n/<langue>.xml` sont leur seule source (clés `publication.*`, et `viewer.form.*` pour les formes d'un `<choice>`). `xslt_scenarios.scenario_request(language=…)` ajoute les paramètres `langue` et `catalogues` sauf si le scénario les fixe (comme `css`) ; `${langue}` se remplace dans une valeur (`substitute`) ; `catalogs_uri(language)` rend l'URI du dossier `i18n/` terminée par « / », ou « » si la langue n'a pas de catalogue (lxml refuse un fichier absent). `transform_ui` passe `current_i18n().language` ; `formatted_view.publication_params()` fait de même pour l'aperçu. XSLT 3 (`apparat-commun.xsl`) : `f:libelle($cle)` et `f:libelle($cle, map)` (`{nom}` remplacé), catalogue lu par `doc-available`/`doc`, repli `f:textes-fr` ; `$f:langue` vaut `fr` sans catalogue ; `xsl:message` passe par `f:libelle`. XSLT 1.0 (`tei-to-html.xsl`) : modèles `texte`, `texte-fr`, `texte-avec`, `detail` ; `document()` n'est appelé que si `$catalogues` n'est pas vide (le repli .NET l'interdit). `test_publication_texts.py` vérifie que chaque clé citée par les feuilles existe dans les sept catalogues et que les replis français égalent `fr.xml`. Boîte d'un scénario : `ScenarioDialog._update_value_widget` (genre `LANGUAGE_PARAM` → `_language_combo` : « Langue de l'interface » = `${langue}`, puis `available_languages()`).
- Listes de complétion à la frappe (`CodeEditor` : pointeurs après « # », noms d'attributs, fermeture) : Entrée et Tab passent par `CodeEditor._chosen_completion`, qui lit l'entrée surlignée du popup (`popup().currentIndex()`, rôle `completionRole()`), et non `currentCompletion()` (ligne courante du compléteur, restée à 0) ; `test_gui_value_popup.py`. Boîte de Ctrl+Espace et de Ctrl+E (`completion_ui.CompletionDialog`) : `eventFilter` du champ, posé dans les deux modes ; ↓ passe à la liste et sélectionne la première entrée si aucune ne l'est, sinon la suivante ; Tab passe à la liste (`test_gui_ctrl_e_choice.py`).
- Menu Aide : `main_menus.TEI_GUIDE_URL`, `action_tei_guide` (entre deux séparateurs) ; même entrée dans le menu sans projet (`editeur_tei.py`) ; clé `help.tei_guide` (×7).
- Aide : `help/<langue>.html`, mêmes ancres dans les sept langues, sections non emboîtées (`help_search` découpe par titres), aucun numéro de version.
