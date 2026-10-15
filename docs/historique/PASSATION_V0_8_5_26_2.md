# VARIANS V0.8.5.26.2 — PASSATION DU CORRECTIF RELAX NG

**Base source :** V0.8.5.26.1 complète, 265 fichiers, ZIP CRC validé. La version 0.8.5.26.2 est un correctif ciblé sans refonte de la roadmap.

## Problème signalé

Des erreurs RELAX NG corrigées depuis longtemps réapparaissaient dans la liste. Le mécanisme V0.8.5.26 conservait une dépendance à la visibilité immédiate du panneau : un changement effectué lorsqu'il était masqué ne déclenchait pas la revalidation différée. L'ancien résultat pouvait alors être montré à nouveau. Cette insuffisance du code est vérifiée ; aucun projet Mu/F/A/N/L réel n'étant inclus dans le paquet, il reste à confirmer qu'elle explique tous les cas constatés par l'utilisateur.

## Modification

1. Connexion aux modifications du widget ET du document Qt, avec déduplication par révision. Les modifications de `QTextCursor`, annuler/refaire et de l'éditeur de fragment invalident aussi les résultats.
2. L'invalidation vide immédiatement le tableau, retire le résultat RNG mis en cache et indique que les anciens diagnostics sont périmés.
3. Après première activation par l'utilisateur du panneau, le timer de 1 250 ms relance la validation sans dépendre de sa visibilité ; lors d'une réouverture, la révision est vérifiée immédiatement et revalidée au besoin.
4. Toute tentative de publier un résultat calculé sur une révision dépassée est rejetée, après la résolution du schéma et après la validation elle-même. Une passe récente est programmée à sa place.
5. Wrapper anti-récursion pour éviter qu'une ouverture du panneau pendant un contrôle ne relance ce contrôle ; le bouton F8 demeure disponible.
6. Traces documentaires actualisées et traduction corrigée du message « résultats périmés » dans les sept langues.

## Invariants

Ne pas toucher au XML, au RNG, au format projet, aux identifiants de lignes, aux `base_keys`, à l'ordre/visibilité des témoins, aux vues IIIF et au viewer web. Ne pas réactiver la roadmap suspendue.

## Validation / limites

Exécuter `python -m pytest -q --disable-warnings` et `python -m compileall -q .`. Les nouveaux tests de cycle (sans Qt natif) vérifient corrections panneau masqué, réouverture, double notification Qt, premier F8, revalidation après calcul obsolète, et réutilisation du validateur lxml sans erreurs résiduelles. **PySide6 n'est pas disponible** dans l'environnement de production : aucun test GUI Windows réel ne doit être annoncé comme effectué.

## Test utilisateur indispensable

Ouvrir un projet réel ; provoquer une erreur RNG dans la source ; F8 pour afficher le panneau ; masquer le panneau ou ouvrir XPath ; corriger l'erreur ; revenir au panneau ; vérifier que la liste est vide (ou ne contient que les problèmes encore présents). Tester ensuite sans masquer, puis avec annuler/refaire et plusieurs erreurs corrigées successivement. Toute réapparition doit être accompagnée du texte exact de l'erreur et de l'action précédente.
