# -*- coding: utf-8 -*-
"""Gestion de projet : sérialisation et création de projets portables.

Ce module ne dépend pas de Qt. Il contient uniquement les opérations de fichiers
utilisées par les dialogues de l'éditeur V0.4.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

from project_config import DEFAULT_APPLICATION_XSLT, DocumentConfig



@dataclass
class LocalImageDraft:
    path: Path
    label: str = ""  # folio/page affiché et repris dans tei:pb/@n
    width: int | None = None
    height: int | None = None
    surface_id: str = ""  # xml:id stable de tei:surface (V0.7.9)

@dataclass
class AltoFileDraft:
    path: Path
    label: str = ""

@dataclass
class WitnessDraft:
    id: str
    label: str
    alignment: Path | None = None
    role: str = "secondary"
    # V0.7.2 : la source d’image est déclarée indépendamment de la
    # synchronisation. ``auto`` conserve le comportement historique : les
    # pages/images sont lues dans le JSON d’alignement lorsqu’il existe.
    # ``none`` exprime explicitement qu’aucune image n’est associée pour le
    # moment. Les valeurs ``files`` et ``iiif`` sont réservées aux étapes
    # suivantes et le champ value accueillera alors un dossier ou un Manifest.
    image_source_type: str = "auto"
    image_source_value: str | None = None
    image_files: list[LocalImageDraft] = field(default_factory=list)
    image_import_mode: str = "keep"  # keep | copy | reference
    iiif_manifest_data: dict | None = None  # cache transitoire chargé depuis le dialogue
    # V0.7.5 : ressource ALTO indépendante. ``auto`` conserve les données ALTO
    # historiques incluses dans le JSON de synchronisation ; ``files`` associe
    # une liste ordonnée de fichiers XML ALTO.
    alto_source_type: str = "auto"
    alto_files: list[AltoFileDraft] = field(default_factory=list)
    alto_import_mode: str = "keep"  # keep | copy | reference
    # V0.7.6 : la synchronisation est une ressource facultative importable
    # ultérieurement. Ce mode n'est pas sérialisé ; il pilote seulement la
    # matérialisation du JSON au moment où les paramètres du projet sont sauvés.
    alignment_import_mode: str = "keep"  # keep | copy | reference
    iiif_local_copy: bool = False
    iiif_web_local_copy: bool = False
    iiif_download_scope: str = "all"
    iiif_selection_mode: str = "all"  # all (legacy) | selected
    iiif_selected_canvases: list[str] = field(default_factory=list)
    iiif_ocr_links: list[tuple[str, str]] = field(default_factory=list)  # file, canvas ID
    iiif_page_links: list[tuple[str, str]] = field(default_factory=list)  # sync page ID, canvas ID


@dataclass
class ProjectDraft:
    title: str
    edition: Path
    language: str
    fallback_language: str
    translations_dir: Path
    xslt: Path
    css: Path
    custom_elements: Path
    web_output_dir: Path
    web_filename: str
    witnesses: list[WitnessDraft]
    base_witness: str
    xslt_mode: str = "file"
    schema_mode: str = "auto"
    schema: Path | None = None
    schema_type: str = "relaxng"
    documents: list[DocumentConfig] = field(default_factory=list)
    xpath_queries: list = field(default_factory=list)
    parts: list = field(default_factory=list)
    transformations: list = field(default_factory=list)




TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
DEFAULT_TEI_RNG = "https://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng"


def minimal_tei_text(
    title: str,
    witnesses: list[WitnessDraft],
    base_witness: str,
    *,
    language: str = "fr",
    schema_mode: str = "auto",
) -> str:
    """Construit une édition TEI minimale pour une nouvelle transcription.

    Le document ne suppose aucune image, aucun ALTO ni synchronisation. En mode
    de schéma ``auto``, une instruction ``xml-model`` vers TEI All est ajoutée
    afin que la validation et la complétion RNG soient disponibles dès que le
    schéma distant est accessible (puis via le cache local de Varians).
    """
    ET.register_namespace("", TEI_NS)
    q = lambda name: f"{{{TEI_NS}}}{name}"
    root = ET.Element(q("TEI"))
    tei_header = ET.SubElement(root, q("teiHeader"))
    file_desc = ET.SubElement(tei_header, q("fileDesc"))
    title_stmt = ET.SubElement(file_desc, q("titleStmt"))
    ET.SubElement(title_stmt, q("title")).text = (title or "Nouvelle édition").strip()
    publication = ET.SubElement(file_desc, q("publicationStmt"))
    source_desc = ET.SubElement(file_desc, q("sourceDesc"))

    if (language or "fr").lower().startswith("en"):
        publication_text = "Edition in preparation."
        source_prefix = "Transcription in progress"
    else:
        publication_text = "Édition en préparation."
        source_prefix = "Transcription en cours"
    ET.SubElement(publication, q("p")).text = publication_text

    # Les témoins sont structurés dès la création de l'édition. Cela fournit
    # immédiatement de vraies cibles TEI pour @wit (#A1, #B, etc.), au lieu
    # d'une description textuelle impossible à référencer.
    list_wit = ET.SubElement(source_desc, q("listWit"))
    XML_NS = "http://www.w3.org/XML/1998/namespace"
    for witness in witnesses:
        wid = (witness.id or "").strip()
        if not wid:
            continue
        wel = ET.SubElement(list_wit, q("witness"), {f"{{{XML_NS}}}id": wid})
        wel.text = (witness.label or wid).strip()

    text = ET.SubElement(root, q("text"))
    body = ET.SubElement(text, q("body"))
    ET.SubElement(body, q("p"))
    ET.indent(root, space="  ")
    xml = ET.tostring(root, encoding="unicode", short_empty_elements=False)
    prolog = '<?xml version="1.0" encoding="UTF-8"?>\n'
    if schema_mode == "auto":
        prolog += (
            f'<?xml-model href="{DEFAULT_TEI_RNG}" type="application/xml" '
            'schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
        )
    return prolog + xml + "\n"


def write_minimal_tei(
    path: str | Path,
    title: str,
    witnesses: list[WitnessDraft],
    base_witness: str,
    *,
    language: str = "fr",
    schema_mode: str = "auto",
) -> Path:
    """Écrit le squelette TEI minimal d'une nouvelle transcription."""
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        minimal_tei_text(title, witnesses, base_witness, language=language, schema_mode=schema_mode),
        encoding="utf-8",
        newline="\n",
    )
    return path

