# 06 — Procédures de maintenance, vérification et livraison

## 1. Identification et intégrité de la version

Avant toute modification, extraire `BASE_SOURCE/Varians_V0.8.5.26.2_Correctif_Validation_RELAX_NG_Complete.zip` dans un dossier **neuf**. L'archive de référence comporte **268 membres** et sa somme SHA-256 doit correspondre à `BASE_SOURCE/Varians_V0.8.5.26.2_SHA256.txt`. Vérifier également l'absence d'erreur CRC ZIP. Dans `editeur_tei.py`, `APP_VERSION` vaut `0.8.5.26.2`.

Ne pas réutiliser à la place un dossier Spyder contenant des anciens modules Python en mémoire. Une nouvelle fenêtre Varians peut continuer à charger un ancien `web_viewer/generator.py` depuis un chemin antérieur : contrôler le chemin du module réellement importé si les résultats diffèrent. Un viewer HTML antérieur **reste ancien même si l'application a été mise à jour** : régénérer l'export.

## 2. Dépendances

- Production : Python 3, `PySide6`, `lxml` (fichier `requirements.txt`).
- Développement : `pytest`, plus éventuellement Node.js et Chromium/Playwright pour les essais du viewer.
- Aucun composant Visual Studio/Windows n'est requis dans le cœur Python. Les lanceurs `.bat` ne sont que des aides.
- Pour macOS/Linux : vérifier Qt, fontes locales (notamment caractères japonais), fenêtres détachées, accès fichiers et comportement d'Always-on-top en environnement Wayland.

## 3. Contrôles automatisés

```bash
python -m pytest -q --disable-warnings --maxfail=1
python -m compileall -q .
python -m web_viewer.generator project.xml
```

**Observation indépendante de cette passation** : 479 tests réussis, 2 ignorés, zéro échec ; compilation Python sans erreur. Le rapport texte de l'exécution est joint à `VERIFICATION/pytest_independant.txt`. Les deux tests ignorés ne doivent pas être annoncés comme « réussis ». Une grande partie des contrôles UI Qt repose sur des substitutions, AST ou logique sans Qt ; **ne pas confondre les tests de logique avec un test graphique natif**.

Pour les tests Javascript, vérifier la disponibilité de Node (`node --version`) et utiliser les tests du répertoire `tests/`; certains scripts Playwright nécessitent une installation optionnelle. La sortie `web_output/viewer.html` incluse est une **démonstration**, pas les manuscrits de l'utilisateur.

## 4. Recettes manuelles minimales avant de livrer

| Famille | Action testée | Résultat attendu |
|---|---|---|
| Démarrage | ouvrir/fermer un projet, restaurer le dernier | pas de perte de ressource, pas d'ancien module |
| XML | texte mixte, paires imbriquées, autofermantes | source inchangée, surlignage conservateur |
| Complétion | attribut préfixé, valeur RNG, Ctrl+Espace | contexte exact, insertion sans doublon |
| RNG | F8, correction panneau ouvert puis masqué, annuler/refaire | aucune erreur périmée, nouvelle révision affichée |
| XPath | résultats, clic, passage replié | sélection à bon offset, dévoilement |
| Images | image locale/IIIF sans ALTO | consultation possible en mode pages |
| ALTO/PAGE | import OCR isolé et polygone concave | images préservées, sommets fidèles |
| Synchronisation | `base_keys` valides/absentes/orphelines | lignes correctes ou mode pages prudent |
| Double page | deux zones, fractionnement et `<pb>` | une image, zones stables, décision contrôlée |
| Disposition | vertical/horizontal/grille/détaché | mêmes panneaux et réglages |
| Viewer exporté | texte→lignes secondaires, pivot masqué | `data-line` valide, aucun panel fantôme |
| Recherche web | exact, u/v, i/j, c/t séparément | faux positifs maîtrisés, sélection lié au bon passage |
| Langues | changer à chaud fr/en/de/ja/cs/it/ru | libellés/aides corrects et projet conservé |
| Portabilité | déplacer un projet à chemins relatifs | références résolues, pas d'écriture implicite |

## 5. Cas spéciaux à couvrir

- `<lb/>` du pivot dans des notes, `pb/@n` différant de l'ID JSON, absence de `<pb/>`, double image et numéros physiques non consécutifs.
- JSON déclaré secondaire mais sans `base_keys`, même avec des milliers de boîtes ALTO.
- IIIF dont les images sélectionnées sont valides mais l'OCR ne se rapproche d'aucun Canvas ; le manifeste doit rester canonique.
- Bitmaps réduits à 490 px pour un Canvas de plusieurs milliers de pixels ; les cadres restent alignés.
- Deux fenêtres détachées sur plusieurs moniteurs et changement de langue ; topmost dépend de l'OS.
- Réseau indisponible, 403/404/429/500, servi partiel, bascule rapide de page pendant un téléchargement.
- Références `base_keys` orphelines après suppression éditoriale : diagnostiquer, **ne pas remailler les références automatiquement**.

## 6. Procédure recommandée pour toute évolution

1. Écrire en quelques lignes l'anomalie/priorité **explicitement approuvée** et son scénario de reproduction (ne pas reprendre une ancienne roadmap).
2. Faire un **diff contrôlé** depuis le ZIP de référence ; isoler les modules touchés et les contrats scientifiques affectés.
3. Ajouter des tests de caractérisation avant de transformer la logique ; pour le viewer, prévoir un cas synthétique qui échouait avec l'ancien code et passe avec le nouveau.
4. Préserver une archive originale intacte ; travailler dans un autre dossier.
5. Exécuter suite ciblée puis suite entière ; relever le nombre de tests, les ignorés, les résultats JS et les limites GUI.
6. Mettre à jour toutes les traductions et aides affectées, les fichiers de passation pertinents et le rapport de version.
7. Produire **une archive complète**, sans fichiers `__pycache__`/`.pytest_cache` temporaires, contrôler CRC, nombre de membres, présence des sources et documentation, SHA-256.
8. Donner un essai utilisateur ciblé, puis seulement considérer la nouvelle version stable une fois les retours reçus.

## 7. Règles d'écriture et sauvegarde

`save_io.py` prévoit une sauvegarde atomique et un fichier antérieur `.bak`. Des opérations de rafraîchissement, d'export ou de changement de disposition ne doivent pas modifier le contenu scientifique. Les migrations de `project.xml` doivent être explicites, conservatrices et, lorsqu'elles sont nécessaires, accompagnées de sauvegardes. Ne jamais supprimer automatiquement des images anciennement copiées simplement parce qu'un témoin est masqué dans le dernier export.

## 8. Limites actuelles à déclarer explicitement

- Le test de l'application PySide6 sur Windows/macOS/Linux n'a **pas** été exécuté par l'environnement ayant construit le ZIP de référence ; plusieurs vérifications Chromium synthétiques appartiennent à des étapes antérieures.
- Aucun package de manuscrits scientifiques réels Mu/F/A/N/L n'est inclus dans l'archive. Le test utilisateur a confirmé la reprise correcte du viewer, mais ne couvre pas toutes les zones, toutes les pages ou tous les serveurs.
- L'export web dépend de la qualité et de l'intégrité des données, et de la disponibilité/réglementation des services IIIF.
