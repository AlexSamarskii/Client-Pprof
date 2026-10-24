from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from app.database.handler import DatabaseHandler
from app.database.types_autogen import (
    PublicApprovalDecisions,
    PublicApprovalDecisionsInsert,
    PublicApprovalDecisionsUpdate,
    PublicAuditEvents,
    PublicAuditEventsInsert,
    PublicComments,
    PublicCommentsInsert,
    PublicCommentsUpdate,
    PublicClients,
    PublicClientsInsert,
    PublicClientsUpdate,
    PublicDeliverableVersionFiles,
    PublicDeliverableVersionFilesInsert,
    PublicDeliverableVersionFilesUpdate,
    PublicDeliverables,
    PublicDeliverablesInsert,
    PublicDeliverablesUpdate,
    PublicDeliverableVersions,
    PublicDeliverableVersionsInsert,
    PublicDeliverableVersionsUpdate,
    PublicProjectGrants,
    PublicProjectGrantsInsert,
    PublicProjectGrantsUpdate,
    PublicProjects,
    PublicProjectsInsert,
    PublicProjectsUpdate,
)
from supabase import Client


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClientsHandler(DatabaseHandler[PublicClients, PublicClientsInsert, PublicClientsUpdate]):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='clients',
            row_model=PublicClients,
            organization_id=organization_id,
        )

    def get_for_auth_user(self, auth_user_id: UUID) -> PublicClients | None:
        result = (
            self.client.table('clients')
            .select('*')
            .eq('organization_id', str(self.organization_id))
            .eq('external_auth_user_id', str(auth_user_id))
            .is_('deleted_at', 'null')
            .limit(2)
            .execute()
        )
        data = result.data
        if not isinstance(data, list):
            return None
        for row in data:
            return self._parse_row(row)
        return None


class ProjectsHandler(DatabaseHandler[PublicProjects, PublicProjectsInsert, PublicProjectsUpdate]):
    def __init__(self, client: Client, *, organization_id: UUID | None = None) -> None:
        super().__init__(
            client,
            table='projects',
            row_model=PublicProjects,
            organization_id=organization_id,
        )

    def find_by_id(self, project_id: UUID) -> PublicProjects | None:
        result = (
            self.client.table('projects').select('*').eq('id', str(project_id)).limit(2).execute()
        )
        data = result.data
        if isinstance(data, list) and len(data) == 1:
            return self._parse_row(data[0])
        return None

    def list_tenant_projects(self) -> list[PublicProjects]:
        result = self._apply_deleted_at_scope(
            self._apply_org_scope(self.client.table('projects').select('*'))
        ).execute()
        data = result.data
        if not isinstance(data, list):
            return []
        return [self._parse_row(row) for row in data]


class DeliverablesHandler(
    DatabaseHandler[PublicDeliverables, PublicDeliverablesInsert, PublicDeliverablesUpdate]
):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='deliverables',
            row_model=PublicDeliverables,
            organization_id=organization_id,
        )

    def find_in_project(self, project_id: UUID, deliverable_id: UUID) -> PublicDeliverables | None:
        result = (
            self._apply_deleted_at_scope(
                self._apply_org_scope(self.client.table('deliverables').select('*'))
            )
            .eq('project_id', str(project_id))
            .eq('id', str(deliverable_id))
            .limit(2)
            .execute()
        )
        data = result.data
        if isinstance(data, list) and len(data) == 1:
            return self._parse_row(data[0])
        return None


