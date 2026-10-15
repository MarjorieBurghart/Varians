# Passation Varians V0.8.5.25 — 14 octobre 2026

**Base exclusivement reprise : archive complète `Varians_V0.8.5.24_Parite_Geometrique_Viewer_Web_Complete.zip`.** Les 230 fichiers du paquet antérieur sont conservés ; seules les sources affectées, quelques tests de contrat de version et les documentations courantes ont évolué. La V0.8.5.25 est une nouvelle version du logiciel, et non un patch isolé.

**Décisions intangibles :** pas de modèles de génération d'apparat TEI, surlignage bidirectionnel XML déjà livré, TEI scientifique immuable lors des affichages/exports, aucune synchronisation imaginaire, ressources IIIF/images/OCR indépendantes, Windows/Linux/macOS, 7 langues et 7 aides. La distinction entre pivot technique et choix philologique de base reste fondamentale.

## Changements et fichiers

`web_viewer/iiif.js` ajoute la sélection d'images selon zoom/densité, support Image API v1/v2/v3, requêtes de région, limites de taille, repli progressif et annulation de chargements obsolètes. `web_viewer/generator.py` l'injecte en ligne et publie un avertissement lorsque des images restent distantes. `iiif_manifest.py` et `image_sources.py` propagent les limites IIIF reconnues sans altérer les sources d'origine. `web_output/viewer.html` est régénéré depuis le projet de démonstration. Sept chaînes traduites pour les dépendances IIIF distantes et sept aides sont mises à jour. Voir `WEB_VIEWER_IIIF.md` pour les contrats détaillés.

## Validation

Rapport indépendant : `TEST_REPORT_V0_8_5_25.txt`. La suite héritée V0.8.5.24 était de 435 réussites, 2 tests ignorés ; la suite V0.8.5.25 ajoute 9 tests réussis. Les tests historiques vérifiant un numéro de version ou le nombre exact de clés de traduction sont actualisés de **0.8.5.24 → 0.8.5.25** et **621 → 622**, sans supprimer leur vérification du contenu. Chromium/Playwright vérifie le repli 429→403→image complète et la navigation. Le réseau IIIF réel, les droits, PySide6 Windows/macOS/Linux et les manuscrits utilisateurs n'ont pas été testés. L'absence de PySide6 provoque deux tests ignorés.

## Marche à suivre lors de la reprise

1. Partir de **cette** archive complète, sans copier une version historique du générateur.
2. Préserver `web_viewer/geometry.js` et `web_viewer/iiif.js` comme modules distincts et injectés dans le HTML autonome. Refaire les tests `pytest`, Node, Chromium.
3. Pour le prochain chantier **0.8.5.26**, discuter d'abord des décisions toujours ouvertes de personnalisation du viewer et des profils XSLT/CSS (`WEB_EXPORT_CUSTOMIZATION_DESIGN.md`), sans confondre avec la XSLT d'aperçu Qt qui existe déjà.
4. Conserver dans le plan **0.8.6** l'audit **en lecture seule**, l'archivage portable, les diagnostics des chemins et droits, et les données scientifiques non destructives.
5. Ne jamais déclarer qu'une interface Qt native a été testée sans essai PySide6 graphique réel. Les tests utilisateurs annoncés après la 0.8.5.25 restent à effectuer.

**Références durables :** `DEVELOPER_HANDOFF.md`, `CODE_MAP.md`, `ALIGNMENT_FORMAT.md`, `PAGE_IIIF_LOCAL.md`, `IIIF_SYNC_RESOLUTION.md`, `DOUBLE_PAGE_PARTS.md`, `WEB_VIEWER_GEOMETRY.md`, `WEB_VIEWER_IIIF.md`, `XSLT_POLICY.md`, `ROADMAP_REVISED_2026_10.md`, `PROJECT_AUDIT_PLAN.md`.
