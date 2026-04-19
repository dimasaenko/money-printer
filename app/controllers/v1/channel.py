from typing import Optional

from fastapi import Path, Query, Request
from loguru import logger
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import channel as channel_service
from app.services import idea as idea_service
from app.utils import utils

router = new_router()


# --- Request/Response models ---

class ChannelCreateRequest(BaseModel):
    name: str
    slug: str
    niche: str = ""
    target_audience: str = ""
    tone: str = ""
    content_notes: list[str] = []
    language: str = "en"
    video_length_preset: str = "medium"  # short | medium | long
    status: str = "active"
    voice_config: dict = {}
    music_config: dict = {}
    video_source_config: dict = {}
    youtube_config: dict = {}


class ChannelUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    niche: Optional[str] = None
    target_audience: Optional[str] = None
    tone: Optional[str] = None
    content_notes: Optional[list[str]] = None
    language: Optional[str] = None
    video_length_preset: Optional[str] = None
    status: Optional[str] = None
    voice_config: Optional[dict] = None
    music_config: Optional[dict] = None
    video_source_config: Optional[dict] = None
    youtube_config: Optional[dict] = None


class GenerateIdeasRequest(BaseModel):
    topic_hint: str = ""
    count: int = 3


# --- Endpoints ---

@router.post("/channels", summary="Create a YouTube channel profile")
def create_channel(request: Request, body: ChannelCreateRequest):
    data = body.model_dump(exclude_none=True)
    existing = channel_service.get_channel_by_slug(data.get("slug", ""))
    if existing:
        raise HttpException(
            task_id="", status_code=400,
            message=f"channel with slug '{data['slug']}' already exists",
        )
    channel = channel_service.create_channel(data)
    logger.success(f"channel created: {channel['slug']}")
    return utils.get_response(200, channel)


@router.get("/channels", summary="List all channels")
def list_channels(request: Request, status: Optional[str] = Query(None)):
    channels = channel_service.list_channels(status=status)
    return utils.get_response(200, {"channels": channels})


@router.get("/channels/{channel_id}", summary="Get channel by ID")
def get_channel(request: Request, channel_id: int = Path(...)):
    channel = channel_service.get_channel(channel_id)
    if not channel:
        raise HttpException(task_id="", status_code=404, message="channel not found")
    return utils.get_response(200, channel)


@router.put("/channels/{channel_id}", summary="Update a channel")
def update_channel(request: Request, body: ChannelUpdateRequest, channel_id: int = Path(...)):
    channel = channel_service.get_channel(channel_id)
    if not channel:
        raise HttpException(task_id="", status_code=404, message="channel not found")
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HttpException(task_id="", status_code=400, message="no fields to update")
    updated = channel_service.update_channel(channel_id, data)
    logger.success(f"channel updated: {updated['slug']}")
    return utils.get_response(200, updated)


@router.delete("/channels/{channel_id}", summary="Delete a channel")
def delete_channel(request: Request, channel_id: int = Path(...)):
    deleted = channel_service.delete_channel(channel_id)
    if not deleted:
        raise HttpException(task_id="", status_code=404, message="channel not found")
    logger.success(f"channel deleted: id={channel_id}")
    return utils.get_response(200)


@router.post("/channels/{channel_id}/ideas", summary="Generate video ideas for a channel")
def generate_ideas(request: Request, body: GenerateIdeasRequest, channel_id: int = Path(...)):
    channel = channel_service.get_channel(channel_id)
    if not channel:
        raise HttpException(task_id="", status_code=404, message="channel not found")
    ideas = idea_service.generate_ideas(channel, topic_hint=body.topic_hint, count=body.count)
    return utils.get_response(200, {"ideas": ideas})
