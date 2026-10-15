# Varians 0.8.5.25.1 — Correctif de résolution des lignes TEI dans le viewer web

## Symptôme signalé

Le viewer HTML peut présenter **tous les témoins en pages entières** alors que les fichiers JSON de synchronisation contiennent les lignes du pivot et les liens `base_keys` des témoins secondaires.

Il existe une cause reproductible dans la version 0.8.5.25 : `build_dataset()` rapprochait les pages extraites de l'édition TEI par la **valeur de `pb/@n`**, utilisée directement comme clé du dictionnaire des pages JSON (`page.id`). Dans les projets modernes, `@n` est souvent un **folio éditorial** (`f002v`, `f003r`), tandis que la clé JSON est l'identifiant technique de l'image/OCR. Même lorsque `pb/@facs` fournit une référence explicite et exacte à `<surface>` ou `<zone>`, celle-ci n'était pas utilisée pour établir les clés. Une absence totale de pages émises pouvait désactiver `meta.line_sync` et faire passer tous les panneaux en mode page.

Ceci est un **défaut de code confirmé** avec un corpus synthétique et un navigateur réel. La présence de cette même cause dans les données privées de l'utilisateur reste à confirmer par son essai.

## Correctif

`web_viewer/page_resolver.py` établit une résolution *conservatrice* des jalons TEI vers les identifiants réels de pages des JSON de synchronisation, en donnant priorité aux preuves documentées :

1. `pb/@facs` vers le `xml:id` d'une `<surface>` associée au témoin par `tei_surface_id` ;
2. `pb/@facs` vers une `<zone>` appartenant à une telle surface, y compris parties gauche et droite d'une même image ;
3. Référence exacte entre `<graphic url="…">` et l'URL conservée d'une image de page, uniquement lorsqu'elle est univoque ;
4. Compatibilité ancienne : valeur de `pb/@n` identique à un **ID technique JSON** ; lorsque `@facs` n'est pas résoluble, ce repli nécessite un `@edRef` explicite désignant le témoin ;
5. Sans `@facs`, `pb/@n` peut représenter un libellé de page **strictement égal et unique**, sous réserve d'un `@edRef` explicite.

Aucune correspondance n'est déduite de l'ordre des pages, de la position d'un Canvas dans un manifeste, de la proximité de textes, d'un libellé approximatif, ou d'un identifiant ambigu. Les conflits d'identifiants, de zones et de pointeurs restent non résolus, plutôt que de fabriquer une association.

`extract_corrected_pages()` et `extract_reading_document()` acceptent un résolveur optionnel. Leur API historique, sans résolveur, reste inchangée. Le générateur crée un seul résolveur pour le témoin pivot **après l'assemblage des ressources** et l'applique aux deux extractions : les segments HTML `data-line`, les identifiants des lignes JSON et les `base_keys` se retrouvent alors dans le même référentiel.

**Double page :** deux `<pb>` peuvent pointer vers les deux `<zone>` d'une même `<surface>`. L'extraction HTML conserve désormais un compteur de lignes **par page physique** ; elle n'attribue plus la clé `page::1` à la première ligne de la seconde partie, à moins que le JSON ne représente effectivement une autre page physique.

## Informations de diagnostic intégrées

Le JSON incorporé dans `viewer.html` conserve :

- `meta.raw_pivot_lines` : lignes du pivot dans le JSON brut ;
- `meta.matched_pivot_lines` : lignes pivot réellement émises avec leur ancrage TEI ;
- `meta.tei_page_resolution` : nombres de pointeurs résolus par `@facs`, ID ou libellé, et des pointeurs non résolus/ambigus ;
- `witnesses[].sync_diagnostic` : `raw_lines`, `matched_base_keys`, `emitted_lines`, mode effectif `line|page`.

Ces compteurs servent à distinguer données absentes, noms de page incompatibles et liens secondaires manquants. **Ils ne modifient aucun fichier scientifique.** Dans la console JavaScript du visualiseur, `DATA.meta` et `DATA.witnesses.map(w => [w.id, w.sync_diagnostic])` permettent de consulter ces nombres.

Le viewer ne doit pas passer en mode lignes sur la simple existence d'un fichier OCR ou d'un JSON déclaré `role=secondary` ; il faut des lignes pivot publiables et des `base_keys` résolubles pour chaque secondaire.

## Tests et limites

- Tests automatisés : `tests/test_v08526_web_page_anchor_resolution.py` (noms de folios distincts des ID JSON, zones doubles, correspondance URL exacte, liens secondaires valides/absents, collisions, repli historique).
- Navigateur Chromium : `tests/manual_v085251_line_sync_chromium.py`, deux témoins indépendants, recadrages de lignes effectifs, clic TEI -> deux statuts de ligne mis à jour.
- Régression Chromium sur les doubles pages (`manual_v08524_chromium.py`) et les replis IIIF (`manual_v08525_iiif_chromium.py`).
- Suite complète et compilation : `TEST_REPORT_V0_8_5_25_1.txt`.

Non testé sur les manuscrits réels Mu–F–L de l'utilisateur ni dans une session Windows/PySide6. Les services IIIF authentifiés et les données historiques ambiguës ne sont pas validés. **Si un projet concret reste en mode pages**, conserver les JSON et la TEI originaux et examiner les diagnostics ; ne jamais créer des `base_keys` supposés pour forcer l'affichage.

## Feuille de route préservée

La présente version est un **correctif V0.8.5.25.1**, pas la V0.8.5.26. La personnalisation XSLT/CSS et les profils de publication restent un chantier distinct, dont les choix ouverts doivent être discutés avec l'utilisateur. L'audit scientifique V0.8.6 est toujours prévu en lecture seule.
