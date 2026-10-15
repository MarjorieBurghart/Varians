# 10 — Provenance, méthodes de contrôle et portée des preuves

## 1. Référence primaire

Nom de l'archive source : `Varians_V0.8.5.26.2_Correctif_Validation_RELAX_NG_Complete.zip`.

Cette archive est recopiée **octet pour octet** dans `BASE_SOURCE/`. Les fichiers documentaires supplémentaires de la présente passation ne sont pas des modifications du logiciel ; leur présence ne doit pas être interprétée comme un lancement de nouvelle version.

Valeurs observées indépendamment :

- **268 fichiers** dans l'archive ZIP ; contrôle CRC : aucune erreur ;
- `APP_VERSION = "0.8.5.26.2"` dans `editeur_tei.py` ;
- dépendances déclarées : `PySide6`, `lxml` ;
- `python -m pytest -q --disable-warnings --maxfail=1` : **479 passed, 2 skipped** (exécuté dans l'environnement documentaire, sortie jointe) ;
- `python -m compileall -q ...` : réussite ;
- les sept langues d'interface et les sept aides HTML sont dans la distribution ;
- le rapport d'origine indiquait **629 entrées de catalogue par langue** et l'absence de modification du viewer web dans la version .2.

Le manifeste SHA-256 et le rapport d'inventaire machine produits pendant cette passation rendent ces constats reproductibles. Un rapport de tests peut varier en temps d'exécution selon le poste.

## 2. Distinction vérification / retour d'usage / hypothèse

| Affirmation | Nature de la preuve | Portée |
|---|---|---|
| Archive V0.8.5.26.2 identifiée | SHA-256, CRC, `APP_VERSION` | Base exacte et non modifiée |
| Suite Python 479/2 | exécution indépendante | Tests présents dans cette distribution, hors couverture GUI native |
| XML validé après corrections | retour utilisateur + tests ciblés | Résolution pratique plausible et retenue, non preuve de tous les cas futurs |
| Recherche `u/v`, `i/j`, `c/t` | tests JS/Chromium synthétiques antérieurs et retour utilisateur | Parcours de recherche et surlignage validés dans scénarios connus |
| Ordre/visibilité du viewer | essais Chromium synthétiques et confirmation utilisateur | Fonction du viewer retenue |
| Parité `<lb/>` pivot | tests Python, diagnostic HTML réel, confirmation utilisateur | Retour à une cohérence observée ; surveiller nouveaux corpus |
| JSON secondaires sans clé | contrat source | Mode pages volontaire, sans inventer de lignes |
| Validité des images IIIF distantes | dépend du serveur et des droits | Pas de garantie hors ligne ni d'accès permanent |
| Toute l'UI Qt macOS/Linux | non testée physiquement ici | Ne pas l'annoncer validée |

## 3. Protection des données utilisateurs

La distribution ZIP contient des fichiers d'exemple `T1/T2/P`. Les vrais manuscrits Mu/F/A/N/L ne sont pas incorporés comme corpus scientifique à cette passation. Les diagnostics partagés dans les échanges ont donné des nombres de lignes, de clés et des identifiants, mais **ne remplacent pas les vrais fichiers** et n'autorisent pas à reconstruire le projet réel. Ne pas publier de manuscrits, de scans sous droits, ni d'URLs authentifiées dans la documentation sans permission.

## 4. Maintenance documentaire

À chaque version future, compléter un addendum qui indique explicitement : base exacte, fichiers source modifiés, comportement antérieur/nouveau, hypothèses éliminées, tests précis, limites, statut d'essai utilisateur, nouvelle empreinte. Ajouter l'addendum à un handover consolidé si la version devient un nouveau jalon majeur. Ne jamais écraser l'archive originale ni réécrire l'histoire : les notes antérieures restent consultables mais doivent être qualifiées par leur date et version.
