# Varians — Proposition d'audit scientifique des projets

**Cahier des charges à discuter ; aucun audit automatique complet livré dans V0.8.5.23.**

## Contrôles

1. **Portabilité** : chemins absolus Windows ou Unix, résolution relative à la racine du projet, symlinks quittant le dossier, noms différant seulement par la casse (sensibles sur Linux), encodage et caractères spéciaux, doublons physiques et références orphelines.
2. **Configuration** : cohérence de `project.xml`, présence de la TEI, XSLT, CSS, RNG, répertoires de sortie, identifiants de témoins uniques et manuscrit pivot défini.
3. **Intégrité TEI** : XML bien formé, `xml:id` uniques, existence des cibles de `@facs`, `@edRef`, `@corresp` lorsque la sémantique l'autorise, liens TEI/ressources, coordonnées de zones valides, et éventuellement validation RELAX NG.
4. **Synchronisation** : JSON lisible, `meta.base_witness` conforme, identifiants page/ligne cohérents, clés `base_keys` existantes dans le pivot, doublons, lignes ignorées, lignes hors périmètre ; aucune correspondance devinée.
5. **Images et OCR** : ALTO/PAGE associés avec preuves suffisantes, dimensions valides, polygons dans le repère attendu, images présentes, copies IIIF correctement référencées, images IIIF v2/v3 et leurs Canvas ; contrôle réseau uniquement sur demande.
6. **Publication** : fichiers exportés, dépendances distantes, droits de diffusion et disponibilité des ressources externes ; ne jamais prétendre qu'une archive web est entièrement autonome si des images IIIF restent distantes.
7. **Sécurité technique** : autorisations en lecture/écriture, XML et XSLT externes, imports/includes, DTD/entités, chemins pouvant sortir du projet. Privilégier un fonctionnement multiplateforme sans secours dépendant de PowerShell pour les sorties essentielles.

## Restitution

Rapport en lecture seule classé `bloquant / avertissement / information`, avec référence du fichier ou de l'élément incriminé, cause exacte et correction envisageable. Proposer une correction manuelle ; ne réécrire ni TEI, ni JSON, ni images automatiquement. Ajouter un export du rapport en JSON/HTML pour le support.

Une commande distincte `Vérifier et empaqueter…` doit créer une archive de projet indépendante avec **manifest SHA-256**, table de ressources et rapport des dépendances distantes. Les ressources qui ne peuvent pas légalement être copiées restent des références externes déclarées.

## Compatibilité

L'audit ne doit pas casser les formats de projet historiques ni supposer que les chemins sont spécifiques à Windows. Tester Windows, macOS (Apple Silicon/Intel selon disponibilité), Linux X11 et Wayland pour les fenêtres indépendantes.
