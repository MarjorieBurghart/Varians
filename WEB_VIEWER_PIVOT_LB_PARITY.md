# VARIANS — V0.8.5.25.3 — Parité des jalons `<lb/>` entre éditeur et viewer web

## Diagnostic et cause

**Incident remonté :** les images sont correctement affichées en mode lignes dans le HTML exporté, mais cliquer dans le texte ne place pas correctement les manuscrits secondaires, alors que le même projet fonctionne dans l'éditeur PySide6.

La cause **constatée dans les sources** de la 0.8.5.25.2 était une divergence du contrat d'indexation :

- `editeur_tei.MainWindow.lb_spans` relève les `<lb edRef="#PIVOT"/>` dans **l'ordre global de leur apparition dans la source XML**, puis `ordinal_at_cursor` fournit un indice dans `base_items` (`flatten_primary` : ordre des pages JSON, puis ordre des lignes JSON). Le résultat est la clé **réelle**, de type `page_id::line`, utilisée ensuite par les `base_keys` des témoins secondaires.
- `web_viewer.legacy_v11_core.extract_reading_document` repartait de `pb/@n`, résolvait un identifiant de page physique via `@facs` si possible, puis **recomptait les `<lb>` par page** à partir de 1. La TEI peut pourtant employer des folios éditoriaux, deux `<pb>` pour une image double, des `<pb>` d'autres témoins, des liens `@facs` non résolubles, ou une numérotation de lignes non consécutive.
- `web_viewer.generator.build_dataset` supprimait en outre du pivot exporté les lignes absentes de ce rapprochement TEI/page, alors que l'éditeur les conserve dans `base_items`. Une bonne clé du témoin secondaire pouvait ainsi être absente du viewer.

Exemple : le JSON pivot contient `physical-A::4`, `physical-A::9`, `physical-B::3`. Avec trois jalons `<lb edRef="#Mu"/>`, l'éditeur utilise ces **trois clés exactes**, dans cet ordre. L'ancienne logique web pouvait émettre `physical-A::1`, `physical-A::2`, voire aucune clé quand `pb/@facs` ne se résolvait pas.

## Correction

1. `web_viewer/tei_line_anchors.py` définit un indexeur pur et testable qui associe chaque `<lb edRef="#PIVOT"/>` de la TEI, dans son ordre source, à **la clé effective du JSON pivot**, selon le contrat de l'éditeur. Aucune comparaison textuelle, géométrique ou par numéro de folio ne crée de clé.
2. Les deux parcours TEI (`extract_corrected_pages` et `extract_reading_document`) utilisent ce même contrat. Les références de page restent utilisées pour **la navigation folio**, jamais pour renuméroter les clés de ligne.
3. Le pivot publié conserve désormais **toutes** les lignes physiques chargées selon la politique de l'éditeur. Les textes/runs/annotations sont ajoutés **par clé exacte**, sans éliminer les lignes sans texte éditorial correspondant.
4. Les témoins secondaires continuent à être synchronisés exclusivement par leurs `base_keys`/`keys816` existants. Les témoins sans clés utilisables restent en mode pages.
5. Le jeu de données exporté contient `meta.pivot_lb_index` : `tei_lb_count`, `physical_line_count`, `mapped_lb_count`, `unmapped_lb_count`, `physical_without_lb`, `count_match`. Un décalage de nombre provoque un avertissement traduit (7 langues) ; au-delà des clés réellement disponibles, **aucun lien n'est inventé**.

### Périmètre et prudence

La politique de sélection du pivot, la sérialisation scientifique, les fonctions desktop, les images, les coordonnées PAGE/ALTO, les zones de doubles pages et le chargement IIIF n'ont pas été transformés. Les deux schémas de correspondances (TEI→pivot, pivot→secondaire) demeurent séparés. L'association **ordinale** TEI→pivot existait déjà dans l'éditeur ; elle ne doit pas être confondue avec une nouvelle inférence philologique ou une interpolation entre témoins.

Quand les `<lb/>` de la TEI et les lignes physiques du JSON diffèrent en nombre, une partie du document peut rester sans ancre, ou une ligne physique sans texte éditorial : cette situation est signalée sans déplacer les indices suivants pour la masquer. Si l'utilisateur ajoute des `<lb edRef="#pivot"/>` dans des notes ou des lectures alternatives, ils sont comptés comme dans le cache lexical de l'éditeur, même si leur texte n'est pas rendu dans la lecture principale.

## Validation sur données synthétiques

- 460 tests automatisés réussis, 2 ignorés, 0 échec.
- 5 scénarios Chromium exécutés : doubles pages et polygones, IIIF et replis réseau, ligne/folio, clics notes/références, parité ordinale multipage avec deux manuscrits et trois lignes.
- Nouveau corpus : absence de `<pb>`, `pb/@facs` non résolu, `pb` d'un autre témoin, plusieurs pages JSON, lignes `4/9/3` non consécutives, `lb` dans une note, nombre de jalons excédant les lignes physiques, impossibilité d'inventer des clés supplémentaires.
- Export du projet de démonstration T1/T2/P : **3790 `<lb/>` pivot et 3790 lignes physiques**, 0 clé de texte orpheline.
- Vérification graphique native **PySide6 non exécutée** (bibliothèque absente de l'environnement) ; corpus utilisateur Mu–F–L **non fourni** et non testé.

## Vérification utilisateur

1. Fermer les anciens viewers, lancer **Varians 0.8.5.25.3** et régénérer l'export HTML de son propre projet ; ne pas réutiliser l'ancien `viewer.html`.
2. Dans le navigateur, cliquer sur trois passages éloignés, idéalement appartenant à des pages et colonnes différentes. Vérifier que le pivot **et** chaque témoin muni de `base_keys` pointent sur les lignes correspondantes.
3. Tester également une note, une variante, une image double et un témoin sans synchronisation, lequel doit rester en mode pages.
4. Si la synchronisation échoue encore, noter la clé `data-line` de la portion sélectionnée et les compteurs `meta.pivot_lb_index` / `sync_diagnostic` du HTML exporté. Les données réelles permettent d'identifier alors une éventuelle divergence entre le balisage TEI et l'ordre des lignes JSON, sans faire d'hypothèse.
