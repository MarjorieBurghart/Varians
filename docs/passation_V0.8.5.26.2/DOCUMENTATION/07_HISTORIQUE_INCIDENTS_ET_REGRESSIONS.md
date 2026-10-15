# 07 — Historique, décisions et incidents à ne pas répéter

## 1. Jalons antérieurs utiles à comprendre

| Version | Apport structurant |
|---|---|
| 0.4.2 / 0.5.x | Aperçu interne XSLT/CSS, validation XML/RELAX NG et complétion contextuelle |
| 0.7.x | Ressources indépendantes : images, ALTO, synchronisation facultative ; sources locales et IIIF |
| 0.8.4 | Distinction JSON présent / lignes réellement synchronisées |
| 0.8.5.9–.17 | Sécurité du crop multicolonnes, navigation mixte, respect du manifeste, ordre des témoins, rafraîchissement transactionnel |
| 0.8.5.18–.21 | Double page à zones et dispositions du poste de travail |
| 0.8.5.22–.23 | Repliage XML sûr puis surlignage bidirectionnel des paires |
| **0.8.5.24** | Géométrie PAGE/ALTO, polygones, recadrage web et doubles pages |
| **0.8.5.25** | Chargements IIIF adaptatifs, régions, fallback et annulation |
| **0.8.5.25.1** | Correspondance de folios TEI/Canvas et page physique du viewer |
| **0.8.5.25.2** | Navigation au clic, notes et affichage de la ligne active |
| **0.8.5.25.3** | **Parité de l'index global `<lb/>` pivot entre web et desktop** |
| **0.8.5.26** | Refresh RNG A01, noms d'attributs A02, recherche plein texte médiévale A03 |
| **0.8.5.26.1** | Recherche sans case globale, ordre/visibilité des témoins à l'export |
| **0.8.5.26.2** | **Invalidation robuste des erreurs RELAX NG par révision Qt** |

Ce tableau est une synthèse ; les notes `PASSATION_V0_8_5_*` et les rapports `TEST_REPORT_V0_8_5_*` contenus dans la distribution précisent dates et limites. L'application et son projet d'exemple ont évolué bien au-delà des titres historiques des documents.

## 2. Incident majeur : le viewer n'affichait plus correctement les lignes

Après les améliorations de géométrie/IIIF, les images s'affichaient d'abord en pages complètes ; après des correctifs, elles s'affichaient en mode lignes mais un clic dans le texte ne suivait pas correctement les autres manuscrits. Les corrections successives de clic ou de repérage visuel n'ont pas suffi. **Enseignement : ne pas multiplier des patches sur les effets visibles sans comparer la chaîne de données desktop/web**.

La cause structurelle identifiée en 0.8.5.25.3 : le viewer reconstruisait les identifiants des lignes à partir de `<pb/>` et de la numérotation par page, alors que l'éditeur utilisait l'ordre global des `<lb edRef="#pivot"/>` et les clés **physiques réelles** du JSON. Cette divergence et la suppression de lignes pivot au moment de l'export causaient des `data-line` incohérents.

Un script de diagnostic Spyder sur un ancien `viewer.html` réel a trouvé 701 segments non ancrés et 41 clés textuelles absentes du pivot. Après régénération réelle depuis 0.8.5.25.3, le diagnostic est passé à 0 segment sans clé, 0 clé absente, 226 `<lb/>` pour 226 lignes physiques, avec retour utilisateur confirmant que la navigation semblait fonctionner. **Ne pas confondre ces constats historiques et un état permanent des fichiers manuscrits.**

La source HTML testée initialement n'était pas celle attendue de 0.8.5.25.3 : la nouvelle rubrique `meta.pivot_lb_index` était absente. Enseignement : vérifier le fichier réellement généré et les modules importés, particulièrement avec Spyder et plusieurs distributions extraites.

## 3. Incident distinct : page sans image Mu

Un diagnostic de l'export a repéré une page `BSB Clm 14713 4v` (`image.type=none`, un seul segment géométrique). L'utilisateur a confirmé que c'était un **défaut de données du projet**, non une anomalie du viewer. Un audit ne doit pas transformer tous les `image.type=none` en anomalies du code, ni inventer une URL IIIF.

## 4. Incident : références secondaires vers une clé physique absente

Un export réel récent a montré **une** référence inconnue chez F, A et L malgré un pivot texte désormais cohérent. L'utilisateur a signalé la suppression d'une ligne vide de Mu, explication plausible, **non confirmée sans inspection des clés exactes**. Le bon comportement est de signaler les liens orphelins, d'en déterminer la provenance et de ne pas reconstituer des correspondances par position ni par ressemblance de texte.

## 5. Incident : anciennes erreurs RELAX NG qui reviennent

A01 dans la version 0.8.5.26 a réactualisé la liste, mais une dépendance à la visibilité du panneau demeurait. Après correction pendant que le panneau était masqué, un résultat ancien pouvait réapparaître. La V0.8.5.26.2 invalide l'état à chaque nouvelle révision Qt, relance même si le panneau est masqué après première utilisation, rejette les calculs tardifs et contrôle la réouverture. Le retour utilisateur est positif : **« ça semble résolu »** ; ne pas le décrire comme une preuve de robustesse formelle universelle.

## 6. Demandes d'apparat critique et nouvelle feuille de route

L'utilisateur a explicitement abandonné les modèles/générateurs d'apparat critique, conservant les fonctions XML générales. La feuille de route proposée à l'automne 2026 (personnalisation XSLT/CSS de l'export, audit intégral et empaquetage, etc.) a ensuite été **remise à zéro** à sa demande. Des propositions et documents peuvent subsister dans les sources à valeur historique ; **aucune n'est programmée** jusqu'à nouvelle décision.

## 7. Pratiques anti-régression

- Comparer une version connue fonctionnelle **et** la nouvelle, par diff ciblé des fonctions touchées.
- Reconstituer un projet synthétique qui porte les propriétés réelles de l'incident (IDs techniques, folio, multiples zones, numéros de lignes non consécutifs), pas uniquement le projet T1/T2/P de démonstration.
- Examiner la sérialisation des clés dans l'export avant la partie graphique.
- Documenter ce qui est vérifié par des tests Python, Node, Chromium, Qt simulé ou une session Windows réelle ; ces niveaux ne sont pas interchangeables.
- Lorsqu'un utilisateur dit que le résultat ne fonctionne pas, reprendre le diagnostic plutôt que d'empiler des correctifs non démontrés.
