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
  <!-- Textes de la feuille (V0.9.3.1) : langue de l'interface et adresse
       des catalogues i18n de Varians (« file:…/i18n/ »), passées par Varians. -->
  <xsl:param name="langue" select="'fr'"/>
  <xsl:param name="catalogues" select="''"/>

  <!-- Le texte d'une clé dans le catalogue de la langue demandée, sinon le
       français. document() n'est appelé qu'avec un catalogue : le moteur
       .NET de secours (sans lxml) l'interdit. -->
  <xsl:template name="texte">
    <xsl:param name="cle"/>
    <xsl:variable name="traduit">
      <xsl:if test="$catalogues != ''">
        <xsl:value-of select="document(concat($catalogues, $langue, '.xml'))/translations/string[@key = $cle]"/>
      </xsl:if>
    </xsl:variable>
    <xsl:choose>
      <xsl:when test="string($traduit) != ''"><xsl:value-of select="$traduit"/></xsl:when>
      <xsl:otherwise><xsl:call-template name="texte-fr"><xsl:with-param name="cle" select="$cle"/></xsl:call-template></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Le français, identique au catalogue français. -->
  <xsl:template name="texte-fr">
    <xsl:param name="cle"/>
    <xsl:choose>
      <xsl:when test="$cle = 'viewer.form.sic'">Leçon transmise</xsl:when>
      <xsl:when test="$cle = 'viewer.form.corr'">Correction</xsl:when>
      <xsl:when test="$cle = 'viewer.form.orig'">Graphie originale</xsl:when>
      <xsl:when test="$cle = 'viewer.form.reg'">Graphie normalisée</xsl:when>
      <xsl:when test="$cle = 'viewer.form.abbr'">Abréviation</xsl:when>
      <xsl:when test="$cle = 'viewer.form.expan'">Développement</xsl:when>
      <xsl:when test="$cle = 'viewer.form.gap'">Lacune</xsl:when>
      <xsl:when test="$cle = 'viewer.form.detail'">{label} : {value}</xsl:when>
      <xsl:when test="$cle = 'publication.page'">Page : {n}</xsl:when>
      <xsl:when test="$cle = 'publication.unclear'">Lecture incertaine</xsl:when>
      <xsl:when test="$cle = 'publication.sic'">Leçon transmise (sic)</xsl:when>
      <xsl:when test="$cle = 'publication.gap'">[lacune]</xsl:when>
      <xsl:when test="$cle = 'publication.gap.extent'">[lacune : {extent}]</xsl:when>
      <xsl:when test="$cle = 'publication.critique.front_matter'">Préliminaires</xsl:when>
      <xsl:when test="$cle = 'publication.critique.back_matter'">Annexes</xsl:when>
      <xsl:when test="$cle = 'publication.editor_siglum'">éd.</xsl:when>
    </xsl:choose>
  </xsl:template>

  <!-- Le texte d'une clé, sa variable {nom} remplacée par valeur. -->
  <xsl:template name="texte-avec">
    <xsl:param name="cle"/>
    <xsl:param name="nom"/>
    <xsl:param name="valeur"/>
    <xsl:variable name="texte"><xsl:call-template name="texte"><xsl:with-param name="cle" select="$cle"/></xsl:call-template></xsl:variable>
    <xsl:variable name="marque" select="concat('{', $nom, '}')"/>
    <xsl:choose>
      <xsl:when test="contains($texte, $marque)">
        <xsl:value-of select="concat(substring-before($texte, $marque), $valeur, substring-after($texte, $marque))"/>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$texte"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- « Libellé : valeur » (viewer.form.detail). -->
  <xsl:template name="detail">
    <xsl:param name="libelle"/>
    <xsl:param name="valeur"/>
    <xsl:variable name="modele"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.detail'"/></xsl:call-template></xsl:variable>
    <xsl:variable name="debut" select="concat(substring-before($modele, '{label}'), $libelle, substring-after($modele, '{label}'))"/>
    <xsl:value-of select="concat(substring-before($debut, '{value}'), $valeur, substring-after($debut, '{value}'))"/>
  </xsl:template>

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

  <!-- Groupes de <lb> contigus (Varians 0.9.3.4) : ceux qui suivent un même
       nœud, des blancs entre eux n'y changeant rien. -->
  <xsl:key name="lb-groupe" match="tei:lb"
    use="concat(generate-id(..), '/', generate-id(preceding-sibling::node()[not(self::tei:lb) and not(self::text() and normalize-space() = '')][1]))"/>

  <!-- Divisions de l'édition (Varians 0.9.2.9), préliminaires et annexes
       compris (Varians 0.9.3.4). -->
  <xsl:variable name="divisions"
    select="(//tei:front | //tei:body | //tei:back)//*[self::tei:div or self::tei:div1 or self::tei:div2 or self::tei:div3
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
              <xsl:apply-templates select="//tei:front/* | //tei:body/* | //tei:back/*" mode="toc"/>
            </ul>
          </nav>
        </xsl:if>
        <main>
          <xsl:apply-templates select="//tei:front | //tei:body | //tei:back"/>
        </main>
      </body>
    </html>
  </xsl:template>

  <!-- BODY -->
  <xsl:template match="tei:body">
    <xsl:apply-templates/>
  </xsl:template>

  <!-- Préliminaires et annexes (Varians 0.9.3.4) : rendus, titrés comme
       dans « Édition critique ». -->
  <xsl:template match="tei:front | tei:back">
    <h2 class="section-title">
      <xsl:choose>
        <xsl:when test="self::tei:front"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'publication.critique.front_matter'"/></xsl:call-template></xsl:when>
        <xsl:otherwise><xsl:call-template name="texte"><xsl:with-param name="cle" select="'publication.critique.back_matter'"/></xsl:call-template></xsl:otherwise>
      </xsl:choose>
    </h2>
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

  <!-- VERSE (Varians 0.9.2.9, 0.9.3.0) : chaque <lg> est un seul bloc, ses
       vers séparés par un <br/> ; l'aperçu de Varians (Qt) ne regroupe pas
       des blocs imbriqués. Dans un navigateur, tei.css fait de chaque vers
       un bloc. Un <l> hors d'un <lg> est un bloc. -->
  <xsl:template match="tei:lg">
    <div class="lg"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="tei:lg/tei:l">
    <span class="l"><xsl:apply-templates/></span>
    <xsl:if test="following-sibling::tei:l"><br/></xsl:if>
  </xsl:template>

  <xsl:template match="tei:l">
    <div class="l"><xsl:apply-templates/></div>
  </xsl:template>

  <!-- THEATRE (Varians 0.9.3.1), comme le viewer web : chaque réplique
       (<sp>) est un bloc, son locuteur (<speaker>) en tête. Une didascalie
       (<stage>), entre parenthèses comme dans « Édition critique », est un
       bloc entre deux blocs, une ligne dans une strophe, en italique dans
       une phrase ; les parenthèses touchent son texte (voir text()). -->
  <xsl:template match="tei:sp">
    <div class="sp"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="tei:speaker">
    <div class="speaker"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="tei:stage">
    <span class="stage">(<xsl:apply-templates/>)</span>
  </xsl:template>

  <xsl:template match="tei:lg/tei:stage">
    <span class="stage">(<xsl:apply-templates/>)</span>
    <xsl:if test="following-sibling::tei:l"><br/></xsl:if>
  </xsl:template>

  <xsl:template match="tei:stage[parent::tei:sp or parent::tei:spGrp or parent::tei:body or parent::tei:front
                       or parent::tei:back or parent::tei:div or parent::tei:div1 or parent::tei:div2
                       or parent::tei:div3 or parent::tei:div4 or parent::tei:div5 or parent::tei:div6
                       or parent::tei:div7]">
    <div class="stage">(<xsl:apply-templates/>)</div>
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

  <!-- TABLE (Varians 0.9.3.0) : son <head> en légende ; une cellule
       @role="label", ou d'une ligne @role="label", en en-tête ; @cols et
       @rows fusionnent les cellules. -->
  <xsl:template match="tei:table">
    <table class="table">
      <xsl:if test="tei:head">
        <caption><xsl:apply-templates select="tei:head[1]/node()"/></caption>
      </xsl:if>
      <tbody><xsl:apply-templates select="node()[not(self::tei:head)]"/></tbody>
    </table>
  </xsl:template>

  <xsl:template match="tei:row">
    <tr><xsl:apply-templates/></tr>
  </xsl:template>

  <xsl:template match="tei:cell">
    <xsl:choose>
      <xsl:when test="@role = 'label' or (not(@role) and ../@role = 'label')">
        <th><xsl:call-template name="cell-span"/><xsl:apply-templates/></th>
      </xsl:when>
      <xsl:otherwise>
        <td><xsl:call-template name="cell-span"/><xsl:apply-templates/></td>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="cell-span">
    <xsl:if test="number(@cols) &gt; 1">
      <xsl:attribute name="colspan"><xsl:value-of select="normalize-space(@cols)"/></xsl:attribute>
    </xsl:if>
    <xsl:if test="number(@rows) &gt; 1">
      <xsl:attribute name="rowspan"><xsl:value-of select="normalize-space(@rows)"/></xsl:attribute>
    </xsl:if>
  </xsl:template>

  <!-- PAGE BREAK -->
  <xsl:template match="tei:pb">
    <span class="pb">
      <xsl:attribute name="title">
        <xsl:call-template name="texte-avec">
          <xsl:with-param name="cle" select="'publication.page'"/>
          <xsl:with-param name="nom" select="'n'"/>
          <xsl:with-param name="valeur" select="string(@n)"/>
        </xsl:call-template>
      </xsl:attribute>[<xsl:value-of select="@n"/>]</span>
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
    <!-- Des <lb> contigus (de plusieurs témoins) sont une seule coupure,
         comme dans « Édition critique » : l'espace du premier, aucune si
         l'un porte break="no" (Varians 0.9.3.4). -->
    <xsl:variable name="groupe" select="key('lb-groupe', concat(generate-id(..), '/',
      generate-id(preceding-sibling::node()[not(self::tei:lb) and not(self::text() and normalize-space() = '')][1])))"/>
    <xsl:if test="not($groupe[@break='no']) and generate-id($groupe[1]) = generate-id(.)">
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
    <!-- Les <lb> contigus avant et après ce texte : leur groupe soude-t-il
         le mot (Varians 0.9.3.4) ? -->
    <xsl:variable name="avant" select="preceding-sibling::node()[not(self::text() and normalize-space() = '')][1][self::tei:lb]"/>
    <xsl:variable name="apres" select="following-sibling::node()[not(self::text() and normalize-space() = '')][1][self::tei:lb]"/>
    <xsl:variable name="soudeAvant" select="$avant and key('lb-groupe', concat(generate-id(..), '/',
      generate-id($avant/preceding-sibling::node()[not(self::tei:lb) and not(self::text() and normalize-space() = '')][1])))[@break='no']"/>
    <xsl:variable name="soudeApres" select="$apres and key('lb-groupe', concat(generate-id(..), '/',
      generate-id($apres/preceding-sibling::node()[not(self::tei:lb) and not(self::text() and normalize-space() = '')][1])))[@break='no']"/>
    <!-- Le premier et le dernier texte d'une didascalie touchent ses parenthèses. -->
    <xsl:variable name="afterBreakNo" select="$soudeAvant
      or (ancestor::tei:stage and generate-id(ancestor::tei:stage[1]/descendant::text()[1]) = generate-id())"/>
    <xsl:variable name="beforeBreakNo" select="$soudeApres
      or (ancestor::tei:stage and generate-id(ancestor::tei:stage[1]/descendant::text()[last()]) = generate-id())"/>
    <xsl:choose>
      <!-- Un blanc entre deux <lb> d'un même groupe : la coupure est celle
           du groupe. -->
      <xsl:when test="normalize-space($s) = '' and $avant and $apres"/>
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
  
  <!-- CITATION (Varians 0.9.3.0) : la citation, puis sa référence entre
       chevrons, grisée (classe « ref »). -->
  <xsl:template match="tei:cit">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="tei:cit/tei:ref">
    <xsl:text> </xsl:text>
    <span class="ref">&lt;<xsl:apply-templates/>&gt;</span>
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
  
  <!-- Autres rendus de <hi> (Varians 0.9.3.0, comme « Édition critique » et
       le viewer web) : italique, gras, souligné, exposant, indice, petites
       capitales, par les éléments HTML que l'aperçu (Qt) sait afficher sans
       CSS ; l'italique seul reste ci-dessus. -->
  <xsl:template match="tei:hi">
    <xsl:variable name="r" select="concat(' ', translate(normalize-space(@rend),
      'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), ' ')"/>
    <xsl:call-template name="hi-couches">
      <xsl:with-param name="couches">
        <xsl:if test="contains($r, ' italic ') or contains($r, ' italics ')">i </xsl:if>
        <xsl:if test="contains($r, ' bold ')">b </xsl:if>
        <xsl:if test="contains($r, ' underline ')">u </xsl:if>
        <xsl:if test="contains($r, ' sup ') or contains($r, ' superscript ')">sup </xsl:if>
        <xsl:if test="contains($r, ' sub ') or contains($r, ' subscript ')">sub </xsl:if>
        <xsl:if test="contains($r, ' smallcaps ') or contains($r, ' small-caps ')">sc </xsl:if>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  <xsl:template name="hi-couches">
    <xsl:param name="couches"/>
    <xsl:variable name="c" select="substring-before($couches, ' ')"/>
    <xsl:choose>
      <xsl:when test="$c = ''"><xsl:apply-templates/></xsl:when>
      <xsl:when test="$c = 'sc'">
        <span class="petites-capitales">
          <xsl:call-template name="hi-couches">
            <xsl:with-param name="couches" select="substring-after($couches, ' ')"/>
          </xsl:call-template>
        </span>
      </xsl:when>
      <xsl:otherwise>
        <xsl:element name="{$c}">
          <xsl:call-template name="hi-couches">
            <xsl:with-param name="couches" select="substring-after($couches, ' ')"/>
          </xsl:call-template>
        </xsl:element>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="tei:emph | tei:title | tei:foreign">
    <i><xsl:apply-templates/></i>
  </xsl:template>

  <!-- UNCLEAR -->
  <xsl:template match="tei:unclear">
    <span class="unclear">
      <xsl:attribute name="title"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'publication.unclear'"/></xsl:call-template></xsl:attribute>
      <xsl:apply-templates/>
    </span>
  </xsl:template>

  <!-- PHÉNOMÈNES ÉDITORIAUX (Varians 0.9.3.0), comme « Édition critique » :
       un <choice> montre la première forme présente parmi corr, reg, expan,
       sic, orig, abbr (sinon la première), les autres en infobulle ; <sic>
       signalé ; <del> et <surplus> barrés, <add> marqué ; <supplied> entre
       crochets ; <gap> « [lacune] » (dans la langue de l'interface,
       V0.9.3.1) ; <space> une espace. -->
  <xsl:template match="tei:choice">
    <xsl:variable name="forme">
      <xsl:choose>
        <xsl:when test="tei:corr">corr</xsl:when>
        <xsl:when test="tei:reg">reg</xsl:when>
        <xsl:when test="tei:expan">expan</xsl:when>
        <xsl:when test="tei:sic">sic</xsl:when>
        <xsl:when test="tei:orig">orig</xsl:when>
        <xsl:when test="tei:abbr">abbr</xsl:when>
        <xsl:otherwise><xsl:value-of select="local-name(*[1])"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <span class="choice">
      <xsl:if test="*[local-name() != $forme][normalize-space()]">
        <xsl:attribute name="title">
          <xsl:for-each select="*[local-name() != $forme][normalize-space()]">
            <xsl:if test="position() &gt; 1"> · </xsl:if>
            <xsl:call-template name="detail">
              <xsl:with-param name="libelle"><xsl:call-template name="nom-de-forme"/></xsl:with-param>
              <xsl:with-param name="valeur" select="normalize-space(.)"/>
            </xsl:call-template>
          </xsl:for-each>
        </xsl:attribute>
      </xsl:if>
      <xsl:apply-templates select="*[local-name() = $forme][1]"/>
    </span>
  </xsl:template>

  <xsl:template name="nom-de-forme">
    <xsl:choose>
      <xsl:when test="self::tei:sic"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.sic'"/></xsl:call-template></xsl:when>
      <xsl:when test="self::tei:corr"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.corr'"/></xsl:call-template></xsl:when>
      <xsl:when test="self::tei:orig"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.orig'"/></xsl:call-template></xsl:when>
      <xsl:when test="self::tei:reg"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.reg'"/></xsl:call-template></xsl:when>
      <xsl:when test="self::tei:abbr"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.abbr'"/></xsl:call-template></xsl:when>
      <xsl:when test="self::tei:expan"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.expan'"/></xsl:call-template></xsl:when>
      <xsl:otherwise><xsl:value-of select="local-name()"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="tei:sic">
    <span class="sic">
      <xsl:attribute name="title"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'publication.sic'"/></xsl:call-template></xsl:attribute>
      <xsl:apply-templates/>
    </span>
  </xsl:template>

  <xsl:template match="tei:del | tei:surplus">
    <span class="rature"><xsl:apply-templates/></span>
  </xsl:template>

  <xsl:template match="tei:add">
    <span class="ajout"><xsl:apply-templates/></span>
  </xsl:template>

  <xsl:template match="tei:supplied">
    <span class="restitution">[<xsl:apply-templates/>]</span>
  </xsl:template>

  <xsl:template match="tei:gap">
    <span class="lacune">
      <xsl:variable name="lacune"><xsl:call-template name="texte"><xsl:with-param name="cle" select="'viewer.form.gap'"/></xsl:call-template></xsl:variable>
      <xsl:attribute name="title">
        <xsl:choose>
          <xsl:when test="normalize-space(@reason)">
            <xsl:call-template name="detail">
              <xsl:with-param name="libelle" select="$lacune"/>
              <xsl:with-param name="valeur" select="normalize-space(@reason)"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:otherwise><xsl:value-of select="$lacune"/></xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
      <xsl:choose>
        <xsl:when test="normalize-space(@extent)">
          <xsl:call-template name="texte-avec">
            <xsl:with-param name="cle" select="'publication.gap.extent'"/>
            <xsl:with-param name="nom" select="'extent'"/>
            <xsl:with-param name="valeur" select="normalize-space(@extent)"/>
          </xsl:call-template>
        </xsl:when>
        <xsl:otherwise><xsl:call-template name="texte"><xsl:with-param name="cle" select="'publication.gap'"/></xsl:call-template></xsl:otherwise>
      </xsl:choose>
    </span>
  </xsl:template>

  <xsl:template match="tei:space">
    <xsl:text> </xsl:text>
  </xsl:template>

  <!-- NOTE -->
  <xsl:template match="tei:note">
    <span class="note">[<em><xsl:apply-templates/></em>]</span>
  </xsl:template>

  <!-- Suppress teiHeader -->
  <xsl:template match="tei:teiHeader"/>
  
  <!-- APP : l'apparat en ligne, « [leçon (sigles) | leçon (sigles) ] », avec
       la règle commune (Varians 0.9.3.4) : un séparateur entre deux leçons,
       celles d'un <rdgGrp> comprises ; le @wit d'un <rdgGrp> vaut pour ses
       leçons ; une leçon sans témoin est « éd. » ; une omission « om. ».
       Un vers qui suit un apparat de vers va à la ligne. -->
  <xsl:template match="tei:app">
    <span class="apparatus"><xsl:text>[</xsl:text><xsl:apply-templates select="node()[not(self::text() and normalize-space() = '')]"/><xsl:text>]</xsl:text></span>
    <xsl:if test="parent::tei:lg and .//tei:l and following-sibling::tei:l"><br/></xsl:if>
  </xsl:template>
  <xsl:template match="tei:lem | tei:rdg">
    <xsl:variable name="app" select="ancestor::tei:app[1]"/>
    <xsl:variable name="lecons" select="$app/tei:lem | $app/tei:rdg | $app/tei:rdgGrp/tei:lem | $app/tei:rdgGrp/tei:rdg
                                        | $app/tei:rdgGrp/tei:rdgGrp/tei:lem | $app/tei:rdgGrp/tei:rdgGrp/tei:rdg"/>
    <xsl:if test="generate-id(.) != generate-id($lecons[1])"> | </xsl:if>
    <xsl:variable name="wit">
      <xsl:choose>
        <xsl:when test="@wit"><xsl:value-of select="normalize-space(@wit)"/></xsl:when>
        <xsl:otherwise><xsl:value-of select="normalize-space(ancestor::tei:rdgGrp[@wit][generate-id(ancestor::tei:app[1]) = generate-id($app)][1]/@wit)"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:choose>
      <!-- Ni texte (hors des notes), ni lacune, ni rien qui ait valeur de leçon. -->
      <xsl:when test="not(.//text()[normalize-space()][count(ancestor::tei:note) = count(current()/ancestor::tei:note)])
                      and not(.//tei:gap | .//tei:space | .//tei:app | .//tei:graphic | .//tei:lacunaStart | .//tei:lacunaEnd)">
        <em class="editeur">om.</em><xsl:apply-templates/>
      </xsl:when>
      <xsl:when test="self::tei:lem"><b><xsl:apply-templates/></b></xsl:when>
      <xsl:otherwise><xsl:apply-templates/></xsl:otherwise>
    </xsl:choose>
    <em>
      <xsl:text> (</xsl:text>
      <xsl:choose>
        <xsl:when test="$wit != ''"><xsl:call-template name="sigles"><xsl:with-param name="wit" select="$wit"/></xsl:call-template></xsl:when>
        <xsl:otherwise><xsl:call-template name="texte"><xsl:with-param name="cle" select="'publication.editor_siglum'"/></xsl:call-template></xsl:otherwise>
      </xsl:choose>
      <xsl:text>)</xsl:text>
    </em>
    <xsl:text> </xsl:text>
  </xsl:template>

  <!-- Lacunes : rien dans le texte ; dans une leçon, « lacuna incipit » ou
       « lacuna desinit », avec les témoins de la balise s'ils ne sont pas
       ceux de sa leçon (Varians 0.9.3.4). -->
  <xsl:template match="tei:lacunaStart | tei:lacunaEnd"/>
  <xsl:template match="tei:lacunaStart[ancestor::tei:lem or ancestor::tei:rdg] | tei:lacunaEnd[ancestor::tei:lem or ancestor::tei:rdg]">
    <em class="editeur">
      <xsl:choose>
        <xsl:when test="self::tei:lacunaStart">lacuna incipit</xsl:when>
        <xsl:otherwise>lacuna desinit</xsl:otherwise>
      </xsl:choose>
      <xsl:if test="normalize-space(@wit) != '' and normalize-space(@wit) != normalize-space(ancestor::*[self::tei:lem or self::tei:rdg][1]/@wit)">
        <xsl:text> </xsl:text><xsl:call-template name="sigles"><xsl:with-param name="wit" select="normalize-space(@wit)"/></xsl:call-template>
      </xsl:if>
    </em>
  </xsl:template>
  
  

</xsl:stylesheet>
