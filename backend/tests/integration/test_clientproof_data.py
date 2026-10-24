import uuid
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Iterator
import threading
from pathlib import Path
import os
import time

import psycopg
import pytest


MIGRATION_PATHS = [
    (Path(__file__).parents[2] / 'supabase/migrations/20260320000000_clientproof_schema.sql'),
    (
        Path(__file__).parents[2]
        / 'supabase/migrations/20260320001000_clientproof_project_activation_quota.sql'
    ),
]
CLIENTPROOF_TABLES = (
    'approval_decisions',
    'audit_events',
    'clients',
    'comments',
    'deliverable_version_files',
    'deliverable_versions',
    'deliverables',
    'plan_entitlements',
    'project_grants',
    'projects',
)
BASELINE_DEPENDENCIES = """
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role; end if;
end $$;

create schema if not exists auth;

create table if not exists auth.users (
  id uuid primary key,
  email text,
  encrypted_password text,
  raw_user_meta_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz
);

create table if not exists organizations (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz,
  deleted_at timestamptz,
  name text not null,
  billing_email text,
  billing_plan_key text,
  billing_is_paid boolean not null default false,
  billing_status text,
  billing_current_period_start timestamptz,
  billing_current_period_end timestamptz,
  billing_cancel_at_period_end boolean not null default false,
  billing_updated_at timestamptz,
  stripe_customer_id text
);

create table if not exists assets (
  id uuid primary key default gen_random_uuid(),
  asset_id uuid not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz,
  deleted_at timestamptz,
  user_id uuid,
  organization_id uuid not null,
  filename text not null,
  storage_key text not null unique,
  thumbnail_url text,
  mime_type text not null,
  status text not null default 'pending',
  size_bytes bigint,
  provider text not null
);
"""


@pytest.fixture(scope='module')
def database_url() -> Iterator[str]:
    admin_url = os.environ.get('CLIENTPROOF_DATA_TEST_ADMIN_URL')
    if not admin_url:
        pytest.fail(
            'Missing CLIENTPROOF_DATA_TEST_ADMIN_URL; point it at a disposable Postgres database.'
        )
    database_name = f'clientproof_data_test_{uuid.uuid4().hex}'
    with psycopg.connect(admin_url, autocommit=True) as admin_connection:
        admin_connection.execute(f'create database {database_name}')
    base_url = admin_url.rsplit('/', 1)[0]
    url = f'{base_url}/{database_name}'
    try:
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin_connection:
            admin_connection.execute(f'drop database if exists {database_name} with (force)')


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute('drop schema public cascade')
        connection.execute('create schema public')
        connection.execute(BASELINE_DEPENDENCIES)
        for migration_path in MIGRATION_PATHS:
            connection.execute(migration_path.read_text())
        yield connection
        connection.execute('drop schema public cascade')
        connection.execute('create schema public')


def _create_user(connection: psycopg.Connection) -> uuid.UUID:
    user_id = uuid.uuid4()
    connection.execute(
        'insert into auth.users (id, email) values (%s, %s)',
        (user_id, f'client-{user_id}@example.invalid'),
    )
    return user_id


def _create_organization(
    connection: psycopg.Connection,
    *,
    paid: bool = True,
    plan_key: str | None = 'studio',
) -> uuid.UUID:
    organization_id = uuid.uuid4()
    connection.execute(
        """
        insert into organizations (id, name, billing_is_paid, billing_plan_key)
        values (%s, %s, %s, %s)
        """,
        (organization_id, f'org-{organization_id}', paid, plan_key),
    )
    return organization_id


def _create_client(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
) -> uuid.UUID:
    user_id = _create_user(connection)
    client_id = uuid.uuid4()
    connection.execute(
        """
        insert into clients (id, organization_id, external_auth_user_id, email)
        values (%s, %s, %s, %s)
        """,
        (client_id, organization_id, user_id, f'client-{user_id}@example.invalid'),
    )
    return client_id


def _create_project(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    client_id: uuid.UUID,
) -> uuid.UUID:
    project_id = uuid.uuid4()
    connection.execute(
        """
        insert into projects (
          id, organization_id, client_id, name, response_deadline_at
        )
        values (%s, %s, %s, %s, now() + interval '7 days')
        """,
        (project_id, organization_id, client_id, f'project-{project_id}'),
    )
    return project_id


