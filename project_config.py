# -*- coding: utf-8 -*-
"""Chargement du fichier de projet de l'éditeur TEI/manuscrits générique."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


class ProjectConfigError(ValueError):
    """Erreur de project.xml traduisible : ``key`` est une clé des catalogues
    i18n et ``values`` ses paramètres ; l'interface affiche le message dans sa
    langue (``app_context.error_message``). ``str()`` donne le texte français,
    pour les appels sans interface (export en ligne de commande, tests)."""

    def __init__(self, key, default, **values):
        super().__init__(default.format(**values))
        self.key = key
        self.values = values


APPLICATION_ROOT = Path(__file__).resolve().parent
DEFAULT_APPLICATION_XSLT = APPLICATION_ROOT / "rendering" / "tei-to-html.xsl"



@dataclass(frozen=True)
class LocalImageConfig:
    path: Path
    label: str = ""  # folio/page affiché et utilisé dans @n
    width: int | None = None
    height: int | None = None
    surface_id: str = ""  # xml:id stable de tei:surface (V0.7.9)

@dataclass(frozen=True)
class AltoFileConfig:
    path: Path
    label: str = ""

@dataclass(frozen=True)
class WitnessConfig:
    id: str
    label: str
    alignment: Path | None
    role: str = "secondary"
    # ``auto`` = compatibilité historique (images éventuellement décrites
    # dans le JSON d’alignement) ; ``none`` = aucune image, choix explicite.
    image_source_type: str = "auto"
    image_source_value: str | None = None
    image_files: tuple[LocalImageConfig, ...] = ()
    # V0.7.5 : ALTO indépendant de la source d'image et de la synchronisation.
    # ``auto`` conserve les ALTO historiques éventuellement présents dans le
    # JSON d'alignement ; ``files`` charge les XML ALTO déclarés ici.
    alto_source_type: str = "auto"
    alto_files: tuple[AltoFileConfig, ...] = ()
    iiif_local_copy: bool = False
    iiif_web_local_copy: bool = False
    iiif_download_scope: str = "all"  # all | ocr
    iiif_selection_mode: str = "all"
    iiif_selected_canvases: tuple[str, ...] = ()
    iiif_ocr_links: tuple[tuple[str, str], ...] = ()
    iiif_page_links: tuple[tuple[str, str], ...] = ()  # synchronization page ID -> IIIF canvas URI

    @property
    def is_base(self) -> bool:
        return self.role == "base"


@dataclass(frozen=True)
class DocumentConfig:
    """Document XML auxiliaire du projet (fichier d'autorités, notes…), édité
    à côté de l'édition mais sans aperçu ni témoins."""
    path: Path
    label: str = ""
    # Mêmes valeurs que ProjectConfig.schema_mode ; ``schema`` n'est
    # renseigné qu'en mode file.
    schema_mode: str = "auto"
    schema: Path | None = None

    @property
    def display_label(self) -> str:
        return self.label or self.path.name


def has_line_synchronization(witness: WitnessConfig) -> bool:
    """Vrai si une *ressource* JSON de synchronisation explicite existe.

    Attention : depuis V0.8.4, cette fonction ne signifie pas à elle seule que
    le mode ligne est effectivement exploitable. Un JSON peut être vide ou ne
    contenir encore aucun ``base_keys``. La décision finale appartient aux
    fonctions de :mod:`resource_state`, qui examinent le JSON brut avant toute
    superposition ALTO.

    Un ALTO indépendant fournit une structure physique (pages/lignes), mais il
    n'établit aucune correspondance avec les <lb> de l'édition TEI.
    """
    try:
        return bool(witness.alignment and Path(witness.alignment).is_file())
    except OSError:
        return False


@dataclass(frozen=True)
class ProjectConfig:
    path: Path
    title: str
    edition: Path
    xslt: Path
    css: Path
    custom_elements: Path
    web_output_dir: Path
    web_filename: str
    translations_dir: Path
    language: str
    fallback_language: str
    base_witness: str
    witnesses: tuple[WitnessConfig, ...]
    xslt_mode: str = "file"
    # RELAX NG: auto = suivre <?xml-model?>, file = schéma explicitement choisi,
    # none = aucune validation. ``schema`` n'est renseigné qu'en mode file.
    schema_mode: str = "auto"
    schema: Path | None = None
    schema_type: str = "relaxng"
    # Documents XML auxiliaires, dans l'ordre de <documents>. Vide pour un
    # projet qui n'en déclare pas.
    documents: tuple[DocumentConfig, ...] = ()

    @property
    def root_dir(self) -> Path:
        return self.path.parent

    @property
    def witness_by_id(self) -> dict[str, WitnessConfig]:
        return {w.id: w for w in self.witnesses}

    @property
    def base(self) -> WitnessConfig:
        return self.witness_by_id[self.base_witness]


def _resolve(root: Path, value: str | None, default: str) -> Path:
    p = Path(value or default)
    return p if p.is_absolute() else (root / p).resolve()


_SCHEMA_SOURCE_ALIASES = {
    "xml-model": "auto", "xmlmodel": "auto", "auto": "auto",
    "project": "file", "file": "file", "manual": "file",
    "none": "none", "disabled": "none", "off": "none",
}


def _parse_schema(root: ET.Element, root_dir: Path) -> tuple[str, Path | None, str]:
    """Lit la politique de schéma avec rétrocompatibilité V0.5.0.

    Absence de <schema> => mode automatique xml-model, nouveau comportement par
    défaut. Un ancien <schema file="..."> sans @source reste un schéma projet.
    """
    schema_el = root.find("schema")
    if schema_el is None:
        return "auto", None, "relaxng"

    schema_type = (schema_el.get("type") or "relaxng").strip().lower()
    if schema_type not in {"relaxng", "rng"}:
        raise ValueError(f"Type de schéma inconnu : {schema_type!r} (attendu : relaxng)")

    source = (schema_el.get("source") or "").strip().lower()
    raw_schema = (schema_el.get("file") or "").strip()
    if not source:
        # Rétrocompatibilité : un @file ancien signifiait schéma explicite.
        source = "project" if raw_schema else "xml-model"

    mode = _SCHEMA_SOURCE_ALIASES.get(source)
    if mode is None:
        raise ValueError(f"Source de schéma inconnue : {source!r}")

    schema = None
    if mode == "file":
        if not raw_schema:
            raise ValueError("Le mode de schéma projet exige un attribut file=\"…\".")
        schema = _resolve(root_dir, raw_schema, "schema/edition.rng")
    return mode, schema, "relaxng"


def _parse_documents(root: ET.Element, root_dir: Path, edition: Path) -> tuple[DocumentConfig, ...]:
    """Lit <documents><document file label schema schemaFile/></documents>.

    Une entrée sans fichier, un doublon ou l'édition elle-même sont ignorés :
    l'édition reste toujours le document principal. Un fichier absent du
    disque n'empêche pas d'ouvrir le projet.
    """
    documents_el = root.find("documents")
    if documents_el is None:
        return ()
    documents = []
    seen = {edition}
    for document_el in documents_el.findall("document"):
        raw_file = (document_el.get("file") or "").strip()
        if not raw_file:
            continue
        path = _resolve(root_dir, raw_file, raw_file)
        if path in seen:
            continue
        seen.add(path)
        source = (document_el.get("schema") or "auto").strip().lower()
        mode = _SCHEMA_SOURCE_ALIASES.get(source)
        if mode is None:
            raise ValueError(f"Source de schéma inconnue pour {raw_file} : {source!r}")
        schema = None
        if mode == "file":
            raw_schema = (document_el.get("schemaFile") or "").strip()
            if not raw_schema:
                raise ValueError(
                    f"Le document {raw_file} déclare schema=\"file\" sans attribut schemaFile=\"…\".")
            schema = _resolve(root_dir, raw_schema, raw_schema)
        documents.append(DocumentConfig(path, (document_el.get("label") or "").strip(), mode, schema))
    return tuple(documents)


def load_project(path: str | Path) -> ProjectConfig:
    path = Path(path).expanduser().resolve()
    root_dir = path.parent
    root = ET.parse(path).getroot()
    if root.tag not in {"teiManuscriptProject", "project"}:
        raise ValueError("La racine du projet doit être <teiManuscriptProject> ou <project>.")

    title = (root.findtext("title") or path.stem).strip()
    edition_el = root.find("edition")
    rendering_el = root.find("rendering")
    witnesses_el = root.find("witnesses")
    if edition_el is None or witnesses_el is None:
        raise ValueError("Le projet doit contenir <edition> et <witnesses>.")

    raw_edition = (edition_el.get("file") or "").strip()
    if raw_edition:
        edition = _resolve(root_dir, raw_edition, "xml/edition.xml")
    else:
        # Rétrocompatibilité : les projets historiques plaçaient edition.xml à
        # la racine. Si @file est absent, préférer ce fichier lorsqu’il existe ;
        # sinon utiliser la nouvelle architecture xml/edition.xml.
        legacy_edition = (root_dir / "edition.xml").resolve()
        modern_edition = (root_dir / "xml" / "edition.xml").resolve()
        edition = legacy_edition if legacy_edition.exists() else modern_edition

    xslt_mode = ((rendering_el.get("xsltMode") if rendering_el is not None else None) or "file").strip().lower()
    if xslt_mode not in {"builtin", "file"}:
        raise ValueError(f"Mode XSLT inconnu : {xslt_mode!r} (attendu : builtin ou file)")
    xslt = (DEFAULT_APPLICATION_XSLT if xslt_mode == "builtin" else
            _resolve(root_dir, rendering_el.get("xslt") if rendering_el is not None else None,
                     "rendering/tei-to-html.xsl"))
    if xslt_mode == "builtin" and not xslt.is_file():
        raise FileNotFoundError(f"XSLT par défaut de l’application introuvable : {xslt}")
    css = _resolve(root_dir, rendering_el.get("css") if rendering_el is not None else None, "rendering/tei.css")
    custom = _resolve(root_dir, rendering_el.get("customElements") if rendering_el is not None else None, "rendering/custom-elements.xml")

    web_el = root.find("webViewer")
    web_output_dir = _resolve(root_dir, web_el.get("outputDir") if web_el is not None else None, "web_output")
    web_filename = (web_el.get("filename") if web_el is not None else None) or "viewer.html"

    schema_mode, schema, schema_type = _parse_schema(root, root_dir)

    interface_el = root.find("interface")
    translations_dir = _resolve(root_dir, interface_el.get("translationsDir") if interface_el is not None else None, "i18n")
    language = ((interface_el.get("language") if interface_el is not None else None) or "fr").strip()
    fallback_language = ((interface_el.get("fallbackLanguage") if interface_el is not None else None) or "en").strip()

    base_witness = (witnesses_el.get("base") or "").strip()
    witnesses: list[WitnessConfig] = []
    for w in witnesses_el.findall("witness"):
        wid = (w.get("id") or "").strip()
        if not wid:
            raise ValueError("Chaque <witness> doit avoir un @id.")
        label = (w.get("label") or wid).strip()
        raw_alignment = (w.get("alignment") or "").strip()
        if raw_alignment:
            alignment = _resolve(root_dir, raw_alignment, f"alignments/{wid}.json")
        else:
            # V0.7.0 : un témoin peut exister sans ALTO/synchronisation. Pour
            # préserver les très anciens project.xml qui omettaient @alignment
            # tout en utilisant le chemin conventionnel, on l'adopte seulement
            # si le fichier existe réellement.
            conventional = (root_dir / "alignments" / f"{wid}.json").resolve()
            alignment = conventional if conventional.is_file() else None
        role = (w.get("role") or ("base" if wid == base_witness else "secondary")).strip().lower()

        # V0.7.2 : déclaration de la source d’image au niveau du témoin.
        # L’absence de <images> est volontairement interprétée comme ``auto``
        # afin que tous les anciens projets continuent à utiliser leurs images
        # provenant des caches d’alignement.
        images_el = w.find("images")
        if images_el is None:
            image_source_type = "auto"
            image_source_value = None
        else:
            image_source_type = (images_el.get("type") or "none").strip().lower()
            if image_source_type not in {"auto", "none", "files", "iiif"}:
                raise ValueError(
                    f"Type de source d’image inconnu pour {wid}: {image_source_type!r}"
                )
            image_files = []
            if image_source_type == "files":
                raw = (images_el.get("path") or "").strip()
                if raw:
                    image_source_value = str(_resolve(root_dir, raw, raw))
                else:
                    image_source_value = None
                for image_el in images_el.findall("image"):
                    raw_file = (image_el.get("file") or image_el.get("path") or "").strip()
                    if not raw_file:
                        continue
                    try:
                        width = int(image_el.get("width")) if image_el.get("width") else None
                    except ValueError:
                        width = None
                    try:
                        height = int(image_el.get("height")) if image_el.get("height") else None
                    except ValueError:
                        height = None
                    image_files.append(LocalImageConfig(
                        _resolve(root_dir, raw_file, raw_file),
                        (image_el.get("label") or Path(raw_file).stem).strip(),
                        width, height,
                        (image_el.get("surface") or "").strip(),
                    ))
            elif image_source_type == "iiif":
                image_source_value = (images_el.get("manifest") or "").strip() or None
            else:
                image_source_value = None
                image_files = []
        if images_el is None:
            image_files = []
        iiif_local_copy = (images_el is not None and image_source_type == 'iiif'
                           and images_el.get('localCopy', 'false').lower() == 'true')
        iiif_web_local_copy = (images_el is not None and image_source_type == 'iiif'
                               and images_el.get('webLocalCopy', 'false').lower() == 'true')
        iiif_download_scope = ((images_el.get('downloadScope') or 'all').strip().lower()
                               if images_el is not None and image_source_type == 'iiif' else 'all')
        if iiif_download_scope not in {'all', 'ocr'}:
            raise ValueError(f'Invalid IIIF download scope for {wid}: {iiif_download_scope}')
        iiif_selection_mode = (images_el.get('selectionMode') or 'all').strip().lower() if images_el is not None else 'all'
        if iiif_selection_mode not in ('all', 'selected'):
            raise ValueError(f'Invalid IIIF selection mode for {wid}: {iiif_selection_mode}')
        iiif_selected_canvases = tuple((x.get('ref') or '').strip() for x in images_el.findall('canvas') if (x.get('ref') or '').strip()) if images_el is not None else ()
        iiif_ocr_links = tuple((_resolve(root_dir, x.get('file'), x.get('file')), (x.get('canvas') or '').strip()) for x in images_el.findall('ocrLink') if x.get('file') and x.get('canvas')) if images_el is not None else ()
        iiif_page_links = tuple(
            ((x.get('page') or '').strip(), (x.get('canvas') or '').strip())
            for x in images_el.findall('pageLink') if x.get('page') and x.get('canvas')
        ) if images_el is not None else ()
        # V0.7.5 : les fichiers ALTO sont une ressource indépendante.
        alto_el = w.find("alto")
        alto_source_type = "auto"
        alto_files = []
        if alto_el is not None:
            alto_source_type = (alto_el.get("type") or "files").strip().lower()
            if alto_source_type not in {"auto", "files"}:
                raise ValueError(f"Type de source ALTO inconnu pour {wid}: {alto_source_type!r}")
            if alto_source_type == "files":
                for file_el in alto_el.findall("file"):
                    raw_file = (file_el.get("file") or file_el.get("path") or "").strip()
                    if not raw_file:
                        continue
                    alto_files.append(AltoFileConfig(
                        _resolve(root_dir, raw_file, raw_file),
                        (file_el.get("label") or Path(raw_file).stem).strip(),
                    ))

        witnesses.append(WitnessConfig(
            wid, label, alignment, role, image_source_type, image_source_value, tuple(image_files),
            alto_source_type, tuple(alto_files), iiif_local_copy, iiif_web_local_copy, iiif_download_scope,
            iiif_selection_mode, iiif_selected_canvases, iiif_ocr_links, iiif_page_links
        ))

    if not witnesses:
        raise ValueError("Le projet ne contient aucun témoin.")
    explicit_bases = [w.id for w in witnesses if w.is_base]
    if not base_witness:
        if len(explicit_bases) == 1:
            base_witness = explicit_bases[0]
        else:
            raise ValueError("Déclarez le témoin pivot avec <witnesses base=\"…\"> ou role=\"base\".")
    if base_witness not in {w.id for w in witnesses}:
        raise ProjectConfigError(
            "project.error.unknown_pivot",
            "Témoin pivot inconnu : « {witness} » ne figure pas parmi les témoins de project.xml ({witnesses}).",
            witness=base_witness, witnesses=", ".join(w.id for w in witnesses))

    witnesses = [
        WitnessConfig(
            w.id, w.label, w.alignment,
            "base" if w.id == base_witness else "secondary",
            w.image_source_type, w.image_source_value, w.image_files,
            w.alto_source_type, w.alto_files,
            w.iiif_local_copy, w.iiif_web_local_copy, w.iiif_download_scope,
            w.iiif_selection_mode, w.iiif_selected_canvases, w.iiif_ocr_links, w.iiif_page_links,
        )
        for w in witnesses
    ]

    return ProjectConfig(
        path=path,
        title=title,
        edition=edition,
        xslt=xslt,
        css=css,
        custom_elements=custom,
        web_output_dir=web_output_dir,
        web_filename=web_filename,
        translations_dir=translations_dir,
        language=language,
        fallback_language=fallback_language,
        base_witness=base_witness,
        witnesses=tuple(witnesses),
        xslt_mode=xslt_mode,
        schema_mode=schema_mode,
        schema=schema,
        schema_type=schema_type,
        documents=_parse_documents(root, root_dir, edition),
    )


def update_project_language(path: str | Path, language: str) -> None:
    """Persist the selected interface language in project.xml."""
    path = Path(path).expanduser().resolve()
    tree = ET.parse(path)
    root = tree.getroot()
    interface_el = root.find("interface")
    if interface_el is None:
        interface_el = ET.Element("interface")
        insert_at = 2 if len(root) >= 2 else len(root)
        root.insert(insert_at, interface_el)
    interface_el.set("language", language)
    if not interface_el.get("translationsDir"):
        interface_el.set("translationsDir", "i18n")
    if not interface_el.get("fallbackLanguage"):
        interface_el.set("fallbackLanguage", "en")
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
