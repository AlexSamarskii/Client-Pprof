from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.auth.deps import Principal
from app.clientproof import routers
from app.clientproof.access import (
    ProjectAccessContext,
    require_project_access,
)
from app.database.types_autogen import (
    PublicMemberships,
    PublicProjects,
    PublicUsers,
)


@dataclass
class FakeResult:
    data: Any


@dataclass
class FakeQuery:
    data: Any
    filters: dict[str, Any] = field(default_factory=dict)

    def select(self, _columns: str) -> 'FakeQuery':
        return self

    def eq(self, column: str, value: Any) -> 'FakeQuery':
        self.filters[column] = value
        return self

    def is_(self, _column: str, _value: Any) -> 'FakeQuery':
        return self

    def limit(self, _count: int) -> 'FakeQuery':
        return self

    def insert(self, payload: Any) -> 'FakeQuery':
        rows = [payload] if isinstance(payload, dict) else list(payload or [])
        for row in rows:
            if isinstance(row, dict):
                row.setdefault('id', str(uuid4()))
                row.setdefault('occurred_at', '2026-03-20T00:00:00Z')
                row.setdefault('created_at', '2026-03-20T00:00:00Z')
                row.setdefault('updated_at', None)
        return FakeQuery(rows)

    def update(self, payload: Any) -> 'FakeQuery':
        return FakeQuery([payload] if isinstance(payload, dict) else list(payload or []))

    def order(self, _column: str, *, desc: bool = False) -> 'FakeQuery':
        return self

    def range(self, _start: int, _end: int) -> 'FakeQuery':
        return self

    def execute(self) -> FakeResult:
        return FakeResult(self.data)


@dataclass
class FakeSupabase:
    tables: dict[str, list[dict[str, Any]]]
    rpc_results: dict[str, Any] = field(default_factory=dict)

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self.tables.get(name, []))

    def insert(self, _payload: Any) -> FakeQuery:
        return FakeQuery([_payload])

    def rpc(self, name: str, _payload: dict[str, Any]) -> FakeQuery:
        return FakeQuery(self.rpc_results.get(name))


def _project(organization_id: UUID) -> PublicProjects:
    return PublicProjects(
        id=uuid4(),
        created_at='2026-03-20T00:00:00Z',
        updated_at=None,
        organization_id=organization_id,
        client_id=uuid4(),
        name='Identity system',
        description=None,
        status='draft',
        response_deadline_at='2026-04-01T00:00:00Z',
        archived_at=None,
        archived_by_user_id=None,
    )


def _principal() -> Principal:
    return Principal(kind='user', subject=str(uuid4()), roles=frozenset())


def _staff_context(project: PublicProjects) -> ProjectAccessContext:
    principal = _principal()
    return ProjectAccessContext(
        db=FakeSupabase(tables={}),
        principal=principal,
        project=project,
        user=PublicUsers(
            id=UUID(principal.subject),
            created_at='2026-01-01T00:00:00Z',
            updated_at=None,
            deleted_at=None,
            email='staff@example.test',
            full_name=None,
            username='staff',
            avatar_url=None,
            additional_data={},
        ),
        staff_membership=PublicMemberships(
            id=uuid4(),
            created_at='2026-01-01T00:00:00Z',
            updated_at=None,
            deleted_at=None,
            organization_id=project.organization_id,
            user_id=None,
            role='member',
            invited_email=None,
            invited_by_id=None,
            invitation_id=None,
            invitation_expires_at=None,
            additional_data={},
        ),
        client_id=None,
    )


def test_staff_can_access_project_without_grant() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    user_id = uuid4()
    db = FakeSupabase(
        {
            'projects': [project.model_dump(mode='json')],
            'memberships': [
                {
                    'id': str(uuid4()),
                    'organization_id': str(organization_id),
                    'user_id': str(user_id),
                    'role': 'member',
                    'invited_email': None,
                    'invited_by_id': None,
                    'invitation_id': None,
                    'invitation_expires_at': None,
                    'additional_data': {},
                    'created_at': '2026-01-01T00:00:00Z',
                    'updated_at': None,
                    'deleted_at': None,
                }
            ],
            'users': [
                {
                    'id': str(user_id),
                    'email': 'staff@example.test',
                    'full_name': None,
                    'username': 'staff',
                    'avatar_url': None,
                    'additional_data': {},
                    'created_at': '2026-01-01T00:00:00Z',
                    'updated_at': None,
                    'deleted_at': None,
                }
            ],
        }
    )
    context = require_project_access(
        project.id,
        Principal(kind='user', subject=str(user_id), roles=frozenset()),
        db=db,
    )
    assert context.is_staff


