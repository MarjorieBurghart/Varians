# Décisions : éditions assemblées (XInclude) et choix des onglets

Décisions arrêtées le 20 octobre 2026, pendant la préparation de la
V0.8.8.0, pour les versions suivantes. Elles précisent la piste
« Inclusion structurelle » de
`Varians_Reflexions_Preparatoires_Avenir_2026-10-15.md`. Rien de ce qui
suit n'est encore réalisé, sauf mention contraire.

## Principe directeur

Le XML produit avec Varians doit rester utilisable tel quel par les autres
outils XML (XSLT, oXygen, TEI Publisher…). Varians ne donne pas aux
pointeurs ni aux inclusions un sens qui lui serait propre : il suit les
normes (URI, XInclude) et la pratique TEI.

Déjà appliqué en V0.8.8.0 aux références entre documents :

- `#id` désigne un élément du document qui contient la référence ;
- `fichier.xml#id` vise un autre document, par un chemin relatif ;
- une forme courte dont la cible n'existe que dans un autre document est
  signalée par la commande « Références », avec la forme à écrire.

Les pointeurs abrégés TEI (`<prefixDef>`, par exemple `ref="pers:bernard"`)
restent une piste ultérieure. Ils sont standard, mais peu d'outils les
développent : `fichier.xml#id` reste la forme sûre.

## État en V0.8.8.0

XInclude n'est pas géré. Constaté sur une édition dont le `<body>` contient
`<xi:include href="chapitre1.xml"/>` :

| Fonction | Comportement |
|---|---|
| Validation RELAX NG | erreur sur `xi:include` (« Did not expect element include there »), alors que le document assemblé est valide au regard de TEI_ALL |
| Vue XSLT / CSS | texte inclus absent |
| Export web | texte inclus absent |
| Références | un `#id` visant le texte inclus est « introuvable », ou « forme courte vers un autre document » si le fichier inclus est déclaré comme document du projet |
| Synchronisation des témoins | les `<lb/>` des fichiers inclus ne sont pas comptés (l'index ne lit que le texte de l'édition) |

## Éditions assemblées

Cas type : une collection de sermons, avec un document maître qui inclut une
vingtaine de fichiers, un par sermon.

1. **L'édition est le document assemblé ; les fichiers sont l'endroit où l'on
   écrit.** Dans `project.xml`, l'édition reste le document maître. Varians
   lit ses `xi:include` et connaît ainsi les parties de l'édition, sans autre
   déclaration. Les fichiers d'autorités restent des documents auxiliaires,
   cités par des références.
2. **Deux formes de parties, toutes deux possibles**, pour respecter les
   pratiques existantes :
   - des fragments (`<xi:include href="sermon01.xml"/>`, fichier dont la
     racine est le `<div>` du sermon) : seul l'ensemble est validé ;
   - des documents TEI complets, inclus par `xpointer`, soit par identifiant
     (`xpointer="s01"`), soit par `element(/1/2/1)` : chaque fichier peut
     aussi être validé seul, avec son propre `<?xml-model?>`. Seule la partie
     incluse entre dans l'édition ; l'en-tête propre à chaque fichier en reste
     exclu.
3. **Tout calcul porte sur le document assemblé**, comme dans les autres
   outils :
   - synchronisation des témoins : voir « Synchronisation des collections »
     ci-dessous (décision du 21 octobre 2026, qui précise celle-ci) ;
   - références : après inclusion, toutes les parties forment un seul
     document, donc `#id` d'une partie à l'autre est correct ;
   - validation : chaque erreur est indiquée dans le bon fichier, à la bonne
     ligne ;
   - Vue XSLT / CSS et export web : voir le point suivant.
4. **Vue XSLT / CSS : toute l'édition assemblée**, placée sur la partie en
   cours. Les XSLT numérotent souvent notes et apparat sur l'ensemble de
   l'édition : une vue limitée à une partie donnerait de faux numéros. Une
   modification faite dans la vue est réécrite dans le fichier d'origine (après
   inclusion, chaque élément garde la trace de son fichier et de sa ligne). Une
   option « partie en cours seulement » pourra s'ajouter si la vue devient
   lente sur de très grosses collections. L'export web porte lui aussi sur
   l'édition assemblée.
5. **Édition et enregistrement** : chaque partie s'édite dans son propre
   fichier, avec son historique d'annulation ; Ctrl+S enregistre la partie
   affichée ; avant de quitter, Varians propose d'enregistrer toutes les
   parties modifiées.
