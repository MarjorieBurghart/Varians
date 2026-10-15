# VARIANS V0.8.5.25.3 — Note de passation complète du correctif

**Date :** 14 octobre 2026. **Base source :** V0.8.5.25.2 complète. **Type :** correctif ciblé de synchronisation TEI→images dans le viewer web ; pas le chantier XSLT/CSS V0.8.5.26.

## Déclencheur

L'utilisateur constate que le viewer web affiche enfin les lignes, mais ne suit pas correctement les clics sur les passages correspondant aux `<lb/>` du pivot et aux `base_keys` des autres manuscrits, alors que les mêmes liaisons fonctionnent dans Varians desktop. Les précédents correctifs (0.8.5.25.1/0.8.5.25.2) visaient surtout la résolution des pages et l'interactivité du clic ; **la divergence de numérotation des lignes n'avait pas été corrigée**.

## Cause prouvée et réalisation

Lire impérativement `WEB_VIEWER_PIVOT_LB_PARITY.md`. L'éditeur fonctionne par **ordinal global de `<lb edRef="#pivot"/>` → ligne physique JSON pivot → clé `page_id::line` → `base_keys` secondaires** ; l'export utilisait une logique de **pagination `<pb>` + compteur local de `<lb>`**, qui peut générer des clés inexistantes.

Les modifications se trouvent dans :

- `web_viewer/tei_line_anchors.py` (nouveau) : contrat partagé d'indexation source TEI/JSON et diagnostic de divergences.
- `web_viewer/legacy_v11_core.py` : extraction des lignes éditoriales et de la lecture fondée sur ce contrat.
- `web_viewer/generator.py` : conservation de la totalité des lignes physiques JSON du pivot, enrichissement par clé réelle, métriques et avertissements des numéros de ligne.
- `tests/test_v085253_pivot_lb_contract.py` (nouveau) ; `tests/manual_v085253_lb_ordinal_chromium.py` (nouveau) ; test de résolution de pages mis à jour pour ne pas confondre erreur de folio et rupture de synchronisation par lignes.
- `i18n/{fr,en,de,ja,cs,it,ru}.xml`, `help/{fr,en,de,ja,cs,it,ru}.html` (chaînes/sections sur les jalons et le diagnostic), `editeur_tei.py` (`APP_VERSION`), `README.txt`, feuille de route, documentation et HTML de démonstration régénéré.

**À préserver absolument :** pas de générateur d'apparat critique ; pas d'alignement secondaire déduit ; pas de réécriture TEI/JSON ; les témoins sans `base_keys` restent en mode page ; aucune confusion entre le folio éditorial et la page physique ; multiples parties d'une seule image ; images IIIF et OCR indépendants ; 7 langues et 7 aides ; sauvegardes et projets anciens.

## Tests et limites

À la clôture : **460 passed, 2 skipped** sur Python (PySide6 réel absent), compilation Python réussie, les cinq scripts Chromium existants ou nouveaux réussis, génération HTML de démonstration T1/T2/P et correspondance de **3790** lignes pivot vérifiées. Les résultats sont des preuves sur données synthétiques/démonstration, **pas** un contrôle sur le projet réel Mu–F–L ni sur Windows/PySide6.

## Prochaines actions

Faire tester la V0.8.5.25.3 sur les manuscrits réels après **regénération** du viewer. En cas de divergence résiduelle, comparer les séquences ordonnées des `<lb edRef="#pivot"/>` de la TEI avec `flatten_primary` du JSON et les `base_keys` réels (sans inventer les relations). Si cela fonctionne, poursuivre la conception avec l'utilisateur de V0.8.5.26 XSLT/CSS, encore non approuvée, puis l'audit scientifique et l'archivage portable V0.8.6.
