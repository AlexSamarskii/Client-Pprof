"""
Integration tests for the handle_new_user() trigger introduced in
20260318000000_signup_claims_pending_invites.sql.

Each test creates an auth.users row via the admin API, which fires the
trigger; we then assert on the resulting public.users / organizations /
memberships state. Hard-cleans in finally so the local DB stays tidy.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from supabase import Client
from tests.utils.db_cleanup import purge_test_records


def _unique_email() -> str:
    return f'inviteclaim+{uuid4().hex[:12]}@example.com'


def _list_org_ids_for_user(client: Client, user_id: str) -> list[str]:
    rows = (
        client.table('memberships')
        .select('organization_id')
        .eq('user_id', user_id)
        .is_('deleted_at', 'null')
        .execute()
        .data
        or []
    )
    return [row['organization_id'] for row in rows if row.get('organization_id')]


def _cleanup(
    client: Client,
    *,
    user_id: str | None,
    extra_org_ids: list[str],
    extra_membership_ids: list[str],
) -> None:
    # Resolve any orgs the trigger may have created for this user (personal org)
    # via the supabase client, then hand the full set to the bypass purge.
    org_ids: set[str] = set(extra_org_ids)
    if user_id is not None:
        org_ids.update(_list_org_ids_for_user(client, user_id))

    purge_test_records(
        user_ids=[user_id] if user_id else (),
        organization_ids=org_ids,
        membership_ids=extra_membership_ids,
    )


def test_signup_with_no_pending_invite_creates_personal_org(
    supabase_service_client: Client,
) -> None:
    email = _unique_email()
    user_id: str | None = None

    try:
        created = supabase_service_client.auth.admin.create_user(
            {
                'email': email,
                'password': 'test-password-123!',
                'email_confirm': True,
            }
        )
        user_id = str(created.user.id)

        org_ids = _list_org_ids_for_user(supabase_service_client, user_id)
        assert len(org_ids) == 1, f'expected 1 personal org, got {org_ids}'

        membership = (
            supabase_service_client.table('memberships')
            .select('role')
            .eq('user_id', user_id)
            .eq('organization_id', org_ids[0])
            .single()
            .execute()
            .data
        )
        assert membership['role'] == 'owner'
    finally:
        _cleanup(
            supabase_service_client,
            user_id=user_id,
            extra_org_ids=[],
            extra_membership_ids=[],
        )


def test_signup_claims_pending_invite_and_skips_personal_org(
    supabase_service_client: Client,
) -> None:
    email = _unique_email()
    user_id: str | None = None
    inviter_org_id: str | None = None
    membership_id: str | None = None

    try:
        # Pre-create the inviter org with a pending invite for `email`.
        inviter_org = (
            supabase_service_client.table('organizations')
            .insert({'name': f'test-inviter-{uuid4().hex[:8]}'})
            .execute()
            .data[0]
        )
        inviter_org_id = inviter_org['id']

        invitation_expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        pending = (
            supabase_service_client.table('memberships')
            .insert(
                {
                    'organization_id': inviter_org_id,
                    'user_id': None,
                    'role': 'member',
                    'invited_email': email,
                    'invitation_id': str(uuid4()),
                    'invitation_expires_at': invitation_expires_at,
                }
            )
            .execute()
            .data[0]
        )
        membership_id = pending['id']

        # Sign up the invited email — trigger should claim the invite.
        created = supabase_service_client.auth.admin.create_user(
            {
                'email': email,
                'password': 'test-password-123!',
                'email_confirm': True,
            }
        )
        user_id = str(created.user.id)

        org_ids = _list_org_ids_for_user(supabase_service_client, user_id)
        assert org_ids == [inviter_org_id], (
            f'expected user to be in only the inviter org (no personal org); got {org_ids}'
        )

        claimed = (
            supabase_service_client.table('memberships')
            .select('user_id, invited_email, invitation_id, invitation_expires_at')
            .eq('id', membership_id)
            .single()
            .execute()
            .data
        )
        assert claimed['user_id'] == user_id
        assert claimed['invited_email'] is None
        assert claimed['invitation_id'] is None
        assert claimed['invitation_expires_at'] is None
    finally:
        _cleanup(
            supabase_service_client,
            user_id=user_id,
            extra_org_ids=[inviter_org_id] if inviter_org_id else [],
            extra_membership_ids=[membership_id] if membership_id else [],
        )


def test_signup_does_not_claim_expired_invite(
    supabase_service_client: Client,
) -> None:
    email = _unique_email()
    user_id: str | None = None
    inviter_org_id: str | None = None
    membership_id: str | None = None

    try:
        inviter_org = (
            supabase_service_client.table('organizations')
            .insert({'name': f'test-inviter-{uuid4().hex[:8]}'})
            .execute()
            .data[0]
        )
        inviter_org_id = inviter_org['id']

        expired_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        pending = (
            supabase_service_client.table('memberships')
            .insert(
                {
                    'organization_id': inviter_org_id,
                    'user_id': None,
                    'role': 'member',
                    'invited_email': email,
                    'invitation_id': str(uuid4()),
                    'invitation_expires_at': expired_at,
                }
            )
            .execute()
            .data[0]
        )
        membership_id = pending['id']

        created = supabase_service_client.auth.admin.create_user(
            {
                'email': email,
                'password': 'test-password-123!',
                'email_confirm': True,
            }
        )
        user_id = str(created.user.id)

        # Personal org WAS created (expired invite ignored).
        org_ids = _list_org_ids_for_user(supabase_service_client, user_id)
        assert len(org_ids) == 1
        assert org_ids[0] != inviter_org_id

        # Expired invite untouched: user_id still null.
        untouched = (
            supabase_service_client.table('memberships')
            .select('user_id, invited_email')
            .eq('id', membership_id)
            .single()
            .execute()
            .data
        )
        assert untouched['user_id'] is None
        assert untouched['invited_email'] == email
    finally:
        _cleanup(
            supabase_service_client,
            user_id=user_id,
            extra_org_ids=[inviter_org_id] if inviter_org_id else [],
            extra_membership_ids=[membership_id] if membership_id else [],
        )


def test_signup_does_not_claim_soft_deleted_invite(
    supabase_service_client: Client,
) -> None:
    email = _unique_email()
    user_id: str | None = None
    inviter_org_id: str | None = None
    membership_id: str | None = None

    try:
        inviter_org = (
            supabase_service_client.table('organizations')
            .insert({'name': f'test-inviter-{uuid4().hex[:8]}'})
            .execute()
            .data[0]
        )
        inviter_org_id = inviter_org['id']

        invitation_expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        pending = (
            supabase_service_client.table('memberships')
            .insert(
                {
                    'organization_id': inviter_org_id,
                    'user_id': None,
                    'role': 'member',
                    'invited_email': email,
                    'invitation_id': str(uuid4()),
                    'invitation_expires_at': invitation_expires_at,
                    'deleted_at': datetime.now(timezone.utc).isoformat(),
                }
            )
            .execute()
            .data[0]
        )
        membership_id = pending['id']

        created = supabase_service_client.auth.admin.create_user(
            {
                'email': email,
                'password': 'test-password-123!',
                'email_confirm': True,
            }
        )
        user_id = str(created.user.id)

        # Personal org WAS created (soft-deleted invite ignored).
        org_ids = _list_org_ids_for_user(supabase_service_client, user_id)
        assert len(org_ids) == 1
        assert org_ids[0] != inviter_org_id

        # Soft-deleted invite still has user_id null.
        untouched = (
            supabase_service_client.table('memberships')
            .select('user_id, deleted_at')
            .eq('id', membership_id)
            .single()
            .execute()
            .data
        )
        assert untouched['user_id'] is None
        assert untouched['deleted_at'] is not None
    finally:
        _cleanup(
            supabase_service_client,
            user_id=user_id,
            extra_org_ids=[inviter_org_id] if inviter_org_id else [],
            extra_membership_ids=[membership_id] if membership_id else [],
        )


def test_signup_email_match_is_case_insensitive(
    supabase_service_client: Client,
) -> None:
    email_lower = _unique_email()
    email_upper = email_lower.upper()
    user_id: str | None = None
    inviter_org_id: str | None = None
    membership_id: str | None = None

    try:
        inviter_org = (
            supabase_service_client.table('organizations')
            .insert({'name': f'test-inviter-{uuid4().hex[:8]}'})
            .execute()
            .data[0]
        )
        inviter_org_id = inviter_org['id']

        # Invite stored lowercased; sign up with uppercase variant.
        pending = (
            supabase_service_client.table('memberships')
            .insert(
                {
                    'organization_id': inviter_org_id,
                    'user_id': None,
                    'role': 'member',
                    'invited_email': email_lower,
                    'invitation_id': str(uuid4()),
                    'invitation_expires_at': (
                        datetime.now(timezone.utc) + timedelta(days=7)
                    ).isoformat(),
                }
            )
            .execute()
            .data[0]
        )
        membership_id = pending['id']

        created = supabase_service_client.auth.admin.create_user(
            {
                'email': email_upper,
                'password': 'test-password-123!',
                'email_confirm': True,
            }
        )
        user_id = str(created.user.id)

        # Trigger uses lower(invited_email) = lower(new.email), so this should claim.
        claimed = (
            supabase_service_client.table('memberships')
            .select('user_id')
            .eq('id', membership_id)
            .single()
            .execute()
            .data
        )
        assert claimed['user_id'] == user_id
    finally:
        _cleanup(
            supabase_service_client,
            user_id=user_id,
            extra_org_ids=[inviter_org_id] if inviter_org_id else [],
            extra_membership_ids=[membership_id] if membership_id else [],
        )
