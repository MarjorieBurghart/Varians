# Validation RELAX NG — V0.5.1

Cette couche TEI-aware distingue trois notions :

1. **XML bien formé** : la syntaxe XML est correcte.
2. **XML valide selon RELAX NG** : le document bien formé respecte le schéma actif.
3. **Schematron** : les règles du schéma et des déclarations Schematron sont
   appliquées depuis la V0.9.2.3 (voir la dernière section).

## Politique de schéma du projet

`project.xml` accepte trois modes.

### 1. Détection automatique depuis `<?xml-model?>` — mode recommandé

```xml
<schema type="relaxng" source="xml-model"/>
```

L'éditeur inspecte le prologue de l'édition et cherche une instruction :

```xml
<?xml-model
  href="schema/edition.rng"
  type="application/xml"
  schematypens="http://relaxng.org/ns/structure/1.0"?>
```

Le `href` peut être relatif, absolu, `file:` ou HTTP/HTTPS.

### 2. Schéma explicitement choisi pour le projet

```xml
<schema type="relaxng" source="project" file="schema/edition.rng"/>
```

Le schéma déclaré dans le projet est alors prioritaire ; `<?xml-model?>` n'est
pas utilisé pour RELAX NG.

### 3. Aucune validation RELAX NG

```xml
<schema type="relaxng" source="none"/>
```

Le document reste éditable normalement. Les déclarations Schematron de
`<?xml-model?>` sont détectées à titre informatif, mais leurs règles ne sont
pas vérifiées (« Schematron : non vérifié »).

Les anciens projets contenant simplement :

```xml
<schema type="relaxng" file="schema/edition.rng"/>
```

restent compatibles et sont interprétés comme `source="project"`.

Un projet sans élément `<schema>` est interprété comme `source="xml-model"`.

## Schémas distants et cache

Une URL HTTP/HTTPS n'est pas téléchargée à chaque validation. Le schéma et ses
`include` / `externalRef` distants sont mis en cache localement :

- Windows : `%LOCALAPPDATA%/TEIManuscriptEditor/schema_cache`
- autres systèmes : `~/.cache/tei-manuscript-editor/schema_cache`

Le bouton `↻` du panneau de validation force un nouveau téléchargement puis une
nouvelle validation. Le cache n'est pas stocké dans le dossier du projet.

## Schematron

Une instruction de la forme :

```xml
<?xml-model
  href="rules.sch"
  type="application/xml"
  schematypens="http://purl.oclc.org/dsdl/schematron"?>
```

était seulement détectée et signalée dans la barre d'état de la V0.5.1 à la
V0.9.2.2. Depuis la V0.9.2.3, ses règles sont appliquées : voir « V0.9.2.3 —
règles Schematron » ci-dessous.

## Signal visuel des états

Les deux onglets `XML source` et `Vue XSLT/CSS` partagent un indicateur visuel :

- **rouge pâle** : XML non bien formé ;
- **orange pâle** : XML bien formé mais invalide selon le RELAX NG actif ;
- apparence normale : XML bien formé et aucune invalidité RNG connue.

Le rouge est prioritaire sur l'orange.

Après une modification du texte, l'ancien résultat RNG est considéré comme
périmé. Le contrôle de bien-formation continue après une courte pause ; la
validation RNG est relancée manuellement avec `F8`, à l'ouverture et lors de la
sauvegarde.

## Sauvegarde : avertir, ne pas bloquer

La V0.5.1 protège en priorité le travail de l'utilisateur.

### XML non bien formé

L'enregistrement est **autorisé**, mais un dialogue prévient que :

- le document contient une erreur de syntaxe XML ;
- l'aperçu XSLT et le RNG peuvent être indisponibles ;
- le fichier pourra être corrigé plus tard.

L'utilisateur choisit explicitement `Enregistrer quand même` ou `Annuler`.

### XML bien formé mais non valide selon RELAX NG

L'enregistrement est également **autorisé** après un avertissement indiquant le
nombre d'erreurs RNG.

