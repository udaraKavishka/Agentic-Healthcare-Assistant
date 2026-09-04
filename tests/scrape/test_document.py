from pathlib import Path

from pypdf import PdfWriter

from assistant.scrape.document import pdf_title, pdf_to_markdown


def _pdf(tmp_path: Path, title: str | None = None) -> Path:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if title:
        writer.add_metadata({"/Title": title})

    path = tmp_path / "policy.pdf"
    writer.write(path)
    return path


def test_the_documents_own_title_is_preferred(tmp_path: Path):
    path = _pdf(tmp_path, title="Policy on Whistleblowing")

    assert pdf_title(path, "https://host/x.pdf") == "Policy on Whistleblowing"


def test_a_missing_title_falls_back_to_the_file_name(tmp_path: Path):
    path = _pdf(tmp_path)
    url = "https://www.nawaloka.com/Board-Remuneration-Policy.pdf"

    assert pdf_title(path, url) == "Board Remuneration Policy"


def test_a_pdf_without_extractable_text_yields_nothing(tmp_path: Path):
    assert pdf_to_markdown(_pdf(tmp_path)) == ""


def test_an_authoring_tool_placeholder_is_not_used_as_a_title(tmp_path: Path):
    path = _pdf(tmp_path, title="Microsoft Word - 6a12-dc8b-c11c-8b5c")
    url = "https://www.nawaloka.com/(k)-Policy-on-Whistleblowing-NHL-(Approved).pdf"

    assert pdf_title(path, url) == "(k) Policy on Whistleblowing NHL (Approved)"


def test_a_real_title_behind_the_placeholder_survives(tmp_path: Path):
    path = _pdf(tmp_path, title="Microsoft Word - Whistleblowing Policy")

    assert pdf_title(path, "https://host/x.pdf") == "Whistleblowing Policy"
