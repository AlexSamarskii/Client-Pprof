from __future__ import annotations

import datetime
import uuid
from typing import (
    Annotated,
    Any,
    List,
    Literal,
    NotRequired,
    Optional,
    TypeAlias,
    TypedDict,
)

from pydantic import BaseModel, Field

NetRequestStatus: TypeAlias = Literal['PENDING', 'SUCCESS', 'ERROR']

RealtimeEqualityOp: TypeAlias = Literal['eq', 'neq', 'lt', 'lte', 'gt', 'gte', 'in']

RealtimeAction: TypeAlias = Literal['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'ERROR']

StorageBuckettype: TypeAlias = Literal['STANDARD', 'ANALYTICS', 'VECTOR']

AuthFactorType: TypeAlias = Literal['totp', 'webauthn', 'phone']

AuthFactorStatus: TypeAlias = Literal['unverified', 'verified']

AuthAalLevel: TypeAlias = Literal['aal1', 'aal2', 'aal3']

AuthCodeChallengeMethod: TypeAlias = Literal['s256', 'plain']

AuthOneTimeTokenType: TypeAlias = Literal[
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token',
]

AuthOauthRegistrationType: TypeAlias = Literal['dynamic', 'manual']

AuthOauthAuthorizationStatus: TypeAlias = Literal['pending', 'approved', 'denied', 'expired']

AuthOauthResponseType: TypeAlias = Literal['code']

AuthOauthClientType: TypeAlias = Literal['public', 'confidential']


class PublicUsers(BaseModel):
    additional_data: dict[str, Any] = Field(alias='additional_data')
    avatar_url: Optional[str] = Field(alias='avatar_url')
    created_at: datetime.datetime = Field(alias='created_at')
    deleted_at: Optional[datetime.datetime] = Field(alias='deleted_at')
    email: str = Field(alias='email')
    full_name: Optional[str] = Field(alias='full_name')
    id: uuid.UUID = Field(alias='id')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')
    username: Optional[str] = Field(alias='username')


class PublicUsersInsert(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    avatar_url: NotRequired[Annotated[Optional[str], Field(alias='avatar_url')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    email: Annotated[str, Field(alias='email')]
    full_name: NotRequired[Annotated[Optional[str], Field(alias='full_name')]]
    id: Annotated[uuid.UUID, Field(alias='id')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    username: NotRequired[Annotated[Optional[str], Field(alias='username')]]


class PublicUsersUpdate(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    avatar_url: NotRequired[Annotated[Optional[str], Field(alias='avatar_url')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    email: NotRequired[Annotated[str, Field(alias='email')]]
    full_name: NotRequired[Annotated[Optional[str], Field(alias='full_name')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    username: NotRequired[Annotated[Optional[str], Field(alias='username')]]


class PublicOrganizations(BaseModel):
    additional_data: dict[str, Any] = Field(alias='additional_data')
    billing_cancel_at_period_end: bool = Field(alias='billing_cancel_at_period_end')
    billing_current_period_end: Optional[datetime.datetime] = Field(
        alias='billing_current_period_end'
    )
    billing_current_period_start: Optional[datetime.datetime] = Field(
        alias='billing_current_period_start'
    )
    billing_email: Optional[str] = Field(alias='billing_email')
    billing_is_paid: bool = Field(alias='billing_is_paid')
    billing_plan_key: Optional[str] = Field(alias='billing_plan_key')
    billing_status: Optional[str] = Field(alias='billing_status')
    billing_updated_at: Optional[datetime.datetime] = Field(alias='billing_updated_at')
    created_at: datetime.datetime = Field(alias='created_at')
    deleted_at: Optional[datetime.datetime] = Field(alias='deleted_at')
    id: uuid.UUID = Field(alias='id')
    name: str = Field(alias='name')
    stripe_customer_id: Optional[str] = Field(alias='stripe_customer_id')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicOrganizationsInsert(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    billing_cancel_at_period_end: NotRequired[
        Annotated[bool, Field(alias='billing_cancel_at_period_end')]
    ]
    billing_current_period_end: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='billing_current_period_end')]
    ]
    billing_current_period_start: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='billing_current_period_start')]
    ]
    billing_email: NotRequired[Annotated[Optional[str], Field(alias='billing_email')]]
    billing_is_paid: NotRequired[Annotated[bool, Field(alias='billing_is_paid')]]
    billing_plan_key: NotRequired[Annotated[Optional[str], Field(alias='billing_plan_key')]]
    billing_status: NotRequired[Annotated[Optional[str], Field(alias='billing_status')]]
    billing_updated_at: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='billing_updated_at')]
    ]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    name: Annotated[str, Field(alias='name')]
    stripe_customer_id: NotRequired[Annotated[Optional[str], Field(alias='stripe_customer_id')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicOrganizationsUpdate(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    billing_cancel_at_period_end: NotRequired[
        Annotated[bool, Field(alias='billing_cancel_at_period_end')]
    ]
    billing_current_period_end: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='billing_current_period_end')]
    ]
    billing_current_period_start: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='billing_current_period_start')]
    ]
    billing_email: NotRequired[Annotated[Optional[str], Field(alias='billing_email')]]
    billing_is_paid: NotRequired[Annotated[bool, Field(alias='billing_is_paid')]]
    billing_plan_key: NotRequired[Annotated[Optional[str], Field(alias='billing_plan_key')]]
    billing_status: NotRequired[Annotated[Optional[str], Field(alias='billing_status')]]
    billing_updated_at: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='billing_updated_at')]
    ]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    name: NotRequired[Annotated[str, Field(alias='name')]]
    stripe_customer_id: NotRequired[Annotated[Optional[str], Field(alias='stripe_customer_id')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicMemberships(BaseModel):
    additional_data: dict[str, Any] = Field(alias='additional_data')
    created_at: datetime.datetime = Field(alias='created_at')
    deleted_at: Optional[datetime.datetime] = Field(alias='deleted_at')
    id: uuid.UUID = Field(alias='id')
    invitation_expires_at: Optional[datetime.datetime] = Field(alias='invitation_expires_at')
    invitation_id: Optional[str] = Field(alias='invitation_id')
    invited_by_id: Optional[uuid.UUID] = Field(alias='invited_by_id')
    invited_email: Optional[str] = Field(alias='invited_email')
    organization_id: uuid.UUID = Field(alias='organization_id')
    role: str = Field(alias='role')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')
    user_id: Optional[uuid.UUID] = Field(alias='user_id')


class PublicMembershipsInsert(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    invitation_expires_at: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='invitation_expires_at')]
    ]
    invitation_id: NotRequired[Annotated[Optional[str], Field(alias='invitation_id')]]
    invited_by_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='invited_by_id')]]
    invited_email: NotRequired[Annotated[Optional[str], Field(alias='invited_email')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    role: NotRequired[Annotated[str, Field(alias='role')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='user_id')]]


class PublicMembershipsUpdate(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    invitation_expires_at: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='invitation_expires_at')]
    ]
    invitation_id: NotRequired[Annotated[Optional[str], Field(alias='invitation_id')]]
    invited_by_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='invited_by_id')]]
    invited_email: NotRequired[Annotated[Optional[str], Field(alias='invited_email')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    role: NotRequired[Annotated[str, Field(alias='role')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='user_id')]]


class PublicSubscriptions(BaseModel):
    additional_data: dict[str, Any] = Field(alias='additional_data')
    cancel_at_period_end: bool = Field(alias='cancel_at_period_end')
    cancel_request_at: Optional[datetime.datetime] = Field(alias='cancel_request_at')
    created_at: datetime.datetime = Field(alias='created_at')
    current_period_end: Optional[datetime.datetime] = Field(alias='current_period_end')
    current_period_start: Optional[datetime.datetime] = Field(alias='current_period_start')
    deleted_at: Optional[datetime.datetime] = Field(alias='deleted_at')
    ended_at: Optional[datetime.datetime] = Field(alias='ended_at')
    id: uuid.UUID = Field(alias='id')
    organization_id: uuid.UUID = Field(alias='organization_id')
    status: str = Field(alias='status')
    stripe_customer_id: Optional[str] = Field(alias='stripe_customer_id')
    stripe_price_id: str = Field(alias='stripe_price_id')
    stripe_product_id: str = Field(alias='stripe_product_id')
    stripe_subscription_id: str = Field(alias='stripe_subscription_id')
    stripe_subscription_item_id: Optional[str] = Field(alias='stripe_subscription_item_id')
    trial_end: Optional[datetime.datetime] = Field(alias='trial_end')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicSubscriptionsInsert(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    cancel_at_period_end: NotRequired[Annotated[bool, Field(alias='cancel_at_period_end')]]
    cancel_request_at: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='cancel_request_at')]
    ]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    current_period_end: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='current_period_end')]
    ]
    current_period_start: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='current_period_start')]
    ]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    ended_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='ended_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    status: Annotated[str, Field(alias='status')]
    stripe_customer_id: NotRequired[Annotated[Optional[str], Field(alias='stripe_customer_id')]]
    stripe_price_id: Annotated[str, Field(alias='stripe_price_id')]
    stripe_product_id: Annotated[str, Field(alias='stripe_product_id')]
    stripe_subscription_id: Annotated[str, Field(alias='stripe_subscription_id')]
    stripe_subscription_item_id: NotRequired[
        Annotated[Optional[str], Field(alias='stripe_subscription_item_id')]
    ]
    trial_end: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='trial_end')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicSubscriptionsUpdate(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    cancel_at_period_end: NotRequired[Annotated[bool, Field(alias='cancel_at_period_end')]]
    cancel_request_at: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='cancel_request_at')]
    ]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    current_period_end: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='current_period_end')]
    ]
    current_period_start: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='current_period_start')]
    ]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    ended_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='ended_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    stripe_customer_id: NotRequired[Annotated[Optional[str], Field(alias='stripe_customer_id')]]
    stripe_price_id: NotRequired[Annotated[str, Field(alias='stripe_price_id')]]
    stripe_product_id: NotRequired[Annotated[str, Field(alias='stripe_product_id')]]
    stripe_subscription_id: NotRequired[Annotated[str, Field(alias='stripe_subscription_id')]]
    stripe_subscription_item_id: NotRequired[
        Annotated[Optional[str], Field(alias='stripe_subscription_item_id')]
    ]
    trial_end: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='trial_end')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicStripeWebhookEvents(BaseModel):
    additional_data: dict[str, Any] = Field(alias='additional_data')
    created_at: datetime.datetime = Field(alias='created_at')
    id: uuid.UUID = Field(alias='id')
    livemode: bool = Field(alias='livemode')
    organization_id: Optional[uuid.UUID] = Field(alias='organization_id')
    payload: dict[str, Any] = Field(alias='payload')
    processed_at: Optional[datetime.datetime] = Field(alias='processed_at')
    processing_error: Optional[str] = Field(alias='processing_error')
    received_at: datetime.datetime = Field(alias='received_at')
    stripe_customer_id: Optional[str] = Field(alias='stripe_customer_id')
    stripe_event_id: str = Field(alias='stripe_event_id')
    type: str = Field(alias='type')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicStripeWebhookEventsInsert(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    livemode: Annotated[bool, Field(alias='livemode')]
    organization_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='organization_id')]]
    payload: NotRequired[Annotated[dict[str, Any], Field(alias='payload')]]
    processed_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='processed_at')]]
    processing_error: NotRequired[Annotated[Optional[str], Field(alias='processing_error')]]
    received_at: NotRequired[Annotated[datetime.datetime, Field(alias='received_at')]]
    stripe_customer_id: NotRequired[Annotated[Optional[str], Field(alias='stripe_customer_id')]]
    stripe_event_id: Annotated[str, Field(alias='stripe_event_id')]
    type: Annotated[str, Field(alias='type')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicStripeWebhookEventsUpdate(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    livemode: NotRequired[Annotated[bool, Field(alias='livemode')]]
    organization_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='organization_id')]]
    payload: NotRequired[Annotated[dict[str, Any], Field(alias='payload')]]
    processed_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='processed_at')]]
    processing_error: NotRequired[Annotated[Optional[str], Field(alias='processing_error')]]
    received_at: NotRequired[Annotated[datetime.datetime, Field(alias='received_at')]]
    stripe_customer_id: NotRequired[Annotated[Optional[str], Field(alias='stripe_customer_id')]]
    stripe_event_id: NotRequired[Annotated[str, Field(alias='stripe_event_id')]]
    type: NotRequired[Annotated[str, Field(alias='type')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicAssets(BaseModel):
    asset_id: uuid.UUID = Field(alias='asset_id')
    created_at: datetime.datetime = Field(alias='created_at')
    deleted_at: Optional[datetime.datetime] = Field(alias='deleted_at')
    filename: str = Field(alias='filename')
    id: uuid.UUID = Field(alias='id')
    mime_type: str = Field(alias='mime_type')
    organization_id: uuid.UUID = Field(alias='organization_id')
    provider: str = Field(alias='provider')
    size_bytes: Optional[int] = Field(alias='size_bytes')
    status: str = Field(alias='status')
    storage_key: str = Field(alias='storage_key')
    thumbnail_url: Optional[str] = Field(alias='thumbnail_url')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')
    user_id: Optional[uuid.UUID] = Field(alias='user_id')


class PublicAssetsInsert(TypedDict):
    asset_id: Annotated[uuid.UUID, Field(alias='asset_id')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    filename: Annotated[str, Field(alias='filename')]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    mime_type: Annotated[str, Field(alias='mime_type')]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    provider: Annotated[str, Field(alias='provider')]
    size_bytes: NotRequired[Annotated[Optional[int], Field(alias='size_bytes')]]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    storage_key: Annotated[str, Field(alias='storage_key')]
    thumbnail_url: NotRequired[Annotated[Optional[str], Field(alias='thumbnail_url')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='user_id')]]


class PublicAssetsUpdate(TypedDict):
    asset_id: NotRequired[Annotated[uuid.UUID, Field(alias='asset_id')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    filename: NotRequired[Annotated[str, Field(alias='filename')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    mime_type: NotRequired[Annotated[str, Field(alias='mime_type')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    provider: NotRequired[Annotated[str, Field(alias='provider')]]
    size_bytes: NotRequired[Annotated[Optional[int], Field(alias='size_bytes')]]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    storage_key: NotRequired[Annotated[str, Field(alias='storage_key')]]
    thumbnail_url: NotRequired[Annotated[Optional[str], Field(alias='thumbnail_url')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='user_id')]]


class PublicStripeCatalogItems(BaseModel):
    additional_data: dict[str, Any] = Field(alias='additional_data')
    billing_interval: Optional[str] = Field(alias='billing_interval')
    billing_interval_count: Optional[int] = Field(alias='billing_interval_count')
    billing_type: str = Field(alias='billing_type')
    created_at: datetime.datetime = Field(alias='created_at')
    default_stripe_coupon_id: Optional[str] = Field(alias='default_stripe_coupon_id')
    deleted_at: Optional[datetime.datetime] = Field(alias='deleted_at')
    description: Optional[str] = Field(alias='description')
    feature_set: List[str] = Field(alias='feature_set')
    id: uuid.UUID = Field(alias='id')
    key: str = Field(alias='key')
    name: Optional[str] = Field(alias='name')
    override_stripe_coupon_id: Optional[str] = Field(alias='override_stripe_coupon_id')
    plan_family: Optional[str] = Field(alias='plan_family')
    rank: Optional[int] = Field(alias='rank')
    stripe_price_id: str = Field(alias='stripe_price_id')
    stripe_product_id: str = Field(alias='stripe_product_id')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicStripeCatalogItemsInsert(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    billing_interval: NotRequired[Annotated[Optional[str], Field(alias='billing_interval')]]
    billing_interval_count: NotRequired[
        Annotated[Optional[int], Field(alias='billing_interval_count')]
    ]
    billing_type: Annotated[str, Field(alias='billing_type')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    default_stripe_coupon_id: NotRequired[
        Annotated[Optional[str], Field(alias='default_stripe_coupon_id')]
    ]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    description: NotRequired[Annotated[Optional[str], Field(alias='description')]]
    feature_set: NotRequired[Annotated[List[str], Field(alias='feature_set')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    key: Annotated[str, Field(alias='key')]
    name: NotRequired[Annotated[Optional[str], Field(alias='name')]]
    override_stripe_coupon_id: NotRequired[
        Annotated[Optional[str], Field(alias='override_stripe_coupon_id')]
    ]
    plan_family: NotRequired[Annotated[Optional[str], Field(alias='plan_family')]]
    rank: NotRequired[Annotated[Optional[int], Field(alias='rank')]]
    stripe_price_id: Annotated[str, Field(alias='stripe_price_id')]
    stripe_product_id: Annotated[str, Field(alias='stripe_product_id')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicStripeCatalogItemsUpdate(TypedDict):
    additional_data: NotRequired[Annotated[dict[str, Any], Field(alias='additional_data')]]
    billing_interval: NotRequired[Annotated[Optional[str], Field(alias='billing_interval')]]
    billing_interval_count: NotRequired[
        Annotated[Optional[int], Field(alias='billing_interval_count')]
    ]
    billing_type: NotRequired[Annotated[str, Field(alias='billing_type')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    default_stripe_coupon_id: NotRequired[
        Annotated[Optional[str], Field(alias='default_stripe_coupon_id')]
    ]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    description: NotRequired[Annotated[Optional[str], Field(alias='description')]]
    feature_set: NotRequired[Annotated[List[str], Field(alias='feature_set')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    key: NotRequired[Annotated[str, Field(alias='key')]]
    name: NotRequired[Annotated[Optional[str], Field(alias='name')]]
    override_stripe_coupon_id: NotRequired[
        Annotated[Optional[str], Field(alias='override_stripe_coupon_id')]
    ]
    plan_family: NotRequired[Annotated[Optional[str], Field(alias='plan_family')]]
    rank: NotRequired[Annotated[Optional[int], Field(alias='rank')]]
    stripe_price_id: NotRequired[Annotated[str, Field(alias='stripe_price_id')]]
    stripe_product_id: NotRequired[Annotated[str, Field(alias='stripe_product_id')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicJobs(BaseModel):
    created_at: datetime.datetime = Field(alias='created_at')
    data: dict[str, Any] = Field(alias='data')
    external_id: Optional[str] = Field(alias='external_id')
    finished_at: Optional[datetime.datetime] = Field(alias='finished_at')
    id: uuid.UUID = Field(alias='id')
    organization_id: uuid.UUID = Field(alias='organization_id')
    result_data: dict[str, Any] = Field(alias='result_data')
    status: str = Field(alias='status')
    submitted_at: datetime.datetime = Field(alias='submitted_at')
    task: str = Field(alias='task')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')
    user_id: uuid.UUID = Field(alias='user_id')


class PublicJobsInsert(TypedDict):
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    data: NotRequired[Annotated[dict[str, Any], Field(alias='data')]]
    external_id: NotRequired[Annotated[Optional[str], Field(alias='external_id')]]
    finished_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='finished_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    result_data: NotRequired[Annotated[dict[str, Any], Field(alias='result_data')]]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    submitted_at: NotRequired[Annotated[datetime.datetime, Field(alias='submitted_at')]]
    task: Annotated[str, Field(alias='task')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    user_id: Annotated[uuid.UUID, Field(alias='user_id')]


class PublicJobsUpdate(TypedDict):
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    data: NotRequired[Annotated[dict[str, Any], Field(alias='data')]]
    external_id: NotRequired[Annotated[Optional[str], Field(alias='external_id')]]
    finished_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='finished_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    result_data: NotRequired[Annotated[dict[str, Any], Field(alias='result_data')]]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    submitted_at: NotRequired[Annotated[datetime.datetime, Field(alias='submitted_at')]]
    task: NotRequired[Annotated[str, Field(alias='task')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    user_id: NotRequired[Annotated[uuid.UUID, Field(alias='user_id')]]


class PublicPlanEntitlements(BaseModel):
    active: bool = Field(alias='active')
    active_project_limit: int = Field(alias='active_project_limit')
    created_at: datetime.datetime = Field(alias='created_at')
    id: uuid.UUID = Field(alias='id')
    plan_key: str = Field(alias='plan_key')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicPlanEntitlementsInsert(TypedDict):
    active: NotRequired[Annotated[bool, Field(alias='active')]]
    active_project_limit: Annotated[int, Field(alias='active_project_limit')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    plan_key: Annotated[str, Field(alias='plan_key')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicPlanEntitlementsUpdate(TypedDict):
    active: NotRequired[Annotated[bool, Field(alias='active')]]
    active_project_limit: NotRequired[Annotated[int, Field(alias='active_project_limit')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    plan_key: NotRequired[Annotated[str, Field(alias='plan_key')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicClients(BaseModel):
    created_at: datetime.datetime = Field(alias='created_at')
    deleted_at: Optional[datetime.datetime] = Field(alias='deleted_at')
    display_name: Optional[str] = Field(alias='display_name')
    email: Optional[str] = Field(alias='email')
    external_auth_user_id: uuid.UUID = Field(alias='external_auth_user_id')
    id: uuid.UUID = Field(alias='id')
    organization_id: uuid.UUID = Field(alias='organization_id')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicClientsInsert(TypedDict):
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    display_name: NotRequired[Annotated[Optional[str], Field(alias='display_name')]]
    email: NotRequired[Annotated[Optional[str], Field(alias='email')]]
    external_auth_user_id: Annotated[uuid.UUID, Field(alias='external_auth_user_id')]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicClientsUpdate(TypedDict):
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deleted_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='deleted_at')]]
    display_name: NotRequired[Annotated[Optional[str], Field(alias='display_name')]]
    email: NotRequired[Annotated[Optional[str], Field(alias='email')]]
    external_auth_user_id: NotRequired[Annotated[uuid.UUID, Field(alias='external_auth_user_id')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicProjects(BaseModel):
    archived_at: Optional[datetime.datetime] = Field(alias='archived_at')
    archived_by_user_id: Optional[uuid.UUID] = Field(alias='archived_by_user_id')
    client_id: uuid.UUID = Field(alias='client_id')
    created_at: datetime.datetime = Field(alias='created_at')
    description: Optional[str] = Field(alias='description')
    id: uuid.UUID = Field(alias='id')
    name: str = Field(alias='name')
    organization_id: uuid.UUID = Field(alias='organization_id')
    response_deadline_at: Optional[datetime.datetime] = Field(alias='response_deadline_at')
    status: str = Field(alias='status')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicProjectsInsert(TypedDict):
    archived_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='archived_at')]]
    archived_by_user_id: NotRequired[
        Annotated[Optional[uuid.UUID], Field(alias='archived_by_user_id')]
    ]
    client_id: Annotated[uuid.UUID, Field(alias='client_id')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    description: NotRequired[Annotated[Optional[str], Field(alias='description')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    name: Annotated[str, Field(alias='name')]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    response_deadline_at: NotRequired[
        Annotated[Optional[datetime.datetime], Field(alias='response_deadline_at')]
    ]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicProjectsUpdate(TypedDict):
    archived_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='archived_at')]]
    archived_by_user_id: NotRequired[
        Annotated[Optional[uuid.UUID], Field(alias='archived_by_user_id')]
    ]
    client_id: NotRequired[Annotated[uuid.UUID, Field(alias='client_id')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    description: NotRequired[Annotated[Optional[str], Field(alias='description')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    name: NotRequired[Annotated[str, Field(alias='name')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    response_deadline_at: NotRequired[
        Annotated[datetime.datetime, Field(alias='response_deadline_at')]
    ]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicDeliverables(BaseModel):
    archived_at: Optional[datetime.datetime] = Field(alias='archived_at')
    created_at: datetime.datetime = Field(alias='created_at')
    description: Optional[str] = Field(alias='description')
    id: uuid.UUID = Field(alias='id')
    name: str = Field(alias='name')
    organization_id: uuid.UUID = Field(alias='organization_id')
    position: int = Field(alias='position')
    project_id: uuid.UUID = Field(alias='project_id')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicDeliverablesInsert(TypedDict):
    archived_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='archived_at')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    description: NotRequired[Annotated[Optional[str], Field(alias='description')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    name: Annotated[str, Field(alias='name')]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    position: NotRequired[Annotated[int, Field(alias='position')]]
    project_id: Annotated[uuid.UUID, Field(alias='project_id')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicDeliverablesUpdate(TypedDict):
    archived_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='archived_at')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    description: NotRequired[Annotated[Optional[str], Field(alias='description')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    name: NotRequired[Annotated[str, Field(alias='name')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    position: NotRequired[Annotated[int, Field(alias='position')]]
    project_id: NotRequired[Annotated[uuid.UUID, Field(alias='project_id')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicDeliverableVersions(BaseModel):
    content: str = Field(alias='content')
    created_at: datetime.datetime = Field(alias='created_at')
    deliverable_id: uuid.UUID = Field(alias='deliverable_id')
    id: uuid.UUID = Field(alias='id')
    organization_id: uuid.UUID = Field(alias='organization_id')
    project_id: uuid.UUID = Field(alias='project_id')
    published_at: Optional[datetime.datetime] = Field(alias='published_at')
    published_by_user_id: Optional[uuid.UUID] = Field(alias='published_by_user_id')
    review_seq: Optional[int] = Field(alias='review_seq')
    title: str = Field(alias='title')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')
    version_number: int = Field(alias='version_number')


class PublicDeliverableVersionsInsert(TypedDict):
    content: Annotated[str, Field(alias='content')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deliverable_id: Annotated[uuid.UUID, Field(alias='deliverable_id')]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    project_id: Annotated[uuid.UUID, Field(alias='project_id')]
    published_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='published_at')]]
    published_by_user_id: NotRequired[
        Annotated[Optional[uuid.UUID], Field(alias='published_by_user_id')]
    ]
    review_seq: NotRequired[Annotated[Optional[int], Field(alias='review_seq')]]
    title: Annotated[str, Field(alias='title')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    version_number: Annotated[int, Field(alias='version_number')]


class PublicDeliverableVersionsUpdate(TypedDict):
    content: NotRequired[Annotated[str, Field(alias='content')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    deliverable_id: NotRequired[Annotated[uuid.UUID, Field(alias='deliverable_id')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    project_id: NotRequired[Annotated[uuid.UUID, Field(alias='project_id')]]
    published_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='published_at')]]
    published_by_user_id: NotRequired[
        Annotated[Optional[uuid.UUID], Field(alias='published_by_user_id')]
    ]
    review_seq: NotRequired[Annotated[Optional[int], Field(alias='review_seq')]]
    title: NotRequired[Annotated[str, Field(alias='title')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    version_number: NotRequired[Annotated[int, Field(alias='version_number')]]


class PublicProjectGrants(BaseModel):
    client_id: uuid.UUID = Field(alias='client_id')
    created_at: datetime.datetime = Field(alias='created_at')
    id: uuid.UUID = Field(alias='id')
    organization_id: uuid.UUID = Field(alias='organization_id')
    project_id: uuid.UUID = Field(alias='project_id')
    revoked_at: Optional[datetime.datetime] = Field(alias='revoked_at')
    revoked_by_user_id: Optional[uuid.UUID] = Field(alias='revoked_by_user_id')
    status: str = Field(alias='status')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')


class PublicProjectGrantsInsert(TypedDict):
    client_id: Annotated[uuid.UUID, Field(alias='client_id')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    project_id: Annotated[uuid.UUID, Field(alias='project_id')]
    revoked_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='revoked_at')]]
    revoked_by_user_id: NotRequired[
        Annotated[Optional[uuid.UUID], Field(alias='revoked_by_user_id')]
    ]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicProjectGrantsUpdate(TypedDict):
    client_id: NotRequired[Annotated[uuid.UUID, Field(alias='client_id')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    project_id: NotRequired[Annotated[uuid.UUID, Field(alias='project_id')]]
    revoked_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='revoked_at')]]
    revoked_by_user_id: NotRequired[
        Annotated[Optional[uuid.UUID], Field(alias='revoked_by_user_id')]
    ]
    status: NotRequired[Annotated[str, Field(alias='status')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]


class PublicComments(BaseModel):
    author_client_id: Optional[uuid.UUID] = Field(alias='author_client_id')
    author_user_id: Optional[uuid.UUID] = Field(alias='author_user_id')
    body: str = Field(alias='body')
    created_at: datetime.datetime = Field(alias='created_at')
    id: uuid.UUID = Field(alias='id')
    organization_id: uuid.UUID = Field(alias='organization_id')
    project_id: uuid.UUID = Field(alias='project_id')
    version_id: uuid.UUID = Field(alias='version_id')


class PublicCommentsInsert(TypedDict):
    author_client_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='author_client_id')]]
    author_user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='author_user_id')]]
    body: Annotated[str, Field(alias='body')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    project_id: Annotated[uuid.UUID, Field(alias='project_id')]
    version_id: Annotated[uuid.UUID, Field(alias='version_id')]


class PublicCommentsUpdate(TypedDict):
    author_client_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='author_client_id')]]
    author_user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='author_user_id')]]
    body: NotRequired[Annotated[str, Field(alias='body')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    project_id: NotRequired[Annotated[uuid.UUID, Field(alias='project_id')]]
    version_id: NotRequired[Annotated[uuid.UUID, Field(alias='version_id')]]


class PublicApprovalDecisions(BaseModel):
    active: bool = Field(alias='active')
    client_id: uuid.UUID = Field(alias='client_id')
    created_at: datetime.datetime = Field(alias='created_at')
    decision: str = Field(alias='decision')
    id: uuid.UUID = Field(alias='id')
    organization_id: uuid.UUID = Field(alias='organization_id')
    project_id: uuid.UUID = Field(alias='project_id')
    version_id: uuid.UUID = Field(alias='version_id')


class PublicApprovalDecisionsInsert(TypedDict):
    active: NotRequired[Annotated[bool, Field(alias='active')]]
    client_id: Annotated[uuid.UUID, Field(alias='client_id')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    decision: Annotated[str, Field(alias='decision')]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    project_id: Annotated[uuid.UUID, Field(alias='project_id')]
    version_id: Annotated[uuid.UUID, Field(alias='version_id')]


class PublicApprovalDecisionsUpdate(TypedDict):
    active: NotRequired[Annotated[bool, Field(alias='active')]]
    client_id: NotRequired[Annotated[uuid.UUID, Field(alias='client_id')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    decision: NotRequired[Annotated[str, Field(alias='decision')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    project_id: NotRequired[Annotated[uuid.UUID, Field(alias='project_id')]]
    version_id: NotRequired[Annotated[uuid.UUID, Field(alias='version_id')]]


class PublicDeliverableVersionFiles(BaseModel):
    asset_id: uuid.UUID = Field(alias='asset_id')
    created_at: datetime.datetime = Field(alias='created_at')
    filename: str = Field(alias='filename')
    id: uuid.UUID = Field(alias='id')
    is_public: bool = Field(alias='is_public')
    mime_type: str = Field(alias='mime_type')
    organization_id: uuid.UUID = Field(alias='organization_id')
    position: int = Field(alias='position')
    project_id: uuid.UUID = Field(alias='project_id')
    size_bytes: int = Field(alias='size_bytes')
    storage_key: str = Field(alias='storage_key')
    updated_at: Optional[datetime.datetime] = Field(alias='updated_at')
    version_id: uuid.UUID = Field(alias='version_id')


class PublicDeliverableVersionFilesInsert(TypedDict):
    asset_id: Annotated[uuid.UUID, Field(alias='asset_id')]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    filename: Annotated[str, Field(alias='filename')]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    is_public: NotRequired[Annotated[bool, Field(alias='is_public')]]
    mime_type: Annotated[str, Field(alias='mime_type')]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    position: Annotated[int, Field(alias='position')]
    project_id: Annotated[uuid.UUID, Field(alias='project_id')]
    size_bytes: Annotated[int, Field(alias='size_bytes')]
    storage_key: Annotated[str, Field(alias='storage_key')]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    version_id: Annotated[uuid.UUID, Field(alias='version_id')]


class PublicDeliverableVersionFilesUpdate(TypedDict):
    asset_id: NotRequired[Annotated[uuid.UUID, Field(alias='asset_id')]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias='created_at')]]
    filename: NotRequired[Annotated[str, Field(alias='filename')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    is_public: NotRequired[Annotated[bool, Field(alias='is_public')]]
    mime_type: NotRequired[Annotated[str, Field(alias='mime_type')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    position: NotRequired[Annotated[int, Field(alias='position')]]
    project_id: NotRequired[Annotated[uuid.UUID, Field(alias='project_id')]]
    size_bytes: NotRequired[Annotated[int, Field(alias='size_bytes')]]
    storage_key: NotRequired[Annotated[str, Field(alias='storage_key')]]
    updated_at: NotRequired[Annotated[Optional[datetime.datetime], Field(alias='updated_at')]]
    version_id: NotRequired[Annotated[uuid.UUID, Field(alias='version_id')]]


class PublicAuditEvents(BaseModel):
    actor_client_id: Optional[uuid.UUID] = Field(alias='actor_client_id')
    actor_kind: str = Field(alias='actor_kind')
    actor_user_id: Optional[uuid.UUID] = Field(alias='actor_user_id')
    data: dict[str, Any] = Field(alias='data')
    deliverable_id: Optional[uuid.UUID] = Field(alias='deliverable_id')
    event_type: str = Field(alias='event_type')
    id: uuid.UUID = Field(alias='id')
    occurred_at: datetime.datetime = Field(alias='occurred_at')
    organization_id: uuid.UUID = Field(alias='organization_id')
    project_id: uuid.UUID = Field(alias='project_id')
    version_id: Optional[uuid.UUID] = Field(alias='version_id')


class PublicAuditEventsInsert(TypedDict):
    actor_client_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='actor_client_id')]]
    actor_kind: Annotated[str, Field(alias='actor_kind')]
    actor_user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='actor_user_id')]]
    data: NotRequired[Annotated[dict[str, Any], Field(alias='data')]]
    deliverable_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='deliverable_id')]]
    event_type: Annotated[str, Field(alias='event_type')]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    occurred_at: NotRequired[Annotated[datetime.datetime, Field(alias='occurred_at')]]
    organization_id: Annotated[uuid.UUID, Field(alias='organization_id')]
    project_id: Annotated[uuid.UUID, Field(alias='project_id')]
    version_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='version_id')]]


class PublicAuditEventsUpdate(TypedDict):
    actor_client_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='actor_client_id')]]
    actor_kind: NotRequired[Annotated[str, Field(alias='actor_kind')]]
    actor_user_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='actor_user_id')]]
    data: NotRequired[Annotated[dict[str, Any], Field(alias='data')]]
    deliverable_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='deliverable_id')]]
    event_type: NotRequired[Annotated[str, Field(alias='event_type')]]
    id: NotRequired[Annotated[uuid.UUID, Field(alias='id')]]
    occurred_at: NotRequired[Annotated[datetime.datetime, Field(alias='occurred_at')]]
    organization_id: NotRequired[Annotated[uuid.UUID, Field(alias='organization_id')]]
    project_id: NotRequired[Annotated[uuid.UUID, Field(alias='project_id')]]
    version_id: NotRequired[Annotated[Optional[uuid.UUID], Field(alias='version_id')]]