### Éditeur de fragment

L'éditeur de fragment reste volontairement plus strict : un fragment qui
rendrait le document non bien formé ne peut pas être appliqué. Comme la zone à
corriger est limitée et localisée, cette protection reste utile et évite de
réinjecter une erreur syntaxique dans le document complet.

## Panneau de validation

`F8` ou `Valider RNG` affiche les diagnostics structurés : niveau, ligne,
colonne et message. Un double-clic sur une erreur positionne la source XML à la
ligne correspondante.

La validation RELAX NG requiert `lxml`. L'éditeur reste utilisable sans cette
dépendance ; seul le contrôle RNG est alors indisponible.


## V0.5.5 — contrôle automatique de bonne formation

Le contrôle automatique qui suit la frappe reste distinct de la validation RELAX NG F8. Il vérifie la **bonne formation XML** et maintient l'état visuel rouge/normal.

À partir de V0.5.5, cette passe est lancée après une courte pause de saisie dans un worker séparé du thread graphique. Un résultat calculé sur une ancienne révision du document est ignoré. Les opérations qui exigent une réponse immédiate — notamment la sauvegarde — conservent un contrôle synchrone avant de poursuivre.

La reconstruction des repères de lignes `<lb>` réutilise le même instantané de texte. Pendant la saisie ordinaire, les positions des repères existants sont ajustées incrémentalement ; un balayage complet n'est demandé que lorsqu'une modification peut toucher la structure des balises.


## V0.5.6 — optimisation de Ctrl+S

La sauvegarde conserve les mêmes contrôles de sécurité, mais évite désormais les travaux répétés inutiles.

- Le RNG compilé par `lxml.etree.RelaxNG` est conservé en mémoire et réutilisé entre validations.
- Le cache est invalidé automatiquement si le fichier RNG racine ou l'un des `include` / `externalRef` locaux change.
- Le graphe des dépendances est lui-même mémorisé : lorsqu'aucun fichier n'a changé, seules des métadonnées de fichiers sont consultées.
- Si le contrôle automatique de bonne formation porte déjà sur la révision courante, Ctrl+S réutilise ce résultat au lieu de relancer `ElementTree.fromstring`.
- Si une validation RNG antérieure porte exactement sur la même révision et le même jeton de schéma, son résultat est réutilisé.
- L'écriture du fichier est atomique : le nouveau texte est écrit dans un temporaire du même dossier, l'ancien fichier est renommé en `.bak`, puis le temporaire prend sa place. Cela évite la copie complète que faisait `shutil.copy2` avant chaque sauvegarde.

La validation du document XML courant reste effectuée lorsqu'il a changé : seule la recompilation du schéma, beaucoup plus coûteuse sur un gros RNG TEI, est amortie.

## V0.8.5.26 — Actualisation du panneau
Lorsqu’il est affiché, le panneau invalide et efface immédiatement les résultats périmés puis recalcule les erreurs après 1,25 seconde de pause. Le contrôle automatique n’ouvre pas un panneau fermé. Le bouton F8 conserve son comportement explicite. Le parse RELAX NG est encore exécuté dans le fil Qt après debounce, distinct du contrôle XML hors fil existant.

## V0.8.5.26.2 — invalidation fiable des diagnostics du panneau

- Après une première activation du panneau par F8, toute modification du document invalide aussitôt le résultat RNG et vide les erreurs périmées.
- Le temporisateur de 1 250 ms reste actif après un changement d’onglet ou la fermeture du panneau ; rouvrir le panneau revalide si la dernière révision n’est pas couverte.
- Les modifications via QTextCursor et annuler/refaire sont suivies également par `QTextDocument.contentsChanged`, avec garde de révision contre le double traitement.
- Un contrôle tardif dont la révision ne correspond plus à l’édition courante est rejeté, et une nouvelle passe est demandée.
- La validation explicite F8 et la résolution des schémas d’origine ne changent pas ; aucune correction XML ou RNG n’est appliquée automatiquement.
- Limite : tests de cycle exécutés sur des substituts Qt, l’interface PySide6 Windows doit être vérifiée par l’utilisateur.

