"""Invoice service functions — shared by API routers and view routes."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models.contractor import Contractor
from artemis.models.invoice import Invoice, InvoiceStatus
from artemis.models.mission import Mission

# Valid status transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    InvoiceStatus.SUBMITTED: {InvoiceStatus.UNDER_REVIEW},
    InvoiceStatus.UNDER_REVIEW: {InvoiceStatus.APPROVED, InvoiceStatus.REJECTED},
    InvoiceStatus.APPROVED: {InvoiceStatus.PAID},
}


def _next_invoice_number(contractor_slug: str, seq: int) -> str:
    prefix = contractor_slug.upper()[:4]
    return f"INV-{prefix}-{seq:04d}"


async def _resolve_contractor(db: AsyncSession, contractor_slug: str) -> Contractor:
    result = await db.execute(
        select(Contractor).where(Contractor.slug == contractor_slug)
    )
    contractor = result.scalar_one_or_none()
    if contractor is None:
        raise HTTPException(status_code=404, detail=f"Contractor '{contractor_slug}' not found")
    return contractor


async def list_invoices_for_contractor(
    db: AsyncSession, contractor_slug: str
) -> list[Invoice]:
    contractor = await _resolve_contractor(db, contractor_slug)
    result = await db.execute(
        select(Invoice)
        .where(Invoice.contractor_id == contractor.id)
        .order_by(Invoice.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all_invoices(
    db: AsyncSession, status: str | None = None
) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.created_at.desc())
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_invoice(
    db: AsyncSession, contractor_slug: str, invoice_id: uuid.UUID
) -> Invoice:
    contractor = await _resolve_contractor(db, contractor_slug)
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.contractor_id == contractor.id,
        )
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return invoice


async def create_invoice(
    db: AsyncSession,
    contractor_slug: str,
    mission_id: uuid.UUID,
    amount: float,
    description: str,
    line_items: list | None = None,
    task_id: uuid.UUID | None = None,
) -> Invoice:
    contractor = await _resolve_contractor(db, contractor_slug)

    # Verify mission exists
    mission_result = await db.execute(select(Mission).where(Mission.id == mission_id))
    if mission_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    # Generate sequential invoice number
    count_result = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.contractor_id == contractor.id)
    )
    seq = (count_result.scalar() or 0) + 1

    invoice = Invoice(
        contractor_id=contractor.id,
        mission_id=mission_id,
        task_id=task_id,
        invoice_number=_next_invoice_number(contractor_slug, seq),
        amount=amount,
        status=InvoiceStatus.SUBMITTED,
        description=description,
        line_items=line_items or [],
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def update_invoice_status(
    db: AsyncSession,
    contractor_slug: str,
    invoice_id: uuid.UUID,
    new_status: str,
    reviewer_username: str,
    notes: str = "",
) -> Invoice:
    invoice = await get_invoice(db, contractor_slug, invoice_id)

    valid_next = _VALID_TRANSITIONS.get(invoice.status, set())
    if new_status not in valid_next:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {invoice.status} to {new_status}. "
                   f"Valid transitions: {sorted(valid_next) if valid_next else 'none'}",
        )

    invoice.status = new_status
    invoice.reviewer_username = reviewer_username
    invoice.notes = notes
    invoice.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(invoice)
    return invoice


async def get_budget_summary(
    db: AsyncSession, mission_id: uuid.UUID | None = None
) -> dict:
    """Return budget totals grouped by mission and contractor."""
    stmt = select(Invoice).where(
        Invoice.status.in_([
            InvoiceStatus.APPROVED,
            InvoiceStatus.PAID,
        ])
    )
    if mission_id is not None:
        stmt = stmt.where(Invoice.mission_id == mission_id)

    result = await db.execute(stmt)
    invoices = list(result.scalars().all())

    # Load contractor slugs for grouping
    contractor_ids = {inv.contractor_id for inv in invoices}
    contractors_by_id: dict[uuid.UUID, str] = {}
    if contractor_ids:
        c_result = await db.execute(
            select(Contractor).where(Contractor.id.in_(contractor_ids))
        )
        for c in c_result.scalars().all():
            contractors_by_id[c.id] = c.slug

    # Load mission names
    mission_ids = {inv.mission_id for inv in invoices}
    missions_by_id: dict[uuid.UUID, str] = {}
    if mission_ids:
        m_result = await db.execute(
            select(Mission).where(Mission.id.in_(mission_ids))
        )
        for m in m_result.scalars().all():
            missions_by_id[m.id] = m.name

    by_mission: dict[str, float] = {}
    by_contractor: dict[str, float] = {}
    total = 0.0

    for inv in invoices:
        total += inv.amount
        m_name = missions_by_id.get(inv.mission_id, str(inv.mission_id))
        c_slug = contractors_by_id.get(inv.contractor_id, str(inv.contractor_id))
        by_mission[m_name] = by_mission.get(m_name, 0.0) + inv.amount
        by_contractor[c_slug] = by_contractor.get(c_slug, 0.0) + inv.amount

    return {
        "total": total,
        "by_mission": by_mission,
        "by_contractor": by_contractor,
        "invoice_count": len(invoices),
    }
