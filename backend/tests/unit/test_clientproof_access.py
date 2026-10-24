from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.auth.deps import Principal
from app.clientproof.access import require_project_access


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

    def execute(self) -> FakeResult:
        return FakeResult(self.data)


@dataclass
class FakeSupabase:
    tables: dict[str, list[dict[str, Any]]]

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self.tables.get(name, []))


def test_revoked_grant_denies_access_immediately() -> None:
    organization_id = uuid4()
    db = FakeSupabase(
        {
            'projects': [{'id': str(uuid4()), 'organization_id': str(organization_id)}],
            'clients': [{'id': str(uuid4()), 'organization_id': str(organization_id)}],
            'project_grants': [],
            'users': [],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        require_project_access(
            uuid4(),
            Principal(kind='user', subject=str(uuid4()), roles=frozenset()),
            db=db,
        )
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_audit_append_uses_schema_timestamp_without_created_at():
    from types import SimpleNamespace
    from uuid import uuid4
    from app.database.clientproof import AuditEventsHandler

    organization_id, project_id, actor_id = uuid4(), uuid4(), uuid4()
    captured = {}

    class AuditDatabase:
        def table(self, name):
            assert name == 'audit_events'
            return self

        def insert(self, payload):
            assert 'created_at' not in payload, 'audit schema uses occurred_at'
            captured.update(payload)
            return self

        def execute(self):
            return SimpleNamespace(
                data=[dict(captured, id=str(uuid4()), occurred_at='2026-03-20T00:00:00Z')]
            )

    event = AuditEventsHandler(AuditDatabase(), organization_id=organization_id).append(
        project_id=project_id,
        deliverable_id=None,
        version_id=None,
        actor_kind='staff',
        actor_user_id=actor_id,
        actor_client_id=None,
        event_type='project.read',
        data={},
    )
    assert event.organization_id == organization_id and event.project_id == project_id
    assert event.actor_user_id == actor_id and event.occurred_at.tzinfo is not None
