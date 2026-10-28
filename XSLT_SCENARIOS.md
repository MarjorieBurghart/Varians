# Scénarios de transformation XSLT (V0.9.2.0), feuilles éditées dans Varians (V0.9.2.1) et TEI Stylesheets (V0.9.2.2)

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
| `tei_stylesheets.py` | bibliothèque des TEI Stylesheets : versions, installation sûre, archive livrée, dernière version, téléchargement (V0.9.2.2) ; sans Qt |
| `tei_stylesheets_ui.py` | fenêtre « TEI Stylesheets… », vérification au lancement, installation avec accord (V0.9.2.2) |

## Chemins et sources

Les chemins d'un scénario (`xslt`, `css`, `output`, `file`) sont gardés tels
qu'ils sont écrits : relatifs au projet, absolus, `${varians}/…` pour les
feuilles fournies avec Varians (dossier `rendering` de l'application), ou
`${tei}/…` pour un fichier de la version active des TEI Stylesheets
(V0.9.2.2, voir plus bas). `stylesheet_path` est la seule fonction qui trouve
la feuille d'un scénario. `scenario_path` écrit le chemin d'un fichier
choisi (relatif au projet, sinon `${varians}/…`, sinon `${tei}/…` pour un
fichier d'une version installée, sinon absolu).

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
fixe), `protected`, et pour Saxon `catalogs` et `library` (V0.9.2.2, voir
« TEI Stylesheets »). L'aperçu remplace le dossier du résultat par un dossier
temporaire de la session (`output_dir`).

`xslt_engines.run` rend un `TransformResult` : `ok`, `outputs` (le résultat
d'abord), `journal` (`[code, détail]`, `JOURNAL_CODES` : `library`,
`message`, `warning`, `network_read`, `css_copied`, `write_refused`,
`assembly`),
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
  `tocTitle`), puis les quatre scénarios « TEI : … » (V0.9.2.2), que
  « Dupliquer… » copie dans le projet ; « Aperçu », « Exécuter » ; bouton
  « TEI Stylesheets… ».
- Bouton « Transformer ▾ » : dernier scénario lancé dans le projet (réglage
  local `transformLastScenario`, Ctrl+Shift+T), liste des scénarios.
- Avant l'exécution (`_save_for_transform`) : l'édition, ses parties
  modifiées et le fragment non appliqué (`_save_edition_for_export`), puis
  le document source, la feuille et la CSS s'ils sont ouverts et modifiés.
- « Transformation en cours… » avec Annuler au-delà d'une demi-seconde ;
  compte rendu avec « Ouvrir », « Ouvrir le dossier » (V0.9.2.2) et le
  journal en détail ; l'aperçu s'ouvre aussitôt.

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

## TEI Stylesheets (V0.9.2.2)

Les feuilles XSLT 3.0 du TEI Consortium (github.com/TEIC/Stylesheets)
servent aux scénarios prédéfinis « TEI : … ».

- **Bibliothèque** (`tei_stylesheets`) : une version par dossier,
  `<bibliothèque>/7.61.0/`, dans le dossier de données de l'utilisateur
  (`library_dir` : `%LOCALAPPDATA%\Varians\tei-stylesheets`, sinon
  `$XDG_DATA_HOME` ou `~/.local/share` `/varians/tei-stylesheets` ;
  `VARIANS_TEI_STYLESHEETS` le remplace, notamment pour les tests). Seuls
  `xml/tei/stylesheet/` (à la racine du dossier de la version) et
  `doc/tei-xsl/LICENCE` (`LICENCE`) sont extraits d'une archive du TEI-C.
  La version active (`active`) est la plus récente installée complètement :
  son témoin `.varians-installed` (version, origine, date) est écrit en
  dernier.
- **Archive livrée** : `resources/tei-stylesheets/tei-xsl-7.61.0.zip`
  (feuilles et licence seules ; origine, licence et façon de la refaire dans
  son `LISEZMOI.md`), installée au premier usage (`ensure_installed`,
  appelée par `xslt_scenarios.tei_library`), ou si elle est plus récente
  que la version installée.
