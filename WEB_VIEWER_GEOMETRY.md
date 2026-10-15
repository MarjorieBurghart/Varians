# Varians V0.8.5.24 — Contrat de géométrie du viewer web

## État, principe et responsabilités

La V0.8.5.24 corrige les calculs géométriques et le choix des lignes de contexte du viewer web **sans modifier les données scientifiques** (TEI, PAGE/ALTO, alignements JSON). Il s'agit d'un module de visualisation, pas de création d'alignement ou d'apparat critique. L'étape IIIF avancée a été livrée en V0.8.5.25 : voir `WEB_VIEWER_IIIF.md`. Les interfaces/profils XSLT/CSS (proposés pour V0.8.5.26) restent à discuter. La comparaison réelle de rendu PySide6/Chromium sur les manuscrits de l'utilisateur demeure à réaliser.

Modules : `web_viewer/geometry.js`, sans DOM ni réseau, est injecté dans le HTML **autonome** par `web_viewer/generator.py` ; `image_sources.py` détermine côté Python les bornes géométriques, la continuité physique et les requêtes d'image ; `editeur_tei.py` définit les rectangles de crop et le tracé Qt ; `folio_navigation.py` traite la géométrie des parties de double page. Le module JavaScript n'imagine jamais de `base_keys` ni de relations TEI.

## Conventions et transformations

- **Repère OCR** : `(x_ocr, y_ocr)`, dimensions `(W_ocr, H_ocr)` fournies par PAGE/ALTO ou par un JSON d'alignement. Les polygones conservent tous leurs sommets dans leur ordre initial ; pas de simplification implicite.
- **Repère source image/Canvas** : `(x_img, y_img)`, dimensions `(W_img, H_img)` déclarées par la source image. Pour une ligne OCR, `x_img = x_ocr × W_img / W_ocr` et `y_img = y_ocr × H_img / H_ocr`. La même transformation s'applique indépendamment à tous les points d'un polygone concave, dans le même ordre.
- **Cadre de recadrage** : `(crop_x, crop_y, crop_w, crop_h)` en pixels de **l'image source**. La fenêtre de contexte est choisie avec la même fonction de continuité physique que l'éditeur : élément courant, au plus un voisin précédent et suivant, arrêt au changement de page ou de colonne. Les côtés du crop sont tirés des bornes des lignes retenues, augmentées de **24 pixels source** et bornées à l'image ; si une bbox historique ne contient pas tous les points du polygone, on utilise leur union. Une géométrie absente empêche le recadrage et non la consultation de la page.
- **Image effectivement décodée** : `(W_bitmap, H_bitmap)` peut ne valoir que `490 × 338` pour un Canvas déclaré `3924 × 2704`. Dans le crop, un sommet source apparaît dans le bitmap aux coordonnées `((x_img − crop_x) × W_bitmap / crop_w, (y_img − crop_y) × H_bitmap / crop_h)`. Le navigateur emploie un `viewBox` SVG défini dans le même repère crop.
- **IIIF recadré** : si un service Image API permet de demander la région source, l'image reçue correspond au seul rectangle crop ; le SVG utilise toujours le `viewBox` exprimé dans le repère image source. En l'absence de service, ou lors du repli sur une image complète, le navigateur applique un crop local (image de pleine largeur placée dans un conteneur masqué), sans changer le repère des contours. Les limites et cas d'erreur des services sont à renforcer en V0.8.5.25.
- **Image double** : `<surface><graphic .../><zone xml:id="...-left" .../><zone xml:id="...-right" .../></surface>` décrit **une image et deux parties**. `zone/@ulx`, etc. sont **déjà** en pixels source image : ne jamais les remultiplier par `W_img / W_ocr`. Les `<pb @facs>` désignent l'une des zones. Les régions sont bornées à l'image ; aucune association n'est déduite d'un numéro de page ambigu.

## Robustesse, images et cohérence scientifique

Le navigateur présente une ligne courante ou réellement synchronisée (orange) ; une ligne consultée sans correspondance apparaît en bleu. En mode page, l'affichage de cadres n'implique **aucun alignement** entre témoins. Un secondaire n'est déclaré synchronisé dans l'export que lorsqu'un `base_keys`/`keys816` réellement présent dans le **JSON brut** peut être résolu à une ligne du pivot effectivement publiée. Sinon il reste en mode page. Un chemin d'image locale inexistant est indiqué dans `meta.export_warnings`, sous la forme d'un **nom de fichier** (jamais un chemin local complet divulgué dans un HTML public), et aucune fausse URL relative n'est émise. L'export conserve les assets locaux existants et les références IIIF distantes restent soumises à disponibilité et droits.

Le viewer ne requiert pas l'accès à `localStorage` pour démarrer (navigateurs ou contextes qui le refusent). Le titre inséré dans `<title>` est échappé. Les profils personnalisés et les XSLT externes n'ont pas été activés dans cette livraison.

## Tests et limites

`python -m pytest -q` : suite existante + `tests/test_v08524_web_geometry.py` ; les comparaisons Python/JavaScript exécutent réellement le module JS via Node lorsqu'il est installé et exécutent les **fonctions de production** de `editeur_tei.py` extraites par AST sans charger PySide6. Les tests comparent changement de colonne/page, polygones concaves dépassant une bbox, polygones seuls, géométrie absente, dimensions OCR/Canvas différentes, repères des zones, liens secondaires orphelins et assets manquants.

Une vérification Chromium headless par Playwright a été exécutée le 14/10/2026 sur une image synthétique `490 × 338` représentant un Canvas `3924 × 2704`, avec OCR `1962 × 1352`, deux zones TEI et un polygone concave ; sélection des deux parties et inspection du SVG et de l'image chargée. La page a été injectée en contexte `about:blank` (la navigation file:// est bloquée par l'environnement de validation). Ce test navigateur n'est **pas** un essai de l'application PySide6 sous Windows ni une vérification d'un véritable serveur IIIF. Les validations visuelles des manuscrits réels sont à mener sur le poste utilisateur.

### Essai de réception demandé

Avec un projet possédant une page PAGE XML multicolonnes et une double image, exporter le viewer, l'ouvrir dans un navigateur, activer **Cadres** et comparer le même passage avec l'éditeur : ordre des sommets, alignement des contours, cadrage en début/fin de colonne, sélection des parties via `<pb @facs>`, cas image réduite et mode page d'un secondaire non synchronisé. Toute divergence doit être remontée avec le projet exporté (les images protégées peuvent être retirées), les dimensions sources et une capture des deux rendus.

## Addendum V0.8.5.25.1 — lien géométrie / TEI

Une zone de double page référencée par `pb/@facs` désigne sa surface parente ; le viewer peut donc accéder à la page physique JSON et aux lignes sans confondre `pb/@n` (folio) et l’ID technique de l’image. Voir `WEB_VIEWER_LINE_SYNC_FIX.md`. Deux `<pb>` de parties gauche/droite sur la même surface ne réinitialisent pas les clés de lignes physiques.