6. **Un projet sans `xi:include` est inchangé.**

## Choix des onglets affichés

Indépendant d'XInclude, et déjà utile avec les fichiers d'autorités.
**Réalisé en V0.8.9.0** (module `document_display.py`), pour l'édition et
les documents auxiliaires ; les parties de l'édition s'y ajouteront avec
XInclude.

- Affichage ▸ **« Choisir les documents affichés… »**, sur le modèle de
  « Choisir les témoins affichés… » : une case par document (parties de
  l'édition et documents auxiliaires) et un ordre réglable. Le choix est
  mémorisé localement pour chaque projet ; `project.xml` n'est pas modifié.
- **À la première ouverture**, tous les onglets sont affichés : l'édition,
  ses parties dans l'ordre d'inclusion, puis les documents auxiliaires.
- **Un document masqué** auquel on est conduit (F12, double-clic dans le
  panneau « Références ») est affiché quand même : son onglet réapparaît.
- **Clic droit sur un onglet** :
  - « Masquer l'onglet » : le document reste dans le projet et revient par le
    menu Affichage ;
  - « Renommer l'onglet… » (sauf pour l'édition) : modifie `@label` du
    `<document>` dans `project.xml` ; un nom vide revient au nom du
    fichier ;
  - « Choisir les documents affichés… » ;
  - « Retirer le document du projet » : la commande existante, avec sa
    confirmation ; le fichier n'est jamais supprimé.

  « Masquer » plutôt que « Fermer » : « Fermer » laisserait croire que le
  fichier est fermé, alors qu'il fait toujours partie du projet.
- **Règles** : un document masqué garde ses modifications en mémoire, et
  Varians propose de les enregistrer avant de quitter ; masquer l'onglet du
  document affiché fait passer à l'onglet voisin ; le dernier onglet visible
  ne peut pas être masqué.
- **Précisions arrêtées pendant la réalisation** :
  - un onglet que F12 ou le panneau « Références » fait réapparaître reste
    affiché aux ouvertures suivantes ;
  - l'enregistrement de tous les documents ne fait réapparaître aucun
    onglet ; si l'enregistrement d'un document masqué échoue, ce document
    reste affiché, avec son onglet ;
  - le document affiché a toujours son onglet : à l'ouverture, Varians
    affiche l'édition, et son onglet réapparaît s'il avait été masqué ;
  - décocher le document affiché dans la fenêtre fait afficher le premier
    onglet resté visible ;
  - la commande du menu Affichage n'est active que si le projet compte
    plusieurs documents.

## Ordre de réalisation prévu

1. Choix des onglets affichés — réalisé en V0.8.9.0.
2. XInclude, références et validation — réalisé en V0.9.0.0 (voir
   ci-dessous) : parties en onglets, validation du document assemblé avec
   les erreurs ramenées au bon fichier, références d'une partie à l'autre,
   les deux formes de parties (`xpointer` par identifiant et `element()`).
   La synchronisation des témoins y est suspendue pour une édition qui a
   des parties.
3. Synchronisation des collections, cas 1 (numérotation continue) —
   réalisé en V0.9.1.0 (voir ci-dessous).
