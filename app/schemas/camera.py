from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CameraBase(BaseModel):
    site_id: int
    name: str
    code: str
    description: str | None = None
    rtsp_url: str
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    site_id: int | None = None
    name: str | None = None
    code: str | None = None
    description: str | None = None
    rtsp_url: str | None = None
    is_active: bool | None = None


class CameraResponse(CameraBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )