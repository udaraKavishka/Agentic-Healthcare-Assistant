from functools import lru_cache
from pathlib import Path

import yaml

from assistant.config import ROOT

PROMPTS = ROOT / "configs" / "prompts.yml"


@lru_cache(maxsize=1)
def _prompts() -> dict[str, str]:
    return yaml.safe_load(Path(PROMPTS).read_text())


def prompt(name: str, **values: str) -> str:
    """Prompts live in configs/prompts.yml, not in the code that sends them.

    Routing accuracy is mostly a property of these descriptions, so they are
    edited and reviewed as text rather than buried in string literals.
    """
    return _prompts()[name].format(**values) if values else _prompts()[name]
