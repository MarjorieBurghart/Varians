# 03 — Édition XML, RELAX NG, complétion et diagnostics

## 1. Modules et mécanismes

- `editeur_tei.py::CodeEditor` : composant Qt du texte source, coloration, suggestions, paires, repliage et opérations interactives.
- `editeur_tei.py::MainWindow` : orchestration des panneaux, de F8, de la résolution du schéma, des timers et des actions de sauvegarde.
- `schema_resolution.py` : politique du schéma du projet et `<?xml-model?>` ; résolution des ressources, cache.
- `relaxng_validation.py` : lxml, chargement et validation du RNG, données d'erreurs structurées et cache de schémas.
- `rng_completion.py` : modèle des éléments/attributs/valeurs permis selon la position du curseur et la structure RELAX NG, avec traitements de cas partiellement saisis.
- `custom_completion.py` : extensions de complétion par règles de projet, sans déroger au contrat scientifique du document.
- `xml_tag_pairs.py` : fermeture suggérée, appariement lexical prudent, renommage couplé et mise en évidence dans les deux sens.
- `xml_folding.py` : repliage des blocs visuels sans suppression de caractères dans la TEI.
- `xpath_search.py`, `selection_sync.py`, `tei_formatter.py` : requêtes XPath, liens aperçu/texte et formatage à espaces significatifs protégés.

## 2. Contrat A01 dans V0.8.5.26.2 : cycle des erreurs RNG

Le bogue observé en production : des erreurs déjà corrigées réapparaissaient dans la liste de validation. Le correctif ne consiste **pas** à éliminer des messages ressemblant aux anciens : il invalide les résultats par **révision exacte de `QTextDocument`**.

**Séquence d'exécution :**

1. Un changement du document Qt survient (saisie, `QTextCursor`, annuler/refaire). Les notifications du widget et du document sont dédupliquées par `_last_processed_edit_revision`.
2. `MainWindow._text_changed` marque le travail modifié, invalide le résultat RNG et sa révision, efface immédiatement les lignes du panneau et affiche un état « résultats périmés ».
3. Si la surveillance a été activée par un premier passage au panneau, `rng_refresh_timer` démarre pour **1 250 ms**. Le timer ne dépend plus de la visibilité au moment du changement : l'utilisateur peut être dans XPath ou avoir masqué le panneau.
4. `MainWindow._auto_refresh_rng` revalide la révision courante, sans relancer lorsque le cache concerne déjà celle-ci.
5. `validate_relaxng_document` est protégé contre les appels récursifs par `_rng_validation_in_progress`, puis délègue à `_validate_relaxng_document_impl`.
6. Après résolution du schéma **et après** validation lxml, le code revérifie `revision == editor.document().revision()`. Si la révision a changé entretemps, **le résultat est rejeté**, et un nouveau contrôle est planifié (court délai de rattrapage).
7. Seuls les résultats à jour renseignent `_last_rng_result`, `_last_rng_revision`, `_last_rng_schema_token`, le résumé et le tableau. En cas de document valide, le tableau est vidé et l'état approprié affiché.
8. `show_validation_panel` réactive la surveillance et déclenche immédiatement une validation si la révision n'est pas à jour ; F8 reste le déclencheur manuel et `refresh_schema_cache` recharge volontairement les données de schéma.

**Ne pas régresser** sur la distinction entre résultat « invalide », schéma introuvable/invalide, `lxml` absent, absence de `xml-model`, validation désactivée, XML mal formé et document XML valide mais non conforme au RNG. Tous ces cas disposent de messages et de changements d'état propres.

## 3. Contrat A02 : complétion d'attributs pendant la frappe

Lorsqu'un curseur se trouve dans le **tag ouvrant d'un élément**, la frappe initiale d'un nom d'attribut peut proposer les attributs autorisés par le RNG, filtrés selon le préfixe saisi. Exemple : `<rdg wi` → `wit` si autorisé. L'insertion peut produire `wit=""` avec curseur entre les guillemets. Les suggestions prennent en compte l'élément/contexte, les attributs déjà présents, les préfixes XML et l'état syntaxique partiellement saisi.

