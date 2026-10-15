# 04 — Images, IIIF, ALTO/PAGE, géométrie, double page

## 1. Trois ressources indépendantes par témoin

1. La source d'image peut être absente (`none`), locale ou fournie par un manifeste/service IIIF.
2. La géométrie ALTO/PAGE peut venir d'un JSON de synchronisation ou de fichiers OCR externes indépendants.
3. La correspondance au pivot exige un JSON possédant de véritables `base_keys`, jamais la simple existence d'ALTO/PAGE.

Tout nouvel import doit préserver une image IIIF sélectionnée lorsque l'ALTO ajouté n'a pas pu être associé à son Canvas. Les pages OCR orphelines figurent dans `unassociated_layout_pages`, sans remplacer une image canonique par un objet vide.

## 2. Modules et trajets des données

- `alto_import.py` : lecture ALTO/PAGE, positions OCR, lignes, identifiants et polygones ; acceptation des sources indépendantes.
- `iiif_manifest.py` : lecture des manifestes Presentation API v2/v3.
- `iiif_selection.py`, `iiif_page_selection.py` : décisions de sélection des images et rapprochements sûrs.
- `iiif_resolution.py` : association déterministe Canvas↔OCR/JSON, via identifiant service/image explicite, `ocrLink`/`pageLink` choisi, libellé exact unique ou index local sûr ; **jamais** par le rang dans une liste.
- `iiif_local.py` : copies IIIF locales indexées, gestion scope all/ocr ; `iiif_download_manager.py` : interface et opérations asynchrones.
- `image_sources.py` : politiques d'image, repères d'origine, crop, limites de colonne/page et résolutions.
- `tei_facsimile.py` et `folio_navigation.py` : liens `<surface>/<graphic>/<zone>/<pb>` et doubles pages ; validation du côté à partir de la géométrie.
- `editeur_tei.py::ManuscriptPanel` : rendu graphique PySide6.
- `web_viewer/geometry.js`, `iiif.js` : rendu de navigateur, crop et politiques de téléchargement.

## 3. Coordonnées : formule et repères

| Repère | Dimension habituelle | Utilisation |
|---|---|---|
| OCR ALTO/PAGE | `alto_width`, `alto_height` | Bbox, sommets du polygone |
| Image source / Canvas | `image.width`, `image.height` | Zones TEI, crop, requête IIIF |
| Bitmap reçu | parfois beaucoup plus petit | affichage et scaling seulement |
| Viewbox/crop | pixels source image | position des contours et fenêtres de lignes |

Si la taille OCR diffère de la taille image, appliquer chaque composante `x × W_img/W_ocr`, `y × H_img/H_ocr`. **Ne jamais transformer une zone TEI déjà exprimée en pixels source**. Une vignette IIIF 490 px ne doit ni déplacer les cadres ni faire grossir arbitrairement la scène.

Le recadrage du viewer retient la ligne courante et, au plus, ses voisines physiques autorisées **sur la même page et dans la même colonne**, avec marge source documentée de **24 pixels** puis bornage à l'image. Une forme PAGE concave reste un polygone SVG ayant tous ses sommets, pas son rectangle minimal.

## 4. Double page et liens TEI

Une `<surface>` correspond à **une seule image**, même si elle comprend deux zones `-left` et `-right`. Un `<pb>` éditorial peut pointer vers la gauche et un autre vers la droite (`@facs`). Deux `<pb>` pour la même image ne doivent **jamais** entraîner une remise à zéro des lignes physiques du pivot.

Le dialogue « Double page… » reste accessible même en mode lignes, affiche une vignette de **l'image entière** et autorise le déplacement d'une barre de séparation. Les zones sont mises à jour de façon sûre sans suppression des autres annotations ni changement des `xml:id` pointés par des `<pb/>` existants.

La partie pertinente n'est pas devinée lorsque la ligne chevauche la séparation ou ne possède pas une géométrie claire ; la politique historique de décision impose au moins 85 % dans la partie retenue et au plus 15 % dans l'autre. Sinon, demander un choix explicite.

## 5. IIIF dans le viewer web

`web_viewer/iiif.js` est incorporé au HTML par le générateur :

- support du format de requête Image API v1/v2/v3 et de la différence `full` / `max` pour l'image entière ;
- demande de région dimensionnée selon le crop et la densité d'affichage, avec limites annoncées par la source/le `info.json` quand disponibles ;
- repli sur région plus légère, image entière recadrée localement, puis vignette ;
- gestion des erreurs 403/404/429/5xx et réseau lent, timeout et abandon des requêtes obsolètes ;
- le PNG/JPEG exporté localement est distinct de l'URL IIIF distante ; une page HTML autonome ne garantit pas la disponibilité des serveurs, des licences et des contrôles d'accès.

**Sécurité/réalisme :** une ressource distante n'est pas implicitement embarquée ni utilisable hors ligne. L'export doit signaler les images IIIF externes et les copies locales effectivement présentes. La suppression de ressources anciennes dans le répertoire de sortie n'est **pas automatique** ; privilégier un répertoire propre si l'on doit diffuser seulement une sélection de témoins.

## 6. Test matrix géométrique minimale

- ALTO rectangulaire et PAGE concave à six sommets, même page/image.
- Rapport OCR/image de 1:2, vignette très basse résolution, zoom fort.
- Ligne au bord d'une colonne avec une ligne voisine physiquement proche dans une autre colonne : celle-ci **ne doit pas** être incluse dans le crop.
- Double page : deux zones d'une seule image, `<pb>` vers chacune, marge de séparation ambiguë.
- Canvas IIIF connu mais OCR non lié : image maintenue, OCR orphelin signalé.
- Images uniquement, sans OCR ou JSON : navigation page préservée.
- JSON secondaire sans `base_keys` : mode pages malgré contours OCR.
- Service IIIF v2/v3 : région réussie ; région 429/403 puis image entière ; échec général et vignette ; bascule rapide de témoin sans image ancienne dans le nouveau panneau.

Tests associés : `tests/test_v08524_web_geometry.py`, `test_v08525_iiif_web.py`, `test_v08514_iiif_alto_independence.py`, `test_v08518_folio_navigation.py`, `test_v08520_double_page_parts.py`, `test_v0859_column_crop.py`, `test_v085_page_iiif_local.py`. Les scripts `tests/manual_v08524_chromium.py`, `manual_v08525_iiif_chromium.py`, etc. servent de scénarios navigateur synthétiques mais ne remplacent pas l'essai sur vrais manuscrits et vrais serveurs.

## 7. Limites historiques connues

Les services IIIF d'institutions peuvent être indisponibles, filtrer les requêtes, refuser CORS ou le recadrage, ou limiter les dimensions. Une panne Gallica/IRHT n'est pas automatiquement un problème Varians. Les effets exacts du gestionnaire natif de fenêtres détachées et de la superposition des cadres doivent encore être validés sur les systèmes cibles selon le contexte d'usage.
