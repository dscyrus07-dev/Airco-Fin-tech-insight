import importlib.util, os, sys
os.environ["OCR_SERVICE_AUTOSTART"] = "0"
spec = importlib.util.spec_from_file_location("ocr_app", os.path.join(os.path.dirname(__file__), "..", "app.py"))
m = importlib.util.module_from_spec(spec); sys.modules["ocr_app"] = m; spec.loader.exec_module(m)


def test_pages_param():
    assert m.parse_pages_param("1,2", 5) == [1, 2]
    assert m.parse_pages_param("", 3) == [1, 2, 3]
    assert m.parse_pages_param("0,9,x,2,2", 5) == [2]


def test_vl_mapping():
    r = {"res": {"parsing_res_list": [{"block_label": "table", "block_bbox": [1, 2, 3, 4], "block_content": "<table></table>"}]}}
    assert m.blocks_from_vl(r) == [{"label": "table", "bbox": [1.0, 2.0, 3.0, 4.0], "content": "<table></table>"}]
    assert m.blocks_from_vl({}) == []


def test_ocr_lines_drop_unscored_lines():
    r = {"rec_texts": ["a", "b"], "rec_scores": [0.99], "rec_boxes": [[0, 0, 1, 1], [0, 0, 1, 1]]}
    assert m.lines_from_ocr(r) == [{"text": "a", "box": [0.0, 0.0, 1.0, 1.0], "score": 0.99}]


def test_render_pages(tmp_path):
    fitz = __import__("pytest").importorskip("fitz")
    d = fitz.open(); d.new_page(width=200, height=100); p = str(tmp_path / "a.pdf"); d.save(p)
    got = list(m.render_pages(p, [1], dpi=72))
    assert got[0][0] == 1 and got[0][1][:4] == b"\x89PNG"
