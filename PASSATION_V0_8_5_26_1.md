# VARIANS — PASSATION V0.8.5.26.1 (ERGONOMIE DE LA RECHERCHE ET ORDRE DES TÉMOINS)

**Base vérifiée : V0.8.5.26. Cette version reste une correction intermédiaire, la nouvelle roadmap n'étant pas encore définie.**

## Retours utilisateur (14 octobre 2026)

Les fonctions A01 (rafraîchissement de la validation RELAX NG) et A02 (complétion des attributs XML) ont été essayées et fonctionnent selon l'utilisateur. A03 (recherche plein texte) fonctionne, mais l'ancienne case globale « Medieval spellings » était redondante avec les trois cases u/v, i/j et c/t. L'utilisateur souhaite également reprendre dans le viewer exporté les témoins visibles et leur ordre tels que configurés dans l'éditeur de bureau.

## Modifications réalisées

1. **Recherche** : suppression du bouton à cocher global `searchMedieval` ; l'intitulé `viewer.search.medieval` reste traduit comme texte non cliquable. Les trois cases `searchUV`, `searchIJ`, `searchCT` sont initialement décochées. Chaque case active immédiatement sa propre équivalence graphique ; sans aucune case, la recherche est exacte (insensible à la casse). Les résultats continuent de conserver les offsets, les surlignages et les clés des lignes TEI, sans modification du texte.
2. **Ordre et visibilité à la publication depuis l'éditeur** : `MainWindow.generate_web_viewer` transmet la liste courante ordonnée issue de `_witness_display_order` filtrée par `_visible_witness_ids`. Ces préférences demeurent enregistrées dans `QSettings` par projet et ne sont jamais recopiées dans `project.xml`.
3. **Générateur indépendant de Qt** : `web_viewer.generator.generate(project_path, ..., display_witness_ids=...)`, puis `build_dataset`, acceptent cette liste facultative. L'absence de paramètre (`None`) reproduit le comportement historique CLI : tous les témoins, dans l'ordre scientifique du projet. Le tableau vide signifie aucun témoin visible, et non « tous ».
4. **Données exportées** : `meta.display_witnesses` contient l'ordre d'affichage exact. Les témoins secondaires masqués sont exclus du JSON de l'export. Le pivot reste dans ce JSON comme témoin *technique* même lorsqu'il est masqué, indispensable à la correspondance `<lb edRef="#pivot"/>` → clé physique → `base_keys`. Dans ce cas, ses liens vers les images sont retirés de l'export et le navigateur n'affiche aucun panneau correspondant au pivot. Aucun lien scientifique n'est créé ou recalculé.
5. **Viewer web** : tous les panneaux sont construits à partir de `meta.display_witnesses` ; les mises à jour de langue et la synchronisation ne tentent pas de dessiner des panneaux masqués. La navigation des lignes reste fondée sur le pivot technique.

## Limites, portabilité et précautions

- Une exportation par commande `python -m web_viewer.generator project.xml` sans liste explicite continue à afficher tous les témoins ; le générateur autonome ne peut pas reconstituer de manière fiable l'état de l'interface graphique en cours d'exécution. Utiliser la commande « Générer le viewer web » de Varians pour reprendre les panneaux visibles à cet instant.
- Les fichiers image copiés lors **d'un export antérieur** peuvent rester présents dans le dossier `web_output/images`, même s'ils ne sont plus référencés par le nouveau HTML. Ne jamais présenter la totalité d'un ancien dossier de sortie comme un paquet filtré ; réaliser un export dans un dossier propre pour diffuser uniquement les images nécessaires. La présente version ne supprime jamais automatiquement ces fichiers antérieurs.
- Les résultats de recherche n'infèrent jamais de nouvelles correspondances, y compris si un témoin est masqué.
- **Cibles** : Windows, macOS, Linux ; aucune dépendance Windows dans le moteur. L'éditeur Qt natif n'a pas été testé dans l'environnement de build (absence de PySide6), mais les parcours JS ont été testés dans Chromium sur un document de synthèse.
- Les sept langues (fr, en, de, ja, cs, it, ru) et leurs aides sont maintenues et actualisées ; les textes d'interface existants pour `viewer.search.medieval` restent utilisés.

## Vérifications reproductibles

- `python -m pytest -q --disable-warnings`
- `python -m compileall -q .`
- `PYTHONPATH=. python tests/manual_v085261_presentation_chromium.py`
- `python -m web_viewer.generator project.xml`
- Les nouveaux tests `tests/test_v085261_web_viewer_presentation.py` couvrent l'ordre, la visibilité, les duplications, les identifiants invalides, le pivot masqué, l'absence de témoins visibles, l'export autonome et la connexion avec les préférences d'interface. Les tests hérités de V0.8.5.26 restent actifs.
- L'état de validation précis se trouve dans `TEST_REPORT_V0_8_5_26_1.txt`.

## Essai utilisateur recommandé

1. Dans Varians, choisir par exemple F, A puis L, masquer Mu et N ; exporter depuis le bouton de l'éditeur et vérifier F → A → L (pas de carte Mu/N).
2. Cliquer deux passages éloignés du texte : la synchronisation vers F/A/L doit fonctionner malgré le pivot Mu masqué.
3. Rechercher `servvs` dans `seruus`, d'abord sans case (aucun résultat), puis avec u/v seulement (résultat). Décocher u/v et vérifier le retour exact ; essayer i/j et c/t indépendamment.
4. Réafficher Mu dans l'éditeur, changer l'ordre, régénérer le HTML et vérifier le nouvel ordre.
