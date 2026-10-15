# ARCHIVE HISTORIQUE — FEUILLE DE ROUTE ABANDONNÉE LE 14 OCTOBRE 2026

Ce document est conservé uniquement pour la traçabilité. Il ne définit plus de priorités ni de versions futures. Une nouvelle roadmap sera élaborée avec l’utilisateur.

---

# Varians — Feuille de route révisée (octobre 2026)

La version de référence est **0.8.5.25.3** (géométrie et robustesse IIIF du viewer web livrées). Les assistants de génération automatique de `<app>`, `<lem>` et `<rdg>` sont **retirés**. Les fonctions déjà présentes d'édition TEI restent maintenues.

## Étape 1 — Correction XML (0.8.5.23)

Surlignage bidirectionnel conservateur des balises XML, tests d’imbrication, espaces de noms et autofermantes. Livré dans cette version.

## Étape 2 — Fidélité du visualiseur web (0.8.5.24 et 0.8.5.25 livrées)

- Conserver les vrais polygones PAGE XML (tous les sommets) et les présenter dans les mêmes coordonnées que l’éditeur ; SVG ou Canvas selon les besoins.
- Harmoniser la sélection des lignes, le recadrage, le repère source et les zones de double page avec l’application.
- IIIF Image API v2/v3 : métadonnées `info.json`, région et taille adaptées, pleine résolution si nécessaire, gestion des droits, CORS, latence, repli sur copies locales et aperçus.
- Tests avec images locales et IIIF et cas hors connexion.

## Étape 3 — Personnalisation du rendu web (proposé : 0.8.5.26)

- Conserver `rendering/xsltMode` + `rendering/css` pour l’aperçu Qt existant.
- Étudier une configuration `webExport` indépendante : profil CSS / profil XSLT de la TEI / thème optionnel, sélection par projet et profils nommés.
- Contrat stable entre HTML issu de XSLT et données de navigation : identifiants, `data-*`, liens vers témoins/pages/lignes.
- L’XSLT transforme la TEI en HTML ; la CSS habille l’HTML ; le JS existant gère les actions IIIF, la synchronisation et les polygones.
- Résolution portable des chemins, ressources embarquées et contrôle de sécurité des XSLT utilisateur. Ne pas écraser les fichiers externes ou déjà personnalisés.
- Les modalités exactes de l’interface et des transformations indépendantes restent à valider avec l’utilisateur avant codage.

## Étape 4 — Audit et emballage de projets (proposé : 0.8.6)

- Contrôle en lecture seule des fichiers/répertoires, chemins relatifs, fichiers présents/manquants, doublons, collision de `xml:id`, témoins/pivot, références `@facs` et `@edRef`, alignements `base_keys`, dimensions OCR/image, copies IIIF et compatibilité des ressources.
- Rapport explicatif de gravité et provenance (erreur/avertissement/information), liens vers la ressource et possibilités de correction ; aucun remaniement automatique des données scientifiques.
- Option d’archivage reproductible et portable avec manifeste de sommes de contrôle, tests Windows/macOS/Linux et avertissements sur licences ou accès IIIF.

### État au 14 octobre 2026 — V0.8.5.25
La géométrie v0.8.5.24 (polygones, recadrages, parties doubles) est conservée. La v0.8.5.25 ajoute les requêtes IIIF adaptatives et versionnées, le repli progressif, l'annulation des chargements obsolètes, des diagnostics sur les images distantes et les essais Chromium synthétiques. **La parité visuelle réelle PySide6/Chrome sur le corpus utilisateur reste à tester.** Les profils XSLT/CSS du viewer sont encore au stade de la conception : demander confirmation de leurs modalités avant de coder.

## Correctif intermédiaire livré : V0.8.5.25.1

L’affichage en pages entières des témoins réellement synchronisés a motivé la correction du rapprochement de `pb/@n` et des identifiants JSON. `pb/@facs` est désormais résolu de façon explicite et prudente ; la numérotation des lignes persiste entre deux zones d’une même double page. Ce correctif ne modifie pas les travaux encore prévus pour la V0.8.5.26 (personnalisation des exports XSLT/CSS, à discuter) ou V0.8.6 (audit du projet et archivage).

## Correctif intermédiaire : V0.8.5.25.2

Le HTML exporté rétablit et sécurise la sélection des lignes par clic dans le texte de lecture, y compris notes, variantes et références éditoriales possédant une clé vérifiée. La ligne active est identifiée visuellement ; le panneau manuscrit se recentre après le clic. Les références manquantes produisent un diagnostic explicite sans inventer de `base_keys`. L'export intègre deux compteurs de diagnostic de la liaison du texte. Les chantiers V0.8.5.26 (XSLT/CSS, à décider avec l'utilisateur) et V0.8.6 (audit) restent inchangés.


## Correctif de parité TEI ↔ JSON — V0.8.5.25.3

Le viewer web utilise désormais, comme l’éditeur, l’ordre global des `<lb edRef="#pivot"/>` dans la TEI et l’ordre des lignes physiques du JSON pivot, sans recalcul à partir des `<pb/>` de folio. Les `base_keys` secondaires restent obligatoires ; toute divergence de nombre de jalons est diagnostiquée, sans invention d’alignement. Les développements XSLT/CSS de 0.8.5.26 n’ont pas commencé.
