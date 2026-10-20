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

## Organisation du code de l'interface

`editeur_tei.py` lance l'application (`main()`), définit la fenêtre
d'accueil et la fenêtre principale `MainWindow`. Celle-ci est composée de
*mixins*, un par responsabilité, dont elle hérite :

| Module | Rôle |
|---|---|
| `document_io.py` | ouvrir, enregistrer, fermer le document XML |
| `validation_panel.py` | panneau et validation RELAX NG, résolution du schéma |
| `completion_ui.py` | complétion Ctrl+Espace guidée par le schéma |
| `xpath_panel.py` | recherche XPath |
| `witness_workspace.py` | disposition des panneaux de témoins |
| `witness_sync.py` | synchronisation XML ↔ témoins, folios, ressources |
| `main_menus.py` | barre d'outils, menus, projets récents, langue |
| `project_actions.py` | export web, ouverture/création/réglages de projet |
| `document_tabs.py` | documents du projet affichés : édition et documents auxiliaires |
| `document_dialogs.py` | ajouter, créer, retirer un document XML auxiliaire |

Composants autonomes utilisés par la fenêtre :

| Module | Rôle |
|---|---|
| `document_session.py` | état d'un document ouvert (`DocumentSession`, `LbIndex`) |
| `code_editor.py` | éditeur de la source XML (`CodeEditor`) |
| `formatted_view.py` | aperçu XSLT/CSS et édition par fragments |
| `manuscript_panel.py` | panneau d'un témoin manuscrit |
| `image_fetch.py` | téléchargement des images, cache disque |
| `help_dialogs.py` | aide, dictionnaire latin, « À propos » |
| `app_context.py` | traductions actives, réglages, projets récents, version |

Les modules de l'interface n'importent jamais `editeur_tei` (il peut être
exécuté comme script) : les services communs passent par `app_context`.
Tout nouveau module local importé par `editeur_tei.py` doit figurer dans
`_LOCAL_MODULE_NAMES` (un test le vérifie).

Un nouveau message de l'interface s'ajoute, traduit, aux sept catalogues
`i18n/*.xml` ; `CATALOG_SIZE` dans `tests/varians_source.py` donne le
nombre de messages attendu dans chacun.

## Transformations XSLT de l'aperçu

`formatted_view.transform_with_xslt` emploie lxml (XSLT 1.0). Une feuille
peut lire des fichiers locaux (`document()`, `xsl:import`), mais ne peut ni
écrire de fichier (`exsl:document`), ni créer de dossier, ni accéder au
réseau. Une erreur de la feuille est signalée telle quelle, au format
`fichier:ligne: message`. Le moteur .NET via PowerShell ne sert de secours
que si lxml n'est pas installé.

## Historique et versions

Depuis V0.8.6.0, l'historique est porté par Git. Les rapports de test et
addenda de passation produits version par version, ainsi que le manifeste
SHA-256, ne sont plus générés ; les anciens sont archivés dans
`docs/historique/`. Le dossier de passation majeure de V0.8.5.26.2 se
trouve dans `docs/passation_V0.8.5.26.2/` : ses invariants scientifiques
restent la référence.

La version affichée par l'application est `APP_VERSION` dans
`app_context.py`. Pour une nouvelle version : modifier `APP_VERSION`,
`CURRENT_VERSION` dans `tests/varians_source.py`, l'en-tête de
`editeur_tei.py`, ajouter une section en tête de `README.txt` et une section
`<section id="vXYZ">` dans chacune des sept aides (`help/*.html`) ;
`tests/test_version.py` vérifie l'ensemble.

## Défauts connus

Aucun défaut hérité de V0.8.5.26.2 n'est actuellement connu. Corrigés en
V0.8.6.0 :

- la lenteur à la frappe d'une balise ouvrante dans un long document
  (recherche de la balise fermante de coût quadratique dans
  `xml_tag_pairs`) — voir `tests/test_xml_tag_pairs_performance.py` ;
- l'index des `<lb/>` momentanément périmé lorsqu'on modifiait l'intérieur
  d'une balise sans saisir `<` ni `>` (ex. `edRef="#T"` → `"#T1"`) — voir
  `tests/test_document_session.py` ;
- l'erreur `Signal source has been deleted` affichée si une fenêtre était
  fermée pendant un téléchargement d'image — voir
  `tests/gui/test_gui_image_fetch.py` ;
- les erreurs affichées si une fenêtre était détruite peu après
  l'ouverture d'un document (appels différés) — voir
  `tests/gui/test_gui_delayed_calls.py`. Pour programmer un appel différé
  visant une fenêtre ou un widget, utiliser `app_context.call_later`.
