# 01 — Architecture fonctionnelle, composants et flux

## 1. Système et philosophie

Varians est une application **Python 3 / PySide6 (Qt 6)**, complétée par `lxml` pour RELAX NG, XPath et transformations XSLT. Les modules indépendants de Qt portent progressivement la logique scientifique, afin de rester testables sans interface. La cible est **Windows, Linux et macOS** ; le poste usuel de validation utilisateur est Windows (parfois Spyder), mais aucun chemin absolu Windows ne doit entrer dans les modules cœur.

La racine `editeur_tei.py` demeure un contrôleur UI volumineux (voir l'index symbolique pour sa taille exacte). **Ne pas refondre en bloc ce fichier** : le séparer progressivement avec tests d'invariants et vérification des instances Qt. `web_viewer/generator.py` construit les données du viewer, `web_viewer/legacy_v11_core.py` extrait la lecture à partir de la TEI, et plusieurs scripts JS autonomes sont incorporés dans `viewer.html` au moment de sa génération. Le viewer ne réutilise **pas automatiquement** la feuille XSLT de l'aperçu interne.

## 2. Architecture en couches

```text
project.xml  --project_config.py--> ProjectConfig / WitnessConfig
    |                           |                 |
    |                           |             QSettings (vue locale seulement)
    v                           v
TEI source <---- MainWindow / CodeEditor ----> panneau RELAX NG / RNG / XPath
    |                     |                    (schema_resolution.py,
    |                     |                     relaxng_validation.py,
    |                     |                     rng_completion.py)
    |                     v
    |                ManuscriptPanel[]  <--- image_sources.py / iiif_* / alto_import.py
    |                     ^
    |                     |
    |             JSON sync du pivot + secondaires
    |
    +------> web_viewer/generator.py
                      |-- tei_line_anchors.py / page_resolver.py
                      |-- legacy_v11_core.py : lecture structurée
                      |-- geometry.js : repères et crop
                      |-- iiif.js : plan des images et replis
                      |-- fulltext_search.js : texte, offsets, équivalences
                      '--> web_output/viewer.html + images locales embarquées
```

Chaque bloc opère sur des ressources qui peuvent être absentes. Une image n'implique pas un OCR, un OCR n'implique pas des `base_keys`, et des balises TEI n'impliquent pas une image publiable.

## 3. Responsabilités de modules (principaux)

| Domaine | Modules | Points de contrôle |
|---|---|---|
| Interface XML | `editeur_tei.py` (`CodeEditor`, `MainWindow`) | selection, undo/redo, texte source inchangé lors des vues |
| Panneaux images | `editeur_tei.py` (`ManuscriptPanel`, `DetachedWitnessWindow`) | mêmes instances et zoom après réorganisation |
| Projets | `project_config.py`, `project_management.py`, `project_dialogs.py` | chemins relatifs, schéma, témoins facultatifs, rétrocompatibilité |
| Sauvegardes | `save_io.py` | écriture atomique, `.bak` |
| État scientifique d'alignement | `resource_state.py`, `witness_resource_refresh.py` | JSON brut, actualisation transactionnelle |
| ALTO/PAGE | `alto_import.py` | coordonnées et polygones non dégradés |
| IIIF et images | `image_sources.py`, `iiif_manifest.py`, `iiif_resolution.py`, `iiif_selection.py`, `iiif_local.py`, `iiif_download_manager.py` | Canvas exact, copies indexées, pas d'association par simple position |
| TEI fac-similé | `tei_facsimile.py`, `folio_navigation.py`, `tei_pivot_scaffold.py` | surface, graphic, zones et `pb/@facs` |
| XML et schema | `xml_tag_pairs.py`, `xml_folding.py`, `rng_completion.py`, `schema_resolution.py`, `relaxng_validation.py`, `custom_completion.py` | contexte lexical et absence de suggestion incertaine |
| Aperçu interne | `selection_sync.py`, `tei_formatter.py`, XSLT et CSS dans `rendering/` | `xml:space`, `<lb break="no"/>`, édition inchangée |
| Export web | `web_viewer/*` | clés physiques, visibilité, images et HTML autonome |
| Langues | `i18n.py`, `i18n/*.xml`, `help/*.html` | sept variantes cohérentes |

## 4. Entrée et démarrage

`editeur_tei.py::main()` initialise l'application, la fenêtre de bienvenue ou le dernier projet selon QSettings. Il est possible de lancer directement `python editeur_tei.py project.xml`. L'édition du projet d'exemple, T1/T2/P, n'est **pas** celle des manuscrits réels Mu/F/A/N/L de l'utilisateur.

Les chemins absolus ne sont admis dans les projets anciens que pour la compatibilité ; les nouveaux projets doivent privilégier les chemins relatifs, résolus par `project_config.py`. Ne pas créer de migration automatique destructive.

## 5. Cycle d'un projet et sources de vérité

1. `project_config.load_project` lit la configuration et identifie le pivot par ID.
2. Le chargement assemble les caches JSON, les images et la géométrie ALTO/PAGE **sans ajouter des liaisons intertémoins non établies**.
3. Les ressources IIIF sont résolues à partir des preuves explicites disponibles (service, Canvas, liens choisis, libellé exact unique, index local).
4. L'éditeur conserve une liste ordonnée de lignes physiques du pivot (`flatten_primary`). Les `<lb edRef="#pivot"/>` sont liés à cette liste par **leur ordinal source global**.
5. Les témoins secondaires utilisent leurs véritables `base_keys`; le contrôleur décide ligne ou page selon l'état effectif et la disponibilité du pivot.
6. Le viewer exporte ces mêmes contrats et les images qui sont publiables ; le texte enrichi reste relié aux mêmes clés.

## 6. Affichage desktop et préférences

Depuis la V0.8.5.21, l'interface prévoit pile verticale, panneaux horizontaux, grille deux colonnes et fenêtres détachées. `workspace_layout.py` normalise les décisions, tandis que `MainWindow._apply_witness_panel_order` réorganise les **mêmes objets `ManuscriptPanel`**. La liste et l'ordre des témoins sont stockés dans `QSettings` par chemin de projet ; ils ne changent pas l'ordre scientifique de `ProjectConfig.witnesses`.

La génération web déclenchée par l'interface utilise `self._witness_display_order` filtré par `self._visible_witness_ids`. Le générateur Python en CLI, qui n'a pas l'état Qt courant, prend tous les témoins en ordre de projet lorsque `display_witness_ids=None`. Le pivot masqué demeure un index technique sans panneau affiché.

## 7. Les changements qui appellent plusieurs modules

- Une modification du contrat de clé `page_id::line` touche l'éditeur, `resource_state`, l'indexeur TEI, le JSON et le viewer : **interdire un correctif isolé à un seul niveau**.
- Un changement du recadrage ou d'IIIF doit préserver les sommets PAGE, la géométrie des zones TEI et le choix de colonnes ; vérifier Python **et** JavaScript.
- Un changement de l'apparence ou de l'ordre des panneaux doit préserver `QSettings`, la synchronisation du pivot caché et le mode page des témoins non alignés.
- Un changement du panneau RELAX NG doit invalider les diagnostics obsolètes sans réécrire ni le RNG ni la TEI et sans dégrader Ctrl+S ou F8.

## 8. Dette et arbitrages

- `editeur_tei.py` et `web_viewer/legacy_v11_core.py` restent de gros fichiers historiques : refactorings *uniquement* avec tests de caractérisation d'abord.
- L'interface native Qt n'est pas intégralement couverte par des tests end-to-end multiplateformes.
- Le viewer dépend parfois de serveurs IIIF distants : un HTML autonome ne garantit pas un accès hors ligne aux images.
- Les esquisses historiques de personnalisation XSLT/CSS et d'audit de projet restent de la **documentation de conception**, pas un engagement de développement.
