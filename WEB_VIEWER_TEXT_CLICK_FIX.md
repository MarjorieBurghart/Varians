# Varians V0.8.5.25.2 — clic texte ↔ images manuscrites du viewer web

## Diagnostic fondé sur le code

- L'affichage en mode lignes est restauré par V0.8.5.25.1 et n'a pas été refondu ici.
- La navigation de V0.8.5.25.1 est conditionnée par l'existence de `data-line` et par la présence de cette clé dans `lineMap`. Les échecs étaient silencieux.
- Par régression avec le viewer historique `legacy_v11_core.py`, le clic sur les marqueurs de note et de variante n'utilisait plus leur clé de ligne avant l'ouverture de la notice. Les références éditoriales possédaient une clé source, mais leur HTML exporté ne la publiait plus.
- Des lignes de contexte voisines peuvent produire le même rectangle de crop ; dans l'ancien CSS, même la ligne courante n'était plus mise en évidence lorsque le mode « Cadres » était désactivé.
- Les fichiers TEI/JSON/images particuliers de l'utilisateur ne sont **pas** contenus dans la livraison : cela ne prouve pas que ces régressions expliquent à elles seules son symptôme précis.

## Corrections

1. Une interaction sur n'importe quel élément de lecture muni d'un `data-line` valide prend désormais la voie `selectLine`, avant la notice ou les opérations de page.
2. Les marqueurs de notes, de variantes et les références éditoriales transportent le `line_key` de leur segment dans le HTML.
3. `selectLine` vérifie l'existence exacte dans `lineMap`, sans fallback approximatif ; si absente, message traduit avec la clé manquante. Les portions de texte sans ancre affichent un diagnostic distinct.
4. La ligne sélectionnée reçoit un contour bleu visible même si le cadre orange des voisins est masqué. Le rendu conserve les polygones PAGE et la fenêtre physique de recadrage hérités de V0.8.5.24.
5. Après un clic textuel, le témoin synchronisé est recentré sur le centre géométrique de la ligne dans la région courante, y compris à zoom supérieur à 100 %, sans changer le zoom choisi.
6. Le jeu exporté publie `meta.unresolvable_text_line_keys` et `meta.unanchored_text_segments` pour aider un diagnostic ultérieur.

## Invariants scientifiques et techniques

Une ligne dépourvue de correspondance explicite ne déclenche jamais de liaison inférée. La version maintient les conditions de synchronisation de `resource_state.py`, les `base_keys` réels, la dissociation OCR/images, les surfaces et zones TEI, les coordonnées source, les réponses IIIF v1/v2/v3 et les replis de réseau. Aucune TEI ou JSON d'édition n'est réécrit par l'export.

## Vérification de l'utilisateur

Regénérer `web_output/viewer.html` depuis Varians 0.8.5.25.2. Cliquer d'abord un mot proche du début de la transcription, puis un autre plus loin ; contrôler le numéro de ligne sur les cartes du pivot et de chaque témoin secondaire et le contour bleu actif. Tester une note, une variante, un marqueur de page et le zoom. Si le diagnostic indique une clé inconnue, relever cette clé et les compteurs embarqués du viewer, puis communiquer un fragment TEI/JSON ne comportant pas de contenu sensible.