- **Installation sûre** (`install_zip`) : chemin absolu, `..`, `:`, `\` ou
  lien refusent l'archive entière ; nombre de fichiers et taille plafonnés ;
  extraction dans un dossier temporaire voisin (`.tmp-…`), contrôle de
  `VERSION`, `catalog.xml`, `profiles/default/html/to.xsl` et `LICENCE`,
  témoin, puis renommage. Une archive refusée ne change rien. Les anciennes
  versions, les versions incomplètes et les dossiers `.tmp-…` sont supprimés
  au lancement suivant (`remove_old_versions`).
- **Scénarios prédéfinis** (`TEI_SCENARIOS`) : « TEI : HTML », « TEI :
  texte », « TEI : Markdown », « TEI : LaTeX », et depuis la V0.9.2.7
  « TEI : HTML en plusieurs fichiers », « TEI : DOCX (Word) », « TEI : ODT
  (LibreOffice) », « TEI : EPUB » (voir plus bas), Saxon, source `edition`,
  feuille `${tei}/profiles/default/<format>/to.xsl`, résultat dans
  `publications/tei/` : un dossier à part, pour que `tei.css` ne
  remplace pas la CSS de l'édition HTML de Varians. Dans la liste, ils
  forment le sous-groupe dépliable « TEI Stylesheets » (`transform_ui`,
  `is_tei_scenario`, clé `(groupe, rang)` de chaque ligne), et un sous-menu
  du bouton Transformer. Le HTML copie
  `${tei}/tei.css` et reçoit `cssFile=tei.css`, `cssPrintFile=` (vide) et
  `homeURL=` (vide) : aucun lien vers tei-c.org ni vers « / ». Les quatre
  reçoivent `lang` et `documentationLanguage`, la langue de l'interface
  (textes ajoutés par les feuilles, « Table des matières »…).
- **Problème** `tei_missing` : un scénario qui emploie `${tei}/` alors
  qu'aucune version n'est installée (ni installable depuis l'archive
  livrée) ; le détail est le dossier de la bibliothèque.
- **Catalogue** : la requête d'un scénario Saxon (`scenario_request`) et
  celle d'une vérification (`check_request`) portent `catalogs`, le
  `catalog.xml` de la version active. `xslt_engines._saxon_catalogs` le
  donne à Saxon (`set_catalog_files`) avant la compilation : il renvoie
  l'adresse officielle `http://www.tei-c.org/release/xml/tei/stylesheet/`
  (`tei_stylesheets.OFFICIAL_URI`) vers les fichiers installés. Saxon garde
  le catalogue reçu ; chaque exécution a son propre processus.
- **Journal** : `library` (« Bibliothèque : TEI Stylesheets 7.61.0 ») si la
  feuille est une des TEI Stylesheets ou si son texte contient l'adresse
  officielle (`request["library"]`).
- **Feuille de personnalisation** : « Ouvrir la feuille » d'un scénario du
  projet dont la feuille commence par `${tei}/` crée, après accord,
  `xslt/<customization_name>` (`tei-html.xsl`…, sans remplacer un fichier)
  avec `customization_text` : un commentaire dans la langue de l'interface
  (coupé selon la largeur affichée), deux exemples, et un `xsl:import` de
  l'adresse officielle ; pour une sortie HTML, l'espace de noms par défaut
  est celui du XHTML. Le scénario l'emploie ensuite.
- **Mises à jour** (`tei_stylesheets_ui`) : `at_launch` (appelée par
  `editeur_tei.main`, 1,5 s après l'affichage de la fenêtre) supprime les
  anciennes versions, puis, si le réglage `teiStylesheets/lastCheck` date
  d'au moins 30 jours, lance `check_for_update` : `latest_version` (fichier
  `VERSION` de la branche `released` du dépôt, délai 15 s) dans un fil à
  part ; silence sans nouveauté ni réseau. Une nouvelle version est proposée
  (Installer / Plus tard) ; `install` télécharge l'archive publiée
  (`RELEASE_URL`) dans un dossier `.tmp-…` de la bibliothèque, avec
  progression et Annuler, l'installe (`install_zip`), puis l'efface. La
  fenêtre « TEI Stylesheets… » (Fichier, et bouton de la liste des
  scénarios) montre la version, l'origine, le dossier, la licence et la
  dernière vérification ; « Rechercher une mise à jour » vérifie aussitôt
  et dit aussi « à jour » ou l'erreur.

## Formats en plusieurs fichiers, pré-passage, édition critique (V0.9.2.7)

- **Paramètres** : Saxon les reçoit sans type (`make_atomic_value("untypedAtomic", …)`),
  comme sa ligne de commande ; lxml, des chaînes. `xslt_scenarios.substitute`
  remplace `${pivot}` (`ProjectConfig.base_witness`) et `${tei}/` (adresse
  `file:` de la bibliothèque) dans leurs valeurs.
- **Format du résultat** (`TransformScenario.package`, attribut `package`) :
  `pages`, `docx`, `odt`, `epub` (`xslt_packages`), Saxon seulement (sinon,
  problème `package_invalid`). `pages` : `STDOUT=false`, `splitLevel=0` par
  défaut ; le résultat principal prend un autre nom (`.varians-principal…`)
  pour ne pas gêner `index.html`, qui devient le résultat ; les autres pages
  suivent les règles habituelles (dossier du résultat, fichiers protégés).
  Archives : un dossier de travail temporaire, dont l'adresse va au paramètre
  `word-directory`, `outputDir` ou `directory` ; `prepare` y déballe le
  modèle des TEI Stylesheets (`package_template`), retire ce que retirent les
  tâches ant, passe `fixstyle.xsl` (`package_fixstyle`) sur les styles du
  DOCX ; `copy_images` copie les images locales (`resource{N}.{ext}`) et
  écrit `image-size-info.xml` (dimensions lues dans l'en-tête PNG, GIF,
  JPEG ; journal `image_skipped` pour une image distante ou absente). La
  feuille n'écrit que dans ce dossier (sinon `write_refused`) ; `finish`
  place le résultat principal (`word/document.xml`, `content.xml`), renomme
  `docProps/new*.xml`, puis fait l'archive (`mimetype` en tête et non
  compressé, sans les fichiers de travail), écrite par `_write_outputs`.
