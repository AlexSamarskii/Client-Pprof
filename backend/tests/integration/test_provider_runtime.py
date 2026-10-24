"""Real private object transfer and immutable published references; no storage/API doubles."""

import json
import os
import time
from uuid import uuid4

import boto3
import httpx
import psycopg
import pytest


def api(method, path, body=None, role='OWNER'):
    return httpx.request(
        method,
        os.environ['CLIENTPROOF_TEST_API_URL'] + '/api/v1/clientproof' + path,
        headers={'Authorization': 'Bearer ' + os.environ[f'CLIENTPROOF_TEST_{role}_TOKEN']},
        json=body,
        timeout=30,
    )


def test_real_private_upload_seals_published_content_and_denies_foreign_access():
    if not os.environ.get('CP_S3_ENDPOINT'):
        pytest.fail('Run owned local acceptance with genuine private S3-compatible storage')
    fixture = json.loads(os.environ['CP_FIXTURE_JSON'])
    project = api(
        'POST',
        f'/organizations/{fixture["organization_id"]}/projects',
        {'client_id': fixture['client_id'], 'name': 'Приватный файл ' + uuid4().hex},
    ).json()
    prefix = f'/projects/{project["id"]}'
    grant_response = api('POST', prefix + '/grants', {'client_id': fixture['client_id']})
    assert grant_response.status_code == 200
    deliverable_response = api('POST', prefix + '/deliverables', {'name': 'Файл результата'})
    assert deliverable_response.status_code == 200
    deliverable = deliverable_response.json()
    version_response = api(
        'POST',
        prefix + f'/deliverables/{deliverable["id"]}/versions',
        {'title': 'Версия с файлом', 'content': 'Неизменяемый результат'},
    )
    assert version_response.status_code == 200
    version = version_response.json()
    original = b'original-private-result'
    upload_body = {
        'deliverable_id': deliverable['id'],
        'version_id': version['id'],
        'filename': 'proof.txt',
        'mime_type': 'text/plain',
        'size_bytes': len(original),
    }
    for invalid in ({'size_bytes': 0}, {'size_bytes': 2_147_483_649}, {'mime_type': 'x'}):
        assert api('POST', prefix + '/files/uploads', upload_body | invalid).status_code == 422
    assert api('POST', prefix + '/files/uploads', upload_body, role='CLIENT').status_code == 403
    assert httpx.post(
        os.environ['CLIENTPROOF_TEST_API_URL'] + '/api/v1/clientproof' + prefix + '/files/uploads',
        json=upload_body,
        timeout=30,
    ).status_code == 401
    upload_response = api(
        'POST',
        prefix + '/files/uploads',
        {
            'deliverable_id': deliverable['id'],
            'version_id': version['id'],
            'filename': 'proof.txt',
            'mime_type': 'text/plain',
            'size_bytes': len(original),
        },
    )
    assert upload_response.status_code == 200
    upload = upload_response.json()
    assert upload['storage_key'].startswith(
        f'{fixture["organization_id"]}/projects/{project["id"]}/'
    )
    completion_path = prefix + f'/files/uploads/{upload["asset_id"]}/complete'
    completion_body = {'deliverable_id': deliverable['id'], 'version_id': version['id']}
    assert httpx.put(
        upload['upload_url'], content=original + b'x',
        headers={'Content-Type': 'text/plain'}, timeout=30,
    ).is_success
    rejected = api('POST', completion_path, completion_body)
    assert rejected.status_code == 422 and rejected.json()['detail']['kind'] == 'asset_size_mismatch'
    # Owned storage operator writes genuine mismatched metadata to the staging object.
    s3 = boto3.client(
        's3', endpoint_url=os.environ['CP_S3_ENDPOINT'],
        aws_access_key_id=os.environ['CLOUDFLARE_ACCESS_KEY'],
        aws_secret_access_key=os.environ['CLOUDFLARE_SECRET_ACCESS_KEY'],
        region_name='us-east-1',
    )
    s3.put_object(
        Bucket=os.environ['CLOUDFLARE_R2_BUCKET'], Key=upload['storage_key'],
        Body=original, ContentType='application/octet-stream',
    )
    rejected = api('POST', completion_path, completion_body)
    assert rejected.status_code == 422
    assert rejected.json()['detail']['kind'] == 'asset_content_type_mismatch'
    with psycopg.connect(os.environ['CLIENTPROOF_DATA_TEST_ADMIN_URL']) as connection:
        assert connection.execute(
            'select count(*) from deliverable_version_files where version_id=%s', (version['id'],)
        ).fetchone() == (0,)
    assert httpx.put(
        upload['upload_url'], content=original, headers={'Content-Type': 'text/plain'}, timeout=30
    ).is_success
    # Anonymous object GET without a signature is denied by the actual object store.
    assert httpx.get(upload['upload_url'].split('?')[0], timeout=30).status_code in (401, 403)
    completion = api(
        'POST',
        prefix + f'/files/uploads/{upload["asset_id"]}/complete',
        {'deliverable_id': deliverable['id'], 'version_id': version['id']},
    )
    assert completion.status_code == 200, completion.text
    file_id = completion.json()['id']
    assert api('POST', prefix + f'/versions/{version["id"]}/publish').status_code == 200
    assert api('GET', prefix + f'/files/{file_id}/link', role='FOREIGN').status_code == 404
    link = api('GET', prefix + f'/files/{file_id}/link', role='CLIENT')
    assert link.status_code == 200
    assert 0 < link.json()['expires_in_seconds'] <= 300
    assert httpx.get(link.json()['url'], timeout=30).content == original
    # Replaying the original still-valid PUT may replace staging only, never sealed content.
    assert httpx.put(
        upload['upload_url'],
        content=b'replaced',
        headers={'Content-Type': 'text/plain'},
        timeout=30,
    ).is_success
    assert httpx.get(link.json()['url'], timeout=30).content == original
    assert api(
        'POST',
        prefix + f'/files/uploads/{upload["asset_id"]}/complete',
        {'deliverable_id': deliverable['id'], 'version_id': version['id']},
    ).status_code in (404, 409)
    assert api('POST', prefix + f'/grants/{grant_response.json()["id"]}/revoke').status_code == 200
    assert api('GET', prefix + f'/files/{file_id}/link', role='CLIENT').status_code == 404
    with psycopg.connect(os.environ['CLIENTPROOF_DATA_TEST_ADMIN_URL']) as connection:
        row = connection.execute(
            "select actor_kind, actor_user_id, actor_client_id, occurred_at from audit_events where project_id=%s and event_type='grant.revoked'",
            (project['id'],),
        ).fetchone()
        assert row is not None and row[0] == 'staff' and row[1] is not None and row[2] is None
        assert row[3].tzinfo is not None
    # Genuine object store enforces the originally issued signed URL's expiry.
    # The harness injects a shorter real TTL; the production default remains 300.
    time.sleep(link.json()['expires_in_seconds'] + 1)
    assert httpx.get(link.json()['url'], timeout=30).status_code in (401, 403)


def test_hosted_r2_runtime_private_signed_url():
    required = ['CLIENTPROOF_HOSTED_R2_UPLOAD_URL', 'CLIENTPROOF_HOSTED_R2_READ_URL']
    if not all(os.environ.get(name) for name in required):
        pytest.skip(
            'pending_environment: short-lived upload/read URLs for a disposable private hosted R2 test object, injected in memory'
        )
    data = b'clientproof-hosted-r2-runtime'
    upload_url, read_url = (os.environ[name] for name in required)
    assert '.r2.cloudflarestorage.com/' in upload_url and '.r2.cloudflarestorage.com/' in read_url
    assert httpx.put(
        upload_url, content=data, headers={'Content-Type': 'text/plain'}, timeout=30
    ).is_success
    assert httpx.get(read_url, timeout=30).content == data
    assert httpx.get(read_url.split('?')[0], timeout=30).status_code in (401, 403)
