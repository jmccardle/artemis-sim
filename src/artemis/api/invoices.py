"""Invoice REST API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import (
    BudgetSummary,
    InvoiceCreate,
    InvoiceResponse,
    InvoiceStatusUpdate,
)
from artemis.auth.dependencies import require_role
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.services import invoices as invoice_svc

router = APIRouter()


@router.post(
    "/contractors/{slug}/invoices",
    response_model=InvoiceResponse,
    status_code=201,
)
async def create_invoice(
    slug: str,
    body: InvoiceCreate,
    user: UserInfo = Depends(require_role("contractor-pm")),
    db: AsyncSession = Depends(get_db_session),
):
    invoice = await invoice_svc.create_invoice(
        db,
        contractor_slug=slug,
        mission_id=body.mission_id,
        amount=body.amount,
        description=body.description,
        line_items=body.line_items,
        task_id=body.task_id,
    )
    return invoice


@router.get(
    "/contractors/{slug}/invoices",
    response_model=list[InvoiceResponse],
)
async def list_invoices(
    slug: str,
    user: UserInfo = Depends(require_role("contractor-pm")),
    db: AsyncSession = Depends(get_db_session),
):
    return await invoice_svc.list_invoices_for_contractor(db, slug)


@router.get(
    "/contractors/{slug}/invoices/{invoice_id}",
    response_model=InvoiceResponse,
)
async def get_invoice(
    slug: str,
    invoice_id: uuid.UUID,
    user: UserInfo = Depends(require_role("contractor-pm")),
    db: AsyncSession = Depends(get_db_session),
):
    return await invoice_svc.get_invoice(db, slug, invoice_id)


@router.patch(
    "/contractors/{slug}/invoices/{invoice_id}",
    response_model=InvoiceResponse,
)
async def update_invoice_status(
    slug: str,
    invoice_id: uuid.UUID,
    body: InvoiceStatusUpdate,
    user: UserInfo = Depends(require_role("nasa-contracts-officer")),
    db: AsyncSession = Depends(get_db_session),
):
    return await invoice_svc.update_invoice_status(
        db,
        contractor_slug=slug,
        invoice_id=invoice_id,
        new_status=body.status,
        reviewer_username=user.username,
        notes=body.notes,
    )


@router.get("/budget", response_model=BudgetSummary)
async def budget_summary(
    mission_id: uuid.UUID | None = None,
    user: UserInfo = Depends(require_role("nasa-contracts-officer")),
    db: AsyncSession = Depends(get_db_session),
):
    return await invoice_svc.get_budget_summary(db, mission_id)