- **Pré-passage** (`TransformScenario.prepare`, attribut `prepare`) : une
  feuille TEI → TEI appliquée par Saxon à la source avant la feuille du
  scénario, avec les mêmes paramètres ; son résultat est relu avec l'URI de
  base de la source. Sans Saxon : problème `prepare_invalid` ; feuille
  absente : `xslt_missing`. Elle est protégée comme une source.
- **DOCX et ODT** : pré-passage `${varians}/apparat-en-notes.xsl`,
  `temoin-de-base=${pivot}` : chaque `<app>` devient sa leçon retenue suivie
  de `<note place="foot" type="apparatus">` ; note de l'éditeur sans
  `@place` → `place="end"` ; `<pb>` du témoin → `<seg type="folio">⟨n⟩</seg>`,
  les autres supprimés ; `<lb>` → espaces (un groupe de `<lb>` contigus est
  une seule coupure) ; l'espace entre deux éléments va dans un `<seg>`, que
  les TEI Stylesheets gardent dans Word ; l'appel d'une note suit son mot.
- **EPUB** : `cssFile=${tei}/tei.css`, `cssPrintFile=${tei}/epub-print.css`
  (sinon lues sur tei-c.org, que le catalogue ne renvoie pas : https).
- **HTML en plusieurs fichiers** : `splitLevel=1` dans le scénario (une page
  par pièce d'un recueil réuni dans une seule division) ; selon les TEI
  Stylesheets (`tei:keepDivOnPage`), la première division reste sur
  `index.html` si rien ne la précède.
- **Édition critique** (`${varians}/edition-critique.xsl`, scénario après
  « Édition HTML (feuille de Varians) ») : la feuille du kit, retouchée ;
  ses règles d'apparat sont dans `rendering/apparat-commun.xsl` (module
  inclus, partagé avec le pré-passage : `f:choix`, `f:lecons` avec les
  `rdgGrp`, `f:apparat` → map, `f:folio-montre`, `f:lb-groupe`,
  `f:texte-net`, `f:verifier`). Deux séries par division : apparat
  (chiffres) et notes, moins nombreuses (lettres :
  `format-integer(…, 'a')`).
- **Témoin des feuilles d'apparat** : dans la boîte d'un scénario, la valeur
  du paramètre `temoin-de-base` (`WITNESS_PARAM`) se choisit dans une liste
  (`witness_choices` : le pivot, enregistré `${pivot}`, puis les témoins du
  projet et du `<listWit>` de l'édition ; `aucun`) ; une autre valeur est
  gardée.
- **Copie d'une feuille de Varians** (« Ouvrir la feuille ») : avec les
  feuilles qu'elle inclut ou importe par un chemin relatif
  (`xslt_scenarios.included_stylesheets`), sans remplacer un fichier.

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
- TEI Stylesheets (V0.9.2.2) : le
  LaTeX se compile hors de Varians (xelatex) ; en texte et en Markdown, les
  TEI Stylesheets écrivent le lemme et la variante à la suite. Une seule
  version est installée pour tous les projets : une publication refaite
  après une mise à jour peut différer (le journal donne la version). Deux
  instances de Varians : celle qui se lance supprime les anciennes versions,
  même si l'autre transforme encore avec l'une d'elles.

## Tests

`tests/test_transformations_format.py`, `tests/test_xslt_scenarios.py`,
`tests/test_xslt_engine_lxml.py`, `tests/test_xslt_engine_saxon.py`
(ignorés sans Saxon, sauf le message « Saxon n'est pas installé »),
`tests/test_transform_worker.py`, `tests/gui/test_gui_transform_runner.py`,
`tests/gui/test_gui_transform_scenarios.py`,
`tests/gui/test_gui_transform_run.py` ; feuilles (V0.9.2.1) :
`tests/test_document_files.py`, `tests/test_xslt_check.py`,
`tests/test_xslt_completion.py`, `tests/gui/test_gui_document_dialogs.py`,
`tests/gui/test_gui_xslt_check.py`, `tests/gui/test_gui_xslt_completion.py` ;
TEI Stylesheets (V0.9.2.2) : `tests/test_tei_stylesheets.py`,
`tests/test_tei_scenarios_saxon.py` (ignoré sans Saxon),
`tests/gui/test_gui_tei_stylesheets.py`, et des tests dans
`tests/test_xslt_scenarios.py`, `tests/gui/test_gui_transform_scenarios.py`
et `tests/gui/test_gui_transform_run.py`. V0.9.2.7 : `tests/test_apparatus_notes_saxon.py`,
`tests/test_edition_critique_saxon.py` (exemples du kit dans
`tests/data/edition_critique/`), et des tests dans
`tests/test_xslt_engine_saxon.py`, `tests/test_tei_scenarios_saxon.py`,
`tests/test_xslt_scenarios.py`. Les tests installent la
bibliothèque dans un dossier temporaire de la session
(`tests/conftest.py`, `tests/gui/conftest.py`).
