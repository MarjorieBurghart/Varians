# Scénarios de transformation XSLT (V0.9.2.0) et feuilles éditées dans Varians (V0.9.2.1)

Un scénario applique une feuille XSLT à l'édition, au document affiché ou à
un fichier, et écrit le résultat dans un fichier. Les scénarios sont
nommés, enregistrés dans le projet (`<transformations>`, voir
`PROJECT_MANAGEMENT.md`) et se rejouent à l'identique. Le viewer web natif
reste une voie de publication distincte : un scénario ne le modifie pas.
Les règles de la Vue XSLT / CSS (`XSLT_POLICY.md`) ne changent pas.

## Modules

| Module | Rôle |
|---|---|
| `xslt_scenarios.py` | chemins d'un scénario, source, problèmes, garde-fous, requête d'exécution, scénarios prédéfinis ; sans Qt |
| `xslt_engines.py` | `run(request)` : moteurs lxml (XSLT 1.0) et Saxon (XSLT 3.0), même contrat ; `TransformResult` ; sans Qt |
| `transform_worker.py` | processus d'une exécution (Varians relancé avec `--transform-worker`) ; sans Qt |
| `transform_runner.py` | client Qt de ce processus (`TransformRunner` : `start`, `cancel`, `finished`) |
| `transform_ui.py` | liste et boîte d'un scénario, bouton « Transformer ▾ », exécution, compte rendu, « Ouvrir la feuille » (mixin de `MainWindow`) |
| `xslt_check_ui.py` | vérification de la feuille affichée « comme le RNG » (V0.9.2.1, mixin de `MainWindow`) |
| `xslt_completion.py` | complétion d'une feuille XSLT d'après le schéma XSLT 3.0 livré (V0.9.2.1) ; sans Qt |

## Chemins et sources

