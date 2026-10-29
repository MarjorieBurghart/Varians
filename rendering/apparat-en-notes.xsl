<?xml version="1.0" encoding="UTF-8"?>
<!--
  Apparat en notes (Varians 0.9.2.7) : pré-passage TEI → TEI des scénarios
  « TEI : DOCX (Word) » et « TEI : ODT (LibreOffice) », appliqué à l'édition
  avant les TEI Stylesheets. Paramètre : temoin-de-base (voir
  apparat-commun.xsl ; les scénarios donnent le témoin pivot, ${pivot}).

  - Chaque <app> devient sa leçon retenue, suivie d'une note de bas de page
    <note place="foot" type="apparatus"> : « leçon ] variante sigles ; … »,
    avec om., add., lacuna incipit et lacuna desinit, comme dans l'édition
    critique HTML : tout texte de la note qui ne vient pas d'un témoin
    (sigles, om., add., lacunes, commentaires) est en italique ; les
    leçons sont en romain, un <sic> suivi de « sic ».
  - Une note de l'éditeur sans @place devient une note de fin
    (place="end") : une autre série que celle de l'apparat. Dans une
    note, une note devient « (…) » et l'entrée d'un apparat se met entre
    crochets : Word et LibreOffice n'admettent pas une note dans une note.
  - Les <pb> du témoin deviennent des repères de folio ⟨12r⟩ dans le texte
    (<seg type="folio">), les autres disparaissent : pas de saut de page.
  - Les <lb> deviennent des espaces (des <lb> contigus sont une seule
    coupure ; break="no" soude les segments d'un mot) ; les balises de
    lacune hors de l'apparat disparaissent.
  - Une suite d'espaces devient une seule espace, l'appel d'une note suit
    son mot ; l'espace qui sépare deux éléments va dans un <seg>, que Word
    garde.
  - Règle commune (Varians 0.9.3.4), comme « Édition critique », au lieu
    des TEI Stylesheets : la forme retenue d'un <choice> (corr, reg,
    expan…) ; une didascalie entre parenthèses, en italique ; la référence
    d'une citation biblique entre chevrons, celle d'une autre citation en
    note de fin ; une note en marge (ou à une autre place que foot, end,
    inline) en note de fin ; <space/> une espace ; <gap/> « [lacune] » ;
    les folios du témoin choisi dans une leçon non retenue ; la note d'un
    lemme n'est pas répétée dans la note de l'apparat.
  Le reste du document est recopié.
