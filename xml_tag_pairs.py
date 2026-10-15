# -*- coding: utf-8 -*-
"""Outils lexicaux conservateurs pour les paires de balises XML.

Le module ne dépend pas de Qt. Il travaille directement sur le texte de
l'éditeur afin de rester utilisable lorsque le document est momentanément non
bien formé pendant une frappe. Il ignore commentaires, CDATA, instructions de
traitement et déclarations, respecte les guillemets dans les attributs, et
apparie les éléments selon leur imbrication XML.

V0.8.0 : moteur commun utilisé pour la surbrillance des paires, la suppression
couplée d'une enveloppe et le renommage synchronisé du QName ouvrant/fermant.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_QNAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]*")


@dataclass(frozen=True)
class XmlTagToken:
    start: int
    end: int                 # exclusif, inclut le > dans la tranche
    name: str
    name_start: int
    name_end: int            # exclusif
    kind: str                # open | close | self

    @property
    def is_opening(self) -> bool:
        return self.kind == "open"

    @property
    def is_closing(self) -> bool:
        return self.kind == "close"

    @property
    def is_self_closing(self) -> bool:
        return self.kind == "self"


@dataclass(frozen=True)
class XmlTagPair:
    opening: XmlTagToken
    closing: XmlTagToken


@dataclass(frozen=True)
class RenameMirror:
    """Patch à appliquer au nom de la balise fermante.

    Les offsets sont calculés dans *new_text*, c.-à-d. après l'édition du nom
    ouvrant mais avant l'application du miroir.
    """
    start: int
    end: int
    old_name: str
    new_name: str


def _find_markup_end(text: str, start: int) -> int:
    """Retourne l'offset exclusif du markup commençant à ``start``.

    Pour les balises ordinaires, les ``>`` placés dans une valeur d'attribut
    sont ignorés. Pour les déclarations ``<!...>`` on tient aussi compte d'un
    éventuel sous-ensemble interne DOCTYPE entre crochets.
    """
    n = len(text)
    if text.startswith("<!--", start):
        stop = text.find("-->", start + 4)
        return n if stop < 0 else stop + 3
    if text.startswith("<![CDATA[", start):
        stop = text.find("]]>", start + 9)
        return n if stop < 0 else stop + 3
    if text.startswith("<?", start):
        stop = text.find("?>", start + 2)
        return n if stop < 0 else stop + 2

    quote = None
    bracket_depth = 0
    i = start + 1
    declaration = text.startswith("<!", start)
    while i < n:
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif declaration and ch == "[":
            bracket_depth += 1
        elif declaration and ch == "]" and bracket_depth:
            bracket_depth -= 1
        elif ch == ">" and bracket_depth == 0:
            return i + 1
        i += 1
    return n


def scan_xml_tags(xml_text: str) -> list[XmlTagToken]:
    """Extrait les balises d'éléments lexicalement reconnaissables.

    Les zones de commentaire, CDATA, PI et déclaration sont sautées. Les balises
    incomplètes ou dont le QName n'est pas reconnaissable ne sont pas émises.
    """
    text = str(xml_text or "")
    n = len(text)
    result: list[XmlTagToken] = []
    i = 0
    while i < n:
        start = text.find("<", i)
        if start < 0:
            break
        end = _find_markup_end(text, start)
        if text.startswith(("<!--", "<![CDATA[", "<?", "<!"), start):
            i = max(end, start + 1)
            continue

        p = start + 1
        kind = "open"
        if p < n and text[p] == "/":
            kind = "close"
            p += 1
        m = _QNAME_RE.match(text, p)
        if not m:
            i = max(end, start + 1)
            continue
        name_start, name_end = m.span()
        name = m.group(0)

        if end <= start or end > n or text[end - 1:end] != ">":
            # markup encore incomplet pendant une frappe : ne pas prétendre
            # connaître sa structure.
            i = max(end, start + 1)
            continue

        if kind == "open":
            before_gt = text[start:end - 1].rstrip()
            if before_gt.endswith("/"):
                kind = "self"
        result.append(XmlTagToken(start, end, name, name_start, name_end, kind))
        i = max(end, start + 1)
    return result



def _inside_special_markup(text: str, position: int) -> bool:
    """Détecte rapidement commentaire/CDATA/PI autour d'un offset candidat."""
    pos = max(0, min(len(text), int(position)))
    if text.rfind("<!--", 0, pos + 1) > text.rfind("-->", 0, pos + 1):
        return True
    if text.rfind("<![CDATA[", 0, pos + 1) > text.rfind("]]>", 0, pos + 1):
        return True
    if text.rfind("<?", 0, pos + 1) > text.rfind("?>", 0, pos + 1):
        return True
    return False


