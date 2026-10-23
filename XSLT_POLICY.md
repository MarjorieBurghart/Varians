# XSLT de l’application ou XSLT personnalisée — V0.4.2

## Pourquoi deux modes ?

Depuis V0.4.2, un projet peut **référencer la XSLT installée avec l’éditeur** au lieu de conserver une copie figée. Ainsi, une correction de la XSLT livrée (p. ex. `<lb break="no"/>`) s’applique à tous les projets concernés lors du lancement avec la nouvelle version de l’éditeur.

Le choix se fait dans **Fichier → Nouveau projet…** et **Fichier → Paramètres du projet…**.

### Mode 1 — XSLT par défaut de l’éditeur (choix proposé pour un nouveau projet)

Le `project.xml` contient :

```xml
<rendering xsltMode="builtin"
           css="rendering/tei.css"
           customElements="rendering/custom-elements.xml"/>
```

- **Aucune copie de la XSLT** n’est créée dans le dossier du nouveau projet.
- La XSLT est résolue à partir du dossier du **programme lancé** : `rendering/tei-to-html.xsl` situé à côté de `editeur_tei.py`.
- Le projet conserve sa **CSS** et son **custom-elements.xml** personnalisables dans son dossier.
- La mise à jour du logiciel peut donc faire évoluer l’apparence du projet : c’est le compromis choisi délibérément pour bénéficier des correctifs.
- Si l’on partage le projet avec une autre personne, cette dernière doit disposer d’une version compatible de l’éditeur et de sa XSLT intégrée.
- Aucun chemin absolu vers l’installation n’est stocké dans le projet, ce qui évite de casser le lien lors d’un déplacement entre machines.

### Mode 2 — XSLT personnalisée

```xml
<rendering xsltMode="file" xslt="rendering/tei-to-html.xsl"
           css="rendering/tei.css"
           customElements="rendering/custom-elements.xml"/>
```

- **Nouveau projet** : une copie de la XSLT livrée est créée dans `rendering/`.
- **Projet existant** : passer du mode intégré au mode personnalisé et conserver le chemin proposé crée une copie locale lors de l’enregistrement, **seulement si le fichier n’existe pas déjà**.
- Un chemin vers un autre fichier XSLT est possible via le sélecteur de fichiers.
- Une XSLT existante ne sera **jamais écrasée** lors du changement de mode.
- Les mises à jour de l’application **ne modifient pas** cette XSLT : le projet garde son rendu propre.
- Repasser en mode intégré **ne supprime pas** la copie locale, ce qui permet de revenir plus tard au mode personnalisé.

## Projets créés avant V0.4.2

Leur balise `<rendering xslt="…">` ne déclare généralement pas de `xsltMode`. Pour garantir la compatibilité, le chargeur interprète **l’absence de `xsltMode` comme `file`**. Aucune XSLT existante n’est changée ou supprimée automatiquement.

Pour utiliser le correctif de la XSLT installée sur un projet existant :

1. Ouvrir le projet dans V0.4.2.
2. Aller dans **Fichier → Paramètres du projet…**.
3. Choisir **XSLT par défaut de l’éditeur**.
4. Enregistrer. Le `project.xml` est sauvegardé, avec copie de sauvegarde `.bak`, puis le projet est rechargé.

On peut revenir ensuite à la XSLT personnalisée ; la copie présente dans le dossier du projet n’a pas été supprimée.

## Et pour le viewer web ?

Le générateur du viewer web utilise son **moteur JavaScript/HTML propre** dans `web_viewer/`, pas la XSLT de l’aperçu Qt. Le choix `xsltMode` ne change donc pas la génération du viewer web.

## Fichiers de traduction (anciens projets)

L’application charge ses traductions FR/EN intégrées, puis les **surcharge** avec celles de `i18n/` dans le projet. Les nouvelles clés d’interface apparaissent ainsi dans les projets anciens, sans toucher aux traductions personnalisées. Cette priorité fonctionne également pour les catalogues exportés vers le viewer web.

## À noter

Les boutons `XSLT…` / `CSS…` de la vue de rendu permettent encore un choix **temporaire pour la session** ; pour changer durablement la XSLT d’un projet, utiliser **Paramètres du projet…**.

## V0.9.2.0 — scénarios de transformation

Les scénarios de transformation XSLT (Fichier ▸ « Scénarios de
transformation… ») sont distincts de la feuille de l'aperçu : chacun nomme
sa feuille, sa CSS et son résultat, et peut employer Saxon (XSLT 3.0). Le
scénario prédéfini « Édition HTML » emploie la feuille et la CSS de Varians
(`${varians}/tei-to-html.xsl`), sans copie dans le projet. La feuille de
Varians reçoit un paramètre `css` (`tei.css` par défaut) pour son
`<link>`. Voir `XSLT_SCENARIOS.md`.
