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