def _parse_element_tag_at(text: str, start: int) -> XmlTagToken | None:
    """Parse une seule balise d'élément commençant exactement à ``start``."""
    n = len(text)
    if start < 0 or start >= n or text[start] != "<":
        return None
    if text.startswith(("<!--", "<![CDATA[", "<?", "<!"), start):
        return None
    if _inside_special_markup(text, start):
        return None
    end = _find_markup_end(text, start)
    if end <= start or end > n or text[end - 1:end] != ">":
        return None
    p = start + 1
    kind = "open"
    if p < n and text[p] == "/":
        kind = "close"
        p += 1
    m = _QNAME_RE.match(text, p)
    if not m:
        return None
    if kind == "open" and text[start:end - 1].rstrip().endswith("/"):
        kind = "self"
    return XmlTagToken(start, end, m.group(0), m.start(), m.end(), kind)


def _opening_near_position(text: str, position: int) -> XmlTagToken | None:
    """Trouve localement la balise ouvrante susceptible de contenir position."""
    pos = max(0, min(len(text), int(position)))
    lt = text.rfind("<", 0, min(len(text), pos + 1))
    if lt < 0:
        return None
    token = _parse_element_tag_at(text, lt)
    return token if token is not None and token.kind == "open" else None


def matching_closing_tag(xml_text: str, opening: XmlTagToken) -> XmlTagToken | None:
    """Cherche la fermeture structurale d'une ouverture sans rescanner le préfixe.

    Une pile complète de QNames garantit le bon résultat pour les éléments
    imbriqués de même nom. Un mismatch rencontré pendant l'édition rend la paire
    indéterminée plutôt que de provoquer une association spéculative.
    """
    text = str(xml_text or "")
    stack = [opening.name]
    i = opening.end
    n = len(text)
    while i < n:
        start = text.find("<", i)
        if start < 0:
            return None
        end = _find_markup_end(text, start)
        token = _parse_element_tag_at(text, start)
        i = max(end, start + 1)
        if token is None or token.kind == "self":
            continue
        if token.kind == "open":
            stack.append(token.name)
            continue
        # Fermeture : elle doit fermer le sommet de pile dans un XML structurel.
        if not stack or stack[-1] != token.name:
            return None
        stack.pop()
        if not stack:
            return token
    return None


def tag_pairs(xml_text: str) -> list[XmlTagPair]:
    """Apparie les balises bien imbriquées, y compris de même nom.

    En présence d'un croisement/mismatch temporaire, aucune paire spéculative
    n'est fabriquée : seules les fermetures correspondant au sommet de pile sont
    acceptées.
    """
    stack: list[XmlTagToken] = []
    pairs: list[XmlTagPair] = []
    for token in scan_xml_tags(xml_text):
        if token.kind == "open":
            stack.append(token)
        elif token.kind == "close":
            if stack and stack[-1].name == token.name:
                pairs.append(XmlTagPair(stack.pop(), token))
            # Mismatch : garder la pile intacte. Le texte peut être en cours de
            # frappe ; mieux vaut n'associer rien que la mauvaise fermeture.
    return pairs


def _selection_bounds(selection_start: int | None, selection_end: int | None) -> tuple[int, int] | None:
    if selection_start is None or selection_end is None:
        return None
    a, b = int(selection_start), int(selection_end)
    if b < a:
        a, b = b, a
    return a, b


