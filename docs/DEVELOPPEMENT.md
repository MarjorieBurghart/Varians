# Développer Varians

## Installation

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate    —    Linux/macOS : source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python editeur_tei.py                    # ou : python editeur_tei.py chemin/vers/project.xml
```

`requirements.txt` contient les dépendances d'exécution (PySide6, lxml) ;
`requirements-dev.txt` y ajoute les outils de test (pytest, pytest-qt).

## Tests

Depuis la racine du dépôt :

```bash
python -m pytest -q
```

- `tests/test_*.py` : tests historiques (jusqu'à V0.8.5.26.2). Beaucoup
  s'exécutent sans Qt.
- `tests/gui/` : tests qui pilotent la **vraie** fenêtre Qt, sans écran.
  Ils fixent le comportement observable (ouvrir, modifier, enregistrer,
  valider, XPath, synchronisation des témoins, aperçu, parcours « une image,
  une transcription ») et servent de filet de sécurité pour les
  restructurations. Leur infrastructure (`tests/gui/conftest.py`) isole les
  réglages QSettings, coupe le réseau et impose que chaque boîte de dialogue
  soit prévue par le test.

Sous Linux sans écran, définir `QT_QPA_PLATFORM=offscreen` (fait
automatiquement par `tests/gui/conftest.py`). PySide6 requiert alors
quelques bibliothèques système (`libegl1`, `libxkbcommon0`,
`libfontconfig1`, `libdbus-1-3`).

Ces tests ne remplacent pas une vérification à l'écran : l'affichage
réel sous Windows, macOS ou Linux reste à contrôler à la main avant une
livraison.

## Tests automatiques sur GitHub

`.github/workflows/tests.yml` lance la suite complète sous Ubuntu et
Windows à chaque envoi et pull request. Les résultats sont visibles dans
l'onglet *Actions* du dépôt.

## Historique et versions

Depuis V0.8.6.0, l'historique est porté par Git. Les rapports de test et
addenda de passation produits version par version, ainsi que le manifeste
SHA-256, ne sont plus générés ; les anciens sont archivés dans
`docs/historique/`. Le dossier de passation majeure de V0.8.5.26.2 se
trouve dans `docs/passation_V0.8.5.26.2/` : ses invariants scientifiques
restent la référence.

La version affichée par l'application est `APP_VERSION` dans
`app_context.py`.

## Défauts connus (hérités de V0.8.5.26.2, correction prévue)

1. **Lenteur à la frappe d'une balise ouvrante dans un long document.**
   Pendant la saisie d'une balise ouvrante non encore fermée, la recherche
   de la balise fermante correspondante (`xml_tag_pairs.matching_closing_tag`,
   pour le renommage simultané des paires) parcourt la suite du document et,
   pour chaque balise rencontrée, recherche en arrière jusqu'au début du
   texte d'éventuels commentaires ou sections CDATA. Coût quadratique : sur
   le projet exemple (≈ 530 000 caractères), plusieurs dizaines de secondes
   par frappe sur une machine lente.
2. **Index des `<lb/>` momentanément périmé** lorsqu'on modifie l'intérieur
   d'une balise sans saisir `<` ni `>` (ex. `edRef="#T"` → `"#T1"`), jusqu'au
   contrôle XML automatique suivant (voir `tests/test_document_session.py`).
3. **Erreur dans la console** (`Signal source has been deleted`) si une
   fenêtre est fermée pendant un téléchargement d'image.
4. **Erreur dans la console** si une fenêtre est fermée moins de 120 ms
   après l'ouverture d'un document (validation différée de `open_path`).
