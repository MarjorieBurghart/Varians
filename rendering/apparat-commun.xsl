<?xml version="1.0" encoding="UTF-8"?>
<!--
  Règles communes de l'apparat critique (Varians 0.9.2.7), incluses par
  edition-critique.xsl (édition HTML) et apparat-en-notes.xsl (pré-passage
  des scénarios DOCX et ODT), d'après la feuille du kit « Édition critique ».

  - Leçon retenue : le <lem>, s'il existe (un <lem/> vide est une omission
    établie), sinon la leçon du témoin choisi par le paramètre
    temoin-de-base (« A » ou « #A ») ; sans valeur, le premier <witness> de
    <listWit>. La valeur « aucun » suit les seuls <lem>, et demande un <lem>
    dans chaque <app>.
  - Leçons d'un <app> : ses <lem> et <rdg>, y compris ceux d'un <rdgGrp>.
  - Si le texte établi omet le passage, les autres leçons sont des additions
    (« add. ») ; une leçon vide est une omission (« om. ») ; une leçon qui
    ne contient qu'un début ou une fin de lacune (<lacunaStart/>,
    <lacunaEnd/>) donne « lacuna incipit » ou « lacuna desinit ».
  - Folios : seuls les <pb> du témoin choisi, ou sans @edRef ; avec
    « aucun », tous.
  - Sauts de ligne : des <lb> contigus (de plusieurs témoins) sont une
    seule coupure, qui soude un mot si l'un d'eux porte break="no".
  - Sigles (Varians 0.9.2.8.2) : celui du <idno type="siglum"> du témoin
    dans <listWit>, sinon son identifiant.

  Les deux feuilles mettent en forme ce que donne f:apparat (une map) :
  retenue (la leçon retenue, ou rien), lemme (montrer « leçon ] »),
  variantes (un tableau de maps : lecon, genre om|lacune|add|lecon, sigles).

  Textes (Varians 0.9.3.1) : f:libelle lit la clé dans le catalogue i18n de
  Varians de la langue demandée (paramètres langue et catalogues, que
  Varians passe : la langue de l'interface, sauf si le scénario en fixe
  une) ; sans catalogue, ou sans la clé, le français ci-dessous
  (f:textes-fr, identique au catalogue français). Les abréviations de
  l'apparat (om., add., lacuna incipit, lacuna desinit, sic) sont latines.
