from assistant.knowledge_base import search
from assistant.state import Passage


def retrieve(question: str) -> list[Passage]:
    return [
        Passage(
            origin="vector",
            content=passage["text"],
            citation=passage["url"] or passage["title"],
        )
        for passage in search.search(question)
    ]
