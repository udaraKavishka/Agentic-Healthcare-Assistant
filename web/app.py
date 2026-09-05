import re
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from web.client import Event, ask
from web.styles import LOGO, css, skeleton

API_URL = "http://localhost:8000"
PLACEHOLDER = "Ask about doctors, tests, packages or the hospital"
# The model reaches for a dash as a separator whatever the prompt says, so
# the one it writes is turned into the colon it means.
SEPARATOR_DASH = re.compile(r"\s+[—–]\s+")

ROUTE_LABELS = {
    "sql": "Hospital database",
    "vector": "Hospital website",
    "both": "Database and website",
    "faq": "General",
    "refuse": "Referred to a doctor",
}

OPENERS = [
    "What doctors are available and what do they charge?",
    "What health checkup packages do you offer?",
    "What services does the hospital provide?",
]


@dataclass
class Message:
    role: str
    content: str
    route: str = ""
    sources: list[str] = field(default_factory=list)


@dataclass
class Turn:
    """What the stream has produced so far, gathered in one place."""

    route: str = ""
    spoken: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    @property
    def answer(self) -> str:
        return "".join(self.spoken)


def main() -> None:
    st.set_page_config(
        page_title="Nawaloka assistant", page_icon=str(LOGO), layout="centered"
    )
    st.markdown(css(), unsafe_allow_html=True)

    _start_conversation()
    _header()

    if st.session_state.messages:
        _conversation()
    else:
        st.markdown(skeleton(), unsafe_allow_html=True)
        _landing()

    # Last, because Streamlit renders everything after `chat_input` inside the
    # dock pinned to the bottom of the window. Anything drawn after it lands
    # down there rather than in the page.
    asked = st.chat_input(PLACEHOLDER)
    st.markdown(
        '<div class="disclaimer">AI responses may contain mistakes. This is'
        " information only, not medical advice.</div>",
        unsafe_allow_html=True,
    )

    if asked:
        _queue(asked)


def _queue(question: str) -> None:
    """Record the question and rerun, so the answer is composed on a clean page.

    Answering in the same run as the landing page would leave that page on
    screen for the whole of the reply.
    """
    st.session_state.messages.append(Message(role="user", content=question))
    st.session_state.awaiting = question
    st.rerun()


def _start_conversation() -> None:
    """Start a conversation, or discard one this code can no longer read.

    Session state outlives a reload of the app, so a browser left open across a
    change to `Message` would come back holding the previous shape.
    """
    started = "conversation_id" in st.session_state
    readable = all(
        isinstance(message, Message) for message in st.session_state.get("messages", [])
    )

    if not started or not readable:
        _reset()


def _reset() -> None:
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.messages = []


def _header() -> None:
    brand, action = st.columns([4, 1.1], vertical_alignment="center")

    with brand:
        st.markdown(
            '<div class="brand"><div class="brand-mark"></div><div>'
            '<div class="brand-kicker">Smart hospital assistant</div>'
            '<div class="brand-name">Nawaloka AI</div>'
            "</div></div>",
            unsafe_allow_html=True,
        )

    with action:
        # Keyed so the stylesheet can find it: a hand-written wrapper would be
        # closed by Streamlit before the button is drawn inside it.
        if st.session_state.messages and st.button("＋  New chat", key="new-chat"):
            _reset()
            st.rerun()


def _landing() -> None:
    """Greeting and prompts sit low, beside the input the patient will type in."""
    st.markdown(
        '<div class="landing"></div>'
        '<div class="greeting"><div class="greeting-avatar"></div>'
        '<div class="greeting-text">Hi 👋 How can I help you today?</div></div>',
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown(
            '<div class="dock"></div>'
            '<div class="invite">What would you like to know?</div>',
            unsafe_allow_html=True,
        )

        for column, opener in zip(st.columns(3), OPENERS, strict=True):
            with column:
                if st.button(opener, use_container_width=True, key=f"ask-{opener}"):
                    _queue(opener)


def _conversation() -> None:
    _replay()

    asked = st.session_state.pop("awaiting", None)
    if not asked:
        return

    with st.chat_message("assistant"):
        st.session_state.messages.append(_answer(asked))


def _replay() -> None:
    for message in st.session_state.messages:
        if message.role == "user":
            _said(message.content)
            continue

        with st.chat_message("assistant"):
            st.markdown(_prose(message.content))
            _sources(message.sources, message.route)


def _answer(question: str) -> Message:
    """Stream one answer, showing progress until the first token arrives."""
    body = st.empty()
    turn = Turn()

    body.markdown(_thinking("Reading your question"), unsafe_allow_html=True)

    try:
        for event in ask(API_URL, st.session_state.conversation_id, question):
            _apply(event, body, turn)
    except httpx.HTTPError as error:
        message = f"I could not reach the assistant. Is the API running? ({error})"
        body.markdown(message)
        return Message(role="assistant", content=message)

    body.markdown(_prose(turn.answer))
    _sources(turn.sources, turn.route)

    return Message(
        role="assistant",
        content=turn.answer,
        route=turn.route,
        sources=turn.sources,
    )


def _apply(event: Event, body: DeltaGenerator, turn: Turn) -> None:
    if event.kind == "route":
        turn.route = event.value
        body.markdown(
            _thinking(f"Looking in the {ROUTE_LABELS.get(event.value, '').lower()}"),
            unsafe_allow_html=True,
        )
        return

    if event.kind == "tool":
        body.markdown(_thinking(event.detail or event.value), unsafe_allow_html=True)
        return

    if event.kind == "source":
        turn.sources.append(event.value)
        return

    if event.kind in {"token", "error"}:
        turn.spoken.append(event.value)
        body.markdown(_prose(turn.answer))


def _said(question: str) -> None:
    with st.chat_message("user"):
        st.markdown(f'<div class="msg-user">{question}</div>', unsafe_allow_html=True)


def _sources(sources: list[str], route: str) -> None:
    """Where the answer came from, behind a button.

    A patient wants the answer, and a reviewer wants to check where it came
    from. Both the route and the pages live here rather than labelling every
    reply with the kind of question it was.
    """
    if not sources:
        return

    pages = [source for source in sources if source.startswith("http")]

    with st.popover(f"Sources ({len(pages) or 1})"):
        st.markdown(
            f'<div class="source-line">Answered from the '
            f"{ROUTE_LABELS.get(route, route).lower()}</div>",
            unsafe_allow_html=True,
        )

        for page in pages:
            st.markdown(f"[{_label(page)}]({page})")


def _prose(answer: str) -> str:
    return SEPARATOR_DASH.sub(": ", answer)


def _thinking(step: str) -> str:
    return (
        '<div class="thinking"><span class="dots"><span></span><span></span>'
        f"<span></span></span>{step}…</div>"
    )


def _label(url: str) -> str:
    """The page, not the whole URL: a citation should read like a page name."""
    path = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]

    return path.replace("-", " ") or urlparse(url).netloc