def portable_path(project_dir: Path, path: Path) -> str:
    """Retourne un chemin relatif quand *path* se trouve dans le projet."""
    project_dir = project_dir.resolve()
    path = Path(path).expanduser().resolve()
    try:
        return path.relative_to(project_dir).as_posix()
    except ValueError:
        return str(path)


def write_project_xml(path: str | Path, draft: ProjectDraft) -> Path:
    """Écrit un project.xml à partir d'un brouillon validé."""
    path = Path(path).expanduser().resolve()
    root_dir = path.parent
    root = ET.Element("teiManuscriptProject", {"version": "1"})
    ET.SubElement(root, "title").text = draft.title.strip() or path.parent.name
    ET.SubElement(root, "edition", {"file": portable_path(root_dir, draft.edition)})
    if draft.schema_mode not in {"auto", "file", "none"}:
        raise ValueError(f"Mode de schéma inconnu : {draft.schema_mode}")
    schema_attrs = {"type": draft.schema_type or "relaxng"}
    if draft.schema_mode == "auto":
        schema_attrs["source"] = "xml-model"
    elif draft.schema_mode == "none":
        schema_attrs["source"] = "none"
    else:
        if draft.schema is None:
            raise ValueError("Le mode de schéma projet exige un fichier RELAX NG.")
        schema_path = Path(draft.schema).expanduser().resolve()
        schema_attrs["source"] = "project"
        schema_attrs["file"] = portable_path(root_dir, schema_path)
    ET.SubElement(root, "schema", schema_attrs)
    ET.SubElement(root, "interface", {
        "language": draft.language or "fr",
        "translationsDir": portable_path(root_dir, draft.translations_dir),
        "fallbackLanguage": draft.fallback_language or "en",
    })
    if draft.xslt_mode not in {"builtin", "file"}:
        raise ValueError(f"Mode XSLT inconnu : {draft.xslt_mode}")
    rendering_attrs = {
        "xsltMode": draft.xslt_mode,
        "css": portable_path(root_dir, draft.css),
        "customElements": portable_path(root_dir, draft.custom_elements),
    }
    # En mode builtin, ne sérialiser AUCUN chemin vers l'installation :
    # un projet reste transportable d'une machine à une autre.
    if draft.xslt_mode == "file":
        rendering_attrs["xslt"] = portable_path(root_dir, draft.xslt)
    ET.SubElement(root, "rendering", rendering_attrs)
    ET.SubElement(root, "webViewer", {
        "outputDir": portable_path(root_dir, draft.web_output_dir),
        "filename": draft.web_filename or "viewer.html",
    })
    witnesses_el = ET.SubElement(root, "witnesses", {"base": draft.base_witness})
    for w in draft.witnesses:
        attrs = {
            "id": w.id.strip(),
            "label": w.label.strip() or w.id.strip(),
        }
        if w.alignment is not None:
            attrs["alignment"] = portable_path(root_dir, Path(w.alignment))
        if w.id == draft.base_witness:
            attrs["role"] = "base"
        witness_el = ET.SubElement(witnesses_el, "witness", attrs)
        image_type = (getattr(w, "image_source_type", "auto") or "auto").strip().lower()
        image_value = (getattr(w, "image_source_value", None) or "").strip()
        if image_type not in {"auto", "none", "files", "iiif"}:
            raise ValueError(f"Type de source d’image inconnu : {image_type}")
        # L’absence de <images> signifie « auto » pour conserver strictement
        # les anciens project.xml. ``none`` est au contraire sérialisé afin de
        # distinguer un choix explicite de l’utilisateur d’une donnée héritée.
        if image_type != "auto":
            image_attrs = {"type": image_type}
            if image_value:
                if image_type == "files":
                    raw = Path(image_value).expanduser()
                    if raw.is_absolute():
                        image_attrs["path"] = portable_path(root_dir, raw)
                    else:
                        image_attrs["path"] = image_value.replace("\\", "/")
                elif image_type == "iiif":
                    image_attrs["manifest"] = image_value
            if image_type == 'iiif':
                if getattr(w, 'iiif_local_copy', False):
                    image_attrs['localCopy'] = 'true'
                if getattr(w, 'iiif_web_local_copy', False):
                    image_attrs['webLocalCopy'] = 'true'
                scope = getattr(w, 'iiif_download_scope', 'all')
                if scope not in ('all', 'ocr'):
                    raise ValueError(f'Invalid IIIF scope: {scope}')
                if scope == 'ocr':
                    image_attrs['downloadScope'] = 'ocr'
                selection = getattr(w, 'iiif_selection_mode', 'all')
                if selection not in ('all', 'selected'):
                    raise ValueError(f'Invalid IIIF selection mode: {selection}')
                if selection == 'selected':
                    image_attrs['selectionMode'] = 'selected'
            images_el = ET.SubElement(witness_el, "images", image_attrs)
            if image_type == 'iiif' and getattr(w, 'iiif_selection_mode', 'all') == 'selected':
                for canvas in dict.fromkeys(getattr(w, 'iiif_selected_canvases', ())):
                    ET.SubElement(images_el, 'canvas', {'ref': canvas})
                for filename, canvas in getattr(w, 'iiif_ocr_links', ()):
                    f = Path(filename).expanduser()
                    file_value = portable_path(root_dir, f) if f.is_absolute() else str(f).replace('\\', '/')
                    ET.SubElement(images_el, 'ocrLink', {'file': file_value, 'canvas': canvas})
                for page_id, canvas in getattr(w, 'iiif_page_links', ()):
                    ET.SubElement(images_el, 'pageLink', {'page': str(page_id), 'canvas': str(canvas)})
            if image_type == "files":
                for image in getattr(w, "image_files", []) or []:
                    ipath = Path(image.path).expanduser()
                    attrs = {
                        "file": portable_path(root_dir, ipath) if ipath.is_absolute() else str(ipath).replace("\\", "/"),
                        "label": (image.label or ipath.stem),
                    }
                    if image.width:
                        attrs["width"] = str(int(image.width))
                    if image.height:
                        attrs["height"] = str(int(image.height))
                    if getattr(image, "surface_id", ""):
                        attrs["surface"] = str(image.surface_id)
                    ET.SubElement(images_el, "image", attrs)

        # V0.7.5 : la ressource ALTO est sérialisée séparément des images et
        # du fichier de synchronisation. L'absence de <alto> signifie ``auto``
        # pour préserver les projets historiques.
        alto_type = (getattr(w, "alto_source_type", "auto") or "auto").strip().lower()
        if alto_type not in {"auto", "files"}:
            raise ValueError(f"Type de source ALTO inconnu : {alto_type}")
        if alto_type == "files":
            alto_el = ET.SubElement(witness_el, "alto", {"type": "files"})
            for alto in getattr(w, "alto_files", []) or []:
                apath = Path(alto.path).expanduser()
                attrs = {
                    "file": portable_path(root_dir, apath) if apath.is_absolute() else str(apath).replace("\\", "/"),
                    "label": (alto.label or apath.stem),
                }
                ET.SubElement(alto_el, "file", attrs)

    documents_el = documents_element(root_dir, draft.documents)
    if documents_el is not None:
        root.append(documents_el)
    queries_el = xpath_queries_element(draft.xpath_queries)
    if queries_el is not None:
        root.append(queries_el)
    parts_el = parts_element(draft.parts)
    if parts_el is not None:
        root.append(parts_el)
    transformations_el = transformations_element(draft.transformations)
    if transformations_el is not None:
        root.append(transformations_el)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def documents_element(root_dir: Path, documents) -> ET.Element | None:
    """Élément <documents> des documents auxiliaires, ou None s'il n'y en a
    aucun : un projet simple ne reçoit jamais d'élément vide."""
    if not documents:
        return None
    documents_el = ET.Element("documents")
    for document in documents:
        mode = document.schema_mode or "auto"
        if mode not in {"auto", "file", "none"}:
            raise ValueError(f"Mode de schéma inconnu : {mode}")
        attrs = {"file": portable_path(root_dir, Path(document.path))}
        if document.label:
            attrs["label"] = document.label
        if mode != "auto":
            attrs["schema"] = mode
        if mode == "file":
            if document.schema is None:
                raise ValueError("Le mode de schéma projet exige un fichier RELAX NG.")
            attrs["schemaFile"] = portable_path(root_dir, Path(document.schema))
        ET.SubElement(documents_el, "document", attrs)
    return documents_el


