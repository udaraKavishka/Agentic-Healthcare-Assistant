import base64
from functools import lru_cache
from pathlib import Path

STYLESHEET = Path(__file__).with_name("styles.css")
LOGO = Path(__file__).parent / "assets" / "logo.svg"


@lru_cache(maxsize=1)
def css() -> str:
    """The stylesheet as a tag Streamlit can write into the page.

    Kept as a real .css file rather than a Python string so an editor can
    highlight it and a diff reads as CSS. The mark is the one thing the file
    cannot hold: a relative url() would not resolve, so it arrives inlined as
    a custom property the stylesheet reads as var(--logo).
    """
    mark = base64.b64encode(LOGO.read_bytes()).decode()
    logo = f':root {{--logo: url("data:image/svg+xml;base64,{mark}");}}'

    return f"<style>{logo}{STYLESHEET.read_text()}</style>"


def skeleton() -> str:
    """Placeholder bars in the shape of a reply.

    Always in the page; the stylesheet reveals it only while Streamlit is
    running a script. Written and cleared from Python it would never be seen,
    because both happen in one pass before the browser paints.
    """
    bars = "".join(
        f'<div class="bar" style="width: {width}%"></div>' for width in (38, 64, 52)
    )

    return f'<div class="skeleton">{bars}</div>'
