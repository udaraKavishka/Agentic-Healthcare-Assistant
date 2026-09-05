import re
import time
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from assistant.logging import logger
from web.client import Event, ask
from web.styles import LOGO, css, skeleton

API_URL = "http://localhost:8000"
# Typing pace: characters per frame, and how far the model may run ahead
# before the rest is shown at once.
STRIDE = 4
FRAME = 0.012
BACKLOG = 240
UNREACHABLE = (
    "I couldn't complete that just now. Please try again in a moment, or call"
    " Nawaloka Hospitals on 0115 577 111."
)
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
    """What the stream has produced so far, gathered in one place.

    `pending` is what has arrived but not yet been shown, which is what lets
    the reply appear at a readable pace rather than in the model's bursts.
    """

    route: str = ""
    spoken: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    pending: str = ""
    failed: bool = False

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
    """Stream one answer: what it is doing on one line, the reply filling below.

    Two placeholders rather than one. Sharing a single slot meant the first
    token wiped the line that said where the answer was being looked for, so
    the work the assistant did disappeared exactly when it paid off.
    """
    status = st.empty()
    body = st.empty()
    turn = Turn()

    status.markdown(_thinking("Reading your question"), unsafe_allow_html=True)

    try:
        for event in ask(API_URL, st.session_state.conversation_id, question):
            _apply(event, status, body, turn)
    except httpx.HTTPError as error:
        # The transport detail belongs in the log, not in front of a patient.
        logger.warning("The assistant is unreachable: %s", error)
        status.empty()
        body.markdown(UNREACHABLE)

        return Message(role="assistant", content=UNREACHABLE)

    status.empty()
    body.markdown(_prose(turn.answer))

    # A turn that failed cites nothing: the pages were fetched, but nothing was
    # said from them, and a citation under an apology credits a source for an
    # answer it never gave.
    sources = [] if turn.failed else turn.sources
    route = "" if turn.failed else turn.route
    _sources(sources, route)

    return Message(role="assistant", content=turn.answer, route=route, sources=sources)


def _apply(
    event: Event, status: DeltaGenerator, body: DeltaGenerator, turn: Turn
) -> None:
    if event.kind == "route":
        turn.route = event.value
        status.markdown(
            _thinking(f"Looking in the {ROUTE_LABELS.get(event.value, '').lower()}"),
            unsafe_allow_html=True,
        )
        return

    if event.kind == "tool":
        status.markdown(_thinking(event.detail or event.value), unsafe_allow_html=True)
        return

    if event.kind == "source":
        turn.sources.append(event.value)
        return

    if event.kind in {"token", "error"}:
        turn.failed = turn.failed or event.kind == "error"
        turn.pending += event.value
        _type(body, turn)


def _type(body: DeltaGenerator, turn: Turn) -> None:
    """Reveal what has arrived a few characters at a time.

    The model answers in bursts, so rendering each chunk whole lands a reply in
    two or three jumps. Draining the buffer at a fixed rate reads as typing.
    The backlog rule is what keeps that honest: once the model is further ahead
    than a reader would notice, the rest is shown at once rather than pacing a
    long answer to the slowest few characters.
    """
    while turn.pending:
        step = STRIDE if len(turn.pending) <= BACKLOG else len(turn.pending)
        turn.spoken.append(turn.pending[:step])
        turn.pending = turn.pending[step:]
        body.markdown(_prose(turn.answer))

        if turn.pending:
            time.sleep(FRAME)


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
