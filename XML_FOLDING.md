# Varians 0.8.5.22 — Repliage structurel XML

## Contrat

Le repliage ne modifie jamais `QTextDocument` comme texte : aucun marqueur
placeholder n’est écrit en TEI. `xml_folding.py` ne dépend pas de Qt et produit
les plages `FoldRegion` à partir de `scan_xml_tags` de `xml_tag_pairs.py`.
Il n’apparie pas des balises mal imbriquées et refuse les lignes partagées
avec des caractères significatifs.

L’éditeur `CodeEditor` cache uniquement des blocs `QTextBlock` complets
par `setVisible(False)` et `setLineCount(0)`. Les blocs sont rendus visibles
par `setVisible(True)` ; un appel à `markContentsDirty` force le recalcul de
la mise en page sans changer le texte. Les triangles ▾ / ▸ sont peints dans
`LineNumberArea` ; leur activation est indépendante des données TEI.

## Commandes

- Affichage → Repliage XML → Replier/déplier l’élément (`Ctrl+Alt+F`).
- Replier les éléments structurels (premiers niveaux éditoriaux : on ne replie
  pas d’un bloc les enveloppes `TEI`, `text`, `body` etc.).
- Tout déplier (`Ctrl+Alt+Maj+F`).
- Clic sur chevron en marge pour une balise ouvrante admissible.

## Sécurité et limites

- Le repliage est limité aux éléments sur plusieurs lignes dont les balises
  ouvrante et fermante ont leur propre ligne ; on ne peut cacher qu’un bloc
  QTextBlock entier sans risquer de masquer des frères/du texte situé à côté.
- Une modification quelconque du XML déplie tout, afin d’éviter des caches
  de positions invalides lors d’un collage, Ctrl+Z ou formatage automatique.
- Une navigation XPath, une recherche, un lien TEI ou une synchronisation
  conduisant dans une ligne cachée entraîne le dépliage de toutes les zones.
- Le XML reste intégralement présent dans `toPlainText()` ; Ctrl+Z, la
  sauvegarde, les positions de curseur et le modèle TEI sont inchangés.
- L’état de pliage est une préférence volatile du poste de travail, non
  sérialisée dans les fichiers de projet ni dans les éditions.
- Les éléments sur une seule ligne ne peuvent pas être réduits par cette
  technique ; une implémentation de repliage inline pourrait être étudiée
  sans réécrire le XML.
- PySide6 absent de l’environnement d’intégration : les essais GUI natifs
  sous Windows/Linux/macOS restent à exécuter.