def xpath_queries_element(queries) -> ET.Element | None:
    """Élément <xpathQueries> des requêtes nommées, ou None s'il n'y en a
    pas (un projet sans requête reste inchangé)."""
    if not queries:
        return None
    queries_el = ET.Element("xpathQueries")
    for query in queries:
        ET.SubElement(queries_el, "query", {"name": query.name}).text = query.expression
    return queries_el


def parts_element(parts) -> ET.Element | None:
    """Élément <parts> des pivots propres à certains textes, ou None s'il n'y
    en a pas (un projet sans exception reste inchangé)."""
    if not parts:
        return None
    parts_el = ET.Element("parts")
    for part in parts:
        ET.SubElement(parts_el, "part", {"name": part.name, "base": part.base})
    return parts_el


def transformations_element(scenarios) -> ET.Element | None:
    """Élément <transformations> des scénarios XSLT, ou None s'il n'y en a
    pas (un projet sans scénario reste inchangé). Les chemins sont écrits
    tels qu'ils sont gardés dans ``TransformScenario``."""
    if not scenarios:
        return None
    transformations_el = ET.Element("transformations")
    for scenario in scenarios:
        attrs = {"name": scenario.name, "source": scenario.source}
        if scenario.file:
            attrs["file"] = scenario.file
        attrs["engine"] = scenario.engine
        attrs["xslt"] = scenario.xslt
        if scenario.css:
            attrs["css"] = scenario.css
        attrs["output"] = scenario.output
        scenario_el = ET.SubElement(transformations_el, "scenario", attrs)
        for name, value in scenario.params:
            ET.SubElement(scenario_el, "param", {"name": name, "value": value})
    return transformations_el


