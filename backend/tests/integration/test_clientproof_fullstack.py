"""Real HTTP → production auth/access/handlers → PostgREST → PostgreSQL.

Execute through scripts/run_local_acceptance.py --verify. Missing runtime is a
failure, never a skipped integration check. No dependency overrides or doubles.
"""

import json
import os
from datetime import datetime
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest


@pytest.fixture(scope='module')
def runtime():
    required = (
        'CLIENTPROOF_TEST_API_URL',
        'CLIENTPROOF_TEST_CLIENT_TOKEN',
        'CLIENTPROOF_TEST_OWNER_TOKEN',
        'CLIENTPROOF_TEST_FOREIGN_TOKEN',
        'CLIENTPROOF_DATA_TEST_ADMIN_URL',
        'CP_FIXTURE_JSON',
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.fail('Run the owned local acceptance harness; missing ' + ', '.join(missing))
    return json.loads(os.environ['CP_FIXTURE_JSON'])


def request(method, path, role='CLIENT', body=None):
    return httpx.request(
        method,
        os.environ['CLIENTPROOF_TEST_API_URL'] + '/api/v1/clientproof' + path,
        headers={'Authorization': f'Bearer {os.environ[f"CLIENTPROOF_TEST_{role}_TOKEN"]}'},
        json=body,
        timeout=30,
    )


@pytest.mark.parametrize('outcome', ['approved', 'changes_requested'])
def test_real_persisted_decision_history_conflict_and_isolation(runtime, outcome):
    project = runtime['projects'][f'api_{outcome}']
    prefix = f'/projects/{project["project_id"]}'
    version_prefix = f'{prefix}/versions/{project["version_id"]}'
    assert request('GET', prefix).status_code == 200
    assert request('GET', prefix, role='FOREIGN').status_code == 404
    assert request('GET', f'/organizations/{runtime["organization_id"]}/clients').status_code == 403
    comment = f'Сохранённый API комментарий {outcome}'
    response = request('POST', version_prefix + '/comments', body={'body': comment})
    assert response.status_code == 200
    response = request('POST', version_prefix + '/decision', body={'decision': outcome})
    assert response.status_code == 200
    decision_id = response.json()['id']
    retry = request('POST', version_prefix + '/decision', body={'decision': outcome})
    assert retry.status_code == 200
    assert retry.json()['id'] == decision_id
    conflict = 'changes_requested' if outcome == 'approved' else 'approved'
    assert (
        request('POST', version_prefix + '/decision', body={'decision': conflict}).status_code
        == 409
    )
    history = request('GET', version_prefix + '/decisions')
    assert history.status_code == 200
    assert [row['id'] for row in history.json()] == [decision_id]
    assert request('GET', version_prefix + '/decisions', role='FOREIGN').status_code == 404
    # A new HTTP client/read proves persisted server state, not browser cache.
    assert comment in [row['body'] for row in request('GET', version_prefix + '/comments').json()]
    with psycopg.connect(os.environ['CLIENTPROOF_DATA_TEST_ADMIN_URL']) as connection:
        row = connection.execute(
            'select decision, active from approval_decisions where id=%s', (decision_id,)
        ).fetchone()
        assert row == (outcome, True)
        assert (
            connection.execute(
                'select count(*) from comments where project_id=%s and body=%s',
                (project['project_id'], comment),
            ).fetchone()[0]
            == 1
        )
        # Actual signup personal organization remains; external user is never agency member.
        assert (
            connection.execute(
                'select count(*) from memberships where user_id=%s and organization_id=%s',
                (runtime['users']['client']['id'], runtime['organization_id']),
            ).fetchone()[0]
            == 0
        )

        assert (
            connection.execute(
                'select count(*) from memberships where user_id=%s',
                (runtime['users']['client']['id'],),
            ).fetchone()[0]
            == 1
        )
    revoke = request('POST', prefix + f'/grants/{project["grant_id"]}/revoke', role='OWNER')
    assert revoke.status_code == 200
    assert request('GET', prefix).status_code == 404
    assert request('GET', version_prefix + '/decisions').status_code == 404
    assert request('POST', version_prefix + '/comments', body={'body': 'denied'}).status_code == 404


def test_real_anonymous_clientproof_tables_are_denied(runtime):
    # Genuine PostgREST JWT/RLS boundary, distinct from backend application scope.
    base = os.environ['SUPABASE_TEST_URL']
    headers = {
        'apikey': os.environ['CP_ANON_KEY'],
        'Authorization': 'Bearer ' + os.environ['CP_ANON_KEY'],
    }
    for table in ('projects', 'clients', 'project_grants', 'comments', 'approval_decisions'):
        response = httpx.get(base + f'/rest/v1/{table}?select=id', headers=headers, timeout=15)
        assert response.status_code in (200, 401, 403)
        if response.status_code == 200:
            assert response.json() == []


def owner_request(method, path, body=None):
    response = request(method, path, role='OWNER', body=body)
    assert response.status_code == 200, f'{method} {path}: {response.status_code}'
    return response.json()


def test_real_client_project_crud_and_optional_deadline(runtime):
    organization = runtime['organization_id']
    clients_path = f'/organizations/{organization}/clients'
    created = owner_request(
        'POST',
        clients_path,
        {
            'external_auth_user_id': runtime['users']['foreign']['id'],
            'email': runtime['users']['foreign']['email'],
            'display_name': 'Новый клиент ' + uuid4().hex,
        },
    )
    edited = owner_request(
        'PATCH',
        f'/clients/{created["id"]}?organization_id={organization}',
        {
            'display_name': 'Отредактированный клиент',
        },
    )
    assert edited['display_name'] == 'Отредактированный клиент'
    listed = owner_request('GET', clients_path)
    assert any(
        row['id'] == created['id'] and row['display_name'] == edited['display_name']
        for row in listed
    )
    project = owner_request(
        'POST',
        f'/organizations/{organization}/projects',
        {
            'client_id': created['id'],
            'name': 'Проект без срока',
        },
    )
    assert project['response_deadline_at'] is None
    prefix = f'/projects/{project["id"]}'
    deadline = '2030-01-02T12:00:00Z'
    updated = owner_request(
        'PATCH',
        prefix,
        {
            'name': 'Изменённый проект',
            'description': 'Сохранённое описание',
            'response_deadline_at': deadline,
        },
    )
    assert updated['name'] == 'Изменённый проект'
    assert datetime.fromisoformat(updated['response_deadline_at']) == datetime.fromisoformat(
        deadline
    )
    reloaded = owner_request('GET', prefix)
    assert reloaded['name'] == updated['name']
    assert reloaded['description'] == 'Сохранённое описание'
    cleared = owner_request('PATCH', prefix, {'response_deadline_at': None})
    assert cleared['response_deadline_at'] is None
    assert owner_request('GET', prefix)['response_deadline_at'] is None
    with psycopg.connect(os.environ['CLIENTPROOF_DATA_TEST_ADMIN_URL']) as connection:
        assert (
            connection.execute(
                'select display_name from clients where id=%s', (created['id'],)
            ).fetchone()[0]
            == 'Отредактированный клиент'
        )
        assert connection.execute(
            'select name, response_deadline_at from projects where id=%s', (project['id'],)
        ).fetchone() == ('Изменённый проект', None)


def test_real_new_version_preserves_old_history_without_inheriting_approval(runtime):
    organization = runtime['organization_id']
    project = owner_request(
        'POST',
        f'/organizations/{organization}/projects',
        {
            'client_id': runtime['client_id'],
            'name': 'Согласование версий ' + uuid4().hex,
        },
    )
    prefix = f'/projects/{project["id"]}'
    owner_request('POST', prefix + '/grants', {'client_id': runtime['client_id']})
    deliverable = owner_request('POST', prefix + '/deliverables', {'name': 'Макет с историей'})
    version_path = prefix + f'/deliverables/{deliverable["id"]}/versions'
    first = owner_request(
        'POST', version_path, {'title': 'Версия 1', 'content': 'Первое содержимое'}
    )
    first_path = prefix + f'/versions/{first["id"]}'
    owner_request('POST', first_path + '/publish')
    comment = 'Комментарий остаётся у первой версии'
    assert request('POST', first_path + '/comments', body={'body': comment}).status_code == 200
    decision = request('POST', first_path + '/decision', body={'decision': 'approved'})
    assert decision.status_code == 200
    second = owner_request(
        'POST', version_path, {'title': 'Версия 2', 'content': 'Новое содержимое'}
    )
    second_path = prefix + f'/versions/{second["id"]}'
    owner_request('POST', second_path + '/publish')
    assert owner_request('GET', prefix)['status'] == 'in_review'
    assert request('GET', second_path + '/decisions').json() == []
    assert request('GET', second_path + '/comments').json() == []
    history = request('GET', first_path + '/decisions')
    assert history.status_code == 200
    assert [row['id'] for row in history.json()] == [decision.json()['id']]
    # Architecture defines one active decision per version. Publishing v2
    # preserves v1's own decision, while v2 has no inherited decision above.
    assert history.json()[0]['version_id'] == first['id']
    assert history.json()[0]['active'] is True
    comments = request('GET', first_path + '/comments')
    assert comments.status_code == 200
    assert [row['body'] for row in comments.json()] == [comment]
    with psycopg.connect(os.environ['CLIENTPROOF_DATA_TEST_ADMIN_URL']) as connection:
        assert connection.execute(
            'select version_id, active from approval_decisions where id=%s',
            (decision.json()['id'],),
        ).fetchone() == (UUID(first['id']), True)
        assert (
            connection.execute(
                'select count(*) from approval_decisions where version_id=%s', (second['id'],)
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    ('role', 'user_kind', 'project_status', 'management_status', 'write_status'),
    [
        ('OWNER', 'owner', 200, 200, 200),
        ('ADMIN', 'agency_admin', 200, 200, 200),
        ('MEMBER', 'agency_member', 200, 403, 200),
        ('INACTIVE', 'inactive_staff', 404, 403, 404),
        ('FOREIGN', 'foreign', 404, 403, 404),
        ('CLIENT', 'client', 200, 403, 403),
    ],
)
def test_real_persisted_staff_role_and_inactive_membership_matrix(
    runtime,
    role,
    user_kind,
    project_status,
    management_status,
    write_status,
):
    project = runtime['projects']['browser_approved']
    prefix = f'/projects/{project["project_id"]}'
    assert request('GET', prefix, role=role).status_code == project_status
    assert (
        request(
            'GET',
            f'/organizations/{runtime["organization_id"]}/clients',
            role=role,
        ).status_code
        == management_status
    )
    # Listing is available to staff and returns only the caller's active grant
    # for external clients; only issuing/revoking grants requires admin.
    grants = request('GET', prefix + '/grants', role=role)
    assert grants.status_code == project_status
    if role == 'CLIENT':
        assert {row['client_id'] for row in grants.json()} == {runtime['client_id']}
    if management_status == 403:
        assert request(
            'POST',
            prefix + '/grants',
            role=role,
            body={'client_id': runtime['client_id']},
        ).status_code == (403 if project_status == 200 else 404)
    name = f'Результат проверки роли {role} {uuid4().hex}'
    created = request('POST', prefix + '/deliverables', role=role, body={'name': name})
    assert created.status_code == write_status
    with psycopg.connect(os.environ['CLIENTPROOF_DATA_TEST_ADMIN_URL']) as connection:
        assert connection.execute(
            'select count(*) from deliverables where project_id=%s and name=%s',
            (project['project_id'], name),
        ).fetchone()[0] == (1 if write_status == 200 else 0)
        memberships = connection.execute(
            'select role, deleted_at is null from memberships where organization_id=%s and user_id=%s',
            (runtime['organization_id'], runtime['users'][user_kind]['id']),
        ).fetchall()
        expected = {
            'OWNER': [('owner', True)],
            'ADMIN': [('admin', True)],
            'MEMBER': [('member', True)],
            'INACTIVE': [('admin', False)],
            'FOREIGN': [],
            'CLIENT': [],
        }
        assert memberships == expected[role]
        if role != 'OWNER':
            # Real signup's personal owner organization remains independently
            # of the agency role (or absence of an active agency membership).
            assert (
                connection.execute(
                    "select count(*) from memberships where user_id=%s and organization_id<>%s and role='owner' and deleted_at is null",
                    (runtime['users'][user_kind]['id'], runtime['organization_id']),
                ).fetchone()[0]
                == 1
            )