def opening_pair_at_context(
    xml_text: str,
    cursor_position: int,
    selection_start: int | None = None,
    selection_end: int | None = None,
) -> XmlTagPair | None:
    """Paire dont la balise ouvrante contient le curseur/la sélection.

    La recherche de l'ouverture est locale ; seule sa fermeture est ensuite
    parcourue vers l'avant. Les positions exactement avant ``<`` ou après ``>``
    sont considérées hors de la balise.
    """
    text = str(xml_text or "")
    pos = max(0, min(len(text), int(cursor_position)))
    selection = _selection_bounds(selection_start, selection_end)
    probe = selection[0] if selection and selection[0] != selection[1] else pos
    opening = _opening_near_position(text, probe)
    if opening is None:
        return None
    if selection and selection[0] != selection[1]:
        a, b = selection
        if not (opening.start <= a and b <= opening.end and not (b <= opening.start or a >= opening.end)):
            return None
    elif not (opening.start < pos < opening.end):
        return None
    closing = matching_closing_tag(text, opening)
    return XmlTagPair(opening, closing) if closing is not None else None


def closing_pair_at_context(
    xml_text: str,
    cursor_position: int,
    selection_start: int | None = None,
    selection_end: int | None = None,
) -> XmlTagPair | None:
    """Retourne une paire sûre lorsque le curseur est dans la *fermeture*.

    Contrairement au cas ouvrant, il faut parcourir le préfixe XML pour
    identifier l'ouverture associée à la fermeture sélectionnée. Le parcours
    utilise une pile stricte : la première fermeture orpheline ou croisée
    invalide le résultat (pas de surlignage spéculatif en cours de saisie).
    Les balises autofermantes ne modifient jamais la pile.

    Les offsets sont ceux du texte XML original, sans transformation du document.
    """
    text = str(xml_text or "")
    pos = max(0, min(len(text), int(cursor_position)))
    selection = _selection_bounds(selection_start, selection_end)
    probe = selection[0] if selection and selection[0] != selection[1] else pos
    lt = text.rfind("<", 0, min(len(text), probe + 1))
    if lt < 0:
        return None
    closing = _parse_element_tag_at(text, lt)
    if closing is None or closing.kind != "close":
        return None
    if selection and selection[0] != selection[1]:
        a, b = selection
        if not (closing.start <= a and b <= closing.end and a < b):
            return None
    elif not (closing.start < pos < closing.end):
        return None

    stack: list[XmlTagToken] = []
    # Ne parcourir que le préfixe : une balise non terminée plus loin dans le
    # document ne rend pas la paire actuelle indéterminée.
    for token in scan_xml_tags(text[:closing.end]):
        if token.kind == "self":
            continue
        if token.kind == "open":
            stack.append(token)
            continue
        if not stack or stack[-1].name != token.name:
            # Un </x> orphelin ou un croisement interdit tout jumelage sûr.
            return None
        opening = stack.pop()
        if token.start == closing.start and token.end == closing.end:
            return XmlTagPair(opening, token)
    return None


def pair_at_context(
    xml_text: str,
    cursor_position: int,
    selection_start: int | None = None,
    selection_end: int | None = None,
) -> XmlTagPair | None:
    """Paire sûre dans les deux sens, destinée au seul surlignage visuel.

    Les automatismes de renommage, suppression couplée et repliage continuent
    d'employer leurs routines spécifiques, sans changement de comportement.
    """
    return opening_pair_at_context(
        xml_text, cursor_position, selection_start, selection_end
    ) or closing_pair_at_context(
        xml_text, cursor_position, selection_start, selection_end
    )


def exact_selected_opening_pair(xml_text: str, selection_start: int, selection_end: int) -> XmlTagPair | None:
    """Retourne la paire si la sélection est exactement la balise ouvrante."""
    text = str(xml_text or "")
    bounds = _selection_bounds(selection_start, selection_end)
    if not bounds:
        return None
    a, b = bounds
    if a == b or a < 0 or b > len(text) or text[a:a + 1] != "<":
        return None
    opening = _parse_element_tag_at(text, a)
    if opening is None or opening.kind != "open" or opening.end != b:
        return None
    closing = matching_closing_tag(text, opening)
    return XmlTagPair(opening, closing) if closing is not None else None



