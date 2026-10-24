from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.api.deps import get_supabase_client
from app.auth.deps import Principal, get_principal
from app.database.memberships import MembershipRole, MembershipsHandler
from app.database.types_autogen import PublicMemberships, PublicProjects, PublicUsers
from app.database.users import UsersHandler
from supabase import Client

_STAFF_ROLES = {MembershipRole.member, MembershipRole.admin, MembershipRole.owner}
_ADMIN_ROLES = {MembershipRole.admin, MembershipRole.owner}


@dataclass(frozen=True)
class ProjectAccessContext:
    db: Client
    principal: Principal
    project: PublicProjects
    user: PublicUsers | None
    staff_membership: PublicMemberships | None
    client_id: UUID | None

    @property
    def organization_id(self) -> UUID:
        return self.project.organization_id

    @property
    def is_staff(self) -> bool:
        return self.staff_membership is not None

    @property
    def role(self) -> MembershipRole | None:
        if self.staff_membership is None:
            return None
        return MembershipRole(self.staff_membership.role)

    @property
    def is_admin(self) -> bool:
        return self.role in _ADMIN_ROLES


def result_rows(result: Any) -> list[dict[str, Any]]:
    data = result.data
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')


def _forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')


def require_project_access(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Client = Depends(get_supabase_client),
) -> ProjectAccessContext:
    if principal.kind != 'user':
        raise _forbidden()

    user_id = UUID(principal.subject)
    user = UsersHandler(db).get_item(user_id)
    if user is None:
        raise _not_found()

    project_rows = result_rows(
        db.table('projects').select('*').eq('id', str(project_id)).limit(2).execute()
    )
    if len(project_rows) != 1:
        raise _not_found()
    project = PublicProjects.model_validate(project_rows[0])
    organization_id = project.organization_id

    memberships_handler = MembershipsHandler(db, organization_id=organization_id)
    try:
        staff_membership = memberships_handler.get_for_user_in_org(user.id)
    except HTTPException:
        staff_membership = None
    if staff_membership is not None and staff_membership.role in _STAFF_ROLES:
        return ProjectAccessContext(
            db=db,
            principal=principal,
            project=project,
            user=user,
            staff_membership=staff_membership,
            client_id=None,
        )

    client_rows = result_rows(
        db.table('clients')
        .select('*')
        .eq('organization_id', str(organization_id))
        .eq('external_auth_user_id', str(user.id))
        .is_('deleted_at', 'null')
        .limit(2)
        .execute()
    )
    if len(client_rows) == 1:
        client_id = UUID(client_rows[0]['id'])
        grant_rows = result_rows(
            db.table('project_grants')
            .select('id')
            .eq('organization_id', str(organization_id))
            .eq('project_id', str(project_id))
            .eq('client_id', str(client_id))
            .eq('status', 'active')
            .limit(1)
            .execute()
        )
        if grant_rows:
            return ProjectAccessContext(
                db=db,
                principal=principal,
                project=project,
                user=user,
                staff_membership=None,
                client_id=client_id,
            )

    raise _not_found()


def require_staff_access(context: ProjectAccessContext) -> ProjectAccessContext:
    if not context.is_staff:
        raise _forbidden()
    return context


def require_admin_access(context: ProjectAccessContext) -> ProjectAccessContext:
    if not context.is_admin:
        raise _forbidden()
    return context
