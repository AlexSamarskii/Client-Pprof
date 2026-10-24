"""Real Stripe signature verification; endpoint doubles are explicitly local unit evidence."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.v1 import stripe as routes
from app.stripe import webhooks

# Synthetic test material, never a provider credential.
TEST_SIGNING_VALUE = 'local-signature-fixture'


def signed_payload(event_id='evt_local_signature', event_type='customer.subscription.updated'):
    payload = json.dumps(
        {
            'id': event_id,
            'object': 'event',
            'type': event_type,
            'livemode': False,
            'data': {
                'object': {
                    'id': 'sub_local',
                    'object': 'subscription',
                    'metadata': {},
                    'customer': 'cus_local',
                }
            },
        }
    ).encode()
    return payload


def signature(payload, secret=TEST_SIGNING_VALUE, timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(
        secret.encode(), str(timestamp).encode() + b'.' + payload, hashlib.sha256
    ).hexdigest()
    return f't={timestamp},v1={digest}'


def test_webhook_signed_payload_is_verified(monkeypatch):
    monkeypatch.setattr(webhooks, 'STRIPE_WEBHOOK_SECRET', TEST_SIGNING_VALUE)
    payload = signed_payload()
    event = webhooks.construct_event(payload=payload, signature=signature(payload))
    summary = webhooks.summarize_event(event)
    assert summary.event_id == 'evt_local_signature'
    assert summary.livemode is False


@pytest.mark.parametrize('case', ['missing', 'wrong', 'tampered', 'expired', 'malformed'])
def test_webhook_rejects_untrusted_payload(monkeypatch, case):
    monkeypatch.setattr(webhooks, 'STRIPE_WEBHOOK_SECRET', TEST_SIGNING_VALUE)
    payload = signed_payload()
    header = signature(payload)
    if case == 'missing':
        header = ''
    if case == 'wrong':
        header = signature(payload, secret='different-local-fixture')
    if case == 'tampered':
        payload += b' '
    if case == 'expired':
        header = signature(payload, timestamp=int(time.time()) - 600)
    if case == 'malformed':
        header = 'invalid'
    with pytest.raises(ValueError):
        webhooks.construct_event(payload=payload, signature=header)


def test_webhook_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(webhooks, 'STRIPE_WEBHOOK_SECRET', None)
    with pytest.raises(ValueError):
        webhooks.construct_event(payload=signed_payload(), signature='invalid')


@pytest.mark.parametrize('first_failure', [False, True])
def test_webhook_endpoint_repeat_and_failed_retry(monkeypatch, first_failure):
    monkeypatch.setattr(webhooks, 'STRIPE_WEBHOOK_SECRET', TEST_SIGNING_VALUE)
    organization_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(), organization_id=organization_id, processed_at=None, processing_error=None
    )
    calls = []

    def process(**kwargs):
        assert kwargs['organization_id'] == organization_id
        calls.append('attempt')
        if first_failure and len(calls) == 1:
            raise RuntimeError('synthetic transient failure')

    def mark_processed(**kwargs):
        row.processed_at = datetime.now(timezone.utc)
        row.processing_error = None

    def mark_failed(**kwargs):
        row.processing_error = kwargs['error_message']

    monkeypatch.setattr(routes, 'get_or_create_webhook_event_row', lambda **kwargs: (row, False))
    monkeypatch.setattr(routes, 'resolve_organization_id', lambda **kwargs: None)
    monkeypatch.setattr(routes, 'handle_customer_subscription_event', process)
    monkeypatch.setattr(routes, 'mark_event_processed', mark_processed)
    monkeypatch.setattr(routes, 'mark_event_failed', mark_failed)
    app = FastAPI()
    app.include_router(routes.webhook_router)
    app.dependency_overrides[routes.get_supabase_client] = lambda: object()
    payload = signed_payload()
    with TestClient(app) as client:
        first = client.post(
            '/stripe/webhook', content=payload, headers={'Stripe-Signature': signature(payload)}
        )
        assert first.status_code == (500 if first_failure else 200)
        second = client.post(
            '/stripe/webhook', content=payload, headers={'Stripe-Signature': signature(payload)}
        )
        assert second.status_code == 200
        third = client.post(
            '/stripe/webhook', content=payload, headers={'Stripe-Signature': signature(payload)}
        )
        assert third.status_code == 200
    assert len(calls) == (2 if first_failure else 1)
    assert row.processed_at is not None and row.processing_error is None


def test_webhook_endpoint_denies_unsigned_before_persistence(monkeypatch):
    def must_not_persist(**kwargs):
        raise AssertionError('untrusted input reached persistence')

    monkeypatch.setattr(routes, 'get_or_create_webhook_event_row', must_not_persist)
    app = FastAPI()
    app.include_router(routes.webhook_router)
    app.dependency_overrides[routes.get_supabase_client] = lambda: object()
    with TestClient(app) as client:
        assert client.post('/stripe/webhook', content=signed_payload()).status_code == 400
