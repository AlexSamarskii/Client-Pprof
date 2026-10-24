from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.database.handler import DatabaseHandler, Filter
from app.database.types_autogen import (
    PublicOrganizations,
    PublicOrganizationsInsert,
    PublicOrganizationsUpdate,
)
from app.utils.logger import get_logger
from supabase import Client

logger = get_logger(__name__)


class OrganizationsHandler(
    DatabaseHandler[
        PublicOrganizations,
        PublicOrganizationsInsert,
        PublicOrganizationsUpdate,
    ]
):
    def __init__(self, client: Client) -> None:
        super().__init__(client, table='organizations', row_model=PublicOrganizations)

    def set_stripe_customer(
        self,
        organization_id: UUID,
        *,
        stripe_customer_id: str,
        billing_email: str | None = None,
        additional_data: Mapping[str, Any] | None = None,
    ) -> PublicOrganizations:
        payload: PublicOrganizationsUpdate = {'stripe_customer_id': stripe_customer_id}
        if billing_email is not None:
            payload['billing_email'] = billing_email
        if additional_data is not None:
            payload['additional_data'] = dict(additional_data)
        return self.update_item(organization_id, payload)

    def list_organizations_for_user(self, user_id: UUID) -> list[PublicOrganizations]:
        """Return organizations the user is a member of (non-deleted memberships)."""
        result = (
            self.client.table('memberships')
            .select('organization_id')
            .eq('user_id', str(user_id))
            .is_('deleted_at', 'null')
            .execute()
        )
        data = result.data
        org_ids: list[UUID] = []
        if isinstance(data, list):
            for row in data:
                if not isinstance(row, dict):
                    continue
                oid = row.get('organization_id')
                if isinstance(oid, str):
                    try:
                        org_ids.append(UUID(oid))
                    except ValueError:
                        continue
        if not org_ids:
            return []
        return self.list_items(filters=[Filter(column='id', op='in', value=org_ids)])

    def accept_pending_invites_for_user(self, *, user_id: UUID, email: str | None) -> int:
        """
        Claim all non-deleted, non-expired pending invites for this user's email.

        Resilience path: if a user signs up or signs in without the explicit
        invite_token query param being honored, this still attaches them to
        any orgs that invited them.
        """
        normalized_email = (email or '').strip().lower()
        if normalized_email == '':
            return 0

        result = (
            self.client.table('memberships')
            .select('id, invitation_expires_at')
            .is_('deleted_at', 'null')
            .is_('user_id', 'null')
            .eq('invited_email', normalized_email)
            .execute()
        )
        rows = result.data if isinstance(result.data, list) else []
        now = datetime.now(timezone.utc)
        accepted = 0

        for row in rows:
            if not isinstance(row, dict):
                continue
            membership_id = row.get('id')
            if not isinstance(membership_id, str):
                continue

            expires_at_raw = row.get('invitation_expires_at')
            if isinstance(expires_at_raw, str) and expires_at_raw.strip() != '':
                try:
                    expires_at = datetime.fromisoformat(expires_at_raw.replace('Z', '+00:00'))
                except ValueError:
                    continue
                if expires_at < now:
                    continue

            self.client.table('memberships').update(
                {
                    'user_id': str(user_id),
                    'invited_email': None,
                    'invitation_id': None,
                    'invitation_expires_at': None,
                    'updated_at': now.isoformat(),
                }
            ).eq('id', membership_id).is_('deleted_at', 'null').is_('user_id', 'null').execute()
            accepted += 1

        if accepted > 0:
            logger.info('Accepted %s pending invite(s) for user_id=%s', accepted, user_id)
        return accepted

    def get_by_stripe_customer_id(self, stripe_customer_id: str) -> PublicOrganizations | None:
        if stripe_customer_id.strip() == '':
            raise ValueError('stripe_customer_id is required')

        result = (
            self.client.table(self.table)
            .select('*')
            .eq('stripe_customer_id', stripe_customer_id)
            .limit(2)
            .execute()
        )
        data = result.data
        if isinstance(data, list):
            if len(data) == 0:
                return None
            if len(data) > 1:
                logger.warning(
                    '%s: multiple rows found for stripe_customer_id=%s',
                    self.table,
                    stripe_customer_id,
                )
            return self.row_model.model_validate(data[0])
        if isinstance(data, dict):
            return self.row_model.model_validate(data)
        return None