## V0.8.9.2 — validation dans un processus séparé

La compilation d’un gros schéma (TEI_ALL : une dizaine de secondes) bloquait
toute la fenêtre : lxml garde le verrou de Python pendant la compilation, si
bien qu’un fil d’exécution n’aurait pas suffi. La validation se fait donc
dans un processus à part.

- `relaxng_worker.py` (sans Qt) : une requête JSON par ligne sur le
  descripteur 0, une réponse par ligne sur le descripteur 1 ; il réutilise
  `validate_relaxng` et son cache, si bien qu’un schéma compilé l’est pour
  toute la session. Les descripteurs sont lus directement, car `sys.stdin`
  et `sys.stdout` peuvent manquer dans une application Windows sans console.
- Lancement : c’est Varians lui-même, relancé avec `--relaxng-worker`
  (`python editeur_tei.py --relaxng-worker` depuis les sources, l’exécutable
  dans une version autonome). `editeur_tei.py` reconnaît l’option avant
  d’importer PySide6 : le processus ne charge que lxml.
- `validation_worker.py` : un seul processus pour l’application, lancé au
  premier besoin (`CREATE_NO_WINDOW` sous Windows), arrêté à la fermeture ;
  fils d’écriture et de lecture dédiés, réponses remises au fil principal.
  - validation automatique (`validate_relaxng_document(background=True)` :
    ouverture, changement de document, modification) : sans attente ; le
    résultat n’est affiché que s’il concerne encore le document affiché
    dans la même révision ;
  - validation demandée (F8, enregistrement, rechargement du schéma) :
    attend la réponse en laissant tourner la boucle d’événements, clics et
    frappes ignorés.
- Repli : processus introuvable, arrêté ou sans réponse pendant 5 minutes →
  validation dans Varians comme avant, signalée une fois dans la barre
  d’état, sans perte des requêtes en cours.
- `busy_indicator.py` : la lueur affichée avant « RNG » tant qu’une
  validation est en cours.
- Limite : le téléchargement d’un schéma distant, à sa toute première
  utilisation, se fait encore dans Varians.

## V0.9.0.0 — édition assemblée par XInclude

Une édition qui inclut ses parties par `xi:include` est validée assemblée,
comme le feraient `xmllint --xinclude` ou oXygen, mais chaque erreur est
rapportée dans **son** fichier, à sa ligne :

- `xml_assembly.assemble` remplace chaque `xi:include` par une copie de
  l’élément inclus (fragment, `xpointer` par identifiant ou `element()`),
  en retenant le fichier d’origine de chaque copie ; les éléments gardent
  leur ligne. Le texte des parties ouvertes, même non enregistré, remplace
  celui des fichiers.
- `relaxng_validation.validate_assembled` valide le document assemblé et
  ramène chaque erreur à son fichier par le chemin de l’élément fautif
  (`error_log.path`) : `ValidationIssue.file` porte le chemin de la partie,
  vide pour l’édition. (`xmllint` attribue ces erreurs au fichier maître.)
- Un problème d’assemblage (partie absente ou mal formée, inclusion
  circulaire, `parse="text"`, `xi:fallback`, autre schéma `xpointer`) est
  une erreur du domaine `XINCLUDE` : `type_name` est son code, `message`
  son détail ; le panneau le met en forme dans la langue de l’interface.
- `validate_document` est le point d’entrée commun au processus de
  validation (champ `parts` de la requête : `{chemin: texte}`, même vide)
  et au repli dans Varians.
- Le schéma est toujours celui de l’édition (son `<?xml-model?>` ou celui
  du projet), même quand une partie est affichée.

Dans la fenêtre : colonne **Document** (seulement pour une édition qui a des
parties), double-clic vers la bonne partie, couleur de chaque onglet selon
ses propres erreurs ; le résultat est partagé par l’édition et ses parties,
et toute modification de l’une le rend périmé pour toutes.

