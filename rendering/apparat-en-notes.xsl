<?xml version="1.0" encoding="UTF-8"?>
<!--
  Apparat en notes (Varians 0.9.2.7) : pré-passage TEI → TEI des scénarios
  « TEI : DOCX (Word) » et « TEI : ODT (LibreOffice) », appliqué à l'édition
  avant les TEI Stylesheets. Paramètre : temoin-de-base (voir
  apparat-commun.xsl ; les scénarios donnent le témoin pivot, ${pivot}).

  - Chaque <app> devient sa leçon retenue, suivie d'une note de bas de page
    <note place="foot" type="apparatus"> : « leçon ] variante sigles ; … »,
    les sigles en italique, avec om., add., lacuna incipit et lacuna
    desinit, comme dans l'édition critique HTML.
  - Une note de l'éditeur sans @place devient une note de fin
    (place="end") : une autre série que celle de l'apparat.
  - Les <pb> du témoin deviennent des repères de folio ⟨12r⟩ dans le texte
    (<seg type="folio">), les autres disparaissent : pas de saut de page.
  - Les <lb> deviennent des espaces (des <lb> contigus sont une seule
    coupure ; break="no" soude les segments d'un mot) ; les balises de
    lacune hors de l'apparat disparaissent.
  - Une suite d'espaces devient une seule espace, l'appel d'une note suit
    son mot ; l'espace qui sépare deux éléments va dans un <seg>, que Word
    garde.
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
    <xsl:choose>
      <xsl:when test="exists($retenue)"><xsl:apply-templates select="$retenue/node()"/></xsl:when>
      <xsl:otherwise><xsl:value-of select="$f:non-disponible"/></xsl:otherwise>
    </xsl:choose>
    <xsl:if test="array:size($apparat?variantes) gt 0">
      <note place="foot" type="apparatus">
        <xsl:if test="$apparat?lemme">
          <xsl:choose>
            <xsl:when test="exists($retenue)"><xsl:apply-templates select="$retenue/node()" mode="note"/></xsl:when>
            <xsl:otherwise><xsl:value-of select="$f:non-disponible"/></xsl:otherwise>
          </xsl:choose>
          <xsl:text> ] </xsl:text>
        </xsl:if>
        <xsl:for-each select="$apparat?variantes?*">
          <xsl:if test="position() gt 1"><xsl:text> ; </xsl:text></xsl:if>
          <xsl:choose>
            <xsl:when test="?genre = 'om'">
              <xsl:value-of select="$f:om"/>
              <xsl:apply-templates select="?lecon//tei:note" mode="note"/>
            </xsl:when>
            <xsl:otherwise>
              <xsl:apply-templates select="?lecon/node()" mode="note"/>
              <xsl:if test="?genre = 'add'"><xsl:text> </xsl:text><xsl:value-of select="$f:add"/></xsl:if>
            </xsl:otherwise>
          </xsl:choose>
          <xsl:text> </xsl:text>
          <hi rend="italic"><xsl:value-of select="?sigles"/></hi>
        </xsl:for-each>
      </note>
    </xsl:if>
  </xsl:template>

  <xsl:template match="tei:text//tei:note[not(@place)]">
    <note place="end">
      <xsl:apply-templates select="@* | node()"/>
    </note>
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
    <xsl:variable name="texte" select="if (starts-with($texte, ' ')
        and not(preceding-sibling::node()[1][self::tei:note[@type = 'apparatus']])
        and matches(string($precedent), '\s$') and f:bloc($precedent) is f:bloc(.))
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
  <!-- La mise en forme est gardée, sans les identifiants (déjà dans le texte). -->
  <xsl:template match="tei:hi | tei:emph | tei:foreign | tei:title | tei:term" mode="note">
    <xsl:copy><xsl:copy-of select="@* except @xml:id"/><xsl:apply-templates mode="note"/></xsl:copy>
  </xsl:template>
  <xsl:template match="@*" mode="note"/>
  <xsl:template match="tei:app" mode="note">
    <xsl:variable name="retenue" select="f:choix(.)"/>
    <xsl:choose>
      <xsl:when test="exists($retenue)"><xsl:apply-templates select="$retenue/node()" mode="note"/></xsl:when>
      <xsl:otherwise><xsl:value-of select="$f:non-disponible"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="tei:choice" mode="note">
    <xsl:apply-templates select="(tei:corr, tei:reg, tei:expan, tei:sic, tei:orig, tei:abbr, *[1])[1]" mode="note"/>
  </xsl:template>
  <xsl:template match="tei:note" mode="note">
    <xsl:text> (</xsl:text><xsl:apply-templates mode="note"/><xsl:text>)</xsl:text>
  </xsl:template>
  <xsl:template match="tei:lb" mode="note">
    <xsl:if test="f:lb-espace(.)"><xsl:text> </xsl:text></xsl:if>
  </xsl:template>
  <xsl:template match="tei:pb | tei:cb | tei:milestone | tei:fw" mode="note"/>
  <xsl:template match="tei:lacunaStart" mode="note">
    <xsl:value-of select="$f:lacuna-incipit"/>
    <xsl:if test="f:sigles-lacune(.) != ''"><xsl:text> </xsl:text><xsl:value-of select="f:sigles-lacune(.)"/></xsl:if>
  </xsl:template>
  <xsl:template match="tei:lacunaEnd" mode="note">
    <xsl:value-of select="$f:lacuna-desinit"/>
    <xsl:if test="f:sigles-lacune(.) != ''"><xsl:text> </xsl:text><xsl:value-of select="f:sigles-lacune(.)"/></xsl:if>
  </xsl:template>
  <xsl:template match="tei:gap" mode="note">
    <xsl:text>[…]</xsl:text>
  </xsl:template>
  <xsl:template match="tei:supplied" mode="note">
    <xsl:text>[</xsl:text><xsl:apply-templates mode="note"/><xsl:text>]</xsl:text>
  </xsl:template>

</xsl:stylesheet>
