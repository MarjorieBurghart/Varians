# -*- coding: utf-8 -*-
"""Retrouver une sélection d'une vue à l'autre (V0.9.4.5), sans Qt.

Le passage de la source XML à l'aperçu XSLT / CSS (et à l'éditeur de
fragment), et retour, ne peut pas se fier aux positions : la feuille XSLT
change tout. Il se fie au texte visible, réduit à ses caractères sans
blancs (une feuille ajoute ou retire des espaces et des sauts de ligne) :

* ``xml_compact`` lit le texte visible d'un XML : balises retirées, quelles
  qu'elles soient (``<lb/>``, ``<hi>``, ``<persName>``…), entités décodées,
  commentaires, instructions de traitement et DOCTYPE écartés, contenu des
  sections CDATA gardé ; chaque caractère garde sa place dans le XML.
  ``plain_compact`` fait de même pour le texte de l'aperçu (sans les
  crayons ✎ ni les WORD JOINER des repères de ligne).
* ``quote`` décrit une sélection par sa citation exacte et son contexte,
  comme une annotation du web (TextQuoteSelector : exact, prefix, suffix),
  plus sa place relative dans le document.
* ``resolve`` cherche la citation dans l'autre texte et choisit, parmi ses
  occurrences, celle dont l'entourage ressemble le plus au contexte de
  départ ; un indice de position (élément modifiable, repère de ligne,
  place relative) ne sert qu'à départager. Il ne compte pas les
  occurrences : une feuille qui ajoute, retire ou déplace du texte (notes
  en fin de page, ``<choice>``, numéros) ne le trompe pas.
"""
from __future__ import annotations

import heapq
import html
import re
from bisect import bisect_left
from dataclasses import dataclass

CONTEXT = 32             # caractères visibles (sans blancs) gardés de part et d'autre
_MANY = 400              # au-delà, un premier tri grossier ne garde que les plus prometteurs
_KEPT = 200
_SLACK = 16              # l'entourage cherché déborde le contexte : texte ajouté par la feuille
_GRAM = 3

# Un seul passage : chaque mot de texte, ou ce qui n'en est pas (balise,
# commentaire…) ; les blancs, jamais pris, sont sautés.
_XML_TOKEN = re.compile(
    r"(?P<word>[^<&\s]+)"
    r"|<!--.*?(?:-->|\Z)"                              # commentaire
    r"|<\?.*?(?:\?>|\Z)"                              # instruction de traitement
    r"|<!\[CDATA\[(?P<cdata>.*?)(?:\]\]>|\Z)"         # section CDATA : son contenu est du texte
    r"|<!DOCTYPE(?:[^\[>]|\[.*?\])*>?"                # DOCTYPE, sous-ensemble interne compris
    r"|<[^>]*>?"                                       # balise
    r"|(?P<entity>&(?:#[0-9]+|#[xX][0-9A-Fa-f]+|[A-Za-z_][\w.\-]*);)"
    r"|(?P<amp>&)",                                    # « & » isolé (XML mal formé) : du texte
    re.DOTALL,
)
_WORD = re.compile(r"\S+")
_PLAIN_WORD = re.compile(r"[^\s\u2060\u270e\ufffc]+")


class CompactText:
    """Texte visible sans blancs (``text``) et, pour chaque caractère, sa
    place dans le texte d'origine : il y commence en ``starts[i]`` et finit
    en ``starts[i] + 1``, sauf une entité (``&amp;``), qui couvre toute sa
    référence."""

    __slots__ = ("text", "starts", "_ends")

    def __init__(self, text, starts, ends=None):
        self.text = text
        self.starts = starts
        self._ends = ends or {}

    def __len__(self):
        return len(self.text)

    def end_of(self, index):
        """Fin, dans le texte d'origine, du caractère ``index``."""
        return self._ends.get(index, self.starts[index] + 1)

    def span(self, i, j):
        """Plage du texte d'origine qui va du caractère ``i`` à la fin du
        caractère ``j - 1`` (balises intermédiaires comprises)."""
        if j <= i:
            position = self.starts[i] if i < len(self.starts) else (self.end_of(i - 1) if i else 0)
            return position, position
        return self.starts[i], self.end_of(j - 1)

    def range_of(self, start, end):
        """Caractères visibles ``(i, j)`` qui commencent entre ``start`` et
        ``end`` dans le texte d'origine."""
        return bisect_left(self.starts, int(start)), bisect_left(self.starts, int(end))

    def index_at(self, position):
        """Premier caractère visible qui commence à ``position`` ou après."""
        return bisect_left(self.starts, int(position))


def xml_compact(xml_text):
    """Texte visible d'un XML (voir le module), sans blancs."""
    pieces, starts, ends = [], [], {}
    append, extend = pieces.append, starts.extend
    for token in _XML_TOKEN.finditer(xml_text):
        kind = token.lastgroup
        if kind == "word" or kind == "amp":
            append(token.group())
            extend(range(token.start(), token.end()))
        elif kind == "entity":
            decoded = html.unescape(token.group())
            if decoded == token.group():                      # entité inconnue : ignorée
                continue
            for char in decoded:
                if not char.isspace():
                    ends[len(starts)] = token.end()
                    append(char)
                    starts.append(token.start())
        elif kind == "cdata":
            base = token.start("cdata")
            for word in _WORD.finditer(token.group("cdata")):
                append(word.group())
                extend(range(base + word.start(), base + word.end()))
    return CompactText("".join(pieces), starts, ends)


