# TEI Stylesheets livrées avec Varians

Les scénarios de transformation prédéfinis « TEI : … » emploient les feuilles
XSLT du TEI Consortium (les « TEI Stylesheets »). Varians en apporte une
version, `tei-xsl-7.61.0.zip`, pour qu'elles marchent dès le premier usage,
sans réseau. Le module `tei_stylesheets` (V0.9.2.2) l'installe dans le dossier
de données de l'utilisateur, hors des projets :

- Windows : `%LOCALAPPDATA%\Varians\tei-stylesheets\7.61.0\` ;
- autres systèmes : `~/.local/share/varians/tei-stylesheets/7.61.0/`
  (ou `$XDG_DATA_HOME/varians/…`).

Une version plus récente publiée par le TEI-C peut ensuite être téléchargée
et installée au même endroit, avec l'accord de l'utilisateur.

## Origine

- Dépôt : [github.com/TEIC/Stylesheets](https://github.com/TEIC/Stylesheets).
- Archive publiée, version 7.61.0 :
  `https://github.com/TEIC/Stylesheets/releases/download/v7.61.0/tei-xsl-7.61.0.zip`
  (empreinte MD5 `fd488fae991ed98082ffad40bef05a7d`).
- `tei-xsl-7.61.0.zip` ne garde, de cette archive, que les feuilles
  (`xml/tei/stylesheet/`, environ 760 fichiers) et la licence
  (`doc/tei-xsl/LICENCE`). Les fichiers gardés sont copiés tels quels, avec
  leurs chemins : l'archive livrée a la structure de l'archive publiée, et
  Varians les installe de la même façon. La documentation du TEI-C (134 Mo)
  n'est pas reprise.

## Licence

Les TEI Stylesheets sont distribuées, au choix, sous la licence
[Creative Commons Attribution-ShareAlike 3.0 Unported](http://creativecommons.org/licenses/by-sa/3.0/)
ou sous la licence [BSD à deux clauses](http://www.opensource.org/licenses/BSD-2-Clause) :
Copyright 2011–2020 TEI Consortium. Le texte de la licence est dans l'archive
(`doc/tei-xsl/LICENCE`) et Varians l'installe avec les feuilles (`LICENCE`) :
il doit les accompagner.

## Refaire l'archive livrée

Pour une nouvelle version du TEI-C (ici `X.Y.Z`) :

1. télécharger `tei-xsl-X.Y.Z.zip` depuis la page des versions du dépôt
   (Releases) ;
2. ne garder que les feuilles et la licence, avec ce script Python :

   ```python
   import sys
   import zipfile

   PREFIX, LICENCE = "xml/tei/stylesheet/", "doc/tei-xsl/LICENCE"
   source, destination = sys.argv[1], sys.argv[2]
   with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as bundle:
       for info in original.infolist():
           name = info.filename
           if (name.startswith(PREFIX) or name == LICENCE
                   or (name.endswith("/") and (PREFIX.startswith(name) or LICENCE.startswith(name)))):
               bundle.writestr(info, original.read(info))
   ```

   `python reduire.py tei-xsl-X.Y.Z.zip resources/tei-stylesheets/tei-xsl-X.Y.Z.zip` ;
3. retirer l'ancienne archive de ce dossier (il n'en contient qu'une) et
   mettre à jour ce LISEZMOI (version, adresse, empreinte) ;
4. lancer les tests (`tests/test_tei_stylesheets.py` contrôle l'archive
   livrée, `tests/test_tei_scenarios_saxon.py` les scénarios TEI).
