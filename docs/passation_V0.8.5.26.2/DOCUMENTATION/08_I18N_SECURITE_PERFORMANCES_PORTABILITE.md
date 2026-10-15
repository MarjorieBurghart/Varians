# 08 — Internationalisation, sécurité, performance, portabilité

## 1. Sept langues, source unique des traductions

Fichiers interface `i18n/fr.xml`, `en.xml`, `de.xml`, `ja.xml`, `cs.xml`, `it.xml`, `ru.xml` et aides `help/{lang}.html`. Les sept catalogues comptaient **629 messages distincts chacun** dans le rapport 0.8.5.26.2. `i18n.py` gère chargement, fallback et changement de langue ; les textes du viewer web sont également exportés et doivent provenir des mêmes politiques de traduction. Les commandes XML, la recherche médiévale et les diagnostics RNG exigent un vocabulaire précis, particulièrement pour les lettres u/v, i/j et c/t qui ne doivent pas être assimilées à une traduction typographique.

À chaque nouveau libellé : ajouter la même clé dans les sept catalogues, traduire selon sa fonction et non mot à mot, maintenir les sept aides, vérifier la substitution des paramètres (espaces réservés) et tester le changement de langue pendant qu'un projet est ouvert. Conserver la terminologie « témoin pivot » technique, « parties gauche/droite » pour les doubles pages, « lignes synchronisées » seulement quand les clés sont vérifiables.

## 2. Sécurité XML / XSLT

L'aperçu XSLT interne peut utiliser des feuilles intégrées ou de projet. `document()`, `xsl:include` et `xsl:import` créent potentiellement des accès au système ou au réseau ; le parseur XML avec `no_network=True` **ne sécurise pas nécessairement la totalité de l'exécution XSLT**. Tout futur mécanisme de profils d'export devrait définir explicitement des restrictions fichiers/réseau, inclure la protection contre l'expansion d'entités et les résolutions hors racine du projet. Une telle fonctionnalité n'est **pas** une décision de roadmap actuelle.

Les diagnostics et la recherche ne doivent pas écrire dans la source TEI. Les chemins relatifs traversant `..`, les symlinks externes, les collusions casse-insensible et les archives destinées à diffusion demandent une prudence particulière. Les URL d'image/HTML doivent être échappées ou filtrées par protocole ; le moteur IIIF JS possède des contrôles d'URL avant le chargement.

## 3. HTML et données exportées

- Sérialiser les données JSON de façon à empêcher qu'une chaîne de contenu termine prématurément un `<script>` HTML ; le générateur neutralise notamment `</`.
- Échapper titres, attributs, HTML de recherche et textes de balisage ; ne pas transformer une entrée TEI en script exécutable.
- Ne pas exposer un chemin local absolu dans un HTML public lorsqu'une ressource est manquante : messages d'export basés sur des noms de fichiers, pas sur le disque personnel de l'utilisateur.
- Un fichier `viewer.html` local peut contenir le contenu du corpus et des métadonnées : éviter sa diffusion sans autorisation.
- Les demandes IIIF sont dépendantes de droits, authentification, politiques de CORS et disponibilité. Une image distante n'est jamais garantie publiable à l'infini ni disponible offline.

## 4. Performance

- Le rafraîchissement RNG est temporisé : **1 250 ms** après changement (une fois surveillance activée), et met en cache les schémas ; ne pas recompiler le RNG à chaque caractère ni laisser publier un résultat périmé.
- La complétion se fonde sur des caches de contexte lexical/modèles RNG ; le changement de projet ou de schéma doit les invalider.
- Les images IIIF sont adaptées à la taille de la fenêtre/région et disposent de plans de repli, annulations et timeouts ; ne pas requérir systématiquement le Canvas entier en définition maximale.
- Les caches IIIF/ALTO et les copies locales reposent sur des index ; éviter de lire/recalculer le manifeste pour chaque sommet affiché.
- Le viewer recherche sur un index calculé depuis le texte visible ; `spansByPosition` évite un parcours intégral des résultats pour chaque fragment ; la limite de 5 000 occurrences est une protection, pas une spécification d'exhaustivité.

## 5. Portabilité

La compatibilité Windows/macOS/Linux doit être conservée dans les chemins (Pathlib), l'Unicode, le chargement Qt et le traitement des fichiers. Pour Windows/Spyder, il faut pouvoir identifier le chemin de l'interpréteur et le module chargé ; les artefacts `.bat` sont auxiliaires. Sur Linux/Wayland, « Toujours au premier plan » et le placement exact des fenêtres détachées peuvent dépendre du compositeur. Sous macOS, tester les raccourcis, les fenêtres natives et les chemins encodés. Les projets qui pointent vers des ressources locales sous licence ou vers des services IIIF authentifiés ne deviennent pas portables par une simple copie du XML.

## 6. Protection contre les pertes

Réutiliser `save_io.py` pour des sauvegardes atomiques et `.bak`; un simple changement d'export ou de disposition ne doit écrire dans aucune ressource scientifique. Lors de l'import ou du rafraîchissement, utiliser la préparation transactionnelle de `witness_resource_refresh.py`. Les suppressions (images copiées, anciens JSON, zones, lignes, références) doivent être volontaires et tracées, jamais un effet secondaire d'une « optimisation ».
