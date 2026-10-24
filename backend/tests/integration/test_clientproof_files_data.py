import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest


MIGRATION_PATH = (
    Path(__file__).parents[2] / 'supabase/migrations/20260320000000_clientproof_schema.sql'
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
    database_name = f'clientproof_files_data_test_{uuid.uuid4().hex}'
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
        connection.execute(MIGRATION_PATH.read_text())
        yield connection
        connection.execute('drop schema public cascade')
        connection.execute('create schema public')


def _create_organization(connection: psycopg.Connection) -> uuid.UUID:
    organization_id = uuid.uuid4()
    connection.execute(
        'insert into organizations (id, name, billing_is_paid, billing_plan_key) '
        "values (%s, %s, true, 'agency')",
        (organization_id, f'org-{organization_id}'),
    )
    return organization_id


def _create_client(connection: psycopg.Connection, organization_id: uuid.UUID) -> uuid.UUID:
    client_id = uuid.uuid4()
    external_user_id = uuid.uuid4()
    connection.execute(
        'insert into auth.users (id, email) values (%s, %s)',
        (external_user_id, f'auth-{external_user_id}@example.invalid'),
    )
    connection.execute(
        """
        insert into clients (id, organization_id, external_auth_user_id, email)
        values (%s, %s, %s, %s)
        """,
        (client_id, organization_id, external_user_id, f'client-{client_id}@example.invalid'),
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
        insert into projects (id, organization_id, client_id, name, response_deadline_at)
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
        insert into deliverables (id, organization_id, project_id, name, position)
        values (%s, %s, %s, %s, 1)
        """,
        (deliverable_id, organization_id, project_id, f'deliverable-{deliverable_id}'),
    )
    return deliverable_id


def _create_draft_version(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    deliverable_id: uuid.UUID,
) -> uuid.UUID:
    version_id = uuid.uuid4()
    connection.execute(
        """
        insert into deliverable_versions (
          id, organization_id, project_id, deliverable_id, title, content, version_number
        )
        values (
          %s, %s, %s, %s, %s, %s,
          coalesce(
            (select max(version_number)
             from deliverable_versions
             where project_id = %s),
            0
          ) + 1
        )
        """,
        (
            version_id,
            organization_id,
            project_id,
            deliverable_id,
            'Draft',
            'Draft content',
            project_id,
        ),
    )
    return version_id


def _create_asset(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
) -> uuid.UUID:
    asset_id = uuid.uuid4()
    connection.execute(
        """
        insert into assets (
          id, asset_id, organization_id, filename, storage_key, mime_type, size_bytes, provider
        )
        values (%s, %s, %s, %s, %s, 'image/png', 128, 'local')
        """,
        (
            asset_id,
            asset_id,
            organization_id,
            'result.png',
            f'{organization_id}/projects/{project_id}/{asset_id}',
        ),
    )
    return asset_id


def _create_version_file(
    connection: psycopg.Connection,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    asset_id: uuid.UUID,
    *,
    position: int = 1,
) -> uuid.UUID:
    row = connection.execute(
        """
        insert into deliverable_version_files (
          organization_id, project_id, version_id, asset_id, filename,
          storage_key, mime_type, size_bytes, position
        )
        values (%s, %s, %s, %s, %s, %s, 'image/png', 128, %s)
        returning id
        """,
        (
            organization_id,
            project_id,
            version_id,
            asset_id,
            f'result-{position}.png',
            f'{organization_id}/projects/{project_id}/{asset_id}',
            position,
        ),
    ).fetchone()
    assert row is not None
    return row[0]


def _publish_version(
    connection: psycopg.Connection,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
) -> None:
    result = connection.execute(
        'select public.publish_version_atomic(%s, %s, null)',
        (project_id, version_id),
    ).fetchone()
    assert result is not None and result[0]['kind'] == 'published'


def test_version_file_keys_and_scope_are_project_private(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    asset_id = _create_asset(connection, organization_id, project_id)
    file_id = _create_version_file(connection, organization_id, project_id, version_id, asset_id)

    row = connection.execute(
        """
        select storage_key, is_public, mime_type, size_bytes, position
        from deliverable_version_files
        where id = %s
        """,
        (file_id,),
    ).fetchone()
    assert row is not None
    expected_key = f'{organization_id}/projects/{project_id}/{asset_id}'
    assert row[0] == expected_key
    assert row[1:] == (False, 'image/png', 128, 1)

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            """
            insert into deliverable_version_files (
              organization_id, project_id, version_id, asset_id, filename,
              storage_key, mime_type, size_bytes, position, is_public
            )
            values (%s, %s, %s, %s, %s, %s, 'image/png', 128, 2, true)
            """,
            (
                organization_id,
                project_id,
                version_id,
                asset_id,
                'public.png',
                f'{organization_id}/projects/{project_id}/{uuid.uuid4()}',
            ),
        )


def test_version_file_metadata_and_tenant_references_are_constrained(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    other_organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    asset_id = _create_asset(connection, organization_id, project_id)

    common_insert = """
        insert into deliverable_version_files (
          organization_id, project_id, version_id, asset_id, filename,
          storage_key, mime_type, size_bytes, position
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, 1)
    """
    valid_values = (
        organization_id,
        project_id,
        version_id,
        asset_id,
        'result.png',
        f'{organization_id}/projects/{project_id}/{asset_id}',
        'image/png',
        128,
    )
    connection.execute(common_insert, valid_values)

    invalid_cases = [
        (psycopg.errors.CheckViolation, ('small', 'image/png', -1)),
        (psycopg.errors.CheckViolation, ('oversized', 'image/png', 2_147_483_649)),
        (psycopg.errors.CheckViolation, ('empty', '', 128)),
        (psycopg.errors.CheckViolation, ('empty', '   ', 128)),
    ]
    for exception, (_case_name, mime_type, size_bytes) in invalid_cases:
        with pytest.raises(exception):
            connection.execute(
                common_insert,
                valid_values[:-2] + (mime_type, size_bytes),
            )

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            common_insert,
            (
                organization_id,
                project_id,
                version_id,
                asset_id,
                'cross-project.png',
                f'{organization_id}/projects/{uuid.uuid4()}/{asset_id}',
                'image/png',
                128,
            ),
        )
    foreign_project_id = uuid.uuid4()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        connection.execute(
            common_insert,
            (
                other_organization_id,
                foreign_project_id,
                version_id,
                asset_id,
                'cross-tenant.png',
                f'{other_organization_id}/projects/{foreign_project_id}/{asset_id}',
                'image/png',
                128,
            ),
        )

    foreign_project_id = uuid.uuid4()
    foreign_asset_id = _create_asset(
        connection,
        other_organization_id,
        foreign_project_id,
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        connection.execute(
            common_insert,
            (
                organization_id,
                project_id,
                version_id,
                foreign_asset_id,
                'foreign-asset.png',
                f'{organization_id}/projects/{project_id}/{foreign_asset_id}',
                'image/png',
                128,
            ),
        )


def test_published_file_references_cannot_be_mutated_or_detached(
    connection: psycopg.Connection,
) -> None:
    organization_id = _create_organization(connection)
    client_id = _create_client(connection, organization_id)
    project_id = _create_project(connection, organization_id, client_id)
    deliverable_id = _create_deliverable(connection, organization_id, project_id)
    version_id = _create_draft_version(connection, organization_id, project_id, deliverable_id)
    asset_id = _create_asset(connection, organization_id, project_id)
    other_asset_id = _create_asset(connection, organization_id, project_id)
    _create_version_file(connection, organization_id, project_id, version_id, asset_id)
    _publish_version(connection, project_id, version_id)

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            """
            update deliverable_version_files
            set storage_key = %s, updated_at = now()
            where version_id = %s and asset_id = %s
            """,
            (
                f'{organization_id}/projects/{project_id}/{other_asset_id}',
                version_id,
                asset_id,
            ),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            'delete from deliverable_version_files where version_id = %s',
            (version_id,),
        )

    with pytest.raises(
        (psycopg.errors.ForeignKeyViolation, psycopg.errors.RestrictViolation)
    ) as protected_asset:
        connection.execute('delete from assets where id = %s', (asset_id,))
    assert protected_asset.value.sqlstate in {'23503', '23001'}
    assert (
        connection.execute('select count(*) from assets where id=%s', (asset_id,)).fetchone()[0]
        == 1
    )

    row = connection.execute(
        'select asset_id, storage_key from deliverable_version_files where version_id = %s',
        (version_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == asset_id
    assert row[1] == f'{organization_id}/projects/{project_id}/{asset_id}'