4. Synchronisation des collections, cas 2 (un JSON par texte), en deux
   versions (décision du 22 octobre 2026) :
   - V0.9.1.1, réalisée (voir ci-dessous) : un JSON par texte et par
     témoin, pivot propre à un texte, synchronisation par lignes texte par
     texte ;
   - V0.9.1.3, réalisée (voir ci-dessous) : lacunes, témoins synchronisés
     par pages dans un texte synchronisé à part (page de départ par
     `<locus from>` ou par le premier `<pb>`) ;
   - V0.9.1.4, réalisée (voir ci-dessous) : parcours d'un manuscrit dans
     son propre ordre (décidé le 22 octobre 2026 : une navigation nouvelle,
     des panneaux vers l'édition, qui mérite sa version).
5. Vue XSLT / CSS et export web à partir du document assemblé,
   modifications par fragment réécrites dans le bon fichier, avec les mêmes
   continuités de synchronisation sur le site :
   - V0.9.1.5, réalisée (voir ci-dessous) : la Vue XSLT / CSS de l'édition
     assemblée, comme pour une édition en un seul fichier (décidé le
     22 octobre 2026 : toutes ses fonctions, plus celles des parties) ;
   - V0.9.1.6, réalisée (voir ci-dessous) : l'export web de l'édition
     assemblée, avec les continuités du bureau (décidé le 23 octobre 2026 :
     une seule version pour tout ; les flèches de tout panneau du viewer
     mènent le texte, comme sur le bureau). L'étape 5 est terminée.
6. Cas avancés : `parse="text"`, `<xi:fallback>`, autres schémas `xpointer`.

## Réalisé en V0.9.0.0

- **Onglets des parties** : le nom du fichier. Ordre : l'édition, ses
  parties dans l'ordre d'inclusion (une partie imbriquée après celle qui
  l'inclut), puis les documents auxiliaires. Une partie nouvelle se place
  après les parties déjà présentes, même si un ordre a été mémorisé.
- **Une partie** est un fichier inclus qui existe, même mal formé (pour
  pouvoir le corriger). Un fichier à la fois inclus et déclaré dans
  `<documents>` est une partie : une seule session par fichier.
- **La liste des parties** est relue après chaque enregistrement de
  l'édition ou d'une partie (fichiers enregistrés, non le texte en cours).
  Une partie qui n'est plus incluse garde son onglet tant qu'elle a des
  modifications non enregistrées ; déclarée dans `<documents>`, elle
  redevient un document auxiliaire.
- **Renommer l'onglet et Retirer le document** ne concernent que les
  documents auxiliaires (les deux réécrivent `<documents>`).
- **« Enregistrer l'édition sous »** dans un autre dossier avertit que les
  `xi:include`, relatifs, ne trouveraient plus les parties.
- **Validation** : l'édition et chaque partie font valider l'édition
  assemblée, avec le schéma de l'édition et le texte non enregistré des
  parties modifiées. Le résultat est rangé sur l'édition et ses parties ;
  une modification de l'une le rend périmé pour toutes. Colonne Document
  (seulement pour une édition qui a des parties), double-clic vers la
  bonne partie ; l'onglet de chaque partie prend la couleur de ses propres
  erreurs. Les problèmes d'assemblage sont des erreurs du domaine
  `XINCLUDE`, traduites dans la langue de l'interface.
- **Références** : un `#id` se cherche d'abord dans son propre fichier
  (en-tête compris), puis parmi les identifiants que les autres fichiers
  apportent à l'édition assemblée. Un identifiant défini dans deux parties
  n'est ambigu que pour une référence qui ne le trouve pas dans son propre
  fichier. Un témoin déclaré seulement dans le `<teiHeader>` d'une partie
  incluse par `xpointer` est trouvé dans cette partie, mais il manque au
  document assemblé : un outil qui ne lit que celui-ci ne le voit pas.
- **Témoins d'une partie** (« Débugger l'apparat », complétion de
  `@wit`) : son `<listWit>` ; sinon les témoins de l'édition dont un
  `<locus target="#…">` vise un élément de la partie ; sinon les témoins
  cités dans ses `@wit`. Les trois pratiques de déclaration sont acceptées :
  `<listWit>` dans chaque texte, dans l'édition seule, ou les deux. Un même
  manuscrit garde le même sigle dans toute la collection.
- **Vue XSLT / CSS** (décidé à l'essai de la V0.9.0.0) : elle montre
  l'édition assemblée, parties comprises (texte non enregistré des parties
  modifiées), en **lecture seule** : ses paragraphes ne sont plus ceux de la
  source, donc pas d'édition par fragment ni de report de position entre
  la source et l'aperçu. L'édition par fragment réécrite dans le bon
  fichier reste pour l'étape 5 (réalisée en V0.9.1.5). L'export web, lui, ne contenait pas
  encore les parties (message avant l'export, jusqu'à la V0.9.1.6).
- **Folios d'un texte dans un témoin** : notés soit par `<locus from to>`
  dans un en-tête (forme structurée, lisible par Varians), soit seulement
  par les `<pb/>` de l'édition ; les deux pratiques existent.

## Synchronisation des collections (décision du 21 octobre 2026)

Constat : dans une collection, les témoins n'ont pas toujours les mêmes
textes, ni dans le même ordre ; le pivot peut changer d'un texte à l'autre ;
un texte peut être incomplet dans un témoin. Un texte en plusieurs morceaux
dans un manuscrit est remembré par l'éditeur ; deux copies d'un texte dans un
même manuscrit font deux témoins.

Deux cas, réunis par une seule règle : **un texte qui a son dossier
d'alignements est synchronisé à part ; les autres suivent la numérotation
continue.** Un projet simple n'a rien à choisir, et les deux cas peuvent se
mêler.

1. **Cas 1 (V0.9.1.0) : une collection découpée par commodité.** Les textes
   se suivent de la même façon dans la plupart des manuscrits ; un fichier
   par texte sert seulement à manier de plus petites unités. Les
   `<lb edRef="#pivot"/>` sont comptés dans l'ordre du document assemblé
   (décalage par partie) ; les JSON sont ceux d'aujourd'hui, un par témoin
   pour toute l'édition. Condition : le pivot contient ces textes, dans
   l'ordre de l'édition. Les autres témoins peuvent avoir un autre ordre ou
   ne pas avoir un texte : leurs lignes désignent déjà des lignes du pivot.
2. **Cas 2 (V0.9.1.1, V0.9.1.3 et V0.9.1.4) : un corpus aux témoins variables.** Un JSON par texte
   et par témoin, au format actuel (VariansSynchro ne change pas), rangé
   selon une convention, sans déclaration : `alignments/s02/B.json`, le
   dossier portant le nom du fichier du texte. Les témoins affichés pour un
   texte sont ceux qui ont un JSON pour lui. Le pivot est celui du projet,
   sauf exception déclarée dans `project.xml` (par exemple
   `<part name="s02" base="B"/>`) : le pivot est une notion propre à
   Varians, sans encodage TEI évident. Page de départ d'un texte dans un
   témoin : le `<locus from>` d'un en-tête, sinon la page qui précède le
   premier `<pb>` du témoin dans le texte, dans l'ordre des pages du
   témoin. Lacune d'un témoin : « lacune » (`<lacunaStart/>` …
   `<lacunaEnd/>`) ; une lacune du pivot arrête la synchronisation le temps
   du passage.

