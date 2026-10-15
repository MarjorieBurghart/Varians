# Varians — Proposition pour le viewer web et les exports XSLT/CSS

**Document de discussion, pas une fonctionnalité livrée en V0.8.5.23.**

## État réel en V0.8.5.22

- L'aperçu Qt utilise déjà les choix `rendering/@xsltMode` (`builtin` / `file`), `@xslt` et `@css`. Une XSLT personnalisée peut être choisie et une CSS de projet existe déjà. Voir `XSLT_POLICY.md` et `project_config.py`.
- L'export web est autonome : `web_viewer/generator.py` assemble des données JSON et une interface HTML/CSS/JavaScript. Son comportement **n'est pas piloté** par `rendering/@xsltMode`.
- Le viewer web comporte déjà `scaledPolygon` et un calque de polygones SVG, des fonctions de recadrage et de construction d'URL IIIF régionales. Il faut en valider la fidélité à l'éditeur sur tous les cas, et corriger les écarts ; il ne faut pas déduire de leur présence que tous les cas PAGE XML/IIIF sont déjà maîtrisés.

## Trois couches indépendantes

1. **XSLT** : transformation de la TEI en contenu HTML (présentation du texte, paragraphes, notes, variantes et balises explicites) ; profil indépendant pour sortie HTML ou autres formats.
2. **CSS** : typographie, colonnes, thème, espaces et apparence de l'interface web ; remplacement/surcharge sans transformer les données scientifiques.
3. **JavaScript et données structurées** : synchronisation, navigation, polygones PAGE, zoom, zones de double page, requêtes IIIF. Ces actions ne peuvent pas être obtenues uniquement par CSS/XSLT.

Séparer le **contenu textuel transformé** du noyau graphique du viewer. Une XSLT personnalisée ne doit pas casser silencieusement la navigation : le HTML transformé doit conserver un contrat versionné (IDs stables, attributs `data-*` de liaisons, ancres de ligne et de folio). Contrôler/valider ce contrat et fournir un aperçu avant de publier.

## Interface proposée

Dans `Fichier → Paramètres du projet` : section `Rendu et publications` avec onglets `Aperçu dans Varians` (existant), `Viewer web`, `Transformations personnalisées`.

* Viewer web : thèmes CSS intégrés, CSS personnalisé facultatif, XSLT intégrée/personnalisée pour la seule transcription TEI ; bouton aperçu ; sortie autonome ou assets séparés ; avertissement ressources IIIF externes.
* Transformations personnalisées : profils nommés et réutilisables, chacun avec entrée TEI, feuille XSLT locale, CSS facultative si sortie HTML, paramètres XSLT, format de sortie, destination et aperçu. Les profils n'interfèrent pas avec le viewer web intégré.
* Possibilité de **réutiliser le profil d'aperçu existant** comme point de départ, sans confondre les réglages distincts.

## Format XML envisagé (NON IMPLÉMENTÉ)

```xml
<webViewer outputDir="web_output" filename="viewer.html">
  <appearance mode="custom" css="web/styles/edition.css"/>
  <textTransform mode="file" xslt="web/xslt/transcription.xsl"/>
</webViewer>
<exportProfiles>
  <exportProfile id="edition-lecture" label="Édition de lecture"
      input="xml/edition.xml" xslt="exports/lecture.xsl"
      css="exports/lecture.css" format="html"
      output="exports/lecture.html"/>
</exportProfiles>
```

Ce schéma est illustratif ; il doit être discuté et versionné avant intégration. Une absence de balises supplémentaires doit conserver le comportement actuel. La sauvegarde des anciennes configurations ne doit pas les supprimer accidentellement.

## Formats et sécurité

- Transformation actuelle : XSLT **1.0 par lxml**, éventuellement PowerShell/.NET en secours. XSLT 2.0/3.0 impliquerait un moteur supplémentaire (à choisir explicitement, non présumé).
- Prévisualiser la sortie HTML avec les ressources locales et le rendu web réel.
- Sécuriser l'exécution des XSLT personnalisées (contrôles d'accès sur `document()`, écriture de fichiers, import/include, chemins/symlinks, entités externes et accès réseau). L'utilisation de `no_network=True` pour le parseur XML n'équivaut pas, à elle seule, à interdire toutes les fonctions d'accès externes de XSLT.
- Ne pas inclure de JavaScript arbitraire dans le mode standard ; un mode expert serait distinct, clairement marqué et à risque.
- Conserver les droits de diffusion et les exigences d'authentification propres aux services IIIF ; l'export ne peut pas garantir l'accès distant permanent.

## Tests de fidélité web

Utiliser les mêmes cas de référence dans l'application et le viewer exporté : PAGE polygons concaves et quadrilatères, polygones ALTO, ligne entièrement hors recadrage, double page, source locale différente des dimensions OCR, IIIF v2/v3, qualité/résolution, échecs réseau et navigateur hors connexion. Comparer positions et formes des sommets, distances de crop et liens `@facs`/`@edRef`.