-->
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  xmlns:f="urn:varians:apparat"
  xmlns:map="http://www.w3.org/2005/xpath-functions/map"
  exclude-result-prefixes="#all">

  <xsl:param name="temoin-de-base" as="xs:string" select="''"/>
  <!-- Langue des textes (fr, en, de…) et adresse des catalogues i18n
       (« file:…/i18n/ »). -->
  <xsl:param name="langue" as="xs:string" select="'fr'"/>
  <xsl:param name="catalogues" as="xs:string" select="''"/>

  <xsl:variable name="f:catalogue" as="element()*"
    select="let $uri := $catalogues || $langue || '.xml'
            return if ($catalogues != '' and doc-available($uri)) then doc($uri)/translations/string else ()"/>
  <!-- La langue des textes produits : le français sans catalogue. -->
  <xsl:variable name="f:langue" as="xs:string" select="if (exists($f:catalogue)) then $langue else 'fr'"/>
  <xsl:variable name="f:textes-fr" as="element()*">
    <string key="publication.critique.title">Édition critique</string>
    <string key="publication.critique.lemmas_only">Texte établi à partir des lemmes explicites, sans témoin choisi.</string>
    <string key="publication.critique.witness">Leçon explicite prioritaire, sinon lecture du témoin {witness}.</string>
    <string key="publication.critique.undefined">non défini</string>
    <string key="publication.critique.rejected">Les variantes rejetées figurent dans l’apparat.</string>
    <string key="publication.critique.highlight">Surligner les leçons hors &lt;lem&gt;</string>
    <string key="publication.critique.sigla">Sigles des témoins</string>
    <string key="publication.critique.footer">Édition produite à partir d’un document TEI · Apparat par division</string>
    <string key="publication.critique.apparatus">Apparat critique</string>
    <string key="publication.critique.notes">Notes</string>
    <string key="publication.critique.apparatus_notes">Apparat critique et notes</string>
    <string key="publication.critique.call_apparatus">Apparat {n}</string>
    <string key="publication.critique.call_note">Note {n}</string>
    <string key="publication.critique.back">Retour au texte</string>
    <string key="publication.reference">[référence]</string>
    <string key="publication.caesura">Césure</string>
    <string key="publication.unclear">Lecture incertaine</string>
    <string key="publication.sic">Leçon transmise (sic)</string>
    <string key="publication.folio">Changement de folio ou de page</string>
    <string key="publication.gap">[lacune]</string>
    <string key="publication.gap.extent">[lacune : {extent}]</string>
    <string key="publication.not_available">[lecture du témoin non disponible]</string>
    <string key="publication.error.no_lemma">temoin-de-base=aucun : {count} apparat(s) sans lemme (lem). Ajoutez un lemme à chacun, ou choisissez un témoin.</string>
    <string key="publication.error.unknown_witness">Témoin inconnu : {witness} (témoins déclarés : {witnesses}).</string>
  </xsl:variable>

  <!-- Le texte d'une clé, dans la langue demandée, sinon en français. -->
  <xsl:function name="f:libelle" as="xs:string">
    <xsl:param name="cle" as="xs:string"/>
    <xsl:sequence select="string(($f:catalogue[@key = $cle], $f:textes-fr[@key = $cle])[1])"/>
  </xsl:function>
  <!-- Le même, ses variables ({n}, {witness}…) remplacées. -->
  <xsl:function name="f:libelle" as="xs:string">
    <xsl:param name="cle" as="xs:string"/>
    <xsl:param name="valeurs" as="map(xs:string, xs:anyAtomicType)"/>
    <xsl:sequence select="fold-left(map:keys($valeurs), f:libelle($cle),
      function($texte, $nom) { replace($texte, '{' || $nom || '}', string($valeurs($nom)), 'q') })"/>
  </xsl:function>

  <xsl:variable name="f:temoins" as="xs:string*"
    select="(/tei:TEI/tei:teiHeader//tei:listWit//tei:witness/@xml:id) ! string()"/>
  <xsl:variable name="f:sans-temoin" as="xs:boolean"
    select="lower-case(normalize-space($temoin-de-base)) = 'aucun'"/>
  <xsl:variable name="f:temoin" as="xs:string"
    select="if ($f:sans-temoin) then ''
            else if (normalize-space($temoin-de-base) = '') then string($f:temoins[1])
            else replace(normalize-space($temoin-de-base), '^#', '')"/>

  <!-- Mots de l'apparat. -->
  <xsl:variable name="f:om" select="'om.'"/>
  <xsl:variable name="f:add" select="'add.'"/>
  <xsl:variable name="f:lacuna-incipit" select="'lacuna incipit'"/>
  <xsl:variable name="f:lacuna-desinit" select="'lacuna desinit'"/>
  <xsl:variable name="f:non-disponible" select="f:libelle('publication.not_available')"/>

  <!-- Arrêt si le témoin choisi n'est pas déclaré, ou si « aucun » laisse
       un apparat sans lemme. -->
  <xsl:template name="f:verifier">
    <xsl:if test="$f:sans-temoin and exists(/tei:TEI/tei:text//tei:app[not(tei:lem or tei:rdgGrp//tei:lem)])">
      <xsl:message terminate="yes"><xsl:value-of select="f:libelle('publication.error.no_lemma',
        map {'count': count(/tei:TEI/tei:text//tei:app[not(tei:lem or tei:rdgGrp//tei:lem)])})"/></xsl:message>
    </xsl:if>
    <xsl:if test="not($f:sans-temoin) and exists($f:temoins) and not($f:temoin = $f:temoins)">
      <xsl:message terminate="yes"><xsl:value-of select="f:libelle('publication.error.unknown_witness',
        map {'witness': $f:temoin, 'witnesses': string-join($f:temoins, ', ')})"/></xsl:message>
    </xsl:if>
  </xsl:template>

  <!-- Le sigle d'un témoin : son <idno type="siglum"> dans <listWit>, sinon
       son identifiant (« _1760 » pour le sigle « 1760 »). -->
  <xsl:variable name="f:racine" select="/"/>
  <xsl:function name="f:sigle" as="xs:string">
    <xsl:param name="id" as="xs:string"/>
    <xsl:sequence select="string(($f:racine/tei:TEI/tei:teiHeader//tei:listWit//tei:witness[@xml:id = $id]
                                   /tei:idno[@type = 'siglum'][normalize-space()], $id)[1]) => normalize-space()"/>
  </xsl:function>

  <!-- Les témoins d'une leçon : son @wit, sinon celui de son <rdgGrp>. -->
  <xsl:function name="f:wit" as="xs:string*">
    <xsl:param name="lecon" as="element()?"/>
    <xsl:sequence select="tokenize(normalize-space(string(($lecon/@wit, $lecon/ancestor::tei:rdgGrp[@wit][1]/@wit)[1])), '\s+')
                          ! replace(., '^.*#', '')"/>
  </xsl:function>

  <!-- Comparaison par jetons : « #A #B » contient A, « #AA » non. -->
  <xsl:function name="f:porte-temoin" as="xs:boolean">
    <xsl:param name="lecon" as="element()?"/>
    <xsl:param name="sigle" as="xs:string"/>
    <xsl:sequence select="exists($lecon) and replace(normalize-space($sigle), '^.*#', '') = f:wit($lecon)"/>
  </xsl:function>

  <!-- Les leçons de l'apparat : ses <lem> et <rdg>, ceux d'un <rdgGrp>
       compris, mais pas ceux d'un apparat imbriqué. -->
  <xsl:function name="f:lecons" as="element()*">
    <xsl:param name="a" as="element(tei:app)"/>
    <xsl:sequence select="$a//(tei:lem | tei:rdg)[ancestor::tei:app[1] is $a]"/>
  </xsl:function>

  <!-- La leçon retenue : le lemme, sinon la première leçon du témoin choisi. -->
  <xsl:function name="f:choix" as="element()?">
    <xsl:param name="a" as="element(tei:app)"/>
    <xsl:variable name="lecons" select="f:lecons($a)"/>
    <xsl:sequence select="if (exists($lecons[self::tei:lem])) then $lecons[self::tei:lem][1]
                          else if ($f:sans-temoin) then ()
                          else $lecons[f:porte-temoin(., $f:temoin)][1]"/>
  </xsl:function>

  <!-- Le nœud est-il dans le texte établi (dans la leçon retenue de chaque
       apparat qui l'englobe) ? -->
  <xsl:function name="f:dans-texte-etabli" as="xs:boolean">
    <xsl:param name="n" as="node()"/>
    <xsl:sequence select="every $r in $n/ancestor-or-self::*[self::tei:lem or self::tei:rdg][ancestor::tei:app]
                          satisfies ($r is f:choix($r/ancestor::tei:app[1]))"/>
  </xsl:function>

  <xsl:function name="f:sigles" as="xs:string">
    <xsl:param name="lecon" as="element()?"/>
    <xsl:variable name="sigles" select="f:wit($lecon)"/>
    <xsl:sequence select="if (empty($sigles)) then 'éd.' else string-join($sigles ! f:sigle(.), ' ')"/>
  </xsl:function>

  <!-- Le texte d'une leçon, hors des notes qu'elle contient (elle peut
       elle-même être dans une note). -->
  <xsl:function name="f:texte" as="xs:string">
    <xsl:param name="lecon" as="element()?"/>
    <xsl:variable name="notes" select="$lecon/descendant::tei:note"/>
    <xsl:sequence select="normalize-space(string-join($lecon/descendant::text()[empty(ancestor::tei:note intersect $notes)], ''))"/>
  </xsl:function>

  <!-- Une omission : ni texte, ni lacune, ni rien qui ait valeur de leçon. -->
  <xsl:function name="f:omission" as="xs:boolean">
    <xsl:param name="lecon" as="element()?"/>
    <xsl:sequence select="exists($lecon) and f:texte($lecon) = ''
      and empty($lecon/descendant::*[self::tei:gap or self::tei:space or self::tei:app or self::tei:graphic
                                     or self::tei:lacunaStart or self::tei:lacunaEnd])"/>
  </xsl:function>

  <!-- Une leçon qui n'est qu'un début ou une fin de lacune. -->
  <xsl:function name="f:lacune" as="xs:boolean">
    <xsl:param name="lecon" as="element()?"/>
    <xsl:sequence select="exists($lecon/descendant::*[self::tei:lacunaStart or self::tei:lacunaEnd])
                          and f:texte($lecon) = ''"/>
  </xsl:function>

  <!-- Les témoins d'une balise de lacune, s'ils diffèrent de ceux de sa
       leçon (att.rdgPart) : à nommer après « lacuna incipit ». -->
  <xsl:function name="f:sigles-lacune" as="xs:string">
    <xsl:param name="balise" as="element()"/>
    <xsl:variable name="propres" select="tokenize(normalize-space(string($balise/@wit)), '\s+') ! replace(., '^.*#', '')"/>
    <xsl:variable name="lecon" select="$balise/ancestor::*[self::tei:lem or self::tei:rdg][1]"/>
    <xsl:sequence select="if (empty($propres) or (exists($lecon) and deep-equal(sort($propres), sort(f:wit($lecon)))))
                          then '' else string-join($propres ! f:sigle(.), ' ')"/>
  </xsl:function>

  <xsl:function name="f:apparat" as="map(*)">
    <xsl:param name="a" as="element(tei:app)"/>
    <xsl:variable name="retenue" select="f:choix($a)"/>
    <xsl:variable name="ajouts" select="exists($retenue) and f:omission($retenue)"/>
    <xsl:sequence select="map {
      'retenue': $retenue,
      'lemme': not($ajouts),
      'variantes': array { f:lecons($a)[not(. is $retenue)] ! map {
          'lecon': .,
          'genre': if (f:omission(.)) then 'om' else if (f:lacune(.)) then 'lacune'
                   else if ($ajouts) then 'add' else 'lecon',
          'sigles': f:sigles(.) } } }"/>
  </xsl:function>

  <!-- Un <pb> à montrer : du témoin choisi, ou sans @edRef ; tous avec « aucun ». -->
  <xsl:function name="f:folio-montre" as="xs:boolean">
    <xsl:param name="pb" as="element()"/>
    <xsl:sequence select="$f:sans-temoin or normalize-space($pb/@edRef) = ''
      or $f:temoin = (tokenize(normalize-space($pb/@edRef), '\s+') ! replace(., '^.*#', ''))"/>
  </xsl:function>

  <xsl:function name="f:folio" as="xs:string">
    <xsl:param name="pb" as="element()"/>
    <xsl:sequence select="concat('⟨', if ($f:sans-temoin and normalize-space($pb/@edRef) != '')
      then concat(replace(normalize-space($pb/@edRef), '(^|\s)#', '$1'), ' : ') else '', $pb/@n, '⟩')"/>
  </xsl:function>

  <!-- Sauts de ligne. Les <lb> contigus de plusieurs témoins (« fu <lb
       edRef="#A" break="no"/><lb edRef="#B"/>it ») sont une seule coupure :
       un mot coupé si l'un d'eux porte break="no", sinon une espace. -->
  <xsl:function name="f:lb-avant" as="element()*">
    <xsl:param name="n" as="node()"/>
    <xsl:variable name="debut" select="$n/preceding-sibling::node()[not(self::tei:lb)][1]"/>
    <xsl:sequence select="$n/preceding-sibling::tei:lb[empty($debut) or . &gt;&gt; $debut]"/>
  </xsl:function>
  <xsl:function name="f:lb-apres" as="element()*">
    <xsl:param name="n" as="node()"/>
    <xsl:variable name="fin" select="$n/following-sibling::node()[not(self::tei:lb)][1]"/>
    <xsl:sequence select="$n/following-sibling::tei:lb[empty($fin) or . &lt;&lt; $fin]"/>
  </xsl:function>
  <xsl:function name="f:lb-groupe" as="element()*">
    <xsl:param name="lb" as="element()"/>
    <xsl:sequence select="f:lb-avant($lb) | $lb | f:lb-apres($lb)"/>
  </xsl:function>
  <!-- Le <lb> qui donne l'espace de sa coupure : le premier du groupe, si
       aucun ne porte break="no". -->
  <xsl:function name="f:lb-espace" as="xs:boolean">
    <xsl:param name="lb" as="element()"/>
    <xsl:variable name="groupe" select="f:lb-groupe($lb)"/>
    <xsl:sequence select="not($groupe/@break = 'no') and $lb is $groupe[1]"/>
  </xsl:function>

  <!-- Espaces : les retours de ligne deviennent des espaces ; une coupure
       break="no" soude les segments d'un mot. -->
  <xsl:function name="f:texte-net" as="xs:string">
    <xsl:param name="t" as="text()"/>
    <xsl:variable name="s" select="if ($t/ancestor::*[@xml:space][1]/@xml:space = 'preserve')
      then string($t) else replace(string($t), '\s+', ' ')"/>
    <!-- Le premier et le dernier texte d'une didascalie touchent ses parenthèses (V0.9.3.1). -->
    <xsl:variable name="didascalie" select="$t/ancestor::tei:stage[1]//text()"/>
    <xsl:variable name="a" select="if (f:lb-avant($t)/@break = 'no' or $t is $didascalie[1])
      then replace($s, '^\s+', '') else $s"/>
    <xsl:sequence select="if (f:lb-apres($t)/@break = 'no' or $t is $didascalie[last()])
      then replace($a, '\s+$', '') else $a"/>
  </xsl:function>

</xsl:stylesheet>
