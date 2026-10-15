# Varians — passation majeure de la branche V0.8.5.26.2

**Date de constitution du dossier : 15 octobre 2026.**  
**Base technique unique et immuable : `Varians_V0.8.5.26.2_Correctif_Validation_RELAX_NG_Complete.zip`.**  
**Nature du présent dossier : documentation et inventaire, sans nouvelle version du logiciel, ni modification de ses sources.**

## Message impératif au développeur repreneur

Varians est un éditeur TEI critique généraliste, particulièrement destiné aux éditions de textes médiévaux. Il réunit un éditeur XML/PySide6, une validation et complétion RELAX NG, un aperçu transformé par XSLT, XPath, des manuscrits-images (locaux ou IIIF), leurs coordonnées OCR ALTO/PAGE, une synchronisation physique intertémoins fournie par des JSON, et un viewer web exportable autonome. **Il ne produit pas automatiquement l'apparat critique**, et il est interdit d'inférer des correspondances entre témoins à partir de la proximité, du numéro de page ou d'un texte ressemblant.

La V0.8.5.26.2 constitue la **version de référence fonctionnelle désormais acceptée par l'utilisateur**, après vérifications de l'interface web, de la complétion XML et du correctif du panneau RELAX NG en pratique. Les 479 tests Python passés (2 ignorés) et le contrôle SHA-256 des sources ont également été reproduits indépendamment lors de la préparation de cette passation. Voir toutefois les limites de validation graphique et de corpus réel détaillées dans les rapports.

**La précédente feuille de route est abandonnée/suspendue**. Ne pas réactiver automatiquement les chantiers anciennement annoncés comme V0.8.5.26 XSLT/CSS, V0.8.6 audit, ou les assistants d'apparat. Une nouvelle feuille de route sera discutée avec l'utilisateur ; les documents historiques ne sont pas des commandes de développement.

## Contenu du paquet

- `BASE_SOURCE/` : **ZIP complet original V0.8.5.26.2 non modifié**, plus son empreinte.
- `DOCUMENTATION/` : dix dossiers techniques rédigés pour la reprise, articulés de l'architecture à la recette.
- `DOCUMENTATION/11_INDEX_SYMBOLIQUE_ET_TESTS.md` : index des symboles et des tests généré par analyse des vrais fichiers.
- `VERIFICATION/` : sortie pytest indépendante, rapports d'empreintes, manifeste et procédure de contrôle.
- `PASSATION_INTEGRALE.md` : compilation des documents thématiques, destinée à une lecture continue.

**Ordre de lecture recommandé :** 01 architecture → 02 formats et intégrité → 03 édition et validation → 04 images et géométrie → 05 export web et synchronisation → 06 maintenance/test → 07 incidents → 08 i18n/sécurité → 09 stratégie de reprise. L'index 11 permet ensuite de retrouver rapidement le code.

## Reprise rapide et reproductible

```bash
python -m venv .venv
# Activer le venv selon son système
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q --disable-warnings
python -m compileall -q .
python editeur_tei.py
# Ou : python editeur_tei.py /chemin/vers/project.xml
python -m web_viewer.generator project.xml
```

Exécuter les commandes **à la racine des sources extraites**, non dans le dossier documentaire. `PySide6` est requis pour l'application graphique ; `lxml` pour les schémas/XSLT ; `pytest` est une dépendance de développement. Les fichiers `.bat` fournis historiquement sont des commodités Windows, pas une dépendance de l'architecture.

## Invariants non négociables

1. **TEI éditoriale et données sources intouchées** par les réglages de vue et de publication ; sauvegarde et modifications scientifiques toujours explicites.
2. **Témoin pivot technique ≠ leçon de base philologique**. La clé physique canonique est `page_id::line` du JSON du pivot ; le secondaire n'est synchronisé que via ses `base_keys` vérifiables.
3. **Images ≠ géométrie OCR ≠ synchronisation** : ces couches sont indépendantes, facultatives et ne prouvent rien l'une sur l'autre.
4. **Parité obligatoire entre desktop et web sur les `<lb/>`** : l'ordre global des jalons pivot suit l'ordre réel des lignes du JSON pivot, et non une numérotation réinventée à chaque `<pb/>`.
5. **Polygones PAGE intacts**, coordonnées indépendantes des bitmaps d'aperçu, une image peut contenir deux parties avec deux `<zone>` TEI.
6. **Préférences locales dans QSettings**, format scientifique dans `project.xml` ; respecter ordre/visibilité de la vue à l'export depuis l'interface.
7. **Sept langues et sept aides** : fr, en, de, ja, cs, it, ru ; ajouter ou corriger les traductions dans leur contexte réel.
8. **Aucune affirmation de vérification graphique native** sans avoir effectivement exécuté PySide6 sur le système concerné.
9. Une version livrée = **archive complète**, tests et documentation mis à jour, bilan d'intégrité et liens réellement vérifiés.

## Hiérarchie des autorités en cas de contradiction

1. **Code et données effectifs du ZIP V0.8.5.26.2**.
2. Tests portant sur ce code et leur exécution indépendante.
3. Addenda de passation les plus récents (`PASSATION_V0_8_5_26_2.md`, etc.).
4. Contrats thématiques historiques, utiles mais parfois antérieurs à un correctif.
5. Suggestions d'anciennes roadmaps : *non actives*.

Des fichiers comme `CODE_MAP.md` portent encore dans leur titre des numéros anciens : ils sont historiquement cumulatifs. Ne pas confondre titre initial et état de la distribution.