class DeliverableVersionsHandler(
    DatabaseHandler[
        PublicDeliverableVersions,
        PublicDeliverableVersionsInsert,
        PublicDeliverableVersionsUpdate,
    ]
):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='deliverable_versions',
            row_model=PublicDeliverableVersions,
            organization_id=organization_id,
        )

    def find_in_project(
        self, project_id: UUID, version_id: UUID
    ) -> PublicDeliverableVersions | None:
        result = (
            self._apply_org_scope(self.client.table('deliverable_versions').select('*'))
            .eq('project_id', str(project_id))
            .eq('id', str(version_id))
            .limit(2)
            .execute()
        )
        data = result.data
        if isinstance(data, list) and len(data) == 1:
            return self._parse_row(data[0])
        return None

    def next_version_number(self, project_id: UUID) -> int:
        result = (
            self._apply_org_scope(
                self.client.table('deliverable_versions').select('version_number')
            )
            .eq('project_id', str(project_id))
            .execute()
        )
        data = result.data
        numbers = [row.get('version_number') for row in data] if isinstance(data, list) else []
        return max((int(value) for value in numbers if isinstance(value, int)), default=0) + 1


class ProjectGrantsHandler(
    DatabaseHandler[PublicProjectGrants, PublicProjectGrantsInsert, PublicProjectGrantsUpdate]
):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='project_grants',
            row_model=PublicProjectGrants,
            organization_id=organization_id,
        )

    def active_exists(self, project_id: UUID, client_id: UUID) -> bool:
        result = (
            self._apply_org_scope(self.client.table('project_grants').select('id'))
            .eq('project_id', str(project_id))
            .eq('client_id', str(client_id))
            .eq('status', 'active')
            .limit(1)
            .execute()
        )
        return isinstance(result.data, list) and len(result.data) > 0


class CommentsHandler(DatabaseHandler[PublicComments, PublicCommentsInsert, PublicCommentsUpdate]):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='comments',
            row_model=PublicComments,
            organization_id=organization_id,
        )


class ApprovalDecisionsHandler(
    DatabaseHandler[
        PublicApprovalDecisions,
        PublicApprovalDecisionsInsert,
        PublicApprovalDecisionsUpdate,
    ]
):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='approval_decisions',
            row_model=PublicApprovalDecisions,
            organization_id=organization_id,
        )


class DeliverableVersionFilesHandler(
    DatabaseHandler[
        PublicDeliverableVersionFiles,
        PublicDeliverableVersionFilesInsert,
        PublicDeliverableVersionFilesUpdate,
    ]
):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='deliverable_version_files',
            row_model=PublicDeliverableVersionFiles,
            organization_id=organization_id,
        )

    def get_for_asset(self, asset_id: UUID) -> PublicDeliverableVersionFiles | None:
        result = (
            self._apply_org_scope(self.client.table('deliverable_version_files').select('*'))
            .eq('asset_id', str(asset_id))
            .limit(2)
            .execute()
        )
        data = result.data
        if isinstance(data, list) and len(data) == 1:
            return self._parse_row(data[0])
        return None


class AuditEventsHandler(DatabaseHandler[PublicAuditEvents, PublicAuditEventsInsert, Any]):
    def __init__(self, client: Client, *, organization_id: UUID) -> None:
        super().__init__(
            client,
            table='audit_events',
            row_model=PublicAuditEvents,
            organization_id=organization_id,
        )

    def append(
        self,
        *,
        project_id: UUID,
        deliverable_id: UUID | None,
        version_id: UUID | None,
        actor_kind: str,
        actor_user_id: UUID | None,
        actor_client_id: UUID | None,
        event_type: str,
        data: dict[str, Any],
    ) -> PublicAuditEvents:
        organization_id = cast(UUID, self.organization_id)
        payload: PublicAuditEventsInsert = {
            'organization_id': organization_id,
            'project_id': project_id,
            'deliverable_id': deliverable_id,
            'version_id': version_id,
            'actor_kind': actor_kind,
            'actor_user_id': actor_user_id,
            'actor_client_id': actor_client_id,
            'event_type': event_type,
            'data': data,
        }
        # Audit rows use occurred_at, not the CRUD helper's created_at column.
        # All ownership fields are derived above from this scoped handler/context.
        result = (
            self.client.table(self.table).insert(self._jsonify_payload(dict(payload))).execute()
        )
        rows = result.data
        if isinstance(rows, list) and rows:
            return self._parse_row(rows[0])
        if isinstance(rows, dict):
            return self._parse_row(rows)
        raise ValueError('audit event insert returned no row')
