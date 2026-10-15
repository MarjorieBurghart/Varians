# Passation technique — Varians V0.8.5.25.1

Date : 14 octobre 2026. Base unique : archive complète V0.8.5.25 (237 fichiers). Cette livraison est un **correctif autonome complet**, sans suppression de fonctions scientifiques, et non une anticipation de la V0.8.5.26.

## Origine du correctif

L'utilisateur signale que l'export HTML affiche **tous les manuscrits en pages entières** malgré les liens TEI ↔ lignes disponibles. Diagnostic dans les sources V0.8.5.25 : `web_viewer/generator.py` extrayait les pages de `pb/@n` et cherchait directement ces clés dans les pages JSON. Les projets dont `pb/@n` est un folio et dont `pb/@facs` pointe vers une surface/zone pouvaient produire zéro ligne synchronisée, malgré le JSON du pivot et les `base_keys` du secondaire. Reproduction synthétique positive et vérifiée dans Chromium ; la TEI/les JSON particuliers de l'utilisateur n'ont pas été reçus ici.

## Changements

- Ajout `web_viewer/page_resolver.py` pour résolution conservatrice et contrôlable des pages ; aucune association approximative ou ordinale.
- Adaptation ciblée de `extract_corrected_pages()` et `extract_reading_document()` dans `web_viewer/legacy_v11_core.py` ; compatibilité de leur API par défaut ; protection des clés de lignes lorsque deux `<pb>` renvoient à une même image double.
- `web_viewer/generator.py` utilise la résolution sur les deux flux, et joint des compteurs de diagnostic anonymes de contenu à `meta` / `witnesses`.
- Nouveau corpus de tests `tests/test_v08526_web_page_anchor_resolution.py` (nom conservé par historique de développement, mais la livraison est bien **0.8.5.25.1**) et essai de navigateur `tests/manual_v085251_line_sync_chromium.py`.
- Actualisation des sept aides, du README, de la cartographie et des documents de passation ; sept catalogues d'interface d'origine conservés sans changement de clés.
- Régénération du HTML de démonstration avec le moteur corrigé.

## Contrats intangibles

Éditeur Python/PySide6 multi-OS, XML-TEI scientifique inchangé, JSON Varians-Synchro inchangés, `base_keys` effectifs obligatoires sur secondaires, images IIIF et ALTO distinctes de la synchronisation, vraie géométrie PAGE XML, zones de doubles pages, 7 langues et 7 aides, sauvegardes atomiques ; pas de générateur d'apparat critique.

## Validation et limites

Consulter `TEST_REPORT_V0_8_5_25_1.txt`. Le rendu est testé dans Chromium **sur des images synthétiques**, et non sur les images réelles de l'utilisateur. Absence d'essai GUI natif Windows/PySide6. Le code signale les ambiguïtés mais ne prétend pas corriger des JSON sans lien effectif. Si un problème persiste, examiner les champs de diagnostic embarqués avant toute modification supplémentaire.

## Reprise ultérieure

À partir de cette archive complète, conserver les corrections du résolveur et les régressions. La V0.8.5.26 reste le projet de personnalisation des exports web XSLT/CSS **à discuter avant décision de format**. La V0.8.6 concerne l'audit scientifique et le paquet portable, en lecture seule.
