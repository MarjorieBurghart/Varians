# Varians V0.8.5.21 — Dispositions des témoins et fenêtres détachées

## Principe

Les trois dispositions intégrées sont accessibles dans **Affichage → Disposition des témoins** :

- **Verticale** : la pile redimensionnable historique, défilable si besoin.
- **Horizontale** : panneaux en colonnes, avec barre d'outils compacte et défilement horizontal si l'écran ne suffit pas.
- **Grille (2 colonnes)** : deux témoins par rangée ; les témoins supplémentaires occupent de nouvelles rangées défilables.

Le **quatrième mode** est le détachement individuel : dans le même menu, **Détacher un témoin** permet de sortir n'importe quel panneau dans une fenêtre top-level native. Le bouton **↗** de l'en-tête agit de la même manière ; **↙**, le bouton Rattacher de la fenêtre, ou la fermeture de celle-ci le réinsèrent dans la disposition courante. Plusieurs témoins peuvent être détachés en même temps et déplacés sur plusieurs moniteurs.

Chaque fenêtre indépendante dispose de sa propre option **Toujours au premier plan** (Windows `WindowStaysOnTopHint`), non imposée par défaut. La géométrie de chaque fenêtre et son option sont enregistrées localement, par identité de projet et de témoin. L'ordre des panneaux et leur état de visibilité restent indépendants.

Le séparateur principal de la fenêtre permet de réduire la colonne de l'éditeur XML jusqu'à **environ 20 %** de l'espace de travail et, selon la taille de fenêtre, davantage. Le minimum fixe de 560 px de la colonne manuscrits a été supprimé ; le scroll horizontal reste disponible si des commandes demandent plus d'espace. Le rapport de largeur XML/images est mémorisé par projet ; l'utilisateur ne subit pas un rapport 20/80 imposé.

## Architecture et invariants

- `workspace_layout.py` : politique pure de normalisation des modes, constitution des lignes de grille, validation des témoins détachés.
- `MainWindow.workspace_root` : conteneur **stable** d'une `QScrollArea` unique. On ne remplace jamais le widget du scroll lors d'un changement de mode (Qt détruirait l'ancien widget).
- `witness_splitter` : pile verticale conservée pour le code de maximisation et de taille déjà en place.
- `witness_horizontal_splitter`, `witness_grid_splitter` et `_grid_rows` : QSplitters supplémentaires, créés puis réutilisés.
- `MainWindow._apply_witness_panel_order` : déplace les **mêmes instances** de `ManuscriptPanel`, sans nouvel objet, sans nouveau chargement de JSON ni nouvelle source d'image.
- `DetachedWitnessWindow` : fenêtre native possédant temporairement le `ManuscriptPanel` d'origine ; une fermeture normale demande au contrôleur de le rattacher. La fermeture de l'éditeur principal ferme aussi toutes ses fenêtres détachées.
- Le mode « grille » et « horizontal » utilisent une barre d'outils courte, sans modifier les signaux ni l'état des commandes. Le mode vertical et les fenêtres détachées affichent les libellés complets.

La synchronisation TEI/IIIF, les numéros de page, `base_keys`, zoom, cadres, page courante, image, données de l'éditeur source et historique d'annulation ne sont pas reconstruits lorsque l'on change de disposition.

Les préférences se trouvent dans `QSettings` sous `projectView/<hachage du chemin>/` : `workspaceMode`, `witnessOrder`, `visibleWitnesses`, `witnessHeights`, `horizontalSizes`, `gridSizes`, `xmlColumnRatio`, `detachedWitnesses`, `floatingAlwaysOnTop/<id>`, `floatingGeometry/<id>`.

Ces réglages ne sont **pas** écrits dans `project.xml`, les JSON de synchronisation, la TEI ou les images : il s'agit de préférences locales purement visuelles.

## Contrôles

Tests Python exécutables sans PySide6 : déplacements réels de méthodes extraites du contrôleur (AST) avec substituts de `QSplitter` et de fenêtre, ordre, nombre impair de témoins, raccrochage, tailles persistées par identifiant, ratio 20 %, fenêtres détachées et réglages indépendants « Toujours au premier plan ».

**Validation interactive requise sur Windows/PySide6** : changement de disposition pendant le chargement IIIF, glissement des séparateurs, navigation TEI pendant le détachement, basculement « Toujours au premier plan » sur deux moniteurs, fermeture d'une fenêtre, enregistrement et réouverture d'un projet, et changement de langue pendant qu'une fenêtre est détachée. La simulation AST ne peut valider le gestionnaire natif de fenêtres Windows.
