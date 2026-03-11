"""Prompt template rendering and NPR context loading."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROMPTS_DIR = Path(__file__).parent
NPRS_DIR = Path(__file__).parent.parent / "seed" / "nprs"

_env = Environment(
    loader=FileSystemLoader(str(PROMPTS_DIR)),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    autoescape=False,
)

# Map component types → additional NPR files (beyond the always-included 7120.5)
_COMPONENT_NPR_MAP: dict[str, list[str]] = {
    "structures": ["npr_8705_2.txt"],
    "propulsion": ["npr_8705_2.txt"],
    "recovery-systems": ["npr_8705_2.txt"],
    "solid-rocket-boosters": ["npr_8705_2.txt"],
    "engines": ["npr_8705_2.txt"],
    "materials": ["npr_8705_2.txt"],
    "avionics": ["npr_7150_2.txt"],
    "crew-vehicle": ["npr_8705_2.txt", "npr_7150_2.txt"],
    "life-support": ["npr_8705_2.txt"],
}


def render_prompt(template_name: str, **kwargs: object) -> str:
    """Render a Jinja2 prompt template. Raises on missing template or variable."""
    template = _env.get_template(template_name)
    return template.render(**kwargs)


def load_npr_context(component_type: str) -> str:
    """Load relevant NPR reference text for a component type.

    Always includes NPR 7120.5 (milestone reviews). Adds structural or
    software NPRs based on the component type.
    """
    files = ["npr_7120_5.txt"]
    extra = _COMPONENT_NPR_MAP.get(component_type, [])
    for f in extra:
        if f not in files:
            files.append(f)

    sections: list[str] = []
    for filename in files:
        path = NPRS_DIR / filename
        sections.append(path.read_text())

    return "\n---\n".join(sections)