Les chemins d'un scénario (`xslt`, `css`, `output`, `file`) sont gardés tels
qu'ils sont écrits : relatifs au projet, absolus, ou `${varians}/…` pour les
feuilles fournies avec Varians (dossier `rendering` de l'application).
`stylesheet_path` est la seule fonction qui trouve la feuille d'un
scénario : une bibliothèque installée hors du projet (les TEI Stylesheets,
version suivante) s'y ajoutera. `scenario_path` écrit le chemin d'un fichier
choisi (relatif au projet, sinon `${varians}/…`, sinon absolu).

Sources (`scenario_source`) :

- `edition` : l'édition du projet, assemblée par XInclude
  (`xml_assembly.assemble`, fichiers enregistrés). Chaque partie garde son
  URI de base (`xml:base`) : un `document()` relatif à un nœud d'une partie
  est résolu depuis son fichier ;
- `current` : le fichier du document affiché, lu tel quel ; l'édition,
  assemblée, si c'est elle ;
- `file` : un fichier, lu tel quel (ses `xi:include` ne sont pas résolus).

## Garde-fous

`scenario_problems` relève ce qui empêche un scénario de s'exécuter
(`PROBLEM_CODES`, messages `transform.problem.<code>`). Le résultat, ou la
copie de la CSS à côté de lui, ne remplace jamais une source du projet
(`project_sources` : `project.xml`, l'édition et ses parties enregistrées,
les documents et leurs schémas, la feuille, la CSS et les éléments
personnalisés de l'aperçu, le schéma, les JSON d'alignement) ni une source du
scénario. La boîte d'un scénario refuse ces cas ; le moteur vérifie encore
chaque écriture (`request["protected"]`).

## Requête et compte rendu

`scenario_request` prépare un dictionnaire sérialisable en JSON : `name`,
`engine`, `source`, `assemble`, `xslt`, `css`, `output`, `params` (paires
de chaînes ; `css`, le nom de la CSS, est ajouté sauf si le scénario le
fixe), `protected`. L'aperçu remplace le dossier du résultat par un dossier
temporaire de la session (`output_dir`).

`xslt_engines.run` rend un `TransformResult` : `ok`, `outputs` (le résultat
d'abord), `journal` (`[code, détail]`, `JOURNAL_CODES` : `message`,
`warning`, `network_read`, `css_copied`, `write_refused`, `assembly`),
`error_code` (`ERROR_CODES`) et `error` (« fichier:ligne: message »),
`engine`, `version`, `seconds`.

## Moteurs

Contrat commun :

- **entrée** lue avec son URI de base ; entités externes non résolues ;
- **paramètres** : des chaînes (`XSLT.strparam`, `make_string_value`) ;
- **lecture** : tout fichier local, et `http`/`https` ;
- **écriture** : le résultat n'est écrit que si la transformation réussit,
  de façon atomique (fichier temporaire, puis remplacement) : un échec
  laisse le précédent intact. Puis la CSS est copiée à côté de lui.

**lxml (XSLT 1.0).** `XSLTAccessControl(read_file=True, read_network=True,
write_file=False, create_dir=False, write_network=False)`. Les URL
`http(s)` passent par un résolveur de Varians (`urllib`, délai de 30 s),
noté au journal (`network_read`) ; un échec arrête l'exécution
(`network_failed`). `exsl:document` est refusé (`write_refused`). Les
`xsl:message` (entrées du journal lxml sans fichier ni ligne) vont au
journal, y compris ceux qui précèdent une erreur.

**Saxon-HE (XSLT 3.0, paquet `saxonche`).** Installé avec Varians
(`requirements.txt`, `installer_dependances.bat`) ; sans lui, un scénario
Saxon est signalé (`saxon_missing`). Un seul processeur par processus. Les
entités externes, les entités paramètres et la DTD externe ne sont pas lues
(propriétés `parserFeature` du processeur). Saxon lit lui-même le réseau :
ses lectures ne sont pas notées au journal. Il écrit ses erreurs, avec leur
lieu, sur la sortie d'erreur du processus, et non dans le message de son
exception : le processus de transformation reçoit donc, dès sa création, un
fichier pour sortie d'erreur, nommé dans la requête (`stderr_log`), où
Varians lit ce qui a été écrit pendant l'exécution pour former
« fichier:ligne: CODE message ». Détourner la sortie d'erreur une fois le
processus lancé ne suffit pas sous Windows. Sans ce fichier (exécution dans
Varians même), l'erreur garde le message de Saxon, sans son lieu.

Fichiers supplémentaires (`xsl:result-document`) : Saxon peut les garder en
mémoire (`set_capture_result_documents`), mais sans leur mise en forme
d'écriture (méthode, doctype, encodage). D'où deux passages :

1. les fichiers sont gardés en mémoire, pour connaître leurs chemins,
   résolus depuis le résultat ; rien n'est écrit dans le dossier du
   résultat ;
2. s'ils sont tous dans le dossier du résultat (ou ses sous-dossiers),
   Saxon les écrit lui-même, avec leur mise en forme exacte, dans un dossier
   temporaire, puis Varians les range ; sinon l'exécution est refusée
   (`write_refused`) et rien n'est écrit.

Le second passage n'a lieu que si la feuille produit d'autres fichiers, avec
une feuille compilée à nouveau : SaxonC plante si l'on réutilise celle du
premier passage.

## Processus

Chaque exécution a son processus (`transform_worker`) : Varians reste
réactif, « Annuler » tue le processus (`cancelled`), et un plantage de
Saxon ou une boucle sans fin n'emporte pas Varians. La commande
(`transform_worker.worker_command`) est valable depuis les sources comme dans
une version autonome. Sa sortie d'erreur est un fichier temporaire
(`new_stderr_log`), passé par `TransformRunner` (QProcess) ou, sans Qt, par
`transform_worker.run_in_process`, qu'emploient les tests de Saxon. Saxon garde le verrou de
Python pendant une transformation : dans un même processus, un serveur http
en Python ne pourrait pas lui répondre (les tests lancent le leur à part).

Une version autonome (PyInstaller, Nuitka) devra embarquer `saxonche`.

## Interface

- Fichier ▸ « Scénarios de transformation… » : scénarios du projet
  (enregistrés à chaque changement par `update_project_transformations`)
  et scénarios prédéfinis (`predefined_scenarios` : « Édition HTML »,
  `${varians}/tei-to-html.xsl` et `${varians}/tei.css`, avec le titre du
  sommaire de l'aperçu dans la langue de l'interface, paramètre
  `tocTitle`), que « Dupliquer… » copie dans le projet ; « Aperçu »,
  « Exécuter ».
- Bouton « Transformer ▾ » : dernier scénario lancé dans le projet (réglage
  local `transformLastScenario`, Ctrl+Shift+T), liste des scénarios.
- Avant l'exécution (`_save_for_transform`) : l'édition, ses parties
  modifiées et le fragment non appliqué (`_save_edition_for_export`), puis
  le document source, la feuille et la CSS s'ils sont ouverts et modifiés.
- « Transformation en cours… » avec Annuler au-delà d'une demi-seconde ;
  compte rendu avec « Ouvrir » et le journal en détail ; l'aperçu s'ouvre
  aussitôt.

La feuille de Varians (`rendering/tei-to-html.xsl`) reçoit le paramètre
`css` (`tei.css` par défaut) pour son `<link>` : l'aperçu est inchangé.

## Feuilles éditées dans Varians (V0.9.2.1)

Une feuille XSLT est un document du projet comme un autre (`<documents>`,
voir `PROJECT_MANAGEMENT.md`) : le format de `project.xml` ne change pas.
`xslt_scenarios.stylesheet_info` la reconnaît à sa racine (`stylesheet`,
`transform` ou `package` de l'espace de noms XSLT, ou élément résultat
littéral portant `xsl:version`) et donne le préfixe XSLT et la version ;
si la racine est illisible, l'extension `.xsl`/`.xslt` suffit.

**Ajout.** `document_dialogs` copie une feuille venue d'ailleurs dans le
dossier `xslt/` du projet (créé par `create_portable_project`, ou à la
première copie), jamais par-dessus un fichier (`free_path`) ; « Nouvelle
feuille XSLT… » écrit une feuille minimale 1.0 ou 3.0
(`new_stylesheet_text`). « Ouvrir la feuille » (`transform_ui`) inscrit au
besoin la feuille d'un scénario du projet et l'affiche ; une feuille de
Varians (`${varians}/…`) est d'abord copiée dans `xslt/`, une feuille hors
du projet peut l'être (ou s'ouvrir sur place), et le scénario emploie la
copie (`update_project_transformations`). Les fichiers annexes (feuilles
importées, images, CSS, JS) ne sont pas copiés : l'utilisateur les place
lui-même dans `xslt/`.