def plain_compact(text):
    """Texte de l'aperçu sans blancs, sans crayons ✎, sans WORD JOINER des
    repères de ligne ni caractère d'objet (image)."""
    pieces, starts = [], []
    append, extend = pieces.append, starts.extend
    for word in _PLAIN_WORD.finditer(text):
        append(word.group())
        extend(range(word.start(), word.end()))
    return CompactText("".join(pieces), starts)


@dataclass(frozen=True)
class Quote:
    """Une sélection décrite par son texte : ``exact`` (sans blancs), le
    contexte qui la précède (``prefix``) et qui la suit (``suffix``), et sa
    place relative dans le document (``ratio``, de 0 à 1)."""
    exact: str
    prefix: str
    suffix: str
    ratio: float


def quote(compact, i, j, context=CONTEXT):
    """Citation des caractères ``i`` à ``j`` de ``compact`` ; None si elle est
    vide."""
    i, j = max(0, int(i)), min(len(compact), int(j))
    if j <= i:
        return None
    text = compact.text
    return Quote(text[i:j], text[max(0, i - context):i], text[j:j + context], i / max(1, len(text)))


def _common_suffix(a, b):
    """Longueur de la fin commune de ``a`` et ``b`` (comparaisons de
    tranches, par dichotomie)."""
    if not a or not b or a[-1] != b[-1]:
        return 0
    if a == b:
        return len(a)
    low, high = 0, min(len(a), len(b))
    while low < high:
        middle = (low + high + 1) // 2
        if a[len(a) - middle:] == b[len(b) - middle:]:
            low = middle
        else:
            high = middle - 1
    return low


def _common_prefix(a, b):
    """Longueur du début commun de ``a`` et ``b``."""
    if not a or not b or a[0] != b[0]:
        return 0
    if a == b:
        return len(a)
    low, high = 0, min(len(a), len(b))
    while low < high:
        middle = (low + high + 1) // 2
        if a[:middle] == b[:middle]:
            low = middle
        else:
            high = middle - 1
    return low


def _grams(text):
    return {text[k:k + _GRAM] for k in range(len(text) - _GRAM + 1)}


def _weighted_grams(text, context, before):
    """Trigrammes du contexte ``text``, chacun pesant d'autant plus qu'il
    est près de la sélection (``before`` : le contexte la précède)."""
    weights = {}
    for k in range(len(text) - _GRAM + 1):
        distance = len(text) - _GRAM - k if before else k
        weight = (context + 1 - distance) / (context + 1)
        gram = text[k:k + _GRAM]
        if weight > weights.get(gram, 0):
            weights[gram] = weight
    return weights


def resolve(compact, wanted, scope=None, hint=None):
    """Caractères ``(i, j)`` de ``compact`` où se trouve la citation
    ``wanted`` ; None si son texte n'y est pas.

    ``scope`` : ``(i, j)`` où chercher (un élément modifiable) ; ``hint`` :
    caractère près duquel la sélection devrait être (repère de ligne, place
    dans l'élément), qui départage des entourages qui se valent ; sans lui,
    la place relative de la citation.

    L'entourage est comparé par ses trigrammes, chacun pesant d'autant plus
    qu'il est près de la sélection : un texte que la feuille ajoute contre
    elle (« [ » d'un apparat, appel de note, numéro) n'en retire que
    quelques-uns, au lieu d'arrêter une comparaison caractère par
    caractère ; l'accord exact au plus près ne fait que s'y ajouter."""
    if wanted is None or not wanted.exact:
        return None
    text, exact = compact.text, wanted.exact
    size, context = len(exact), max(len(wanted.prefix), len(wanted.suffix), 1)
    low, high = (0, len(text)) if scope is None else (max(0, scope[0]), min(len(text), scope[1]))
    candidates = []
    found = text.find(exact, low)
    while found != -1 and found + size <= high:
        candidates.append(found)
        found = text.find(exact, found + 1)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0], candidates[0] + size
    target = hint if hint is not None else wanted.ratio * len(text)
    reach = context + _SLACK

    def before(at):
        return text[max(0, at - reach):at]

    def after(at):
        return text[at + size:at + size + reach]

    if len(candidates) > _MANY:
        # Tri grossier, en C : morceaux de 4 caractères du contexte présents
        # dans l'entourage.
        pieces_before = [wanted.prefix[k:k + 4] for k in range(max(0, len(wanted.prefix) - 4), -1, -4)][:8]
        pieces_after = [wanted.suffix[k:k + 4] for k in range(0, max(0, len(wanted.suffix) - 3), 4)][:8]

        def rough(at):
            near_before, near_after = before(at), after(at)
            return (sum(piece in near_before for piece in pieces_before)
                    + sum(piece in near_after for piece in pieces_after))

        candidates = heapq.nlargest(_KEPT, candidates, key=lambda at: (rough(at), -abs(at - target)))
    prefix_grams = _weighted_grams(wanted.prefix, context, before=True)
    suffix_grams = _weighted_grams(wanted.suffix, context, before=False)

    def score(at):
        near_before, near_after = _grams(before(at)), _grams(after(at))
        shared = (sum(weight for gram, weight in prefix_grams.items() if gram in near_before)
                  + sum(weight for gram, weight in suffix_grams.items() if gram in near_after))
        close = (_common_suffix(wanted.prefix, text[max(0, at - context):at])
                 + _common_prefix(wanted.suffix, text[at + size:at + size + context]))
        return shared + close / 4

    best = max(candidates, key=lambda at: (score(at), -abs(at - target)))
    return best, best + size
