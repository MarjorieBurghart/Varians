# 09 — Gouvernance de la reprise et feuille de route ouverte

## 1. Statut au 15 octobre 2026

**Base de référence : Varians V0.8.5.26.2.** Sa synchronisation web, son ordre/visibilité des témoins, son moteur de recherche à graphies médiévales, la complétion des noms d'attributs XML et le rafraîchissement corrigé du panneau RELAX NG sont les jalons conservés. L'utilisateur a confirmé le fonctionnement du viewer web et a indiqué que le défaut RNG semble résolu. Aucune modification supplémentaire du code n'est décidée dans la présente passation.

**La roadmap antérieure est suspendue intégralement.** La séquence proposée « version XSLT/CSS → audit → empaquetage » n'est plus une consigne. Les notes de conception correspondantes sont conservées pour référence, pas pour exécution automatique.

## 2. Principe d'entrée d'un nouveau chantier

Chaque nouvelle demande devra être discutée avec l'utilisateur avant codage. La fiche de décision recommandée contient :

- **Identifiant** de la demande et formulation exacte de l'utilisateur ;
- problème constaté, objectif recherché et preuve disponible (cas de reproduction, fichiers, captures) ;
- domaines/modèles touchés et risque scientifique de transformation non demandée ;
- comportement attendu à l'écran et sur disque ;
- exclusions explicites, limites de portabilité et droits des images ;
- critère d'acceptation vérifiable (tests Python, HTML, Qt natif, corpus réel) ;
- impact sur les sept langues/aides et sur les documents de transmission ;
- numéro de version envisagé **seulement après choix**, non inféré de vieux tableaux.

## 3. Critères d'une version livrable

Une version ne doit pas être présentée comme stable uniquement parce que les tests statiques passent. Conditions recommandées :

1. Sources complètes et même projet de démonstration, tous fichiers utiles présents ; données scientifiques inchangées sauf décision explicite.
2. Tests de régression pertinents et contrôle d'absence de nouveaux échecs ; couverture du cas déclencheur de la correction.
3. Vérification des points transversaux : sauvegarde, `lb`/`base_keys`, images et PAGE/ALTO, dispositions, panneau RNG et recherche, selon périmètre.
4. Compilation Python ; syntaxe JS et tests navigateur si viewer affecté ; essai PySide6 natif quand l'UI est affectée.
5. Traductions/HTML d'aide en sept langues à jour, sans clé manquante.
6. ZIP complet CRC vérifié, SHA-256 fourni, inventaire de provenance, documentation actuelle, informations sur limites de tests.
7. Validation utilisateur sur le corpus réel ou au moins un scénario représentatif avant promotion en référence.

## 4. État des risques ouverts — observation, pas agenda

- Tests GUI multiplateformes natifs moins complets que les tests logiques.
- Fichiers de recherche/alignement peuvent contenir des références historiques orphelines, à diagnostiquer sans réparation automatique.
- Disponibilité et droit d'usage des images IIIF hors du contrôle du logiciel.
- Gros modules historiques difficiles à refondre sans tests de caractérisation.
- Docs historiques portant des promesses anciennement envisagées, désormais sans valeur prescriptive.

Ces constats servent à la vigilance de maintenance. Ils ne constituent **ni une demande ni une priorité de développement**.

## 5. Communication de reprise

Le repreneur doit expliciter pour chaque résultat : « implémenté », « testé automatiquement », « testé dans un navigateur synthétique », « testé par l'utilisateur Windows », « documenté comme hypothèse » ou « proposé sans décision ». En particulier, des compteurs de tests ne prouvent pas la validité de toutes les correspondances scientifiques d'un projet réel ; un `image.type=none` n'est pas forcément un bug du code ; une ancienne exportation peut ne pas refléter la nouvelle version.

## 6. Première session conseillée au repreneur

1. Vérifier le ZIP original, les versions et le rapport de tests de ce dossier ; ne pas modifier les sources.
2. Exécuter le projet de démonstration, ouvrir la TEI, inspecter quelques panneaux et générer un viewer frais.
3. Parcourir `MainWindow.sync_panels_to_cursor`, `flatten_primary`, `web_viewer.tei_line_anchors`, `build_dataset`, et les diagnostics `pivot_lb_index` pour comprendre le contrat le plus délicat.
4. Tester délibérément une erreur RNG corrigée panneau visible/masqué et une suggestion d'attribut, comme premiers parcours Qt.
5. Reproduire un viewer avec pivot masqué et secondaires affichés, puis un clic de recherche médiévale conduisant à la bonne ligne.
6. **Demander la nouvelle feuille de route au porteur du projet**, sans reprendre celle des documents anciens.

## 7. Points à ne pas interpréter comme des autorisations

Le fait que des documents de conception décrivent des profils d'export personnalisés, un audit scientifique, un système de génération d'apparat ou une migration du format JSON ne signifie pas qu'ils sont prévus. Ne pas modifier la TEI, ni les archives/manuscrits, pour satisfaire des tests de démonstration sans autorisation. La reprise doit préserver l'autonomie scientifique de l'éditeur et celle de Varians-Synchro.