**Vérification.** `xslt_engines.check(request)`, requête `op: "check"` du
processus de transformation : la feuille est compilée sans être exécutée,
depuis le texte de l'éditeur (`text`, même non enregistré) lu avec l'URI de
base de son fichier, sinon depuis le fichier. Le compte rendu
(`TransformResult.issues`) donne toutes les erreurs et tous les
avertissements, `[fichier, ligne, niveau, message]` :

- lxml : le journal de libxslt situe chaque erreur par une entrée « compilation
  error, element 'x' » (fichier, ligne), suivie des entrées sans lieu qui la
  décrivent ; le journal est vidé avant chaque compilation. Après une
  compilation réussie, ce ne sont que des avertissements ;
- Saxon : la feuille est lue par un `DocumentBuilder` (URI de base, numéros
  de ligne), compilée par `compile_stylesheet(stylesheet_node=…)` ; les
  erreurs, avec leur lieu, sont lues sur la sortie d'erreur du processus
  (Windows) et dans le message de l'exception, sans doublon ;
- une feuille qui n'est pas un XML bien formé a le code `xslt_malformed`.

Le moteur (`xslt_scenarios.check_engines`) : celui des scénarios du projet qui
emploient la feuille, chacun une fois ; sinon d'après `@version` (`1.0` :
lxml, une autre : Saxon).

