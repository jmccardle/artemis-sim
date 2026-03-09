"""LLM activities — generate text via LLM providers.

Phase 1: Stub implementations returning placeholder content.
Phase 3: Real LLM provider integration.
"""
from __future__ import annotations

from dataclasses import dataclass

from temporalio import activity


@dataclass
class GenerateRFPInput:
    mission_id: str
    component_name: str
    component_type: str


@dataclass
class GenerateProposalInput:
    rfp_text: str
    contractor_slug: str
    contractor_name: str
    contractor_profile: str
    contractor_reliability: float
    contractor_cost_factor: float


@dataclass
class EvaluateProposalInput:
    rfp_text: str
    proposal_text: str
    contractor_name: str


@dataclass
class GenerateTestReportInput:
    test_name: str
    passed: bool
    component_name: str
    details: str = ""


@dataclass
class LLMActivityResult:
    content: str
    artifact_type: str = ""


@activity.defn
async def generate_rfp(input: GenerateRFPInput) -> LLMActivityResult:
    """Generate an RFP document for a component.

    Phase 1 stub: returns template text.
    """
    content = (
        f"REQUEST FOR PROPOSALS\n"
        f"Mission Component: {input.component_name}\n"
        f"Category: {input.component_type}\n\n"
        f"The National Aeronautics and Space Administration (NASA) seeks proposals "
        f"for the procurement of {input.component_name} for mission {input.mission_id}.\n\n"
        f"Requirements:\n"
        f"- Component must meet all applicable NASA safety standards\n"
        f"- Delivery within specified timeline\n"
        f"- Full documentation and test reports required\n"
        f"- Quality assurance plan required\n"
    )
    return LLMActivityResult(content=content, artifact_type="RFP")


@activity.defn
async def generate_proposal(input: GenerateProposalInput) -> LLMActivityResult:
    """Generate a contractor proposal in response to an RFP.

    Phase 1 stub: returns template proposal.
    """
    content = (
        f"TECHNICAL PROPOSAL\n"
        f"Contractor: {input.contractor_name} ({input.contractor_slug})\n\n"
        f"Technical Approach:\n"
        f"We propose to deliver the requested component using our proven "
        f"manufacturing processes with a reliability factor of {input.contractor_reliability:.0%}.\n\n"
        f"Cost Estimate: Baseline \u00d7 {input.contractor_cost_factor:.2f}\n\n"
        f"Schedule: Standard delivery timeline\n\n"
        f"Risk Assessment:\n"
        f"- Low risk: Proven technology and processes\n"
        f"- Mitigation: Redundant quality checks\n"
    )
    return LLMActivityResult(content=content, artifact_type="PROPOSAL")


@activity.defn
async def evaluate_proposal(input: EvaluateProposalInput) -> LLMActivityResult:
    """Evaluate a contractor proposal against an RFP.

    Phase 1 stub: returns template evaluation.
    """
    content = (
        f"PROPOSAL EVALUATION SCORECARD\n"
        f"Contractor: {input.contractor_name}\n\n"
        f"Technical Approach: 4/5 \u2014 Meets requirements\n"
        f"Cost Reasonableness: 4/5 \u2014 Within acceptable range\n"
        f"Schedule Feasibility: 4/5 \u2014 Achievable timeline\n"
        f"Risk Management: 3/5 \u2014 Adequate mitigation\n\n"
        f"Overall: ACCEPT\n"
        f"Recommendation: Proceed with contract award.\n"
    )
    return LLMActivityResult(content=content, artifact_type="SCORECARD")


@activity.defn
async def generate_test_report(input: GenerateTestReportInput) -> LLMActivityResult:
    """Generate a test report for a component test.

    Phase 1 stub: returns template report.
    """
    status = "PASS" if input.passed else "FAIL"
    content = (
        f"TEST REPORT: {input.test_name}\n"
        f"Component: {input.component_name}\n"
        f"Result: {status}\n\n"
        f"Details: {input.details or 'Standard test procedure completed.'}\n\n"
        f"{'All acceptance criteria met.' if input.passed else 'Component did not meet acceptance criteria. Rework recommended.'}\n"
    )
    return LLMActivityResult(content=content, artifact_type="TEST_REPORT")
