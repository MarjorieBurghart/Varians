<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  exclude-result-prefixes="tei">

  <!-- Fourni par l’éditeur depuis project.xml. -->
  <xsl:param name="baseWitness" select="''"/>
  <xsl:param name="tocTitle" select="'Contents'"/>
  <!-- Scénarios de transformation (V0.9.2.0) : nom de la CSS copiée à côté du résultat. -->
  <xsl:param name="css" select="'tei.css'"/>

  <xsl:output method="html" encoding="UTF-8" indent="yes" doctype-system="about:legacy-compat"/>

  <!-- Sigles d'un @wit (Varians 0.9.2.8.2) : pour chaque témoin, son
       <idno type="siglum"> dans <listWit>, sinon son identifiant. -->
  <xsl:key name="witness-by-id" match="tei:witness[@xml:id]" use="@xml:id"/>
  <xsl:template name="sigles">
    <xsl:param name="wit"/>
    <xsl:variable name="token" select="substring-before(concat($wit, ' '), ' ')"/>
    <xsl:variable name="id">
      <xsl:choose>
        <xsl:when test="contains($token, '#')"><xsl:value-of select="substring-after($token, '#')"/></xsl:when>
        <xsl:otherwise><xsl:value-of select="$token"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="idno" select="key('witness-by-id', $id)/tei:idno[@type = 'siglum'][normalize-space()]"/>
    <xsl:choose>
      <xsl:when test="$idno"><xsl:value-of select="normalize-space($idno[1])"/></xsl:when>
      <xsl:otherwise><xsl:value-of select="$id"/></xsl:otherwise>
    </xsl:choose>
    <xsl:if test="substring-after($wit, ' ')">
      <xsl:text> </xsl:text>
      <xsl:call-template name="sigles"><xsl:with-param name="wit" select="substring-after($wit, ' ')"/></xsl:call-template>
    </xsl:if>
  </xsl:template>

  <!-- Divisions de l'édition (Varians 0.9.2.9). -->
  <xsl:variable name="divisions"
    select="//tei:body//*[self::tei:div or self::tei:div1 or self::tei:div2 or self::tei:div3
                          or self::tei:div4 or self::tei:div5 or self::tei:div6 or self::tei:div7]"/>

  <!-- ROOT. L'en-tête montre le titre de l'édition ; la langue de la page
       est celle du texte (@xml:lang de <text>, sinon de <TEI>). -->
  <xsl:template match="/">
    <html>
      <xsl:choose>
        <xsl:when test="/tei:TEI/tei:text/@xml:lang">
          <xsl:attribute name="lang"><xsl:value-of select="/tei:TEI/tei:text/@xml:lang"/></xsl:attribute>
        </xsl:when>
        <xsl:when test="/*/@xml:lang">
          <xsl:attribute name="lang"><xsl:value-of select="/*/@xml:lang"/></xsl:attribute>
        </xsl:when>
      </xsl:choose>
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title><xsl:value-of select="//tei:titleStmt/tei:title"/></title>
        <link rel="stylesheet" href="{$css}"/>
      </head>
      <body>
        <header>
          <h1><xsl:value-of select="//tei:titleStmt/tei:title"/></h1>
        </header>
        <!-- Sommaire : les divisions titrées, par niveaux. -->
        <xsl:if test="$divisions[tei:head or normalize-space(@n) != '']">
          <nav class="toc">
            <div class="toc-title"><xsl:value-of select="$tocTitle"/></div>
            <ul class="toc-list">
              <xsl:apply-templates select="//tei:body/*" mode="toc"/>
            </ul>
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

  <!-- Ancre d'une division : son @xml:id, sinon un identifiant produit. -->
  <xsl:template name="ancre">
    <xsl:choose>
      <xsl:when test="@xml:id"><xsl:value-of select="@xml:id"/></xsl:when>
      <xsl:otherwise><xsl:value-of select="generate-id()"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- DIVISION (Varians 0.9.2.9), comme dans « Édition critique » : titrée
       par son premier <head>, sinon par son @n ; un @xml:id n'est pas un
       titre. -->
  <xsl:template match="tei:div | tei:div1 | tei:div2 | tei:div3 | tei:div4 | tei:div5 | tei:div6 | tei:div7">
    <xsl:variable name="ancre"><xsl:call-template name="ancre"/></xsl:variable>
    <a name="{$ancre}"></a>
    <div class="section" id="{$ancre}">
      <xsl:if test="not(tei:head) and normalize-space(@n) != ''">
        <h2 class="section-title"><xsl:value-of select="@n"/></h2>
      </xsl:if>
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <!-- Titre d'une division : son premier <head>. -->
  <xsl:template match="tei:head[not(preceding-sibling::tei:head)]
                       [parent::tei:div or parent::tei:div1 or parent::tei:div2 or parent::tei:div3
                        or parent::tei:div4 or parent::tei:div5 or parent::tei:div6 or parent::tei:div7]">
    <h2 class="section-title"><xsl:apply-templates/></h2>
  </xsl:template>

  <!-- SOMMAIRE : une entrée par division titrée, ses sous-divisions titrées
       en dessous ; une division sans titre laisse passer les siennes. -->
  <xsl:template match="tei:div | tei:div1 | tei:div2 | tei:div3 | tei:div4 | tei:div5 | tei:div6 | tei:div7"
                mode="toc">
    <xsl:choose>
      <xsl:when test="tei:head or normalize-space(@n) != ''">
        <xsl:variable name="ancre"><xsl:call-template name="ancre"/></xsl:variable>
        <li>
          <a class="toc-link" href="tei-toc:/{$ancre}">
            <xsl:choose>
              <xsl:when test="tei:head"><xsl:apply-templates select="tei:head[1]" mode="toc-label"/></xsl:when>
              <xsl:otherwise><xsl:value-of select="normalize-space(@n)"/></xsl:otherwise>
            </xsl:choose>
          </a>
          <xsl:variable name="sous" select=".//*[self::tei:div or self::tei:div1 or self::tei:div2 or self::tei:div3
                                                 or self::tei:div4 or self::tei:div5 or self::tei:div6
                                                 or self::tei:div7][tei:head or normalize-space(@n) != '']"/>
          <xsl:if test="$sous">
            <ul><xsl:apply-templates select="*" mode="toc"/></ul>
          </xsl:if>
        </li>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="*" mode="toc"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="*" mode="toc">
    <xsl:apply-templates select="*" mode="toc"/>
  </xsl:template>

  <!-- Libellé du sommaire : le texte du titre, sans notes ni leçons
       variantes. -->
  <xsl:template match="tei:note | tei:rdg | tei:rdgGrp | tei:witDetail" mode="toc-label"/>
  <xsl:template match="text()" mode="toc-label">
    <xsl:value-of select="."/>
  </xsl:template>

  <!-- PARAGRAPH -->
  <xsl:template match="tei:p">
    <p><xsl:apply-templates/></p>
  </xsl:template>

  <!-- VERSE (Varians 0.9.2.9) : chaque <lg> en bloc, chaque <l> sur sa ligne. -->
  <xsl:template match="tei:lg">
    <div class="lg"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="tei:l">
    <div class="l"><xsl:apply-templates/></div>
  </xsl:template>

  <!-- HEAD (Varians 0.9.2.9) -->
  <xsl:template match="tei:head">
    <h3 class="head"><xsl:apply-templates/></h3>
  </xsl:template>

  <!-- LIST (Varians 0.9.2.9) : son <head> avant la liste ; liste numérotée
       si @rend contient « numbered », ou si @type vaut « ordered » ou
       « numbered » (comme dans la feuille « Édition critique »). -->
  <xsl:template match="tei:list">
    <xsl:apply-templates select="tei:head"/>
    <xsl:choose>
      <xsl:when test="contains(concat(' ', normalize-space(@rend), ' '), ' numbered ')
                      or @type = 'ordered' or @type = 'numbered'">
        <ol class="list"><xsl:apply-templates select="node()[not(self::tei:head)]"/></ol>
      </xsl:when>
      <xsl:otherwise>
        <ul class="list"><xsl:apply-templates select="node()[not(self::tei:head)]"/></ul>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="tei:item">
    <li><xsl:apply-templates/></li>
  </xsl:template>

  <!-- FIGURE (Varians 0.9.2.9) -->
  <xsl:template match="tei:figure">
    <div class="figure"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="tei:figDesc">
    <div class="figdesc"><xsl:apply-templates/></div>
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
      <xsl:if test="@wit"><xsl:text> (</xsl:text><xsl:call-template name="sigles"><xsl:with-param name="wit" select="normalize-space(@wit)"/></xsl:call-template><xsl:text>)</xsl:text></xsl:if>
    </em>
    <xsl:text> </xsl:text>
  </xsl:template>
  <xsl:template match="tei:rdg">
    <xsl:if test="position() != 1"> | </xsl:if>
    <xsl:if test=". = ''"><xsl:text>--</xsl:text></xsl:if>
    <xsl:apply-templates/> <em>
      <xsl:if test="@wit"><xsl:text> (</xsl:text><xsl:call-template name="sigles"><xsl:with-param name="wit" select="normalize-space(@wit)"/></xsl:call-template><xsl:text>)</xsl:text></xsl:if>
    </em>
    <xsl:text> </xsl:text>
  </xsl:template>
  
  

</xsl:stylesheet>