Continuités voulues : suivre l'édition (chaque témoin saute à l'endroit où il
a le texte suivant, ou indique qu'il ne l'a pas) ; suivre un manuscrit dans
son propre ordre, l'édition ouvrant la bonne partie ; garder affichée et
synchronisée une page qui porte la fin d'un texte et le début d'un autre ;
parcourir d'un seul tenant un pivot commun à plusieurs textes. L'export web
devra offrir les mêmes continuités. Dans le cas 2, suivre un manuscrit d'un
texte à l'autre suppose de déduire l'ordre des textes dans ce manuscrit à
partir de ses pages : c'est la partie la plus délicate, qui peut venir en
second temps.

## Réalisé en V0.9.1.0 (cas 1)

- **Numérotation** : les `<lb edRef="#pivot"/>` sont comptés dans l'ordre
  du document assemblé (module `pivot_lines.py`), comme le font la XSLT, le
  viewer web et `xmllint --xinclude` : un `<lb/>` placé dans un commentaire
  ou hors de l'élément inclus d'une partie ne compte pas. Un texte placé
  avant le premier `<lb/>` d'une partie appartient à la dernière ligne de ce
  qui la précède, comme dans un fichier unique ; une position placée après
  un `xi:include` reçoit la dernière ligne de son contenu.
- **Les deux sens** : le curseur de l'édition ou d'une partie fait suivre
  les témoins ; un clic ou un défilement dans le pivot place le curseur dans
  la partie qui contient la ligne et l'affiche (son onglet réapparaît s'il
  était masqué, ses modifications non enregistrées sont conservées).
- **Interface** : les témoins, leurs fenêtres détachées, l'état de structure
  et leurs commandes restent affichés sur une partie ; la Vue XSLT / CSS et
  « Enregistrer l'édition sous… » restent réservées à l'édition.
