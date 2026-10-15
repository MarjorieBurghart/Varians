# Navigation en image double — V0.8.5.20

## Interface

Le bouton **Double page…** est ajouté à la barre d'outils EXISTANTE du témoin.
La rangée supplémentaire « Folios : » est supprimée pour éviter de réduire
l'espace d'affichage de l'image. Les flèches du panneau continuent de
parcourir les parties en mode page.

La boîte de dialogue présente une vignette de l'image complète, indépendamment
du cadrage synchronisé de la ligne courante. Les copies locales sont lues à
résolution réduite avec QImageReader, sans charger un énorme QPixmap ; les
images IIIF sont demandées en miniature (largeur 800 px) de manière asynchrone.
Le chargement distant passe par un QObject récepteur, garantissant que le QPixmap et le QWidget sont manipulés sur le fil d’exécution de l’interface. Si la vignette est indisponible, un texte indique le problème et le pourcentage
peut encore être renseigné manuellement.

Le déplacement de la barre rouge et la saisie du pourcentage sont reliés.
L'abscisse de séparation en pixels source est conservée dans les <zone>, ce
qui évite une seconde opération d'arrondi sur le pourcentage.

Terminologie : « partie gauche / partie droite » ; leur libellé peut être une
référence de folio, de page, etc. Les zones restent dans la <surface> unique
sans duplication de <graphic> et aucune liaison base_keys n'est modifiée. Les deux zones déjà créées automatiquement peuvent être rouvertes et leur séparation ajustée ; les identifiants et les pointeurs <pb> sont conservés. Un renommage de zone déjà référencée par un <pb> est refusé pour éviter une incohérence du @n.

## Marquer la page

Si la surface du témoin comporte précisément deux zones distinctes :

* Dans le mode **lignes synchronisées**, l'abscisse des lignes est obtenue de
  leur bbox (ou bbox dérivée des polygones), convertie de la taille ALTO vers
  la taille complète de l'image. Une ligne unique de référence est prise :
  la ligne courante du témoin, jamais celles des voisins affichés.
  Une zone est retenue si elle couvre au moins 85 % de cette ligne, tandis
  que l'autre n'en couvre pas plus de 15 %. Sinon, demander explicitement
  à l'utilisateur quelle partie marquer.
* En **mode page**, la partie explicitement sélectionnée est utilisée ; à
  défaut, l'utilisateur choisit entre les deux parties.
* Le <pb edRef="#L" n="..." facs="#L-p0008-left"/> inséré pointe vers
  **la zone**, jamais vers la surface entière lorsque deux parties existent.
  Vérifier que la zone existe toujours dans la TEI avant toute modification.
* Un document temporairement invalide ou un curseur dans une balise restent
  protégés par les garde-fous historiques. Le bouton n'écrase aucun <pb>.

## Compatibilité

Le contrat de `split_surface_into_folios` accepte un paramètre optionnel
`split_pixel=` ; les anciens appels à `split_percent=` sont préservés.
Les projets ne contenant pas de zones se comportent comme avant.
Le visualiseur web continue d'interpréter les deux zones de folios.

## Limites et validation

Les tests unitaires/AST sont exécutés en CI Python ; PySide6 n'est pas installé
dans le conteneur de test. Vérifier sur Windows : bouton sur la même rangée,
chargement local/IIIF de la vignette, déplacement du séparateur, création de
zones, « Marquer la page » sur une ligne droite/gauche, et cas ambigu.
