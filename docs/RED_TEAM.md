# Red team ciblée : intégrité des données et sécurité

Version examinée : 0.9.3.2. Corrections : version 0.9.3.3.

Deux red teams : la première, ci-dessous (intégrité des données et
sécurité) ; la seconde, plus bas (robustesse et cohérence).

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
  le viewer web et les feuilles livrées : faite ensuite, voir « Red team
  2 » ci-dessous.

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

# Red team 2 : robustesse et cohérence

Version examinée : 0.9.3.3. Corrections : version 0.9.3.4.

## Objet

Les deux axes laissés de côté par la première red team :

- **Robustesse** : documents très grands, très imbriqués ou abîmés ;
  formateur ; index des lignes du pivot.
- **Cohérence** : l'interface, le viewer web et les feuilles livrées
  (aperçu, Édition HTML, Édition critique, DOCX/ODT) disent-ils la même
  chose du même document, dans la même langue ?

## Méthode

1. Quatre agents ont cherché en parallèle : A grands documents ;
   B documents malformés, formateur, index des lignes ; C rendus des
   sorties ; D navigation et interface. Chaque piste est venue avec une
   preuve (mesure, script ou projet d'essai).
2. Chaque piste a été vérifiée, mesurée quand il s'agissait de
   performances, puis classée.
3. Quatre choix ont été posés à l'utilisatrice ; quatre autres ont été
   annoncés, sans objection (voir « Décisions »).
4. Comme la première fois : un test d'abord, vu en échec ; une correction
   par étape ; la suite complète verte avant de publier (environ 2 600
   tests). Elle a trouvé un défaut des pluriels (a53bef3) : une variable
   nommée `text` dans un message (`status.route_uncertain`) entrait en
   conflit avec un paramètre de `format_message` ; corrigé dans 051bd2d.

## Décisions de l'utilisatrice

| Question | Réponse |
|---|---|
| Quand les sorties divergent, laquelle fait référence ? | L'Édition critique (les choix propres au viewer restent : texte d'un témoin, leçon de repli grisée). |
| Un `<lb>` d'un autre témoin que le pivot | La règle TEI partout, viewer compris : sans `break="no"`, une fin de mot ; avec, le mot est soudé. |
| Fenêtre d'une variante dans le viewer | Comme l'apparat de l'Édition critique : « sigle : leçon », om., lacuna incipit/desinit, [lacune], notes entre parenthèses. |
| DOCX/ODT | Le pré-passage suit la même règle : forme développée et corrigée, didascalies entre parenthèses, citation espacée, note en marge en fin de document, `<space>` en espace. |
| *Annoncé* : JSON d'alignement abîmé | Le projet s'ouvre ; seule la synchronisation de ce témoin est coupée ; message traduit. |
| *Annoncé* : U+2029 dans un fichier | Écrit `&#x2029;` à l'ouverture, et signalé. |
| *Annoncé* : ligne très longue | Coloration arrêtée au-delà de 10 000 caractères de la ligne. |
| *Annoncé* : nombres | Formes plurielles de chaque langue dans les catalogues. |

## Faiblesses trouvées et corrigées

### Robustesse

