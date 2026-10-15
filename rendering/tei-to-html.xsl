<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  exclude-result-prefixes="tei">

  <!-- Fourni par l’éditeur depuis project.xml. -->
  <xsl:param name="baseWitness" select="''"/>
  <xsl:param name="tocTitle" select="'Contents'"/>

  <xsl:output method="html" encoding="UTF-8" indent="yes" doctype-system="about:legacy-compat"/>

  <!-- ROOT -->
  <xsl:template match="/">
    <html lang="la">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title><xsl:value-of select="//tei:titleStmt/tei:title"/></title>
        <link rel="stylesheet" href="tei.css"/>
      </head>
      <body>
        <header>
          <h1><xsl:value-of select="//tei:titleStmt/tei:title"/></h1>
          <p class="meta">
            <xsl:value-of select="//tei:msContents//tei:origDate"/>
            <xsl:text> · </xsl:text>
            <xsl:value-of select="//tei:msContents//tei:textLang"/>
          </p>
        </header>
        <xsl:if test="//tei:body//tei:div[@xml:id]">
          <nav class="toc">
            <div class="toc-title"><xsl:value-of select="$tocTitle"/></div>
            <div class="toc-list">
              <xsl:for-each select="//tei:body//tei:div[@xml:id]">
                <a class="toc-link" href="tei-toc:/{@xml:id}">
                  <xsl:value-of select="translate(@xml:id, '_', ' ')"/>
                </a>
                <xsl:text> </xsl:text>
              </xsl:for-each>
            </div>
          </nav>
        </xsl:if>
        <main>
          <xsl:apply-templates select="//tei:body"/>
        </main>
      </body>
    </html>
  </xsl:template>

  <!-- BODY -->
  <xsl:template match="tei:body">
    <xsl:apply-templates/>
  </xsl:template>

  <!-- DIV with @xml:id -->
  <xsl:template match="tei:div[@xml:id]">
    <a name="{@xml:id}"></a>
    <div class="section" id="{@xml:id}">
      <h2 class="section-title"><xsl:value-of select="@xml:id"/></h2>
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <!-- DIV without @xml:id -->
  <xsl:template match="tei:div">
    <xsl:apply-templates/>
  </xsl:template>

  <!-- PARAGRAPH -->
  <xsl:template match="tei:p">
    <p><xsl:apply-templates/></p>
  </xsl:template>

  <!-- PAGE BREAK -->
  <xsl:template match="tei:pb">
    <span class="pb" title="Page : {@n}">[<xsl:value-of select="@n"/>]</span>
  </xsl:template>

  <!-- LINE BREAK -->
  <xsl:template match="tei:lb">
    <!-- Marqueur technique invisible utilisé par l’application.
         U+2060 WORD JOINER est volontairement utilisé ici (et non U+200B) :
         il reste invisible mais interdit une coupure de ligne à l’emplacement
         d’un <lb break="no"/>, afin de reconstituer correctement les mots.
         IMPORTANT : l’indice n’est plus calculé ici avec count(preceding::...),
         opération très coûteuse sur plusieurs milliers de lignes. Python remplace
         INDEX par 0,1,2... en un seul passage linéaire après la transformation. -->
    <xsl:if test="@edRef=concat('#',$baseWitness)">
      <a class="tei-line-marker" href="tei-line://base/INDEX"><xsl:text>&#8288;</xsl:text></a>
    </xsl:if>
    <xsl:if test="not(@break='no')">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>

  <!--
    TEXT NODES
    A <lb break="no"/> splits a word across two XML lines, leaving
    whitespace on both sides:  "me\n<lb break="no"/>\ncum"
    We strip trailing ws from the text node BEFORE the lb,
    and leading ws from the text node AFTER it.
  -->
  <xsl:template match="text()">
    <xsl:variable name="s" select="."/>
    <xsl:variable name="afterBreakNo" select="preceding-sibling::node()[1][self::tei:lb[@break='no']]"/>
    <xsl:variable name="beforeBreakNo" select="following-sibling::node()[1][self::tei:lb[@break='no']]"/>
    <xsl:choose>
      <!--
        A text node can be BETWEEN two <lb break="no"/> elements belonging
        to different witnesses. In that case both ends must be cleaned.
        Using only an xsl:choose with separate before/after branches would
        clean one side and leave the other one untouched.
      -->
      <xsl:when test="$afterBreakNo and $beforeBreakNo">
        <xsl:call-template name="strip-both-ws">
          <xsl:with-param name="s" select="$s"/>
        </xsl:call-template>
      </xsl:when>
      <!-- AFTER lb break=no: strip leading whitespace -->
      <xsl:when test="$afterBreakNo">
        <xsl:call-template name="strip-leading-ws">
          <xsl:with-param name="s" select="$s"/>
        </xsl:call-template>
      </xsl:when>
      <!-- BEFORE lb break=no: strip trailing whitespace -->
      <xsl:when test="$beforeBreakNo">
        <xsl:call-template name="strip-trailing-ws">
          <xsl:with-param name="s" select="$s"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$s"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Strip whitespace at BOTH ends (needed between two break=no lb nodes). -->
  <xsl:template name="strip-both-ws">
    <xsl:param name="s"/>
    <xsl:variable name="len" select="string-length($s)"/>
    <xsl:choose>
      <xsl:when test="$len = 0"/>
      <xsl:when test="translate(substring($s,1,1), ' &#9;&#10;&#13;', '') = ''">
        <xsl:call-template name="strip-both-ws">
          <xsl:with-param name="s" select="substring($s, 2)"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="translate(substring($s,$len,1), ' &#9;&#10;&#13;', '') = ''">
        <xsl:call-template name="strip-both-ws">
          <xsl:with-param name="s" select="substring($s, 1, $len - 1)"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$s"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Recursively strip leading whitespace -->
  <xsl:template name="strip-leading-ws">
    <xsl:param name="s"/>
    <xsl:choose>
      <xsl:when test="string-length($s) = 0"/>
      <xsl:when test="translate(substring($s,1,1), ' &#9;&#10;&#13;', '') = ''">
        <xsl:call-template name="strip-leading-ws">
          <xsl:with-param name="s" select="substring($s, 2)"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$s"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Recursively strip trailing whitespace -->
  <xsl:template name="strip-trailing-ws">
    <xsl:param name="s"/>
    <xsl:variable name="len" select="string-length($s)"/>
    <xsl:choose>
      <xsl:when test="$len = 0"/>
      <xsl:when test="translate(substring($s, $len, 1), ' &#9;&#10;&#13;', '') = ''">
        <xsl:call-template name="strip-trailing-ws">
          <xsl:with-param name="s" select="substring($s, 1, $len - 1)"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$s"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- QUOTE -->
  <!--
  <xsl:template match="tei:quote">
    <span class="quote"><xsl:apply-templates/></span>
  </xsl:template>
  -->
  
  <xsl:template match="tei:cit">
    <xsl:apply-templates select="tei:quote"/>
  </xsl:template>
  
  <!-- HI -->
  <xsl:template match="tei:hi[@rend='italic' or @rend='italics']">
    <xsl:element name="span">
      <xsl:attribute name="class">quote</xsl:attribute>
      <xsl:if test="parent::tei:quote">
        <xsl:attribute name="title"><xsl:value-of select="ancestor::tei:cit/tei:ref"/></xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/>
    </xsl:element>
  </xsl:template>
  
  <!-- UNCLEAR -->
  <xsl:template match="tei:unclear">
    <span class="unclear" title="Lecture incertaine"><xsl:apply-templates/></span>
  </xsl:template>

  <!-- NOTE -->
  <xsl:template match="tei:note">
    <span class="note">[<em><xsl:apply-templates/></em>]</span>
  </xsl:template>

  <!-- Suppress teiHeader -->
  <xsl:template match="tei:teiHeader"/>
  
  <!-- APP -->
  <xsl:template match="tei:app">
    <span class="apparatus"><xsl:text>[</xsl:text><xsl:apply-templates/><xsl:text>]</xsl:text></span>
  </xsl:template>
  <xsl:template match="tei:lem">
    <xsl:if test=". = ''"><xsl:text>--</xsl:text></xsl:if>    
    <b><xsl:apply-templates/></b> <em>
      <xsl:if test="@wit"><xsl:text> (</xsl:text><xsl:value-of select="translate(@wit, '#', '')"/><xsl:text>)</xsl:text></xsl:if>
    </em>
    <xsl:text> </xsl:text>
  </xsl:template>
  <xsl:template match="tei:rdg">
    <xsl:if test="position() != 1"> | </xsl:if>
    <xsl:if test=". = ''"><xsl:text>--</xsl:text></xsl:if>
    <xsl:apply-templates/> <em>
      <xsl:if test="@wit"><xsl:text> (</xsl:text><xsl:value-of select="translate(@wit, '#', '')"/><xsl:text>)</xsl:text></xsl:if>
    </em>
    <xsl:text> </xsl:text>
  </xsl:template>
  
  

</xsl:stylesheet>
