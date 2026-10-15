"""Regression: exact OCR/IIIF basename association without positional guessing."""
from pathlib import Path
from dataclasses import dataclass
from iiif_manifest import parse_manifest
from iiif_page_selection import canvas_key, exact_image_stem, propose_exact_ocr_links


@dataclass
class OCR:
    path: Path


def manifest(*filenames):
    return parse_manifest({'sequences': [{'canvases': [
        {'@id': f'https://example.test/canvas/{n}', 'label': filename,
         'images': [{'resource': {'@id': f'https://example.test/full/{filename}.jpg'}}]}
        for n, filename in enumerate(filenames, 1)
    ]}]}, 'https://example.test/manifest.json')


def alto(path: Path, image: str):
    path.write_text(f'<alto><Description><sourceImageInformation><fileName>{image}</fileName>'
                    '</sourceImageInformation></Description><Layout><Page WIDTH="50" HEIGHT="50">'
                    '<TextBlock><TextLine ID="one" HPOS="1" VPOS="1" WIDTH="20" HEIGHT="5"/>'
                    '</TextBlock></Page></Layout></alto>', encoding='utf-8')
    return OCR(path)


def page(path: Path, image: str):
    path.write_text(f'<PcGts><Page imageFilename="{image}" imageWidth="50" imageHeight="50">'
                    '<TextRegion><TextLine id="one"><Coords points="0,0 20,0 20,5 0,5"/>'
                    '</TextLine></TextRegion></Page></PcGts>', encoding='utf-8')
    return OCR(path)


def test_exact_names_find_links_no_manual_steps(tmp_path):
    m = manifest('img_1r', 'img_1v', 'img_10r')
    o1 = alto(tmp_path/'img_10r.xml', 'img_10r.jpg')
    o2 = page(tmp_path/'img_1r.xml', 'img_1r.jpg')
    links, issues = propose_exact_ocr_links(m, [o1, o2])
    assert issues == []
    assert links == {canvas_key(m.pages[2]): str(o1.path), canvas_key(m.pages[0]): str(o2.path)}


def test_embedded_source_image_matches_even_when_ocr_file_renamed(tmp_path):
    m = manifest('folio_alpha', 'folio_beta')
    o = page(tmp_path/'PERO_569812.xml', 'folio_beta.png')
    links, issues = propose_exact_ocr_links(m, [o])
    assert links == {canvas_key(m.pages[1]): str(o.path)} and issues == []


def test_url_query_extensions_and_case_insensitive_stem():
    assert exact_image_stem('https://x.test/iiif/IMG_1R.JPEG?token=aa') == 'img_1r'
    assert exact_image_stem('c:\\images\\IMG_1R.TIF') == 'img_1r'
    assert exact_image_stem('img_1r.xml') == 'img_1r'
    assert exact_image_stem('img_1-r.xml') != exact_image_stem('img_1r.jpg')


def test_repeated_canvas_image_names_are_never_guessed(tmp_path):
    m = manifest('same', 'same')
    o = alto(tmp_path/'same.xml', 'same.jpg')
    assert propose_exact_ocr_links(m, [o])[0] == {}


def test_multiple_ocr_formats_for_same_image_are_ambiguous(tmp_path):
    m = manifest('img_1r')
    a = alto(tmp_path/'img_1r.xml', 'img_1r.jpg')
    b = page(tmp_path/'other.xml', 'img_1r.jpg')
    proposals, issues = propose_exact_ocr_links(m, [a, b])
    assert proposals == {} and len(issues) == 2


def test_existing_manual_link_wins_and_is_not_overwritten(tmp_path):
    m = manifest('img_1r', 'img_1v')
    a = alto(tmp_path/'img_1r.xml', 'img_1r.jpg')
    b = page(tmp_path/'other.xml', 'something_unrelated.jpg')
    manual = [(str(b.path), canvas_key(m.pages[0]))]
    links, issues = propose_exact_ocr_links(m, [a, b], manual)
    assert links == {} and issues == []


def test_conflicting_metadata_and_xml_filename_reject_guess(tmp_path):
    m = manifest('img_1r', 'img_2r')
    a = alto(tmp_path/'img_1r.xml', 'img_2r.jpg')
    links, issues = propose_exact_ocr_links(m, [a])
    assert links == {} and len(issues) == 1


def test_non_identical_folio_or_names_are_not_fuzzy_matched(tmp_path):
    m = manifest('img_1r')
    a = alto(tmp_path/'img-1r.xml', 'f. 1r.jpg')
    links, issues = propose_exact_ocr_links(m, [a])
    assert links == {} and issues == []


def test_pero_style_page_and_alto_can_each_match_image_filename(tmp_path):
    m = manifest('Assisi541-test-1r')
    # Model the PAGE / ALTO metadata conventions of PERO OCR without shipping
    # any manuscript images or OCR produced from user material.
    a = alto(tmp_path/'Assisi541-test-1r.xml', 'Assisi541-test-1r.jpg')
    b = page(tmp_path/'Assisi541-test-1r-PAGE.xml', 'Assisi541-test-1r.jpg')
    for item in (a, b):
        proposals, issues = propose_exact_ocr_links(m, [item])
        assert issues == []
        assert proposals == {canvas_key(m.pages[0]): str(item.path)}
