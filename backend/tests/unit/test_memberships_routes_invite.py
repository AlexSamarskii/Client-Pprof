from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import app.api.routes.v1.memberships as memberships_routes
import pytest
from app.database.memberships import MembershipsHandler
from app.database.types_autogen import PublicMemberships
from fastapi import HTTPException
from tests.unit.test_memberships_routes_last_owner import _membership_row
from tests.utils.db_query_test_stub import TestDbClient


def _ctx_with_user(role: str, user_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        membership=SimpleNamespace(role=role),
        org=None,
        principal=None,
        user=SimpleNamespace(id=user_id),
    )


def _user(user_id: UUID, email: str) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, email=email)


def _patched_create_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fill in required PublicMemberships fields the test stub doesn't backfill."""

    def create_item(self: MembershipsHandler, values: dict[str, object]) -> PublicMemberships:  # type: ignore[type-arg]
        now = datetime.now(timezone.utc)
        payload: dict[str, object] = dict(values)
        payload.setdefault('id', str(uuid4()))
        payload.setdefault('additional_data', {})
        payload.setdefault('deleted_at', None)
        payload.setdefault('updated_at', None)
        payload.setdefault('created_at', now.isoformat())
        if isinstance(payload.get('organization_id'), UUID):
            payload['organization_id'] = str(payload['organization_id'])
        if isinstance(payload.get('invited_by_id'), UUID):
            payload['invited_by_id'] = str(payload['invited_by_id'])
        if isinstance(payload.get('invitation_expires_at'), datetime):
            payload['invitation_expires_at'] = payload['invitation_expires_at'].isoformat()  # type: ignore[union-attr]
        self.client.storage.setdefault(self.table, []).append(payload)  # type: ignore[attr-defined]
        return PublicMemberships.model_validate(payload)

    monkeypatch.setattr(MembershipsHandler, 'create_item', create_item)


# ---------- invite_membership ----------


def test_admin_invite_member_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_create_item(monkeypatch)
    organization_id = uuid4()
    actor_user_id = uuid4()

    db = TestDbClient()
    db.storage['memberships'] = []

    result = memberships_routes.invite_membership(
        organization_id=organization_id,
        payload=memberships_routes.InviteMembershipRequest(
            email='Foo@Example.com',  # type: ignore[arg-type]
            role=memberships_routes.MembershipRole.member,
        ),
        db=db,  # type: ignore[arg-type]
        ctx=_ctx_with_user('admin', actor_user_id),  # type: ignore[arg-type]
    )

    assert result.invited_email == 'foo@example.com'
    assert result.role == 'member'
    assert result.invitation_id is not None
    assert result.user_id is None
    assert result.invited_by_id == actor_user_id
    assert result.invitation_expires_at is not None
    delta = result.invitation_expires_at - datetime.now(timezone.utc)
    assert timedelta(days=6) < delta <= timedelta(days=7)


