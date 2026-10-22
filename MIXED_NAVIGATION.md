# Varians V0.8.5.11 — Navigation mixte par témoin

## Contrat de navigation

La présence d’une synchronisation exploitable pour le **témoin pivot** n'impose
plus un mode unique à tous les panneaux. Le mode est déterminé par témoin :

- `panel.sync_enabled = True` pour le pivot disposant de lignes de base et les
  autres témoins dont le JSON brut possède des `base_keys` associés à ce pivot ;
- `panel.sync_enabled = False` pour les témoins sans alignement, à images seules,
  ou dont les synchronisations ne sont pas encore utilisables.

Lors de chaque mouvement du curseur XML, `MainWindow.sync_panels_to_cursor()`
actualise **d'abord les panneaux page** via `_sync_page_panels_to_cursor()`,
puis, si le pivot est synchronisé, les panneaux ligne via `set_primary()`.
Une optimisation ancienne fondée sur le dernier ordinal `lb` ne doit jamais
bloquer le changement de page d'un témoin sans JSON : il peut avoir un `pb`
entre deux `lb` du pivot. `navigate_to_base_ordinal()` et
`_primary_panel_navigate()` rafraîchissent également les pages puisque le
timer Qt est parfois suspendu lors de leur navigation contrôlée.

## Identité d'une page

`tei_facsimile.facsimile_ref_at_position()` cherche en priorité le dernier
`<pb edRef="#C" facs="#C-p0003"/>` *antérieur au curseur* pour le témoin C.
Un `pb` d'un autre témoin ne réinitialise pas cette page. Les anciennes TEI
sans `@edRef` restent prises en charge lorsque `@facs` identifie sans
ambiguïté une surface du bon témoin.

Une TEI écrite manuellement peut aussi contenir
`<pb edRef="#C" n="3r"/>`. Pour les panneaux page seulement, `@n` est alors
admis si sa valeur (après suppression des espaces extérieurs et sans tenir
compte de la casse) correspond **exactement à un unique libellé à l’intérieur de ce témoin**.
Deux manuscrits peuvent donc avoir le même `@n="3r"` : c’est bien le couple
`@edRef` + `@n` qui identifie la page, non `@n` isolément. Un éventuel
doublon de libellé *dans le même témoin* reste ambigu sans `@facs`. Aucun rapprochement approximatif, via `image index`, ni par
rang ordinal. Si `@facs` est présent mais invalide, `@n` ne masque pas
l'erreur ; la page précédemment connue reste affichée.

## Viewer web

Le dataset comprend déjà `witness.line_sync` indépendamment du mode global.
Le navigateur utilise `pageMode = !lineMode || !w.line_sync` pour chaque témoin.
La V0.8.5.11 améliore `selectLine()` : le `data-doc-pos` du fragment de texte
permet de retrouver les derniers `pb` de chaque témoin page avant d'appeler
`syncAll()`. Les `<pb/>` sans `@facs` sont admis via `data-n` uniquement si leur
nom est unique dans le panneau ; les noms ambigus sont ignorés.

## Non-régressions / portée

- Aucun changement à `project.xml`, ALTO/PAGE, JSON, `base_keys`, TEI, surfaces.
- Aucune modification des limites de colonnes (V0.8.5.9) ni du tracé des cadres
  (V0.8.5.10).
- Le clic manuel sur les boutons précédent/suivant de **chaque** panneau image
  continue d'être indépendant pour les témoins page.
- Les tests de logique de la fenêtre de bureau exécutent les **véritables
  méthodes Python** de `MainWindow` extraites par AST, sous doubles de Qt,
  afin de vérifier le comportement même sans installation PySide6.
- Le rendu graphique complet PySide6/Windows nécessite toujours un essai utilisateur.

## Reproduction type

Trois témoins : `Mu` (pivot JSON), `F` (JSON relié par `base_keys`),
`C` (images locales `C-p0001`, `C-p0002`, sans ALTO/PAGE ni JSON).
Dans le corps TEI, un `pb` de `C` à la page 3r est placé entre deux `lb` de
`Mu`. Le changement de curseur au-delà de ce `pb` doit montrer `C-p0002` dans
le panneau C sans changer le centre de Mu ou F tant que l'ordinal de leur
ligne courante reste le même.

## V0.8.5.12 — Identité du folio dans le mode page

Le rôle TEI est celui du **manuscrit pivot** et ne désigne pas un manuscrit
choisi comme texte de base de l'édition critique. Le projet continue à stocker
`base_witness`, `role="base"` et les `base_keys` pour préserver les fichiers.
Ce sont exclusivement les chaînes traduites à l'écran qui changent.

Une même chaîne `@n="3r"` sur les folios de deux témoins ne pose aucun problème.
`facsimile_ref_at_position()` cherche les repères du témoin défini par
`@edRef`; son index `@n` est construit à partir **des seules pages de ce
témoin**. Le viewer web a le même contrat via `pbWitnessIds()` et les
`labelIndex` privés de `states.get(witness_id)`. L'identifiant `@facs` reste
prioritaire. Une répétition *dans un même témoin* sans `@facs` n'est pas
attribuée arbitrairement ; aucune identification par ordre d'images.

## V0.9.1.3 — Mode page dans un texte synchronisé à part, lacunes

Dans un texte synchronisé à part (V0.9.1.1), un témoin sans JSON pour ce
texte mais qui a le texte (un `<pb edRef>` dans le texte, ou un
`<locus target>` vers l'un de ses éléments dans son `<witness>` du
`<listWit>`) est un témoin par pages. Sa page vient des seuls `<pb>` de ce
texte : l'ordre de l'édition ne dit rien de l'ordre d'un manuscrit. Avant
son premier `<pb>` dans le texte, il montre sa page de départ :

1. le `@from` de son `<locus from to target>` pour ce texte, rapproché des
   folios comme un `pb/@n` (même règle que `pb_folio`) ;
2. sinon la page qui précède, dans l'ordre de ses pages (zones d'une
   surface divisée comprises), celle de ce premier `<pb>`.

Dans le segment de l'édition (numérotation continue), rien ne change : la
page continue d'une partie à l'autre, dans l'ordre de l'édition.

Un témoin par pages en lacune (`<rdg wit="#C"><lacunaStart/></rdg>`)
garde la page de son dernier `<pb>`, avec le bandeau « Lacune » ; pendant
une lacune du pivot, les témoins par pages continuent de suivre leurs
`<pb>`.
