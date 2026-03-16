"""Simulation & external system activity worker — handles simulation task queue.

Processes: inspection simulations, duration simulations, and all external
system adapter activities (MES, CMMS, HR, Inventory, QMS, preflight checks).
"""
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from artemis.activities.external_systems import (
    check_certification,
    check_equipment_status,
    check_material_cert,
    check_pm_current,
    create_ncr,
    create_wad,
    record_inspection_qms,
    reserve_parts,
    run_preflight_check,
    sign_off_wad_step,
    verify_labor_auth,
)
from artemis.activities.simulation import run_inspection, simulate_task_duration
from artemis.config import get_settings


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=settings.temporal_simulation_queue,
        activities=[
            # Simulation
            run_inspection,
            simulate_task_duration,
            # MES
            create_wad,
            sign_off_wad_step,
            # CMMS
            check_equipment_status,
            check_pm_current,
            # HR
            check_certification,
            verify_labor_auth,
            # Inventory
            reserve_parts,
            check_material_cert,
            # QMS
            create_ncr,
            record_inspection_qms,
            # Composite
            run_preflight_check,
        ],
    )

    print(f"Simulation worker started on queue: {settings.temporal_simulation_queue}")
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
