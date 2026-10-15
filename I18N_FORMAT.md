# Internationalisation — format des catalogues XML

## Principe

L'éditeur et le viewer web utilisent les mêmes catalogues, stockés dans le dossier indiqué par `project.xml` :

```xml
<interface language="fr" translationsDir="i18n" fallbackLanguage="en"/>
```

Chaque fichier XML correspond à une langue.

## Format

```xml
<?xml version="1.0" encoding="UTF-8"?>
<translations lang="fr" label="Français">
  <string key="toolbar.save">Enregistrer</string>
  <string key="viewer.stats">{witnesses} témoin(s) · {lines} lignes de base · {variants} variantes</string>
</translations>
```

- `@lang` : code stable de langue (`fr`, `en`, `de`, etc.).
- `@label` : nom présenté dans le sélecteur de langue.
- `string/@key` : identifiant stable utilisé par le code. **Ne pas traduire la clé.**
- le contenu de `string` : texte traduit.

## Variables

Les valeurs entre accolades sont remplacées au runtime :

```xml
<string key="status.cursor">ligne {line}, colonne {column}</string>
```

Une traduction doit conserver les noms de variables, mais peut modifier leur ordre :

```xml
<string key="status.cursor">line {line}, column {column}</string>
```

## Retours à la ligne

On peut écrire `\n` dans un catalogue. Le chargeur le transforme en véritable retour à la ligne.

## Fallback

Lorsqu'une clé est absente :

1. recherche dans la langue active ;
2. recherche dans `fallbackLanguage` ;
3. affichage de la clé elle-même.

Ce dernier comportement est volontaire : une traduction manquante reste visible pendant le développement.

## Ajouter une langue

1. Copier `en.xml` sous un nouveau nom, par exemple `de.xml`.
2. Définir `<translations lang="de" label="Deutsch">`.
3. Traduire toutes les valeurs.
4. Ne pas changer les `key` ni les variables `{...}`.
5. Relancer l'éditeur.
6. Régénérer le viewer web pour incorporer le nouveau catalogue.

Aucune modification du code Python n'est nécessaire.

## Portée

Les catalogues couvrent notamment :

- barre d'outils et onglets de l'éditeur ;
- panneaux des manuscrits ;
- aperçu XSLT/CSS et recherche ;
- éditeur de fragments ;
- Ctrl+E et messages de sauvegarde ;
- génération du viewer web ;
- contrôles et métadonnées d'interface du viewer web.

Les contenus scientifiques du projet ne sont pas traduits automatiquement : titre de l'édition, sigles, labels de témoins, texte TEI, lectures de l'apparat, etc.

Les libellés natifs fournis par le système d'exploitation dans certains sélecteurs de fichiers peuvent suivre la langue du système plutôt que celle du projet.

## V0.4.2 — Priorité des traductions et mises à jour

À la lecture, les chaînes livrées avec l'application sont d'abord chargées ;
le catalogue de la langue situé dans le projet les remplace clé par clé.
Un ancien projet peut donc bénéficier des nouveaux libellés (par exemple le
sélecteur de source XSLT) sans que ses fichiers de traduction soient modifiés.

## Langues livrées depuis V0.8.4.2

L'installation standard contient sept catalogues complets :

- `fr.xml` — Français ;
- `en.xml` — English ;
- `de.xml` — Deutsch ;
- `ja.xml` — 日本語 ;
- `cs.xml` — Čeština ;
- `it.xml` — Italiano ;
- `ru.xml` — Русский.

Les catalogues doivent conserver exactement le même ensemble de clés et les
mêmes variables `str.format` (`{path}`, `{count}`, etc.). Le test
`tests/test_v0842_i18n_handoff.py` vérifie ces deux invariants.

La terminologie de l'interface doit être relue dans son contexte éditorial :
« witness » désigne un témoin textuel et non un témoin au sens courant ; les
noms de standards (TEI, ALTO, IIIF, XPath, RELAX NG, XSLT, CSS, Schematron) ne
sont pas traduits. Les labels du menu de langue sont écrits dans leur propre
langue afin de rester identifiables quelle que soit la langue active.


## Convention philologique — V0.8.5.12

Ne jamais appeler « manuscrit de base » le témoin utilisé uniquement comme
référence pour la synchronisation. L'expression retenue en français est
**manuscrit pivot** ; les six traductions utilisent la même distinction
(pivot manuscript / Pivot-Handschrift / ピボット写本 / pivotní rukopis /
manoscritto pivot / опорная рукопись). La chaîne `project.witness.pivot_tip`
explique son rôle ; conserver la différence éditoriale explicite dans toutes
les langues. Les clés de traduction contenant `base` sont des identifiants
techniques anciens : **ne pas les renommer** ni traduire les métadonnées JSON.