## V0.9.2.1 — feuilles XSLT

Une feuille XSLT affichée n’est pas validée par RELAX NG : les mêmes
déclencheurs (ouverture, F8 — « Vérifier la feuille XSLT » —, frappe une fois
F8 utilisé, enregistrement) la font compiler par lxml ou Saxon
(`xslt_check_ui`, voir `XSLT_SCENARIOS.md`). Le résultat prend la forme d’un
`ValidationResult` et se range comme celui d’une validation RNG ; le panneau,
la barre d’état et la couleur de l’onglet le montrent de la même façon. À
l’enregistrement, une feuille qui a des erreurs demande « Enregistrer quand
même ? » (titre « Feuille XSLT incorrecte »). Le panneau affiche la colonne
Document quand une erreur est dans un autre fichier (feuille importée ou
incluse) ; le double-clic mène à ce fichier s’il est un document du projet.

## V0.9.2.3 — règles Schematron

Les règles Schematron sont appliquées dans le même passage que le RNG, par
le même processus de validation, aux mêmes moments (ouverture, frappe, F8,
enregistrement).

**Sources des règles** (`schema_resolution.SchemaResolution.schematron_sources`,
en modes `auto` et `file`) :

1. le RNG employé (`schema_path`), qu'il vienne du `<?xml-model?>` ou du
   projet : ses règles intégrées (`sch:ns`, `sch:let`, `sch:pattern`,
   `sch:diagnostics` hors d'un élément Schematron), y compris celles des RNG
   inclus ; un RNG sans règles ne compte pas ;
2. chaque déclaration `xml-model` de type Schematron, vers un `.sch` ou un
   RNG, résolue comme celle du RNG : relative au document, ou distante
   (`http`/`https`) et mise en cache avec ses inclusions
   (`_fetch_remote_rng`, qui suit aussi `sch:include`).

Pas de doublon (`path_key`) ; une même adresse n'est téléchargée qu'une fois
par résolution : la déclaration Schematron des documents TEI désigne le même
`tei_all.rng` que leur RNG. Une déclaration introuvable va dans
`schematron_errors` sans arrêter le reste. Mode `none` : aucune source.

**Moteur** (`schematron.py`, sans Qt) : SchXslt2 1.11.2
(`resources/schxslt2/transpile.xsl`, MIT, voir son LISEZMOI) transforme la
Schematron en feuille XSLT 3.0, compilée par Saxon (`saxonche`, processeur
partagé avec `xslt_engines`) ; la feuille compilée reste en cache tant que la
source et les fichiers qu'elle inclut ne changent pas
(`_schema_dependency_signature`). Paramètres statiques :
`schxslt:compact-report` vrai, `schxslt:terminate-validation-on-error` faux
(une erreur d'exécution d'une règle est écrite dans le rapport). Toutes les
règles sont évaluées en XPath 3.1, quel que soit `queryBinding` ; phase :
`defaultPhase`, sinon toutes.

**Validation** (`relaxng_validation.validate_document(…, schematron=[…])`) :
après le RNG, si le document est bien formé et que le RNG a pu être chargé,
les règles sont appliquées au même arbre lxml (l'édition assemblée, avec le
texte des parties ouvertes). Saxon lit cet arbre sérialisé ; chaque message
(`svrl:failed-assert`, `svrl:successful-report`) est ramené à son élément
par son emplacement (`@location`, `fn:path()`), donc à sa ligne lxml et, par
`Assembly.origin`, à sa partie. Un attribut ou un texte donne la ligne de
son élément.

- `ValidationIssue.domain = "SCHEMATRON"` ; `type_name` : identifiant de
  l'assertion, sinon de la règle ou du groupe ; niveau d'après `@severity`,
  sinon `@role` : `warning`, `warn`, `nonfatal` → `WARNING` ; `info`,
  `information` → `INFO` ; le reste → `ERROR`.
- `valid` est faux s'il y a une erreur RNG ou Schematron ; un avertissement
  ou une information ne rendent pas invalide.
- `ValidationResult.schematron_rules` (sources appliquées),
  `schematron_errors` (`(source, détail)` des règles incorrectes : fichier
  absent ou mal formé, XPath fautif — « fichier:ligne: message » —, erreur
  d'exécution) et `schematron_error` (`saxon_missing`). Une règle incorrecte
  ne rend pas le document invalide.
- Sans RNG mais avec une déclaration Schematron : bien-formation, puis les
  règles seules (`schema` vide dans la requête).
- Processus : champ `"schematron": [chemins]` des requêtes ; sa sortie
  d'erreur est un fichier temporaire (`VARIANS_STDERR_LOG`), où Saxon écrit,
  sous Windows, le détail d'une erreur de compilation ; effacé à l'arrêt.

**Fenêtre** : colonne **Origine** (XML, RELAX NG, XInclude, Schematron,
XSLT) après **Niveau** ; niveau Information ; résumé qui compte à part les
erreurs RELAX NG et Schematron ; un document valide garde ses avertissements
dans la liste ; étiquette Schematron de la barre d'état (✓, erreurs,
messages, aucune règle, règles incorrectes, Saxon manquant, non vérifié),
info-bulle avec les sources et le détail ; onglet orange pour une erreur
seulement ; question d'enregistrement « Document non valide » qui compte les
erreurs RELAX NG et Schematron. Le jeton de validation
(`_validation_token`) couvre le RNG et les sources des règles : une règle
modifiée fait valider de nouveau à l'enregistrement.

**Nouveaux projets** : `minimal_tei_text` écrit aussi la déclaration
Schematron de TEI All.

**Limites** : XPath 3.1 pour toutes les règles (une règle écrite pour
XPath 1.0 peut, dans de rares comparaisons de types, lever une erreur
qu'XPath 1.0 taisait : elle est alors signalée comme règle incorrecte) ;
phase par défaut seulement, `phase` d'une déclaration ignoré ; ni
Schematron 1.5, ni règles d'un XSD ; un `document()` d'une règle lit les
fichiers locaux.

## V0.9.2.4 — phases, règles incorrectes, fichiers `.sch`

**Phases.** Une source de règles est un `SchematronSource(path, phase)`
(`schema_resolution`) : phase vide pour le RNG employé, celle de
l'attribut `phase` (`XmlModelDeclaration.phase`) pour une déclaration. Une
déclaration du même fichier avec une phase remplace la phase de la source
déjà retenue : la TEI déclarée avec `phase="#ALL"` n'est vérifiée qu'une fois.
`schematron.compiled(path, phase)` garde une feuille compilée par couple
(chemin, phase) et passe `schxslt:phase` au transpileur (`#DEFAULT` si la
phase est vide). Phases acceptées : vide, `#DEFAULT`, `#ALL`, ou l'identifiant
d'un `sch:phase` du fichier ou d'un fichier inclus ; sinon (et pour un
`defaultPhase` inconnu) erreur des règles `phase`, avec la liste des phases :
SchXslt2, lui, ne garderait aucune règle sans rien dire. Le processus reçoit
`"schematron": [[chemin, phase], …]` (un chemin seul reste accepté).

**Règles incorrectes structurées.** `SchematronReport.errors` et
`ValidationResult.schematron_errors` sont des `ValidationIssue` du domaine
`SCHEMATRON_RULES` : `file` et `line` de la règle fautive (0 si inconnue),
`type_name` = code (`missing`, `malformed`, `phase`, `xpath`, `compile`,
`runtime` ; l'interface ajoute `declaration` pour une déclaration que la
résolution n'a pas pu suivre, et la vérification d'un `.sch` `assembly`),
`message` = détail (pour `phase` : la phase, une tabulation, les phases du
fichier). `result_from_dict` accepte encore la forme `(source, détail)`.

**Panneau.** Une ligne par règle incorrecte, après les messages du document :
niveau Erreur, origine « Schematron (règles) », message traduit selon le code
(`schematron.rules.<code>`), colonne Document : le fichier des règles. Elle
ne compte ni dans la validité, ni dans la couleur de l'onglet, ni dans la
question d'enregistrement (`_is_error` ignore ce domaine). Double-clic
(`_open_rules_file`) : un document du projet s'affiche à la ligne ; un
fichier du dossier du projet peut être ajouté aux documents (question) ; un
fichier hors du projet est signalé dans la barre d'état. L'info-bulle de
l'étiquette Schematron nomme la phase de chaque source
(`schematron.tip.phase`).

**Revalidation.** `_restore_document_view` relance la validation (en
arrière-plan) quand le jeton du schéma et des règles a changé depuis le
dernier résultat du document (`_validation_outdated`) : un `.sch`
enregistré dans Varians est appliqué dès qu'on revient à l'édition.

**Fichiers `.sch` comme documents** (`schematron_check`, `schematron_check_ui`,
`schematron_completion`, `xml_roots`). Un fichier Schematron affiché
(`xml_roots.schematron_info`, sinon l'extension `.sch`) est vérifié à la
place de la validation RELAX NG, comme une feuille XSLT : F8, affichage,
frappe après F8, enregistrement. Opération du processus
`{"op": "check_schematron", "text": …, "path": …}` → `schematron_check.check` :

1. bonne formation (domaine `PARSER`) ;
2. structure d'après `resources/schemas/schematron/iso-schematron.rng`
   (ISO/IEC 19757-3 2016, copie de lxml complétée de `@severity`, voir son
   LISEZMOI). Ce schéma est fait d'`interleave` : libxml2 y donne, pour une
   seule faute, une cascade de messages souvent sans ligne ou trompeurs.
   `_structure_errors` parcourt donc l'arbre avec le modèle de complétion
   du schéma (`schematron_completion`, attentif à l'ordre des frères) : une
   erreur par élément non permis à sa place (`element`), attribut sans
   espace de noms inconnu (`attribute`), attribut obligatoire absent
   (`required`, table `_REQUIRED`), message « nom, tabulation, parent ».
   Les éléments et attributs étrangers sont permis. S'il ne trouve rien,
   libxml2 sert de repli (`RELAXNGV`, types de données, `IDREF`…) : une
   référence `IDREF` à un identifiant d'un fichier inclus est retirée ; une
   référence inconnue, que libxml2 ne situe pas, est donnée à la ligne de
   l'élément qui la porte. Un fichier inclus (racine autre que
   `sch:schema`) n'est vérifié que par `_structure_errors` ;
3. inclusions : un `sch:include` vers un fichier absent → `missing` à sa
   ligne ;
4. si rien n'a été trouvé et que la racine est `sch:schema`, compilation
   (`schematron.check_compilation`) du texte de l'éditeur, base
   = le chemin du fichier, phase `#ALL`, avec un second transpileur où
   `schxslt:check-assembled-schema` est vrai et dont les `xsl:message` sont
   gardés (`set_save_xsl_message`) : erreurs d'assemblage (`assembly`,
   message de SchXslt2 en anglais, ligne retrouvée d'après la valeur citée,
   `_ASSEMBLY_SITES`), puis erreur XPath à la ligne de l'expression dans le
   texte (`_expression_site(…, text)`).

Sans Saxon : étapes 1 à 3, `schematron_error = "saxon_missing"`. Le résultat
est rangé avec le jeton `("schematron",)`. Complétion : schéma ISO livré,
préfixe du fichier, éléments étrangers ignorés, valeurs proposées pour
`severity`, `role`, `queryBinding`.

**Limites** : phase choisie par la déclaration seulement ; l'édition est
validée avec les règles enregistrées, pas avec le texte non enregistré d'un
`.sch` ouvert ; la vérification d'un `.sch` suit l'édition 2016 (+
`@severity`) : `sch:group`, `sch:library`… y sont des erreurs de structure ;
ni Schematron 1.5, ni règles d'un XSD.