def update_project_documents(path: str | Path, documents) -> Path:
    """Remplace les documents auxiliaires déclarés dans project.xml sans
    modifier le reste du fichier ; l'ancienne version est copiée en ``.bak``."""
    path = Path(path).expanduser().resolve()
    return _replace_project_element(path, "documents", documents_element(path.parent, documents))


def update_project_xpath_queries(path: str | Path, queries) -> Path:
    """Remplace les requêtes XPath nommées de project.xml, comme
    ``update_project_documents``."""
    return _replace_project_element(Path(path).expanduser().resolve(), "xpathQueries",
                                    xpath_queries_element(queries))


def update_project_transformations(path: str | Path, scenarios) -> Path:
    """Remplace les scénarios de transformation de project.xml, comme
    ``update_project_documents``."""
    return _replace_project_element(Path(path).expanduser().resolve(), "transformations",
                                    transformations_element(scenarios))


def _replace_project_element(path: Path, tag: str, new_el: ET.Element | None) -> Path:
    """Remplace (ou retire, si ``new_el`` est None) l'élément ``tag`` de
    project.xml, à sa place, sans toucher au reste ; copie ``.bak`` préalable."""
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    tree = ET.parse(path, parser)
    root = tree.getroot()
    old_el = root.find(tag)
    if old_el is not None:
        index = list(root).index(old_el)
        root.remove(old_el)
        if new_el is not None:
            root.insert(index, new_el)
    elif new_el is not None:
        root.append(new_el)
    shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path



