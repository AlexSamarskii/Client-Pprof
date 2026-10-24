"""Persisted webhook receipt/signature/idempotency; hosted Stripe test-mode stays separate."""

import hashlib
import hmac
import json
import os
import time
from uuid import uuid4

import httpx
import pytest


def test_webhook_repeat_delivery_persists_one_processed_event(supabase_service_client):
    base = os.environ.get('CLIENTPROOF_TEST_API_URL')
    signing_value = os.environ.get('STRIPE_WEBHOOK_SECRET')
    if not base or not signing_value:
        pytest.fail('Run scripts/run_local_acceptance.py --verify for owned webhook runtime')
    organization_id = str(uuid4())
    supabase_service_client.table('organizations').insert(
        {
            'id': organization_id,
            'name': 'Disposable webhook tenant',
            'billing_is_paid': True,
            'billing_plan_key': 'team',
        }
    ).execute()
    event_id = 'evt_local_' + uuid4().hex
    subscription_id = 'sub_local_' + uuid4().hex
    payload = json.dumps(
        {
            'id': event_id,
            'object': 'event',
            'type': 'customer.subscription.deleted',
            'livemode': False,
            'data': {
                'object': {
                    'id': subscription_id,
                    'object': 'subscription',
                    'status': 'canceled',
                    'customer': 'cus_local_' + uuid4().hex,
                    'cancel_at_period_end': False,
                    'items': {
                        'object': 'list',
                        'data': [
                            {
                                'id': 'si_local',
                                'price': {
                                    'id': 'price_local',
                                    'object': 'price',
                                    'product': 'prod_local',
                                },
                            }
                        ],
                    },
                    'metadata': {'organization_id': organization_id},
                }
            },
        }
    ).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(
        signing_value.encode(), timestamp.encode() + b'.' + payload, hashlib.sha256
    ).hexdigest()
    headers = {'Stripe-Signature': f't={timestamp},v1={digest}'}
    url = base + '/api/v1/stripe/webhook'
    # Follow actual mounted route; both deliveries hit production signature and persistence handlers.
    first_subscription = None
    for _ in range(2):
        response = httpx.post(url, content=payload, headers=headers, timeout=30)
        assert response.status_code == 200, response.text
        subscriptions = (
            supabase_service_client.table('subscriptions')
            .select('*')
            .eq('stripe_subscription_id', subscription_id)
            .execute()
            .data
        )
        assert len(subscriptions) == 1 and subscriptions[0]['status'] == 'canceled'
        if first_subscription is None:
            first_subscription = subscriptions[0]
        else:
            assert subscriptions[0] == first_subscription, (
                'Duplicate changed subscription/business effects'
            )
    # A distinct later signed event updates persisted business state. Replaying
    # the earlier processed event must not roll that newer state back.
    later_event = json.loads(payload)
    later_event['id'] = 'evt_local_later_' + uuid4().hex
    later_event['data']['object']['ended_at'] = int(time.time()) + 30
    later_payload = json.dumps(later_event).encode()
    later_digest = hmac.new(
        signing_value.encode(), timestamp.encode() + b'.' + later_payload, hashlib.sha256
    ).hexdigest()
    response = httpx.post(
        url,
        content=later_payload,
        headers={'Stripe-Signature': f't={timestamp},v1={later_digest}'},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    latest = (
        supabase_service_client.table('subscriptions')
        .select('*')
        .eq('stripe_subscription_id', subscription_id)
        .execute()
        .data[0]
    )
    assert latest['ended_at'] is not None and latest != first_subscription
    assert httpx.post(url, content=payload, headers=headers, timeout=30).status_code == 200
    assert (
        supabase_service_client.table('subscriptions')
        .select('*')
        .eq('stripe_subscription_id', subscription_id)
        .execute()
        .data[0]
        == latest
    )
    organization = (
        supabase_service_client.table('organizations')
        .select('billing_is_paid,billing_status')
        .eq('id', organization_id)
        .execute()
        .data[0]
    )
    assert organization['billing_is_paid'] is False and organization['billing_status'] == 'canceled'
    rows = (
        supabase_service_client.table('stripe_webhook_events')
        .select('*')
        .eq('stripe_event_id', event_id)
        .execute()
        .data
    )
    assert len(rows) == 1
    assert rows[0]['processed_at'] is not None and rows[0]['processing_error'] is None
    assert rows[0]['organization_id'] == organization_id
    assert httpx.post(url, content=payload + b' ', headers=headers, timeout=30).status_code == 400
    assert (
        len(
            supabase_service_client.table('stripe_webhook_events')
            .select('id')
            .eq('stripe_event_id', event_id)
            .execute()
            .data
        )
        == 1
    )


def test_stripe_runtime_checkout_portal_test_mode():
    required = [
        'CLIENTPROOF_STRIPE_RUNTIME_API_URL',
        'CLIENTPROOF_STRIPE_RUNTIME_OWNER_TOKEN',
        'CLIENTPROOF_STRIPE_RUNTIME_ORGANIZATION_ID',
        'CLIENTPROOF_STRIPE_RUNTIME_CATALOG_KEY',
        'CLIENTPROOF_STRIPE_TEST_SECRET',
    ]
    if not all(os.environ.get(name) for name in required):
        pytest.skip(
            'pending_environment: dedicated test-mode application API, owner session, tenant/catalog and Stripe test account injected in memory'
        )
    secret = os.environ['CLIENTPROOF_STRIPE_TEST_SECRET']
    assert secret.startswith('sk_test_'), 'Live Stripe credentials are prohibited'
    base = os.environ[required[0]] + '/api/v1/org/' + os.environ[required[2]] + '/stripe'
    headers = {'Authorization': 'Bearer ' + os.environ[required[1]]}
    # These are the actual retained application endpoints, not direct provider substitutes.
    checkout = httpx.post(
        base + '/checkout-session',
        headers=headers,
        json={
            'catalog_key': os.environ[required[3]],
            'success_url': 'http://127.0.0.1:5173/projects',
            'cancel_url': 'http://127.0.0.1:5173/upgrade',
        },
        timeout=60,
    )
    assert checkout.status_code == 200, 'Application checkout endpoint failed'
    assert checkout.json()['url'].startswith('https://checkout.stripe.com/')
    import stripe

    provider = stripe.StripeClient(secret)
    session = provider.v1.checkout.sessions.retrieve(checkout.json()['id'])
    assert session.livemode is False and session.mode == 'subscription'
    assert session.metadata['organization_id'] == os.environ[required[2]]
    portal = httpx.post(
        base + '/billing-portal-session',
        headers=headers,
        json={'return_url': 'http://127.0.0.1:5173/upgrade'},
        timeout=60,
    )
    assert portal.status_code == 200, 'Application portal endpoint failed'
    assert portal.json()['url'].startswith('https://billing.stripe.com/')
    # No payment/subscription is completed, no purchase is made. Actual signed event
    # subscription persistence/repeat behavior is a separate genuine DB test above.