| Id | Gravité | Constat | Correction | Tests | Commit |
|---|---|---|---|---|---|
| A1 | critique | « Tout lister » : le tableau ouvert, rempli de nouveau à chaque pause de frappe, mesurait ses colonnes à chaque cellule ; 1 000 résultats figeaient la fenêtre 16 s à chaque frappe. | Colonnes mesurées une fois, après le remplissage. | `gui/test_gui_search_results_scale.py` | 34e74e7 |
| A2, A5, A7 | élevée | Frappe dans un grand document : repliage de tout le document recalculé à chaque frappe (130 ms par Mo), texte lu une dizaine de fois par frappe, une ligne très longue colorée en entier. | Repères de repliage décalés, recalculés après 300 ms de pause ; texte et positions UTF-16 lus une fois par modification ; coloration limitée aux 10 000 premiers caractères d'une ligne. 1 Mo : 130 → 10 ms ; 2 Mo : 300 → 11 ms ; ligne de 0,5 Mo : 580 → 115 ms. | `gui/test_gui_typing_large.py` | 88ff0ed |
| A3 | élevée | Recherche XPath quadratique : 20 000 `<lb/>` frères, 104 s. | Positions par élément, rangs des frères calculés une fois par parent : 0,36 s. | `test_xpath_search_linear.py` | cc60130 |
| A4, A10, B1, B7 | élevée | Formateur : une espace insécable entre deux éléments était prise pour un blanc et remplacée par un retour à la ligne ; `xml:space` mal lu ; un DOCTYPE avec une apostrophe dans un commentaire était refusé ; 40 000 zones prenaient 62 s ; une imbrication profonde levait `RecursionError`. | Seuls les blancs XML sont des blancs ; `xml:space` lu dans l'arbre ; texte assemblé en un passage, parcours sans récursion. | `test_formatter_robustness.py` | 9ed8eab |
| A8 | moyenne | L'aperçu automatique, après une pause de la frappe, figeait la fenêtre le temps de la transformation (0,85 s par Mo). | Transformation dans un autre fil ; un résultat dépassé par une nouvelle frappe est jeté. | `gui/test_gui_depth_and_background_preview.py` | 57660c3 |
| A10 | moyenne | Un document de plus de 256 niveaux d'imbrication était refusé par l'aperçu et les paquets DOCX/ODT/EPUB ; l'export web levait `RecursionError` dès ~400 niveaux. | `huge_tree` (sans entités ni réseau) ; limite de récursion relevée le temps de l'export. | `gui/test_gui_depth_and_background_preview.py` | 57660c3 |
| B3/D1, B6 | moyenne | Un `<lb edRef="#T1"/>` dans un commentaire, une CDATA ou une instruction comptait comme une ligne du pivot : toute la synchronisation suivante était décalée d'une ligne. La casse et les guillemets n'étaient pas respectés ; `<pb>` et lacunes avaient chacun leur propre balayage. | Un seul motif (`xml_tag_pairs.element_tag_pattern`), qui saute commentaires, CDATA, instructions et DOCTYPE, pour les `<lb/>`, les `<pb>` et les lacunes. | `test_pivot_lb_scan.py`, `test_pivot_lines.py`, `gui/test_gui_commented_lb.py` | f1cbeb8 |
| B4 | moyenne | Édition en parties : la numérotation des lignes du pivot restait périmée quand un `xi:include` changeait de cible, ou qu'une lacune ou un `<pb>` était ajouté. | Gardée tant que la structure du fichier (`pivot_lines.structure_signature`) ne change pas. | `gui/test_gui_pivot_lines_cache.py` | 1fff1f7 |
| B5 | moyenne | Un fichier d'alignement JSON abîmé empêchait d'ouvrir le projet, avec un message brut. | Le projet s'ouvre ; la synchronisation de ce seul témoin est coupée ; message traduit, avec le fichier et l'endroit (ligne et colonne, page, ligne, champ). | `test_damaged_inputs.py`, `gui/test_gui_damaged_inputs.py` | 22b0062 |
| B2 | basse | Un U+2029 du fichier devenait un saut de ligne à l'enregistrement (Qt coupe ses blocs à ce caractère). | Écrit `&#x2029;` à l'ouverture, et signalé. | `test_damaged_inputs.py`, `gui/test_gui_damaged_inputs.py` | 22b0062 |
| B8 | basse | Des inclusions XInclude en éventail croissaient sans borne. | Assemblage arrêté au-delà de 2 000 000 d'éléments inclus, avec un problème traduit. | `test_damaged_inputs.py` | 22b0062 |

### Cohérence des rendus

| Id | Gravité | Constat | Correction | Tests | Commit |
|---|---|---|---|---|---|
| C1/D9 | élevée | Viewer : les `<lb>` des autres témoins étaient ignorés : mot non soudé avec `break="no"`, mots collés sans. | Règle TEI pour tout `<lb>`. | `test_viewer_reading_coherence.py` | f5b9580 |
| C6, C14, D2, D4, D10, C15 | moyenne | Viewer : espace insécable perdue ; `<emph>` en romain, `<quote>` en italique, référence collée ; un mot coupé par un `<lb break="no"/>` du pivot introuvable par la recherche ; « Lacune du pivot » nommée par son identifiant ; libellés de page altérés ; « de le témoin pivot », « 0 variantes ». | Comme l'Édition critique ; recherche à travers la coupure ; sigle ; libellé tel quel ; tournures propres au pivot ; nombre de variantes de l'apparat. | `test_viewer_reading_coherence.py`, `test_web_reading_blocks.py` | f5b9580 |
| C2–C5 | élevée | Viewer, fenêtre d'une variante : `<app>` imbriqué lu en entier, `<app>` dans une note perdu, notes d'une leçon absentes, lacunes et suppressions réduites à ∅, identifiants au lieu des sigles, `@wit` d'un `<rdgGrp>` non hérité. | Comme l'apparat de l'Édition critique. | `test_viewer_variant_window.py` | 473302f |
| C7, C8, C13, C15, C+ | élevée | Édition critique : variante d'un `<app>` dans une note perdue ; folio du témoin choisi dans une leçon non retenue perdu ; `hi` en exposant, indice, petites capitales mal rendus ; « Préliminaires », « Annexes », « éd. » non traduits ; note du lemme répétée dans l'apparat. | Corrigés dans `edition-critique.xsl` et `apparat-commun.xsl`. | `test_critique_coherence_saxon.py` | be76a21 |
| C8, C9, C10, C+ | élevée | DOCX/ODT : espace après un élément vide supprimée ; `choice`, `stage`, `cit`, note en marge et `space` laissés aux TEI Stylesheets ; folio d'une leçon non retenue perdu ; lacune d'une leçon sans étendue. | Pré-passage aligné sur la règle commune. | `test_docx_prepass_coherence_saxon.py` | 689e135 |
| C11, C12, C16, C4 | élevée | Aperçu et Édition HTML : `<front>` et `<back>` non rendus ; `<lb>` contigus de plusieurs témoins mal soudés ; apparat en ligne mal séparé, `<rdgGrp>` non hérité, vers collés ; lacunes d'une leçon perdues. | Corrigés dans `tei-to-html.xsl`. | `test_preview_coherence.py` | 0695433 |
| D3 | moyenne | Après un texte synchronisé à part, un témoin suivi par pages prenait, dans l'édition, les `<pb>` de ce texte. | Il ne suit que ceux de son texte, comme le viewer web. | `gui/test_gui_pivot_lines_cache.py` | 1fff1f7 |
| D5 | basse | Témoin sans données pour le texte affiché (projet à textes à part) : le viewer le disait, le bureau montrait un panneau vide. | Le bureau affiche le même message. | `gui/test_gui_text_sync.py` | e2883bd |