-->
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  xmlns:array="http://www.w3.org/2005/xpath-functions/array"
  xmlns:f="urn:varians:apparat"
  xmlns="http://www.tei-c.org/ns/1.0"
  exclude-result-prefixes="#all">

  <xsl:include href="apparat-commun.xsl"/>
  <xsl:output method="xml" encoding="UTF-8"/>
  <xsl:mode on-no-match="shallow-copy"/>
  <!-- Le contenu d'une note d'apparat : texte et mise en forme simple. -->
  <xsl:mode name="note" on-no-match="shallow-skip"/>

  <!-- Espaces du texte établi, après coup. -->
  <xsl:mode name="espaces" on-no-match="shallow-copy"/>

  <xsl:template match="/">
    <xsl:call-template name="f:verifier"/>
    <xsl:variable name="etabli"><xsl:apply-templates/></xsl:variable>
    <xsl:apply-templates select="$etabli" mode="espaces"/>
  </xsl:template>

  <!-- Le texte établi. -->
  <xsl:template match="tei:text//text()">
    <xsl:value-of select="f:texte-net(.)"/>
  </xsl:template>

  <xsl:template match="tei:text//tei:app">
    <xsl:variable name="apparat" select="f:apparat(.)"/>
    <xsl:variable name="retenue" select="$apparat?retenue"/>
    <!-- Les folios du témoin choisi dans les leçons non retenues : avant
         le texte s'ils précèdent tout texte de leur leçon, sinon après la
         note. -->
    <xsl:variable name="app" select="."/>
    <xsl:variable name="folios" select="f:folios-ecartes(., $retenue)"/>
    <xsl:apply-templates select="$folios[f:folio-en-tete(., $app)]"/>
    <xsl:choose>
      <xsl:when test="exists($retenue)"><xsl:apply-templates select="$retenue/node()"/></xsl:when>
      <xsl:otherwise><xsl:value-of select="$f:non-disponible"/></xsl:otherwise>
    </xsl:choose>
    <xsl:if test="array:size($apparat?variantes) gt 0">
      <xsl:choose>
        <!-- Dans une note (Word et LibreOffice n'admettent pas une note
             dans une note) : l'entrée entre crochets. -->
        <xsl:when test="ancestor::tei:note">
          <xsl:text> [</xsl:text>
          <xsl:call-template name="entree"><xsl:with-param name="apparat" select="$apparat"/></xsl:call-template>
          <xsl:text>]</xsl:text>
        </xsl:when>
        <xsl:otherwise>
          <note place="foot" type="apparatus">
            <xsl:call-template name="entree"><xsl:with-param name="apparat" select="$apparat"/></xsl:call-template>
          </note>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:if>
    <xsl:apply-templates select="$folios[not(f:folio-en-tete(., $app))]"/>
  </xsl:template>

  <!-- « leçon ] variante sigles ; … » -->
  <xsl:template name="entree">
    <xsl:param name="apparat" as="map(*)"/>
    <xsl:variable name="retenue" select="$apparat?retenue"/>
    <xsl:if test="$apparat?lemme">
      <xsl:choose>
        <xsl:when test="exists($retenue)">
          <!-- La note du lemme a son appel dans le texte : pas ici. -->
          <xsl:apply-templates select="$retenue/node()" mode="note"><xsl:with-param name="lemme" tunnel="yes" select="true()"/></xsl:apply-templates>
        </xsl:when>
        <xsl:otherwise><hi rend="italic"><xsl:value-of select="$f:non-disponible"/></hi></xsl:otherwise>
      </xsl:choose>
      <xsl:text> ] </xsl:text>
    </xsl:if>
    <xsl:for-each select="$apparat?variantes?*">
      <xsl:if test="position() gt 1"><xsl:text> ; </xsl:text></xsl:if>
      <xsl:choose>
        <xsl:when test="?genre = 'om'">
          <hi rend="italic"><xsl:value-of select="$f:om"/></hi>
          <xsl:apply-templates select="?lecon//tei:note" mode="note"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:apply-templates select="?lecon/node()" mode="note"/>
          <xsl:if test="?genre = 'add'"><xsl:text> </xsl:text><hi rend="italic"><xsl:value-of select="$f:add"/></hi></xsl:if>
        </xsl:otherwise>
      </xsl:choose>
      <xsl:text> </xsl:text>
      <hi rend="italic"><xsl:value-of select="?sigles"/></hi>
    </xsl:for-each>
  </xsl:template>

  <!-- Une note dans une note : « (…) » dans le texte de la première. -->
  <xsl:template match="tei:text//tei:note[ancestor::tei:note]" priority="2">
    <xsl:text> (</xsl:text><xsl:apply-templates/><xsl:text>)</xsl:text>
  </xsl:template>

  <!-- Une note sans @place, ou en marge (toute place autre que foot, end
       et inline), devient une note de fin : en marge, elle coupait le
       paragraphe (Varians 0.9.3.4). -->
  <xsl:template match="tei:text//tei:note[not(@place = ('foot', 'end', 'inline'))]">
    <note place="end">
      <xsl:apply-templates select="(@* except @place) | node()"/>
    </note>
  </xsl:template>

  <!-- Règle commune (Varians 0.9.3.4) : la forme retenue d'un <choice>. -->
  <xsl:template match="tei:text//tei:choice">
    <xsl:apply-templates select="(tei:corr, tei:reg, tei:expan, tei:sic, tei:orig, tei:abbr, *[1])[1]/node()"/>
  </xsl:template>
  <!-- Une didascalie, entre parenthèses, en italique ; dans un paragraphe
       ou un vers, sans y couper une ligne ; entre deux blocs, un bloc. -->
  <xsl:template match="tei:text//tei:stage">
    <xsl:text>(</xsl:text><hi rend="italic"><xsl:apply-templates/></hi><xsl:text>)</xsl:text>
  </xsl:template>
  <xsl:template match="tei:text//tei:stage[parent::tei:sp or parent::tei:spGrp or parent::tei:lg or parent::tei:body
                       or parent::tei:front or parent::tei:back or parent::tei:*[matches(local-name(), '^div[1-7]?$')]]">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
      <xsl:text>(</xsl:text><hi rend="italic"><xsl:apply-templates/></hi><xsl:text>)</xsl:text>
    </xsl:copy>
  </xsl:template>
  <!-- La référence d'une citation biblique suit la citation, espacée,
       entre chevrons ; celle d'une autre citation est une note de fin. -->
  <xsl:template match="tei:text//tei:cit/tei:ref">
    <xsl:choose>
      <xsl:when test="f:biblique(parent::tei:cit)">
        <xsl:text> &lt;</xsl:text><xsl:copy><xsl:apply-templates select="@* | node()"/></xsl:copy><xsl:text>&gt;</xsl:text>
      </xsl:when>
      <xsl:otherwise>
        <note place="end"><xsl:copy><xsl:apply-templates select="@* | node()"/></xsl:copy></note>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <!-- <space/> : une espace ; <gap/> : « [lacune] », comme dans l'apparat. -->
  <xsl:template match="tei:text//tei:space"><xsl:text> </xsl:text></xsl:template>
  <xsl:template match="tei:text//tei:gap">
    <hi rend="italic"><xsl:value-of select="f:texte-gap(.)"/></hi>
  </xsl:template>

  <xsl:template match="tei:text//tei:pb">
    <xsl:if test="f:folio-montre(.)"><seg type="folio"><xsl:value-of select="f:folio(.)"/></seg></xsl:if>
  </xsl:template>

  <xsl:template match="tei:text//tei:lb">
    <xsl:if test="f:lb-espace(.)"><xsl:text> </xsl:text></xsl:if>
  </xsl:template>
  <xsl:template match="tei:text//tei:lacunaStart | tei:text//tei:lacunaEnd"/>

  <!-- Mode espaces : une suite d'espaces devient une seule espace ; l'appel
       d'une note d'apparat suit son mot (« Egyptii¹ sunt », « mecum¹, ») ;
       un texte ne commence pas par une espace si le précédent en finit
       une ; celle qui sépare deux éléments va dans un <seg>, que Word garde
       (les TEI Stylesheets perdent un texte fait d'espaces entre deux
       éléments). -->
  <xsl:template match="tei:text//text()[not(ancestor::*[@xml:space][1]/@xml:space = 'preserve')]" mode="espaces">
    <xsl:variable name="texte" select="replace(., '\s+', ' ')"/>
    <xsl:variable name="apres-note" select="following-sibling::node()[1][self::tei:note[@type = 'apparatus']]
                                             /following-sibling::node()[1]"/>
    <xsl:variable name="texte" select="if (ends-with($texte, ' ')
        and following-sibling::node()[1][self::tei:note[@type = 'apparatus']]
        and (empty($apres-note) or ($apres-note instance of text() and matches($apres-note, '^[\s,.;:!?)\]]'))))
      then replace($texte, ' $', '') else $texte"/>
    <xsl:variable name="precedent" select="preceding::text()[not(ancestor::tei:note[@type = 'apparatus'])][1]"/>
    <!-- Une image ou un pointeur, sans texte, se voit : l'espace qui le
         suit reste (Varians 0.9.3.4). -->
    <xsl:variable name="visibles" select="$precedent/following::*[. &lt;&lt; current()]
                                          [self::tei:graphic or self::tei:ptr or self::tei:figure]"/>
    <xsl:variable name="texte" select="if (starts-with($texte, ' ')
        and not(preceding-sibling::node()[1][self::tei:note[@type = 'apparatus']])
        and matches(string($precedent), '\s$') and f:bloc($precedent) is f:bloc(.) and empty($visibles))
      then replace($texte, '^ ', '') else $texte"/>
    <xsl:choose>
      <xsl:when test="$texte = ' ' and preceding-sibling::node()[1][self::*] and following-sibling::node()[1][self::*]
                      and exists(f:bloc(.))">
        <seg><xsl:value-of select="$texte"/></seg>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$texte"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:function name="f:bloc" as="element()?">
    <xsl:param name="n" as="node()?"/>
    <xsl:sequence select="$n/ancestor::*[self::tei:p or self::tei:ab or self::tei:l or self::tei:head or self::tei:note
                                         or self::tei:item or self::tei:cell][1]"/>
  </xsl:function>

  <!-- Mode note : le texte d'une leçon dans sa note. -->
  <xsl:template match="text()" mode="note">
    <xsl:value-of select="f:texte-net(.)"/>
  </xsl:template>
  <!-- La mise en forme est gardée, sans les identifiants (déjà dans le texte),
       mais une leçon est en romain : l'italique est réservé au texte de
       l'éditeur (V0.9.3.0). -->
  <xsl:template match="tei:hi" mode="note">
    <xsl:choose>
      <xsl:when test="matches(lower-case(string-join((@rend, @style), ' ')), 'italic|italique')">
        <xsl:apply-templates mode="note"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:copy><xsl:copy-of select="@* except @xml:id"/><xsl:apply-templates mode="note"/></xsl:copy>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <!-- <sic> : la leçon, suivie de « sic » en italique. -->
  <xsl:template match="tei:sic" mode="note">
    <xsl:apply-templates mode="note"/><xsl:text> </xsl:text><hi rend="italic">sic</hi>
  </xsl:template>
  <xsl:template match="@*" mode="note"/>
  <xsl:template match="tei:app" mode="note">
    <xsl:variable name="retenue" select="f:choix(.)"/>
    <xsl:choose>
      <xsl:when test="exists($retenue)"><xsl:apply-templates select="$retenue/node()" mode="note"/></xsl:when>
      <xsl:otherwise><hi rend="italic"><xsl:value-of select="$f:non-disponible"/></hi></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="tei:choice" mode="note">
    <xsl:apply-templates select="(tei:corr, tei:reg, tei:expan, tei:sic, tei:orig, tei:abbr, *[1])[1]" mode="note"/>
  </xsl:template>
  <xsl:template match="tei:note" mode="note">
    <xsl:param name="lemme" tunnel="yes" as="xs:boolean" select="false()"/>
    <xsl:if test="not($lemme)">
      <xsl:text> (</xsl:text><hi rend="italic"><xsl:apply-templates mode="note"/></hi><xsl:text>)</xsl:text>
    </xsl:if>
  </xsl:template>
  <xsl:template match="tei:lb" mode="note">
    <xsl:if test="f:lb-espace(.)"><xsl:text> </xsl:text></xsl:if>
  </xsl:template>
  <xsl:template match="tei:pb | tei:cb | tei:milestone | tei:fw" mode="note"/>
  <xsl:template match="tei:lacunaStart | tei:lacunaEnd" mode="note">
    <hi rend="italic">
      <xsl:value-of select="if (self::tei:lacunaStart) then $f:lacuna-incipit else $f:lacuna-desinit"/>
      <xsl:if test="f:sigles-lacune(.) != ''"><xsl:text> </xsl:text><xsl:value-of select="f:sigles-lacune(.)"/></xsl:if>
    </hi>
  </xsl:template>
  <xsl:template match="tei:gap" mode="note">
    <hi rend="italic"><xsl:value-of select="f:texte-gap(.)"/></hi>
  </xsl:template>
  <xsl:template match="tei:supplied" mode="note">
    <xsl:text>[</xsl:text><xsl:apply-templates mode="note"/><xsl:text>]</xsl:text>
  </xsl:template>

</xsl:stylesheet>