def _safe_filename(name: str) -> str:
    keep = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", "."}:
            keep.append(ch)
        else:
            keep.append("_")
    out = "".join(keep).strip("._")
    return out or "image"



def prepare_alignment_files_for_project(project_dir: str | Path, witnesses: list[WitnessDraft]) -> list[WitnessDraft]:
    """Matérialise les fichiers de synchronisation déclarés par les témoins.

    ``copy`` copie/remplace le JSON dans ``alignments/<sigle>.json`` afin de
    rendre le projet portable. Si un ancien fichier interne est remplacé, une
    sauvegarde ``.bak`` est conservée. ``reference`` laisse le fichier externe
    en place. ``keep`` conserve exactement la configuration déjà présente.
    L'absence de fichier reste parfaitement valide.
    """
    project_dir = Path(project_dir).expanduser().resolve()
    result = []
    for witness in witnesses:
        src = Path(witness.alignment).expanduser().resolve() if witness.alignment is not None else None
        mode = (getattr(witness, "alignment_import_mode", "keep") or "keep").lower()
        if mode not in {"keep", "copy", "reference"}:
            raise ValueError(f"Mode d’import de synchronisation inconnu : {mode}")
        if src is None:
            result.append(replace(witness, alignment=None, alignment_import_mode="keep"))
            continue
        if not src.is_file():
            raise FileNotFoundError(f"Fichier de synchronisation introuvable : {src}")
        if mode == "copy":
            dest_dir = project_dir / "alignments"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = (dest_dir / f"{_safe_filename(witness.id)}.json").resolve()
            if src != dest:
                if dest.exists():
                    backup = dest.with_suffix(dest.suffix + ".bak")
                    shutil.copy2(dest, backup)
                shutil.copy2(src, dest)
            src = dest
        result.append(replace(witness, alignment=src, alignment_import_mode="keep"))
    return result

