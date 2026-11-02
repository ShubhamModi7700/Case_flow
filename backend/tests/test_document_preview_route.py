from io import BytesIO
from docx import Document
from openpyxl import Workbook
from app.routes.documents import _preview_html


def test_word_preview_escapes_document_content():
    doc = Document()
    doc.add_paragraph('<script>alert("x")</script>')
    buffer = BytesIO()
    doc.save(buffer)
    output = _preview_html("test.docx", buffer.getvalue())
    assert "&lt;script&gt;" in output
    assert "<script>" not in output


def test_excel_preview_escapes_cells():
    book = Workbook()
    book.active["A1"] = "<unsafe>"
    buffer = BytesIO()
    book.save(buffer)
    output = _preview_html("test.xlsx", buffer.getvalue())
    assert "&lt;unsafe&gt;" in output
    assert "<unsafe>" not in output
