# Varians V0.8.5.23 — Surbrillance bidirectionnelle des paires XML

## Périmètre

Dans l’éditeur XML source, les deux balises sont marquées par `ExtraSelection` en bleu pâle lorsqu’une paire non ambiguë est sous le curseur (ou dans la sélection intégralement contenue dans un des tags). L’ouverture et la fermeture sont détectées symétriquement. Ce mécanisme ne modifie pas la TEI, ne sélectionne pas réellement le texte et ne modifie pas les opérations Ctrl+Z.

## Algorithme et précautions

- Ouverture : réutilisation de `opening_pair_at_context` et de `matching_closing_tag`, qui parcourent une pile d’éléments imbriqués. Les fermetures croisées à l’intérieur de la paire annulent la recherche.
- Fermeture : `closing_pair_at_context` ne parcourt que le préfixe du document et exige une pile cohérente pour retrouver le nom qualifié ouvrant. Fermetures orphelines ou croisées : aucun résultat.
- Un élément vide (`<lb/>`) n’a pas de paire. Les commentaires, CDATA et instructions de traitement sont exclus par le lexer partagé.
- Une paire valide avant une portion XML encore en cours de rédaction reste surlignable.
- Pas de modification des fonctions de renommage, suppression de paire ou repliage existantes.

## Validation et limites

Tests : paires inverses ; noms identiques imbriqués ; noms qualifiés avec préfixe ; XML croisé et fermetures orphelines ; sélections/bornes ; éléments vides ; lexique spécial ; intégration non destructive dans l’éditeur.

Le moteur reste un outil lexical prudent, pas un validateur XML complet. Le contrôle structurel RELAX NG et le parseur XML restent indépendants. PySide6 non disponible sur l’hôte de validation : interaction graphique à confirmer sous Windows/macOS/Linux.