### Textes de l'interface

| Id | Gravité | Constat | Correction | Tests | Commit |
|---|---|---|---|---|---|
| D8 | basse | « 1 lignes », « (s) », « /i », « 21 строк » : pas de forme plurielle. | Syntaxe ICU dans les catalogues (`{count, plural, one {# ligne} other {# lignes}}`), catégories CLDR de chaque langue, mêmes règles pour l'éditeur (`i18n.py`) et le viewer (`plurals.js`). | `test_i18n_plurals.py` | a53bef3 |
| D6 | basse | Après un changement de langue, des textes restaient dans l'ancienne : barre d'état, commande « Éditer cet élément TEI », infobulles, message d'un panneau d'image. | Retraduits ; « XML bien formé » refait dans la nouvelle langue. | `gui/test_gui_language_switch.py` | 051bd2d |
| D7 | basse | Messages en une seule langue : conflits du `<facsimile>`, erreurs et avertissements du squelette du pivot, associations OCR ↔ IIIF, position d'une erreur XML, libellés d'accessibilité de la recherche du viewer. | Messages traduisibles (`i18n.Message`) : texte français de référence, clé et valeurs traduites par l'interface. | `test_untranslated_messages.py` | 051bd2d |

## Vérifié sain

- Repères de repliage pendant la frappe : 12 000 modifications au hasard,
  repères identiques à un recalcul complet.
- Formateur : sur des documents variés, le texte est inchangé (blancs XML
  mis à part) et formater deux fois revient à formater une fois.
- Export web : l'empreinte des données du jeu d'essai n'a changé que par
  les décisions ci-dessus (raison notée dans
  `test_v0916_single_file_export.py`).
- Pluriels : mêmes résultats en Python et dans le viewer pour chaque forme
  des catalogues, sur une quinzaine de nombres par langue.

## Limites connues

- **Première complétion** sur un très grand document : l'analyse du
  contexte prend environ 350 ms pour 4 Mo (gardée ensuite) ; sa mémoire
  croît comme le carré dans un document entièrement plat.
- **Paires de balises** (A6) : une frappe dans le nom d'une balise
  fermante relit le début du document, environ 0,1 s à la fin d'un
  document de 1,6 Mo (0,06 s au milieu). Rare : la balise ouvrante, où se
  fait d'ordinaire le renommage, n'a pas ce coût.
- **Ligne de plus de 10 000 caractères** : la fin n'est pas colorée.
- **U+2029 dans un commentaire ou une CDATA** : écrit `&#x2029;`, qui y
  reste littéral (rare : ce caractère est invisible).
- **Données d'essai** : une trentaine de « XX`<lb edRef="#T2"/>`II » dans
  le corpus d'exemple : sans `break="no"`, la règle TEI y voit deux mots.
- **Référence hors citation** (`<ref>` hors de `<cit>`) : chevrons dans le
  viewer, comme depuis 0.9.3.0.
- **Test instable** : `test_v0916_viewer_arrows.py` perd parfois un clic
  de la barre d'outils quand la machine est très chargée (passe seul).

## Où regarder dans le code

- Frappe : `code_editor` (`_text_snapshot`, `fold_header_lines`,
  `_update_fold_headers`, `HIGHLIGHT_LIMIT`).
- Formateur : `tei_formatter` ; motif commun des balises :
  `xml_tag_pairs.element_tag_pattern`.
- Lignes du pivot : `pivot_lines` (`structure_signature`, `page_at`).
- Aperçu : `formatted_view.render_preview`, `_refresh_preview_in_background`.
- Fichiers abîmés : `witness_resource_refresh.AlignmentError`,
  `document_session.protect_paragraph_separators`,
  `xml_assembly.MAX_ASSEMBLED_ELEMENTS`.
- Rendus : `web_viewer/legacy_v11_core` (`describe_readings`,
  `reading_parts`), `rendering/apparat-commun.xsl`, `edition-critique.xsl`,
  `apparat-en-notes.xsl`, `tei-to-html.xsl`.
- Textes : `i18n` (`plural_category`, `expand_plurals`, `Message`,
  `message_text`), `web_viewer/plurals.js`.
