# Version prête à l'emploi de Varians

Archives sans Python à installer, pour Windows (x64), macOS (Apple Silicon
et Intel) et Linux (x64), construites par PyInstaller. Ce qu'un utilisateur
lit dans l'archive : `readme/` (sept langues).

## Publier

Le workflow **Binaries** (`.github/workflows/binaries.yml`) construit les
quatre archives et les joint à la release **dès qu'elle est publiée**, avec
leur empreinte SHA-256 (`.sha256`). Rien d'autre à faire.

Pour une release déjà publiée (par exemple publiée avant l'existence du
workflow) : Actions ▸ Binaries ▸ **Run workflow**, choisir la branche ou le
tag à construire, et indiquer la release dans **tag** (`v0.9.4.0`). Le
workflow refuse de joindre des archives dont la version (`APP_VERSION`) n'est
pas celle du tag. Sans **tag**, les archives sont seulement téléchargeables
dans le résumé du workflow (pour un essai).

Le workflow tourne aussi, sans rien publier, quand `packaging/` ou le
workflow change.

## Ce qui est vérifié

`packaging/build.py`, sur chaque système :

1. construit avec PyInstaller (`varians.spec`) ;
2. place le dossier sous `Varians-<version>/`, avec le LISEZMOI ×7 et les
   textes des licences (`licences/`) ;
3. lance l'exécutable construit : `Varians --self-test rapport.json`
   (`self_test.py`) vérifie les traductions, l'aide, les ressources, crée un
   projet, lance le processus de validation RELAX NG et une transformation
   avec lxml puis avec Saxon, et ouvre le projet dans la fenêtre de Varians.
   Dans le workflow, la fenêtre s'ouvre avec le module d'affichage du
   système (windows, cocoa, xcb sous Xvfb) ;
4. refuse l'archive si une vérification échoue, si un lien symbolique est
   cassé ou si la vérification a laissé un fichier dans le dossier ;
5. zippe (liens symboliques et droits gardés ; `ditto` sous macOS) et
   écrit l'empreinte.

Le rapport de vérification est gardé dans le résumé du workflow
(`diagnostic-…`), même en cas d'échec.

## Construire sur sa machine

```
pip install -r requirements.txt -r packaging/requirements.txt
python packaging/build.py            # archive dans build/binaries/
```

Sans écran, la vérification utilise `QT_QPA_PLATFORM=offscreen` ; sous
Linux, `QT_QPA_PLATFORM=xcb xvfb-run -a python packaging/build.py` vérifie
aussi l'affichage X11. Sous Linux, installer d'abord les bibliothèques xcb
listées dans le workflow : celles qui sont présentes à la construction sont
emportées dans l'archive.

## Points à connaître

- **Non signé.** Windows (SmartScreen) et macOS (Gatekeeper) avertissent au
  premier lancement ; le LISEZMOI explique comment passer. Signer
  demanderait un certificat Windows et un compte développeur Apple.
- **Données.** Varians lit ses fichiers de données à côté de ses modules
  (`Path(__file__).parent`) : la recette les place dans `_internal/` sous le
  même nom (`DATA_FOLDERS`). Un nouveau dossier de données doit y être
  ajouté ; `tests/test_packaging.py` le vérifie.
- **Processus.** Validation et transformations relancent l'exécutable
  (`--relaxng-worker`, `--transform-worker`). Le crochet d'exécution de
  PySide6 y charge QtCore (environ 0,1 s), jamais l'interface.
- **Greffons Qt retirés** (`UNUSED_QT`, `UNUSED_LINUX`) : clavier virtuel
  (QML), images PDF, plateformes embarquées, thème et pile GTK.
- **Certificats HTTPS** : `rthook_certificates.py` utilise ceux de certifi
  quand ceux du système manquent (macOS, Linux hors Debian/Ubuntu).
- **Linux** : construit sur Ubuntu 22.04, l'archive demande glibc 2.35 ou
  plus récent (Ubuntu 22.04, Debian 12, Fedora 36…).
- **Saxon HE** (saxonche) fait à lui seul près de 100 Mo décompressé.
- **Icône** : `resources/icons/varians.png`, le logo sur un carré blanc arrondi
  (lisible sur une barre des tâches sombre), produite par `make_icon.py` à
  partir de `resources/varians_logo.png`. C'est l'icône de l'exécutable et du
  paquet `.app` (`ICON` dans la recette) et celle des fenêtres
  (`app_context.apply_application_icon`, appelée par `main()`).