- **Structure** : l'état de structure et l'avertissement à l'enregistrement
  (de l'édition ou d'une partie) comptent les lignes de l'édition assemblée.
  La condition du cas 1 (le pivot contient les textes dans l'ordre de
  l'édition) n'est pas vérifiable : seul le nombre de lignes l'est.
- **Mode page** : le dernier `<pb>` d'un témoin est cherché dans l'ordre de
  l'édition, y compris dans une partie précédente ; un témoin qui a les
  textes dans un autre ordre doit donc porter son `<pb>` au début de chaque
  texte. Les folios sont lus dans le `<facsimile>` de l'édition.
- **« Marquer la page » et « Couper le folio » dans une partie** (décidé le
  21 octobre 2026) : le `<pb>` va dans la partie, le `<facsimile>` dans
  l'édition, modifiée sans être affichée ; annuler dans la partie retire le
  `<pb>`, pas le `<facsimile>` complété.
- **Vue XSLT / CSS** (décidé le 21 octobre 2026) : toujours en lecture
  seule, sans synchronisation par un clic, jusqu'à l'étape 5.
- **Mesure** : projet exemple découpé en 22 parties (3790 lignes du pivot),
  environ 45 ms pour un assemblage complet ; aucun assemblage pendant la
  saisie de texte ordinaire.

## Numéros de version (décision du 22 octobre 2026)

On avance moins vite dans les numéros : pas de V1.0 avant que les scénarios
de transformation XSLT soient réalisés. Le cas 2 devient V0.9.1.1 et
V0.9.1.2 (et non V0.9.2.0).

La V0.9.1.2 s'intercale ensuite (décision du 22 octobre 2026, après la
publication de la V0.9.1.1) : sélections partagées entre l'aperçu XSLT / CSS
et l'éditeur de fragment. La fin du cas 2 devient la V0.9.1.3.

## Réalisé en V0.9.1.1 (cas 2, première partie)

- **Dossiers par texte** (`text_alignments.py`) : un texte de l'édition dont
  le dossier `alignments/<nom du fichier>/` contient au moins un JSON est
  synchronisé à part ; seuls les JSON des témoins déclarés dans
  `project.xml` sont pris. Problèmes signalés par « État des témoins… » :
  JSON d'un témoin non déclaré, pivot inconnu (celui du projet est pris),
  pas de JSON pour le pivot, `<part>` qui ne nomme aucun texte, deux textes
  de même nom.
- **Pivot propre à un texte** : `<parts><part name base/></parts>`, écrit à
  la main (décidé le 22 octobre 2026), lu par `load_project` et conservé
  par la fenêtre des paramètres du projet.
- **Segments** (`pivot_lines`) : chaque texte synchronisé à part est
  numéroté pour lui seul, avec son pivot, inclusions imbriquées comprises ;
  le segment de l'édition ne compte plus ses lignes. Un fichier appartient
  à un seul segment : le segment change avec le document affiché.
- **Fenêtre** (`text_segments.py`) : à chaque changement de segment, les
  panneaux reçoivent les données du segment et son pivot, sans être
  recréés ; la disposition et les fenêtres détachées ne changent pas.
  L'état d'un texte est lu à sa première visite, puis gardé (environ
  20 ms, puis 10 ms, sur le projet d'essai).
- **Témoin absent d'un texte** (décidé le 22 octobre 2026) : son panneau
  reste en place, vide, avec « Pas d'alignement de ce témoin pour ce
  texte ».
- **Actualiser et diagnostiquer** portent sur le segment affiché ;
  l'actualisation relit les dossiers.
- **Documentation utilisateur** : mode d'emploi « Mettre en place une
  édition en parties (XInclude) » dans l'aide (demandé le 22 octobre 2026).

## Réalisé en V0.9.1.2 (Vue XSLT / CSS, éditeur de fragment)

Demandé après la V0.9.1.1 ; ne concerne que l'édition sans parties, seule à
avoir un éditeur de fragment.

- **Le crayon ✎** ouvre seulement le paragraphe dans l'éditeur de
  fragment : la source et les témoins ne bougent plus (ils allaient sur la
  première ligne du paragraphe). Un clic sur le texte de l'aperçu les
  synchronise toujours.
- **Aperçu → fragment** : une chaîne sélectionnée à la souris dans le
  paragraphe ouvert est sélectionnée dans l'éditeur de fragment, qui prend
  le focus. Une sélection dans un autre paragraphe ne change rien (décidé
  le 22 octobre 2026) : on change de paragraphe par le crayon, avec la
  question habituelle si le fragment a des modifications non appliquées.
- **Fragment → aperçu** : une sélection faite dans l'éditeur de fragment
  est sélectionnée dans l'aperçu, qui défile jusqu'à elle ; le focus reste
  dans l'éditeur.
- **Même occurrence** : rang de l'occurrence dans le paragraphe, sinon
  position, comme pour le report entre Source et XSLT / CSS (fonctions
  communes `xml_occurrences`, `xml_selection_descriptor`,
  `pick_xml_occurrence`).
- **Report entre Source et XSLT / CSS** : inchangé, et désormais vérifié
  par des tests qui l'exécutent. Pour une édition en parties, il est coupé
  depuis la V0.9.0.0 (aperçu assemblé en lecture seule) ; il reviendra à
  l'étape 5, avec l'édition par fragment de l'édition assemblée (décidé le
  22 octobre 2026 ; rétabli en V0.9.1.5).

