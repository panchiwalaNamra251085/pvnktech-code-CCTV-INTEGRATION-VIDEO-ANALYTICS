from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.camera import Camera
from app.models.site import Site
from app.schemas.camera import (
    CameraCreate,
    CameraResponse,
    CameraUpdate,
)
from app.services.camera_test import test_rtsp_connection


router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)


# ============================================================
# GET /api/v1/cameras
# List all cameras
# ============================================================
@router.get(
    "",
    response_model=list[CameraResponse],
)
def list_cameras(
    db: Session = Depends(get_db),
):
    """
    List all cameras.
    """

    cameras = db.scalars(
        select(Camera).order_by(Camera.id)
    ).all()

    return cameras


# ============================================================
# POST /api/v1/cameras
# Create camera
# ============================================================
@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_camera(
    camera_data: CameraCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new camera.
    """

    # --------------------------------------------------------
    # Check that Site exists
    # --------------------------------------------------------
    site = db.get(
        Site,
        camera_data.site_id,
    )

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found.",
        )

    # --------------------------------------------------------
    # Check duplicate camera code
    # --------------------------------------------------------
    existing_camera = db.scalar(
        select(Camera).where(
            Camera.code == camera_data.code
        )
    )

    if existing_camera is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A camera with this code already exists.",
        )

    # --------------------------------------------------------
    # Create camera
    # --------------------------------------------------------
    camera = Camera(
        site_id=camera_data.site_id,
        name=camera_data.name,
        code=camera_data.code,
        description=camera_data.description,
        rtsp_url=camera_data.rtsp_url,
        is_active=camera_data.is_active,
    )

    db.add(camera)
    db.commit()
    db.refresh(camera)

    return camera


# ============================================================
# GET /api/v1/cameras/{camera_id}
# Get one camera
# ============================================================
@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """
    Get one camera by ID.
    """

    camera = db.get(
        Camera,
        camera_id,
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    return camera


# ============================================================
# PUT /api/v1/cameras/{camera_id}
# Update camera
# ============================================================
@router.put(
    "/{camera_id}",
    response_model=CameraResponse,
)
def update_camera(
    camera_id: int,
    camera_data: CameraUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing camera.
    """

    # --------------------------------------------------------
    # Find camera
    # --------------------------------------------------------
    camera = db.get(
        Camera,
        camera_id,
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    # --------------------------------------------------------
    # Get only fields supplied by client
    # --------------------------------------------------------
    update_data = camera_data.model_dump(
        exclude_unset=True
    )

    # --------------------------------------------------------
    # If site_id is changed, verify Site
    # --------------------------------------------------------
    if "site_id" in update_data:

        site = db.get(
            Site,
            update_data["site_id"],
        )

        if site is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Site not found.",
            )

    # --------------------------------------------------------
    # If code is changed, check duplicate
    # --------------------------------------------------------
    if "code" in update_data:

        existing_camera = db.scalar(
            select(Camera).where(
                Camera.code == update_data["code"],
                Camera.id != camera_id,
            )
        )

        if existing_camera is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A camera with this code already exists.",
            )

    # --------------------------------------------------------
    # Update fields
    # --------------------------------------------------------
    for field, value in update_data.items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)

    return camera


# ============================================================
# DELETE /api/v1/cameras/{camera_id}
# Delete camera
# ============================================================
@router.delete(
    "/{camera_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a camera.
    """

    camera = db.get(
        Camera,
        camera_id,
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    db.delete(camera)
    db.commit()

    return None


# ============================================================
# POST /api/v1/cameras/{camera_id}/test
# Test RTSP connection
# ============================================================
@router.post(
    "/{camera_id}/test",
)
def test_camera(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """
    Test whether the camera RTSP stream is reachable.
    """

    # --------------------------------------------------------
    # Find camera
    # --------------------------------------------------------
    camera = db.get(
        Camera,
        camera_id,
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    # --------------------------------------------------------
    # Check RTSP URL
    # --------------------------------------------------------
    if not camera.rtsp_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera does not have an RTSP URL.",
        )

    # --------------------------------------------------------
    # Test RTSP connection
    # --------------------------------------------------------
    result = test_rtsp_connection(
        camera.rtsp_url
    )

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------
    return {
        "camera_id": camera.id,
        "camera_name": camera.name,
        "camera_code": camera.code,
        "rtsp_url": camera.rtsp_url,
        **result,
    }