def test_external_client_without_active_grant_is_denied() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    user_id = uuid4()
    db = FakeSupabase(
        {
            'projects': [project.model_dump(mode='json')],
            'clients': [{'id': str(uuid4()), 'organization_id': str(organization_id)}],
            'project_grants': [],
            'users': [],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        require_project_access(
            project.id,
            Principal(kind='user', subject=str(user_id), roles=frozenset()),
            db=db,
        )
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_unknown_project_for_known_actor_is_denied() -> None:
    db = FakeSupabase({'projects': [], 'users': []})
    with pytest.raises(HTTPException) as exc_info:
        require_project_access(uuid4(), _principal(), db=db)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_project_routes_require_credentials() -> None:
    app = FastAPI()
    app.include_router(routers.router)

    def missing_principal() -> Principal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing credentials')

    app.dependency_overrides[routers.get_principal] = missing_principal
    with TestClient(app) as client:
        response = client.get('/v1/clientproof/projects')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['detail'] == 'Missing credentials'


def test_decision_rpc_error_is_mapped_to_conflict() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    db = FakeSupabase(
        tables={},
        rpc_results={
            'submit_decision_atomic': {
                'kind': 'decision_conflict',
                'decision_id': str(uuid4()),
                'decision': 'approved',
            }
        },
    )
    context = replace(_staff_context(project), db=db, staff_membership=None, client_id=uuid4())
    with pytest.raises(HTTPException) as exc_info:
        routers.submit_decision(
            uuid4(), routers.DecisionCreate(decision='changes_requested'), context
        )
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail['kind'] == 'decision_conflict'


def test_decision_rpc_idempotent_result_is_accepted() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    version_id = uuid4()
    client_id = uuid4()
    decision_id = uuid4()
    db = FakeSupabase(
        {
            'approval_decisions': [
                {
                    'id': str(decision_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'version_id': str(version_id),
                    'client_id': str(client_id),
                    'decision': 'approved',
                    'active': True,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ]
        },
        rpc_results={
            'submit_decision_atomic': {
                'kind': 'idempotent',
                'decision_id': str(decision_id),
                'decision': 'approved',
            }
        },
    )
    context = replace(_staff_context(project), db=db, staff_membership=None, client_id=client_id)
    response = routers.submit_decision(
        version_id, routers.DecisionCreate(decision='approved'), context
    )
    assert response.id == decision_id
    assert response.active is True


def test_unarchive_requires_serialized_quota_rpc() -> None:
    project = _project(uuid4())
    db = FakeSupabase(
        tables={'projects': [project.model_dump(mode='json')]},
        rpc_results={
            'set_project_archived_atomic': {
                'kind': 'quota_conflict',
                'limit': 5,
                'active_count': 5,
            }
        },
    )
    context = _staff_context(project)
    context = replace(context, db=db)
    with pytest.raises(HTTPException) as exc_info:
        routers.update_project(routers.ProjectUpdate(archived=False), context)
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail['kind'] == 'quota_conflict'


def test_image_upload_provider_is_restricted_to_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    class ImageConnector:
        @staticmethod
        def get_provider() -> routers.AssetProvider:
            return routers.AssetProvider.IMAGE

        @staticmethod
        def generate_presigned_url(**_: object) -> str:
            return 'https://example.test/upload'

    project = _project(uuid4())
    deliverable_id = uuid4()
    version_id = uuid4()
    db = FakeSupabase(
        {
            'deliverables': [
                {
                    'id': str(deliverable_id),
                    'organization_id': str(project.organization_id),
                    'project_id': str(project.id),
                    'name': 'Logo',
                    'description': None,
                    'position': 1,
                    'archived_at': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ],
            'deliverable_versions': [
                {
                    'id': str(version_id),
                    'organization_id': str(project.organization_id),
                    'project_id': str(project.id),
                    'deliverable_id': str(deliverable_id),
                    'version_number': 1,
                    'title': 'Draft',
                    'content': 'draft',
                    'review_seq': None,
                    'published_at': None,
                    'published_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ],
        }
    )
    monkeypatch.setattr(routers, 'get_cloudflare_connector', lambda _: ImageConnector())
    with pytest.raises(HTTPException) as exc_info:
        routers.create_file_upload(
            routers.FileUploadCreate(
                deliverable_id=deliverable_id,
                version_id=version_id,
                filename='logo.png',
                mime_type='image/png',
                size_bytes=128,
            ),
            replace(_staff_context(project), db=db),
        )
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail['kind'] == 'unsupported_upload_provider'


def test_r2_upload_completion_validates_actual_object_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class R2Connector:
        @staticmethod
        def get_provider() -> routers.AssetProvider:
            return routers.AssetProvider.R2

        @staticmethod
        def get_object_metadata(_key: str) -> dict[str, object]:
            return {'size_bytes': 64, 'mime_type': 'image/png'}

    project = _project(uuid4())
    deliverable_id = uuid4()
    version_id = uuid4()
    asset_id = uuid4()
    storage_key = f'{project.organization_id}/projects/{project.id}/{asset_id}'
    db = FakeSupabase(
        {
            'assets': [
                {
                    'id': str(uuid4()),
                    'asset_id': str(asset_id),
                    'organization_id': str(project.organization_id),
                    'user_id': str(uuid4()),
                    'filename': 'logo.png',
                    'storage_key': storage_key,
                    'mime_type': 'image/png',
                    'status': 'pending',
                    'size_bytes': 128,
                    'provider': 'r2',
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                    'deleted_at': None,
                    'thumbnail_url': None,
                }
            ],
            'deliverables': [
                {
                    'id': str(deliverable_id),
                    'organization_id': str(project.organization_id),
                    'project_id': str(project.id),
                    'name': 'Logo',
                    'description': None,
                    'position': 1,
                    'archived_at': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ],
            'deliverable_versions': [
                {
                    'id': str(version_id),
                    'organization_id': str(project.organization_id),
                    'project_id': str(project.id),
                    'deliverable_id': str(deliverable_id),
                    'version_number': 1,
                    'title': 'Draft',
                    'content': 'draft',
                    'review_seq': None,
                    'published_at': None,
                    'published_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ],
        }
    )
    monkeypatch.setattr(routers, 'get_cloudflare_connector', lambda _: R2Connector())
    with pytest.raises(HTTPException) as exc_info:
        routers.complete_file_upload(
            asset_id,
            routers.FileUploadComplete(deliverable_id=deliverable_id, version_id=version_id),
            replace(_staff_context(project), db=db),
        )
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert exc_info.value.detail['kind'] == 'asset_size_mismatch'


def test_successful_version_read_writes_access_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(uuid4())
    version_id = uuid4()
    db = FakeSupabase(
        {
            'deliverable_versions': [
                {
                    'id': str(version_id),
                    'organization_id': str(project.organization_id),
                    'project_id': str(project.id),
                    'deliverable_id': str(uuid4()),
                    'version_number': 1,
                    'title': 'Published',
                    'content': 'published',
                    'review_seq': 1,
                    'published_at': '2026-03-20T00:00:00Z',
                    'published_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ]
        }
    )
    context = replace(_staff_context(project), db=db)
    audit_data: list[tuple[str, dict[str, object], UUID | None]] = []

    def record_append(
        _self: routers.AuditEventsHandler,
        *,
        project_id: UUID,
        deliverable_id: UUID | None,
        version_id: UUID | None,
        actor_kind: str,
        actor_user_id: UUID | None,
        actor_client_id: UUID | None,
        event_type: str,
        data: dict[str, object],
    ) -> None:
        _ = project_id, deliverable_id, actor_kind, actor_user_id, actor_client_id
        audit_data.append((event_type, data, version_id))

    monkeypatch.setattr(routers.AuditEventsHandler, 'append', record_append)
    response = routers.list_versions(context)
    assert response.root[0].id == version_id
    assert audit_data == [
        ('project.versions_read', {'project_id': str(project.id), 'count': 1}, None)
    ]


def test_client_cannot_mutate_project_or_create_deliverable() -> None:
    project = _project(uuid4())
    context = replace(_staff_context(project), staff_membership=None, client_id=uuid4())
    with pytest.raises(HTTPException) as update_error:
        routers.update_project(routers.ProjectUpdate(name='Forbidden'), context)
    with pytest.raises(HTTPException) as deliverable_error:
        routers.create_deliverable(routers.DeliverableCreate(name='Forbidden'), context)
    with pytest.raises(HTTPException) as upload_error:
        routers.create_file_upload(
            routers.FileUploadCreate(
                deliverable_id=uuid4(),
                version_id=uuid4(),
                filename='result.png',
                mime_type='image/png',
                size_bytes=128,
            ),
            context,
        )
    assert update_error.value.status_code == status.HTTP_403_FORBIDDEN
    assert deliverable_error.value.status_code == status.HTTP_403_FORBIDDEN
    assert upload_error.value.status_code == status.HTTP_403_FORBIDDEN


def test_client_version_and_grant_listings_are_scope_filtered() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    client_id = uuid4()
    deliverable_id = uuid4()
    published_version_id = uuid4()
    draft_version_id = uuid4()
    active_grant_id = uuid4()
    other_grant_id = uuid4()
    revoked_grant_id = uuid4()
    db = FakeSupabase(
        {
            'deliverable_versions': [
                {
                    'id': str(published_version_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'deliverable_id': str(deliverable_id),
                    'version_number': 1,
                    'title': 'Published',
                    'content': 'published',
                    'review_seq': 1,
                    'published_at': '2026-03-20T00:00:00Z',
                    'published_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                },
                {
                    'id': str(draft_version_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'deliverable_id': str(deliverable_id),
                    'version_number': 2,
                    'title': 'Draft',
                    'content': 'draft',
                    'review_seq': None,
                    'published_at': None,
                    'published_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                },
            ],
            'project_grants': [
                {
                    'id': str(active_grant_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'client_id': str(client_id),
                    'status': 'active',
                    'revoked_at': None,
                    'revoked_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                },
                {
                    'id': str(other_grant_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'client_id': str(uuid4()),
                    'status': 'active',
                    'revoked_at': None,
                    'revoked_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                },
                {
                    'id': str(revoked_grant_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'client_id': str(client_id),
                    'status': 'revoked',
                    'revoked_at': '2026-03-20T01:00:00Z',
                    'revoked_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                },
            ],
        }
    )
    context = replace(_staff_context(project), db=db, staff_membership=None, client_id=client_id)
    versions = routers.list_versions(context)
    grants = routers.list_grants(context)
    assert [version.id for version in versions.root] == [published_version_id]
    assert [grant.id for grant in grants.root] == [active_grant_id]


def test_project_deadline_is_optional_in_api_contract() -> None:
    payload = routers.ProjectCreate(client_id=uuid4(), name='Launch site')
    assert payload.response_deadline_at is None


def test_file_link_is_project_scoped_and_short_lived(monkeypatch: pytest.MonkeyPatch) -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    context = _staff_context(project)
    file_id = uuid4()
    storage_key = f'{organization_id}/projects/{project.id}/{uuid4()}'
    db = FakeSupabase(
        {
            'deliverable_version_files': [
                {
                    'id': str(file_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'version_id': str(uuid4()),
                    'asset_id': str(uuid4()),
                    'filename': 'result.png',
                    'storage_key': storage_key,
                    'mime_type': 'image/png',
                    'size_bytes': 128,
                    'position': 1,
                    'is_public': False,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ]
        }
    )
    context = replace(context, db=db)

    class StaticConnector:
        def generate_presigned_url(self, **kwargs: Any) -> str:
            assert kwargs['key'] == storage_key
            assert kwargs['expires_in'] == 300
            return f'https://files.test/{kwargs["key"]}?token=short'

    monkeypatch.setattr(routers, 'get_cloudflare_connector', lambda mime_type: StaticConnector())

    response = routers.create_file_link(file_id, context)
    assert response.url.startswith('https://files.test/')
    assert response.expires_in_seconds == 300


def test_file_link_rejects_storage_key_outside_project() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    context = _staff_context(project)
    foreign_project_id = uuid4()
    file_id = uuid4()
    db = FakeSupabase(
        {
            'deliverable_version_files': [
                {
                    'id': str(file_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'version_id': str(uuid4()),
                    'asset_id': str(uuid4()),
                    'filename': 'result.png',
                    'storage_key': f'{organization_id}/projects/{foreign_project_id}/{uuid4()}',
                    'mime_type': 'image/png',
                    'size_bytes': 128,
                    'position': 1,
                    'is_public': False,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ]
        }
    )
    context = replace(context, db=db)
    with pytest.raises(HTTPException) as exc_info:
        routers.create_file_link(file_id, context)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def _draft_version_db(project: PublicProjects) -> tuple[UUID, FakeSupabase]:
    organization_id = project.organization_id
    draft_version_id = uuid4()
    client_id = uuid4()
    return draft_version_id, FakeSupabase(
        {
            'deliverable_versions': [
                {
                    'id': str(draft_version_id),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'deliverable_id': str(uuid4()),
                    'version_number': 1,
                    'title': 'Draft version',
                    'content': 'draft content',
                    'review_seq': None,
                    'published_at': None,
                    'published_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ],
            'project_grants': [
                {
                    'id': str(uuid4()),
                    'organization_id': str(organization_id),
                    'project_id': str(project.id),
                    'client_id': str(client_id),
                    'status': 'active',
                    'revoked_at': None,
                    'revoked_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ],
        }
    )


def _draft_version_client_context(
    project: PublicProjects, draft_version_id: UUID, db: FakeSupabase
) -> ProjectAccessContext:
    grant = db.tables['project_grants'][0]
    return replace(
        _staff_context(project),
        db=db,
        staff_membership=None,
        client_id=UUID(str(grant['client_id'])),
    )


def test_client_cannot_list_draft_version_comments() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    draft_version_id, db = _draft_version_db(project)
    comment_id = uuid4()
    db.tables['comments'] = [
        {
            'id': str(comment_id),
            'organization_id': str(organization_id),
            'project_id': str(project.id),
            'version_id': str(draft_version_id),
            'author_user_id': str(uuid4()),
            'author_client_id': None,
            'body': 'draft comment',
            'created_at': '2026-03-20T00:00:00Z',
            'updated_at': None,
        }
    ]
    context = _draft_version_client_context(project, draft_version_id, db)
    with pytest.raises(HTTPException) as exc_info:
        routers.list_comments(draft_version_id, context)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_client_cannot_list_draft_version_files() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    draft_version_id, db = _draft_version_db(project)
    file_id = uuid4()
    db.tables['deliverable_version_files'] = [
        {
            'id': str(file_id),
            'organization_id': str(organization_id),
            'project_id': str(project.id),
            'version_id': str(draft_version_id),
            'asset_id': str(uuid4()),
            'filename': 'draft.png',
            'storage_key': f'{organization_id}/projects/{project.id}/{file_id}',
            'mime_type': 'image/png',
            'size_bytes': 128,
            'position': 1,
            'is_public': False,
            'created_at': '2026-03-20T00:00:00Z',
            'updated_at': None,
        }
    ]
    context = _draft_version_client_context(project, draft_version_id, db)
    with pytest.raises(HTTPException) as exc_info:
        routers.list_version_files(draft_version_id, context)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_client_cannot_link_draft_version_file() -> None:
    organization_id = uuid4()
    project = _project(organization_id)
    draft_version_id, db = _draft_version_db(project)
    file_id = uuid4()
    storage_key = f'{organization_id}/projects/{project.id}/{file_id}'
    db.tables['deliverable_version_files'] = [
        {
            'id': str(file_id),
            'organization_id': str(organization_id),
            'project_id': str(project.id),
            'version_id': str(draft_version_id),
            'asset_id': str(uuid4()),
            'filename': 'draft.png',
            'storage_key': storage_key,
            'mime_type': 'image/png',
            'size_bytes': 128,
            'position': 1,
            'is_public': False,
            'created_at': '2026-03-20T00:00:00Z',
            'updated_at': None,
        }
    ]
    context = _draft_version_client_context(project, draft_version_id, db)
    with pytest.raises(HTTPException) as exc_info:
        routers.create_file_link(file_id, context)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_client_project_listing_is_grant_scoped() -> None:
    organization_id = uuid4()
    granted_project = _project(organization_id)
    ungranted_project = _project(organization_id)
    client_id = uuid4()
    user_id = uuid4()
    db = FakeSupabase(
        {
            'users': [
                {
                    'id': str(user_id),
                    'email': 'client@example.test',
                    'full_name': None,
                    'username': 'client',
                    'avatar_url': None,
                    'additional_data': {},
                    'created_at': '2026-01-01T00:00:00Z',
                    'updated_at': None,
                    'deleted_at': None,
                }
            ],
            'memberships': [],
            'clients': [
                {
                    'id': str(client_id),
                    'organization_id': str(organization_id),
                    'external_auth_user_id': str(user_id),
                }
            ],
            'projects': [
                granted_project.model_dump(mode='json'),
                ungranted_project.model_dump(mode='json'),
            ],
            'project_grants': [
                {
                    'id': str(uuid4()),
                    'organization_id': str(organization_id),
                    'project_id': str(granted_project.id),
                    'client_id': str(client_id),
                    'status': 'active',
                }
            ],
        }
    )
    response = routers.list_accessible_projects(
        Principal(kind='user', subject=str(user_id), roles=frozenset()), db=db
    )
    assert [project.id for project in response.root] == [granted_project.id]


@pytest.mark.parametrize('staff', [False, True])
def test_published_decision_history_is_scoped_to_project_version_and_client(staff: bool) -> None:
    project = _project(uuid4())
    version_id, client_id = uuid4(), uuid4()

    def decision(*, owner=client_id, target_project=project.id, target_version=version_id):
        return {
            'id': str(uuid4()),
            'organization_id': str(project.organization_id),
            'project_id': str(target_project),
            'version_id': str(target_version),
            'client_id': str(owner),
            'decision': 'approved',
            'active': True,
            'created_at': '2026-03-20T00:00:00Z',
        }

    own = decision()
    other_client = decision(owner=uuid4())
    db = FakeSupabase(
        {
            'approval_decisions': [
                own,
                other_client,
                decision(target_project=uuid4()),
                decision(target_version=uuid4()),
            ],
            'deliverable_versions': [
                {
                    'id': str(version_id),
                    'organization_id': str(project.organization_id),
                    'project_id': str(project.id),
                    'deliverable_id': str(uuid4()),
                    'version_number': 1,
                    'title': 'Published',
                    'content': 'Review',
                    'review_seq': 1,
                    'published_at': '2026-03-20T00:00:00Z',
                    'published_by_user_id': None,
                    'created_at': '2026-03-20T00:00:00Z',
                    'updated_at': None,
                }
            ],
        }
    )
    context = replace(_staff_context(project), db=db)
    if not staff:
        context = replace(context, staff_membership=None, client_id=client_id)
    result = routers.list_decisions(version_id, context)
    expected = [UUID(own['id']), UUID(other_client['id'])] if staff else [UUID(own['id'])]
    assert [row.id for row in result.root] == expected


@pytest.mark.parametrize('resource', ['comments', 'decisions', 'files'])
@pytest.mark.parametrize('published', [False, None])
def test_client_cannot_list_draft_or_missing_version_resources(resource, published) -> None:
    project = _project(uuid4())
    version_id = uuid4()
    versions = (
        []
        if published is None
        else [
            {
                'id': str(version_id),
                'organization_id': str(project.organization_id),
                'project_id': str(project.id),
                'deliverable_id': str(uuid4()),
                'version_number': 1,
                'title': 'Draft',
                'content': 'Private',
                'review_seq': None,
                'published_at': None,
                'published_by_user_id': None,
                'created_at': '2026-03-20T00:00:00Z',
                'updated_at': None,
            }
        ]
    )
    context = replace(
        _staff_context(project),
        db=FakeSupabase({'deliverable_versions': versions}),
        staff_membership=None,
        client_id=uuid4(),
    )
    action = {
        'comments': routers.list_comments,
        'decisions': routers.list_decisions,
        'files': routers.list_version_files,
    }[resource]
    with pytest.raises(HTTPException) as error:
        action(version_id, context)
    assert error.value.status_code == 404


def test_client_access_audit_has_exactly_one_actor(monkeypatch):
    captured = []

    def append(_handler, **payload):
        assert payload['actor_kind'] == 'client'
        assert payload['actor_user_id'] is None
        assert payload['actor_client_id'] is not None
        captured.append(payload)

    monkeypatch.setattr(routers.AuditEventsHandler, 'append', append)
    context = replace(_staff_context(_project(uuid4())), staff_membership=None, client_id=uuid4())
    assert routers.read_project(context).id == context.project.id
    assert len(captured) == 1
