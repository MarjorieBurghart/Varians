VARIANS V0.9.2.7 — DOCX, ODT, EPUB, HTML EN PLUSIEURS FICHIERS, ÉDITION CRITIQUE

• Scénarios prédéfinis : les scénarios des TEI Stylesheets sont réunis
  dans un sous-groupe dépliable « TEI Stylesheets », replié au départ
  (sous-menu du bouton Transformer).
• Quatre formats de plus, avec les TEI Stylesheets : « TEI : HTML en
  plusieurs fichiers » (publications/tei/pages/index.html et une page par
  division et sous-division, splitLevel=1), « TEI : DOCX (Word) », « TEI :
  ODT (LibreOffice) » et « TEI : EPUB » (publications/tei/edition.docx,
  .odt, .epub). Varians fait l'archive (modèle du TEI-C, images locales
  avec leurs dimensions ; l'EPUB lit ses CSS dans la bibliothèque).
• DOCX et ODT : un pré-passage (rendering/apparat-en-notes.xsl) met
  l'apparat en notes de bas de page, d'après le témoin pivot :
  « leçon ] variante sigles », om., add., lacuna incipit, lacuna desinit ;
  les notes de l'éditeur sans @place deviennent des notes de fin ; seuls
  les folios du pivot restent (⟨12r⟩) ; les sauts de ligne des témoins se
  fondent dans le texte.
• Nouveau scénario prédéfini « Édition critique (HTML) »
  (rendering/edition-critique.xsl, Saxon, publications/edition-critique.html),
  d'après la feuille du kit d'édition critique, retouchée : témoin pivot
  par défaut (temoin-de-base=${pivot}), titres tirés du seul @n, folios du
  témoin choisi, lacunes nommées, apparat (lettres) et notes (chiffres) en
  deux séries, leçons des rdgGrp, une coupure par groupe de <lb>.
• Scénarios : « Format du résultat » (pages, docx, odt, epub) et
  « Pré-passage TEI → TEI » dans la boîte d'un scénario, écrits dans
  project.xml (attributs package et prepare) ; avec Saxon, les paramètres
  sont passés sans type (« false » pour un xs:boolean) ; ${pivot} et
  ${tei}/ dans leurs valeurs. Une feuille de Varians copiée dans le projet
  emporte les feuilles qu'elle inclut.
• Voir XSLT_SCENARIOS.md et l'aide (Édition critique, TEI Stylesheets).

VARIANS V0.9.2.6 — RÈGLES SCHEMATRON : FICHIERS INCLUS NON ENREGISTRÉS

• Fichiers inclus : un fichier inclus par un fichier de règles
  (sch:include, sch:extends, inclusions RELAX NG et XSD), ouvert dans
  Varians et modifié, est appliqué au document avec son texte, sans
  l'enregistrer, comme le fichier de règles lui-même depuis la 0.9.2.5.
  L'info-bulle de l'étiquette Schematron le nomme (« regles.sch (non
  enregistré : motifs.sch) ») ; une règle fautive y mène à sa ligne.
• Vérification d'un fichier .sch (F8) : elle lit de même les fichiers
  qu'il inclut, et elle est refaite au retour sur ce fichier quand l'un
  d'eux a changé (modifié, enregistré).
• La boîte « Règles Schematron du document » propose aussi les phases
  définies dans les fichiers inclus non enregistrés.
• Correction : Varians ne se fige plus en passant d'un long document,
  défilé (une partie de l'édition, par exemple), à un document court.
• Le format de project.xml ne change pas. Voir RELAXNG_VALIDATION.md.

VARIANS V0.9.2.5 — RÈGLES SCHEMATRON : TEXTE NON ENREGISTRÉ, PHASE, NORME 2020, XSD

• Règles non enregistrées : un fichier de règles ouvert dans Varians et
  modifié est appliqué au document avec son texte, sans l'enregistrer ;
  revenir au document après l'avoir modifié le fait valider de nouveau.
  L'info-bulle de l'étiquette Schematron le signale (« regles.sch, non
  enregistré ») ; défaire (Ctrl+Z) jusqu'à l'état enregistré revient aux
  règles du disque.
• Boîte « Règles Schematron du document » : un clic sur l'étiquette
  Schematron de la barre d'état, ou le bouton « Règles… » du panneau de
  validation, l'ouvre. Pour chaque fichier de règles déclaré, la phase se
  choisit dans une liste (phase par défaut, toutes les règles, phases du
  fichier) ; « Ajouter… » déclare un fichier, « Retirer » enlève une
  déclaration, « Ouvrir » affiche le fichier. Les changements sont écrits
  dans les <?xml-model?> du document (de l'édition si une partie est
  affichée), en une seule modification annulable.
• Norme 2020 et 2025 : la vérification et la complétion d'un fichier .sch
  acceptent sch:group, sch:rules, sch:library, sch:param au niveau du
  schéma, @as, @visit-each, @from et @when des phases, @schematronEdition,
  comme SchXslt2 (schéma livré complété, voir son LISEZMOI).
• XSD : les règles intégrées à un XSD déclaré comme Schematron comprennent
  celles des fichiers qu'il inclut ou importe (xs:include, xs:import), en
  local comme à distance (cache). La validation par un XSD n'est pas faite.
• Correction : au changement de langue, les en-têtes du panneau de
  validation ne se décalent plus (colonne Origine, depuis la 0.9.2.3).
• Le format de project.xml ne change pas. Voir RELAXNG_VALIDATION.md.

VARIANS V0.9.2.4 — PHASES ET FICHIERS SCHEMATRON

• Phases : une déclaration Schematron peut choisir sa phase, par l'attribut
  standard phase (comme dans Oxygen) :
    <?xml-model href="regles.sch" type="application/xml"
        schematypens="http://purl.oclc.org/dsdl/schematron" phase="lecons"?>
  #ALL : toutes les règles ; #DEFAULT ou rien : la phase par défaut du
  fichier (defaultPhase), sinon toutes. Une phase inconnue est une règle
  incorrecte, avec la liste des phases du fichier. L'info-bulle de
  l'étiquette Schematron nomme la phase de chaque fichier de règles.
• Règles incorrectes (XPath fautif, phase inconnue, fichier introuvable ou
  mal formé) : une ligne chacune dans le panneau de validation, origine
  « Schematron (règles) », sans rendre le document invalide. Double-clic :
  le fichier des règles s'affiche à la ligne de la règle ; Varians propose
  d'ajouter aux documents du projet un fichier de son dossier qui n'en est
  pas encore un ; un fichier hors du projet ne s'ouvre pas (barre d'état).
• Après l'enregistrement d'un fichier de règles, le document est validé de
  nouveau dès qu'on revient à lui.
• Fichiers .sch dans Varians : « Ajouter un document XML, XSLT ou
  Schematron… » les accepte (copie dans xml/ d'un fichier hors du projet) ;
  « Nouveau fichier Schematron… » crée xml/regles.sch (préfixe tei, une
  règle d'exemple). Un fichier Schematron affiché est vérifié à la place de
  la validation RELAX NG (F8 « Vérifier les règles Schematron », affichage,
  frappe après F8, enregistrement) : bonne formation, structure d'après le
  schéma ISO Schematron livré (resources/schemas/schematron, complété de
  @severity), fichiers inclus, compilation de toutes les phases par Saxon ;
  chaque erreur à sa ligne. Ctrl+Espace propose ses éléments, attributs et
  valeurs (severity, role, queryBinding).
• Limites : phase choisie par la déclaration seulement ; l'édition est
  validée avec les règles enregistrées ; la vérification d'un .sch suit
  l'édition 2016 de la norme (+ @severity) ; ni Schematron 1.5, ni règles
  d'un XSD.
• Le format de project.xml ne change pas. Voir RELAXNG_VALIDATION.md.

VARIANS V0.9.2.3 — RÈGLES SCHEMATRON

• Varians applique désormais les règles Schematron, en même temps que la
  validation RELAX NG (ouverture, frappe, F8, enregistrement), dans le même
  processus séparé : celles qui sont intégrées au RNG employé (91 groupes
  dans tei_all.rng, celles d'une personnalisation ODD), qu'il vienne du
  <?xml-model?> ou des paramètres du projet, puis celles de chaque
  déclaration xml-model de type Schematron (fichier .sch ou RNG ; une
  adresse http est mise en cache comme un RNG distant). Les mêmes règles ne
  sont jamais vérifiées deux fois.
• Panneau « Validation RELAX NG et Schematron » : colonne Origine (XML,
  RELAX NG, XInclude, Schematron), niveau Information ; double-clic vers la
  ligne de l'élément, dans sa partie pour une édition assemblée. Niveau
  d'après @severity, sinon @role (warning, warn, nonfatal : avertissement ;
  info : information ; le reste : erreur).
• Une erreur Schematron compte comme une erreur RELAX NG : onglet orange,
  question « Document non valide » avant d'enregistrer. Un avertissement ou
  une information restent listés sans rendre le document invalide.
• Barre d'état : étiquette Schematron (✓, erreurs, messages, règles
  incorrectes, Saxon manquant, non vérifié), info-bulle avec les fichiers
  des règles et le détail d'une règle incorrecte (fichier, ligne, message) ;
  une règle incorrecte ne rend pas le document invalide.
• Moteur : SchXslt2 1.11.2 (David Maus, licence MIT), livré dans
  resources/schxslt2/ (voir son LISEZMOI), et Saxon (saxonche). Sans Saxon,
  seule la validation RELAX NG est faite.
• Les nouveaux projets déclarent aussi les règles Schematron de TEI All.
• Limites : règles évaluées en XPath 3.1 quel que soit leur queryBinding ;
  phase par défaut seulement ; ni Schematron 1.5, ni règles d'un XSD.
• Un document TEI jusqu'ici valide peut recevoir de nouveaux messages. Le
  format de project.xml ne change pas. Voir RELAXNG_VALIDATION.md.
• Un projet qui garde une copie des traductions (dossier i18n/) y garde
  l'ancien titre du panneau et l'ancien texte de la question
  d'enregistrement ; remplacer ces fichiers par ceux de Varians pour
  adopter les nouveaux.

VARIANS V0.9.2.2 — TEI STYLESHEETS

• Varians apporte les TEI Stylesheets, les feuilles XSLT du TEI Consortium
  (github.com/TEIC/Stylesheets), version 7.61.0 : installées au premier
  usage, une fois pour tous les projets, dans le dossier de données de
  l'utilisateur (Windows : %LOCALAPPDATA%\Varians\tei-stylesheets), elles
  marchent sans réseau. Voir resources/tei-stylesheets/LISEZMOI.md.
• Quatre scénarios prédéfinis, avec Saxon : « TEI : HTML », « TEI : texte »,
  « TEI : Markdown » et « TEI : LaTeX » publient l'édition (assemblée) dans
  publications/tei/. Le HTML reçoit la CSS des TEI Stylesheets, sans lien
  vers tei-c.org ; les textes ajoutés suivent la langue de l'interface.
  Dans un scénario, ${tei}/… désigne un fichier des TEI Stylesheets.
• Personnaliser : « Dupliquer… » un scénario TEI, puis « Ouvrir la
  feuille » crée dans xslt/ une feuille de personnalisation (xsl:import de
  l'adresse officielle des TEI Stylesheets, lue dans la version installée,
  comme dans Oxygen) ; ses paramètres et ses règles l'emportent sur ceux
  du TEI-C, qui ne sont jamais modifiés.
• Mises à jour : au lancement, au plus une fois par mois, Varians cherche
  une nouvelle version, sans rien dire s'il n'y en a pas ou sans réseau ;
  il ne l'installe qu'avec votre accord (Installer / Plus tard), avec une
  fenêtre de progression et Annuler. Fichier ▸ « TEI Stylesheets… » (et le
  bouton de la liste des scénarios) : version, origine, dossier, licence,
  « Rechercher une mise à jour ». Le journal d'une exécution donne la
  version employée.
• Licence des TEI Stylesheets : au choix, BSD à deux clauses ou
  CC BY-SA 3.0, © 2011–2020 TEI Consortium ; le fichier LICENCE les
  accompagne.
• Compte rendu d'une transformation : « Ouvrir le dossier » ouvre le
  dossier du résultat. Les boutons et textes standard des fenêtres
  (« Montrer les détails… », « Fermer »…) suivent la langue de l'interface.
• Plus tard : DOCX, ODT, EPUB, HTML en plusieurs fichiers.
• Le format de project.xml ne change pas. Voir XSLT_SCENARIOS.md.

VARIANS V0.9.2.1 — ÉDITER LES FEUILLES XSLT

• Une feuille XSLT s'ouvre comme un document du projet. Fichier ▸
  « Documents XML / XSLT du projet… », désormais juste sous « Paramètres du
  projet… », ▸ « Ajouter un document XML ou XSLT… » accepte .xsl et .xslt ;
  une feuille venue d'ailleurs est copiée dans le dossier xslt/ du projet
  (au même niveau que xml/), sans jamais remplacer un fichier.
  « Nouvelle feuille XSLT… » crée une feuille minimale 1.0 (lxml) ou 3.0
  (Saxon) dans xslt/.
• « Ouvrir la feuille », dans la liste des scénarios ou dans la boîte d'un
  scénario : affiche la feuille du scénario. Une feuille de Varians
  (${varians}/…) est d'abord copiée dans xslt/ ; une feuille hors du projet
  peut l'être aussi ; le scénario emploie alors la copie.
• Vérification « comme le RNG » : F8 devient « Vérifier la feuille XSLT » ;
  la feuille est compilée, sans être exécutée, avec le moteur de ses
  scénarios (sinon d'après sa version : 1.0 par lxml, une autre par Saxon),
  à son premier affichage, pendant la frappe une fois F8 utilisé, et à
  l'enregistrement. Erreurs avec leur ligne dans le panneau de validation
  (double-clic), barre d'état, couleur de l'onglet.
• Complétion (Ctrl+Espace) des éléments et attributs XSLT, avec le préfixe
  de la feuille, d'après le schéma RELAX NG d'XSLT 3.0 du W3C fourni avec
  Varians (resources/schemas/xslt30, licence BSD) ; XSLT 1.0 seul pour une
  feuille version="1.0".
• Les fichiers annexes d'une feuille (feuilles importées ou incluses,
  images, CSS, JS) sont à placer soi-même dans xslt/.
• Dans tout document, Ctrl+Espace complète un nom d'élément tapé juste
  devant une autre balise (<h devant </p>).
• Un projet qui garde une copie des traductions (dossier i18n/) y garde les
  anciens noms du sous-menu et de « Ajouter un document XML… » : remplacer
  ces fichiers par ceux du dossier i18n/ de Varians.
• Le format de project.xml ne change pas. Voir XSLT_SCENARIOS.md.

VARIANS V0.9.2.0 — SCÉNARIOS DE TRANSFORMATION XSLT

• Fichier ▸ « Scénarios de transformation… » : des scénarios nommés,
  enregistrés dans project.xml (<transformations>), appliquent une feuille
  XSLT à l'édition (assemblée si elle a des parties), au document affiché
  ou à un fichier, et écrivent le résultat dans un fichier (édition HTML,
  index, XML transformé…). Ajouter, Modifier, Dupliquer, Supprimer, Aperçu,
  Exécuter. Le viewer web n'est pas touché.
• Scénarios prédéfinis fournis par Varians : pour l'instant « Édition HTML
  (feuille de Varians) » ; « Dupliquer… » le copie dans le projet pour
  l'adapter. (Les scénarios des TEI Stylesheets viendront ensuite.)
• Deux moteurs : XSLT 1.0 (lxml) et XSLT 3.0 (Saxon-HE, paquet saxonche),
  désormais installé avec Varians : installer_dependances.bat, ou
  pip install -r requirements.txt.
• Un scénario : source, moteur, feuille, CSS facultative (copiée à côté du
  résultat ; son nom est passé à la feuille par le paramètre css),
  résultat (remplacé à chaque exécution ; jamais une source du projet),
  paramètres (chaînes). Avec Saxon, xsl:result-document peut écrire
  d'autres fichiers, seulement dans le dossier du résultat.
• Bouton « Transformer ▾ » à côté de « Générer viewer web » : un clic
  relance le dernier scénario (Ctrl+Shift+T), la flèche donne la liste.
  Varians enregistre d'abord ce que le scénario lit ; la transformation
  tourne dans un processus à part (Annuler). Compte rendu avec « Ouvrir »
  et journal (moteur, paramètres, xsl:message, lectures réseau, écritures
  refusées) ; une erreur indique son fichier et sa ligne, et laisse le
  résultat précédent intact. L'aperçu s'ouvre depuis un dossier temporaire.
• Une feuille peut lire tout fichier local et le réseau (http, https) ;
  elle n'écrit que son résultat. Voir XSLT_SCENARIOS.md.

VARIANS V0.9.1.7 — ONGLETS DES DOCUMENTS

• Onglets des documents : l'onglet du document affiché se distingue
  nettement (fond blanc, filet bleu en haut, nom en gras) ; les autres sont
  en retrait, sur un fond plus sombre. La couleur d'un document mal formé
  (rouge) ou non valide (orange) reste visible, même sur l'onglet courant.

VARIANS V0.9.1.6 — EXPORT WEB D'UNE ÉDITION ASSEMBLÉE

• « Générer viewer web » exporte toute l'édition en parties (XInclude) :
  le texte des parties est dans le viewer, et les lignes du pivot y sont
  comptées d'une partie à l'autre, comme dans la fenêtre. Une édition en un
  seul fichier est exportée avec les mêmes données qu'avant.
• Textes synchronisés à part : chacun garde son pivot et ses JSON
  (alignments/s02/). Quand la ligne choisie y passe, chaque panneau montre
  son témoin dans ce texte (ses lignes, ses pages depuis sa page de départ,
  ou « Pas d'alignement de ce témoin pour ce texte. ») ; le zoom et les
  cadres restent. Les boutons de l'en-tête parcourent toutes les lignes
  dans l'ordre de lecture, d'un texte à l'autre.
• Les flèches ← → de tout panneau du viewer mènent le texte, comme dans la
  fenêtre : le témoin avance dans son propre ordre, d'une partie ou d'un
  texte à l'autre ; un témoin par pages mène par ses <pb>, sa liste de
  folios aussi, ou par son <locus from> ; un panneau absent va au texte
  suivant ou précédent qui a ce témoin ; ⤺ ramène sur la ligne reliée. Les
  messages de la barre d'état (début ou fin du manuscrit, ligne non reliée,
  page non située, place incertaine) s'affichent sous le titre du viewer.
• Lacunes : les bandeaux de la fenêtre sont dans le viewer ; une lacune
  continue d'une partie à l'autre, un texte à part repart sans lacune.
• Pour une édition en un seul fichier aussi : les flèches de tout panneau
  et la liste des folios mènent le texte (elles ne faisaient que
  feuilleter), et les lacunes ont leurs bandeaux. Deux corrections : un
  <pb> sans @facs trouve son folio par son nom même quand l'image porte le
  même nom ; un clic retient la position du fragment cliqué, et non le
  début de sa ligne. Régénérez le viewer pour en bénéficier.
• Avant l'export, Varians enregistre l'édition, ses parties modifiées et le
  fragment non appliqué d'une partie (un échec annule l'export) ; la
  question « Exporter quand même » disparaît. Le compte rendu de l'export
  liste les problèmes d'assemblage (partie introuvable…).
