# Varians 0.8.5.8 — Préparation de la transcription TEI depuis le témoin pivot

## Visibilité des commandes (V0.8.5.7, conservée)

Dans « Nouveau projet », les cases figurent dans un encadré dédié
**immédiatement sous « Point de départ »**, indépendamment de la hauteur du
tableau des témoins. Dans « Paramètres du projet », l'encadré est placé **avant**
les témoins. Les fenêtres sont défilables, et leurs boutons de validation
restent visibles. Le titre précise « Varians 0.8.5.7 » pour distinguer
une exécution obsolète (raccourci ancien, cache Spyder).

Un test statique vérifie la présence des choix et leur emplacement dans le
layout ; l'essai visuel sous PySide6 sur Windows reste indispensable.

## Objet et déclenchement

La fonction est **facultative**. Dans **Fichier → Nouveau projet → Commencer une nouvelle transcription**, ou dans **Paramètres du projet**, cocher « Préparer les `<pb/>` du témoin pivot » et, éventuellement, « Générer aussi les `<lb/>` ». Cette seconde option est cochée initialement mais la préparation elle-même reste décochée : aucune génération automatique non demandée.

Seul un **corps TEI réellement vide**, composé d'un seul `<p/>`, `<p></p>`, `<ab/>` ou équivalent vide, est accepté. Les éditions existantes ou déjà initialisées ne sont jamais modifiées par ce mécanisme. Les décisions sont prises pour le seul témoin pivot déclaré ; les autres témoins et leurs données restent inchangés.

Une fenêtre récapitule le nombre de pages, les lignes et les sources identifiées, et donne en détails la liste des pages et avertissements. Confirmation explicite requise, refus par défaut. Le fichier XML d'origine est sauvegardé avec une **date unique**, puis réécrit atomiquement.

## Format généré

Exemple indicatif (l'`xml:id` de surface reprend **l'identifiant stable préexistant**, et non le seul numéro de folio) :

```xml
<facsimile>
  <surface xml:id="Mu-p0014" n="14v">
    <graphic url="images/Mu-14v.jpg"/>
  </surface>
</facsimile>
<text>
  <body>
    <p>
      <pb n="14v" edRef="#Mu" facs="#Mu-p0014"/>
      <lb edRef="#Mu"/>
      <lb edRef="#Mu"/>
    </p>
  </body>
</text>
```

`<lb>` annonce **le début d'une ligne physique** et constitue ici un jalon provisoire que la transcription devra être insérée entre les balises. Le texte reconnu par OCR **n'est jamais injecté** automatiquement. `@edRef` désigne le témoin déclaré dans `<listWit>` ; `@facs` relie le `<pb/>` à sa `<surface>`. Aucun lien `@facs` vers les zones de ligne n’est ajouté à `<lb/>`. Depuis 0.8.5.8, les `<lb/>` ne portent **aucun `@n`** : ces jalons sont des emplacements de travail, pas une numérotation éditoriale imposée.

## Sources et politique d'identité

- Liste des pages : surfaces correspondant aux images de travail déjà retenues, selon `project_facsimile_pages`. Pour les IIIF, on réutilise le Canvas et le numéro *dans le manifeste original*, **jamais son rang dans la sélection**. Les centaines de canvases non sélectionnés ne deviennent pas des `<pb/>`.
- Cas historique `images type="auto"` avec seulement un JSON Varians-Synchro : si les pages JSON fournissent une URL d'image IIIF exploitable, `tei_pivot_scaffold` prépare les seules surfaces de ces pages et les matérialise lors de la validation. Sinon il signale l'absence de surface, sans inventer de chemin d'image.
- Si un fichier PAGE/ALTO est associé de façon **explicite** à un Canvas, cette association est prioritaire. Pour les autres, on utilise la proposition d'association par nom d'image exact et non ambigu du module `iiif_page_selection`. Les rangs respectifs dans les fichiers ne sont pas une preuve.
- Pour les images locales, l'association repose sur le nom exact de l'image ou le libellé univoque, rapproché du nom source déclaré dans ALTO/PAGE et, à défaut, des identifiants de page/légendes présents dans le JSON. Une collision ou une incertitude exclut les lignes concernées.
- Nombre de lignes : le **nombre d'éléments `TextLine`** des fichiers ALTO/PAGE associés est prioritaire. Sans OCR, le JSON peut fournir le compte s'il contient une liste de lignes **numérotées de 1 à N, sans trous ni doublons** ; l'utilisateur est averti que des lignes physiques non synchronisées peuvent manquer. En présence d'un OCR et d'un JSON divergents, l'OCR fait autorité et une alerte décrit l'écart.
- Une page sélectionnée pour laquelle le nombre de lignes ne peut être établi reçoit seulement `<pb/>`. Jamais de `<lb/>` spéculatif. Si une page du JSON n’a pas de surface parmi les images retenues, elle est signalée dans les avertissements, mais Varians n’ajoute pas de page hors du périmètre éditorial.

## Protection de l'édition

`tei_pivot_scaffold.py` est indépendant de Qt. Fonctions principales :

| Fonction | Rôle |
|---|---|
| `build_pivot_plan()` | Purement informatif : plan pages/lignes, avertissements, surfaces à créer uniquement dans le mode JSON historique. |
| `scaffold_is_empty()` | Validation restrictive d'un corps TEI initial vide. |
| `render_pivot_scaffold()` | Génération du XML sans écrire de fichier ; conserve en l'état la déclaration, l'en-tête et le reste des données. Refuse l'édition si elle n'est plus vide. |
| `write_pivot_scaffold()` | Relecture de la source, sauvegarde datée et remplacement atomique sur confirmation de l'interface. |
| `run_pivot_scaffold_dialog()` | Prévisualisation, consentement et déclenchement des opérations dans `project_dialogs.py`. |

Les JSON de synchronisation, `base_keys`, liens ALTO/PAGE, manifestes, `project.xml`, identifiants de lignes et données des autres témoins ne sont pas réécrits par le moteur. La fonction n'est pas une opération de fusion pour une édition commencée : il faut déplacer manuellement les jalons si le texte a déjà été saisi. Lors du retour dans les paramètres, l'interface recontrôle la TEI avant toute insertion ; une seconde invocation sur le document déjà préparé est bloquée.

## Tests

`python -m pytest -q tests/test_v0856_pivot_scaffold.py` et `python -m pytest -q tests` vérifient notamment : projet neuf puis réouverture, associations exactes indépendamment de l'ordre d'import, IMAGE IIIF v2, cinq pages parmi 469, JSON autonome, décompte de lignes, ambiguïtés, TEI préfixée, absence de liens aux zones, sauvegarde et refus de réécriture. Les essais interactifs PySide6 restent nécessaires sur machine équipée.
