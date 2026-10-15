# Varians — Passation de développement V0.8.5.24

**Date : 14 octobre 2026.** **Nouvelle version complète : V0.8.5.24.** La V0.8.5.23 de l'archive `Varians_PASSATION_V0.8.5.23_2026-10-14.zip` est l'unique point de départ. Les 223 membres de la V0.8.5.23 sont préservés, sauf évolution documentée de leurs contenus, et sont accompagnés d'un module géométrique, de tests et d'une documentation dédiés.

## Décisions à respecter sans exception

- **Abandon de l'assistance à la production d'apparat critique** (`<app>`, `<lem>`, `<rdg>`) : pas de modèles ni de génération automatique. Les fonctions d'édition XML existantes ne sont pas retirées.
- Surlignage bilatéral des balises XML = déjà terminé en V0.8.5.23 ; ne pas le recréer.
- **Pivot technique ≠ leçon éditoriale**, OCR géométrique ≠ synchronisation. Des `base_keys` réellement compatibles sont requis ; jamais d'alignement deviné à partir de la proximité, de l'ordre, ou de l'existence de fichiers.
- Une double image = un seul `graphic`, une `surface`, des `zone` et des `pb/@facs` explicites. Préserver les identifiants, la TEI, les JSON, les images, les espaces significatifs et les sauvegardes.
- Architecture Python/PySide6, Windows/Linux/macOS. Les sept catalogues i18n et les sept aides HTML sont obligatoires. L'interface Qt n'a pas été vérifiée physiquement sous Windows lors de cette livraison.

## Travaux réalisés en V0.8.5.24

1. **Nouveau module JavaScript pur `web_viewer/geometry.js`** : coordonnées OCR/image, polygones PAGE XML, cadres, recadrages à 24 pixels source, limites de colonnes/pages, fenêtres de trois lignes sans traversée de colonne, zone de double image en pixels source, choix d'une ligne secondaire réellement liée. Il est injecté par `web_viewer/generator.py` dans l'HTML exporté qui demeure autonome.
2. **Parité Python dans `editeur_tei.py`** : préservation de tous les sommets du polygone même hors de la bbox historique ; bbox dérivée des polygones seuls ; recadrage annulé si la géométrie est absente au lieu d'utiliser une fausse coordonnée (0,0) ; arrondis de la borne supérieure explicites.
3. **Export web** : sélection du folio issu du premier `pb/@facs` dès l'initialisation ; zones source non remultipliées par l'échelle OCR ; recadrage local des images non recadrables à distance, avec overlay dans le même repère source ; repli vers l'image IIIF entière lorsque le crop distant échoue ; cadres orange pour lignes reliées et bleus pour une ligne courante non reliée ; démarrage sans accès `localStorage` ; échappement HTML du titre.
4. **Ressources et liens** : les liens secondaires qui ne correspondent à aucune ligne du pivot publiée n'activent plus le mode lignes dans l'export ; les images locales trouvées sont copiées et les images absentes sont signalées dans `meta.export_warnings` avec le nom de fichier (sans publier le chemin local). Les identifiants de témoins sont protégés contre les collisions de noms portables ; les chemins historiques restent stables en l'absence de collision.
5. **Tests et documents** : suite `tests/test_v08524_web_geometry.py`, scénario facultatif Chromium `tests/manual_v08524_chromium.py`, `WEB_VIEWER_GEOMETRY.md`, mise à jour des aides français, anglais, allemand, japonais, tchèque, italien, russe et addenda aux documents techniques.

## Vérifications effectuées

- Exécution indépendante de `python -m pytest -q --disable-warnings` sous Linux : **435 passed, 2 skipped**. Les deux tests ignorés ne sont pas présentés comme réussis ; la passation initiale V0.8.5.23 annonçait 428 réussis dans un autre environnement, la première exécution locale de la même version a donné 426 réussis et 2 ignorés.
- Compilation `python -m compileall -q .` : réussie.
- Vérification réelle Node.js des fonctions géométriques et de la syntaxe JS du HTML exporté : réussie.
- Export du projet de démonstration `project.xml` : réussi, **3 témoins / 3 790 lignes** ; il ne s'agit pas des manuscrits personnels de l'utilisateur.
- Chromium headless par Playwright : capture synthétique et inspection géométrique des deux zones d'une image de 490 × 338 pixels représentant une source de 3924 × 2704 avec OCR de 1962 × 1352 et polygone concave. **Aucune exception JavaScript ; géométrie attendue vérifiée.** Navigation `file://` bloquée par le conteneur, le test a chargé le HTML en mémoire et la ressource image en data URL. Pas de test IIIF distant réel.
- Sept XML de 621 messages et sept aides HTML avec leur section V0.8.5.24 : vérifiés.
- Les contrôles définitifs d'archive (CRC, contenus, empreintes) figurent dans le rapport et le manifeste accompagnant la distribution.

## Ordre de reprise

**V0.8.5.25** : IIIF Image API v2/v3, haute résolution réellement demandée en fonction de la zone et de l'affichage, interrogations contrôlées `info.json`, politiques de taille/qualité, repli haute→basse définition, 403/404/429/5xx, CORS, latence, requêtes obsolètes, copies et droits, mode offline. Réaliser des tests avec serveur simulé et vérifications sur services réels autorisés, sans dépendre des réseaux pour les tests ordinaires.

**V0.8.5.26 (conception à arbitrer avant développement)** : personnalisation CSS du viewer ; XSLT de rendu de contenu avec contrats HTML de synchronisation, profils génériques HTML/XML/texte, sécurité de `document()`, include/import, symlinks et réseau ; choix de format, assets, scripts et persistance à discuter. L'aperçu **interne** XSLT/CSS existant reste fonctionnel et distinct.

**V0.8.6** : audit scientifique/technique en lecture seule, rapports structurés, contrôle des liens et chemins, manifeste SHA-256, empaquetage portable uniquement de ressources réellement disponibles et autorisées. Aucun « nettoyage » automatique du corpus.

## Essais utilisateur encore nécessaires

Ouvrir Varians sous Windows, vérifier d'abord les paires XML et le repliage, puis exporter un projet véritable avec PAGE XML multicolonnes et une image double ; comparer visuellement les sommets, le contexte de recadrage, les zones `@facs`, les images IIIF locales/distantes et les témoins non synchronisés. Tester aussi les dispositions du poste de travail. Aucun essai réel PySide6 sur Windows, Linux ou macOS n'est revendiqué ici.
