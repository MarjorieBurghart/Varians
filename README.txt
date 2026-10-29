VARIANS V0.9.3.3 — ÉDITEUR XML TEI POUR L'ECDOTIQUE

Varians est un éditeur XML pour l'édition critique de textes transmis par des
manuscrits, encodés en TEI. Il réunit dans une même fenêtre la transcription,
les images des témoins et une vue de lecture, et publie l'édition sans autre
outil :
• éditer la TEI : complétion d'après le schéma, aide au balisage, recherche
  (expressions régulières, XPath), références entre documents ;
• valider : RELAX NG et règles Schematron, pendant la frappe ;
• lire et corriger l'édition mise en forme (Vue XSLT / CSS) ;
• voir les manuscrits (images locales ou IIIF, lignes ALTO ou PAGE XML),
  synchronisés avec la transcription, page par page ou ligne par ligne ;
• contrôler l'apparat critique ;
• publier : viewer web autonome, édition critique HTML, DOCX, ODT, EPUB…
  (TEI Stylesheets fournies), et toute feuille XSLT.

L'interface est en français, anglais, allemand, japonais, tchèque, italien et
russe. Responsable du projet : Marjorie Burghart.


INSTALLATION
------------
Varians demande Python 3 (version testée : 3.12) et trois bibliothèques :
PySide6, lxml et Saxon (paquet saxonche).

  Sous Windows : exécutez une fois installer_dependances.bat
  Ailleurs :     pip install -r requirements.txt


LANCEMENT
---------
  Sous Windows : lancer_editeur.bat
  Ailleurs :     python editeur_tei.py

Pour ouvrir directement un projet :
  python editeur_tei.py chemin/vers/project.xml

Le viewer web d'un projet peut aussi être produit sans ouvrir Varians :
déposez son project.xml sur generer_viewer_web.bat, ou
  python -m web_viewer.generator chemin/vers/project.xml


DOCUMENTATION
-------------
• Le mode d'emploi est dans Varians : Aide → Aide du logiciel (F1), dans la
  langue de l'interface. Il commence par une présentation et un démarrage
  rapide.
• Formats et fonctionnement : PROJECT_MANAGEMENT.md (projets et
  project.xml), ALIGNMENT_FORMAT.md (fichiers d'alignement),
  CUSTOM_ELEMENTS.md (custom-elements.xml), XSLT_SCENARIOS.md,
  I18N_FORMAT.md (traductions), CODE_MAP.md (carte du code).
• Pour reprendre le développement : DEVELOPER_HANDOFF.md, qui contient aussi
  l'historique des versions.


TESTS
-----
  pip install -r requirements-dev.txt
  python -m pytest -q
