from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, RootModel

from app.api.deps import get_supabase_client
from app.api.org_deps import OrgRoleContext, require_org_membership, require_org_role
from app.auth.deps import Principal, require_role
from app.database.memberships import MembershipRole
from app.database.organizations import OrganizationsHandler
from app.database.types_autogen import PublicOrganizations
from app.database.users import UsersHandler
from fastapi import HTTPException, status
from supabase import Client


# API contract models (request/response) - keep these at the top for readability.
class OrganizationResult(PublicOrganizations):
    pass


class OrganizationListResult(RootModel[list[OrganizationResult]]):
    pass


class UpdateOrganizationRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str | None = None


router = APIRouter(prefix='/org', tags=['organizations'])


@router.get('', response_model=OrganizationListResult)
def list_organizations(
    db: Client = Depends(get_supabase_client),
    principal: Principal = Depends(require_role('member')),
) -> OrganizationListResult:
    if principal.kind == 'service':
        # Service principals get a list of all organizations
        org_rows = OrganizationsHandler(db).list_items()
        return OrganizationListResult.model_validate(
            [OrganizationResult.model_validate(org, from_attributes=True) for org in org_rows]
        )

    # User principals get a list of orgs they have access to via memberships
    current_user = UsersHandler(db).get_item(UUID(principal.subject))
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')

    orgs_handler = OrganizationsHandler(db)
    # Auto-claim safety net: if this user has any pending invites matching their email,
    # attach them to those orgs before listing. Idempotent.
    orgs_handler.accept_pending_invites_for_user(user_id=current_user.id, email=current_user.email)

    org_rows = orgs_handler.list_organizations_for_user(current_user.id)
    return OrganizationListResult.model_validate(
        [OrganizationResult.model_validate(org, from_attributes=True) for org in org_rows]
    )


@router.get('/{organization_id}', response_model=OrganizationResult)
def get_organization(
    organization_id: UUID,
    db: Client = Depends(get_supabase_client),
    principal: Principal = Depends(require_role('member')),
) -> OrganizationResult:
    if principal.kind == 'service':
        org = OrganizationsHandler(db).get_item(organization_id)
        if org is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
        return OrganizationResult.model_validate(org, from_attributes=True)

    current_user = UsersHandler(db).get_item(UUID(principal.subject))
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    require_org_membership(organization_id, db=db, current_user=current_user)
    org = OrganizationsHandler(db).get_item(organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    return OrganizationResult.model_validate(org, from_attributes=True)


@router.patch('/{organization_id}', response_model=OrganizationResult)
def update_organization(
    organization_id: UUID,
    payload: UpdateOrganizationRequest,
    db: Client = Depends(get_supabase_client),
    _ctx: OrgRoleContext = Depends(require_org_role(MembershipRole.owner)),
) -> OrganizationResult:
    updated = OrganizationsHandler(db).update_item(
        organization_id, payload.model_dump(exclude_unset=True)
    )
    return OrganizationResult.model_validate(updated, from_attributes=True)
