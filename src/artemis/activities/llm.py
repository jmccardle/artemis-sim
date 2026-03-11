"""LLM activities — generate text via LLM providers.

Each activity renders a Jinja2 prompt template, calls the configured LLM provider,
and returns an LLMResult. Artifacts are saved separately by the orchestration layer.
"""
from __future__ import annotations

import json
import re

from temporalio import activity

from artemis.config import get_settings
from artemis.llm.base import get_llm_provider
from artemis.prompts.loader import load_npr_context, render_prompt
from artemis.workflows.data_types import (
    EvaluateProposalInput,
    GenerateProposalInput,
    GenerateRFPInput,
    GenerateRubricInput,
    GenerateTestReportInput,
    LLMResult,
)


def _extract_json(text: str) -> str:
    """Extract JSON from LLM output that may be wrapped in markdown fences.

    Handles patterns like:
        ```json\n{...}\n```
        ```\n{...}\n```
        Some preamble\n{...}
    """
    # Try markdown fenced block first
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        return match.group(1).strip()

    # Try to find raw JSON object or array
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start != -1:
            end = text.rfind(end_char)
            if end > start:
                return text[start : end + 1]

    # Return as-is — let json.loads() produce the error
    return text.strip()


def _split_system_user(rendered: str) -> tuple[str, str]:
    """Split a rendered prompt into system and user sections.

    Templates use 'SYSTEM:' and 'USER:' markers.
    """
    if "USER:" not in rendered:
        return "", rendered

    parts = rendered.split("USER:", 1)
    system = parts[0]
    user = parts[1].strip()

    # Remove SYSTEM: prefix if present
    if system.startswith("SYSTEM:"):
        system = system[len("SYSTEM:"):].strip()
    else:
        system = system.strip()

    return system, user


@activity.defn
async def generate_rfp(input: GenerateRFPInput) -> LLMResult:
    """Generate an RFP document for a component."""
    npr_context = load_npr_context(input.component_type)

    rendered = render_prompt(
        "rfp_generation.j2",
        mission_id=input.mission_id,
        component_name=input.component_name,
        component_type=input.component_type,
        eligible_contractors=[],
        npr_context=npr_context,
    )

    system, user = _split_system_user(rendered)
    provider = get_llm_provider(get_settings())
    content = await provider.complete(prompt=user, system=system, temperature=0.7)

    return LLMResult(content=content, artifact_type="RFP")


@activity.defn
async def generate_rubric(input: GenerateRubricInput) -> LLMResult:
    """Generate an evaluation rubric from an RFP."""
    npr_context = load_npr_context(input.component_type)

    rendered = render_prompt(
        "rubric_generation.j2",
        rfp_text=input.rfp_text,
        component_type=input.component_type,
        npr_context=npr_context,
    )

    system, user = _split_system_user(rendered)
    provider = get_llm_provider(get_settings())
    raw = await provider.complete(prompt=user, system=system, temperature=0.3)

    # Extract JSON from potential markdown fences, then validate
    content = _extract_json(raw)
    json.loads(content)

    return LLMResult(
        content=content,
        artifact_type="RUBRIC",
        metadata={"format": "json"},
    )


@activity.defn
async def generate_proposal(input: GenerateProposalInput) -> LLMResult:
    """Generate a contractor proposal in response to an RFP."""
    rendered = render_prompt(
        "proposal_generation.j2",
        rfp_text=input.rfp_text,
        contractor_slug=input.contractor_slug,
        contractor_name=input.contractor_name,
        contractor_profile=input.contractor_profile,
        contractor_reliability=input.contractor_reliability,
        contractor_cost_factor=input.contractor_cost_factor,
    )

    system, user = _split_system_user(rendered)
    provider = get_llm_provider(get_settings())
    content = await provider.complete(prompt=user, system=system, temperature=0.8)

    return LLMResult(content=content, artifact_type="PROPOSAL")


@activity.defn
async def evaluate_proposal(input: EvaluateProposalInput) -> LLMResult:
    """Evaluate a contractor proposal against an RFP and rubric."""
    npr_context = load_npr_context(input.component_type) if input.component_type else ""

    rendered = render_prompt(
        "scorecard_generation.j2",
        rfp_text=input.rfp_text,
        rubric_json=input.rubric_json,
        proposal_text=input.proposal_text,
        contractor_name=input.contractor_name,
        npr_context=npr_context,
    )

    system, user = _split_system_user(rendered)
    provider = get_llm_provider(get_settings())
    raw = await provider.complete(prompt=user, system=system, temperature=0.2)

    # Extract JSON from potential markdown fences, then validate
    content = _extract_json(raw)
    json.loads(content)

    return LLMResult(
        content=content,
        artifact_type="SCORECARD",
        metadata={"format": "json"},
    )


@activity.defn
async def generate_test_report(input: GenerateTestReportInput) -> LLMResult:
    """Generate a test report for a component test."""
    component_type = input.component_type or "structures"
    npr_context = load_npr_context(component_type)

    template = "test_report_generation.j2" if input.passed else "failure_report_generation.j2"
    artifact_type = "TEST_REPORT" if input.passed else "FAILURE_REPORT"

    rendered = render_prompt(
        template,
        test_name=input.test_name,
        component_name=input.component_name,
        component_type=component_type,
        details=input.details,
        npr_context=npr_context,
    )

    system, user = _split_system_user(rendered)
    provider = get_llm_provider(get_settings())
    content = await provider.complete(prompt=user, system=system, temperature=0.5)

    return LLMResult(content=content, artifact_type=artifact_type)
