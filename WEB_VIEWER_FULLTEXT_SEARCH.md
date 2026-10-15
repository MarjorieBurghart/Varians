# Viewer web — moteur de recherche plein texte A03

La bibliothèque `web_viewer/fulltext_search.js` est embarquée directement dans le HTML généré par `web_viewer/generator.py` ; aucun appel HTTP de recherche et aucun serveur ne sont nécessaires.

## Modèle d'index

`makeIndex(blocks)` conserve chaque paragraphe en texte visible et un tableau de positions source `(docPos, offset, lineKey)`. Le numéro `docPos` est le même que celui fourni à `segHTML()` ; il inclut les jalons non textuels pour éviter tout décalage. Un résultat fournit des segments de surlignage `(docPos,start,end)` et la clé réelle existante à laquelle il correspond, si elle existe.

La fonction `normalize(value, options)` applique la minuscule et éventuellement les substitutions réversibles par classes `{u,v}→u`, `{i,j}→i`, `{c,t}→c`. Les offsets restent indexés sur les unités UTF-16 du texte original, pas sur la chaîne normalisée ; un emoji ou une lettre dont la casse déplie plusieurs unités ne décale pas le résultat. Le texte TEI n'est jamais transformé sur disque.

`find()` renvoie jusqu'à 5 000 résultats ; `spansByPosition()` évite de parcourir tous les résultats pour chaque fragment DOM. `splitText()` insère uniquement des balises `<mark>` dans le HTML affiché, en échappant systématiquement le texte. Les attributs `data-line` des parents restent inchangés. `selectSearchResult()` appelle `selectLine()` uniquement pour des clés effectivement présentes dans `lineMap`; sinon il retombe sur la navigation de page existante.

## Restrictions volontaires

- Ne pas étendre le mode `c/t` à d'autres alternances présumées ; les faux positifs sont attendus et l'option doit rester explicite.
- La recherche indexe le texte de lecture affiché et les références éditoriales, pas les annotations ouvertes dans des popovers, ni les textes ALTO bruts.
- Aucun OCR ni base de données indépendante ne sont nécessaires.
- La recherche n'altère pas l'export scientifique ni les alignements éditoriaux.

## Addendum V0.8.5.26.1 (14 octobre 2026)

La case globale « Graphies médiévales » a été supprimée ; le moteur fonctionne en mode exact si u/v, i/j et c/t sont tous désactivés, et en mode médiéval pour les équivalences individuelles cochées, sans contrôle supplémentaire. Voir `PASSATION_V0_8_5_26_1.md`.
