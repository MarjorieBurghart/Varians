# VARIANS V0.8.5.17 — DIAGNOSTIC DES TÉMOINS ET ACTUALISATION

## Principe scientifique

Les images, les ALTO/PAGE et les JSON de synchronisation sont des couches indépendantes.
Un ALTO ne prouve pas l'existence d'une correspondance avec le manuscrit pivot ;
seuls des `base_keys` pointant vers de véritables lignes du JSON pivot permettent
de considérer un lien comme reconnu. Le rôle technique de pivot ne constitue
pas un choix de manuscrit de base au sens de la critique textuelle.

## Interface

* `Affichage > État des témoins…` : tableau par témoin (navigation,
  pages, sources d'images, lignes, liens valides, incohérences). Le rapport
  peut être copié sans recopier les textes OCR, transcriptions ou données
  personnelles des chemins locaux.
* `Affichage > Actualiser les synchronisations…` (`Ctrl+Shift+R`) :
  rechargement des JSON/ALTO/PAGE dans l'édition ouverte. La commande
  recharge les copies locales IIIF si elles sont configurées et reconstruit
  leurs associations sans réécrire aucun fichier d'origine.

## Architecture

`witness_resource_refresh.py` ne dépend pas de Qt :

* `read_alignment_json()` refuse les JSON mal formés ou à structure invalide.
* `assemble_resources(project)` prépare tous les caches, index et associations
  pour TOUS les témoins. Si l'un échoue, aucun panneau n'est remplacé.
* `diagnostic_rows(project, state)` renvoie des codes d'anomalies indépendants
  de la langue. Les traductions sont résolues uniquement dans l'interface.
* `changed_witnesses(before, after)` détecte notamment la modification des
  associations même lorsque le nombre de lignes reste identique.

L'instance courante de `MainWindow` garde le texte TEI, le document Qt,
sa pile d'annulations et les `ManuscriptPanel` existants. `refresh_witness_synchronizations()`
remplace uniquement l'état des ressources APRES une construction complète et
une éventuelle confirmation. Les données rechargées sont ensuite appliquées
aux panneaux préexistants ; leurs états d'affichage sont préservés autant que possible.

## Garanties et limites

* Aucun remplacement de `project.xml`, de la TEI, des fichiers de synchronisation,
  des images ou des ALTO/PAGE.
* La commande utilise les chemins DÉJÀ déclarés dans les paramètres du projet :
  elle ne recherche pas automatiquement un fichier récemment déplacé.
* Les fichiers JSON incorrects n'effacent pas les caches actuellement chargés.
* Les images IIIF distantes restent soumises aux serveurs et au cache existant.
* Les vérifications automatisées ne remplacent pas les essais PySide6 sous Windows.
* Les options de navigation par pages restent possibles pour les témoins
  sans synchronisation ; elles ne sont pas signalées comme une corruption.

## Tests

`tests/test_v08517_diagnostic_refresh.py` : témoin pivot, `base_keys`
valables/inconnus, décompte sans lignes OCR, mismatch de pivot, défaut
JSON, rechargement à nombre constant, images locales, `keys816`, sept langues.