def prepare_local_images_for_project(project_dir: str | Path, witnesses: list[WitnessDraft]) -> list[WitnessDraft]:
    """Matérialise les images locales choisies par l'utilisateur.

    ``copy`` copie les fichiers dans ``images/<sigle>/`` en préservant l'ordre
    par un préfixe numérique. ``reference`` conserve les chemins originaux.
    ``keep`` laisse intacte une configuration déjà présente dans le projet.
    Aucun fichier existant n'est supprimé automatiquement.
    """
    project_dir = Path(project_dir).expanduser().resolve()
    result = []
    for witness in witnesses:
        if (getattr(witness, "image_source_type", "auto") or "auto") != "files":
            result.append(witness)
            continue
        mode = (getattr(witness, "image_import_mode", "keep") or "keep").lower()
        images = list(getattr(witness, "image_files", []) or [])
        if mode not in {"keep", "copy", "reference"}:
            raise ValueError(f"Mode d’import d’images inconnu : {mode}")
        if mode != "copy":
            from tei_facsimile import default_surface_id
            normalized = [
                LocalImageDraft(
                    Path(x.path).expanduser().resolve(), x.label, x.width, x.height,
                    getattr(x, "surface_id", "") or default_surface_id(witness.id, i),
                )
                for i, x in enumerate(images, 1)
            ]
            result.append(replace(witness, image_files=normalized, image_source_value=None, image_import_mode="keep"))
            continue
        dest_dir = project_dir / "images" / _safe_filename(witness.id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        from tei_facsimile import default_surface_id
        for index, image in enumerate(images, 1):
            src = Path(image.path).expanduser().resolve()
            if not src.is_file():
                raise FileNotFoundError(f"Image locale introuvable : {src}")
            try:
                src.relative_to(dest_dir.resolve())
                dest = src
            except ValueError:
                base = _safe_filename(src.name)
                dest = dest_dir / f"{index:04d}_{base}"
                if dest.exists() and dest.resolve() != src:
                    stem, suffix = dest.stem, dest.suffix
                    n = 2
                    while dest.exists():
                        dest = dest_dir / f"{stem}_{n}{suffix}"
                        n += 1
                shutil.copy2(src, dest)
            copied.append(LocalImageDraft(
                dest, image.label or src.stem, image.width, image.height,
                getattr(image, "surface_id", "") or default_surface_id(witness.id, index),
            ))
        result.append(replace(witness, image_files=copied, image_source_value=None, image_import_mode="keep"))
    return result



def prepare_alto_files_for_project(project_dir: str | Path, witnesses: list[WitnessDraft]) -> list[WitnessDraft]:
    """Matérialise les fichiers ALTO indépendamment des images/alignements.

    En mode ``copy``, les XML sont copiés dans ``alto/<sigle>/`` ; en mode
    ``reference``, les chemins externes sont conservés. Le cache analysé est
    créé à la demande par :mod:`alto_import` et n'est pas une donnée source.
    """
    project_dir = Path(project_dir).expanduser().resolve()
    result = []
    for witness in witnesses:
        if (getattr(witness, "alto_source_type", "auto") or "auto") != "files":
            result.append(witness)
            continue
        mode = (getattr(witness, "alto_import_mode", "keep") or "keep").lower()
        files = list(getattr(witness, "alto_files", []) or [])
        if mode not in {"keep", "copy", "reference"}:
            raise ValueError(f"Mode d’import ALTO inconnu : {mode}")
        if mode != "copy":
            normalized = []
            for item in files:
                src = Path(item.path).expanduser().resolve()
                if not src.is_file():
                    raise FileNotFoundError(f"Fichier ALTO introuvable : {src}")
                normalized.append(AltoFileDraft(src, item.label or src.stem))
            # Rebase links as well: the editor can declare relative paths.
            link_map = {str(Path(x.path).expanduser().resolve()): str(x.path) for x in files}
            normalized_links = [
                (str(Path(source).expanduser().resolve()), canvas)
                for source, canvas in getattr(witness, 'iiif_ocr_links', ())
            ]
            result.append(replace(witness, alto_files=normalized, alto_import_mode="keep",
                                  iiif_ocr_links=normalized_links))
            continue
        dest_dir = project_dir / "alto" / _safe_filename(witness.id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        for index, item in enumerate(files, 1):
            src = Path(item.path).expanduser().resolve()
            if not src.is_file():
                raise FileNotFoundError(f"Fichier ALTO introuvable : {src}")
            try:
                src.relative_to(dest_dir.resolve())
                dest = src
            except ValueError:
                base = _safe_filename(src.name)
                dest = dest_dir / f"{index:04d}_{base}"
                if dest.exists() and dest.resolve() != src:
                    stem, suffix = dest.stem, dest.suffix
                    n = 2
                    while dest.exists():
                        dest = dest_dir / f"{stem}_{n}{suffix}"
                        n += 1
                shutil.copy2(src, dest)
            copied.append(AltoFileDraft(dest, item.label or src.stem))
        destination_by_source = {
            str(Path(before.path).expanduser().resolve()): str(after.path)
            for before, after in zip(files, copied)
        }
        updated_links = [
            (destination_by_source.get(str(Path(source).expanduser().resolve()), str(source)), canvas)
            for source, canvas in getattr(witness, 'iiif_ocr_links', ())
        ]
        result.append(replace(witness, alto_files=copied, alto_import_mode="keep",
                              iiif_ocr_links=updated_links))
    return result


def prepare_iiif_manifests_for_project(project_dir: str | Path, witnesses: list[WitnessDraft]) -> list[WitnessDraft]:
    """Télécharge/cache les manifests IIIF déclarés par les témoins.

    Le cache brut est conservé dans ``iiif/<sigle>.manifest.json`` afin que
    l'ouverture ultérieure du projet n'ait pas à retélécharger le Manifest.
    """
    from iiif_manifest import cache_path as iiif_cache_path, import_manifest
    project_dir = Path(project_dir).expanduser().resolve()
    result=[]
    for witness in witnesses:
        if (getattr(witness, "image_source_type", "auto") or "auto") != "iiif":
            result.append(witness); continue
        source=(getattr(witness, "image_source_value", None) or "").strip()
        if not source:
            raise ValueError(f"Manifest IIIF manquant pour le témoin {witness.id}.")
        raw=getattr(witness, "iiif_manifest_data", None)
        import_manifest(source, iiif_cache_path(project_dir, witness.id), raw=raw)
        result.append(replace(witness, iiif_manifest_data=None))
    return result

def create_portable_project(
    target_dir: str | Path,
    title: str,
    edition_source: str | Path,
    witnesses: list[WitnessDraft],
    base_witness: str,
    template_root: str | Path,
    language: str = "fr",
    fallback_language: str = "en",
    xslt_mode: str = "builtin",
    schema_source: str | Path | None = None,
    schema_mode: str = "auto",
) -> Path:
    """Crée un projet portable ; la XSLT n'est copiée qu'en mode « file ».

    Le dossier cible doit être absent ou vide. Les ressources de rendu et i18n
    sont copiées depuis l'installation courante. En mode « builtin », le projet
    utilise la XSLT de l'application ; il faut donc l'ouvrir avec le logiciel.
    """
    if xslt_mode not in {"builtin", "file"}:
        raise ValueError(f"Mode XSLT inconnu : {xslt_mode}")
    target_dir = Path(target_dir).expanduser().resolve()
    template_root = Path(template_root).resolve()
    edition_source = Path(edition_source).expanduser().resolve()

    if target_dir.exists() and any(target_dir.iterdir()):
        raise ValueError("TARGET_NOT_EMPTY")
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "xml").mkdir(exist_ok=True)
    (target_dir / "xslt").mkdir(exist_ok=True)                    # feuilles XSLT du projet
    (target_dir / "alignments").mkdir(exist_ok=True)
    (target_dir / "web_output").mkdir(exist_ok=True)

    if schema_mode not in {"auto", "file", "none"}:
        raise ValueError(f"Mode de schéma inconnu : {schema_mode}")
    schema_dest = None
    if schema_mode == "file":
        if not schema_source:
            raise ValueError("Le mode de schéma projet exige un fichier RELAX NG.")
        schema_source = Path(schema_source).expanduser().resolve()
        if not schema_source.is_file():
            raise FileNotFoundError(f"Schéma RELAX NG introuvable : {schema_source}")
        schema_dir = target_dir / "schema"
        schema_dir.mkdir(exist_ok=True)
        schema_dest = schema_dir / "edition.rng"
        shutil.copy2(schema_source, schema_dest)

    edition_dest = target_dir / "xml" / "edition.xml"
    shutil.copy2(edition_source, edition_dest)

    rendering_dest = target_dir / "rendering"
    i18n_dest = target_dir / "i18n"
    rendering_dest.mkdir(parents=True, exist_ok=True)
    for filename in ("tei.css", "custom-elements.xml"):
        shutil.copy2(template_root / "rendering" / filename, rendering_dest / filename)
    if xslt_mode == "file":
        shutil.copy2(template_root / "rendering" / "tei-to-html.xsl", rendering_dest / "tei-to-html.xsl")
    shutil.copytree(template_root / "i18n", i18n_dest, dirs_exist_ok=True)

    # Dans un nouveau projet, le comportement historique est de rendre les
    # synchronisations portables. Un brouillon ancien sans mode explicite
    # (``keep``) est donc traité comme ``copy`` ; ``reference`` reste respecté.
    witnesses = [
        replace(w, alignment_import_mode="copy")
        if w.alignment is not None and (getattr(w, "alignment_import_mode", "keep") or "keep") == "keep"
        else w
        for w in witnesses
    ]
    witnesses = prepare_alignment_files_for_project(target_dir, witnesses)
    witnesses = prepare_local_images_for_project(target_dir, witnesses)
    witnesses = prepare_alto_files_for_project(target_dir, witnesses)
    witnesses = prepare_iiif_manifests_for_project(target_dir, witnesses)
    # IIIF downloads are run by the dedicated non-blocking manager in the UI,
    # after project.xml is written. File-system project creation never calls
    # a remote image server (also safe for headless creation).

    # V0.7.9 : construire la couche TEI page↔image de manière incrémentale.
    # Le moteur ne supprime ni ne remplace jamais un <facsimile> existant.
    from tei_facsimile import project_facsimile_pages, sync_facsimile_file
    facsimile_pages = project_facsimile_pages(witnesses, target_dir, edition_dest)
    if facsimile_pages:
        sync_facsimile_file(edition_dest, facsimile_pages)

    copied_witnesses: list[WitnessDraft] = []
    for witness in witnesses:
        copied_witnesses.append(WitnessDraft(
            witness.id, witness.label, witness.alignment, witness.role,
            getattr(witness, "image_source_type", "auto"),
            getattr(witness, "image_source_value", None),
            list(getattr(witness, "image_files", []) or []),
            "keep", None,
            getattr(witness, "alto_source_type", "auto"),
            list(getattr(witness, "alto_files", []) or []),
            "keep", "keep",
            getattr(witness, 'iiif_local_copy', False),
            getattr(witness, 'iiif_web_local_copy', False),
            getattr(witness, 'iiif_download_scope', 'all'),
            getattr(witness, 'iiif_selection_mode', 'all'),
            list(getattr(witness, 'iiif_selected_canvases', ()) or ()),
            list(getattr(witness, 'iiif_ocr_links', ()) or ()),
            list(getattr(witness, 'iiif_page_links', ()) or ()),
        ))

    draft = ProjectDraft(
        title=title,
        edition=edition_dest,
        language=language,
        fallback_language=fallback_language,
        translations_dir=i18n_dest,
        xslt=rendering_dest / "tei-to-html.xsl",
        css=rendering_dest / "tei.css",
        custom_elements=rendering_dest / "custom-elements.xml",
        web_output_dir=target_dir / "web_output",
        web_filename="viewer.html",
        witnesses=copied_witnesses,
        base_witness=base_witness,
        xslt_mode=xslt_mode,
        schema_mode=schema_mode,
        schema=schema_dest,
        schema_type="relaxng",
    )
    return write_project_xml(target_dir / "project.xml", draft)



def create_new_transcription_project(
    target_dir: str | Path,
    title: str,
    witnesses: list[WitnessDraft],
    base_witness: str,
    template_root: str | Path,
    language: str = "fr",
    fallback_language: str = "en",
    xslt_mode: str = "builtin",
    schema_source: str | Path | None = None,
    schema_mode: str = "auto",
) -> Path:
    """Crée un projet complet sans exiger de fichier TEI préexistant.

    Le squelette TEI est généré dans un fichier temporaire puis passe par le
    même chemin de création que les projets fondés sur une édition existante.
    Cela garantit une arborescence et des ressources strictement identiques.
    """
    if not witnesses:
        raise ValueError("NO_WITNESS")
    if base_witness not in {w.id for w in witnesses}:
        raise ValueError("NO_BASE_WITNESS")
    with tempfile.TemporaryDirectory(prefix="varians-new-transcription-") as td:
        source = Path(td) / "edition.xml"
        write_minimal_tei(
            source, title, witnesses, base_witness,
            language=language, schema_mode=schema_mode,
        )
        return create_portable_project(
            target_dir=target_dir,
            title=title,
            edition_source=source,
            witnesses=witnesses,
            base_witness=base_witness,
            template_root=template_root,
            language=language,
            fallback_language=fallback_language,
            xslt_mode=xslt_mode,
            schema_source=schema_source,
            schema_mode=schema_mode,
        )

def create_local_xslt_if_needed(project_dir: str | Path, draft: ProjectDraft) -> bool:
    """Copie la XSLT livrée uniquement pour une nouvelle personnalisation locale.

    Jamais d'écrasement d'une XSLT existante. Un chemin personnalisé inexistant
    ailleurs que dans rendering/ est considéré comme une erreur utilisateur.
    Renvoie True si une copie a été créée.
    """
    if draft.xslt_mode != "file":
        return False
    project_dir = Path(project_dir).resolve()
    dest = Path(draft.xslt).expanduser().resolve()
    if dest.is_file():
        return False
    if dest.exists():
        raise ValueError(f"Le chemin de la XSLT n'est pas un fichier : {dest}")
    expected = project_dir / "rendering" / "tei-to-html.xsl"
    if dest != expected:
        raise FileNotFoundError(f"XSLT personnalisée introuvable : {dest}")
    if not DEFAULT_APPLICATION_XSLT.is_file():
        raise FileNotFoundError(f"XSLT de l’application introuvable : {DEFAULT_APPLICATION_XSLT}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DEFAULT_APPLICATION_XSLT, dest)
    return True