## Réalisé en V0.9.1.3 (cas 2, suite)

- **Lacunes** (`lacunae.py`) : `<lacunaStart/>` … `<lacunaEnd/>`, le témoin
  par la leçon (`<rdg>`/`<lem>`) qui contient la balise, ou par son `@wit`
  (`att.rdgPart`) dans une leçon de plusieurs témoins. La TEI n'admet ces
  balises que dans `<rdg>` et `<lem>` ; la forme isolée avec `@wit` est
  reconnue aussi, mais la validation TEI la signale. Une lacune sans fin court jusqu'à la fin du texte ; une
  fin sans début est ignorée. Dans l'édition assemblée, une lacune passe
  d'une partie à l'autre (numérotation continue) ; dans un texte à part,
  l'état repart de zéro au début du texte.
- **Panneaux** (décidé le 22 octobre 2026) : un témoin en lacune garde la
  ligne ou la page où son texte s'interrompt, avec un bandeau « Lacune ».
  Pendant une lacune du pivot, les témoins par lignes restent sur sa
  dernière ligne, avec un bandeau et un message ; les témoins par pages
  continuent de suivre leurs `<pb>`.
- **« Débugger l'apparat »** : « `<app>` incomplets » n'attend pas de
  leçon d'un témoin dans sa lacune ; la condition (XPath 1.0) n'est ajoutée
  que pour les témoins qui ont des lacunes dans le document.
- **Témoins par pages dans un texte à part** (décidé le 22 octobre 2026) :
  seulement les témoins qui ont le texte (un `<pb edRef>` dans le texte, ou
  un `<locus target>` vers lui dans leur `<witness>`) ; les autres gardent
  le message d'absence. Leur page vient des seuls `<pb>` du texte ; page de
  départ : `<locus from>`, sinon la page qui précède celle du premier
  `<pb>`, dans l'ordre des pages du témoin.
- **Limites** : l'export web ne montre ni les lacunes ni les parties ; une
  requête de l'apparat lancée dans une partie ne voit que les lacunes de
  cette partie.

## Réalisé en V0.9.1.4 (cas 2, fin)

- **Les flèches de tout panneau mènent l'édition** (décidé le 22 octobre
  2026 : « toujours », et non un bouton à enfoncer) : le témoin est suivi
  dans son propre ordre, d'une partie ou d'un texte à l'autre ; les autres
  témoins suivent le pivot. Feuilleter un témoin sans bouger l'édition ne
  reste possible qu'avec un document auxiliaire affiché.
- **Ordre des textes dans un manuscrit** (décidé le 22 octobre 2026 :
  déduit des pages) : rang des images déclarées, sinon pages communes aux
  JSON du témoin, sinon `<locus from>` ou foliotation, sinon ordre de
  l'édition, signalé (« État des témoins… », barre d'état).