def _create_deliverable(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
) -> uuid.UUID:
    deliverable_id = uuid.uuid4()
    connection.execute(
        """
        insert into deliverables (id, organization_id, project_id, name)
        values (%s, %s, %s, %s)
        """,
        (deliverable_id, organization_id, project_id, f'deliverable-{deliverable_id}'),
    )
    return deliverable_id


def _create_draft_version(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    *,
    version_number: int = 1,
) -> uuid.UUID:
    version_id = uuid.uuid4()
    connection.execute(
        """
        insert into deliverable_versions (
          id, organization_id, project_id, deliverable_id, version_number, title, content
        )
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            version_id,
            organization_id,
            project_id,
            deliverable_id,
            version_number,
            f'Version {version_number}',
            'Review this version.',
        ),
    )
    return version_id


def _publish_version(
    connection: psycopg.Connection,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    staff_user_id: uuid.UUID | None = None,
) -> dict[str, object]:
    row = connection.execute(
        'select public.publish_version_atomic(%s, %s, %s) as result',
        (project_id, version_id, staff_user_id),
    ).fetchone()
    assert row is not None
    return row[0]


def _create_asset(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    filename: str = 'result.png',
) -> tuple[uuid.UUID, str]:
    asset_id = uuid.uuid4()
    storage_key = f'{organization_id}/projects/{project_id}/{asset_id}/{filename}'
    connection.execute(
        """
        insert into assets (
          id, asset_id, organization_id, filename, storage_key,
          mime_type, status, size_bytes, provider
        )
        values (%s, %s, %s, %s, %s, 'image/png', 'uploaded', 8, 'r2')
        """,
        (asset_id, asset_id, organization_id, filename, storage_key),
    )
    return asset_id, storage_key


def _create_file_reference(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
) -> tuple[uuid.UUID, str]:
    asset_id, storage_key = _create_asset(connection, organization_id, project_id)
    file_id = uuid.uuid4()
    connection.execute(
        """
        insert into deliverable_version_files (
          id, organization_id, project_id, version_id, asset_id,
          filename, storage_key, mime_type, size_bytes, position
        )
        values (%s, %s, %s, %s, %s, %s, %s, 'image/png', 8, 1)
        """,
        (file_id, organization_id, project_id, version_id, asset_id, 'result.png', storage_key),
    )
    return file_id, storage_key


def _create_grant(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    client_id: uuid.UUID,
) -> uuid.UUID:
    grant_id = uuid.uuid4()
    connection.execute(
        """
        insert into project_grants (
          id, organization_id, project_id, client_id, status
        )
        values (%s, %s, %s, %s, 'active')
        """,
        (grant_id, organization_id, project_id, client_id),
    )
    return grant_id


def _plan_limits(connection: psycopg.Connection) -> list[tuple[str, int]]:
    return list(
        connection.execute(
            'select plan_key, active_project_limit from plan_entitlements order by plan_key'
        ).fetchall()
    )


def _decision_result(
    database_url: str,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    client_id: uuid.UUID,
    decision_kind: str,
) -> dict[str, object]:
    with psycopg.connect(database_url) as session:
        row = session.execute(
            'select public.submit_decision_atomic(%s, %s, %s, %s) as result',
            (project_id, version_id, client_id, decision_kind),
        ).fetchone()
    assert row is not None
    return row[0]


def _create_project_result(
    database_url: str,
    organization_id: uuid.UUID,
    client_id: uuid.UUID,
    project_name: str,
) -> dict[str, object]:
    with psycopg.connect(database_url) as session:
        row = session.execute(
            'select public.create_project_atomic(%s, %s, %s, null, now() + %s::interval) as result',
            (organization_id, client_id, project_name, '7 days'),
        ).fetchone()
    assert row is not None
    return row[0]


def _activate_project_result(
    database_url: str,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    archived: bool,
    actor_user_id: uuid.UUID,
) -> dict[str, object]:
    with psycopg.connect(database_url) as session:
        row = session.execute(
            'select public.set_project_archived_atomic(%s, %s, %s, %s) as result',
            (project_id, organization_id, archived, actor_user_id),
        ).fetchone()
    assert row is not None
    return row[0]


def test_plan_entitlements_match_product_limits(
    connection: psycopg.Connection,
) -> None:
    assert _plan_limits(connection) == [
        ('agency', 100),
        ('studio', 5),
        ('team', 25),
    ]


@pytest.mark.parametrize('plan_key,limit', [('studio', 5), ('team', 25), ('agency', 100)])
def test_project_quota_is_atomic_and_unmapped_paid_plan_is_zero(
    connection: psycopg.Connection,
    database_url: str,
    plan_key: str,
    limit: int,
) -> None:
    organization_id = _create_organization(connection, paid=True, plan_key=plan_key)
    client_id = _create_client(connection, organization_id)
    for _ in range(limit - 1):
        result = connection.execute(
            'select public.create_project_atomic(%s, %s, %s, null, now() + %s::interval)',
            (organization_id, client_id, f'project-{uuid.uuid4()}', '7 days'),
        ).fetchone()
        assert result is not None and result[0]['kind'] == 'created'

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda number: _create_project_result(
                    database_url,
                    organization_id,
                    client_id,
                    f'quota-race-{number}',
                ),
                range(2),
            )
        )
    assert [result['kind'] for result in results].count('created') == 1
    assert [result['kind'] for result in results].count('quota_conflict') == 1
    assert all(
        result['limit'] == limit and result['active_count'] == limit
        for result in results
        if result['kind'] == 'quota_conflict'
    )

    unmapped_organization = _create_organization(
        connection, paid=True, plan_key='enterprise-custom'
    )
    unmapped_client = _create_client(connection, unmapped_organization)
    unmapped_result = connection.execute(
        'select public.create_project_atomic(%s, %s, %s, null, now() + %s::interval)',
        (unmapped_organization, unmapped_client, 'unmapped-plan', '7 days'),
    ).fetchone()
    assert unmapped_result is not None
    assert unmapped_result[0]['kind'] == 'quota_conflict'



@pytest.mark.parametrize('plan_key', ['studio', 'team', 'agency', None])
def test_unpaid_organization_cannot_create_active_project(
    connection: psycopg.Connection,
    plan_key: str | None,
) -> None:
    organization_id = _create_organization(connection, paid=False, plan_key=plan_key)
    client_id = _create_client(connection, organization_id)
    result = connection.execute(
        'select public.create_project_atomic(%s, %s, %s, null, now() + %s::interval)',
        (organization_id, client_id, 'unpaid-denied', '7 days'),
    ).fetchone()
    assert result is not None and result[0]['kind'] == 'quota_conflict'
    assert result[0]['limit'] == 0
    row = connection.execute(
        'select count(*) from projects where organization_id=%s', (organization_id,)
    ).fetchone()
    assert row is not None and row[0] == 0


def test_unarchive_is_quota_bound_and_serialized_by_org_lock(
    connection: psycopg.Connection,
    database_url: str,
) -> None:
    organization_id = _create_organization(connection, paid=True, plan_key='studio')
    client_id = _create_client(connection, organization_id)
    created = [
        _create_project_result(
            database_url,
            organization_id,
            client_id,
            f'activation-{number}',
        )
        for number in range(5)
    ]
    assert [result['kind'] for result in created] == ['created'] * 5
    project_ids = [uuid.UUID(str(result['project_id'])) for result in created]

    archived = _activate_project_result(
        database_url,
        organization_id,
        project_ids[-1],
        archived=True,
        actor_user_id=_create_user(connection),
    )
    assert archived['kind'] == 'archived'

    replacement = _create_project_result(
        database_url,
        organization_id,
        client_id,
        'activation-replacement',
    )
    assert replacement['kind'] == 'created'

    quota_conflict = _activate_project_result(
        database_url,
        organization_id,
        project_ids[-1],
        archived=False,
        actor_user_id=_create_user(connection),
    )
    assert quota_conflict['kind'] == 'quota_conflict'
    assert quota_conflict['limit'] == 5
    assert quota_conflict['active_count'] == 5

    connection.execute(
        'update projects set archived_at = now() where id = %s',
        (uuid.UUID(str(replacement['project_id'])),),
    )
    unarchived = _activate_project_result(
        database_url,
        organization_id,
        project_ids[-1],
        archived=False,
        actor_user_id=_create_user(connection),
    )
    assert unarchived['kind'] == 'unarchived'
    row = connection.execute(
        'select archived_at, audit_events.event_type '
        'from projects join audit_events on audit_events.project_id = projects.id '
        "where projects.id = %s and audit_events.event_type = 'project.unarchived'",
        (project_ids[-1],),
    ).fetchone()
    assert row is not None and row[0] is None and row[1] == 'project.unarchived'


def test_project_response_deadline_is_optional(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = uuid.uuid4()
    connection.execute(
        """
        insert into projects (id, organization_id, client_id, name)
        values (%s, %s, %s, 'no-deadline')
        """,
        (project_id, organization_id, client_id),
    )

    row = connection.execute(
        'select public.create_project_atomic(%s, %s, %s, null, null) as result',
        (organization_id, client_id, 'rpc-no-deadline'),
    ).fetchone()
    assert row is not None
    assert row[0]['kind'] == 'created'

    deadlines = list(
        connection.execute(
            'select response_deadline_at from projects where organization_id = %s order by created_at',
            (organization_id,),
        ).fetchall()
    )
    assert all(deadline[0] is None for deadline in deadlines)


def test_project_and_grant_records_cannot_cross_tenant_boundaries(
    connection: psycopg.Connection,
) -> None:
    first_organization = _create_organization(connection)
    second_organization = _create_organization(connection)
    first_client = _create_client(connection, first_organization)
    second_client = _create_client(connection, second_organization)
    second_project = _create_project(connection, second_organization, second_client)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        connection.execute(
            'insert into projects (organization_id, client_id, name, response_deadline_at)'
            " values (%s, %s, 'cross-tenant', now() + interval '7 days')",
            (first_organization, second_client),
        )

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _create_grant(connection, first_organization, second_project, first_client)


def test_clientproof_tables_are_deny_by_default(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    _create_project(connection, organization_id, client_id)

    metadata = list(
        connection.execute(
            """
            select relname, relrowsecurity, relforcerowsecurity
            from pg_class
            where relnamespace = 'public'::regnamespace
              and relname = any(%s)
            order by relname
            """,
            (list(CLIENTPROOF_TABLES),),
        ).fetchall()
    )
    assert metadata == [(name, True, True) for name in sorted(CLIENTPROOF_TABLES)]

    policies = list(
        connection.execute(
            """
            select tablename, policyname, roles
            from pg_policies
            where schemaname = 'public' and tablename = any(%s)
            order by tablename, policyname
            """,
            (list(CLIENTPROOF_TABLES),),
        ).fetchall()
    )
    assert len(policies) == len(CLIENTPROOF_TABLES)
    assert all(roles == ['service_role'] for _, _, roles in policies)

    table_names = ', '.join(f'(select count(*) from public.{name})' for name in CLIENTPROOF_TABLES)
    connection.execute('grant usage on schema public to authenticated')
    for name in CLIENTPROOF_TABLES:
        connection.execute(f'grant select on public.{name} to authenticated')
    with connection.transaction():
        connection.execute('set local role authenticated')
        counts = connection.execute(f'select {table_names}').fetchone()
    assert counts == (0,) * len(CLIENTPROOF_TABLES)


def test_published_version_and_file_references_are_immutable(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    file_id, _ = _create_file_reference(connection, organization_id, project_id, version_id)

    connection.execute(
        'update deliverable_version_files set filename = %s where id = %s',
        ('draft-replacement.png', file_id),
    )
    result = _publish_version(connection, project_id, version_id)
    assert result['kind'] == 'published'

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            'update deliverable_versions set content = %s where id = %s',
            ('tampered', version_id),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            'update deliverable_version_files set position = %s where id = %s',
            (2, file_id),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute('delete from deliverable_versions where id = %s', (version_id,))
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute('delete from deliverable_version_files where id = %s', (file_id,))


def test_comments_and_decisions_require_published_version(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    draft_version_id = _create_draft_version(
        connection, organization_id, project_id, deliverable_id
    )

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            """
            insert into comments (
              organization_id, project_id, version_id, author_client_id, body
            )
            values (%s, %s, %s, %s, 'not allowed on a draft')
            """,
            (organization_id, project_id, draft_version_id, client_id),
        )


def test_decision_rpc_is_idempotent_then_conflicts_on_alternative_outcome(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    accepting_client = _create_client(connection, organization_id)
    conflicting_client = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, accepting_client)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    _create_grant(connection, organization_id, project_id, accepting_client)
    _create_grant(connection, organization_id, project_id, conflicting_client)

    assert _publish_version(connection, project_id, version_id)['kind'] == 'published'
    row = connection.execute(
        'select public.submit_decision_atomic(%s, %s, %s, %s) as result',
        (project_id, version_id, accepting_client, 'approved'),
    ).fetchone()
    assert row is not None
    first_result = row[0]
    assert first_result['kind'] == 'created'

    retry_row = connection.execute(
        'select public.submit_decision_atomic(%s, %s, %s, %s) as result',
        (project_id, version_id, accepting_client, 'approved'),
    ).fetchone()
    assert retry_row is not None
    retry_result = retry_row[0]
    assert retry_result['kind'] == 'idempotent'
    assert retry_result['decision_id'] == first_result['decision_id']

    conflict_row = connection.execute(
        'select public.submit_decision_atomic(%s, %s, %s, %s) as result',
        (project_id, version_id, conflicting_client, 'changes_requested'),
    ).fetchone()
    assert conflict_row is not None
    conflict_result = conflict_row[0]
    assert conflict_result['kind'] == 'decision_conflict'
    assert conflict_result['decision_id'] == first_result['decision_id']

    project_status = connection.execute(
        'select status from projects where id = %s', (project_id,)
    ).fetchone()
    assert project_status is not None and project_status[0] == 'approved'
    active_decision_count = connection.execute(
        'select count(*) from approval_decisions where version_id = %s and active', (version_id,)
    ).fetchone()
    assert active_decision_count is not None and active_decision_count[0] == 1


def test_concurrent_decisions_allow_exactly_one_outcome(
    connection: psycopg.Connection,
    database_url: str,
) -> None:
    organization_id = _create_organization(connection)
    accepting_client = _create_client(connection, organization_id)
    conflicting_client = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, accepting_client)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    _create_grant(connection, organization_id, project_id, accepting_client)
    _create_grant(connection, organization_id, project_id, conflicting_client)
    assert _publish_version(connection, project_id, version_id)['kind'] == 'published'

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _decision_result,
                database_url,
                project_id,
                version_id,
                client_id,
                decision_kind,
            )
            for client_id, decision_kind in (
                (accepting_client, 'approved'),
                (conflicting_client, 'changes_requested'),
            )
        ]
        results = [future.result() for future in futures]

    assert [result['kind'] for result in results].count('created') == 1
    assert [result['kind'] for result in results].count('decision_conflict') == 1
    created_result, conflict_result = sorted(results, key=lambda result: result['kind'])
    assert conflict_result['decision_id'] == created_result['decision_id']

    state = connection.execute(
        """
        select p.status, count(ad.id) filter (where ad.active)
        from projects p
        left join approval_decisions ad on ad.version_id = %s
        where p.id = %s
        group by p.status
        """,
        (version_id, project_id),
    ).fetchone()
    assert state is not None
    assert state[1] == 1


def test_revoked_grant_is_rejected_by_atomic_decision_path(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    _create_grant(connection, organization_id, project_id, client_id)
    _publish_version(connection, project_id, version_id)
    connection.execute(
        """
        update project_grants
        set status = 'revoked', revoked_at = now()
        where project_id = %s and client_id = %s
        """,
        (project_id, client_id),
    )

    row = connection.execute(
        'select public.submit_decision_atomic(%s, %s, %s, %s) as result',
        (project_id, version_id, client_id, 'approved'),
    ).fetchone()
    assert row is not None
    assert row[0]['kind'] == 'access_denied'


def test_revoked_grant_before_decision_commit_does_not_create_decision(
    connection: psycopg.Connection,
    database_url: str,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    _create_grant(connection, organization_id, project_id, client_id)
    assert _publish_version(connection, project_id, version_id)['kind'] == 'published'

    with connection.transaction():
        connection.execute(
            """
            update project_grants
            set status = 'revoked', revoked_at = now()
            where project_id = %s and client_id = %s
            """,
            (project_id, client_id),
        )

    with psycopg.connect(database_url) as decision_connection:
        row = decision_connection.execute(
            'select public.submit_decision_atomic(%s, %s, %s, %s) as result',
            (project_id, version_id, client_id, 'approved'),
        ).fetchone()

    assert row is not None
    assert row[0]['kind'] == 'access_denied'
    state = connection.execute(
        """
        select p.status, count(ad.id) filter (where ad.active)
        from projects p
        left join approval_decisions ad on ad.version_id = %s
        where p.id = %s
        group by p.status
        """,
        (version_id, project_id),
    ).fetchone()
    assert state is not None and state[0] == 'in_review' and state[1] == 0


def test_active_grant_lock_serializes_revocation_during_decision(
    connection: psycopg.Connection,
    database_url: str,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    _create_grant(connection, organization_id, project_id, client_id)
    assert _publish_version(connection, project_id, version_id)['kind'] == 'published'

    revocation_started = threading.Event()

    def revoke_active_grant() -> str:
        with psycopg.connect(database_url) as revocation_connection:
            with revocation_connection.transaction():
                revocation_started.set()
                revocation_connection.execute(
                    """
                    update project_grants
                    set status = 'revoked', revoked_at = now()
                    where project_id = %s and client_id = %s
                    """,
                    (project_id, client_id),
                )
        return 'revoked'

    with ThreadPoolExecutor(max_workers=1) as executor:
        with psycopg.connect(database_url) as decision_connection:
            with decision_connection.transaction():
                row = decision_connection.execute(
                    'select public.submit_decision_atomic(%s, %s, %s, %s) as result',
                    (project_id, version_id, client_id, 'approved'),
                ).fetchone()
                assert row is not None and row[0]['kind'] == 'created'

                revocation_future = executor.submit(revoke_active_grant)
                assert revocation_started.wait(timeout=5)
                for _ in range(50):
                    if revocation_future.done():
                        break
                    time.sleep(0.02)
                assert not revocation_future.done()

    assert revocation_future.result() == 'revoked'
    state = connection.execute(
        """
        select g.status, count(ad.id) filter (where ad.active)
        from project_grants g
        cross join projects p
        left join approval_decisions ad on ad.version_id = %s
        where g.project_id = p.id and p.id = %s
        group by g.status
        """,
        (version_id, project_id),
    ).fetchone()
    assert state is not None and state[0] == 'revoked' and state[1] == 1


def test_audit_events_record_required_context_and_are_append_only(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    staff_user_id = _create_user(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    _create_grant(connection, organization_id, project_id, client_id)

    _publish_version(connection, project_id, version_id, staff_user_id)
    connection.execute(
        'select public.submit_decision_atomic(%s, %s, %s, %s)',
        (project_id, version_id, client_id, 'approved'),
    )
    events = list(
        connection.execute(
            """
            select event_type, actor_kind, actor_user_id, actor_client_id,
                   organization_id, project_id, version_id, occurred_at
            from audit_events
            order by occurred_at
            """
        ).fetchall()
    )
    assert [event[0] for event in events] == ['version.published', 'decision.approved']
    assert events[0][1:3] == ('staff', staff_user_id)
    assert events[1][1:4] == ('client', None, client_id)
    assert all(event[4] == organization_id and event[5] == project_id for event in events)
    assert all(event[6] == version_id for event in events)

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            'update audit_events set event_type = %s where event_type = %s',
            ('tampered', 'version.published'),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute('delete from audit_events where event_type = %s', ('decision.approved',))


def test_archiving_does_not_delete_review_history(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    _create_grant(connection, organization_id, project_id, client_id)
    _publish_version(connection, project_id, version_id)
    connection.execute(
        'select public.submit_decision_atomic(%s, %s, %s, %s)',
        (project_id, version_id, client_id, 'changes_requested'),
    )

    connection.execute(
        'update projects set archived_at = now(), status = status where id = %s',
        (project_id,),
    )
    connection.execute(
        'update deliverables set archived_at = now() where id = %s',
        (deliverable_id,),
    )
    archived = connection.execute(
        """
        select p.status, p.archived_at, count(distinct av.id), count(distinct c.id)
        from projects p
        left join deliverable_versions dv on dv.project_id = p.id
        left join approval_decisions av on av.version_id = dv.id
        left join comments c on c.version_id = dv.id
        where p.id = %s
        group by p.status, p.archived_at
        """,
        (project_id,),
    ).fetchone()
    assert archived is not None
    assert archived[0] == 'changes_requested'
    assert archived[2] == 1
    assert archived[3] == 0
