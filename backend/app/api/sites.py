from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.site import Site
from app.schemas.site import SiteCreate, SiteResponse


# ============================================================
# Sites Router
# ============================================================

router = APIRouter(
    prefix="/sites",
    tags=["Sites"],
)


# ============================================================
# Create Site
# ============================================================

@router.post(
    "",
    response_model=SiteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_site(
    site_data: SiteCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new site.
    """

    # --------------------------------------------------------
    # Check duplicate site code
    # --------------------------------------------------------

    if site_data.code:
        existing_site = db.scalar(
            select(Site).where(
                Site.code == site_data.code
            )
        )

        if existing_site:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A site with this code already exists.",
            )

    # --------------------------------------------------------
    # Create Site object
    # --------------------------------------------------------

    site = Site(
        name=site_data.name,
        code=site_data.code,
        description=site_data.description,
    )

    # --------------------------------------------------------
    # Convert latitude/longitude to PostGIS POINT
    # --------------------------------------------------------

    if (
        site_data.latitude is not None
        and site_data.longitude is not None
    ):
        site.location = (
            f"SRID=4326;POINT("
            f"{site_data.longitude} "
            f"{site_data.latitude}"
            f")"
        )

    # --------------------------------------------------------
    # Save to database
    # --------------------------------------------------------

    db.add(site)
    db.commit()
    db.refresh(site)

    return site


# ============================================================
# List Sites
# ============================================================

@router.get(
    "",
    response_model=list[SiteResponse],
)
def list_sites(
    db: Session = Depends(get_db),
):
    """
    List all sites.
    """

    sites = db.scalars(
        select(Site).order_by(Site.id)
    ).all()

    return sites


# ============================================================
# Get Site
# ============================================================

@router.get(
    "/{site_id}",
    response_model=SiteResponse,
)
def get_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    """
    Get one site by ID.
    """

    site = db.get(
        Site,
        site_id,
    )

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found.",
        )

    return site