- **Portée** : témoins par lignes, témoins par pages (flèches et liste des
  folios : ligne d'un JSON, `<pb>`, `<locus from>`), pivot d'un texte à
  l'autre ; le panneau d'un témoin absent mène au texte suivant ou
  précédent qui l'a.
- **Limites** : l'export web ne contient pas encore les parties.

## Réalisé en V0.9.1.5 (étape 5, première partie)

- **Sources de l'aperçu** (`preview_sources.py`, sans Qt) : chaque `<p>`
  du `<body>` assemblé (l'ordre des ✎) et chaque `<lb>` du pivot du
  projet (l'ordre des repères de ligne) est rattaché à son fichier
  (`Assembly.origin`) et à sa place dans ce fichier, par sa ligne et son
  rang dans la ligne (`_match_by_line`), comme les `<lb/>` du pivot. Les
  textes sont ceux des parties ouvertes, sinon le disque.
- **L'aperçu reste ouvert** quand une partie est affichée (il montre
  toujours toute l'édition) ; afficher un document auxiliaire le referme.
- **Clic, table des matières, recherche** : par position, et non par rang
  (`navigate_to_preview_line`) : le curseur va dans le fichier du repère,
  et les témoins suivent avec la numérotation de ce fichier, qui reste
  juste dans un texte synchronisé à part.
- **Fragment** : ouvert dans le fichier de son paragraphe (lu au besoin
  sans être affiché), écrit dans ce fichier, en une seule étape
  d'annulation, par l'éditeur s'il est affiché, sinon dans son propre
  document (`_write_session_text`). Ctrl+S dans le fragment enregistre ce
  fichier, puis le document affiché s'il est modifié ; un fragment non
  appliqué compte pour son fichier dans les demandes d'enregistrement.
- **Reports** (précision du 22 octobre 2026 : vers le fichier inclus qui
  contient le texte, non vers l'édition maîtresse) : de l'aperçu à la
  source, la ligne ouvre son fichier, puis la même occurrence est
  sélectionnée dans le paragraphe, dans son fichier ; dans l'autre sens,
  `paragraph_at` et `line_before`.
- **Limites** : un `<p>` qui contient un `xi:include` s'édite dans le
  fichier de sa balise ; un élément que la XSLT ne rend pas décale les ✎
  et les repères (comme pour un seul fichier) ; l'export web ne contient
  pas encore les parties (V0.9.1.6).

## Réalisé en V0.9.1.6 (étape 5, fin : l'export web)

Format des données et fonctionnement du viewer : `WEB_VIEWER_ASSEMBLED.md`.

- **Règles communes au bureau et au web** (`segment_model.py`, sans Qt) :
  témoins par pages d'un texte, page de départ, `<locus>`, rang des pages
  déclarées, arrêt « présent », page qui mène. La fenêtre
  (`text_segments.py`, `witness_sync.py`) et l'export les appellent ; il
  n'y a pas de copie qui pourrait diverger.
- **L'export lit l'édition assemblée** (`web_viewer/assembled_document.py`) :
  chaque copie de partie est marquée de son texte par un attribut technique
  retiré ensuite ; chaque texte compte les `<lb>` de son pivot et les relie
  à ses JSON (`build_segment_lb_index`), comme `pivot_lines`. Dans un texte
  au pivot B, les leçons, les lignes et les `<pb>` sont ceux de B.
- **Une édition en un seul fichier est exportée exactement comme avant**
  (test d'empreinte de `build_dataset`). Une édition en parties sans texte
  à part aussi : sortir un sermon dans une partie ne change rien.
- **Textes à part** : `meta.segments`, `meta.line_order` ; clés préfixées
  (`~1~`…), car un JSON par texte peut reprendre les pages et les numéros du
  JSON global ; une vue par témoin et par texte (lignes, pages, ou absent) ;
  le pivot d'un texte non affiché est exporté sans images.
- **Parcours** : `witness_route` sur les JSON après les règles d'images
  (sans préfixe, pour garder l'identité des pages du bureau) ; les `<pb>`
  d'un témoin par pages sont situés par leur position dans le texte de
  lecture, et portent la ligne du pivot ouverte à leur place
  (`pb_line_keys`, seulement pour une édition à textes à part).
- **Viewer** : les décisions sans DOM sont dans `web_viewer/sync_model.js`,
  testé avec node, avec la parité des positions (rendu, recherche, Python),
  de `witness_route` et de `segment_model.present_stop` ; le texte suivant
  ou précédent qui a un témoin est calculé par le viewer (il dépend de la
  ligne affichée). Tests de comportement pilotés dans Chromium (ignorés
  sans Playwright).
- **Changements pour une édition en un seul fichier** (choix du 23 octobre
  2026) : les flèches de tout panneau et la liste des folios mènent le
  texte ; les lacunes ont leurs bandeaux. Deux corrections au passage : un
  `<pb>` sans `@facs` trouve son folio par son nom même quand l'image et le
  folio portent le même nom ; la position retenue est celle du fragment
  cliqué, et non le début de sa ligne.
- **Depuis Varians** : plus de question « Exporter quand même » ; l'édition,
  ses parties modifiées et le fragment non appliqué d'une partie sont
  enregistrés avant l'export (un échec l'annule) ; les problèmes
  d'assemblage sont dans le compte rendu.
- **Limites** : la précision des positions est celle des fragments de texte
  affichés ; un `<pb>` ou un `<lb>` dans une leçon non retenue ou dans une
  note n'est pas vu par le viewer ; « État des témoins… », « Actualiser les
  synchronisations… », « Marquer la page » et « Double page… » restent
  propres au bureau ; `parse="text"` et `xi:fallback` sont signalés.

## Plusieurs éditions dans un même projet (décision du 23 octobre 2026)

Les « Réflexions préparatoires » du 15 octobre envisageaient un second
modèle : plusieurs éditions TEI autonomes (« unités éditoriales ») dans un
même projet, chacune avec son document maître, ses témoins, son pivot et
ses alignements, autour de ressources communes. Ce modèle est **retiré de
la feuille de route** :

- des éditions qui ne partagent presque rien (par exemple un sermon latin du
  XIIIᵉ siècle et un poème d'Emily Dickinson) sont plus simples dans des
  projets séparés, ce qui est déjà possible ;
- un corpus de textes transmis par des témoins différents tient dans une
  seule édition en parties, avec des textes synchronisés à part (V0.9.1.1),
  chacun avec son pivot et ses JSON.

Conséquence pour les scénarios de transformation XSLT : leur source est un
fichier ou l'édition (assemblée au besoin) ; une publication portant sur
plusieurs éditions d'un même projet n'est plus envisagée.

## Scénarios de transformation XSLT (décisions du 23 octobre 2026, V0.9.2.0)

- Moteurs : XSLT 1.0 (lxml) et XSLT 3.0 (Saxon-HE, paquet `saxonche`),
  Saxon étant installé avec Varians (`requirements.txt`,
  `installer_dependances.bat`).
- Format : `<transformations><scenario …/>` dans `project.xml`.
- Source : l'édition (assemblée au besoin), le document affiché ou un
  fichier.
- Résultat : un fichier fixé dans le scénario, remplacé à chaque exécution,
  jamais une source du projet. Avec Saxon, d'autres fichiers
  (`xsl:result-document`) seulement dans le dossier du résultat, obtenus en
  deux passages pour garder leur mise en forme exacte.
- Lecture : fichiers locaux et réseau (`http`, `https`).
- CSS copiée à côté du résultat, son nom passé à la feuille (paramètre
  `css`) ; paramètres : valeurs fixes (chaînes).
- Interface : Fichier ▸ « Scénarios de transformation… » et bouton
  « Transformer ▾ » (Ctrl+Shift+T) ; scénarios prédéfinis fournis par
  Varians, dupliqués dans le projet pour les adapter.
- Version suivante : scénarios prédéfinis sur les TEI Stylesheets du TEI-C,
  téléchargés hors des projets et mis à jour automatiquement, la version
  utilisée étant notée au journal ; d'abord les sorties HTML, HTML5, texte,
  Markdown et LaTeX, puis DOCX, ODT et EPUB. Quand vérifier les mises à jour,
  avec quel accord, et s'il faut figer une version par projet : à décider.

Réalisation : `XSLT_SCENARIOS.md`.

## Restent à décider

- La création d'une nouvelle partie depuis Varians (fichier et `xi:include`
  ajoutés au document maître).
- Le schéma d'un document auxiliaire et l'ordre des `<document>` dans
  `project.xml` ne se règlent encore qu'en modifiant ce fichier à la main,
  projet fermé.

## Essai préalable d'XInclude (20 octobre 2026)

Essai fait en mémoire, avant la V0.8.9.0, pour vérifier que les décisions
ci-dessus sont réalisables avec lxml :

- avec un résolveur (`etree.Resolver`) qui sert les textes en mémoire, y
  compris ceux des parties non enregistrées, lxml assemble les deux formes
  de parties : fragments, et documents complets inclus par `xpointer`, par
  identifiant comme par `element()` ; chaque élément garde sa ligne
  d'origine (`sourceline`) ;
- difficulté : une erreur RELAX NG dans une partie est rapportée avec le
  nom du fichier **maître** et la ligne de la **partie** ;
- solution retenue : un assemblage fait par Varians (futur
  `xml_assembly.py`), qui remplace chaque `xi:include` par une copie de la
  partie et retient l'origine de chaque copie ; le chemin de l'erreur
  (`error_log.path`) mène à l'élément fautif, donc à sa partie. L'essai a
  donné « s01.xml, ligne 3 », ce qui est exact ;
- à adapter alors : `ValidationIssue`, qui recevra le fichier ; le panneau
  RELAX NG (colonne Document, saut dans la bonne partie) ; la clé de
  dédoublonnage des erreurs ; l'invalidation du résultat quand une partie
  est modifiée.

## Autres décisions de la série 0.8.8.0

- Numéro de version : V0.8.8.0.
- Projets créés avant la V0.8.8.0 : leur copie des traductions (dossier
  `i18n/` du projet), prioritaire, garde l'ancienne terminologie (« manuscrit
  pivot »). On se contente de l'expliquer (README, aide) : supprimer ce
  dossier ou en remplacer les fichiers. Aucun fichier de projet n'est
  réécrit.
