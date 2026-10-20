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
   - synchronisation des témoins : les `<lb edRef="#pivot"/>` sont comptés
     dans l'ordre du document assemblé (décalage par partie) ;
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
  - « Choisir les documents affichés… » ;
  - « Retirer le document du projet… » : la commande existante, avec sa
    confirmation ; le fichier n'est jamais supprimé.

  « Masquer » plutôt que « Fermer » : « Fermer » laisserait croire que le
  fichier est fermé, alors qu'il fait toujours partie du projet.
- **Règles** : un document masqué garde ses modifications en mémoire, et
  Varians propose de les enregistrer avant de quitter ; masquer l'onglet du
  document affiché fait passer à l'onglet voisin ; le dernier onglet visible
  ne peut pas être masqué.

## Ordre de réalisation prévu

1. Choix des onglets affichés.
2. XInclude, références et validation : identifiants des parties comptés dans
   le document maître ; validation du document assemblé, erreurs ramenées au
   bon fichier ; les deux formes de parties (`xpointer` par identifiant et
   `element()`).
3. Vue XSLT / CSS et export web à partir du document assemblé, modifications
   par fragment réécrites dans le bon fichier.
4. Synchronisation des `<lb/>` à travers les parties.
5. Cas avancés : `parse="text"`, `<xi:fallback>`, autres schémas `xpointer`.

## Restent à décider

- Le nom des onglets des parties : nom du fichier, `@n`, ou `<head>` du
  sermon.
- La création d'une nouvelle partie depuis Varians (fichier et `xi:include`
  ajoutés au document maître).
- Proposé : « Renommer l'onglet… » dans le menu du clic droit d'un onglet
  (modifie `@label` du `<document>` dans `project.xml`). Le nom, le schéma
  et l'ordre des documents ne se règlent aujourd'hui qu'en modifiant
  `project.xml` à la main, projet fermé.

## Autres décisions de la série 0.8.8.0

- Numéro de version : V0.8.8.0.
- Projets créés avant la V0.8.8.0 : leur copie des traductions (dossier
  `i18n/` du projet), prioritaire, garde l'ancienne terminologie (« manuscrit
  pivot »). On se contente de l'expliquer (README, aide) : supprimer ce
  dossier ou en remplacer les fichiers. Aucun fichier de projet n'est
  réécrit.
