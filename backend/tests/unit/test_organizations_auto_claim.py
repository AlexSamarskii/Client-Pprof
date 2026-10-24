from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.database.organizations import OrganizationsHandler
from tests.unit.test_memberships_routes_last_owner import _membership_row
from tests.utils.db_query_test_stub import TestDbClient


def _pending_row(
    *,
    organization_id: UUID,
    invited_email: str | None,
    expires_at: datetime | None = None,
    user_id: UUID | None = None,
    deleted_at: datetime | None = None,
) -> dict[str, object]:
    row = _membership_row(
        membership_id=uuid4(),
        organization_id=organization_id,
        role='member',
        deleted_at=deleted_at,
    )
    row['invited_email'] = invited_email
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=5)
    row['invitation_expires_at'] = expires_at.isoformat()
    if user_id is not None:
        row['user_id'] = str(user_id)
    return row


def test_accept_pending_invites_claims_matching_email() -> None:
    organization_id = uuid4()
    user_id = uuid4()

    db = TestDbClient()
    pending = _pending_row(
        organization_id=organization_id,
        invited_email='alice@example.com',
    )
    db.storage['memberships'] = [pending]

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    accepted = handler.accept_pending_invites_for_user(user_id=user_id, email='alice@example.com')

    assert accepted == 1
    assert pending['user_id'] == str(user_id)
    assert pending['invited_email'] is None
    assert pending['invitation_id'] is None
    assert pending['invitation_expires_at'] is None


def test_accept_pending_invites_no_match_is_noop() -> None:
    organization_id = uuid4()

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_row(
            organization_id=organization_id,
            invited_email='someone-else@example.com',
        )
    ]

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    accepted = handler.accept_pending_invites_for_user(user_id=uuid4(), email='alice@example.com')

    assert accepted == 0


def test_accept_pending_invites_skips_expired() -> None:
    organization_id = uuid4()
    user_id = uuid4()

    db = TestDbClient()
    expired = _pending_row(
        organization_id=organization_id,
        invited_email='alice@example.com',
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.storage['memberships'] = [expired]

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    accepted = handler.accept_pending_invites_for_user(user_id=user_id, email='alice@example.com')

    assert accepted == 0
    assert expired['user_id'] is None  # untouched


def test_accept_pending_invites_skips_soft_deleted() -> None:
    organization_id = uuid4()

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            deleted_at=datetime.now(timezone.utc),
        )
    ]

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    accepted = handler.accept_pending_invites_for_user(user_id=uuid4(), email='alice@example.com')

    assert accepted == 0


def test_accept_pending_invites_skips_rows_already_with_user_id() -> None:
    organization_id = uuid4()
    other_user_id = uuid4()

    db = TestDbClient()
    db.storage['memberships'] = [
        _pending_row(
            organization_id=organization_id,
            invited_email='alice@example.com',
            user_id=other_user_id,
        )
    ]

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    accepted = handler.accept_pending_invites_for_user(user_id=uuid4(), email='alice@example.com')

    # The user_id IS NULL filter excludes already-claimed rows.
    assert accepted == 0
    # Existing user_id is unchanged.
    assert db.storage['memberships'][0]['user_id'] == str(other_user_id)


def test_accept_pending_invites_returns_zero_for_empty_email() -> None:
    db = TestDbClient()
    db.storage['memberships'] = []

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    assert handler.accept_pending_invites_for_user(user_id=uuid4(), email=None) == 0
    assert handler.accept_pending_invites_for_user(user_id=uuid4(), email='') == 0
    assert handler.accept_pending_invites_for_user(user_id=uuid4(), email='   ') == 0


def test_accept_pending_invites_is_idempotent_when_called_twice() -> None:
    organization_id = uuid4()
    user_id = uuid4()
    email = 'alice@example.com'

    db = TestDbClient()
    db.storage['memberships'] = [_pending_row(organization_id=organization_id, invited_email=email)]

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    first = handler.accept_pending_invites_for_user(user_id=user_id, email=email)
    second = handler.accept_pending_invites_for_user(user_id=user_id, email=email)

    assert first == 1
    # After the first call, invited_email is cleared, so the eq filter no longer matches.
    assert second == 0


def test_list_organizations_for_user_returns_orgs_via_membership_join() -> None:
    user_id = uuid4()
    org_a = uuid4()
    org_b = uuid4()
    org_unrelated = uuid4()

    membership_a = _membership_row(membership_id=uuid4(), organization_id=org_a, role='owner')
    membership_a['user_id'] = str(user_id)
    membership_b = _membership_row(membership_id=uuid4(), organization_id=org_b, role='member')
    membership_b['user_id'] = str(user_id)
    membership_other = _membership_row(
        membership_id=uuid4(), organization_id=org_unrelated, role='owner'
    )
    membership_other['user_id'] = str(uuid4())

    now = datetime.now(timezone.utc).isoformat()

    def _org_row(org_id: UUID, name: str) -> dict[str, object]:
        return {
            'id': str(org_id),
            'name': name,
            'additional_data': {},
            'created_at': now,
            'updated_at': None,
            'deleted_at': None,
            'stripe_customer_id': None,
            'billing_email': None,
            'billing_cancel_at_period_end': False,
            'billing_current_period_end': None,
            'billing_current_period_start': None,
            'billing_is_paid': False,
            'billing_plan_key': None,
            'billing_status': None,
            'billing_updated_at': None,
        }

    db = TestDbClient()
    db.storage['memberships'] = [membership_a, membership_b, membership_other]
    db.storage['organizations'] = [
        _org_row(org_a, 'A'),
        _org_row(org_b, 'B'),
        _org_row(org_unrelated, 'Other'),
    ]

    handler = OrganizationsHandler(db)  # type: ignore[arg-type]
    orgs = handler.list_organizations_for_user(user_id)

    returned_ids = {str(org.id) for org in orgs}
    assert returned_ids == {str(org_a), str(org_b)}