def test_admin_cannot_invite_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_create_item(monkeypatch)
    organization_id = uuid4()

    db = TestDbClient()
    db.storage['memberships'] = []

    with pytest.raises(HTTPException) as exc_info:
        memberships_routes.invite_membership(
            organization_id=organization_id,
            payload=memberships_routes.InviteMembershipRequest(
                email='foo@example.com',  # type: ignore[arg-type]
                role=memberships_routes.MembershipRole.admin,
            ),
            db=db,  # type: ignore[arg-type]
            ctx=_ctx_with_user('admin', uuid4()),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 403


def test_owner_can_invite_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_create_item(monkeypatch)
    organization_id = uuid4()

    db = TestDbClient()
    db.storage['memberships'] = []

    result = memberships_routes.invite_membership(
        organization_id=organization_id,
        payload=memberships_routes.InviteMembershipRequest(
            email='foo@example.com',  # type: ignore[arg-type]
            role=memberships_routes.MembershipRole.admin,
        ),
        db=db,  # type: ignore[arg-type]
        ctx=_ctx_with_user('owner', uuid4()),  # type: ignore[arg-type]
    )

    assert result.role == 'admin'


def test_invite_duplicate_email_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_create_item(monkeypatch)
    organization_id = uuid4()

    existing = _membership_row(
        membership_id=uuid4(),
        organization_id=organization_id,
        role='member',
    )
    existing['invited_email'] = 'foo@example.com'
    existing['invitation_id'] = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [existing]

    with pytest.raises(HTTPException) as exc_info:
        memberships_routes.invite_membership(
            organization_id=organization_id,
            payload=memberships_routes.InviteMembershipRequest(
                email='foo@example.com',  # type: ignore[arg-type]
                role=memberships_routes.MembershipRole.member,
            ),
            db=db,  # type: ignore[arg-type]
            ctx=_ctx_with_user('admin', uuid4()),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409


def test_invite_duplicate_email_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_create_item(monkeypatch)
    organization_id = uuid4()

    existing = _membership_row(
        membership_id=uuid4(),
        organization_id=organization_id,
        role='member',
    )
    existing['invited_email'] = 'foo@example.com'
    existing['invitation_id'] = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [existing]

    with pytest.raises(HTTPException) as exc_info:
        memberships_routes.invite_membership(
            organization_id=organization_id,
            payload=memberships_routes.InviteMembershipRequest(
                email='FOO@example.com',  # type: ignore[arg-type]
                role=memberships_routes.MembershipRole.member,
            ),
            db=db,  # type: ignore[arg-type]
            ctx=_ctx_with_user('admin', uuid4()),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409


def test_invite_after_previous_was_soft_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_create_item(monkeypatch)
    organization_id = uuid4()

    soft_deleted = _membership_row(
        membership_id=uuid4(),
        organization_id=organization_id,
        role='member',
        deleted_at=datetime.now(timezone.utc),
    )
    soft_deleted['invited_email'] = 'foo@example.com'

    db = TestDbClient()
    db.storage['memberships'] = [soft_deleted]

    # list_items() applies the deleted_at IS NULL scope, so the soft-deleted row
    # is not visible and the duplicate-email check passes.
    result = memberships_routes.invite_membership(
        organization_id=organization_id,
        payload=memberships_routes.InviteMembershipRequest(
            email='foo@example.com',  # type: ignore[arg-type]
            role=memberships_routes.MembershipRole.member,
        ),
        db=db,  # type: ignore[arg-type]
        ctx=_ctx_with_user('admin', uuid4()),  # type: ignore[arg-type]
    )

    assert result.invited_email == 'foo@example.com'


# ---------- accept_membership_invite ----------


def _pending_invite_row(
    *,
    organization_id: UUID,
    invited_email: str,
    invitation_id: str,
    expires_at: datetime | None = None,
    user_id: UUID | None = None,
) -> dict[str, object]:
    row = _membership_row(
        membership_id=uuid4(),
        organization_id=organization_id,
        role='member',
    )
    row['invited_email'] = invited_email
    row['invitation_id'] = invitation_id
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=5)
    row['invitation_expires_at'] = expires_at.isoformat()
    if user_id is not None:
        row['user_id'] = str(user_id)
    return row


def test_accept_invite_happy_path() -> None:
    organization_id = uuid4()
    user_id = uuid4()
    invitation_id = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_invite_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            invitation_id=invitation_id,
        )
    ]

    result = memberships_routes.accept_membership_invite(
        organization_id=organization_id,
        payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=invitation_id),
        db=db,  # type: ignore[arg-type]
        current_user=_user(user_id, 'alice@example.com'),  # type: ignore[arg-type]
    )

    assert result.user_id == user_id
    assert result.invited_email is None
    assert result.invitation_id is None
    assert result.invitation_expires_at is None


