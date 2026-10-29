<?xml version="1.0" encoding="UTF-8"?>
<!--
  Édition critique (Varians 0.9.2.7) : une édition TEI en HTML5 autonome,
  d'après la feuille du kit « édition critique TEI », retouchée pour Varians.
  Scénario prédéfini « Édition critique (HTML) » (Saxon, XSLT 3.0).

  - Texte établi : le <lem> prime ; sinon la leçon du témoin
    temoin-de-base (le témoin pivot dans le scénario ; sans valeur, le
    premier <witness> de <listWit>). « aucun » suit les seuls <lem> et
    demande un <lem> dans chaque <app>. Règles communes avec le pré-passage
    des scénarios DOCX et ODT : apparat-commun.xsl.
  - Apparat après chaque division, en deux séries : l'apparat critique,
    appelé par des chiffres, et les notes, moins nombreuses, appelées par
    des lettres (a, b… z, aa…). La leçon précède ses sigles, en italique ; om., add., lacuna
    incipit, lacuna desinit ; les leçons d'un <rdgGrp> comptent.
  - Titre d'une division sans <head> : son @n, sinon rien.
  - Folios : ceux du témoin choisi (et sans @edRef) ; tous avec « aucun ».
  - Vers (<l>, <lg>) et strophes gardent leur structure ; divisions,
    citations, listes, tableaux, répliques et marques de transcription sont
    rendues ; un élément inconnu laisse passer son texte.
  Paramètres : temoin-de-base, montrer-folios, montrer-numeros-de-vers,
  sauts-lb (un saut de ligne du témoin choisi par <br>).