def opening_tag_at(xml_text: str, start: int) -> XmlTagToken | None:
    """Retourne une balise ouvrante ordinaire commençant exactement à start."""
    token = _parse_element_tag_at(str(xml_text or ""), int(start))
    return token if token is not None and token.kind == "open" else None

def single_change_span(old_text: str, new_text: str) -> tuple[int, int, int, int] | None:
    """Calcule la différence minimale contiguë old/new.

    Retour : ``(old_start, old_end, new_start, new_end)``. Cette représentation
    suffit pour une frappe, un collage ou le remplacement d'une sélection.
    """
    old = str(old_text or "")
    new = str(new_text or "")
    if old == new:
        return None
    prefix = 0
    limit = min(len(old), len(new))
    while prefix < limit and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    max_suffix = min(len(old) - prefix, len(new) - prefix)
    while suffix < max_suffix and old[len(old) - 1 - suffix] == new[len(new) - 1 - suffix]:
        suffix += 1
    old_end = len(old) - suffix
    new_end = len(new) - suffix
    return prefix, old_end, prefix, new_end


def opening_pair_for_name_change(
    xml_text: str,
    position: int,
    chars_removed: int = 0,
) -> XmlTagPair | None:
    """Retourne la paire si la zone modifiée est contenue dans le QName ouvrant."""
    text = str(xml_text or "")
    start = max(0, min(len(text), int(position)))
    end = max(start, min(len(text), start + max(0, int(chars_removed))))
    opening = _opening_near_position(text, start)
    if opening is None:
        return None
    ns, ne = opening.name_start, opening.name_end
    if start == end:
        touches = ns <= start <= ne
    else:
        touches = ns <= start and end <= ne
    if not touches:
        return None
    closing = matching_closing_tag(text, opening)
    return XmlTagPair(opening, closing) if closing is not None else None


def closing_rename_mirror_for_change(
    old_text: str,
    new_text: str,
    position: int,
    chars_removed: int,
    chars_added: int,
) -> RenameMirror | None:
    """Version efficace fondée sur le signal QTextDocument.contentsChange."""
    old = str(old_text or "")
    new = str(new_text or "")
    old_start = max(0, min(len(old), int(position)))
    old_end = max(old_start, min(len(old), old_start + max(0, int(chars_removed))))
    new_start = max(0, min(len(new), int(position)))
    new_end = max(new_start, min(len(new), new_start + max(0, int(chars_added))))

    pair = opening_pair_for_name_change(old, old_start, old_end - old_start)
    if pair is None:
        return None
    opening = pair.opening
    closing = pair.closing

    new_open = _parse_element_tag_at(new, opening.start)
    if new_open is None or new_open.kind != "open" or not _QNAME_RE.fullmatch(new_open.name):
        return None
    if new_open.name == opening.name:
        return None
    if not (new_open.name_start <= new_start <= new_open.name_end and new_end <= new_open.name_end):
        return None

    delta = len(new) - len(old)
    close_start = closing.name_start + delta
    close_end = closing.name_end + delta
    if not (0 <= close_start <= close_end <= len(new)):
        return None
    if new[close_start:close_end] != closing.name:
        return None
    return RenameMirror(close_start, close_end, closing.name, new_open.name)


def closing_rename_mirror(old_text: str, new_text: str) -> RenameMirror | None:
    """Détecte un renommage à partir d'une différence minimale old/new.

    Cette enveloppe reste utile hors Qt et pour les tests ; l'éditeur utilise la
    variante ``closing_rename_mirror_for_change`` afin d'éviter un diff O(n) à
    chaque frappe.
    """
    diff = single_change_span(old_text, new_text)
    if diff is None:
        return None
    old_start, old_end, new_start, new_end = diff
    return closing_rename_mirror_for_change(
        old_text, new_text, old_start, old_end - old_start, new_end - new_start
    )


