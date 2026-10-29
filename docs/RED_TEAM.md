# Red team ciblée : intégrité des données et sécurité

Version examinée : 0.9.3.2. Corrections : version 0.9.3.3.

## Objet

Deux questions, choisies parmi les axes possibles d'une red team :

- **Intégrité des données** : ce que Varians enregistre est-il exactement ce
  que l'éditrice a écrit, et rien d'autre n'est-il abîmé en passant
  (`project.xml`, droits, fins de ligne, fichiers voisins) ?
- **Sécurité** : que peut faire un fichier **reçu** (document TEI, projet,
  feuille XSLT, règles Schematron, manifeste IIIF, JSON d'alignement) quand
  on l'ouvre, le valide, le publie ou l'exporte ?

La robustesse (entrées extrêmes, performances) et la cohérence d'ensemble
n'en faisaient pas partie.

## Méthode

1. Quatre agents ont cherché en parallèle, chacun sur un terrain :
   A intégrité des fichiers ; B XML, XSLT et Schematron ; C injection dans
   les sorties (viewer web, Édition critique, interface) ; D fichiers et
   réseau. Chaque piste est venue avec une preuve (script ou projet
   d'essai).
2. Chaque piste a été vérifiée à la main ; les fausses alertes ont été
   écartées (voir « Vérifié sain »).
3. Quatre choix de comportement ont été posés à l'utilisatrice (voir
   « Décisions »).
4. Chaque faiblesse corrigée a d'abord été reproduite par un test, vu en
   échec ; puis corrigée, un commit par étape, la suite complète verte à
   chaque fois (environ 2 300 tests, dont Chromium et l'interface Qt).

## Décisions de l'utilisatrice

| Question | Réponse |
|---|---|
| Règles Schematron déclarées par un document | Demander avant de les exécuter ; exécution isolée (sans réseau ni écriture) ; question la première fois pour des règles hors du projet, réponse mémorisée. |
| Schémas distants | Site de la TEI sans question ; pour tout autre site, demander une fois par site et mémoriser. |
| Fichier modifié hors de Varians | Avertir à l'enregistrement : Écraser / Recharger / Annuler. |
| Encodage déclaré autre que UTF-8 | Proposer de corriger la déclaration en UTF-8 ; refuser annule l'enregistrement. |

## Faiblesses trouvées et corrigées

Gravité : ce que permet la faiblesse, à partir d'un fichier reçu ou d'un
usage ordinaire.

| Id | Gravité | Constat | Correction | Tests | Commit |
|---|---|---|---|---|---|
| B1/D1 | critique | Cache des schémas distants : une adresse `http://hôte/%2e%2e/…` faisait écrire le fichier téléchargé hors du cache, n'importe où sur le disque, dès l'ouverture d'un document. | `schema_resolution._url_cache_path` écarte les segments vides, `.`, `..`, `\`, les lecteurs et les caractères interdits ; la cible doit rester dans le cache. | `test_schema_cache_containment.py` | d653dfa |
| B2 | critique | Les règles Schematron déclarées par un document reçu (locales ou distantes) étaient exécutées par Saxon à l'ouverture, avec tous ses droits : lecture de fichiers (`unparsed-text`), réseau, `xsl:result-document` n'importe où. | Processus de validation sans réseau (`allowedProtocols=file`) ; documents résultats capturés, jamais écrits ; accord demandé, par fichier, pour des règles hors du projet ; accord par site pour un schéma ou des règles hors de `tei-c.org`, fichiers inclus et redirections compris (`_CheckedRedirects`), avant toute requête et avant d'employer le cache. | `test_check_without_network.py`, `test_schematron_sandbox.py`, `gui/test_gui_schematron_outside.py`, `test_remote_schema_sites.py`, `gui/test_gui_schema_sites.py` | 86d81c5, a1c1976, 9984554 |
| C1 | élevée | Viewer web : le texte de l'édition pouvait y exécuter un script (ordre des remplacements des marqueurs de la page). | Données JSON insérées sans injection possible. | `test_viewer_injection.py` | 37a01a3 |
| A1 | élevée | Chaque enregistrement changeait les espaces insécables (U+00A0) en espaces et U+2028 en fin de ligne (`QTextDocument.toPlainText`). | Texte exact (`toRawText`) partout où Varians lit l'éditeur (`code_editor.raw_text`, `TextDocument`). | `gui/test_gui_exact_text.py` | d4fed96 |
| A2 | élevée | Après un caractère hors du plan multilingue de base (𝔄), les modifications programmées (formatage, complétion, Ctrl+E, renommage d'une balise, synchronisation…) tombaient à côté : Qt compte en UTF-16, Python en caractères. | Conversion systématique (`text_search.Utf16Positions`, `code_editor.text_positions`, `python_change`). | `gui/test_gui_exact_text.py` | d4fed96 |
| B3 | élevée | Scénario Saxon en pages : à la seconde passe, `xsl:result-document` écrivait hors du dossier du résultat. | `fn:transform` en `delivery-format: serialized` : Saxon n'écrit rien, Varians écrit les seuls fichiers attendus. | `test_xslt_engine_saxon.py` | ae09ff4 |
| B4 | élevée | Pré-passage Saxon (apparat en notes) : `xsl:result-document` non vérifié. | Documents résultats capturés. | `test_xslt_engine_saxon.py` | ae09ff4 |
| B5 | moyenne | Vérifier une feuille XSLT ou des règles affichées, sans les exécuter, consultait le réseau (paramètres statiques, `use-when`, `xsl:include` / `xsl:import` distants) et pouvait y envoyer le contenu d'un fichier local. | Vérification dans un processus sans réseau (Saxon) ; lxml sans lecture réseau. | `test_check_without_network.py` | 86d81c5 |
| C2 | moyenne | Édition critique : un `@target` devenait un lien brut (`javascript:`). | `f:lien` : seuls les liens relatifs, `http(s)` et `mailto`. | `test_edition_critique_saxon.py`, `test_untrusted_outputs.py` | 3f299a9 |
| C3 | moyenne | En-tête d'un panneau de témoin : du HTML dans un libellé IIIF était interprété par Qt. | Libellés en texte brut. | `gui/test_gui_plain_labels.py` | 3f299a9 |
| D2 | moyenne | L'export web copiait tout fichier désigné par un chemin absolu dans un JSON d'alignement. | Seules de vraies images (signature PNG, JPEG…) sont copiées ; sinon l'image distante, ou aucune (problème `local_image_not_image`). | `test_untrusted_outputs.py` | 3f299a9 |
| A3 | moyenne | Un fichier modifié hors de Varians depuis sa lecture était écrasé sans avertissement. | Empreinte du fichier (date, taille) ; à l'enregistrement : Écraser / Recharger / Annuler. | `gui/test_gui_external_changes.py` | 7669422 |
| A4 | moyenne | Un fichier déclarant `encoding="ISO-8859-1"` était enregistré en UTF-8 sous cette déclaration. | « Corriger et enregistrer » écrit UTF-8 dans la déclaration ; Annuler n'enregistre rien. | `test_declared_encoding.py`, `gui/test_gui_declared_encoding.py` | 0f95320 |
| A5 | moyenne | `project.xml` était réécrit sur place : un disque plein le laissait tronqué, illisible au démarrage suivant. | `save_io.XmlFile` : écriture atomique, copie `.bak`. | `test_file_integrity.py` | a75d167 |
| A6 | basse | Projet ▸ Paramètres… perdait le choix du texte du viewer web (`text`, `textWitness`, `highlightNonLem`). | Gardés par `ProjectDraft`. | `test_file_integrity.py`, `gui/test_gui_file_integrity.py` | a75d167 |
| A7 | basse | Un fichier enregistré passait aux droits 0600 ; un fichier en lecture seule était remplacé sans un mot. | Droits gardés ; lecture seule refusée, avec un message (7 langues). | `test_file_integrity.py`, `gui/test_gui_file_integrity.py` | a75d167 |
| A8 | basse | Fins de ligne CRLF changées en LF ; commentaires de `project.xml` perdus. | CRLF gardé ; prologue, épilogue et commentaires gardés par les mises à jour de `project.xml`. | `test_file_integrity.py` | a75d167 |
| D3 | basse | Une image IIIF `file://` d'un manifeste était lue sur le disque et affichée. | `iiif_manifest._web` : images `http(s)` seulement. | `test_untrusted_outputs.py` | 3f299a9 |

En cours de route, la suite complète a révélé un défaut des tests :
`relaxng_worker.serve` et `transform_worker.serve`, appelés dans le
processus de pytest, y laissaient actif le réglage « sans réseau », que
Saxon applique à tout le processus. Ils rendent désormais le réglage
précédent (`test_relaxng_worker.py`). Sans effet dans Varians, où ces
fonctions tournent dans leur propre processus.

## Vérifié sain

- Entités externes (XXE) : non lues par lxml ni par Saxon pour les sources.
- Extraction d'archives (TEI Stylesheets, paquets DOCX/ODT/EPUB) : chemins
  confinés.
- Copies locales IIIF : chemins confinés au dossier du projet.
- Aperçu XSLT / CSS (`QTextBrowser`) : ni réseau ni écriture.
- Viewer web : `esc()` échappe tout texte inséré dans le HTML.
- `save_io.atomic_write_text_with_backup` sur disque plein : l'ancien fichier
  reste intact.

## Limites connues

- **Lectures locales.** Saxon ne sait pas limiter les lectures à un dossier.
  Des règles Schematron acceptées, ou la feuille d'un scénario, peuvent lire
  un fichier de l'ordinateur ; sans réseau ni écriture, ce qu'elles lisent
  ne peut que s'afficher (panneau de validation, résultat du scénario).
- **Validation sans processus séparé.** Si le processus de validation ne
  peut pas être lancé, Varians valide lui-même : les règles n'écrivent
  toujours rien et l'accord reste demandé, mais le réseau n'est pas retiré
  à Saxon (il le serait pour tout Varians, scénarios compris).
- **Scénarios de transformation.** À l'exécution, une feuille lit tout
  fichier local et des adresses `http(s)` ; elle n'écrit que dans le dossier
  de son résultat. C'est un choix du projet, documenté dans l'aide.
- **Projet reçu.** Les manifestes IIIF et images déclarés dans
  `project.xml` sont consultés à l'ouverture du projet (hors du périmètre :
  le projet est choisi par l'utilisatrice). Ses catalogues de traduction
  peuvent contenir du HTML pour les libellés en texte enrichi.
- **Écritures de l'édition par Projet ▸ Paramètres…** (`tei_listwit`,
  `tei_facsimile`) : atomiques, avec `.bak`, mais elles ne gardent pas les
  droits du fichier, et `tei_facsimile` pas les fins de ligne CRLF.
  Projet ▸ Paramètres… réécrit aussi tout `project.xml` : les commentaires
  à l'intérieur de sa racine y sont perdus (gardés par les autres mises à
  jour).
- **Fichier modifié ailleurs** : signalé à l'enregistrement seulement, pas
  dès la modification.
- **Positions de pure navigation** (aperçu) : non converties en UTF-16 ;
  après un caractère hors du plan de base, une sélection peut s'y décaler,
  sans jamais modifier le texte.

## Pistes non poursuivies

- Surveiller les fichiers ouverts (`QFileSystemWatcher`) pour proposer le
  rechargement dès qu'un autre logiciel les modifie.
- Lire un document dans l'encodage qu'il déclare (aujourd'hui : UTF-8
  seulement ; un fichier illisible en UTF-8 est refusé à l'ouverture).
- Garder les droits et les fins de ligne dans `tei_listwit` et
  `tei_facsimile`, et les commentaires internes de `project.xml` dans
  Projet ▸ Paramètres….
- Red team des autres axes : robustesse (documents très grands ou
  malformés, formateur, index des lignes) et cohérence entre l'interface,
  le viewer web et les feuilles livrées.

## Où regarder dans le code

- Texte exact : `code_editor.raw_text`, `TextDocument`, `text_positions`,
  `python_change` ; `text_search.Utf16Positions`.
- Fichiers : `save_io` (`atomic_write_text_with_backup`, `XmlFile`,
  `ReadOnlyFileError`, `declared_encoding`, `is_utf8`) ;
  `document_session.file_stamp`, `DocumentSession.disk_stamp` ;
  `document_io._confirm_external_change`, `_confirm_utf8_declaration`.
- Saxon : `xslt_engines._serialized_results`, `_refuse_result_documents`,
  `saxon_without_network`, `CHECKS_LOCAL_ONLY` ; `schematron.LOCAL_ONLY`,
  `schematron.validate` (documents résultats capturés).
- Schémas et règles : `schema_resolution.trusted_schema_site`,
  `resolve_schema(may_fetch=…)`, `RemoteSchemaRefused`, `rules_outside` ;
  `validation_panel._schema_site_policy`, `_approved_rules`,
  `_allowed_rules` ; réponses mémorisées : `app_context.site_choice`,
  `rules_choice`.
- Sorties : `edition-critique.xsl` (`f:lien`),
  `web_viewer/generator.py` (`_is_image`), `iiif_manifest._web`,
  `manuscript_panel.WitnessHeader`.