`xslt_check_ui` branche cette vérification sur les déclencheurs de la
validation RELAX NG (`_validate_relaxng_document_impl`) : premier affichage,
F8 (« Vérifier la feuille XSLT »), frappe une fois F8 utilisé, enregistrement
(« Enregistrer quand même ? » s'il y a des erreurs). Chaque moteur tourne dans
son processus (`TransformRunner`) ; F8 et l'enregistrement attendent la
réponse (`CHECK_TIMEOUT_MSEC`), la vérification automatique non. Le résultat
devient un `ValidationResult` (`check_validation_result`), rangé comme celui
d'une validation RNG (`last_rng_result`, avec le jeton `("xslt", moteurs…)`) :
panneau de validation (colonne Document pour une erreur dans une feuille
importée ; double-clic vers cette feuille si elle est au projet), barre
d'état, couleur de l'onglet (`rng_invalid`, `malformed`).

**Complétion.** `xslt_completion` lit le schéma XSLT 3.0 du W3C livré dans
`resources/schemas/xslt30` (voir son `LISEZMOI.md` : origine, licence BSD,
conversion) avec le moteur de `rng_completion`, qui ne connaît pas les espaces
de noms : les noms proposés reçoivent le préfixe de la feuille ; un élément
d'un autre espace de noms (reconnu à son préfixe) est un élément résultat
littéral, qui reçoit les instructions (le contenu de `xsl:if`) et les
attributs `xsl:*` (`LITERAL_RESULT_ATTRIBUTES`) ; une feuille `version="1.0"`
ne reçoit que les éléments et attributs d'XSLT 1.0 (`XSLT10_ATTRIBUTES`) ; les
attributs « fantômes » d'XSLT 3.0 (`_match`…) sont écartés.
`StylesheetCompletionModel` offre l'interface du modèle RNG à `completion_ui`
(Ctrl+Espace, liste automatique des attributs, Ctrl+E), sans les éléments
personnalisés du projet.

## Limites

- XSLT 1.0 (lxml) : un seul fichier de résultat.
- Avec Saxon, les lectures réseau ne sont pas notées au journal.
- Sources « Fichier » et « Document affiché » (autre que l'édition) : lues
  telles quelles, sans résoudre leurs `xi:include`.
- La Vue XSLT / CSS garde son fonctionnement : un `document()` relatif pris
  dans le texte de l'édition n'y trouve pas ses fichiers (pas d'URI de base).
- Feuilles (V0.9.2.1) : une feuille faite pour être importée ou incluse est
  vérifiée seule (ses renvois à la feuille principale peuvent être signalés) ;
  une feuille 2.0 reçoit les propositions d'XSLT 3.0 ; les valeurs finies
  d'attributs sont celles d'XSLT 3.0 ; ni les noms déclarés dans la feuille
  (modèles, modes, clés) ni l'XPath ne sont complétés ; une feuille qui déclare
  un `xml-model` est vérifiée par compilation, non par ce schéma.

## Tests

`tests/test_transformations_format.py`, `tests/test_xslt_scenarios.py`,
`tests/test_xslt_engine_lxml.py`, `tests/test_xslt_engine_saxon.py`
(ignorés sans Saxon, sauf le message « Saxon n'est pas installé »),
`tests/test_transform_worker.py`, `tests/gui/test_gui_transform_runner.py`,
`tests/gui/test_gui_transform_scenarios.py`,
`tests/gui/test_gui_transform_run.py` ; feuilles (V0.9.2.1) :
`tests/test_document_files.py`, `tests/test_xslt_check.py`,
`tests/test_xslt_completion.py`, `tests/gui/test_gui_document_dialogs.py`,
`tests/gui/test_gui_xslt_check.py`, `tests/gui/test_gui_xslt_completion.py`.
