from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models.contractor import Contractor

CONTRACTORS = [
    Contractor(
        name="Benning",
        slug="benning",
        reliability=0.85,
        cost_factor=1.3,
        speed_factor=0.8,
        specialties=["core-stage", "structures", "propulsion"],
        llm_profile="Large, established aerospace contractor. Thorough but slow. Detailed proposals with extensive documentation. Occasionally over-budget.",
        branding={
            "primary_color": "#003366",
            "secondary_color": "#6699cc",
            "css_class": "contractor-benning",
        },
    ),
    Contractor(
        name="XYZSpace",
        slug="xyzspace",
        reliability=0.75,
        cost_factor=0.7,
        speed_factor=1.4,
        specialties=["propulsion", "recovery-systems", "structures"],
        llm_profile="Fast-moving, innovative space company. Aggressive timelines, lean proposals. Sometimes cuts corners to meet schedule.",
        branding={
            "primary_color": "#1a1a2e",
            "secondary_color": "#e94560",
            "css_class": "contractor-xyzspace",
        },
    ),
    Contractor(
        name="Caltrop Candlesticks, Inc.",
        slug="caltrop-candlesticks",
        reliability=0.90,
        cost_factor=1.1,
        speed_factor=1.0,
        specialties=["solid-rocket-boosters", "propulsion", "materials"],
        llm_profile="Reliable defense contractor with deep heritage in solid propulsion. Conservative technical approach. Proposals emphasize safety margins and heritage hardware.",
        branding={
            "primary_color": "#2d4a22",
            "secondary_color": "#8fbc8f",
            "css_class": "contractor-caltrop",
        },
    ),
    Contractor(
        name="John Jingleheimer GmbH",
        slug="john-jingleheimer",
        reliability=0.88,
        cost_factor=1.0,
        speed_factor=0.9,
        specialties=["ground-systems", "integration", "testing", "facilities"],
        llm_profile="Ground systems operations specialist. Meticulous attention to procedures and safety protocols. Proposals are process-heavy with detailed staffing plans.",
        branding={
            "primary_color": "#4a0e4e",
            "secondary_color": "#c39bd3",
            "css_class": "contractor-jingleheimer",
        },
    ),
    Contractor(
        name="Jetwash Aerodyne Alliance",
        slug="jetwash-aerodyne",
        reliability=0.82,
        cost_factor=1.2,
        speed_factor=1.1,
        specialties=["engines", "propulsion", "testing"],
        llm_profile="Engine manufacturer with decades of liquid propulsion heritage. Technical proposals emphasize performance data and test history. Moderate cost, good reliability.",
        branding={
            "primary_color": "#8b0000",
            "secondary_color": "#ff6347",
            "css_class": "contractor-jetwash",
        },
    ),
    Contractor(
        name="Conglomerate Risk Distributors (CRD)",
        slug="crd",
        reliability=0.87,
        cost_factor=1.15,
        speed_factor=0.95,
        specialties=["upper-stage", "structures", "integration"],
        llm_profile="Joint venture specializing in upper stages and payload integration. Balanced proposals with good schedule management. Occasionally slow on procurement.",
        branding={
            "primary_color": "#0d47a1",
            "secondary_color": "#42a5f5",
            "css_class": "contractor-crd",
        },
    ),
    Contractor(
        name="Lunkhead Marmot, LLC",
        slug="lunkhead-marmot",
        reliability=0.86,
        cost_factor=1.25,
        speed_factor=0.85,
        specialties=["crew-vehicle", "avionics", "life-support", "structures"],
        llm_profile="Major aerospace and defense contractor. Comprehensive proposals with heavy systems engineering emphasis. Strong on safety and human-rating requirements but tends toward cost growth.",
        branding={
            "primary_color": "#1b5e20",
            "secondary_color": "#66bb6a",
            "css_class": "contractor-lunkhead",
        },
    ),
    Contractor(
        name="Vol Magnifique S.A.R.L.",
        slug="vol-magnifique",
        reliability=0.83,
        cost_factor=1.05,
        speed_factor=0.90,
        specialties=["service-module", "power-systems", "thermal", "propulsion"],
        llm_profile="International aerospace contractor partnered with the Antarctic Space Agency. Technically excellent proposals with multilingual documentation. Schedule sometimes affected by international coordination.",
        branding={
            "primary_color": "#002395",
            "secondary_color": "#ed2939",
            "css_class": "contractor-vol-magnifique",
        },
    ),
]


async def seed_contractors(db: AsyncSession) -> list[Contractor]:
    """Insert all contractor definitions into the database."""
    contractors = []
    for template in CONTRACTORS:
        contractor = Contractor(
            name=template.name,
            slug=template.slug,
            reliability=template.reliability,
            cost_factor=template.cost_factor,
            speed_factor=template.speed_factor,
            specialties=template.specialties,
            llm_profile=template.llm_profile,
            branding=template.branding,
        )
        db.add(contractor)
        contractors.append(contractor)
    await db.flush()
    return contractors
