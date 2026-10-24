from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DecisionKind = Literal['approved', 'changes_requested']
ProjectStatus = Literal['draft', 'in_review', 'approved', 'changes_requested']


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    external_auth_user_id: UUID
    display_name: str | None = None
    email: str | None = None


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    display_name: str | None = None
    email: str | None = None


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    external_auth_user_id: UUID
    display_name: str | None
    email: str | None
    created_at: datetime


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    client_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    response_deadline_at: datetime | None = None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    response_deadline_at: datetime | None = None
    archived: bool | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    client_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    response_deadline_at: datetime | None
    archived_at: datetime | None
    created_at: datetime


class DeliverableCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    position: int = Field(default=1, ge=1)


class DeliverableUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    position: int | None = Field(default=None, ge=1)
    archived: bool | None = None


class DeliverableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    position: int
    archived_at: datetime | None
    created_at: datetime


class VersionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class VersionUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deliverable_id: UUID
    version_number: int
    title: str
    content: str
    review_seq: int | None
    published_at: datetime | None
    created_at: datetime


class GrantCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    client_id: UUID


class GrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    client_id: UUID
    status: Literal['active', 'revoked']
    revoked_at: datetime | None
    created_at: datetime


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    body: str = Field(min_length=1)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_id: UUID
    author_user_id: UUID | None
    author_client_id: UUID | None
    body: str
    created_at: datetime


class DecisionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    decision: DecisionKind


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_id: UUID
    client_id: UUID
    decision: DecisionKind
    active: bool
    created_at: datetime


class FileUploadCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    deliverable_id: UUID
    version_id: UUID
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=255)
    size_bytes: int = Field(ge=1, le=2_147_483_648)


class FileUploadResponse(BaseModel):
    asset_id: UUID
    storage_key: str
    upload_url: str


class FileUploadComplete(BaseModel):
    model_config = ConfigDict(extra='forbid')

    deliverable_id: UUID
    version_id: UUID
    position: int = Field(default=1, ge=1)


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    position: int
    created_at: datetime


class FileLinkResponse(BaseModel):
    file_id: UUID
    url: str
    expires_in_seconds: int