• Limites : la précision des positions est celle des fragments de texte
  affichés ; un <pb> ou un <lb> dans une leçon non retenue ou dans une note
  n'est pas vu par le viewer ; « État des témoins… », « Actualiser les
  synchronisations… », « Marquer la page » et « Double page… » restent
  propres à la fenêtre. Format des données : WEB_VIEWER_ASSEMBLED.md.
• Taille et durée de l'export : inchangées pour une édition en un seul
  fichier (projet exemple : 0,8 s, 5,2 Mo, dont 17 Ko pour le nouveau
  module) ; pour le jeu d'essai « corpus » (3 textes, 3785 lignes, 5
  témoins), 1,4 s et 7,4 Mo, dont 1 Mo de texte, qui manquait, et 1,1 Mo
  pour le parcours des témoins.

VARIANS V0.9.1.5 — VUE XSLT / CSS D'UNE ÉDITION ASSEMBLÉE

• Dans une édition en parties (XInclude), la Vue XSLT / CSS n'est plus en
  lecture seule ; elle s'utilise comme pour une édition en un seul fichier
  et montre toujours toute l'édition. Elle reste ouverte quand une partie
  est affichée ; seul un document auxiliaire la referme.
• Édition par fragment : le crayon ✎ ouvre un paragraphe tel qu'il est
  écrit dans le fichier qui le contient (l'étiquette nomme ce fichier,
  « Fragment TEI · paragraphe 7/12 · s03.xml »). Le fragment appliqué est
  écrit dans ce fichier, même s'il n'est pas affiché ou n'a jamais été
  ouvert : « * » sur son onglet, une seule annulation dans la partie. Le
  fichier doit rester bien formé. Ctrl+S dans le fragment enregistre ce
  fichier, puis le document affiché s'il est modifié.
• Un clic sur une ligne de l'aperçu place le curseur dans le fichier qui la
  contient, dont l'onglet s'ouvre ; les témoins suivent, avec la
  numérotation propre d'un texte synchronisé à part. Table des matières et
  recherche dans l'aperçu : de même.
• Sélections : une chaîne sélectionnée dans l'aperçu est sélectionnée, de
  retour dans l'onglet XML source, dans la partie qui contient le texte, à
  la même occurrence du même paragraphe ; sans sélection, le curseur va à
  la ligne affichée. Inversement depuis une partie ou l'édition. Entre
  l'aperçu et l'éditeur de fragment, comme pour un seul fichier.
• Limites : un paragraphe qui contient lui-même un xi:include s'édite dans
  le fichier de sa balise ; l'export web ne contient pas encore les
  parties (prochaine étape).
• Sous l'aperçu, le nombre de lignes du témoin pivot cliquables est de
  nouveau donné : les versions précédentes disaient, à tort, que la XSLT ne
  produisait pas de marqueurs de ligne (ses repères portent un caractère
  invisible que le décompte n'acceptait pas ; les repères, eux,
  fonctionnaient).
• Éditeur de fragment : si la place manque, la case « Retour automatique à
  la ligne » se raccourcit (son texte reste dans sa bulle d'aide), et
  l'étiquette du fragment reste lisible en entier.
• Tests GUI : les fenêtres de test sont détruites après chaque test (la
  mémoire des serveurs GitHub s'épuisait) ; les appels différés de la
  fenêtre (call_later) ne s'exécutent plus après sa destruction.

VARIANS V0.9.1.4 — SUIVRE UN MANUSCRIT DANS SON PROPRE ORDRE

• Les flèches de tout panneau de témoin mènent l'édition, et non plus
  seulement celles du pivot : le témoin avance dans son propre ordre, et le
  curseur de l'édition va au passage correspondant, dans la bonne partie ou
  le bon texte ; les autres témoins suivent le pivot. Une ligne non reliée
  au pivot laisse l'édition sur la ligne reliée qui la précède. Avec un
  document auxiliaire affiché, les flèches feuillettent seulement le
  témoin.
• D'un texte à l'autre : au bout d'un texte, les flèches passent au texte
  suivant dans le manuscrit, numérotation continue ou texte synchronisé à
  part. Le pivot fait de même : un pivot commun à plusieurs textes se
  parcourt d'un seul tenant.
• Témoins par pages : les flèches et la liste des folios mènent l'édition à
  la page choisie (sa première ligne dans un JSON du témoin, sinon son <pb>,
  sinon le début du texte dont le <locus from> est cette page ; sans repère,
  l'édition reste et un message le dit).
• Panneau d'un témoin absent du texte affiché : ses flèches mènent au texte
  suivant ou précédent qui a ce témoin.
• Ordre des textes dans un manuscrit : déduit de ses pages (images déclarées,
  sinon pages communes à ses JSON, sinon <locus from> ou foliotation) ; un
  texte qui ne s'y rattache pas garde sa place dans l'ordre de l'édition.
  « Affichage → État des témoins… » donne cet ordre pour chaque manuscrit et
  signale une place incertaine.
• L'export web ne contient pas encore les parties ni les lacunes (étape
  suivante : Vue XSLT / CSS et export web de l'édition assemblée).

VARIANS V0.9.1.3 — LACUNES DES TÉMOINS, TÉMOINS PAR PAGES DANS UN TEXTE À PART

• Lacunes : le passage qu'un témoin n'a pas s'encadre par <lacunaStart/> et
  <lacunaEnd/>, placés, comme le veut la TEI, dans une leçon : le témoin est
  celui du <rdg> ou du <lem> qui les contient
  (<app><lem wit="#T1"/><rdg wit="#T2"><lacunaStart/></rdg></app>), ou,
  dans une leçon de plusieurs témoins, celui de leur propre @wit
  (<rdg wit="#T2 #P">… <lacunaStart wit="#P"/></rdg>). Hors d'une leçon,
  <lacunaStart wit="#T2"/> est reconnu aussi, mais la validation TEI le
  signale comme une erreur.
  Dans une lacune, le panneau du témoin garde la ligne (ou la page) où son
  texte s'interrompt, avec un bandeau « Lacune ». Pendant une lacune du
  pivot, les témoins par lignes restent sur sa dernière ligne, avec un
  message ; les témoins par pages continuent de suivre leurs <pb>.
• « Débugger l'apparat » : « <app> incomplets » n'attend plus de leçon d'un
  témoin dans sa lacune (XPath 1.0 ordinaire, comme avant).
• Textes synchronisés à part : un témoin sans JSON pour un texte, mais qui
  a ce texte (un <pb edRef> dans le texte, ou un <locus target> dans son
  <witness>), y suit ses pages au lieu du message d'absence. Avant son
  premier <pb> dans le texte : sa page de départ, le @from de son <locus>,
  sinon la page qui précède celle de ce premier <pb>, dans l'ordre de ses
  pages. « Marquer la page » y fonctionne aussi.
• Tests : deux tests de délai de la validation, trop sensibles à la
  vitesse des machines GitHub, ont été rendus plus robustes.
• L'export web ne montre pas encore les lacunes ni les parties.

VARIANS V0.9.1.2 — SÉLECTIONS PARTAGÉES ENTRE L'APERÇU ET L'ÉDITEUR DE FRAGMENT

• Vue XSLT / CSS : le crayon ✎ ouvre un paragraphe dans l'éditeur de
  fragment sans déplacer les images des témoins ; un clic sur le texte de
  l'aperçu les synchronise toujours.
• L'éditeur de fragment ouvert, une chaîne sélectionnée dans ce paragraphe
  de l'aperçu (glisser, double-clic) est aussi sélectionnée dans l'éditeur
  de fragment, qui prend le focus : le passage à corriger est trouvé tout
  de suite. Une sélection dans un autre paragraphe ne change rien ; on
  ouvre ce paragraphe par son crayon.
• Inversement, une sélection faite dans l'éditeur de fragment est
  sélectionnée dans l'aperçu, qui défile jusqu'à elle ; le focus reste dans
  l'éditeur. Même occurrence d'un mot répété, y compris d'un mot coupé par
  un <lb break="no"/>.
• Le report d'une sélection entre les onglets Source et XSLT / CSS est
  inchangé, et désormais vérifié par des tests qui l'exécutent. Pour une
  édition en parties, l'aperçu reste en lecture seule : ce report et
  l'éditeur de fragment y viendront avec l'édition par fragment de
  l'édition assemblée.
• Réalisé en V0.9.1.3 : les lacunes et les témoins par pages dans un texte
  synchronisé à part ; le parcours d'un manuscrit dans son propre ordre
  vient en V0.9.1.4.

VARIANS V0.9.1.1 — TEXTES SYNCHRONISÉS À PART, MODE D'EMPLOI XINCLUDE

• Corpus dont les textes ne sont pas transmis par les mêmes témoins : dans
  une édition en parties, un texte qui a son dossier d'alignements est
  synchronisé à part. Un JSON par témoin et par texte, au format habituel :
  alignments/s02/B.json pour xml/sermons/s02.xml (le dossier porte le nom du
  fichier du texte, sans extension). Rien à déclarer ; les autres textes
  suivent la numérotation continue (V0.9.1.0).
• Pivot propre à un texte : <parts><part name="s02" base="B"/></parts>
  dans project.xml, écrit à la main ; Varians le garde quand on enregistre
  les paramètres du projet.
• Quand un tel texte est affiché, les panneaux des témoins prennent ses
  alignements et son pivot ; disposition, zoom et fenêtres détachées ne
  changent pas. Un témoin sans JSON pour le texte garde son panneau, avec
  « Pas d'alignement de ce témoin pour ce texte ». L'état de structure
  compte les lignes du texte ; un clic dans le pivot reste dans le texte.
• « État des témoins… » et « Actualiser les synchronisations… » portent
  sur le texte affiché ; le diagnostic liste les textes synchronisés à
  part, leur pivot, leurs témoins et les problèmes de leurs dossiers.
• Aide : nouveau mode d'emploi « Mettre en place une édition en parties
  (XInclude) » : organiser les fichiers, écrire les xi:include, déclarer
  les témoins, choisir la synchronisation de chaque texte, vérifier.
• Viendront en V0.9.1.3 : les lacunes, les témoins synchronisés par pages
  dans un texte synchronisé à part, le parcours d'un manuscrit dans son
  propre ordre. La V1.0 attendra les scénarios de transformation XSLT.
• Un projet sans dossier par texte est inchangé.

VARIANS V0.9.1.0 — SYNCHRONISATION DES TÉMOINS À TRAVERS LES PARTIES

• Pour une édition assemblée par XInclude (V0.9.0.0), les témoins se
  synchronisent de nouveau. Cas d'une collection découpée en fichiers par
  commodité : les lignes du pivot (<lb edRef="#pivot"/>) sont comptées dans
  l'ordre de l'édition assemblée, d'une partie à l'autre, comme dans une
  édition en un seul fichier ; les JSON d'alignement sont ceux d'aujourd'hui,
  un par témoin pour toute l'édition.
• Le curseur de l'édition ou d'une partie fait suivre les témoins ; un clic
  ou un défilement dans le pivot place le curseur dans la partie qui
  contient la ligne et ouvre son onglet (même masqué).
• Les témoins, leurs fenêtres détachées et l'état de structure restent
  affichés sur une partie ; l'état de structure et l'avertissement à
  l'enregistrement comptent les lignes de toute l'édition assemblée.
• Témoins en mode page : le dernier <pb> qui les concerne est cherché dans
  l'ordre de l'édition, y compris dans une partie précédente (page tenue à
  la jonction de deux textes). Les folios sont lus dans le <facsimile> de
  l'édition.
• Depuis une partie, « Marquer la page » insère le <pb> dans la partie et
  complète le <facsimile> de l'édition ; « Double page… » écrit ses zones
  dans l'édition. L'édition est alors modifiée sans être affichée (« * »
  sur son onglet).
• Condition : le pivot contient les textes dans l'ordre de l'édition ;
  Varians vérifie le nombre de lignes, pas leur ordre. Les autres témoins
  peuvent avoir un autre ordre ou ne pas avoir un texte.
• Limites : la synchronisation d'un corpus aux témoins variables (un JSON
  par texte, alignments/s02/B.json) viendra en V0.9.2.0 ; la Vue XSLT / CSS
  de l'édition assemblée reste en lecture seule, sans synchronisation par
  un clic ; l'export web ne contient pas encore les parties.
• Un projet sans xi:include est inchangé ; format de project.xml inchangé.

VARIANS V0.9.0.0 — ÉDITIONS ASSEMBLÉES PAR XINCLUDE

• Une édition peut inclure ses parties (un fichier par sermon, par
  exemple) selon la norme XInclude : <xi:include href="s01.xml"/> pour un
  fragment, ou xpointer="s02", "element(s02)", "element(/1/2/1/1)" pour un
  élément d'un document TEI complet. L'édition déclarée dans project.xml
  reste le document maître ; ses parties se déduisent de ses xi:include,
  sans autre déclaration. Une partie peut en inclure d'autres.
• Chaque partie a son onglet, nommé d'après son fichier, dans l'ordre
  d'inclusion. Elle s'édite et s'enregistre seule, avec son propre
  historique d'annulation ; la liste des parties est relue à chaque
  enregistrement. Renommer et Retirer ne concernent que les documents
  auxiliaires. « Enregistrer sous » dans un autre dossier avertit que les
  xi:include ne trouveraient plus les parties.
• Validation RELAX NG de l'édition assemblée, avec le schéma de l'édition
  et le texte non enregistré des parties : une colonne Document indique
  le fichier de chaque erreur, et un double-clic y mène. Partie absente
  ou mal formée, inclusion circulaire, xi:fallback, parse="text" : signalés
  à la ligne du xi:include. Chaque onglet prend la couleur de ses erreurs.
• Références : l'édition et ses parties forment un seul document. #id se
  cherche d'abord dans son propre fichier (en-tête compris), puis dans les
  autres parties ; F12, la commande Références et la complétion en
  tiennent compte. Dans une partie, la complétion prend le schéma de
  l'édition, et « Débugger l'apparat » les témoins de la partie (son
  <listWit>, sinon les <locus target> de l'édition, sinon ses @wit).
• Limites de cette version :
  - la synchronisation des témoins est suspendue pour une édition qui a
    des parties (navigation libre, état indiqué dans la barre d'état) ;
    elle viendra en V0.9.1.0 (numérotation continue) et V0.9.2.0 (un JSON
    de synchronisation par texte) ;
  - la Vue XSLT / CSS montre l'édition assemblée, parties comprises
    (texte non enregistré compris), mais en lecture seule : l'édition par
    fragment n'y est pas encore possible ;
  - l'export web ne contient pas encore les parties ; un message le dit
    avant l'export.
• Un projet sans xi:include est inchangé ; format de project.xml inchangé.

VARIANS V0.8.9.2 — VALIDATION RELAX NG SANS FIGER LA FENÊTRE

• La validation RELAX NG se fait désormais dans un processus séparé, que
  Varians lance au premier besoin. La première validation après le
  lancement compile le schéma (TEI_ALL : une dizaine de secondes) : la
  fenêtre reste utilisable pendant ce temps, et une petite lueur tourne
  dans la barre d'état, à côté de « RNG : validation en cours… ». Avant,
  l'application restait figée (« Ne répond pas » sous Windows).
• Le schéma compilé est gardé pour toute la session, même si l'on ouvre
  un autre projet.
• F8 (Valider RNG) et l'enregistrement attendent le résultat, en laissant
  la fenêtre s'afficher ; clics et frappes sont ignorés pendant cette
  attente. L'enregistrement garde donc sa vérification RELAX NG.
• Si ce processus ne peut pas être lancé, Varians valide lui-même comme
  avant, et le signale une fois dans la barre d'état.
• Compatible avec une future version autonome (PyInstaller, Nuitka…) :
  c'est Varians lui-même qui est relancé, avec l'option interne
  --relaxng-worker, sans interpréteur Python ni fichier .py à part.
• Aucun changement des résultats de validation, des données TEI, JSON,
  ALTO/PAGE, du viewer web ni du format de project.xml.

VARIANS V0.8.9.1 — DÉBUGGER L'APPARAT

• Aide ▸ Débugger l'apparat… : requêtes XPath toutes prêtes pour repérer
  les erreurs de l'apparat critique du document affiché, encodé en
  parallel segmentation (<app>, <lem>, <rdg>, <rdgGrp>, @wit="#A #B") :
  - <app> où un témoin est cité plusieurs fois (leçon ambiguë) ;
  - <app> incomplets (un témoin du <listWit> n'a pas de leçon ; pour un
    <app> imbriqué, les témoins de la leçon qui le contient) ;
  - <app> où un témoin choisi apparaît, ou n'apparaît pas, dans <lem> ou
    <rdg>, ou dans <rdg> seulement.
  Un <lem> sans @wit est réputé couvrir les témoins absents des <rdg>.
• Mes requêtes : requêtes XPath personnelles, nommées, enregistrées dans
  project.xml (élément <xpathQueries>, voir PROJECT_MANAGEMENT.md) et
  réutilisables à volonté.
• La requête est lancée dans le panneau XPath : un clic sur un résultat
  mène à l'<app>. C'est du XPath 1.0 ordinaire (préfixe tei:), que l'on
  peut copier dans d'autres outils XML.
• Limite : une version antérieure à 0.8.9.1 ouvre normalement un projet
  qui contient des requêtes, mais les efface si l'on y enregistre les
  paramètres du projet.
• Aucun changement des données TEI, JSON, ALTO/PAGE ni du viewer web.

VARIANS V0.8.9.0 — ONGLETS DE DOCUMENTS AFFICHÉS

• Affichage ▸ Choisir les documents affichés… : une case par document du
  projet (Édition, documents auxiliaires) et un ordre réglable (Monter,
  Descendre). Ce choix est mémorisé localement pour le projet ; project.xml
  n'est pas modifié.
• Clic droit sur un onglet : Masquer l'onglet, Renommer l'onglet…,
  Choisir les documents affichés…, Retirer le document du projet. Ces
  commandes portent sur le document de l'onglet cliqué, même s'il n'est
  pas affiché.
• Un document masqué reste dans le projet : ses modifications sont gardées
  et Varians propose de les enregistrer avant de quitter. F12, Ctrl+clic ou
  un double-clic dans le panneau « Références » qui y mènent font
  réapparaître son onglet, durablement.
• Le dernier onglet visible ne peut pas être masqué. À l'ouverture du
  projet, l'édition est affichée, avec son onglet.
• Renommer l'onglet… écrit le nom dans l'attribut label du <document>, dans
  project.xml (copie .bak) ; un nom vide revient au nom du fichier.
• Un projet qui ne compte que l'édition est inchangé : pas de rangée
  d'onglets, commande inactive.
• Aucun changement des données TEI, JSON, ALTO/PAGE, du viewer web ni du
  format de project.xml.

VARIANS V0.8.8.0 — RÉFÉRENCES ENTRE DOCUMENTS

• Références : dans un attribut pointeur (@ref, @corresp, @target, @who,
  @wit, @edRef…), « personnes.xml#bernard » désigne l'élément bernard du
  fichier personnes.xml, et « #bernard », comme en TEI standard, un élément
  du document lui-même. Les liens restent ainsi lisibles par tous les
  outils XML. Les adresses web ne sont pas traitées.
• Saisie : taper « # » dans la valeur ouvre d'elle-même la liste des
  identifiants (« personnes.xml#bernard — Bernardus »), limitée au type
  d'entrée attendu (persName/@ref → person, placeName/@ref → place…), @wit
  compris (témoins du <listWit>). Un identifiant d'un autre document est
  inséré sous la forme fichier.xml#id.
• rdg/@wit propose désormais, comme lem/@wit, les <witness> décrits dans la
  TEI (le <listWit>), que vérifie la commande « Références », et non plus la
  liste des témoins de project.xml. Un projet existant garde sa copie de
  rendering/custom-elements.xml : pour adopter cette règle, y remplacer
  source="witnesses" par source="ids" elements="witness". Entrée ou Tab insère, Échap ferme ;
  Ctrl+Espace reste disponible. custom-elements.xml : nouvelle source
  <values source="ids" elements="…"/> (voir CUSTOM_ELEMENTS.md).
• Navigation : F12, Ctrl+clic ou clic droit ▸ Aller à la cible affiche
  l'élément visé, même dans un autre document ; Alt+← (Revenir) ramène au
  point de départ. Une cible définie plusieurs fois est choisie dans une
  liste.
• Vérification : le bouton « Références » de la barre d'outils liste dans
  un panneau les références introuvables, ambiguës, vers un fichier absent,
  ou en forme courte (« #bernard ») alors que la cible est dans un autre
  document — avec la forme à écrire ; un double-clic y mène, « Vérifier à nouveau » relance la
  vérification. Elle n'empêche jamais d'enregistrer.
• Viewer web : les cases « Variantes » et « Notes » permettent au lecteur
  de masquer les marqueurs correspondants ; le navigateur mémorise le
  choix. Régénérez le viewer pour en bénéficier.
• Terminologie : « témoin pivot » remplace « manuscrit pivot » dans les
  sept langues, et le rôle s'appelle « Pivot » dans les paramètres du
  projet. Le pivot sert à la synchronisation, sans préjuger de sa place
  dans le stemma ni de son statut dans l'édition. project.xml est inchangé
  (role="base").
• Projets créés avant la V0.8.8.0 : leur dossier i18n/ contient une copie
  des traductions, prioritaire sur celle de Varians ; ils affichent donc
  encore « manuscrit pivot ». Pour adopter les nouveaux termes, supprimez
  le dossier i18n/ du projet (Varians emploie alors ses propres
  traductions) ou remplacez ses fichiers par ceux du dossier i18n/ de
  Varians. Si vous aviez personnalisé des messages, reportez-les ensuite.
• Aucun changement des données TEI, JSON, ALTO/PAGE ni du format de
  project.xml.

VARIANS V0.8.7.0 — DOCUMENTS XML AUXILIAIRES

• Un projet peut réunir, à côté de l'édition, d'autres documents XML :
  fichier d'autorités (personnes, lieux), notes, etc. Menu
  Fichier ▸ Documents XML du projet : Ajouter un document XML… (un fichier
  situé hors du projet est copié dans xml/, sans jamais remplacer un
  fichier), Nouveau document XML… (élément racine au choix), Retirer le
  document du projet (le fichier n'est jamais supprimé).
• Une rangée d'onglets « Édition | … » apparaît au-dessus de la source XML
  dès qu'un document auxiliaire existe ; elle reste invisible pour un projet
  simple.
• Chaque document garde son historique d'annulation, sa position, son état
  « modifié » (*) et sa validation RELAX NG, qui suit son propre
  <?xml-model?>.
• Les manuscrits, la vue XSLT / CSS et les commandes des témoins ne
  concernent que l'édition : ils sont masqués pendant l'affichage d'un autre
  document, puis retrouvés tels quels. « Marquer la page » et
  « Double page… » n'écrivent jamais dans l'édition lorsqu'elle n'est pas
  affichée.
• Ctrl+S enregistre le document affiché ; avant de quitter ou de changer de
  projet, Varians propose d'enregistrer tous les documents modifiés. L'export
  web enregistre et utilise l'édition seule.
• project.xml : les documents sont déclarés par un élément facultatif
  <documents> (voir PROJECT_MANAGEMENT.md). Un projet sans document
  auxiliaire reste strictement inchangé. Limite : une version antérieure à
  0.8.7.0 ouvre un tel projet normalement, mais efface <documents> si l'on y
  enregistre les paramètres du projet.
• Aucun changement des données TEI, JSON, ALTO/PAGE ni du viewer web.

VARIANS V0.8.6.0 — RESTRUCTURATION, TESTS ET CORRECTIFS

• Code : editeur_tei.py, auparavant d'environ 7 900 lignes, est découpé en
  modules, un par responsabilité ; l'état d'un document ouvert est regroupé
  dans document_session.py. Carte des modules : docs/DEVELOPPEMENT.md.
• Tests : en plus des tests historiques, des tests pilotent la véritable
  fenêtre de Varians (tests/gui/) ; ils sont lancés automatiquement sur GitHub
  sous Linux et Windows à chaque envoi.
• Saisie : taper une nouvelle balise dans un long document ne fige plus
  l'éditeur (0,12 s par frappe au lieu de plusieurs dizaines de secondes sur
  le projet exemple).
• Synchronisation : une modification à l'intérieur d'une balise (par exemple
  edRef="#T" complété en "#T1") est aussitôt prise en compte.
• Vue XSLT / CSS : une erreur de feuille XSLT est signalée telle quelle
  (fichier, ligne, message) ; une transformation peut lire des fichiers
  locaux, mais ne peut ni écrire de fichier ni accéder au réseau.
• Fermer une fenêtre juste après l'ouverture d'un document, ou pendant le
  chargement d'images, n'affiche plus d'erreur dans la console.
• Aucun changement du format des projets (project.xml), des données TEI,
  JSON, ALTO/PAGE ni du viewer web.
• Historique : les rapports TEST_REPORT_*.txt, les addenda PASSATION_V*.md
  et RELEASE_MANIFEST_SHA256.txt cités ci-dessous sont dans docs/historique/ ;
  le dossier de passation V0.8.5.26.2 est dans docs/passation_V0.8.5.26.2/.

VARIANS V0.8.5.26.2 — CORRECTIF DU RAFRAÎCHISSEMENT RELAX NG

• Après une modification XML, les diagnostics attachés à une révision antérieure sont invalidés sans délai.
• Après la première ouverture du panneau de validation, le contrôle automatique différé se poursuit même si le panneau est masqué ou si XPath est ouvert.
• À la réouverture du panneau, Varians revalide si la révision courante n’a pas encore été contrôlée.
• Le signal QTextDocument.contentsChanged couvre également les modifications directes via QTextCursor et l’historique annuler/refaire.
• Les résultats tardifs d’un contrôle portant sur une ancienne révision ne sont jamais affichés comme diagnostics courants.
• La validation F8 demeure disponible ; aucune modification du schéma, du texte TEI, des images, des JSON ou du viewer web.

Ceci est un correctif ciblé fondé sur la distribution complète V0.8.5.26.1. Les sept langues et les aides sont conservées. Voir PASSATION_V0_8_5_26_2.md et TEST_REPORT_V0_8_5_26_2.txt.

--- HISTORIQUE DU README PRÉCÉDENT ---
VARIANS V0.8.5.26.1 — CORRECTIFS ERGONOMIQUES DU VIEWER WEB

• Recherche plein texte : « Graphies médiévales » est un simple libellé ; les trois cases u/v, i/j et c/t déclenchent directement les équivalences. Sans case : recherche exacte (hors casse).
• Export depuis l'éditeur : reprend exactement la liste des manuscrits visibles et leur ordre d'affichage au moment de l'export.
• Le pivot technique reste disponible pour la synchronisation même si son panneau est masqué, sans publication de ses images.
• La génération autonome depuis la ligne de commande garde le comportement historique : tous les témoins.

Les fonctions A01/A02/A03 de la V0.8.5.26 sont conservées. L'ancienne roadmap reste suspendue.

IMPORTANT : régénérer le fichier web_output/viewer.html après mise à jour. Pour distribuer un export filtré sans anciennes images, le copier avec ses seules ressources nécessaires dans un répertoire propre.
Voir PASSATION_V0_8_5_26_1.md et TEST_REPORT_V0_8_5_26_1.txt.

--- HISTORIQUE DU README PRÉCÉDENT ---
VARIANS V0.8.5.26 — VERSION INTERMÉDIAIRE DE RÉFÉRENCE

Nouveautés : A01 validation RELAX NG actualisée, A02 complétion automatique des noms d’attributs, A03 recherche plein texte avec équivalences médiévales dans le viewer web.

Base : V0.8.5.25.3. La synchronisation `<lb/>` vers les manuscrits secondaires n’a pas été remplacée. L’ancienne roadmap est suspendue et sera redéfinie.

Démarrage : python editeur_tei.py  |  Dépendances : pip install -r requirements.txt
Tests : python -m pytest -q
Export web : python -m web_viewer.generator project.xml
Voir PASSATION_V0_8_5_26.md et ROADMAP_EN_REDEFINITION.md.

--- HISTORIQUE DU README PRÉCÉDENT ---
CORRECTIF V0.8.5.25.3 — 14 octobre 2026
Le viewer exporté synchronise le clic sur le texte, les marqueurs de notes/variantes et les références éditoriales avec les lignes vérifiables des manuscrits.
La ligne sélectionnée est marquée en bleu et centrée dans la fenêtre du témoin.
Toute portion non ancrée ou clé de ligne introuvable produit un diagnostic, jamais une correspondance inventée.
IMPORTANT : regénérer le HTML depuis cette version ; un ancien viewer.html ne se met pas à jour automatiquement.

V0.8.5.25.3 : résolution des <lb edRef="#pivot"/> du viewer web sur le même ordre global de lignes physiques JSON que l’éditeur ; les <pb/> de folio ne réinitialisent plus les clés. Les témoins secondaires suivent uniquement leurs base_keys existants. Voir WEB_VIEWER_PIVOT_LB_PARITY.md.

Consulter PASSATION_V0_8_5_25_2.md et WEB_VIEWER_TEXT_CLICK_FIX.md.

VARIANS 0.8.5.25.1 — CORRECTIF NAVIGATION PAR LIGNES DU VIEWER WEB
===================================================================
Le numéro de folio dans <pb n="…"> ne correspond pas nécessairement à l'ID
physique des pages dans le JSON de synchronisation. Le viewer rapproche
désormais les pages par leurs liens explicites @facs vers <surface>/<zone>,
puis, uniquement lorsque le lien est certain, par ID technique exact ou
libellé exact unique d'un témoin identifié. Aucun rapprochement par rang,
position de Canvas ou ressemblance de texte n'est créé.
Le pivot et les témoins secondaires possédant des base_keys réels sont alors
affichés en recadrage de lignes plutôt qu'en mode pages. Les témoins non
synchronisés restent en mode pages. Voir WEB_VIEWER_LINE_SYNC_FIX.md,
PASSATION_V0_8_5_25_1.md et TEST_REPORT_V0_8_5_25_1.txt.

VARIANS 0.8.5.25 — IIIF HAUTE RÉSOLUTION DU VIEWER WEB
==========================================================
Nouveau module web_viewer/iiif.js : IIIF Image API v1/v2/v3, tailles selon
zoom et résolution, régions, limites annoncées dans manifest/info.json,
replis (région réduite, image entière recadrée localement, vignette).
Chargements obsolètes annulés lors des changements de page ou de témoin.
Images externes signalées explicitement : une archive HTML autonome ne
rend PAS un service IIIF accessible hors ligne ou sans autorisation.
Tests JS/Chromium complémentaires ; sept aides mises à jour.
Voir WEB_VIEWER_IIIF.md et TEST_REPORT_V0_8_5_25.txt.

VARIANS 0.8.5.24 — PARITÉ GÉOMÉTRIQUE DU VIEWER WEB
=====================================================
Marge de recadrage de 24 px, contexte des lignes limité aux colonnes et pages
physiques, polygones PAGE concaves avec tous leurs sommets et leurs bornes.
Zones TEI des doubles pages exprimées dans les pixels de l'image source,
sans multiplication abusive par l'échelle OCR. Repli sur l'image complète
pour les lignes sans géométrie ; aucune synchronisation fondée sur des liens
base_keys orphelins. Images locales manquantes consignées à l'export.
Accès localStorage facultatif, même en contexte de navigation restreint.

Voir WEB_VIEWER_GEOMETRY.md et TEST_REPORT_V0_8_5_24.txt.

VARIANS 0.8.5.23 — SURLIGNAGE BIDIRECTIONNEL DES BALISES XML
==============================================================
Le curseur dans une balise ouvrante OU fermante souligne les deux membres
correspondants en bleu pâle ; un jumelage ambigu n'est jamais inventé.
Imbrication, espaces de noms, autofermantes et XML mal formé : tests dédiés.
Aucune modification du XML, du renommage, du repliage ou des fichiers projet.
Voir XML_TAG_HIGHLIGHT.md et ROADMAP_REVISED_2026_10.md.

VARIANS 0.8.5.22 — REPLIAGE STRUCTUREL XML
===========================================
Nouveau : Affichage > Repliage XML, chevrons dans la marge, Ctrl+Alt+F
(élément courant) et Ctrl+Alt+Maj+F (tout déplier). Le XML source est
préservé intégralement. Guide technique : XML_FOLDING.md.

VARIANS 0.8.5.20 — DOUBLE PAGE COMPACTE, VIGNETTE ET MARQUAGE CIBLÉ
======================================================================

La commande « Double page… » partage désormais la barre d'outils du témoin.
La rangée supplémentaire « Folios » est retirée (les flèches continuent de
naviguer entre les parties logiques en mode page).

La fenêtre montre la VIGNETTE DE L'IMAGE ENTIÈRE, indépendamment du cadrage
synchronisé de l'éditeur. On peut déplacer la ligne rouge à la souris ; le
pourcentage reste éditable, et la position exacte est enregistrée en PIXELS
source dans les coordonnées TEI. Les images locales sont décodées à petite
résolution, les images IIIF sont récupérées en vignette asynchrone.

La terminologie est neutre : « Partie gauche » / « Partie droite » ; leurs
libellés peuvent identifier des folios, des pages ou d'autres unités.

« Marquer la page » emploie la zone de la partie actuellement affichée :
- en mode lignes synchronisées, d'après les coordonnées de la ligne courante ;
- en mode page, d'après la partie choisie ;
- si la ligne franchit la séparation, manque de géométrie ou est ambiguë,
  une fenêtre demande de sélectionner explicitement la partie.
Le <pb/> vise la zone choisie (facs="#…-left/right"), et pas la surface entière.

Les deux zones produites par Varians peuvent être réajustées à l'aide de la
même fenêtre, sans supprimer ni renommer les identifiants ni les <pb/> déjà
présents. Les autres zonages TEI restent protégés contre les remplacements.

Voir DOUBLE_PAGE_PARTS.md, FOLIO_NAVIGATION.md et TEST_REPORT_V0_8_5_20.txt.

VARIANS 0.8.5.19 — CORRECTION DU BOUTON « DOUBLE PAGE… »
========================================================

La commande fonctionne en mode page comme en mode lignes synchronisées.
Les dimensions et les surfaces sont contrôlées avant toute modification.

VARIANS 0.8.5.18 — Navigation par folios et images à double page

Affichage > État des témoins… : rapport des sources d’images, lignes et liens pivot.
Affichage > Actualiser les synchronisations… (Ctrl+Shift+R) : relire sans fermer l’éditeur.
Les modifications TEI et les fichiers JSON/ALTO/images sont préservés.
Documentation : WITNESS_DIAGNOSTICS.md et TEST_REPORT_V0_8_5_17.txt.

VARIANS 0.8.5.16 — Visibilité ET ordre des témoins affichés
===========================================================

Affichage > Choisir les témoins affichés… : cocher les témoins et les déplacer
avec Monter / Descendre. L'ordre des panneaux d'images est mémorisé localement
par projet, comme leur visibilité et leur hauteur. Le manuscrit pivot, les
identifiants de témoin, les JSON, les surfaces TEI et project.xml ne changent
pas. Les témoins masqués conservent leur position ; les nouveaux sont ajoutés
en fin de liste. Les sept traductions et aides sont actualisées.

Voir DISPLAY_NAVIGATION.md et TEST_REPORT_V0_8_5_16.txt.

VARIANS 0.8.5.15 — Images IIIF et diagnostic de synchronisation par lignes
==========================================================================

Correctif du visualiseur pour les manuscrits IIIF avec images de dimensions
variables et JSON de synchronisation nouvellement associés.

- Un aperçu IIIF ou une copie locale plus petite que le Canvas ne doit plus
  placer les contours ALTO/PAGE hors de l'image et perturber le zoom à 100 %.
- En mode page, les cadres sont recalculés dans les dimensions du bitmap
  réellement affiché, sans modifier les coordonnées source.
- Quand un service IIIF Image API est présent, la pleine résolution est
  demandée en priorité ; l'URL d'image du Manifest reste un repli.
- Un JSON de témoin dépourvu de base_keys ne déclenche toujours pas une
  fausse synchronisation. L'interface indique désormais explicitement la
  raison du maintien de la navigation par pages. Un JSON dont les clés ne
  correspondent à aucune ligne pivot est également signalé.
- Aucun fichier source, JSON, ALTO/PAGE, TEI ou cache projet n'est réécrit.
- Le cas particulier L ne peut être confirmé sans examiner alignments/L.json.
- Tests : tests/test_v08515_iiif_preview_scale_and_sync_diagnostics.py.

VARIANS 0.8.5.14 — Images IIIF préservées lors de l’ajout d’ALTO/PAGE
=====================================================================

Correctif non destructif de la régression d’affichage des témoins IIIF
sans JSON de synchronisation après import d’un ALTO/PAGE indépendant.

- Les images du manifeste IIIF (et leurs copies locales) restent les pages
  canoniques du témoin, que les fichiers OCR soient associés ou non.
- Les fichiers OCR enrichissent seulement les canvases identifiés avec certitude :
  lien manuel, identité IIIF, folio unique, nom exact d’une copie locale
  téléchargée et indexée. Jamais d’association par ordre de fichiers.
- Les ALTO/PAGE impossibles à associer sont conservés dans le cache dérivé,
  sans image fictive ; leur nombre apparaît dans l’infobulle du témoin.
- Les identifiants de page, de surface TEI, le JSON de synchronisation et
  les données des autres témoins restent inchangés.
- Le moteur commun protège également le viewer web.
- Documentation technique : IIIF_SYNC_RESOLUTION.md, IMAGE_SOURCES.md,
  DEVELOPER_HANDOFF.md et tests/test_v08514_iiif_alto_independence.py.

VARIANS 0.8.5.13 — Complétion des balises fermantes XML
======================================================

- Dans le XML source et les fragments, taper </ propose immédiatement la
  fermeture de l'élément ouvert le plus proche ; Entrée/Tab accepte, Échap
  ignore et Ctrl+Espace permet de rappeler la suggestion.
- Un QName partiellement saisi (</di) est complété sans ajouter de > en double.
- La suggestion respecte l'imbrication, les balises autofermantes, les espaces
  de noms et les zones non XML (commentaires, CDATA). Pas de devinette en cas
  de balisage momentanément ambigu. Les fonctions RNG existantes restent.
- Nouvelle documentation dans XML_EDITING.md, 7 aides linguistiques mises à
  jour et nouveaux tests ciblés.

VARIANS 0.8.5.8 — Correctif des lignes JSON partielles et <lb/> sans @n
=========================================================================

Reprise complète et non régressive de Varians 0.8.5.7.

- Un JSON Varians-Synchro décrivant un extrait de folio (par ex. lignes 41–68)
  génère autant de <lb/> que de lignes effectivement répertoriées (28), sans
  supposer que la première ligne commence à 1 ni compléter les lignes absentes.
- Un intervalle non continu fait l'objet d'un avertissement ; numéros dupliqués
  ou invalides : aucun <lb/> spéculatif.
- Les nouveaux <lb/> ne portent plus @n ; ils conservent edRef, sans @facs.
- Une page sélectionnée avec JSON `lines: []` conserve son <pb/>. Une page
  du JSON dépourvue d'image/surface sélectionnée est signalée dans l'aperçu.
- Le JSON, ses identifiants et les données TEI existantes ne sont pas altérés.
- Aides en français, anglais, allemand, japonais, tchèque, italien et russe
  mises à jour ; voir TEI_PIVOT_SCAFFOLD.md.

IMPORTANT : la génération ne peut être relancée sur une TEI déjà préparée.
Utilisez un projet neuf ou une copie dont le corps TEI est encore vide.

VARIANS 0.8.5.7 — correction de visibilité de la préparation TEI pivot

Correctif de l'interface de création : les options pb/lb sont désormais dans
une section dédiée juste sous « Point de départ », avant les ressources.
Les fenêtres Nouveau projet et Paramètres du projet disposent d'un défilement
vertical et de boutons de validation toujours visibles, y compris sur de
petits écrans. Le titre précise la version lancée (« Varians 0.8.5.7 »),
ce qui facilite la détection d'une ancienne exécution encore active dans
Spyder ou d'un raccourci vers une ancienne distribution.

Pour activer la préparation : Fichier > Nouveau projet > Commencer une
nouvelle transcription > section « Préparation de la transcription du
témoin pivot » > cocher pb (et conserver lb coché). La génération reste
volontaire et demande une confirmation après création du projet.

VARIANS 0.8.5.6 — préparation facultative de la TEI à partir du témoin pivot

Depuis un projet nouvellement créé ou les paramètres du projet, un témoin pivot
muni de surfaces et de fichiers ALTO/PAGE et/ou de synchronisation JSON peut
amorcer une transcription vide : <pb/> reliés aux surfaces par @facs et au
témoin par @edRef ; <lb/> facultatifs, décomptés par page, sans liens aux zones.
La génération est précédée d'un aperçu et d'une confirmation explicite ; une
sauvegarde datée protège le document. Les TEI déjà remplies sont intouchables.
Le moteur ne modifie pas les JSON, les base_keys ni les autres témoins.
Voir TEI_PIVOT_SCAFFOLD.md et TEST_REPORT_V0_8_5_6.txt.

VARIANS 0.8.5.5 — association fiable des pages synchronisées et des Canvas IIIF

Correctif développé à partir de la V0.8.5.4 complète (aucun retour à une version antérieure).
Nouveau module iiif_resolution.py : correspondance par Canvas, service IIIF Image,
URL d'image normalisée, identification OCR explicite ou folio unique.
Aucun lien par indice de manifeste ; le JSON Varians-Synchro et les base_keys
sont préservés. Association manuelle page JSON -> Canvas dans le sélecteur,
source locale / IIIF affichée et état du rapprochement.
Les nouveaux témoins IIIF privilégient une sélection explicite. L'export web
et l'éditeur partagent le même moteur. Voir IIIF_SYNC_RESOLUTION.md.

VARIANS 0.8.5.4 — association automatique prudente des images IIIF et des ALTO/PAGE

Dans la sélection des images IIIF, Varians propose désormais automatiquement
les associations ALTO/PAGE dont les noms d'image correspondent exactement
(extension et casse ignorées). Il exploite également le nom de l'image source
inscrit dans les fichiers OCR, pour gérer les XML renommés. Les correspondances
ambiguës restent à attribuer manuellement. Les liens enregistrés ont priorité.
Un bouton « Associer automatiquement (noms exacts) » permet de compléter les
associations des sélections déjà existantes. Aucun appariement par position.

La sélection des images et le gestionnaire IIIF de la V0.8.5.3 restent inchangés.
Voir IIIF_CANVAS_SELECTION.md et le rapport TEST_REPORT_V0_8_5_4.txt.

VARIANS 0.8.5.3 — sélection des canvases IIIF, liaisons OCR, tri naturel

NOUVEAU : lorsqu'un manuscrit IIIF comporte des centaines d'images, on peut
retenir seulement les folios utilisés pour l'édition, dans Paramètres du projet
→ Témoins → Modifier → « Choisir les images et associer les OCR… ».
L'identité du canvas (URI IIIF si disponible) est enregistrée dans project.xml.
Chaque image retenue peut être associée MANUELLEMENT à un fichier ALTO/PAGE,
même si les noms de fichiers ou l'ordre diffèrent totalement.

Les images exclues ne sont plus téléchargées en mode « sélection » et ne
provoquent plus la création de nouvelles surfaces TEI. Les surfaces existantes
ne sont jamais supprimées silencieusement : lors d'un changement de sélection,
Varians peut proposer de supprimer UNIQUEMENT les surfaces qui correspondent
exactement à sa génération initiale et qui ne sont ni annotées ni référencées.
La confirmation est facultative et une copie datée de la TEI est créée avant
suppression. En cas de doute, choisir « Non ».

Les nouvelles listes d'images locales et de fichiers ALTO/PAGE sont triées par
ordre numérique naturel (1r, 1v, 2r, …, 10r), et un bouton permet de réappliquer
ce tri aux listes existantes tout en conservant les ajustements manuels possibles.

Cette version conserve la prise en charge mixte ALTO/PAGE, l'export web et le
choix entre copies locales et IIIF distant. Voir IIIF_CANVAS_SELECTION.md,
PAGE_IIIF_LOCAL.md et TEST_REPORT_V0_8_5_3.txt.

VARIANS 0.8.5.2 — gestionnaire IIIF et téléchargement sélectif ALTO/PAGE

NOUVEAUTÉS : chaque témoin IIIF peut demander toutes les images du manifeste ou
uniquement celles associées de manière non ambiguë à un ALTO/PAGE fourni.
Le gestionnaire (Fichier → Gestionnaire de téléchargements IIIF…) affiche les
pages sélectionnées, téléchargées, manquantes et exclues ; téléchargement sur
thread distinct, pause/reprise/arrêt entre images, journal d'erreurs, reprise
sans re-télécharger les images terminées, et choix « tous les témoins ».
Le mode historique « toutes les pages » reste le défaut pour les projets
existants. Après enregistrement, le téléchargement ne bloque plus l'éditeur.
Les copies partielles restent exploitables en mode hybride ; les pages exclues
peuvent encore nécessiter le réseau. Paramètre d'export web inchangé.
Aide intégrée et textes d'interface mis à jour dans les sept langues.
Voir PAGE_IIIF_LOCAL.md § 6 et TEST_REPORT_V0_8_5_2.txt.

VARIANS 0.8.5.1 — correctif d'identité des lignes PERO OCR (ALTO / PAGE)

Cette version conserve toutes les évolutions de la 0.8.5.0 (PAGE XML,
polygones, copie locale des images IIIF, export web et les sept langues).
Correction ciblée : une migration ALTO → PAGE retrouve la même ligne
PERO OCR par son UUID commun même si le préfixe ou l'ordre change.
Les synchronisations éditoriales ne sont plus déplacées vers une ligne
présentant un autre UUID. Voir PAGE_IIIF_LOCAL.md et
TEST_REPORT_V0_8_5_1.txt.

VARIANS 0.8.5.1 — PAGE XML / ALTO / copie de travail IIIF locale

VARIANS — ÉDITEUR XML TEI POUR L'ECDOTIQUE — V0.8.4.2
=====================================================



NOUVEAUTÉ V0.8.4.2 — TRANSMISSION DÉVELOPPEUR ET INTERNATIONALISATION
-----------------------------------------------------------------------
- Le libellé de fichier « edition.xml » a été retiré de la barre d'outils :
  le nom du fichier reste disponible dans le titre de la fenêtre, où il est utile.
- Nouvelle documentation de maintenance : DEVELOPER_HANDOFF.md présente la
  philosophie, les invariants, l'architecture, les contrats de données, les
  risques de compatibilité et la procédure de modification ; CODE_MAP.md fournit
  une carte rapide modules/fonctions/tests.
- Cinq nouvelles traductions complètes de l'interface rejoignent le français et
  l'anglais : allemand, japonais, tchèque, italien et russe.
- L'aide F1 est elle aussi disponible dans les sept langues livrées.
- Les catalogues sont contrôlés pour l'identité des clés et des variables de
  formatage, afin d'éviter les erreurs au runtime.
- Voir DEVELOPER_HANDOFF.md, CODE_MAP.md, I18N_FORMAT.md et
  TEST_REPORT_V0_8_4_2.txt.


NOUVEAUTÉ V0.8.4.1 — XPATH ET AIDE DÉVELOPPÉE
-------------------------------------------------
- Un clic sur un résultat XPath sélectionne maintenant l'élément XML complet,
  depuis la balise ouvrante jusqu'à la fin de la balise fermante.
- Les éléments imbriqués de même nom utilisent le moteur structurel de paires
  XML ; les éléments autofermants sont sélectionnés intégralement.
- L'aide intégrée F1 a été entièrement développée et mise à jour en français
  et en anglais : projets, édition, RNG, XPath, indentation sûre, images,
  fac-similé, ALTO, synchronisation, affichage des témoins et viewer web.
- Voir TEST_REPORT_V0_8_4_1.txt.


NOUVEAUTÉ V0.8.4 — CONSOLIDATION DES MODES DE PROJET
------------------------------------------------------
- La présence d'un JSON d'alignement ne suffit plus à activer le mode ligne :
  le témoin de base doit contenir de vraies lignes de référence et un témoin
  secondaire de vrais `base_keys` (ou `keys816` en lecture historique).
- L'état de synchronisation est évalué sur le JSON brut, avant superposition
  d'un ALTO indépendant. Un ALTO ne peut donc jamais transformer un JSON vide
  en fausse synchronisation.
- Desktop et viewer web utilisent désormais les mêmes critères : un secondaire
  sans `base_keys` reste en mode page des deux côtés.
- Un JSON de base vide/provisoire + images/ALTO retombe proprement en mode page
  et ne masque plus les images du viewer web.
- Nouvelle matrice de non-régression couvrant TEI seule, images, ALTO et sync.
- Voir CONSOLIDATION.md et TEST_REPORT_V0_8_4.txt.


NOUVEAUTÉ V0.8.3 — AFFICHAGE ET NAVIGATION DE TRAVAIL
---------------------------------------------------------
- Nouveau menu « Affichage » entre « Fichier » et « Aide ».
- « Recharger les images » quitte la barre d'outils et rejoint ce menu.
- « Choisir les témoins affichés… » permet de cocher de 0 à n témoins parmi
  ceux du projet. Ce choix est mémorisé localement par projet et ne modifie pas
  project.xml.
- Les panneaux des témoins sont maintenant placés dans un splitter vertical :
  leur hauteur est redimensionnable et mémorisée. Un double-clic sur l'en-tête
  d'un témoin le maximise temporairement ; un second double-clic restaure les
  proportions précédentes.
- Si aucun témoin n'est affiché, toute la colonne images disparaît.
- Le menu « Langue » est désormais placé en bas du menu « Affichage ».
- La barre d'outils regroupe « Valider RNG », « Indenter » et « XPath » ; la
  recherche source est repoussée à droite.
- La synchronisation de sélection XML ↔ XSLT/CSS ne choisit plus la première
  occurrence globale d'une chaîne répétée. Varians transporte le paragraphe et
  le rang de l'occurrence à l'intérieur de ce paragraphe, avec repli
  positionnel si la transformation XSLT diffère légèrement.
- Voir DISPLAY_NAVIGATION.md et TEST_REPORT_V0_8_3.txt.


NOUVEAUTÉ V0.8.1 — INDENTATION TEI SÛRE
-----------------------------------------
- Nouveau bouton « Indenter » dans la barre d'outils.
- Le formateur ne modifie que les blancs structurels dont la réécriture est
  jugée sûre ; les contenus mixtes restent intacts.
- Protection absolue de xml:space="preserve" et des contextes contenant un
  <lb/> direct : aucun blanc nouveau n'est introduit autour de <lb/>.
- Le modèle RELAX NG indique si un élément peut contenir du texte ; en cas
  d'ambiguïté Varians s'abstient.
- custom-elements.xml accepte formatting="inline", "block" ou "preserve".
- XML mal formé : aucune réécriture. Tous les changements d'indentation sont
  groupés dans une seule opération Undo.
- Voir TEI_FORMATTER.md et TEST_REPORT_V0_8_1.txt.


NOUVEAUTÉ V0.8.0 — ÉDITION XML ASSISTÉE PAR PAIRES
----------------------------------------------------
- Nouveau moteur lexical `xml_tag_pairs.py`, indépendant de Qt, qui apparie
  correctement les balises XML y compris lorsque des éléments de même nom sont
  imbriqués. Commentaires, CDATA, instructions de traitement et déclarations
  ne sont jamais interprétés comme des éléments.
- Quand le curseur ou la sélection se trouve dans une balise ouvrante appariée,
  la balise fermante correspondante est surlignée avec le bleu pâle commun de
  Varians.
- Si une balise ouvrante complète est supprimée, sa fermeture correspondante
  est supprimée dans la même opération Undo, sans toucher au contenu intérieur.
  Le comportement couvre clavier, Couper et suppression par le menu contextuel.
- Si le QName d'une balise ouvrante est renommé, le QName de la fermeture
  associée est renommé automatiquement. Les attributs ne sont jamais modifiés.
- Les balises autofermantes ne sont pas concernées par l'appariement.
- Les automatismes sont déclenchés par `QTextDocument.contentsChange`, ce qui
  évite de rescanner/différencier tout le document à chaque frappe ordinaire.
- Voir XML_EDITING.md et TEST_REPORT_V0_8_0.txt.

HOTFIX V0.7.9.2 — MARQUAGE DE PAGE CONSERVATEUR
-------------------------------------------------
- « Marquer la page » est désormais une commande d’insertion uniquement.
- Si le curseur est à l’intérieur de n’importe quelle balise XML, y compris
  <pb/>, aucune insertion et aucune modification n’est effectuée.
- Le message « Placez le curseur dans le texte ou entre deux balises. » est
  affiché dans la barre d’état.
- Les positions immédiatement avant « < » et immédiatement après « > » restent
  des points d’insertion valides.
- Le garde-fou est vérifié avant toute synchronisation de <facsimile> : une
  commande refusée ne modifie donc absolument pas la TEI.
- Contrôles détaillés : TEST_REPORT_V0_7_9_2.txt.

HOTFIX V0.7.9.1 — FRONTIÈRES DU CURSEUR
- Ce hotfix historique a corrigé les positions immédiatement avant/après <pb/>.
- Depuis V0.7.9.2, le curseur à l’intérieur d’un <pb/> est lui aussi refusé : aucun balisage existant n’est modifié par « Marquer la page ».

NOUVEAUTÉ V0.7.9.1 — FAC-SIMILÉ TEI ET MODE PAGE
------------------------------------------------
- Les images du projet reçoivent un identifiant de surface TEI stable et un
  libellé « Folio / page ».
- Varians complète `<facsimile>` de façon incrémentale et non destructive ;
  aucune surface/zone existante n'est reconstruite ou supprimée automatiquement.
- Le bouton « Marquer la page » insère `<pb n="…" facs="#…"/>` uniquement hors de toute balise.
- Sans JSON de synchronisation, y compris lorsqu'un ALTO est présent, Varians
  affiche désormais la page entière. L'ALTO reste une géométrie facultative.
- Le dernier `<pb facs>` précédant le curseur détermine la page affichée.
- Le viewer web suit la même logique et embarque les images locales nécessaires.
- Voir FACSIMILE_PAGES.md pour les garde-fous et le modèle détaillé.
- Contrôles détaillés : TEST_REPORT_V0_7_9_1.txt.


NOUVEAUTÉ V0.7.8 — PAGES / IMAGES LOCALES / ALTO
---------------------------------------------------
- Une ressource ALTO indépendante n'est plus confondue avec une synchronisation
  TEI : elle ne fixe plus un nombre attendu de <lb> et n'active pas à elle seule
  la navigation synchronisée du témoin de base.
- Le nombre de lignes attendu vient exclusivement du JSON de synchronisation
  explicite et est calculé avant toute superposition d'un ALTO indépendant.
- Les photographies locales sans ALTO sont désormais feuilletées une page à la
  fois ; l'ancien contexte ±1, conçu pour trois lignes ALTO, n'empile plus deux
  ou trois pages photographiques dans le même panneau.
- Le statut du panneau indique clairement la position courante (page n/N).
- Les fusions ressources ont été testées avec 4 images + 4 ALTO, ainsi qu'avec
  synchronisation + ALTO + images : toutes les pages sont conservées et les
  base_keys existants restent intacts.

NOUVEAUTÉ V0.7.7 — STABILISATION INTERFACE / PROJETS
----------------------------------------------------
- La couleur de sélection/survol claire du panneau XPath est désormais la
  palette commune des listes et tableaux de Varians, notamment RELAX NG.
- Lorsqu'aucune source d'image n'existe dans le projet, la colonne manuscrits
  est entièrement masquée ; le viewer web devient lui aussi textuel pleine largeur.
- Les éditions créées from scratch structurent maintenant les témoins dans
  sourceDesc/listWit/witness avec xml:id, utilisable directement par @wit.
- À chaque ouverture de document, tous les diagnostics RELAX NG précédents sont
  vidés avant validation afin qu'un autre projet ne puisse laisser de résultats
  visuellement obsolètes.







NOUVEAUTÉ V0.7.6 — SYNCHRONISATION FACULTATIVE ET AJOUTABLE ULTÉRIEUREMENT
----------------------------------------------------------------------------
La synchronisation inter-témoins est désormais gérée comme une ressource
facultative au même titre que les images et les ALTO. Dans la fiche d’un
témoin, un JSON de synchronisation peut être ajouté, remplacé ou retiré à
n’importe quel moment. Par défaut, un nouveau JSON peut être copié dans
alignments/<sigle>.json pour garder le projet portable ; il est aussi possible
de conserver une référence externe. Les sources d’images et ALTO déjà
déclarées ne sont pas modifiées par cette opération.

NOUVEAUTÉ V0.7.5 — ALTO INDÉPENDANT
=====================================

Les fichiers ALTO peuvent désormais être associés à un témoin indépendamment
de sa source d’images et de son fichier de synchronisation. Dans la fiche d’un
témoin, choisir « Fichiers ALTO séparés », ajouter les XML ALTO et choisir de
les copier dans le projet ou de conserver des références externes.

Varians extrait les pages, dimensions, TextLine, bbox et texte HTR/OCR. Quand
un fichier de synchronisation existe déjà, les données ALTO sont fusionnées en
préservant les base_keys, scores et autres métadonnées. Sans synchronisation,
les lignes ALTO restent utilisables comme structure physique du témoin.

L’association avec des images locales privilégie le nom d’image déclaré dans
sourceImageInformation/fileName puis utilise l’ordre des listes comme repli.

NOUVEAUTÉ V0.7.4 — IMPORT DE MANIFEST IIIF
=============================================
- La fiche d’un témoin propose maintenant « Manifest IIIF ».
- Les Manifest IIIF Presentation API 2 et 3 sont pris en charge.
- Varians extrait automatiquement l’ordre des canvases, leurs libellés,
  dimensions, URL d’image et services IIIF Image API.
- Le Manifest est mis en cache sous `iiif/<sigle>.manifest.json` dans le projet :
  l’ouverture du projet ne dépend donc pas d’un nouveau téléchargement des
  métadonnées.
- Le bouton « Charger / actualiser » permet de tester l’URL et affiche le nombre
  de pages et la version Presentation détectée.
- Si un alignement ALTO existe déjà, les nouvelles images IIIF remplacent
  seulement la couche visuelle, dans le même ordre ; lignes et `base_keys` sont
  conservés.

Voir IMAGE_SOURCES.md et TEST_REPORT_V0_7_4.txt.


NOUVEAUTÉ V0.7.3 — IMAGES LOCALES
===================================
- La fiche d’un témoin propose maintenant « Images locales ».
- Plusieurs JPEG/PNG/TIFF/BMP/WebP peuvent être sélectionnés, réordonnés et
  recevoir des libellés éditoriaux.
- Par défaut, Varians copie les images dans `images/<sigle>/` pour rendre le
  projet portable ; il est aussi possible de conserver des références externes.
- Un témoin sans ALTO ni synchronisation peut feuilleter ces images de manière
  autonome dans l’application de bureau.
- Si un alignement existe déjà, les images locales remplacent seulement la source
  visuelle des pages ; les lignes ALTO et `base_keys` sont préservés.
- L’affichage local utilise l’auto-orientation EXIF de Qt.

Voir IMAGE_SOURCES.md, PROJECT_MANAGEMENT.md et TEST_REPORT_V0_7_3.txt.

NOUVEAUTÉ V0.7.2 — TÉMOIN SANS IMAGE EXPLICITE
================================================
- La source d’image est désormais un choix explicite dans la fiche d’un témoin.
- « Aucune image pour le moment » est un état normal et persistant du projet.
- Ce choix est sérialisé sous <images type="none"/> dans project.xml.
- Les anciens témoins sans bloc <images> restent en mode automatique : les
  images décrites dans leurs anciens JSON d’alignement continuent à fonctionner.
- Le modèle réserve déjà les types files et iiif pour les prochaines étapes.

NOUVEAUTÉ V0.7.1 — NOUVELLE TRANSCRIPTION « FROM SCRATCH »
---------------------------------------------------------------
- Fichier > Nouveau projet… propose maintenant deux points de départ :
  * une édition TEI existante ;
  * une nouvelle transcription sans fichier XML préalable.
- Dans le second cas, Varians crée automatiquement `xml/edition.xml` avec un
  `teiHeader` minimal, un `<body><p>…</p></body>` prêt à éditer et le titre du
  projet.
- Aucun fichier image, ALTO ou synchronisation n'est requis : un premier témoin
  sans ressource suffit.
- En mode de schéma automatique, le nouveau TEI reçoit une instruction
  `xml-model` vers TEI All afin de rendre disponibles validation et complétion
  RNG dès que le schéma est accessible ; le cache de Varians permet ensuite la
  réutilisation hors ligne.
- Le mode schéma projet et le mode sans schéma restent disponibles.

Voir PROJECT_MANAGEMENT.md et TEST_REPORT_V0_7_1.txt.

NOUVEAUTÉ V0.7.0 — SOURCES D’IMAGES FLEXIBLES / TÉMOINS SANS RESSOURCES
--------------------------------------------------------------------------
- Première couche du nouveau modèle de ressources : une page peut utiliser une
  source `image` de type `iiif`, `file` ou `none`.
- Les anciens blocs `iiif` restent entièrement compatibles et ne nécessitent
  aucune migration.
- Les fichiers locaux sont déjà compris par le moteur d’affichage de bureau
  lorsqu’un JSON les déclare manuellement ; l’assistant d’import arrivera dans
  une version ultérieure.
- Un témoin peut désormais être déclaré dans project.xml sans fichier
  `alignment`. L’édition TEI fonctionne alors sans image, ALTO ni
  synchronisation.
- Le contrôle du nombre de <lb> n’impose plus de total attendu lorsqu’aucun
  alignement du témoin de base n’est disponible.
- Le viewer web continue à fonctionner pour les projets IIIF existants et sait
  transporter le nouveau bloc générique dans ses données ; le paquetage des
  images locales sera ajouté avec l’interface d’import.

Voir IMAGE_SOURCES.md, ALIGNMENT_FORMAT.md et PROJECT_MANAGEMENT.md.

NOUVEAUTÉ V0.6.4 — WRAP VISUEL DANS L’ÉDITEUR DE FRAGMENT
-------------------------------------------------------------
- L’éditeur de fragment TEI dispose maintenant de la même case « Retour
  automatique à la ligne (affichage uniquement) » que la vue XML source.
- Le repli reste purement visuel : il ne modifie ni le XML, ni les numéros de
  lignes logiques, ni les offsets utilisés pour la validation et la réinjection.
- La préférence est mémorisée localement pour les ouvertures suivantes. Lors de
  sa première utilisation, elle hérite du réglage de la vue XML source.

NOUVEAUTÉ V0.6.3 — ÉDITION DANS LE SOUS-DOSSIER XML
-------------------------------------------------------
Les nouveaux projets placent désormais le document TEI dans `xml/edition.xml`.
`project.xml` reste le seul fichier XML de configuration directement visible à
la racine d'un dossier projet, afin d'éviter de confondre le projet et l'édition.

Nouvelle arborescence :
  project.xml
  xml/
    edition.xml
  alignments/
  rendering/
  i18n/
  web_output/

Les anciens projets avec `edition.xml` à la racine restent entièrement lisibles :
Varians respecte le chemin déclaré dans `<edition file="…"/>` et ne déplace pas
automatiquement leurs fichiers.

NOUVEAUTÉ V0.6.2 — ÉTAT « AUCUN PROJET OUVERT »
---------------------------------------------------
- Correction du texte affiché après fermeture de l’écran d’accueil lorsqu’aucun
  projet n’est ouvert : le message ne peut plus être rogné verticalement.
- L’état vide est maintenant placé dans un panneau central de largeur contrôlée,
  avec hauteur minimale, marges internes et retour à la ligne explicite.
- Aucun autre comportement de la V0.6.1 n’est modifié.


NOUVEAUTÉ V0.6.1 — LISTES DE POINTEURS ET LISIBILITÉ XPATH
-------------------------------------------------------------
- Dans le panneau de résultats XPath, le survol et la sélection utilisent
  désormais des bleus très pâles afin de conserver un contraste élevé du texte.
- Ctrl+Espace reconnaît les listes de pointeurs lorsque toutes les valeurs
  proposées commencent par #. Les pointeurs déjà présents sont retirés de la
  liste des propositions.
- Après <rdg wit="#T2|">, les valeurs restantes du projet sont proposées et
  l'espace séparateur est inséré automatiquement.
- Dans <rdg wit="#T2 #T|">, seul le token partiel #T est remplacé : la valeur
  déjà saisie #T2 est conservée. Les pointeurs placés à droite du curseur sont
  eux aussi exclus afin d'éviter les doublons.


NOUVEAUTÉ V0.6.0 — CUSTOM-ELEMENTS : AIDE DE SAISIE DISTINCTE DU RNG
-----------------------------------------------------------------------
- Ctrl+E et Ctrl+Espace fusionnent désormais les suggestions du RELAX NG et
  celles de rendering/custom-elements.xml en affichant leur provenance :
  « RNG », « Projet » ou « RNG + Projet ».
- Ces indications séparent explicitement validité et commodité : une suggestion
  Projet n'est jamais présentée comme une règle de validité RELAX NG.
- custom-elements.xml peut fournir des listes de valeurs d'attribut avec
  valuesMode="append" ou valuesMode="replace". Le mode replace ne restreint que
  les propositions de l'interface, jamais le schéma.
- Les valeurs peuvent être explicites (<value>…) ou dynamiques. La source
  witnesses génère les pointeurs à partir des témoins déclarés dans project.xml.
  Le fichier livré configure donc rdg/@wit sans figer #T1/#T2/#P dans le logiciel.
- Le logo Varians fourni par le projet remplace définitivement l'illustration
  provisoire de la V0.5.9.

Voir CUSTOM_ELEMENTS.md, RNG_COMPLETION.md, help/fr.html et help/en.html.

NOUVEAUTÉ V0.5.9 — SESSION, MARQUE ET CTRL+E PILOTÉ PAR LE RNG
-----------------------------------------------------------------
- Varians rouvre au démarrage le dernier projet qui était encore ouvert lorsque
  l'application a été quittée. La préférence est distincte de la liste des récents.
- Fichier > Fermer le projet (Ctrl+W) revient à l'accueil sans quitter Varians et
  empêche ce projet d'être rouvert automatiquement au prochain démarrage.
- L'accueil devient une carte centrale compacte : logo Varians, nom « Varians »
  en Cormorant Garamond SemiBold lorsqu'elle est installée, sous-titre, responsable,
  version et logos institutionnels CIHAM/CNRS.
- Aide > À propos… réaffiche la même identité visuelle dans une boîte dédiée.
- Ctrl+E interroge désormais le RNG à la position exacte de la sélection/du curseur
  et propose en premier les éléments autorisés. Le champ reste éditable afin de
  préserver le fonctionnement historique pendant la correction d'un document.
- Les attributs configurés dans custom-elements.xml continuent d'être ajoutés après
  le choix de l'élément ; l'enrichissement/restriction des suggestions par ce fichier
  reste l'étape suivante.

Voir RNG_COMPLETION.md, PROJECT_MANAGEMENT.md, help/fr.html, help/en.html et
TEST_REPORT_V0_5_9.txt.

NOUVEAUTÉ V0.5.8 — WRAP VISUEL, XPATH ET CORRECTIF CTRL+ESPACE
-------------------------------------------------------------------
- Correction de Ctrl+Espace juste avant la fermeture d'une balise vide :
  <lb edRef="#T1"|/> est désormais reconnu comme contexte d'attribut et propose
  les attributs encore autorisés par le RNG.
- La vue XML source dispose d'une case « Retour automatique à la ligne » : le
  repli est purement visuel, ne modifie pas le XML et ne crée pas de nouveaux
  numéros de lignes logiques. Le choix est mémorisé localement.
- Une recherche XPath a été ajoutée (bouton XPath / Ctrl+Shift+F). Les résultats
  sont affichés dans un panneau inférieur ; un simple clic place le curseur sur
  l'élément correspondant dans le XML.
- Les expressions XPath standards avec le préfixe tei: sont acceptées. Pour le
  cas courant d'une TEI à espace de noms par défaut, une requête simple comme
  //note est automatiquement réinterprétée comme //tei:note si nécessaire.
- La future extension de custom-elements.xml pourra fournir des valeurs de saisie
  recommandées ou plus restrictives (par ex. rdg/@wit = #T1, #T2, #P) sans
  confondre cette aide éditoriale avec la validité RELAX NG.

Voir help/fr.html, help/en.html, RNG_COMPLETION.md et TEST_REPORT_V0_5_8.txt.


NOUVEAUTÉ V0.5.7 — ACCUEIL, AIDE ET VALEURS D’ATTRIBUTS RNG
-------------------------------------------------------------
- L'application démarre désormais sans charger le projet de démonstration.
- La fenêtre est maximisée au démarrage et lors du passage à un autre projet.
- Un écran d'accueil léger affiche le titre du projet logiciel, Marjorie Burghart
  comme responsable / Principal Investigator, les logos CIHAM et CNRS et la version.
  Il disparaît au premier clic, sans bloquer l'action cliquée.
- Le projet de démonstration reste livré sous project.xml mais ne s'ouvre plus
  automatiquement.
- Un menu Aide a été ajouté à côté de Fichier : Enigma, Dictionnaire de Latin,
  puis l'aide intégrée du logiciel (F1). Les ressources en ligne s'ouvrent dans
  le navigateur système.
- Ctrl+? ouvre https://www.vocabula.lat/?q= avec le texte sélectionné ; à défaut,
  le mot sous le curseur est utilisé.
- Ctrl+Espace complète maintenant les valeurs d'attributs lorsque le RNG fournit
  une énumération finie explicite via value / choice / ref. Les patterns ouverts
  (text, data, listes libres...) ne produisent volontairement aucune pseudo-liste.
- Les annotations étrangères présentes dans les RNG TEI générés sont ignorées
  lors du calcul de ces énumérations.

Voir RNG_COMPLETION.md, help/fr.html, help/en.html et TEST_REPORT_V0_5_7.txt.


NOUVEAUTÉ V0.5.6 — CTRL+S SANS RECOMPILATION RNG INUTILE
----------------------------------------------------------
- Les schémas RELAX NG compilés sont désormais mis en cache.
- Le cache est invalidé automatiquement si le RNG racine ou un include/externalRef local change.
- Ctrl+S réutilise le résultat du contrôle automatique de bonne formation lorsqu'il correspond exactement à la révision courante.
- Si F8/l'ouverture a déjà validé la même révision avec le même schéma, Ctrl+S réutilise également ce résultat RNG.
- La sauvegarde n'extrait le texte de l'éditeur qu'une seule fois.
- Le fichier .bak est conservé par renommage atomique au lieu d'une copie intégrale préalable ; le nouveau contenu est d'abord écrit dans un temporaire du même dossier.
- Les avertissements XML mal formé / RNG invalide restent en place : aucun garde-fou n'est supprimé.

Voir RELAXNG_VALIDATION.md et TEST_REPORT_V0_5_6.txt pour les détails.

NOUVEAUTÉ V0.5.5 — COMPLÉTION ET CONTRÔLE XML PLUS FLUIDES
------------------------------------------------------------
- Ctrl+Espace conserve maintenant des points de reprise lexicaux : après une modification locale, il ne rescane plus systématiquement tout le document depuis le début.
- La résolution xml-model/RNG est réutilisée tant que les déclarations xml-model n'ont pas changé ; un RNG distant n'est donc plus re-résolu à chaque complétion.
- Le contrôle automatique de bonne formation XML reste actif, mais son parsing complet s'effectue hors du thread graphique après une courte pause de saisie.
- Le même instantané de texte sert au contrôle XML et à la reconstruction des repères <lb>, évitant une seconde lecture intégrale.
- Lors d'une frappe textuelle ordinaire, les positions des <lb> sont ajustées par décalage au lieu de relancer un balayage complet des milliers de balises. Un balayage complet reste déclenché si l'édition touche réellement la structure des balises.
- Les validations explicites nécessaires à la sauvegarde et F8 restent synchrones : aucun garde-fou de validité n'est supprimé.

Voir RNG_COMPLETION.md et TEST_REPORT_V0_5_5.txt pour les détails.

NOUVEAUTÉ V0.5.4 — POSITION DANS LES SÉQUENCES RELAX NG
--------------------------------------------------------
- Ctrl+Espace tient maintenant compte des frères directs déjà présents avant le curseur.
- Les structures group, choice, optional, zeroOrMore, oneOrMore et interleave sont conservées dans le modèle de complétion.
- Dans une séquence A puis B, après A seul B est proposé.
- Lorsque le curseur est au milieu d'un contenu existant, les frères situés à droite servent aussi de contrainte afin d'éviter les insertions incompatibles.
- Si le contenu déjà présent à gauche est lui-même invalide, le moteur revient volontairement à la liste large du parent pour rester utile pendant la correction.
- Le correctif V0.5.3 des contextes <rdg|> / <rdg |> / <rdg wi|> est conservé.
- À ce stade elles ne l’étaient pas encore ; la complétion des valeurs finies est désormais réalisée en V0.5.7.
- La validation F8 reste l’autorité pour la validité du document.

Voir RNG_COMPLETION.md et TEST_REPORT_V0_5_4.txt pour les détails.

NOUVEAUTÉ V0.5.3 — CONTEXTE DES BALISES OUVRANTES
--------------------------------------------------
- <rdg|>, <rdg |> et <rdg wi|> sont correctement reconnus comme contextes d'attributs.
- <rdg>| reste un contexte de contenu d'élément.

NOUVEAUTÉ V0.5.1 — XML-MODEL ET ÉTATS DE VALIDITÉ
---------------------------------------------------
- Trois modes de schéma : détection automatique <?xml-model?>, schéma du projet, aucun RNG.
- Les href RNG relatifs et distants sont pris en charge ; les schémas distants et leurs dépendances sont mis en cache.
- Un bouton ↻ du panneau permet de rafraîchir un schéma distant.
- Les déclarations Schematron de <?xml-model?> sont détectées et signalées (leurs règles sont appliquées depuis la V0.9.2.3).
- Onglets rouge pâle : XML non bien formé.
- Onglets orange pâle : XML bien formé mais invalide selon RELAX NG.
- La sauvegarde est désormais autorisée dans les deux cas après un avertissement explicite.
- L'éditeur de fragment reste strict : il refuse toujours d'appliquer un fragment qui rendrait le document mal formé.

Voir RELAXNG_VALIDATION.md pour le contrat détaillé.

NOUVEAUTÉS V0.4
----------------
Le menu Fichier contient maintenant :
- Nouveau projet… (Ctrl+N)
- Ouvrir un projet… (Ctrl+O)
- Réouvrir un projet récent…
- Paramètres du projet…
- Enregistrer l'édition (Ctrl+S)
- Enregistrer l'édition sous… (Ctrl+Maj+S)
- Configuration Ctrl+E…
- Générer le viewer web
- Quitter (Ctrl+Q)

NOUVEAU PROJET
--------------
L'assistant « Nouveau projet… » demande un dossier vide, un point de départ (TEI existante ou nouvelle transcription), une langue et
les témoins avec leurs fichiers d'alignement JSON. L'un des témoins est défini
comme témoin de base.

Le projet créé est autonome :
  project.xml
  xml/
    edition.xml
  alignments/
  rendering/
  i18n/
  web_output/

Les ressources génériques de rendu et d'internationalisation sont copiées dans
le nouveau projet. Les alignements doivent déjà exister dans cette V0.4 ; ils
seront à terme produits par l'outil d'alignement séparé TEI ↔ ALTO.

PARAMÈTRES DU PROJET
--------------------
« Fichier > Paramètres du projet… » permet de modifier graphiquement :
- le titre et la TEI ;
- la langue ;
- XSLT / CSS / custom-elements.xml ;
- le dossier i18n ;
- le dossier et le nom du viewer web ;
- les témoins, leurs libellés et alignements ;
- le témoin de base.

Avant modification, project.xml est copié en project.xml.bak. Le projet est
rechargé après sauvegarde des paramètres.

PROJETS RÉCENTS
---------------
L'application mémorise jusqu'à 10 project.xml récemment ouverts. Cet historique
est une préférence locale de l'application et n'est jamais écrit dans un projet.
Le sous-menu « Réouvrir un projet récent… » permet de passer rapidement d'une
édition à l'autre et de nettoyer la liste.

Un chemin récent qui n'existe plus est retiré de la liste lorsqu'on le choisit.

PLUSIEURS PROJETS
-----------------
Chaque édition possède son propre dossier et son propre project.xml ; aucune
configuration spécifique à une édition n'est supposée globale. On peut donc
maintenir plusieurs éditions/projets et passer de l'un à l'autre via les récents.

La V0.4 conserve une seule fenêtre de projet active à la fois. Le format et la
gestion des projets n'empêchent pas une évolution ultérieure vers plusieurs
fenêtres simultanées.

INTERFACE ET CORRECTIONS V0.3 CONSERVÉES
----------------------------------------
- les onglets XML source / Vue XSLT-CSS restent l'interface principale ;
- pas de boutons redondants XML/XSLT dans la barre ;
- pas de bouton « Aller au XML » ;
- Configuration Ctrl+E s'édite dans un éditeur XML interne ;
- correction du tremblement liée aux scrollbars des viewers ;
- internationalisation externe FR/EN ;
- générateur web dans web_viewer/.

INTERNATIONALISATION
--------------------
Les textes visibles sont dans :
  i18n/fr.xml
  i18n/en.xml

Les catalogues ont les mêmes clés et incluent maintenant les dialogues de
création/modification de projet et le menu des projets récents.
Voir I18N_FORMAT.md.

LANCEMENT
---------
Démarrage normal, sans projet chargé :
  python editeur_tei.py

Ouverture directe d'un projet précis :
  python editeur_tei.py chemin/vers/project.xml

Sous Windows : lancer_editeur.bat

VIEWER WEB
----------
Depuis l'éditeur :
  Fichier > Générer le viewer web

Indépendamment :
  python web_viewer/generator.py project.xml

DOCUMENTATION
-------------
PROJECT_MANAGEMENT.md  gestion des projets V0.4
ALIGNMENT_FORMAT.md    contrat des fichiers d'alignement
I18N_FORMAT.md         format des traductions
RELAXNG_VALIDATION.md  validation RELAX NG et panneau d’erreurs

TESTS EFFECTUÉS
---------------
- complétion des valeurs d'attributs RNG finies et refus des patterns ouverts ;
- contexte de valeur d'attribut entre guillemets et remplacement de la valeur entière ;
- accueil sans projet, présence des ressources/logo/aide et cohérence FR/EN ;
- complétion RNG positionnelle : séquences, choix, optionnels, répétitions et interleave ;
- prise en compte des frères XML avant et après le curseur ;
- séquences exprimées par plusieurs <ref> frères ;
- compilation syntaxique de tous les modules Python ;
- parsing FR/EN et mêmes clés de traduction ;
- création programmatique d'un nouveau projet autonome ;
- chemins relatifs vérifiés dans le project.xml créé ;
- relecture du projet créé avec project_config.py ;
- modification/sérialisation d'un projet ;
- génération du viewer web : 3 témoins et 3790 lignes de base.

LIMITATION DE TEST
------------------
PySide6 n'est pas installé dans l'environnement de construction utilisé ici.
Les nouveaux dialogues Qt n'ont donc pas pu être manipulés graphiquement ; leur
syntaxe et leur branchement ont été contrôlés statiquement, et toute la logique
de fichiers/projets a été testée hors interface.

V0.4.1 — correctif <lb break="no"/>
-----------------------------------
Correction de la vue XSLT lorsque le même nœud texte XML est situé entre deux
<lb break="no"/> (par exemple deux témoins différents). La XSLT nettoie
maintenant les espaces de début ET de fin du nœud texte dans ce cas.
Exemple corrigé : ope + <lb edRef="#T1" break="no"/> + rosa -> operosa.
Aucune modification du générateur web n'était nécessaire.

V0.4.2 — Choix de la source XSLT
--------------------------------
Fichier > Nouveau projet… : « XSLT par défaut de l’éditeur » est le choix
initial. La XSLT n'est alors pas copiée dans le dossier du projet : les
correctifs de la XSLT installée sont utilisés automatiquement.
« XSLT personnalisée » crée au contraire une copie locale modifiable.
Fichier > Paramètres du projet… permet de changer de mode ensuite.
Les projets antérieurs continuent à utiliser leur XSLT propre sans migration
implicite ; aucune XSLT existante n'est écrasée ou supprimée.
Lire XSLT_POLICY.md pour les détails et la procédure de migration.

V0.4.3 — Menu Fichier compact et recherche XML sécurisée
--------------------------------------------------------
- Le menu déroulant « Fichier » se trouve désormais SUR la barre d'outils,
  à gauche. La barre de menu distincte a été supprimée pour gagner en hauteur.
- Le contenu du menu et les raccourcis existants (Ctrl+N/O/S/Maj+S/Q)
  restent disponibles, ainsi que les projets récents.
- Dans l'onglet XML source, la recherche souligne visuellement son résultat
  d'un jaune très vif, sans le sélectionner dans le document éditable.
  Ainsi, Entrée ne remplace plus le texte par un retour à la ligne.
- Après une recherche, le focus retourne au champ « Rechercher source » :
  Entrée passe à l'occurrence suivante ; les boutons « Précédent » / « Suivant »
  et les raccourcis F3 / Maj+F3 fonctionnent toujours.
- La même sécurité s'applique à la recherche dans l'éditeur de fragments.
- Le résultat courant reste surligné même si l'onglet XML n'a pas le focus ;
  le surlignage disparaît si l'on modifie le texte ou si la recherche échoue.
- Les versions V8o/V11, les données TEI, les alignements, le projet et la XSLT
  restent inchangés. L'internationalisation FR/EN est conservée.

Pour contrôler le mécanisme sans installation Qt :
  python tests/test_recherche_sans_qt.py

Les vérifications GUI du menu et du surlignage restent à réaliser avec PySide6.

V0.4.4 — Ctrl+E : imbrication et insertion sans sélection
--------------------------------------------------------
- Avec texte sélectionné : Ctrl+E entoure la sélection, puis laisse sélectionné
  le NOUVEL élément complet (balises comprises). Un second Ctrl+E peut entourer
  immédiatement le premier élément (ex. <rdg><app>…</app></rdg>).
- Sans sélection : Ctrl+E + « note » produit <note></note>, avec le curseur
  entre les balises ; Ctrl+E + « lb/ » produit <lb/>.
- Les attributs de custom-elements.xml sont conservés. Sans sélection, si un
  attribut n'a pas de defaultValue, le curseur reste d'abord entre ses guillemets.
- Fonctionne dans l'onglet XML source et dans l'éditeur de fragments, en FR/EN.
- Les projets et leurs personnalisations ne sont pas modifiés.
- Tests hors Qt : python tests/test_ctrl_e_sans_qt.py

V0.4.5 — Ctrl+E : sélection intérieure, compatible avec l'usage Oxygen
------------------------------------------------------------------------
- Quand du texte est sélectionné, Ctrl+E l'entoure de balises et conserve
  exactement LE TEXTE sélectionné, sans les balises nouvellement insérées.
- Enchaînement : [uerbum] → Ctrl+E app → <app>[uerbum]</app>
  → Ctrl+E rdg → <app><rdg>[uerbum]</rdg></app>.
  (Les crochets [ ] représentent la sélection, pas du XML.)
- Cette correction remplace le comportement de la V0.4.4 qui sélectionnait
  le bloc entier et pouvait conduire à une imbrication inversée.
- La direction d'une sélection faite de droite à gauche est aussi conservée.
- Sans sélection, comportement V0.4.4 inchangé : insertion <note>|</note>,
  insertion <lb/>, attributs sans defaultValue prioritaires.
- Le changement vaut pour la source XML et l'éditeur de fragments.
- Tester hors Qt : python tests/test_ctrl_e_sans_qt.py.


CORRECTIF V0.4.6 — SPYDER ET MODULES DES ANCIENNES VERSIONS
---------------------------------------------------------
Lorsque plusieurs versions ont été exécutées dans le même noyau Spyder,
Python peut réutiliser project_management.py / project_config.py / i18n.py
provenant d'un autre dossier. Le symptôme est par exemple :
« cannot import name create_local_xslt_if_needed from project_management »
avec un chemin pointant vers V0.4 au lieu de V0.4.5.

L'éditeur V0.4.6 place son propre dossier en tête du chemin de recherche
et élimine de la mémoire les modules de CETTE application chargés depuis
d'autres versions. Cela n'affecte pas les fichiers XML du projet.

Pour démarrer dans Spyder, lancez editeur_tei.py depuis le dossier V0.4.6.
En cas de blocage dû à un noyau déjà instable, redémarrer le noyau Python
de Spyder reste un dépannage possible, mais ne devrait plus être requis.

Si vous ouvrez un projet précédemment créé, utilisez
Fichier > Ouvrir un projet… et sélectionnez son project.xml.


MISE À JOUR V0.4.7 — RECHERCHE DANS LA VUE XSLT
--------------------------------------------------
Dans la vue XSLT, rechercher « effeminatus » trouve désormais aussi la forme
affichée « effe[WORD JOINER]minatus » (U+2060 au point de jonction d'un
<lb break="no"/>). Le texte visible et les marqueurs de synchronisation avec
les images ne sont pas modifiés.

La recherche riche repose sur QTextDocument.find(QRegularExpression) et accepte
U+2060 entre les caractères du mot recherché, en conservant les positions
exactes de QTextCursor pour sélectionner et synchroniser le passage. Elle
continue à distinguer les VRAIS espaces de ces caractères invisibles.
Le champ de recherche garde le focus (Entrée = occurrence suivante).

Les deux modes XSLT (par défaut de l'éditeur / personnalisée) restent pris
en charge ; ce correctif s'applique au moteur de recherche de l'éditeur et
ne nécessite donc pas de mise à jour des fichiers projet ni des XSLT locales
qui utilisent U+2060. L'isolation des modules Spyder de la V0.4.6 est gardée.

Test fonctionnel ciblé :
  python tests/test_recherche_xslt_joiner_sans_qt.py
Voir TEST_REPORT_V0_4_7.txt pour les tests et leurs limites.

MISE À JOUR V0.4.9 — SÉLECTION CONSERVÉE ENTRE XML ET XSLT
-----------------------------------------------------------
Lorsqu'un utilisateur sélectionne une chaîne dans l'onglet XML source puis
passe à la vue XSLT, l'éditeur tente désormais de sélectionner le même passage
visible dans l'aperçu. Le transfert fonctionne aussi dans l'autre sens.

Le transfert privilégie l'occurrence la plus proche de la ligne du témoin de
base actuellement active, afin d'éviter de sauter vers une occurrence identique
située ailleurs dans le sermon ou le document.

Cas particulier : si une sélection de la vue XSLT traverse un <lb break="no"/>,
le texte y est continu (par ex. « simplex »), tandis que la source XML contient
une balise au milieu. Dans la source, la sélection correspondante englobe alors
la plage continue « sim ... <lb break="no"/> ... plex », balise comprise. C'est
le seul équivalent possible avec une sélection QTextCursor continue.

Si aucune correspondance fiable n'est trouvée, l'ancien comportement est
conservé : l'éditeur synchronise et centre le passage sans créer de sélection
artificielle.

Test textuel hors Qt :
  python tests/test_selection_onglets_sans_qt.py
Documentation développeur (V0.8.4.2)
------------------------------------
Pour une reprise complète du projet par un développeur, lire en priorité
`DEVELOPER_HANDOFF.md`, puis `CODE_MAP.md`. Ces documents décrivent la
philosophie de sûreté éditoriale, les contrats de données, la carte des modules,
les invariants de compatibilité, la matrice de tests et les zones de dette
technique. Les documents spécialisés (`PROJECT_MANAGEMENT.md`,
`FACSIMILE_PAGES.md`, `ALTO_IMPORT.md`, `SYNCHRONIZATION.md`, etc.) complètent
ce dossier de transmission.

Depuis la V0.8.4.2, l'interface installée fournit les catalogues français,
anglais, allemand, japonais, tchèque, italien et russe. Les noms des standards
TEI, ALTO, IIIF, XPath, RELAX NG, Schematron, XSLT et CSS sont conservés tels
quels dans les traductions.


## Extension Varians 0.8.5 — PAGE XML et copies IIIF

Voir **PAGE_IIIF_LOCAL.md** pour les procédures, les formats ALTO/PAGE mixtes, les copies locales IIIF, les deux cases indépendantes par témoin (éditeur / export), les chemins, le protocole de cache et les limites. Les anciens projets restent lisibles sans migration.


VARIANS 0.8.5.9 — CORRECTION DU CADRAGE AUX CHANGEMENTS DE COLONNE

Une ligne correctement synchronisée pouvait apparaître sur une image trop large,
car la fenêtre de contexte comprenait la dernière ligne de la colonne précédente
et la première de la colonne suivante. Le recadrage de l'image ignore désormais
les lignes voisines séparées par un changement de colonne ou de page ; la
synchronisation et les données TEI ne sont pas modifiées. Version établie
uniquement sur les sources complètes de Varians 0.8.5.8.


V0.8.5.10 — CADRES DES LIGNES
- Restaure l'encadrement du témoin secondaire lorsque plusieurs correspondances
  non contiguës auraient placé le centre sur une ligne non synchronisée.
- Cadres orange = synchronisés, bleus = ligne consultée manuellement.
- État activé plus visible, diagnostic si la ligne ne possède pas de géométrie.
- Fenêtre PySide6 : PAGE polygonal / ALTO rectangulaire (ou polygonal si fourni).
- Viewer web : surlignage rectangulaire à ce stade.


V0.8.5.11 — NAVIGATION MIXTE PAR TÉMOIN
- Un témoin avec images seules suit ses pb/edRef/facs (ou n exact et unique),
  pendant que le pivot et les témoins synchronisés suivent les lb/base_keys.
- Même logique pour le texte source, la vue mise en forme et le viewer web.
- Voir MIXED_NAVIGATION.md pour les invariants et les essais.


VARIANS V0.8.5.12 — PANNEAUX DÉFILABLES ET MANUSCRIT PIVOT
============================================================
* Une colonne d'images de quatre manuscrits (ou plus) défile verticalement,
  sans écraser les panneaux du bas. Les poignées, boutons de maximisation et
  tailles mémorisées restent utilisables.
* Deux manuscrits peuvent porter le même @n (par exemple 3r) : la navigation
  suit les repères TEI @edRef + @n, puis la surface, témoin par témoin.
  @facs reste prioritaire ; pas d'association spéculative.
* « Manuscrit pivot » désigne le référent technique de synchronisation,
  jamais une décision concernant le manuscrit de base de l'édition critique.
  Les sept traductions et aides sont à jour, sans rupture du format project.xml.
* Tests : tests/test_v08512_scroll_pivot_name.py et suite historique.
* Pour une vérification visuelle, utiliser l'application sous PySide6/Windows,
  macOS ou Linux avec quatre témoins visibles.


Varians V0.8.5.18 — Navigation par folios et images doubles
Voir FOLIO_NAVIGATION.md. Une surface peut contenir deux zones de folio ; aucun changement des JSON/ALTO ou des images source.

V0.8.5.22 : repliage structurel XML non destructif (menu Affichage, chevrons en marge). Voir XML_FOLDING.md.
