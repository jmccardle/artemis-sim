from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models.facility import Facility

FACILITIES = [
    # MVP facility
    Facility(
        name="The Garage",
        location="Home Base",
        capacity=1,
        capabilities=["assembly", "integration", "storage"],
    ),
    # KSC facilities (for Artemis expansion)
    Facility(
        name="Vehicle Assembly Building (VAB) High Bay 3",
        location="KSC, FL",
        capacity=1,
        capabilities=["vehicle-stacking", "integration", "testing"],
    ),
    Facility(
        name="Launch Complex 39B (LC-39B)",
        location="KSC, FL",
        capacity=1,
        capabilities=["launch", "wet-dress-rehearsal", "pad-operations"],
    ),
    Facility(
        name="Rotation, Processing and Surge Facility (RPSF)",
        location="KSC, FL",
        capacity=4,
        capabilities=["srb-processing", "srb-rotation", "storage"],
    ),
    Facility(
        name="Multi-Payload Processing Facility (MPPF)",
        location="KSC, FL",
        capacity=1,
        capabilities=["orion-fueling", "orion-servicing"],
    ),
    Facility(
        name="Launch Abort System Facility (LASF)",
        location="KSC, FL",
        capacity=1,
        capabilities=["las-integration", "las-testing"],
    ),
    Facility(
        name="Neil Armstrong O&C Building",
        location="KSC, FL",
        capacity=2,
        capabilities=["orion-assembly", "orion-testing"],
    ),
    Facility(
        name="Mobile Launcher 1 (ML-1)",
        location="KSC, FL",
        capacity=1,
        capabilities=["launch-platform", "umbilical-connections"],
    ),
    Facility(
        name="Crawler-Transporter 2 (CT-2)",
        location="KSC, FL",
        capacity=1,
        capabilities=["vehicle-transport"],
    ),
]


async def seed_facilities(db: AsyncSession) -> list[Facility]:
    """Insert all facility definitions into the database."""
    facilities = []
    for template in FACILITIES:
        facility = Facility(
            name=template.name,
            location=template.location,
            capacity=template.capacity,
            capabilities=template.capabilities,
        )
        db.add(facility)
        facilities.append(facility)
    await db.flush()
    return facilities
