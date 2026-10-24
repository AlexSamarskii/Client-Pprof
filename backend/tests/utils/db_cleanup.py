"""
Direct-Postgres cleanup helpers for integration tests.

Use these ONLY when you need to bypass triggers that the supabase client cannot
disable (e.g. `prevent_last_owner_removal`, which blocks DELETE of the sole
owner of an org — including via auth.users cascade).

For all other test cleanup, prefer the supabase service-role client. psycopg is
intentionally isolated to this module so tests don't reach for raw SQL casually.
"""

import os
from collections.abc import Iterable

import psycopg

# Local Supabase Postgres (matches `supabase status` for the in-repo project).
# Override via DATABASE_URL when pointing at a different test instance.
LOCAL_PG_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres')


def purge_test_records(
    *,
    user_ids: Iterable[str] = (),
    organization_ids: Iterable[str] = (),
    membership_ids: Iterable[str] = (),
) -> None:
    """
    Hard-delete the given rows with all triggers disabled for this session.

    Order: explicit memberships → org-scoped memberships + organizations →
    auth users (cascades to public.users). Safe to pass empty iterables — call
    is a no-op if nothing is given.
    """
    user_ids = list(user_ids)
    organization_ids = list(organization_ids)
    membership_ids = list(membership_ids)

    if not (user_ids or organization_ids or membership_ids):
        return

    with psycopg.connect(LOCAL_PG_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SET session_replication_role = 'replica'")
        for mid in membership_ids:
            cur.execute('DELETE FROM public.memberships WHERE id = %s', (mid,))
        for oid in organization_ids:
            cur.execute('DELETE FROM public.memberships WHERE organization_id = %s', (oid,))
            cur.execute('DELETE FROM public.organizations WHERE id = %s', (oid,))
        for uid in user_ids:
            cur.execute('DELETE FROM auth.users WHERE id = %s', (uid,))
