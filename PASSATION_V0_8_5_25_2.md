# Varians V0.8.5.25.2 — note de passation

**14 octobre 2026 — version corrective complète.** Base exacte : ZIP V0.8.5.25.1.

## Raison

L'utilisateur confirme le retour au mode lignes, mais signale que cliquer sur une portion du texte ne déplace plus les manuscrits à la ligne correspondante. Le problème spécifique de ses données réelles n'est pas isolé : les fichiers du projet Mu–F–L ne sont pas inclus dans la conversation. Plusieurs régressions certaines ou faiblesses ont été corrigées dans le chemin de clic (voir `WEB_VIEWER_TEXT_CLICK_FIX.md`), sans changer le modèle de données.

## Modules touchés

`web_viewer/generator.py`, `editeur_tei.py` (numéro de version), `i18n/` (7 fichiers, deux clés ajoutées), `help/` (7 sections ajoutées), documentation, nouveaux tests. `web_viewer/page_resolver.py`, `web_viewer/legacy_v11_core.py`, `web_viewer/geometry.js` et `web_viewer/iiif.js` demeurent inchangés par rapport à 0.8.5.25.1.

## Contrats et limites

Aucun assistant de génération d'apparat critique ; les projets sans images, sans OCR et sans `base_keys` restent autorisés ; jamais d'alignement conjectural. Les travaux XSLT/CSS du viewer web (0.8.5.26) et l'audit intégral portable (0.8.6) restent indépendants. Les sept langues et aides demeurent.

Les essais de Chromium sont effectués avec des ressources synthétiques uniquement. Le rendu natif PySide6 Windows/Linux/macOS et les ressources réelles de l'utilisateur ne sont pas testés ; demander un retour ciblé après régénération de l'HTML.

Consulter `TEST_REPORT_V0_8_5_25_2.txt` et le manifeste SHA-256.