def apply_rename_mirror(text: str, mirror: RenameMirror | None) -> str:
    if mirror is None:
        return str(text or "")
    src = str(text or "")
    return src[:mirror.start] + mirror.new_name + src[mirror.end:]


@dataclass(frozen=True)
class ClosingTagSuggestion:
    """Fermeture structurelle proposée pendant la saisie de ``</...``.

    ``replace_start`` débute juste après ``</`` ; ``replace_end`` est le
    curseur. Le QName proposé est celui de l'ouverture non fermée la plus
    profonde, sans dépendre d'un schéma externe.
    """
    name: str
    replace_start: int
    replace_end: int
    typed_prefix: str

    @property
    def label(self) -> str:
        return f"{self.name}>"


def closing_tag_suggestion(xml_text: str, cursor_position: int) -> ClosingTagSuggestion | None:
    """Suggère le plus proche élément non fermé avant ``</`` ou ``</nom``.

    Parcours lexical du *seul préfixe* précédant la balise en cours. Ignore
    CDATA, commentaires, PI, DOCTYPE et les chevrons dans les attributs ;
    respecte les éléments autofermants et les QNames préfixés. En cas de
    fermeture croisée, d'ouverture/attribut incomplet ou de syntaxe douteuse,
    aucune fermeture spéculative n'est proposée.
    """
    text = str(xml_text or "")
    pos = int(cursor_position)
    if not 0 <= pos <= len(text):
        return None
    m = re.search(r"</([A-Za-z_][A-Za-z0-9_.:-]*)?$", text[:pos])
    if m is None:
        return None
    start = m.start()
    typed = m.group(1) or ""
    prefix = text[:start]
    stack: list[str] = []
    i = 0
    n = len(prefix)
    while i < n:
        tag_start = prefix.find("<", i)
        if tag_start < 0:
            break
        end = _find_markup_end(prefix, tag_start)
        chunk = prefix[tag_start:end]
        if prefix.startswith("<!--", tag_start):
            if not chunk.endswith("-->"):
                return None
        elif prefix.startswith("<![CDATA[", tag_start):
            if not chunk.endswith("]]>"):
                return None
        elif prefix.startswith("<?", tag_start):
            if not chunk.endswith("?>"):
                return None
        elif prefix.startswith("<!", tag_start):
            if not chunk.endswith(">"):
                return None
        else:
            if not chunk.endswith(">"):
                return None
            name_at = tag_start + 1
            is_close = name_at < n and prefix[name_at] == "/"
            if is_close:
                name_at += 1
            qname = _QNAME_RE.match(prefix, name_at)
            if qname is None:
                return None
            # Ne pas confondre un QName avec le préfixe d'un nom malformé.
            if qname.end() < end - 1 and not (
                prefix[qname.end()].isspace() or prefix[qname.end()] in "/ >"
            ):
                return None
            name = qname.group(0)
            if is_close:
                if not stack or stack[-1] != name:
                    return None
                stack.pop()
            elif not chunk[:-1].rstrip().endswith("/"):
                stack.append(name)
        i = max(end, tag_start + 1)
    if not stack:
        return None
    name = stack[-1]
    if typed and not name.startswith(typed):
        return None
    return ClosingTagSuggestion(name, start + 2, pos, typed)


def complete_closing_tag(xml_text: str, cursor_position: int) -> tuple[str, int] | None:
    """Calcule la complétion et la position finale du curseur, sans Qt.

    Évite d'ajouter deux ``>`` lorsque l'utilisateur en avait déjà saisi un.
    """
    text = str(xml_text or "")
    suggestion = closing_tag_suggestion(text, cursor_position)
    if suggestion is None:
        return None
    end = suggestion.replace_end
    suffix = "" if text[end:end + 1] == ">" else ">"
    insertion = suggestion.name + suffix
    result = text[:suggestion.replace_start] + insertion + text[end:]
    return result, suggestion.replace_start + len(insertion) + (0 if suffix else 1)
