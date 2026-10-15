# 05 — Viewer web : contrat complet, synchronisation, recherche et publication

## 1. Fonction et artefacts

Le viewer web est généré depuis le projet par `web_viewer/generator.py`; son point d'entrée `generate(project_path, output=None, *, display_witness_ids=None)` appelle `load_project`, `build_dataset`, `package_local_images`, `make_html`, puis écrit `viewer.html` en UTF-8. Le HTML intègre des scripts JS de production `geometry.js`, `iiif.js` et `fulltext_search.js` ainsi que ses données JSON. `legacy_v11_core.py` extrait la lecture TEI et les références éditoriales.

Commande autonome :

```bash
python -m web_viewer.generator project.xml
```

Depuis `MainWindow.generate_web_viewer`, l'éditeur vérifie que l'édition courante correspond au projet, sauvegarde les modifications utiles puis transmet `display_witness_ids` d'après l'ordre et la visibilité **effectifs** des panneaux. L'export autonome CLI sans cette liste reprend tous les témoins de la configuration scientifique.

## 2. Format conceptuel des données exportées

Le jeu de données inclut :

- `meta` : titre, pivot, nombre de lignes, indicateurs de mode lignes, `display_witnesses` et métriques de synchronisation (`pivot_lb_index`, erreurs de clés/segments), dépendances IIIF externes et avertissements ;
- `witnesses` : ID, libellé, rôle base/secondary, état `line_sync`, diagnostics, pages, images, lignes, bbox, polygones et `base_keys` ;
- `reading_document` ou représentation de lecture : blocs/segments de texte annotés par `line_key`, positions et références à notes/variantes ;
- métadonnées de la navigation `<pb>`, zones de doubles pages et traductions d'interface.

Les noms des champs exacts doivent être repris du JSON construit dans `build_dataset` ; éviter de considérer cette liste pédagogique comme un schéma figé. Les clés calculées ne remplacent **jamais** les identifiants physiques d'origine.

## 3. Chaîne de synchronisation à ne jamais casser

```text
<li ...> / <lb edRef="#Mu"/> —(rang dans la source TEI)→
ligne physique effective JSON Mu —(clé page_id::line)→
`base_keys` des JSON secondaires F/A/L —(choix de ligne liée)→
rectangle/polygone/image de chacun des témoins —(JS)→
panneaux du viewer visibles et recadrés
```

La correction structurelle V0.8.5.25.3 a rendu ce contrat identique à celui de l'éditeur. Les marqueurs `pb/@n` sont des libellés éditoriaux et **ne doivent pas** servir à recalculer des `line` physiques. `PageResolver` peut interpréter `pb/@facs` pour la navigation par folio/zone, mais cela demeure distinct du chaînage `<lb/>` vers le JSON pivot.

`meta.pivot_lb_index` doit être examiné en priorité lors d'une régression (nombre de `<lb>` versus lignes physiques, count_match, éléments non associés). Un clic sur une clé `data-line` inconnue ne doit pas déclencher un déplacement arbitraire. Si la clé existe et est liée à des lignes des secondaires, la mise à jour des panneaux doit fonctionner même avec le pivot techniquement présent mais visuellement masqué.

**Incident historique majeur :** la V0.8.5.25.1/.2 pouvait afficher les bonnes images en mode lignes sans déplacer correctement les autres témoins au clic ; les tests synthétiques passaient parce qu'ils n'avaient pas reproduit les identifiants de pages du corpus réel. Un ancien `viewer.html` resté dans le dossier peut se faire passer pour une version récente : **toujours régénérer le fichier et vérifier les métadonnées internes avant de conclure à une régression**.

## 4. Paramètres de présentation et pivot caché

`display_witness_ids` :

- `None` ⇒ tous les témoins dans l'ordre de `project.xml` ;
- liste non vide ⇒ les IDs reconnus dans l'ordre exact demandé (pas l'ordre source) ;
- liste vide ⇒ aucun panneau manuscrit affiché.

Les témoins secondaires masqués ne sont pas publiés. Le pivot masqué reste dans les **données techniques minimales nécessaires au calcul de l'index**, mais les liens vers ses images sont retirés, et aucun panneau n'est affiché. Ce comportement est délibéré : supprimer intégralement le pivot casserait les `base_keys` secondaires. L'export d'un dossier existant peut laisser derrière lui d'anciennes images non utilisées ; aucun nettoyage destructif automatique.

## 5. Recherche plein texte A03

`fulltext_search.js` construit un index à partir du **texte de lecture affiché**. Il conserve pour chaque unité d'origine un lien vers sa position (`docPos`, offset UTF-16, `lineKey`). La recherche peut traverser plusieurs segments de balisage TEI sans perdre les offsets. Les occurrences sont affichées dans une liste, surlignées sans altérer la TEI, et la sélection relaie une clé de ligne existante au viewer.

**Modes de comparaison :** sans case cochée, recherche exacte insensible à la casse ; sinon trois équivalences indépendantes **u/v**, **i/j**, **c/t**. Le libellé « Medieval spellings » / « Graphies médiévales » est **un texte d'intitulé et non une quatrième case à cocher** (correction V0.8.5.26.1). `c/t` peut produire beaucoup de faux positifs : ne l'imposer ni globalement ni sans contrôle utilisateur.

Le texte original n'est pas réécrit ; `splitText` injecte uniquement les surlignages `<mark>` avec échappement du contenu, et les attributs `data-line` des éléments demeurent inchangés. Les recherches sont limitées à 5 000 résultats. Les popovers d'annotation et le texte OCR brut non affiché ne sont pas indexés par cette fonction. Un résultat sans clé valide utilise un fallback prudent (pas de synchronisation inventée).

## 6. Géométrie et IIIF

`geometry.js` convertit les repères des sommets et du crop ; `iiif.js` construit la liste de requêtes par taille/région/version d'API et gère replis et annulation. Une image entière obtenue en repli peut être recadrée localement, tandis qu'une réponse régionale fournit directement la zone utile ; le SVG conserve des repères homogènes. Les `image.type=none` correspondent parfois à de vraies données absentes et **ne doivent pas** être systématiquement corrigés comme des bugs d'export.

## 7. Aperçu XSLT interne ≠ viewer web

L'éditeur offre déjà un aperçu interne basé sur XSLT/CSS, avec `rendering/@xsltMode`, `@xslt`, `@css` et `customElements`. Le viewer web a sa **propre** fabrication HTML/JS, car il exige des ancres scientifiques, des événements, des images et des polygones. Les maquettes historiques de personnalisation de l'export ne sont pas des fonctions livrées ni une roadmap décidée.

## 8. Tests et recettes obligatoires

```bash
python -m pytest -q tests/test_v085253_pivot_lb_contract.py
python -m pytest -q tests/test_v085261_web_viewer_presentation.py
python -m pytest -q tests/test_v08526_interim_features.py
python -m pytest -q tests/test_v08524_web_geometry.py tests/test_v08525_iiif_web.py
python -m web_viewer.generator project.xml
```

Cas de recette utilisateur : clics sur plusieurs pages éloignées (Mu, F, A, L), note/variante/référence, pivot masqué, témoin sans lien en mode pages, images absentes, régions IIIF refusées, doubles pages, recherche variante/forme exacte, tous témoins masqués, nouvelles préférences QSettings. Recueillir le HTML **généré dans l'environnement testé**, l'ID de version réel du code et les diagnostics d'index, jamais simplement le titre annoncé de l'archive.
