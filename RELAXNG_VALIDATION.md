# Validation RELAX NG — V0.5.1

Cette couche TEI-aware distingue trois notions :

1. **XML bien formé** : la syntaxe XML est correcte.
2. **XML valide selon RELAX NG** : le document bien formé respecte le schéma actif.
3. **Schematron** : les déclarations sont détectées mais ne sont pas encore exécutées.

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
`<?xml-model?>` peuvent toutefois être détectées à titre informatif.

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

est détectée et signalée dans la barre d'état. **Aucune validation Schematron
n'est encore exécutée en V0.5.1.** Cette détection réserve le contrat pour une
intégration ultérieure sans changer le format de projet.

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