def test_accept_invite_email_match_is_case_insensitive() -> None:
    organization_id = uuid4()
    user_id = uuid4()
    invitation_id = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_invite_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            invitation_id=invitation_id,
        )
    ]

    result = memberships_routes.accept_membership_invite(
        organization_id=organization_id,
        payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=invitation_id),
        db=db,  # type: ignore[arg-type]
        current_user=_user(user_id, 'ALICE@Example.com'),  # type: ignore[arg-type]
    )

    assert result.user_id == user_id


def test_accept_invite_email_mismatch_returns_403() -> None:
    organization_id = uuid4()
    invitation_id = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_invite_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            invitation_id=invitation_id,
        )
    ]

    with pytest.raises(HTTPException) as exc_info:
        memberships_routes.accept_membership_invite(
            organization_id=organization_id,
            payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=invitation_id),
            db=db,  # type: ignore[arg-type]
            current_user=_user(uuid4(), 'bob@example.com'),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 403


def test_accept_invite_already_accepted_by_same_user_is_idempotent() -> None:
    organization_id = uuid4()
    user_id = uuid4()
    invitation_id = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_invite_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            invitation_id=invitation_id,
            user_id=user_id,
        )
    ]

    result = memberships_routes.accept_membership_invite(
        organization_id=organization_id,
        payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=invitation_id),
        db=db,  # type: ignore[arg-type]
        current_user=_user(user_id, 'alice@example.com'),  # type: ignore[arg-type]
    )

    assert result.user_id == user_id


def test_accept_invite_already_accepted_by_different_user_returns_409() -> None:
    organization_id = uuid4()
    invitation_id = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_invite_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            invitation_id=invitation_id,
            user_id=uuid4(),
        )
    ]

    with pytest.raises(HTTPException) as exc_info:
        memberships_routes.accept_membership_invite(
            organization_id=organization_id,
            payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=invitation_id),
            db=db,  # type: ignore[arg-type]
            current_user=_user(uuid4(), 'alice@example.com'),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 409


def test_accept_invite_expired_returns_410() -> None:
    organization_id = uuid4()
    invitation_id = str(uuid4())

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_invite_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            invitation_id=invitation_id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    ]

    with pytest.raises(HTTPException) as exc_info:
        memberships_routes.accept_membership_invite(
            organization_id=organization_id,
            payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=invitation_id),
            db=db,  # type: ignore[arg-type]
            current_user=_user(uuid4(), 'alice@example.com'),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 410


def test_accept_invite_unknown_invitation_id_returns_404() -> None:
    organization_id = uuid4()

    db = TestDbClient()
    db.storage['memberships'] = []

    with pytest.raises(HTTPException) as exc_info:
        memberships_routes.accept_membership_invite(
            organization_id=organization_id,
            payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=str(uuid4())),
            db=db,  # type: ignore[arg-type]
            current_user=_user(uuid4(), 'alice@example.com'),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404


def test_accept_invite_when_user_already_in_org_is_idempotent() -> None:
    organization_id = uuid4()
    user_id = uuid4()
    invitation_id = str(uuid4())

    existing_active = _membership_row(
        membership_id=uuid4(),
        organization_id=organization_id,
        role='member',
    )
    existing_active['user_id'] = str(user_id)

    db = TestDbClient()
    db.storage['memberships'] = [
        existing_active,
        _pending_invite_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            invitation_id=invitation_id,
        ),
    ]

    result = memberships_routes.accept_membership_invite(
        organization_id=organization_id,
        payload=memberships_routes.AcceptMembershipInviteRequest(invitation_id=invitation_id),
        db=db,  # type: ignore[arg-type]
        current_user=_user(user_id, 'alice@example.com'),  # type: ignore[arg-type]
    )

    # Returns the existing active membership, not the (now soft-deleted) pending row.
    assert result.user_id == user_id
    assert str(result.id) == str(existing_active['id'])

    # The pending invite row was soft-deleted (deleted_at set by delete_item).
    pending_after = next(
        row for row in db.storage['memberships'] if row['id'] != existing_active['id']
    )
    assert pending_after.get('deleted_at') is not None
