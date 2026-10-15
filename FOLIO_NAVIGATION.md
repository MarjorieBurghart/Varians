# Navigation par parties de manuscrit — Varians V0.8.5.20

## Modèle philologique

Une `<surface>` correspond à une **image physique** (fichier ou Canvas IIIF), mais peut porter plusieurs **folios logiques** décrits par des `<zone>` nommées. Cette modélisation ne duplique pas les images et ne préjuge ni de l'ordre scientifique des témoins, ni du rôle du manuscrit pivot.

```xml
<surface xml:id="L-p0008" n="008 - f002v-003r">
  <graphic url="https://exemple.org/iiif/2/identifier"/>
  <zone xml:id="L-p0008-left" n="f002v" ulx="0" uly="0" lrx="1962" lry="2704"/>
  <zone xml:id="L-p0008-right" n="f003r" ulx="1962" uly="0" lrx="3924" lry="2704"/>
</surface>
```

Deux `<pb>` peuvent désigner les deux zones :

```xml
<pb edRef="#L" n="f002v" facs="#L-p0008-left"/>
<!-- le texte correspondant au folio de gauche -->
<pb edRef="#L" n="f003r" facs="#L-p0008-right"/>
```

La résolution TEI est **par témoin** : la combinaison `@edRef` + `@n` est considérée dans le témoin, et `@facs` est prioritaire. Lorsque `@facs` désigne une surface entière et `@n` un de ses folios, Varians reconnaît ce folio si et seulement si la zone correspondante est unique **dans cette surface**. Une zone inconnue n'est jamais devinée d'après l'ordre des images.

## Interface

Dans les témoins **en mode page**, les flèches précédentes/suivantes parcourent les parties logiques quand elles sont définies, plutôt que de sauter directement à l’image suivante. Le sélecteur « Folios » de la V0.8.5.19 ne prend plus une rangée entière : le bouton « Double page… » rejoint la barre d’outils existante.

**Depuis la V0.8.5.19, la commande « Double page… » est aussi disponible pour un témoin synchronisé par lignes** : la définition des surfaces appartient au fac-similé et non à la synchronisation par les `base_keys`. En mode lignes, les zones sont créées, sans déplacer le cadrage sur la ligne synchronisée. Les zones demeurent consultables par les flèches du mode page, sans deuxième rangée de commandes.

La commande « Double page… » demande les libellés de la partie gauche et de la partie droite (qui ne sont pas nécessairement des folios). Une vignette de toute l’image permet de déplacer la barre rouge de séparation ; le pourcentage est aussi modifiable et la séparation est conservée avec précision en pixels. La TEI doit être bien formée et posséder une surface correspondante ; les dimensions de l'image doivent être connues. La commande refuse de modifier une surface qui possède déjà des zones, ainsi que tout conflit d'identifiants. Elle ajoute deux zones uniquement, sans pb automatique. L'utilisateur choisit ensuite le folio et utilise « Marquer la page » au point voulu.

**Sauvegarde et sécurité** : les modifications du fac-similé se font par patch textuel minimal dans l'éditeur, avec Undo Qt. La sauvegarde du document relève du flux habituel de Varians. Ni les fichiers image, ni les JSON d'alignement, ni les ALTO/PAGE ne sont modifiés. Un projet à images seules continue de fonctionner sans zones.

**Synchronisation par lignes** : elle reste prioritaire chez les témoins dotés de liens `base_keys` utilisables ; la navigation en zones de folio cible les témoins en mode page, sans produire artificiellement des correspondances de lignes.

**Viewer web** : le jeu de données exporté transporte les zones TEI. Le lecteur HTML propose le même choix de folio pour les témoins en mode page, avec recadrage par requête IIIF ou CSS pour les copies locales.

**Limites** : cette version traite les deux folios alignés gauche/droite, avec séparation verticale paramétrable. Les zones de forme irrégulière, les folios superposés et l'édition graphique des polygones ne sont pas encore disponibles. Le viewer web exporté conserve sa navigation antérieure tant que l'intégration des zones n'y a pas été effectuée. Le rendu réel PySide6 doit être validé sur les systèmes cibles.