`Ctrl+Espace` doit rester un moyen volontaire de demander la complétion contextuelle, et la liste des éléments ne doit **pas** être proposée lorsqu'on est au milieu des attributs d'un tag ouvrant. Les valeurs à listes finies restent un cas distinct des **noms d'attributs**. Ne pas confondre la simple autocomplétion lexicale et l'autorisation réelle par RELAX NG.

Les règles métier du schéma et les extensions projet peuvent être compilées/mémorisées dans le cache ; le changement de schéma ou d'entité importante doit invalider leur contexte. Pour document temporairement mal formé, la complétion reste conservatrice : éviter de supposer un parent ou un attribut non démontré.

## 4. Syntaxe et sécurité XML

- Balises ouvrantes et fermantes homonymes imbriquées : l'appariement repose sur une analyse lexicale prudente, pas sur la première sous-chaîne homonyme rencontrée.
- Commentaires, CDATA, préfixes, autofermantes, tags croisés et balises provisoirement incomplètes exigent la prudence. **Ne pas surligner une correspondance incertaine.**
- Le surlignage est un effet visuel `ExtraSelection`, jamais une modification du texte ou une sélection réelle de plage.
- Le repliage masque des `QTextBlock` mais laisse les caractères intacts. Toute navigation/recherche vers une ligne masquée doit la rendre visible.
- Le formatage doit préserver `xml:space="preserve"`, la sémantique de `<lb break="no"/>` et les espaces significatifs ; éviter la normalisation XML destructrice.
- `xml-model` et schéma explicite possèdent des règles de compatibilité : consulter `RELAXNG_VALIDATION.md`, `RNG_COMPLETION.md`, `PROJECT_MANAGEMENT.md`, et la source comme autorité finale.

## 5. Tests reproductibles

```bash
python -m pytest -q tests/test_v085262_rng_panel_refresh.py
python -m pytest -q tests/test_v08526_interim_features.py
python -m pytest -q tests/test_rng_completion.py tests/test_rng_context_cache.py
python -m pytest -q tests/test_relaxng_validation.py
python -m pytest -q tests/test_v08523_bidirectional_tag_highlight.py tests/test_v08522_xml_folding.py
```

Les tests de cycle V0.8.5.26.2 instrumentent les méthodes réellement présentes dans `editeur_tei.py`, mais utilisent des doublures pour les objets Qt ; **ils ne prouvent pas l'ergonomie native PySide6**. Le retour utilisateur après installation a confirmé que la réapparition des anciennes erreurs *semblait* résolue. Ne transformer ni cette observation ni les tests simulés en garantie universelle.

## 6. Matrice manuelle de réception Windows

1. Introduire une erreur RNG, F8, vérifier message et position.
2. Corriger **panneau ouvert** ; vérifier suppression et validation après l'inactivité.
3. Introduire une erreur, F8, passer dans XPath ou masquer ; corriger ; rouvrir : aucune ancienne erreur.
4. Faire annuler/refaire, puis corriger plusieurs erreurs en succession rapide ; vérifier la bonne révision finale.
5. Modifier le document pendant une résolution de schéma lente ; aucun ancien résultat ne doit réapparaître.
6. Changer de projet, changer de politique de schéma, revenir : aucune erreur d'un projet précédent.
7. Dans `<rdg wi`, vérifier que `wit` apparaît, que `Ctrl+Espace` reste opérant et que l'éditeur ne propose pas les éléments enfants comme attributs.
8. Tester les préfixes `xml:`, les doublons d'attribut, les guillemets, les valeurs énumérées, un schéma absent et un XML temporairement incomplet.

## 7. Risques de changement

Ne pas réintroduire la dépendance « validation automatique seulement quand `validation_panel.isVisible()` ». Ne pas publier de résultat lxml sans vérification de `QTextDocument.revision()`. Ne pas invalider la pile d'annulation, déplacer le curseur ni réécrire le document pendant une validation. Toute optimisation de debounce ou de cache exige au moins un test de concurrence logique révision N→N+1→N+2.
