# Varians 0.8.5.25 — IIIF haute résolution dans le viewer web

## Périmètre scientifique et contractuel

La version **0.8.5.24** reste la base de la géométrie. Cette version **0.8.5.25** ne modifie ni les fichiers TEI, ALTO/PAGE XML, alignements Varians-Synchro, ni les `base_keys`, les zones doubles, ou la logique de pivot. Elle complète uniquement les demandes, l'affichage et le repli des images du **viewer HTML exporté**, et propage au viewer les limites de taille facultatives des services IIIF documentées dans le manifeste.

Modules concernés :

- `web_viewer/iiif.js` : nouveau planificateur de requêtes, cycle de chargement des images, annulation, repli, lecture facultative de `info.json` ; inséré dans le HTML autonome, sans CDN ni bibliothèque JS externe.
- `web_viewer/generator.py` : appels au planificateur avec le crop existant de `geometry.js`, densité de pixels de l'écran, zoom, largeur du panneau ; gestion des vues supprimées ; indication des images IIIF distantes.
- `iiif_manifest.py` : préservation facultative de `maxWidth`, `maxHeight` et `maxArea` quand elles sont déclarées par l'objet *service* du manifeste (v2/v3).
- `image_sources.py` : propagation de ces limites dans la copie d'image utilisée par le viewer ; les images locales, copies de travail IIIF et contenus d'origine restent inchangés.

## Versions de l'Image API et calcul des requêtes

Les URL sont construites à partir du véritable identifiant du service Image API, et **pas** du Canvas ou de l'image de vignette :

| API | Région demandée | Taille originale | Qualité |
| --- | --- | --- | --- |
| v1 | `full` ou `x,y,w,h` | `full` | `native` |
| v2 | `full` ou `x,y,w,h` | `full` | `default` |
| v3 | `full` ou `x,y,w,h` | `max` | `default` |

Pour une image demandée à résolution réduite, la taille `W,` est utilisée ; `W` dépend de la largeur affichée, du facteur de zoom, de la densité de pixels et des limitations annoncées. Les régions, exprimées dans les pixels de l'image source, sont bornées à cette image. Si la taille demandée atteint la largeur complète de la région, la requête d'image originale utilise le mot réservé `full` ou `max` selon l'API.

Le viewer essaye, dans cet ordre sans duplication d'URL :

1. Région à une résolution adaptée à l'affichage.
2. Même région à une définition moindre (si différente).
3. Image complète réduite, avec **recadrage local**.
4. Image complète encore plus petite (si différente).
5. URL d'aperçu du manifeste, recadrée localement.

Cette suite couvre notamment les services refusant les requêtes de région, les quotas de taille et les serveurs interrompus. Une erreur 403 ou 429 **n'autorise pas** le viewer à contourner un contrôle d'accès ; un éventuel aperçu ne s'affiche que si le serveur l'autorise lui-même.

Quand la requête régionale réussit, l'image rendue est exactement la région source. En repli sur une image entière (de basse ou haute définition), la balise `<img>` est dimensionnée et décalée par CSS dans la vue rognée : l'overlay SVG reste dans les coordonnées source, sans retransformer les polygones ni les zones TEI.

## `info.json` facultatif, et comportement sans réseau

Une interrogation `GET /info.json` peut être lancée en parallèle, **sans bloquer** le premier affichage. L'appel est sans identifiants explicites (`credentials: omit`), limité à 2,5 secondes et cache ses résultats en mémoire de la page. Une réponse JSON avec largeur/hauteur valides peut apporter des limites supplémentaires ; elles s'appliquent aux **prochaines** demandes (il n'y a pas de rechargement intempestif en cours de lecture). L'absence de CORS, une erreur réseau, un JSON invalide ou un refus de connexion n'empêche jamais les requêtes d'images normales. Les limites annoncées dans le manifeste sont utilisées même si `info.json` est inaccessible.

Chaque tentative d'image possède un délai de 12 secondes. Un changement de page, de témoin, de zoom ou de folio élimine les balises précédentes et **annule leurs minuteries et gestionnaires** ; un retour tardif ne peut pas remplacer la nouvelle image. L'image entièrement introuvable est explicitement remplacée par un message traduit.

Le HTML embarque son JavaScript et peut fonctionner sans serveur pour ses fichiers locaux. Il **ne contient pas automatiquement** les octets des images IIIF distantes : le statut de la page avertit du nombre de références IIIF distantes, et ces images requièrent une connexion et des permissions valides. Une copie locale IIIF disponible et autorisée suit le parcours habituel des images locales déjà incluses dans l'export.

## Tests et limites de la vérification

- `tests/test_v08525_iiif_web.py` : Node.js exécute réellement le module JS (versions 1/2/3, tailles, régions, limites, vignettes, sécurité des URL, absence de réseau nécessaire pour les métadonnées initiales). Un manifeste v3 teste la transmission des limites.
- `tests/manual_v08525_iiif_chromium.py` : essai réel Chromium/Playwright **hors réseau**, images synthétiques et réponses interceptées, erreurs 429 puis 403 sur deux tailles de région, repli vers image entière, zone de droite et SVG conservés, bascule vers un autre Canvas, puis scénario sans réseau et message d'échec. Aucune institution n'est contactée.
- `tests/manual_v08524_chromium.py` : régression sur les doubles pages, déformation des images réduites et polygones.

Pas de validation d'accès à un vrai service institutionnel (authentification, droits, requêtes protégées), ni de tests graphiques Qt sous Windows/macOS/Linux. Des différences propres aux serveurs IIIF et aux contraintes CORS peuvent subsister. L'utilisateur effectuera les essais réels sur son poste **après cette version**, comme demandé.

## Suites de la feuille de route

- **0.8.5.26** : consulter l'utilisateur avant de figer l'architecture et l'interface des profils XSLT/CSS de publication et de personnalisation. L'aperçu XSLT/CSS *interne* existe déjà et doit rester indépendant.
- **0.8.6** : audit scientifique et technique des projets en lecture seule, manifeste portable et archivage respectant les droits sur les images.
- Ne pas réintroduire d'assistant de fabrication d'apparat critique. Ne pas présumer de liens inter-témoins en l'absence de `base_keys` effectivement résolubles.

## Correctif postérieur V0.8.5.25.1

Un problème de sélection du *mode pages* à la place du *mode lignes* a été corrigé dans la résolution TEI ↔ JSON (`web_viewer/page_resolver.py`), indépendamment de la stratégie de requêtes IIIF. Ce correctif ne modifie pas `web_viewer/iiif.js`. Voir `WEB_VIEWER_LINE_SYNC_FIX.md`.
