# VARIANS — PASSATION V0.8.5.26 (VERSION INTERMÉDIAIRE)

**Date : 14 octobre 2026 — Base de reprise : V0.8.5.25.3.**

Cette distribution complète constitue la nouvelle **version de référence pour les prochains travaux**, sous réserve des vérifications graphiques Windows par l’utilisateur. L’ancienne feuille de route est suspendue ; aucune prochaine fonctionnalité n’est planifiée automatiquement.

## Corrections fonctionnelles

**A01 — Validation RELAX NG.** Lorsque le panneau de validation est ouvert, les éditions XML effacent immédiatement les diagnostics périmés, puis un `rng_refresh_timer` relance la validation après 1 250 ms sans saisie. Le résultat remplace intégralement les anciennes lignes ; un document redevenu valide produit un tableau vide et le statut valide. La validation explicite F8 fonctionne toujours. Le panneau fermé n'est pas ouvert par cette automatisation. Vérifier `editeur_tei.py` : `_text_changed`, `_auto_refresh_rng`, `validate_relaxng_document(automatic=...)`. La vérification reste synchrone dans le thread Qt après la temporisation ; ne pas prétendre disposer d'un validateur RELAX NG asynchrone complet.

**A02 — Complétion des noms d’attributs.** `CodeEditor` offre une liste de propositions en cours de frappe pour un nom d'attribut partiellement saisi dans la balise ouvrante ; la liste vient de `XmlContextCache`, du modèle RELAX NG actif ; les complétions de projet restent accessibles par Ctrl+Espace. Elle exclut les attributs présents, réévalue le contexte à la sélection, insère un nom suivi de `=""`, place le curseur entre les guillemets et conserve `Ctrl+Espace`. Aucun nom hors schéma n'est inventé. Ne pas ouvrir de complétion dans un commentaire, une fermeture ou une valeur citée. Qt natif non testé dans le conteneur de livraison.

**A03 — Recherche plein texte du viewer web.** `web_viewer/fulltext_search.js` indexe les fragments visibles des paragraphes (texte éditorial et références éditoriales), sans altérer la TEI, les `data-line`, les `base_keys` ni les liens aux images. La recherche est insensible à la casse. Un mode optionnel applique séparément u/v, i/j, c/t, dans les deux sens ; les résultats conservent leurs offsets d'origine, y compris entre deux segments XML voisins. La liste présente les occurrences et leur contexte, le surlignage des résultats, l'accès précédent/suivant et la synchronisation des témoins quand une clé physique reconnue existe. Il n'y a jamais d'alignement implicite. La recherche s'exécute hors ligne à partir du HTML autonome ; les images IIIF restent dépendantes du réseau s'il y a lieu. Par défaut la recherche reste exacte jusqu'à activation « Graphies médiévales » ; les équivalences sont désactivables. Le contenu d'annotations en popover n'est pas indexé. Le nombre de résultats est plafonné à 5 000 pour protéger le navigateur.

## Invariants

- Conserver l'association ordinale des `<lb edRef="#pivot"/>` aux lignes physiques du JSON pivot établie dans V0.8.5.25.3.
- Ne jamais inférer des `base_keys` à partir de voisinages d'images ou d'OCR.
- Ne pas modifier TEI, JSON, ALTO/PAGE ou images lors du rendu et de la recherche.
- Conserver les sept langues : fr, en, de, ja, cs, it, ru ; 629 messages par catalogue et aide HTML correspondante.
- Préserver les fonctionnalités antérieures, les projets historiques, les zones TEI de doubles pages, la compatibilité IIIF et les dispositions Qt.

## Tests et limites

- Suite Python complète, compilation `compileall`, syntaxe JS avec `node --check`, tests Node de recherche ; résultats exacts dans `TEST_REPORT_V0_8_5_26.txt`.
- Génération d'un `web_output/viewer.html` de démonstration depuis le projet T1/T2/P : index pivot 3 790/3 790, zéro clé textuelle orpheline.
- Essai Chromium **réussi sur un jeu synthétique minimal** : saisie `servvs` (recherche exacte : zéro occurrence), activation u/v (recherche médiévale : une occurrence à cheval sur deux fragments XML), deux surlignages actifs et sélection de la ligne pivot sans erreur JavaScript. Consulter `tests/manual_v08526_browser.py`.
- Limites : l'environnement ne dispose pas de PySide6 ; aucun essai graphique Windows/macOS/Linux natif. Le navigateur a refusé de naviguer vers les URL `file:` et `localhost` dans cet environnement. La tentative de chargement du HTML de démonstration de 5 Mo en une seule opération a échoué ; **aucune validation navigateur sur les documents réels ni sur le grand export de démonstration** n'est revendiquée.

## Essai utilisateur recommandé

1. Dans Varians, ouvrir F8 sur un document contenant une erreur RELAX NG ; corriger l'erreur et vérifier que l'entrée disparait du panneau après environ 1,25 seconde, sans F8 supplémentaire.
2. Dans `<rdg wi`, vérifier l'apparition de `wit`, puis l'insertion `wit=""` avec le curseur entre guillemets ; vérifier également `xml:` dans les éléments où `xml:id` est autorisé.
3. Régénérer le viewer HTML avec la présente distribution, rechercher `servos` dans une édition contenant `seruos`. Constater le contraste entre recherche exacte et mode médiéval u/v ; activer/désactiver séparément c/t et i/j ; choisir une occurrence éloignée et confirmer les cadrages correspondants dans Mu et ses témoins synchronisés.

L'ancienne roadmap historique est explicitement archivée. La nouvelle devra être rediscutée.
