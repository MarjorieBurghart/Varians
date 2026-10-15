# 11 — Inventaire vérifié du code et des tests

Généré par analyse syntaxique AST des fichiers Python **réels** de la V0.8.5.26.2 ; cet index est un instrument de navigation, pas une documentation d’API stable.

- **110 modules Python** analysés (sources et tests inclus).
- **35 fichiers Python hors tests**.
- **75 fichiers Python sous tests/**.

## Sources et modules web

| Fichier | Lignes | Classes définies | Fonctions de niveau module | Méthodes de classe |
|---|---:|---:|---:|---:|
| `alto_import.py` | 523 | 1 | 22 | 0 |
| `custom_completion.py` | 211 | 4 | 4 | 8 |
| `editeur_tei.py` | 7855 | 23 | 39 | 314 |
| `folio_navigation.py` | 349 | 1 | 8 | 0 |
| `i18n.py` | 104 | 2 | 1 | 6 |
| `iiif_download_manager.py` | 268 | 2 | 0 | 17 |
| `iiif_local.py` | 262 | 0 | 13 | 0 |
| `iiif_manifest.py` | 192 | 1 | 11 | 0 |
| `iiif_page_selection.py` | 209 | 0 | 7 | 0 |
| `iiif_resolution.py` | 442 | 1 | 9 | 0 |
| `iiif_selection.py` | 99 | 0 | 6 | 0 |
| `image_sources.py` | 685 | 1 | 23 | 1 |
| `project_config.py` | 366 | 4 | 5 | 4 |
| `project_dialogs.py` | 1336 | 6 | 1 | 55 |
| `project_management.py` | 699 | 4 | 12 | 0 |
| `relaxng_validation.py` | 270 | 3 | 13 | 0 |
| `resource_state.py` | 98 | 1 | 5 | 0 |
| `rng_completion.py` | 1272 | 6 | 25 | 30 |
| `save_io.py` | 59 | 0 | 1 | 0 |
| `schema_resolution.py` | 221 | 2 | 6 | 2 |
| `selection_sync.py` | 46 | 0 | 3 | 0 |
| `tei_facsimile.py` | 574 | 2 | 20 | 0 |
| `tei_formatter.py` | 265 | 3 | 7 | 4 |
| `tei_pivot_scaffold.py` | 378 | 2 | 9 | 1 |
| `web_viewer/__init__.py` | 3 | 0 | 0 | 0 |
| `web_viewer/generator.py` | 521 | 0 | 6 | 0 |
| `web_viewer/legacy_v11_core.py` | 1613 | 0 | 38 | 0 |
| `web_viewer/page_resolver.py` | 142 | 1 | 2 | 2 |
| `web_viewer/tei_line_anchors.py` | 59 | 1 | 2 | 1 |
| `witness_layout.py` | 42 | 0 | 3 | 0 |
| `witness_resource_refresh.py` | 255 | 2 | 8 | 0 |
| `workspace_layout.py` | 26 | 0 | 3 | 0 |
| `xml_folding.py` | 89 | 1 | 4 | 0 |
| `xml_tag_pairs.py` | 588 | 4 | 20 | 4 |
| `xpath_search.py` | 300 | 4 | 9 | 0 |

## Symboles de production (classes et fonctions de module)

### `alto_import.py`
Classes : `AltoParsedFile` (L203)
Fonctions : `_local` (L20), `_num` (L24), `_safe_id` (L34), `_norm` (L40), `_first_text` (L46), `_line_text` (L53), `_polygon_bbox` (L72), `_points` (L92), `_bbox_from_points` (L105), `_child` (L115), `parse_page_file` (L119), `parse_layout_file` (L189), `parse_alto_file` (L209), `build_alto_cache` (L273), `_page_keys` (L289), `_line_uuid` (L313), `_merge_lines` (L323), `overlay_alto` (L396), `source_signature` (L472), `cache_path` (L481), `load_or_build_cache` (L486), `apply_witness_alto_policy` (L512)

### `custom_completion.py`
Classes : `DynamicValues` (L48), `CustomAttributeSpec` (L55), `CustomElementSpec` (L72), `CustomCompletionConfig` (L81)
Fonctions : `_local_qname` (L39), `_name_matches` (L43), `load_custom_completion` (L133), `merge_suggestion_sources` (L190)

### `editeur_tei.py`
Classes : `XMLHighlighter` (L324), `LineNumberArea` (L347), `CodeEditor` (L361), `XmlHealthSignals` (L1123), `XmlHealthWorker` (L1128), `FetchSignals` (L1164), `FetchWorker` (L1169), `ImageSceneView` (L1265), `SplitImagePreview` (L1365), `SplitPreviewLoader` (L1458), `WitnessHeader` (L1519), `ManuscriptPanel` (L1543), `ClickablePreview` (L2198), `FormattedEditionWidget` (L2522), `CompletionDialog` (L3431), `CtrlEConfigDialog` (L3521), `SoftwareHelpDialog` (L3583), `AboutDialog` (L3739), `DetachedWitnessWindow` (L3759), `WitnessVisibilityDialog` (L3818), `WitnessDiagnosticDialog` (L3913), `MainWindow` (L3989), `WelcomeWindow` (L7575)
Fonctions : `_install_light_selection_palette` (L143), `_t` (L152), `_settings` (L162), `recent_project_paths` (L166), `remember_recent_project` (L181), `remove_recent_project` (L187), `clear_recent_projects` (L191), `last_open_project_path` (L195), `remember_open_project` (L216), `forget_open_project` (L220), `load_json` (L224), `flatten_primary` (L229), `flatten_secondary` (L241), `scaled_bbox` (L254), `scaled_polygon` (L289), `crop_for_items` (L302), `iiif_image_request` (L319), `find_in_plain_editor` (L922), `find_in_rich_editor` (L979), `_selection_xml_to_visible_text` (L1058), `_rich_selection_pattern` (L1078), `_xml_selection_pattern` (L1096), `_iiif_split_preview_request` (L1476), `load_split_thumbnail` (L1491), `paragraph_spans` (L2107), `resolve_css_variables` (L2118), `inject_edit_markers` (L2130), `make_line_segments_clickable` (L2163), `lxml_available` (L2445), `transform_with_xslt` (L2453), `_selected_text_for_dictionary` (L3609), `_open_external` (L3646), `_open_latin_dictionary` (L3650), `_show_software_help` (L3656), `_varians_font` (L3660), `_scaled_logo_label` (L3672), `_build_varians_card` (L3684), `_show_about` (L3755), `main` (L7819)

### `folio_navigation.py`
Classes : `Folio` (L20)
Fonctions : `_local` (L27), `folios_for_witness` (L31), `folio_at_position` (L83), `split_surface_into_folios` (L135), `scene_rect_for_folio` (L194), `markable_part_for_line` (L208), `inspect_surface_part_split` (L249), `configure_surface_parts` (L290)

### `i18n.py`
Classes : `LanguageInfo` (L22), `I18nManager` (L28)
Fonctions : `load_i18n` (L102)

### `iiif_download_manager.py`
Classes : `DownloadThread` (L18), `IIIFDownloadManager` (L52)

### `iiif_local.py`
Fonctions : `_safe_id` (L23), `store_dir` (L27), `index_path` (L31), `remote_key` (L35), `_request_url` (L41), `_read_index` (L51), `_valid_entry` (L61), `local_image_path` (L82), `apply_working_copy` (L86), `_image_extension` (L110), `_fetch_image` (L124), `plan_witness_copy` (L157), `download_witness_copy` (L204)

### `iiif_manifest.py`
Classes : `IIIFManifest` (L13)
Fonctions : `_text_label` (L21), `_service_info` (L37), `_service_limits` (L52), `_first_v3_image` (L68), `parse_manifest` (L83), `fetch_manifest` (L134), `cache_path` (L146), `write_cache` (L151), `read_cache` (L157), `import_manifest` (L166), `overlay_manifest` (L176)

### `iiif_page_selection.py`
Fonctions : `canvas_key` (L13), `natural_key` (L18), `exact_image_stem` (L29), `propose_exact_ocr_links` (L52), `selected_manifest_pages` (L120), `_canonical_path` (L135), `selected_page_overlay` (L139)

### `iiif_resolution.py`
Classes : `Resolution` (L19)
Fonctions : `_uri` (L26), `_iiif_image_identity` (L39), `_service_of_image_url` (L61), `_label` (L66), `_page_meta` (L72), `resolve_pages` (L79), `_merge_detached_ocr_pages` (L195), `_layout_only_manifest_pages` (L264), `overlay_resolved_manifest` (L374)

### `iiif_selection.py`
Fonctions : `_stem` (L18), `_norm` (L27), `_folio` (L34), `_page_names` (L44), `_ocr_names` (L50), `select_ocr_pages` (L56)

### `image_sources.py`
Classes : `PageImageSource` (L23)
Fonctions : `_as_int` (L43), `_resolve_file` (L50), `page_image_source` (L62), `page_label` (L114), `page_image_dimensions` (L119), `image_scene_reference_crop` (L127), `_gallica_highres_url` (L150), `page_image_request` (L159), `full_page_target` (L254), `normalized_image_block` (L267), `_local_entries` (L303), `_match_key` (L328), `_associate_local_entries` (L338), `apply_witness_image_policy` (L370), `page_navigation_items` (L495), `_same_physical_page` (L514), `_adjacent_line_continuity` (L528), `effective_line_bbox` (L574), `valid_matched_indices` (L602), `matched_line_center` (L617), `visible_line_frame_indices` (L634), `display_window_indices` (L640), `image_only_items` (L669)

### `project_config.py`
Classes : `LocalImageConfig` (L16), `AltoFileConfig` (L24), `WitnessConfig` (L29), `ProjectConfig` (L76)
Fonctions : `has_line_synchronization` (L57), `_resolve` (L110), `_parse_schema` (L115), `load_project` (L152), `update_project_language` (L349)

### `project_dialogs.py`
Classes : `PathRow` (L22), `IIIFCanvasPicker` (L48), `WitnessEditDialog` (L308), `WitnessTable` (L846), `NewProjectDialog` (L1078), `ProjectSettingsDialog` (L1200)
Fonctions : `run_pivot_scaffold_dialog` (L1036)

### `project_management.py`
Classes : `LocalImageDraft` (L20), `AltoFileDraft` (L28), `WitnessDraft` (L33), `ProjectDraft` (L69)
Fonctions : `minimal_tei_text` (L95), `write_minimal_tei` (L154), `portable_path` (L173), `write_project_xml` (L183), `_safe_filename` (L318), `prepare_alignment_files_for_project` (L330), `prepare_local_images_for_project` (L364), `prepare_alto_files_for_project` (L423), `prepare_iiif_manifests_for_project` (L490), `create_portable_project` (L510), `create_new_transcription_project` (L634), `create_local_xslt_if_needed` (L676)

### `relaxng_validation.py`
Classes : `ValidationIssue` (L25), `ValidationResult` (L35), `_CompiledSchema` (L45)
Fonctions : `lxml_available` (L57), `clear_relaxng_cache` (L61), `relaxng_cache_info` (L79), `relaxng_schema_token` (L88), `_issue_from_log` (L93), `_unique_issues` (L104), `_file_uri_to_path` (L116), `_dependency_path` (L126), `_stat_signature` (L141), `_discover_schema_dependencies` (L152), `_schema_dependency_signature` (L182), `_compiled_relaxng` (L204), `validate_relaxng` (L225)

### `resource_state.py`
Classes : `SynchronizationState` (L67)
Fonctions : `primary_sync_line_count` (L16), `secondary_sync_link_count` (L34), `effective_base_line_sync` (L51), `effective_secondary_line_sync` (L56), `synchronization_state` (L76)

### `rng_completion.py`
Classes : `_Pattern` (L109), `CompletionModel` (L279), `_GrammarIndex` (L416), `XmlCompletionContext` (L797), `_XmlScanCheckpoint` (L1072), `XmlContextCache` (L1078)
Fonctions : `_local` (L47), `_is_rng_node` (L51), `_local_qname` (L56), `_names_match` (L60), `_href_path` (L64), `_explicit_names` (L81), `_token` (L119), `_choice` (L124), `_seq` (L141), `_interleave` (L159), `_star` (L177), `_nullable` (L186), `_all_token_names` (L201), `_first_names` (L212), `_derive` (L233), `_consume` (L269), `load_completion_model` (L788), `adapt_pointer_list_value_context` (L812), `format_pointer_list_insertion` (L889), `_find_tag_end` (L917), `_pop_stack` (L934), `_following_direct_children` (L945), `_attribute_context` (L1013), `_analyze_xml_context_from` (L1143), `analyze_xml_context` (L1262)

### `save_io.py`
Fonctions : `atomic_write_text_with_backup` (L10)

### `schema_resolution.py`
Classes : `XmlModelDeclaration` (L29), `SchemaResolution` (L47)
Fonctions : `detect_xml_models` (L58), `default_schema_cache_dir` (L79), `_url_cache_path` (L88), `_fetch_remote_rng` (L99), `_local_href_path` (L150), `resolve_schema` (L161)

### `selection_sync.py`
Fonctions : `containing_span_index` (L10), `occurrence_index_for_position` (L19), `choose_occurrence` (L31)

### `tei_facsimile.py`
Classes : `FacsimilePage` (L227), `FacsimileSyncReport` (L235)
Fonctions : `valid_xml_id` (L32), `safe_id_component` (L36), `default_surface_id` (L45), `_attr` (L49), `_pointer_tokens` (L55), `facsimile_ref_at_position` (L59), `_xml_escape_attr` (L121), `_set_or_add_attr` (L125), `_markup_spans` (L138), `position_inside_xml_markup` (L190), `upsert_pb_at_position` (L201), `_graphic_url` (L243), `project_facsimile_pages` (L255), `_surface_open_tags` (L321), `_tei_prefix` (L330), `_indent_before` (L335), `sync_facsimile_text` (L341), `sync_facsimile_file` (L493), `previous_surface_labels` (L506), `removable_generated_iiif_surfaces` (L516)

### `tei_formatter.py`
Classes : `_Node` (L34), `FormatReplacement` (L50), `FormatResult` (L57)
Fonctions : `_local_qname` (L29), `_build_tree` (L84), `_xml_space_preserve` (L113), `_custom_formatting` (L118), `_rng_text_state` (L130), `_direct_gaps` (L149), `format_tei_xml` (L161)

### `tei_pivot_scaffold.py`
Classes : `PivotPage` (L26), `PivotScaffoldPlan` (L34)
Fonctions : `_resolve` (L45), `_source_names` (L50), `_unique_name_match` (L60), `_load_sync_pages` (L82), `_synced_line_count` (L99), `build_pivot_plan` (L140), `scaffold_is_empty` (L289), `render_pivot_scaffold` (L305), `write_pivot_scaffold` (L357)

### `web_viewer/__init__.py`
Pas de classe ou fonction définie au niveau module (voir contenu).

### `web_viewer/generator.py`
Fonctions : `build_dataset` (L35), `_safe_web_name` (L422), `package_local_images` (L426), `make_html` (L470), `generate` (L485), `main` (L507)

### `web_viewer/legacy_v11_core.py`
Fonctions : `lname` (L105), `clean_text` (L110), `normalize` (L114), `bigrams` (L122), `similarity` (L129), `wit_tokens` (L139), `witness_matches` (L145), `choose_file` (L149), `choose_output` (L171), `extract_witness_labels` (L184), `flatten_editorial_text` (L195), `notes_inside` (L219), `extract_corrected_pages` (L229), `variant_tooltip` (L430), `extract_htr_pages` (L447), `parse_alto` (L494), `align_monotonic` (L521), `align_htr_to_alto` (L559), `label_to_string` (L592), `parse_manifest` (L607), `folio_tokens` (L678), `normalize_label` (L683), `match_canvas` (L689), `normalize_medieval_piece` (L739), `normalize_medieval` (L748), `witness_matches_loose` (L752), `choose_parallel_reading` (L764), `build_parallel_witness_stream` (L778), `project_positions` (L838), `_archive_xml_entries` (L866), `match_single_folio_canvas` (L887), `build_secondary_alignment` (L904), `extract_reading_document` (L1075), `attach_variant_metadata_to_runs` (L1381), `load_json` (L1393), `build_dataset_fast` (L1398), `make_html` (L1564), `main` (L1575)

### `web_viewer/page_resolver.py`
Classes : `PageResolver` (L27)
Fonctions : `_local` (L18), `_unique` (L22)

### `web_viewer/tei_line_anchors.py`
Classes : `AnchorReport` (L22)
Fonctions : `_local_name` (L17), `build_pivot_lb_index` (L40)

### `witness_layout.py`
Fonctions : `minimum_witness_stack_height` (L10), `normalized_witness_order` (L21), `ordered_visible_witnesses` (L38)

### `witness_resource_refresh.py`
Classes : `RuntimeState` (L82), `WitnessDiagnostic` (L162)
Fonctions : `read_alignment_json` (L24), `flatten_primary` (L44), `flatten_secondary` (L54), `line_keys` (L66), `sync_fingerprint` (L76), `assemble_resources` (L96), `diagnostic_rows` (L178), `changed_witnesses` (L251)

### `workspace_layout.py`
Fonctions : `normalize_workspace_mode` (L7), `workspace_slots` (L11), `normalized_detached_witnesses` (L18)

### `xml_folding.py`
Classes : `FoldRegion` (L17)
Fonctions : `foldable_xml_regions` (L26), `region_at_header` (L71), `region_for_cursor` (L76), `visible_line_numbers` (L82)

### `xml_tag_pairs.py`
Classes : `XmlTagToken` (L23), `XmlTagPair` (L45), `RenameMirror` (L51), `ClosingTagSuggestion` (L486)
Fonctions : `_find_markup_end` (L63), `scan_xml_tags` (L102), `_inside_special_markup` (L149), `_parse_element_tag_at` (L161), `_opening_near_position` (L186), `matching_closing_tag` (L196), `tag_pairs` (L228), `_selection_bounds` (L248), `opening_pair_at_context` (L257), `closing_pair_at_context` (L286), `pair_at_context` (L337), `exact_selected_opening_pair` (L355), `opening_tag_at` (L372), `single_change_span` (L377), `opening_pair_for_name_change` (L400), `closing_rename_mirror_for_change` (L423), `closing_rename_mirror` (L462), `apply_rename_mirror` (L478), `closing_tag_suggestion` (L503), `complete_closing_tag` (L574)

### `xpath_search.py`
Classes : `XPathUnavailable` (L23), `XPathQueryError` (L27), `XPathMatch` (L32), `XPathSearchResult` (L42)
Fonctions : `_local_name` (L51), `_find_tag_end` (L57), `_opening_tags` (L74), `_rewrite_unprefixed_tei_steps` (L110), `_element_range_map` (L141), `_path_position_map` (L158), `_display_path` (L185), `_preview` (L209), `search_xpath` (L217)

## Méthodes majeures de `editeur_tei.py`

**CodeEditor** : `_check_attribute_completion_cursor` (L410), `show_attribute_completion` (L429), `_accept_attribute_completion` (L444), `_check_closing_completion_cursor` (L469), `show_closing_tag_completion` (L477), `_accept_closing_completion` (L503), `_apply_xml_fold_visibility` (L602), `toggle_xml_fold` (L625), `unfold_all_xml` (L650), `fold_all_xml` (L656)

**ManuscriptPanel** : `set_folios` (L1774), `_folio_combo_changed` (L1796), `_request_split_folio` (L1801), `set_folio` (L1813), `_current_folio` (L1835), `_redraw_scene` (L2017)

**MainWindow** : `_build_xpath_panel` (L4387), `show_xpath_panel` (L4457), `hide_xpath_panel` (L4460), `focus_xpath_search` (L4464), `run_xpath_search` (L4473), `goto_xpath_result` (L4527), `show_validation_panel` (L4617), `hide_validation_panel` (L4630), `_auto_refresh_rng` (L4680), `validate_relaxng_manual` (L4695), `validate_relaxng_document` (L4724), `_validate_relaxng_document_impl` (L4738), `_resolve_completion_schema` (L4892), `_completion_model_for_schema` (L4916), `_custom_completion_config` (L4926), `_custom_witness_ids` (L4944), `format_xml_source` (L4956), `show_rng_completion` (L5088), `_apply_rng_completion` (L5218), `_load_witness_display_order` (L5266), `_save_witness_display_order` (L5278), `_apply_witness_panel_order` (L5284), `_restore_workspace_sizes` (L5396), `_restore_main_splitter_ratio` (L5433), `_toggle_detached_witness` (L5449), `_detach_witness` (L5456), `_dock_witness` (L5487), `_save_detached_witness_ids` (L5507), `_restore_detached_witnesses` (L5511), `_dock_all_witnesses` (L5530), `_available_image_witness_ids` (L5544), `_load_visible_witness_ids` (L5547), `_save_visible_witness_ids` (L5566), `_load_witness_size_map` (L5572), `_remember_witness_splitter_sizes` (L5589), `_update_witness_scroll_extent` (L5605), `_restore_witness_splitter_sizes` (L5630), `_apply_witness_visibility` (L5639), `choose_visible_witnesses` (L5681), `_toggle_witness_panel_maximize` (L5696), `generate_web_viewer` (L6112), `open_iiif_download_manager` (L6245), `_xml_occurrences_in_paragraph` (L6509), `_select_xml_text_in_paragraph` (L6548), `_select_xml_text_near_ordinal` (L6580), `_cursor_changed` (L6611), `_text_changed` (L6615), `_apply_xml_health_result` (L6710), `_async_xml_health_finished` (L6775), `_refresh_folio_navigation` (L6789), `_split_double_folio` (L6880), `sync_panels_to_cursor` (L7043), `refresh_local_iiif_cache` (L7087), `_witness_resource_snapshot` (L7130), `show_witness_diagnostics` (L7140), `refresh_witness_synchronizations` (L7144), `goto_xml_from_base` (L7300)

## Méthodes majeures de `web_viewer/generator.py`

Exports haut niveau : `build_dataset`, `make_html`, `generate`, `main` ; vérifier les lignes ci-dessus.


## Tests par version (noms réels)

### 0.8.5.26.2
- `tests/test_v085262_rng_panel_refresh.py` — 184 lignes, 6 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)

### 0.8.5.26.x
- `tests/test_v085261_web_viewer_presentation.py` — 95 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v08526_interim_features.py` — 90 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v08526_web_page_anchor_resolution.py` — 179 lignes, 8 fonctions `test_*` de niveau module

### 0.8.5.25.x
- `tests/test_v085252_text_click.py` — 50 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v085253_pivot_lb_contract.py` — 115 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v08525_i18n_export.py` — 17 lignes, 1 fonctions `test_*` de niveau module
- `tests/test_v08525_iiif_web.py` — 104 lignes, 6 fonctions `test_*` de niveau module

### 0.8.5.24
- `tests/test_v08524_web_geometry.py` — 186 lignes, 9 fonctions `test_*` de niveau module

### Plus anciens et transversaux
- `tests/test_ctrl_e_sans_qt.py` — 236 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_custom_completion.py` — 73 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_recherche_sans_qt.py` — 87 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_recherche_xslt_joiner_sans_qt.py` — 113 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_relaxng_validation.py` — 118 lignes, 0 fonctions `test_*` de niveau module
- `tests/test_rng_completion.py` — 352 lignes, 20 fonctions `test_*` de niveau module
- `tests/test_rng_context_cache.py` — 44 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_save_io.py` — 24 lignes, 1 fonctions `test_*` de niveau module
- `tests/test_selection_onglets_sans_qt.py` — 40 lignes, 0 fonctions `test_*` de niveau module
- `tests/test_spyder_import_isolation.py` — 61 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v057_startup_help.py` — 39 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v058_features.py` — 29 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_v059_features.py` — 36 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_v060_features.py` — 32 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v061_features.py` — 60 lignes, 4 fonctions `test_*` de niveau module
- `tests/test_v063_project_layout.py` — 84 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v064_fragment_wrap.py` — 18 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_v070_image_sources.py` — 119 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v071_new_transcription.py` — 111 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v072_no_image_witness.py` — 91 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v073_local_images.py` — 112 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v074_iiif_manifest.py` — 65 lignes, 4 fonctions `test_*` de niveau module
- `tests/test_v075_alto_import.py` — 121 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v076_optional_sync.py` — 88 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v077_stabilization.py` — 74 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v078_resource_pages.py` — 102 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v079_facsimile_pages.py` — 259 lignes, 19 fonctions `test_*` de niveau module
- `tests/test_v080_xml_tag_pairs.py` — 112 lignes, 12 fonctions `test_*` de niveau module
- `tests/test_v081_tei_formatter.py` — 121 lignes, 10 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v082_page_sync.py` — 94 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_v083_display_navigation.py` — 69 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v0841_xpath_help.py` — 66 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v0842_i18n_handoff.py` — 86 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v084_consolidation.py` — 176 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v08510_frame_visibility.py` — 79 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v08511_mixed_page_line.py` — 201 lignes, 7 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08512_scroll_pivot_name.py` — 120 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_v08513_xml_closing_completion.py` — 105 lignes, 10 fonctions `test_*` de niveau module
- `tests/test_v08514_iiif_alto_independence.py` — 225 lignes, 13 fonctions `test_*` de niveau module
- `tests/test_v08515_iiif_preview_scale_and_sync_diagnostics.py` — 87 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v08516_witness_order.py` — 272 lignes, 12 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08517_diagnostic_refresh.py` — 367 lignes, 16 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08518_folio_navigation.py` — 157 lignes, 20 fonctions `test_*` de niveau module
- `tests/test_v08519_split_dialog.py` — 200 lignes, 8 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v0851_pero_uuid_migration.py` — 62 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v08520_double_page_parts.py` — 273 lignes, 19 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08521_workspace.py` — 282 lignes, 11 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08522_xml_folding.py` — 137 lignes, 8 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08523_bidirectional_tag_highlight.py` — 90 lignes, 9 fonctions `test_*` de niveau module
- `tests/test_v0852_iiif_manager.py` — 130 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v0853_iiif_editorial_selection.py` — 225 lignes, 10 fonctions `test_*` de niveau module
- `tests/test_v0854_iiif_exact_autolink.py` — 106 lignes, 9 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v0855_sync_canvas_resolution.py` — 280 lignes, 14 fonctions `test_*` de niveau module
- `tests/test_v0856_pivot_scaffold.py` — 236 lignes, 16 fonctions `test_*` de niveau module
- `tests/test_v0857_pivot_visibility.py` — 50 lignes, 4 fonctions `test_*` de niveau module
- `tests/test_v0858_partial_sync_scaffold.py` — 107 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v0859_column_crop.py` — 79 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_v085_page_iiif_local.py` — 183 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_xpath_search.py` — 51 lignes, 5 fonctions `test_*` de niveau module

## Fichiers complémentaires

Répertoires : `alignments/`, `xml/`, `rendering/`, `resources/`, `help/`, `i18n/`, `web_output/`, `web_viewer/`, `tests/`.

L’inventaire exact des **268 membres ZIP**, y compris les données et les documents hérités, figure dans `VERIFICATION/INVENTAIRE_ZIP_SOURCE.txt`.