-->
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  xmlns:array="http://www.w3.org/2005/xpath-functions/array"
  xmlns:f="urn:varians:apparat"
  exclude-result-prefixes="#all">

  <xsl:include href="apparat-commun.xsl"/>
  <xsl:output method="html" html-version="5" encoding="UTF-8" indent="yes"/>
  <xsl:mode name="base" on-no-match="shallow-skip"/>
  <xsl:mode name="lecture" on-no-match="shallow-skip"/>
  <xsl:strip-space elements="tei:TEI tei:teiHeader tei:facsimile tei:text
    tei:front tei:body tei:back tei:div tei:div1 tei:div2 tei:div3
    tei:div4 tei:div5 tei:div6 tei:div7 tei:lg tei:list tei:table
    tei:app tei:rdgGrp tei:listWit"/>

  <xsl:param name="montrer-folios" as="xs:boolean" select="true()"/>
  <!-- Dans les vers, les seuls numéros @n encodés. -->
  <xsl:param name="montrer-numeros-de-vers" as="xs:boolean" select="true()"/>
  <!-- Un <lb> est un repère de transcription ; avec sauts-lb, ceux du
       témoin choisi deviennent des sauts de ligne. -->
  <xsl:param name="sauts-lb" as="xs:boolean" select="false()"/>

  <!-- L'unité de l'apparat : la division la plus proche (div, div1…div7),
       à défaut front, body ou back. -->
  <xsl:function name="f:section" as="element()">
    <xsl:param name="n" as="element()"/>
    <xsl:sequence select="$n/ancestor-or-self::*
      [self::tei:div or self::tei:div1 or self::tei:div2 or self::tei:div3
       or self::tei:div4 or self::tei:div5 or self::tei:div6 or self::tei:div7
       or self::tei:front or self::tei:body or self::tei:back][1]"/>
  </xsl:function>

  <!-- La référence d'une citation qui n'est pas biblique (le <ref> d'une
       <cit> sans @type « bible ») est une note de l'éditeur (Varians
       0.9.3.0) ; celle d'une citation biblique suit la citation, entre
       chevrons. -->
  <xsl:function name="f:biblique" as="xs:boolean">
    <xsl:param name="cit" as="element()?"/>
    <xsl:sequence select="tokenize(normalize-space(string($cit/@type)), ' ') = 'bible'"/>
  </xsl:function>
  <xsl:function name="f:ref-en-note" as="xs:boolean">
    <xsl:param name="n" as="element()"/>
    <xsl:sequence select="exists($n/self::tei:ref/parent::tei:cit) and not(f:biblique($n/parent::tei:cit))"/>
  </xsl:function>

  <!-- Les apparats et les notes du texte établi d'une section ; les notes
       comprennent les références en note (f:ref-en-note). -->
  <xsl:function name="f:appels-de-section" as="element()*">
    <xsl:param name="section" as="element()"/>
    <xsl:sequence select="$section/descendant::*[self::tei:app or self::tei:note
                                                 or (self::tei:ref and f:ref-en-note(.))]
      [f:section(.) is $section][f:dans-texte-etabli(.)][not(ancestor::tei:note)]"/>
  </xsl:function>

  <!-- Le repère d'un appel : un chiffre pour l'apparat, une lettre pour une
       note (a… z, aa…). -->
  <xsl:function name="f:repere" as="xs:string">
    <xsl:param name="n" as="element()"/>
    <xsl:variable name="memes" select="f:appels-de-section(f:section($n))
      [if ($n/self::tei:app) then self::tei:app else not(self::tei:app)]"/>
    <xsl:variable name="rang" select="count($memes[. &lt;&lt; $n]) + 1"/>
    <xsl:sequence select="if ($n/self::tei:app) then string($rang) else format-integer($rang, 'a')"/>
  </xsl:function>

  <xsl:function name="f:cle-section" as="xs:string">
    <xsl:param name="section" as="element()"/>
    <xsl:sequence select="if ($section/@xml:id) then string($section/@xml:id)
                          else concat(local-name($section), '-', generate-id($section))"/>
  </xsl:function>

  <xsl:function name="f:ancre" as="xs:string">
    <xsl:param name="n" as="element()"/>
    <xsl:sequence select="concat(f:cle-section(f:section($n)), '-', if ($n/self::tei:app) then '' else 'n', f:repere($n))"/>
  </xsl:function>

  <xsl:template match="/tei:TEI">
    <xsl:call-template name="f:verifier"/>
    <xsl:variable name="titre" select="normalize-space(string((tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title)[1]))"/>
    <html lang="fr">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>Édition critique — <xsl:value-of select="$titre"/></title>
        <style>
          :root {color-scheme:light; --encre:#29251f; --secondaire:#6d675d; --filet:#c3bcaf;}
          * {box-sizing:border-box;}
          html {background:#e9e6df;}
          body {max-width:930px; margin:2rem auto; padding:3.5rem 4rem; background:#fffdf9;
            color:var(--encre); box-shadow:0 4px 26px #0002;
            font:18px/1.58 'EB Garamond',Garamond,'Palatino Linotype',Georgia,serif;}
          h1,h2,h3,h4 {font-weight:normal;}
          h1 {text-align:center; font-variant:small-caps; letter-spacing:.045em; font-size:2rem;}
          .source {text-align:center; font-style:italic; margin-bottom:1.5em;}
          .chapeau {text-align:center; font-size:.91em; color:var(--secondaire);}
          .temoins {margin:2rem 0; padding:1rem 0; border-top:1px solid var(--filet);
            border-bottom:1px solid var(--filet); text-align:center; font-size:.88em;}
          .temoins h2 {font-size:1.1em; font-variant:small-caps;}
          .temoins dl {margin:.45rem auto;}
          .temoins dt {display:inline; font-style:italic;}
          .temoins dd {display:inline; margin-left:.5em;}
          .temoins dd::after {content:''; display:block;}
          .partie, .division {margin:1.7rem 0 2rem;}
          .division {border:0;}
          .division .division {margin:1.5rem 0 1.5rem 1.2rem;}
          .titre-division {text-align:center; line-height:1.28; font-size:1.36rem;
             letter-spacing:.016em; margin:1.55rem 0 1.1rem; break-after:avoid;}
          .titre-partie {text-align:center; font-size:1.48rem; margin:2rem 0 1.2rem;}
          .titre-interne {text-align:center; font-size:1.13rem; margin:1rem 0 .65rem;
             break-after:avoid;}
          .corps-tei p, .corps-tei .paragraphe {text-align:justify; text-indent:1.35em;
             margin:.35rem 0 .75rem; orphans:3; widows:3; hyphens:auto;}
          .corps-tei p:first-child {text-indent:0;}
          .corps-tei .versification {margin:1.3rem 0; text-align:left;}
          .corps-tei .strophe {margin:.8rem 0 1.35rem; padding:0 0 0 2rem;
             break-inside:avoid;}
          .corps-tei .strophe .strophe {margin:.6rem 0 1rem; padding-left:1.3rem;}
          .versification > .vers {margin-left:2rem;}
          .vers {display:block; position:relative; padding:0; margin:0; text-align:left;
             text-indent:0; white-space:pre-wrap; overflow-wrap:break-word;
             hyphens:none; break-inside:avoid; line-height:1.55;}
          .vers-numero {position:absolute; right:calc(100% + .75em); min-width:2.6em;
             color:var(--secondaire); text-align:right; font: .72em/2.2 Georgia,serif;}
          .vers.retrait {padding-left:2em;}
          .vers.centre {text-align:center;}
          .strophe .titre-strophe {text-align:left; font-size:1rem; font-style:italic;
             margin:0 0 .32rem; break-after:avoid;}
          .cesure {display:inline-block; min-width:1.85em;}
          .citation {font-style:normal;}
          blockquote.citation-bloc {margin:1rem 2rem; font-size:.99em;}
          .italique {font-style:italic;}
          .souligne {text-decoration:underline;}
          .gras {font-weight:bold;}
          .rature {text-decoration:line-through;}
          .ajout {text-decoration:underline dotted;}
          .lacune {font-style:italic; color:var(--secondaire);}
          .scripture-ref {color:var(--secondaire); font-size:.85em;}
          .folio, .jalon {color:var(--secondaire); font-size:.73em; font-style:normal;
             margin:0 .25em; white-space:nowrap;}
          .incertain {text-decoration:underline dotted #947c60; text-underline-offset:3px;}
          .sic {font-style:italic;}
          .liste-tei {padding-left:2.1em; margin:1rem 0;}
          .liste-tei li {margin:.15rem 0;}
          .tableau-tei {width:100%; border-collapse:collapse; margin:1rem 0; font-size:.9em;}
          .tableau-tei td, .tableau-tei th {border-bottom:1px solid var(--filet); padding:.4em .6em; vertical-align:top; text-align:left;}
          .tableau-tei tr:first-child td, .tableau-tei tr:first-child th {border-top:1px solid var(--filet);}
          .tableau-tei th {font-weight:600;}
          .tableau-tei caption {font-weight:600; text-align:left; padding-bottom:.3em;}
          .discours {margin:1rem 0 1rem 1em;}
          .locuteur {font-variant:small-caps; letter-spacing:.035em; margin-right:.55em;}
          .didascalie {font-style:italic; color:var(--secondaire);}
          .illustration {text-align:center; margin:1.2rem auto;}
          .illustration img {max-width:100%; height:auto;}
          .illustration figcaption {font-size:.8em; color:var(--secondaire);}
          sup.appel {font:normal .59em/0 Georgia,serif; vertical-align:super; margin-left:.09em;}
          sup.appel a {text-decoration:none; color:inherit;}
          .appareil {border-top:1px solid var(--filet); margin:1.7rem 0 2.2rem;
             padding-top:.65rem; font-size:.82rem; line-height:1.42;}
          .appareil h3 {text-align:left; font-variant:small-caps; letter-spacing:.04em;
             font-size:1rem; margin:0 0 .45rem;}
          .appareil ol {list-style:none; padding:0; margin:0;}
          .appareil ol + h3 {margin-top:.85rem;}
          .appareil li {display:grid; grid-template-columns:2.2em minmax(0, 1fr); column-gap:.45em;
             margin:.14rem 0; overflow-wrap:anywhere; break-inside:avoid;}
          .repere {font-weight:bold; text-align:right;}
          .temoin {font-variant:normal; font-style:italic; font-weight:normal;}
          .separateur {color:var(--secondaire); margin:0 .2em;}
          .commentaire {font-style:italic; color:var(--secondaire);}
          .retour {text-decoration:none; font-size:.8em; margin-left:.4em;}
          .groupe-vers-variant {display:inline-block; vertical-align:top; margin:0 .2em;}
          .vers-variant {display:block; white-space:normal;}
          .mention {font-size:.8rem; color:var(--secondaire); text-align:center; margin-top:3rem;}
          @page {size:A4; margin:22mm 24mm;}
          @media print {
            html {background:white;} body {max-width:none; margin:0; padding:0; box-shadow:none;
              font-size:11.5pt; line-height:1.4;}
            .division {break-before:auto;}
            .appareil {break-before:avoid;}
            .strophe,.vers,.appareil li {break-inside:avoid;}
          }
          @media (max-width:650px) {
            body {margin:0; padding:1.3rem 1rem; font-size:16px; box-shadow:none;}
            .strophe {padding-left:1.2rem;} .versification > .vers {margin-left:1.2rem;}
            .vers-numero {right:calc(100% + .2em);}
          }
        </style>
      </head>
      <body>
        <header>
          <h1>Édition critique</h1>
          <p class="source"><xsl:value-of select="$titre"/></p>
          <p class="chapeau">
            <xsl:choose>
              <xsl:when test="$f:sans-temoin">Texte établi à partir des lemmes explicites, sans témoin choisi.</xsl:when>
              <xsl:otherwise>Leçon explicite prioritaire, sinon lecture du témoin <i class="temoin"><xsl:value-of
                select="if ($f:temoin ne '') then f:sigle($f:temoin) else 'non défini'"/></i>.</xsl:otherwise>
            </xsl:choose>
            Les variantes rejetées figurent dans l'apparat.</p>
        </header>
        <xsl:if test="tei:teiHeader//tei:listWit/tei:witness">
          <section class="temoins"><h2>Sigles des témoins</h2><dl>
            <xsl:for-each select="tei:teiHeader//tei:listWit//tei:witness">
              <div><dt><xsl:value-of select="f:sigle(string(@xml:id))"/></dt>
                <dd><xsl:value-of select="normalize-space(string-join(
                  descendant::text()[empty(ancestor::tei:idno[@type = 'siglum'])], ''))"/></dd></div>
            </xsl:for-each>
          </dl></section>
        </xsl:if>
        <main class="corps-tei">
          <xsl:if test="tei:text/@xml:lang">
            <xsl:attribute name="lang" select="tei:text/@xml:lang"/>
          </xsl:if>
          <xsl:apply-templates select="tei:text/tei:front | tei:text/tei:body | tei:text/tei:back" mode="base"/>
        </main>
        <footer class="mention">Édition produite à partir d'un document TEI · Apparat par division</footer>
      </body>
    </html>
  </xsl:template>

  <!-- Les parties contiennent parfois directement des vers, paragraphes ou notes. -->
  <xsl:template match="tei:front | tei:body | tei:back" mode="base">
    <section class="partie" id="{f:cle-section(.)}">
      <xsl:if test="self::tei:front or self::tei:back">
        <h2 class="titre-partie"><xsl:value-of select="if (self::tei:front) then 'Préliminaires' else 'Annexes'"/></h2>
      </xsl:if>
      <xsl:apply-templates mode="base"/>
      <xsl:call-template name="imprimer-apparat">
        <xsl:with-param name="section" select="."/>
      </xsl:call-template>
    </section>
  </xsl:template>

  <xsl:template match="tei:div | tei:div1 | tei:div2 | tei:div3 |
                       tei:div4 | tei:div5 | tei:div6 | tei:div7" mode="base">
    <section class="division" id="{f:cle-section(.)}">
      <xsl:if test="@xml:lang"><xsl:attribute name="lang" select="@xml:lang"/></xsl:if>
      <xsl:choose>
        <xsl:when test="tei:head">
          <h2 class="titre-division"><xsl:apply-templates select="tei:head[1]/node()" mode="base"/></h2>
        </xsl:when>
        <!-- Ni @xml:id ni @type : des identifiants, pas des titres. -->
        <xsl:when test="normalize-space(@n) != ''">
          <h2 class="titre-division"><xsl:value-of select="@n"/></h2>
        </xsl:when>
      </xsl:choose>
      <xsl:apply-templates select="node()[not(self::tei:head[1])]" mode="base"/>
      <xsl:call-template name="imprimer-apparat">
        <xsl:with-param name="section" select="."/>
      </xsl:call-template>
    </section>
  </xsl:template>

  <xsl:template match="tei:head[parent::tei:front or parent::tei:body or parent::tei:back]" mode="base">
    <h2 class="titre-partie"><xsl:apply-templates mode="base"/></h2>
  </xsl:template>
  <xsl:template match="tei:head[parent::tei:lg]" mode="base">
    <h3 class="titre-strophe"><xsl:apply-templates mode="base"/></h3>
  </xsl:template>
  <xsl:template match="tei:head" mode="base">
    <h3 class="titre-interne"><xsl:apply-templates mode="base"/></h3>
  </xsl:template>

  <xsl:template match="tei:p | tei:ab" mode="base">
    <p>
      <xsl:if test="@xml:id"><xsl:attribute name="id" select="@xml:id"/></xsl:if>
      <xsl:if test="@xml:lang"><xsl:attribute name="lang" select="@xml:lang"/></xsl:if>
      <xsl:apply-templates mode="base"/>
    </p>
  </xsl:template>

  <!-- Vers : chaque l est un bloc ; chaque lg un groupe ou une strophe.
       Un lb de transcription ne fait pas un vers. -->
  <xsl:template match="tei:lg" mode="base">
    <div class="strophe">
      <xsl:if test="@xml:id"><xsl:attribute name="id" select="@xml:id"/></xsl:if>
      <xsl:if test="@xml:lang"><xsl:attribute name="lang" select="@xml:lang"/></xsl:if>
      <xsl:apply-templates mode="base"/>
    </div>
  </xsl:template>
  <xsl:template match="tei:l" mode="base">
    <div>
      <xsl:attribute name="class" select="concat('vers',
        if (matches(string(@rend), '(^|\s)(indent|retrait)(\s|$)', 'i')) then ' retrait' else '',
        if (matches(string(@rend), '(^|\s)(centre|center)(\s|$)', 'i')) then ' centre' else '')"/>
      <xsl:if test="@xml:id"><xsl:attribute name="id" select="@xml:id"/></xsl:if>
      <xsl:if test="@xml:lang"><xsl:attribute name="lang" select="@xml:lang"/></xsl:if>
      <xsl:if test="$montrer-numeros-de-vers and @n">
        <span class="vers-numero"><xsl:value-of select="@n"/></span>
      </xsl:if>
      <xsl:apply-templates mode="base"/>
    </div>
  </xsl:template>

  <xsl:template match="tei:caesura" mode="base">
    <span class="cesure" aria-label="Césure">&#x2003;</span>
  </xsl:template>

  <xsl:template match="tei:app" mode="base">
    <xsl:variable name="retenue" select="f:choix(.)" as="element()?"/>
    <xsl:choose>
      <xsl:when test="exists($retenue)">
        <xsl:apply-templates select="$retenue/node()" mode="base"/>
      </xsl:when>
      <xsl:otherwise><span class="incertain"><xsl:value-of select="$f:non-disponible"/></span></xsl:otherwise>
    </xsl:choose>
    <xsl:call-template name="appel-de-note"/>
  </xsl:template>

  <xsl:template match="tei:note" mode="base">
    <xsl:call-template name="appel-de-note"/>
  </xsl:template>

  <xsl:template name="appel-de-note">
    <xsl:variable name="ancre" select="f:ancre(.)"/>
    <xsl:variable name="repere" select="f:repere(.)"/>
    <sup class="appel {if (self::tei:app) then 'appel-apparat' else 'appel-note'}"><a id="ref-{$ancre}"
      href="#note-{$ancre}" aria-label="{if (self::tei:app) then 'Apparat' else 'Note'} {$repere}"><xsl:value-of
      select="$repere"/></a></sup>
  </xsl:template>

  <xsl:template name="imprimer-apparat">
    <xsl:param name="section" as="element()" required="yes"/>
    <xsl:variable name="appels" select="f:appels-de-section($section)"/>
    <xsl:if test="exists($appels)">
      <aside class="appareil" aria-label="Apparat critique et notes">
        <xsl:if test="$appels[self::tei:app]">
          <h3>Apparat critique</h3>
          <ol class="apparat">
            <xsl:for-each select="$appels[self::tei:app]">
              <xsl:call-template name="entree"/>
            </xsl:for-each>
          </ol>
        </xsl:if>
        <xsl:if test="$appels[not(self::tei:app)]">
          <h3>Notes</h3>
          <ol class="notes">
            <xsl:for-each select="$appels[not(self::tei:app)]">
              <xsl:call-template name="entree"/>
            </xsl:for-each>
          </ol>
        </xsl:if>
      </aside>
    </xsl:if>
  </xsl:template>

  <xsl:template name="entree">
    <xsl:variable name="ancre" select="f:ancre(.)"/>
    <li id="note-{$ancre}">
      <span class="repere"><xsl:value-of select="f:repere(.)"/></span>
      <span class="entree">
        <xsl:choose>
          <xsl:when test="self::tei:app">
            <xsl:variable name="apparat" select="f:apparat(.)"/>
            <xsl:if test="$apparat?lemme">
              <span class="lecon-retenue">
                <xsl:choose>
                  <xsl:when test="exists($apparat?retenue)"><xsl:apply-templates select="$apparat?retenue/node()" mode="lecture"/></xsl:when>
                  <xsl:otherwise><xsl:value-of select="$f:non-disponible"/></xsl:otherwise>
                </xsl:choose>
              </span>
              <xsl:if test="array:size($apparat?variantes) gt 0"><xsl:text> ] </xsl:text></xsl:if>
            </xsl:if>
            <xsl:for-each select="$apparat?variantes?*">
              <xsl:if test="position() gt 1"><span class="separateur"> ; </span></xsl:if>
              <span class="variantes">
                <xsl:choose>
                  <xsl:when test="?genre = 'om'"><xsl:value-of select="$f:om"/><xsl:apply-templates select="?lecon//tei:note" mode="lecture"/></xsl:when>
                  <xsl:otherwise><xsl:apply-templates select="?lecon/node()" mode="lecture"/></xsl:otherwise>
                </xsl:choose>
              </span>
              <xsl:if test="?genre = 'add'"><xsl:text> </xsl:text><xsl:value-of select="$f:add"/></xsl:if>
              <xsl:text> </xsl:text>
              <i class="temoin"><xsl:value-of select="?sigles"/></i>
            </xsl:for-each>
          </xsl:when>
          <xsl:when test="self::tei:ref and @target">
            <span class="note-editoriale"><a href="{string(@target)}"><xsl:apply-templates mode="lecture"/></a></span>
          </xsl:when>
          <xsl:otherwise>
            <span class="note-editoriale"><xsl:apply-templates mode="lecture"/></span>
          </xsl:otherwise>
        </xsl:choose>
        <a class="retour" href="#ref-{$ancre}" aria-label="Retour au texte">↩</a>
      </span>
    </li>
  </xsl:template>

  <!-- Rendu commun. Un élément TEI inconnu laisse passer son contenu :
       le document reste lisible et ne perd pas silencieusement son texte. -->
  <xsl:template match="tei:*" mode="base lecture" priority="-10">
    <xsl:apply-templates mode="#current"/>
  </xsl:template>
  <xsl:template match="text()" mode="base lecture">
    <xsl:value-of select="f:texte-net(.)"/>
  </xsl:template>
  <xsl:template match="tei:lem | tei:rdg | tei:rdgGrp | tei:cit | tei:seg | tei:anchor" mode="base lecture">
    <xsl:apply-templates mode="#current"/>
  </xsl:template>
  <xsl:template match="tei:quote | tei:q | tei:said" mode="base">
    <xsl:choose>
      <xsl:when test="tei:p or tei:lg or tei:l or tei:sp">
        <blockquote class="citation-bloc"><xsl:apply-templates mode="base"/></blockquote>
      </xsl:when>
      <xsl:otherwise><span class="citation"><xsl:apply-templates mode="base"/></span></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="tei:quote | tei:q | tei:said" mode="lecture">
    <span class="citation"><xsl:apply-templates mode="lecture"/></span>
  </xsl:template>
  <xsl:template match="tei:hi | tei:emph" mode="base lecture">
    <xsl:variable name="r" select="lower-case(string-join((@rend,@style), ' '))"/>
    <xsl:choose>
      <xsl:when test="matches($r, 'italic|italique') or self::tei:emph">
        <i class="italique"><xsl:apply-templates mode="#current"/></i>
      </xsl:when>
      <xsl:when test="matches($r, 'bold|gras')">
        <b class="gras"><xsl:apply-templates mode="#current"/></b>
      </xsl:when>
      <xsl:when test="matches($r, 'underline|souligne')">
        <span class="souligne"><xsl:apply-templates mode="#current"/></span>
      </xsl:when>
      <xsl:otherwise><xsl:apply-templates mode="#current"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="tei:title | tei:foreign" mode="base lecture">
    <i class="italique"><xsl:apply-templates mode="#current"/></i>
  </xsl:template>
  <xsl:template match="tei:ref" mode="base lecture">
    <xsl:variable name="biblique" select="exists(parent::tei:cit) and f:biblique(parent::tei:cit)"/>
    <xsl:if test="$biblique"><xsl:text> </xsl:text></xsl:if>
    <span class="scripture-ref">
      <xsl:if test="$biblique">&lt;</xsl:if>
      <xsl:choose>
        <xsl:when test="@target">
          <a href="{string(@target)}"><xsl:apply-templates mode="#current"/></a>
        </xsl:when>
        <xsl:otherwise><xsl:apply-templates mode="#current"/></xsl:otherwise>
      </xsl:choose>
      <xsl:if test="$biblique">&gt;</xsl:if>
    </span>
  </xsl:template>
  <!-- Dans le texte établi, la référence d'une citation non biblique est
       une note : son appel seulement. -->
  <xsl:template match="tei:ref[f:ref-en-note(.)]" mode="base" priority="1">
    <xsl:call-template name="appel-de-note"/>
  </xsl:template>
  <xsl:template match="tei:ptr" mode="base lecture">
    <xsl:if test="@target"><a href="{string(@target)}">[référence]</a></xsl:if>
  </xsl:template>
  <xsl:template match="tei:unclear" mode="base lecture">
    <span class="incertain" title="Lecture incertaine"><xsl:apply-templates mode="#current"/></span>
  </xsl:template>
  <xsl:template match="tei:sic" mode="base lecture">
    <span class="sic" title="Leçon transmise (sic)"><xsl:apply-templates mode="#current"/></span>
  </xsl:template>
  <xsl:template match="tei:choice" mode="base lecture">
    <xsl:apply-templates select="(tei:corr,tei:reg,tei:expan,tei:sic,tei:orig,tei:abbr,*[1])[1]" mode="#current"/>
  </xsl:template>
  <xsl:template match="tei:supplied" mode="base lecture">
    <span class="incertain">[<xsl:apply-templates mode="#current"/>]</span>
  </xsl:template>
  <xsl:template match="tei:gap" mode="base lecture">
    <span class="lacune">[lacune<xsl:if test="@extent"> : <xsl:value-of select="@extent"/></xsl:if>]</span>
  </xsl:template>
  <xsl:template match="tei:add" mode="base lecture">
    <span class="ajout"><xsl:apply-templates mode="#current"/></span>
  </xsl:template>
  <xsl:template match="tei:del | tei:surplus" mode="base lecture">
    <span class="rature"><xsl:apply-templates mode="#current"/></span>
  </xsl:template>
  <xsl:template match="tei:space" mode="base lecture"><xsl:text> </xsl:text></xsl:template>
  <xsl:template match="tei:caesura" mode="lecture"><xsl:text> | </xsl:text></xsl:template>
  <xsl:template match="tei:lg" mode="lecture">
    <span class="groupe-vers-variant"><xsl:apply-templates mode="lecture"/></span>
  </xsl:template>
  <xsl:template match="tei:l" mode="lecture">
    <span class="vers-variant"><xsl:apply-templates mode="lecture"/></span>
  </xsl:template>
  <xsl:template match="tei:head | tei:p | tei:ab" mode="lecture">
    <span><xsl:apply-templates mode="lecture"/></span>
  </xsl:template>
  <!-- Liste (Varians 0.9.2.9) : numérotée si @rend contient « numbered »
       ou si @type vaut « ordered » ou « numbered », comme dans la feuille de
       l'aperçu ; son <head> est placé avant elle, hors de la liste HTML. -->
  <xsl:template match="tei:list" mode="base">
    <xsl:apply-templates select="tei:head" mode="base"/>
    <xsl:choose>
      <xsl:when test="@type = ('ordered', 'numbered') or tokenize(string(@rend)) = 'numbered'">
        <ol class="liste-tei"><xsl:apply-templates select="node() except tei:head" mode="base"/></ol>
      </xsl:when>
      <xsl:otherwise>
        <ul class="liste-tei"><xsl:apply-templates select="node() except tei:head" mode="base"/></ul>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="tei:item" mode="base">
    <li><xsl:apply-templates mode="base"/></li>
  </xsl:template>
  <xsl:template match="tei:label" mode="base"><strong><xsl:apply-templates mode="base"/></strong></xsl:template>
  <!-- Tableau (Varians 0.9.3.0) : son <head> en légende ; une cellule
       @role="label", ou d'une ligne @role="label", en en-tête ; @cols et
       @rows fusionnent les cellules. -->
  <xsl:template match="tei:table" mode="base">
    <table class="tableau-tei">
      <xsl:if test="tei:head"><caption><xsl:apply-templates select="tei:head[1]/node()" mode="base"/></caption></xsl:if>
      <tbody><xsl:apply-templates select="node() except tei:head" mode="base"/></tbody>
    </table>
  </xsl:template>
  <xsl:template match="tei:row" mode="base"><tr><xsl:apply-templates mode="base"/></tr></xsl:template>
  <xsl:template match="tei:cell" mode="base">
    <xsl:element name="{if ((@role, ../@role)[1] = 'label') then 'th' else 'td'}">
      <xsl:if test="number(@cols) gt 1"><xsl:attribute name="colspan" select="normalize-space(@cols)"/></xsl:if>
      <xsl:if test="number(@rows) gt 1"><xsl:attribute name="rowspan" select="normalize-space(@rows)"/></xsl:if>
      <xsl:apply-templates mode="base"/>
    </xsl:element>
  </xsl:template>
  <xsl:template match="tei:sp" mode="base"><div class="discours"><xsl:apply-templates mode="base"/></div></xsl:template>
  <xsl:template match="tei:speaker" mode="base"><span class="locuteur"><xsl:apply-templates mode="base"/></span></xsl:template>
  <xsl:template match="tei:stage" mode="base"><span class="didascalie">(<xsl:apply-templates mode="base"/>)</span></xsl:template>
  <xsl:template match="tei:figure" mode="base">
    <figure class="illustration"><xsl:apply-templates mode="base"/>
      <xsl:if test="tei:figDesc"><figcaption><xsl:apply-templates select="tei:figDesc/node()" mode="base"/></figcaption></xsl:if>
    </figure>
  </xsl:template>
  <xsl:template match="tei:figDesc" mode="base"/>
  <xsl:template match="tei:graphic[parent::tei:figure]" mode="base">
    <img src="{string(@url)}" alt="{normalize-space(string(../tei:figDesc))}"/>
  </xsl:template>

  <!-- Sauts de ligne : une coupure par groupe de <lb> contigus (voir
       apparat-commun.xsl) ; avec sauts-lb, celle du témoin choisi est un
       saut de ligne. -->
  <xsl:template match="tei:lb" mode="base">
    <xsl:variable name="groupe" select="f:lb-groupe(.)"/>
    <xsl:choose>
      <xsl:when test="not(. is $groupe[1]) or $groupe/@break = 'no'"/>
      <xsl:when test="$sauts-lb and exists($groupe[f:folio-montre(.)])"><br class="saut-ligne-manuscrit"/></xsl:when>
      <xsl:otherwise><xsl:text> </xsl:text></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="tei:lb" mode="lecture">
    <xsl:if test="f:lb-espace(.)"><xsl:text> </xsl:text></xsl:if>
  </xsl:template>
  <xsl:template match="tei:pb" mode="base">
    <xsl:if test="$montrer-folios and f:folio-montre(.)">
      <span class="folio" title="Changement de folio ou de page"><xsl:value-of select="f:folio(.)"/></span>
    </xsl:if>
  </xsl:template>
  <xsl:template match="tei:pb" mode="lecture"/>
  <xsl:template match="tei:milestone" mode="base">
    <span class="jalon">⟨<xsl:value-of select="@unit"/><xsl:if test="@n"> <xsl:value-of select="@n"/></xsl:if>⟩</span>
  </xsl:template>
  <xsl:template match="tei:milestone" mode="lecture"/>

  <!-- Lacunes : rien dans le texte établi ; dans l'apparat, « lacuna
       incipit » ou « lacuna desinit », avec les témoins de la balise s'ils
       ne sont pas ceux de sa leçon. -->
  <xsl:template match="tei:lacunaStart | tei:lacunaEnd" mode="base"/>
  <xsl:template match="tei:lacunaStart | tei:lacunaEnd" mode="lecture">
    <xsl:value-of select="if (self::tei:lacunaStart) then $f:lacuna-incipit else $f:lacuna-desinit"/>
    <xsl:if test="f:sigles-lacune(.) != ''"><xsl:text> </xsl:text><xsl:value-of select="f:sigles-lacune(.)"/></xsl:if>
  </xsl:template>

  <xsl:template match="tei:app" mode="lecture">
    <xsl:variable name="retenue" select="f:choix(.)"/>
    <xsl:choose>
      <xsl:when test="exists($retenue)"><xsl:apply-templates select="$retenue/node()" mode="lecture"/></xsl:when>
      <xsl:otherwise><xsl:value-of select="$f:non-disponible"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  <xsl:template match="tei:note" mode="lecture">
    <span class="commentaire"> (<xsl:apply-templates mode="lecture"/>)</span>
  </xsl:template>

</xsl:stylesheet>
