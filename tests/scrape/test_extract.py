from assistant.scrape.extract import page_document, to_markdown

PAGE = """
<html><head><title>Heart Centre</title></head>
<body>
  <nav>Home Contact</nav>
  <script>window.analytics = 1;</script>
  <h1>Heart Centre</h1>
  <p>Cardiology   services  around the clock.</p>
  <h2>Consultants</h2>
  <ul><li>Dr Perera</li><li>Dr Silva</li></ul>
  <footer>All rights reserved</footer>
</body></html>
"""


def test_headings_become_markdown():
    markdown = to_markdown(PAGE)

    assert "# Heart Centre" in markdown
    assert "## Consultants" in markdown


def test_chrome_and_scripts_are_dropped():
    markdown = to_markdown(PAGE)

    assert "window.analytics" not in markdown
    assert "All rights reserved" not in markdown
    assert "Home Contact" not in markdown


def test_runs_of_whitespace_collapse():
    assert "Cardiology services around the clock." in to_markdown(PAGE)


def test_front_matter_keeps_the_source_url_with_the_text():
    document = page_document("https://www.nawaloka.com/heart-centre", "Heart", "# Hi")

    assert document.startswith(
        "---\nurl: https://www.nawaloka.com/heart-centre\ntitle: Heart\n---"
    )
    assert document.endswith("# Hi\n")
