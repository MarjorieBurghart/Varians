# Pages TEI et fac-similé — V0.8.2

Varians distingue désormais trois niveaux de correspondance qui ne doivent pas
être confondus :

1. **page TEI ↔ image** : `<facsimile>/<surface>/<graphic>` et `<pb facs>` ;
2. **géométrie physique de la page** : ALTO (lignes, rectangles, texte OCR/HTR) ;
3. **synchronisation ligne-à-ligne** : JSON d'alignement et `base_keys`.

Un ALTO seul ne permet donc jamais de déduire quelle ligne correspond au
curseur de l'édition. Sans synchronisation explicite, le panneau manuscrit
reste en **mode page** et affiche la page entière.

## Création des surfaces depuis les images du projet

Pour les images locales, la fiche du témoin comporte désormais trois colonnes :

- **Folio / page** : libellé éditorial, par exemple `f. 1r` ;
- **Surface TEI** : `xml:id` stable, par exemple `A1-p0001` ;
- **Fichier** : image correspondante.

L'identifiant de surface est volontairement indépendant du libellé et du nom du
fichier. Corriger `f. 1v` en `fol. 1v` ne casse donc pas `@facs`.

À la sauvegarde des paramètres, Varians peut compléter la TEI :

```xml
<facsimile>
  <surface xml:id="A1-p0001" n="f. 1r">
    <graphic url="../images/A1/0001.jpg"/>
  </surface>
</facsimile>
```

Le même principe s'applique aux canvases d'un Manifest IIIF ; leur label sert de
folio/page et un identifiant stable est déterminé par le témoin et l'ordre.

## Garde-fous non destructifs

Le `<facsimile>` appartient à l'édition TEI, pas au fichier de configuration du
projet. Varians applique donc une fusion incrémentale :

- aucun `<facsimile>` existant n'est remplacé en bloc ;
- seules les `<surface>` manquantes sont ajoutées ;
- une surface existante conserve ses attributs et enfants (`<zone>`, annotations,
  métadonnées, `<graphic>` personnalisé, etc.) ;
- aucune surface devenue orpheline n'est supprimée automatiquement ;
- un `xml:id` déjà utilisé sur un autre élément déclenche un conflit et la
  surface correspondante n'est pas créée ;
- si le XML n'est pas bien formé, Varians ne modifie rien ;
- une sauvegarde `edition.xml.bak` est créée lorsqu'une fusion automatique
  modifie effectivement le fichier sur disque.

Pour un changement de foliotage, `surface/@n` et les `pb/@n` qui pointent vers
cette surface ne sont actualisés que si leur valeur est encore exactement
l'ancien libellé connu du projet. Toute valeur qui paraît avoir été modifiée
manuellement est préservée.

Varians ne réécrit pas automatiquement l'URL d'un `<graphic>` existant : c'est
un choix volontaire de prudence. Une TEI enrichie manuellement reste l'autorité.

## Marquer la page dans la transcription

Le panneau manuscrit possède le bouton **Marquer la page**. Pour la page
`A1-p0002`, libellée `f. 1v`, il insère :

```xml
<pb n="f. 1v" edRef="#A1" facs="#A1-p0002"/>
```

« Marquer la page » est volontairement une commande d’insertion uniquement.
Si le curseur est à l’intérieur d’une balise XML — y compris `<pb/>` — Varians
ne modifie rien et affiche : « Placez le curseur dans le texte ou entre deux
balises. » Une position immédiatement avant `<` ou immédiatement après `>` est
au contraire considérée comme un point d’insertion valide. Pour réaffecter un
`<pb>`, l’éditeur le modifie ou le supprime explicitement puis insère le nouveau
marqueur.

Ce contrôle est effectué **avant** toute création/complétion automatique de
`<facsimile>` : un clic involontaire alors que le curseur est dans une balise ne
provoque donc absolument aucune modification de la TEI.

La page courante est ensuite calculée **par témoin** : Varians cherche le dernier
`<pb>` précédent dont `@edRef` désigne le témoin et utilise sa cible `@facs`. Un
texte peut donc être simultanément à `A1-p0002` pour A1 et à `B1-p0001` pour B1.
Les anciens `<pb facs>` sans `@edRef` restent reconnus lorsque leur surface
permet d'identifier sans ambiguïté le témoin. Si aucun repère pertinent n'existe
encore, la navigation reste manuelle et commence sur la première page.

## Modes d'affichage

### Mode page

Actif lorsqu'il n'existe pas de synchronisation ligne-à-ligne :

- toute la page est affichée ;
- les flèches parcourent une page à la fois ;
- si un ALTO existe, le bouton des cadres peut montrer **toutes** les lignes de
  cette page, sans en privilégier une ;
- `<pb edRef="#…" facs="#…">` permet de suivre indépendamment la page de chaque témoin depuis le curseur TEI.

### Mode ligne

Actif uniquement lorsqu'un JSON de synchronisation explicite est présent. Le
panneau peut alors recadrer sur les lignes correspondantes et synchroniser les
témoins à l'aide des `base_keys`.

## Viewer web

Le viewer exporté suit la même distinction. En mode page :

- les images locales nécessaires sont copiées dans `web_output/images/` ;
- la page entière est affichée ;
- un clic sur le texte de l'édition retrouve, pour chaque témoin, le dernier repère de page précédent et synchronise son panneau ;
- les repères des témoins secondaires sont conservés dans le HTML comme ancres invisibles afin de ne pas surcharger la lecture ;
- un clic sur un marqueur de page visible sélectionne directement sa surface ;
- les boutons globaux sont libellés `← page` / `page →` en mode page et `← ligne` / `ligne →` en mode ligne ;
- l'ALTO peut fournir des cadres, mais pas une fausse synchronisation de ligne.

Un projet sans aucune image conserve le viewer textuel pleine largeur introduit
en V0.7.7.


> **Varians 0.8.5.3** : la sélection explicite des canvases IIIF et leur association aux OCR indépendamment du nom de fichier sont documentées en détail dans [IIIF_CANVAS_SELECTION.md](IIIF_CANVAS_SELECTION.md). Les projets antérieurs conservent le mode implicite `all`. Ne pas confondre le manifeste (catalogue) avec les pages sélectionnées de l’édition.
