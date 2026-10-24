import os
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import RootModel
from supabase import Client

from app.api.deps import get_cloudflare_connector, get_supabase_client
from app.auth.deps import Principal, get_principal
from app.api.org_deps import OrgRoleContext, require_org_role
from app.clientproof.access import (
    ProjectAccessContext,
    result_rows,
    require_project_access,
)
from app.database.clientproof import (
    ApprovalDecisionsHandler,
    AuditEventsHandler,
    ClientsHandler,
    CommentsHandler,
    DeliverableVersionFilesHandler,
    DeliverableVersionsHandler,
    DeliverablesHandler,
    ProjectGrantsHandler,
    ProjectsHandler,
    utc_now,
)
from app.database.memberships import MembershipRole
from app.database.users import UsersHandler
from app.database.types_autogen import (
    PublicDeliverableVersionFilesInsert,
    PublicDeliverablesInsert,
    PublicDeliverableVersionsInsert,
    PublicUsers,
    PublicProjects,
)
from app.clientproof.schemas import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    CommentCreate,
    CommentResponse,
    DecisionCreate,
    DecisionResponse,
    DeliverableCreate,
    DeliverableResponse,
    DeliverableUpdate,
    FileLinkResponse,
    FileResponse,
    FileUploadComplete,
    FileUploadCreate,
    FileUploadResponse,
    GrantCreate,
    GrantResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    VersionCreate,
    VersionResponse,
    VersionUpdate,
)
from app.cloudflare.connectors import AssetProvider
from app.database.assets import AssetsHandler
from app.utils.logger import get_logger

router = APIRouter(prefix='/v1/clientproof', tags=['clientproof'])
FILE_LINK_TTL_SECONDS = min(300, max(1, int(os.getenv('CLIENTPROOF_FILE_LINK_TTL_SECONDS', '300'))))
logger = get_logger(__name__)


class ClientListResponse(RootModel[list[ClientResponse]]):
    pass


class ProjectListResponse(RootModel[list[ProjectResponse]]):
    pass


class DeliverableListResponse(RootModel[list[DeliverableResponse]]):
    pass


class VersionListResponse(RootModel[list[VersionResponse]]):
    pass


class GrantListResponse(RootModel[list[GrantResponse]]):
    pass


class CommentListResponse(RootModel[list[CommentResponse]]):
    pass


class DecisionListResponse(RootModel[list[DecisionResponse]]):
    pass


class FileListResponse(RootModel[list[FileResponse]]):
    pass


class AccessibleProjectListResponse(RootModel[list[ProjectResponse]]):
    pass


def _rpc_result(result: Any) -> dict[str, Any]:
    data = result.data
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0]
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={'kind': 'rpc_error'}
    )


def _map_rpc_error(payload: dict[str, Any]) -> HTTPException:
    kind = payload.get('kind')
    if kind == 'validation_error':
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={'kind': kind, 'field': payload.get('field')},
        )
    if kind == 'quota_conflict':
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=payload)
    if kind == 'decision_conflict':
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=payload)
    if kind in {'immutable_version', 'revoked_grant', 'archived_project'}:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=payload)
    if kind == 'not_found':
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=payload)
    if kind == 'access_denied':
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=payload)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={'kind': str(kind)})


def _user(context: ProjectAccessContext) -> PublicUsers:
    if context.user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User token required')
    return context.user


def _append_access_audit(
    context: ProjectAccessContext,
    event_type: str,
    data: dict[str, Any],
    *,
    version_id: UUID | None = None,
) -> None:
    try:
        AuditEventsHandler(context.db, organization_id=context.organization_id).append(
            project_id=context.project.id,
            deliverable_id=None,
            version_id=version_id,
            actor_kind='client' if context.client_id is not None else 'staff',
            actor_user_id=context.user.id
            if context.is_staff and context.user is not None
            else None,
            actor_client_id=context.client_id,
            event_type=event_type,
            data=data,
        )
    except Exception as exc:
        logger.warning('ClientProof access audit was not recorded: %s', exc)


@router.post('/organizations/{organization_id}/clients', response_model=ClientResponse)
def create_client(
    organization_id: UUID,
    payload: ClientCreate,
    db: Client = Depends(get_supabase_client),
    ctx: OrgRoleContext = Depends(require_org_role(MembershipRole.admin)),
) -> ClientResponse:
    auth_user_rows = (
        db.table('users')
        .select('id')
        .eq('id', str(payload.external_auth_user_id))
        .limit(2)
        .execute()
    )
    if not isinstance(auth_user_rows.data, list) or len(auth_user_rows.data) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Auth user not found')
    handler = ClientsHandler(db, organization_id=organization_id)
    client = handler.create_item(
        {
            'organization_id': organization_id,
            'external_auth_user_id': payload.external_auth_user_id,
            'display_name': payload.display_name,
            'email': payload.email,
        }
    )
    return ClientResponse.model_validate(client, from_attributes=True)


@router.get('/organizations/{organization_id}/clients', response_model=ClientListResponse)
def list_clients(
    organization_id: UUID,
    db: Client = Depends(get_supabase_client),
    ctx: OrgRoleContext = Depends(require_org_role(MembershipRole.admin)),
) -> ClientListResponse:
    clients = ClientsHandler(db, organization_id=organization_id).list_items()
    return ClientListResponse.model_validate(
        [ClientResponse.model_validate(client, from_attributes=True) for client in clients]
    )


@router.patch('/clients/{client_id}', response_model=ClientResponse)
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    db: Client = Depends(get_supabase_client),
    ctx: OrgRoleContext = Depends(require_org_role(MembershipRole.admin)),
) -> ClientResponse:
    handler = ClientsHandler(db, organization_id=ctx.org.id)
    updated = handler.update_item(client_id, payload.model_dump(exclude_unset=True))
    return ClientResponse.model_validate(updated, from_attributes=True)


@router.post('/organizations/{organization_id}/projects', response_model=ProjectResponse)
def create_project(
    organization_id: UUID,
    payload: ProjectCreate,
    db: Client = Depends(get_supabase_client),
    ctx: OrgRoleContext = Depends(require_org_role(MembershipRole.admin)),
) -> ProjectResponse:
    client_rows = (
        db.table('clients')
        .select('id')
        .eq('organization_id', str(organization_id))
        .eq('id', str(payload.client_id))
        .is_('deleted_at', 'null')
        .limit(1)
        .execute()
    )
    if not isinstance(client_rows.data, list) or len(client_rows.data) != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Client not found')
    result = db.rpc(
        'create_project_atomic',
        {
            'p_organization_id': str(organization_id),
            'p_client_id': str(payload.client_id),
            'p_project_name': payload.name,
            'p_project_description': payload.description,
            'p_response_deadline': (
                payload.response_deadline_at.isoformat()
                if payload.response_deadline_at is not None
                else None
            ),
        },
    ).execute()
    rpc_payload = _rpc_result(result)
    if rpc_payload.get('kind') != 'created':
        raise _map_rpc_error(rpc_payload)
    project = ProjectsHandler(db, organization_id=organization_id).get_item(
        UUID(rpc_payload['project_id'])
    )
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.get('/organizations/{organization_id}/projects', response_model=ProjectListResponse)
def list_tenant_projects(
    organization_id: UUID,
    db: Client = Depends(get_supabase_client),
    ctx: OrgRoleContext = Depends(require_org_role(MembershipRole.member)),
) -> ProjectListResponse:
    projects = ProjectsHandler(db, organization_id=organization_id).list_tenant_projects()
    return ProjectListResponse.model_validate(
        [ProjectResponse.model_validate(project, from_attributes=True) for project in projects]
    )


@router.get('/projects/{project_id}', response_model=ProjectResponse)
def read_project(
    context: ProjectAccessContext = Depends(require_project_access),
) -> ProjectResponse:
    _append_access_audit(context, 'project.read', {'project_id': str(context.project.id)})
    return ProjectResponse.model_validate(context.project, from_attributes=True)


@router.get('/projects', response_model=AccessibleProjectListResponse)
def list_accessible_projects(
    principal: Principal = Depends(get_principal),
    db: Client = Depends(get_supabase_client),
) -> AccessibleProjectListResponse:
    if principal.kind != 'user':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    user_id = UUID(principal.subject)
    user = UsersHandler(db).get_item(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    memberships = (
        db.table('memberships')
        .select('organization_id')
        .eq('user_id', str(user_id))
        .is_('deleted_at', 'null')
        .execute()
    )
    organization_ids: list[str] = []
    for result in (memberships,):
        if isinstance(result.data, list):
            for row in result.data:
                if not isinstance(row, dict):
                    continue
                organization_value = row.get('organization_id')
                if isinstance(organization_value, str):
                    organization_ids.append(organization_value)
    projects: list[ProjectResponse] = []
    for organization_id in dict.fromkeys(organization_ids):
        project_rows = result_rows(
            db.table('projects')
            .select('*')
            .eq('organization_id', organization_id)
            .is_('archived_at', 'null')
            .execute()
        )
        if not project_rows:
            continue
        rows = [PublicProjects.model_validate(row) for row in project_rows]
        projects.extend(ProjectResponse.model_validate(row, from_attributes=True) for row in rows)
    client_rows = result_rows(
        db.table('clients')
        .select('*')
        .eq('external_auth_user_id', str(user_id))
        .is_('deleted_at', 'null')
        .execute()
    )
    for client_row in client_rows:
        organization_value = client_row.get('organization_id')
        client_value = client_row.get('id')
        if not isinstance(organization_value, str) or not isinstance(client_value, str):
            continue
        granted_project_ids = {
            project_id
            for project_id in (
                row.get('project_id')
                for row in result_rows(
                    db.table('project_grants')
                    .select('project_id')
                    .eq('organization_id', organization_value)
                    .eq('client_id', client_value)
                    .eq('status', 'active')
                    .execute()
                )
            )
            if isinstance(project_id, str)
        }
        if not granted_project_ids:
            continue
        project_rows = result_rows(
            db.table('projects')
            .select('*')
            .eq('organization_id', organization_value)
            .is_('archived_at', 'null')
            .execute()
        )
        rows = [
            PublicProjects.model_validate(row)
            for row in project_rows
            if str(row.get('id')) in granted_project_ids
        ]
        projects.extend(ProjectResponse.model_validate(row, from_attributes=True) for row in rows)
    return AccessibleProjectListResponse(projects)


@router.patch('/projects/{project_id}', response_model=ProjectResponse)
def update_project(
    payload: ProjectUpdate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> ProjectResponse:
    if not context.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    handler = ProjectsHandler(context.db, organization_id=context.organization_id)
    values: dict[str, Any] = payload.model_dump(exclude_unset=True, exclude={'archived'})
    if payload.response_deadline_at is not None:
        values['response_deadline_at'] = payload.response_deadline_at
    if payload.archived is not None:
        result = context.db.rpc(
            'set_project_archived_atomic',
            {
                'p_project_id': str(context.project.id),
                'p_organization_id': str(context.organization_id),
                'p_archived': payload.archived,
                'p_actor_user_id': str(_user(context).id),
            },
        ).execute()
        rpc_payload = _rpc_result(result)
        if rpc_payload.get('kind') not in {'archived', 'unarchived', 'unchanged'}:
            raise _map_rpc_error(rpc_payload)
    updated = handler.update_item(context.project.id, values)
    AuditEventsHandler(context.db, organization_id=context.organization_id).append(
        project_id=context.project.id,
        deliverable_id=None,
        version_id=None,
        actor_kind='staff',
        actor_user_id=_user(context).id,
        actor_client_id=None,
        event_type='project.updated',
        data={'fields': list(values.keys())},
    )
    return ProjectResponse.model_validate(updated, from_attributes=True)


@router.post('/projects/{project_id}/deliverables', response_model=DeliverableResponse)
def create_deliverable(
    payload: DeliverableCreate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> DeliverableResponse:
    _require_staff(context)
    handler = DeliverablesHandler(context.db, organization_id=context.organization_id)
    deliverable_payload: PublicDeliverablesInsert = {
        'organization_id': context.organization_id,
        'project_id': context.project.id,
        'name': payload.name,
        'description': payload.description,
        'position': payload.position,
    }
    deliverable = handler.create_item(deliverable_payload)
    AuditEventsHandler(context.db, organization_id=context.organization_id).append(
        project_id=context.project.id,
        deliverable_id=deliverable.id,
        version_id=None,
        actor_kind='staff',
        actor_user_id=_user(context).id,
        actor_client_id=None,
        event_type='deliverable.created',
        data={'deliverable_id': str(deliverable.id)},
    )
    return DeliverableResponse.model_validate(deliverable, from_attributes=True)


def _require_staff(context: ProjectAccessContext) -> None:
    if not context.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')


def _ensure_client_can_view_version(version_id: UUID, context: ProjectAccessContext) -> None:
    if context.is_staff:
        return
    version = DeliverableVersionsHandler(
        context.db, organization_id=context.organization_id
    ).find_in_project(context.project.id, version_id)
    if version is None or version.published_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')


@router.get('/projects/{project_id}/deliverables', response_model=DeliverableListResponse)
def list_deliverables(
    context: ProjectAccessContext = Depends(require_project_access),
) -> DeliverableListResponse:
    rows = DeliverablesHandler(context.db, organization_id=context.organization_id).list_items(
        filters=[]
    )
    rows = [row for row in rows if row.project_id == context.project.id]
    return DeliverableListResponse.model_validate(
        [DeliverableResponse.model_validate(row, from_attributes=True) for row in rows]
    )


@router.patch(
    '/projects/{project_id}/deliverables/{deliverable_id}', response_model=DeliverableResponse
)
def update_deliverable(
    deliverable_id: UUID,
    payload: DeliverableUpdate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> DeliverableResponse:
    _require_staff(context)
    handler = DeliverablesHandler(context.db, organization_id=context.organization_id)
    existing = handler.find_in_project(context.project.id, deliverable_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    values = payload.model_dump(exclude_unset=True, exclude={'archived'})
    if payload.archived is True:
        values['archived_at'] = utc_now()
    if payload.archived is False:
        values['archived_at'] = None
    updated = handler.update_item(deliverable_id, values)
    return DeliverableResponse.model_validate(updated, from_attributes=True)


@router.post(
    '/projects/{project_id}/deliverables/{deliverable_id}/versions', response_model=VersionResponse
)
def create_version(
    deliverable_id: UUID,
    payload: VersionCreate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> VersionResponse:
    _require_staff(context)
    deliverables = DeliverablesHandler(context.db, organization_id=context.organization_id)
    if deliverables.find_in_project(context.project.id, deliverable_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    versions = DeliverableVersionsHandler(context.db, organization_id=context.organization_id)
    version_payload: PublicDeliverableVersionsInsert = {
        'organization_id': context.organization_id,
        'project_id': context.project.id,
        'deliverable_id': deliverable_id,
        'version_number': versions.next_version_number(context.project.id),
        'title': payload.title,
        'content': payload.content,
    }
    version = versions.create_item(version_payload)
    return VersionResponse.model_validate(version, from_attributes=True)


@router.patch('/projects/{project_id}/versions/{version_id}', response_model=VersionResponse)
def update_version(
    version_id: UUID,
    payload: VersionUpdate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> VersionResponse:
    _require_staff(context)
    versions = DeliverableVersionsHandler(context.db, organization_id=context.organization_id)
    existing = versions.find_in_project(context.project.id, version_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    if existing.published_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'kind': 'immutable_version', 'version_id': str(existing.id)},
        )
    updated = versions.update_item(version_id, payload.model_dump(exclude_unset=True))
    return VersionResponse.model_validate(updated, from_attributes=True)


@router.post('/projects/{project_id}/versions/{version_id}/publish', response_model=VersionResponse)
def publish_version(
    version_id: UUID,
    context: ProjectAccessContext = Depends(require_project_access),
) -> VersionResponse:
    _require_staff(context)
    result = context.db.rpc(
        'publish_version_atomic',
        {
            'p_project_id': str(context.project.id),
            'p_version_id': str(version_id),
            'p_actor_user_id': str(_user(context).id),
        },
    ).execute()
    rpc_payload = _rpc_result(result)
    if rpc_payload.get('kind') != 'published':
        raise _map_rpc_error(rpc_payload)
    version = DeliverableVersionsHandler(
        context.db,
        organization_id=context.organization_id,
    ).get_item(version_id)
    return VersionResponse.model_validate(version, from_attributes=True)


@router.get('/projects/{project_id}/versions', response_model=VersionListResponse)
def list_versions(
    context: ProjectAccessContext = Depends(require_project_access),
) -> VersionListResponse:
    versions = DeliverableVersionsHandler(
        context.db, organization_id=context.organization_id
    ).list_items(filters=[])
    visible = [version for version in versions if version.project_id == context.project.id]
    if not context.is_staff:
        visible = [version for version in visible if version.published_at is not None]
    _append_access_audit(
        context,
        'project.versions_read',
        {'project_id': str(context.project.id), 'count': len(visible)},
    )
    return VersionListResponse.model_validate(
        [VersionResponse.model_validate(version, from_attributes=True) for version in visible]
    )


@router.post('/projects/{project_id}/grants', response_model=GrantResponse)
def create_grant(
    payload: GrantCreate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> GrantResponse:
    if not context.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    clients = ClientsHandler(context.db, organization_id=context.organization_id)
    client = clients.get_item(payload.client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Client not found')
    grants = ProjectGrantsHandler(context.db, organization_id=context.organization_id)
    try:
        grant = grants.create_item(
            {
                'organization_id': context.organization_id,
                'project_id': context.project.id,
                'client_id': payload.client_id,
            }
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'kind': 'grant_conflict', 'reason': str(exc.detail)},
        ) from exc
    AuditEventsHandler(context.db, organization_id=context.organization_id).append(
        project_id=context.project.id,
        deliverable_id=None,
        version_id=None,
        actor_kind='staff',
        actor_user_id=_user(context).id,
        actor_client_id=None,
        event_type='grant.created',
        data={'client_id': str(payload.client_id)},
    )
    return GrantResponse.model_validate(grant, from_attributes=True)


@router.get('/projects/{project_id}/grants', response_model=GrantListResponse)
def list_grants(
    context: ProjectAccessContext = Depends(require_project_access),
) -> GrantListResponse:
    grants = ProjectGrantsHandler(context.db, organization_id=context.organization_id).list_items(
        filters=[]
    )
    visible = [grant for grant in grants if grant.project_id == context.project.id]
    if not context.is_staff:
        visible = [
            grant
            for grant in visible
            if grant.status == 'active' and grant.client_id == context.client_id
        ]
    return GrantListResponse.model_validate(
        [GrantResponse.model_validate(grant, from_attributes=True) for grant in visible]
    )


@router.post('/projects/{project_id}/grants/{grant_id}/revoke', response_model=GrantResponse)
def revoke_grant(
    grant_id: UUID,
    context: ProjectAccessContext = Depends(require_project_access),
) -> GrantResponse:
    if not context.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    grants = ProjectGrantsHandler(context.db, organization_id=context.organization_id)
    grant = grants.get_item(grant_id)
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    if grant.project_id != context.project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    if grant.status != 'active':
        return GrantResponse.model_validate(grant, from_attributes=True)
    updated = grants.update_item(
        grant_id,
        {
            'status': 'revoked',
            'revoked_at': utc_now(),
            'revoked_by_user_id': _user(context).id,
        },
    )
    AuditEventsHandler(context.db, organization_id=context.organization_id).append(
        project_id=context.project.id,
        deliverable_id=None,
        version_id=None,
        actor_kind='staff',
        actor_user_id=_user(context).id,
        actor_client_id=None,
        event_type='grant.revoked',
        data={'grant_id': str(grant_id), 'client_id': str(grant.client_id)},
    )
    return GrantResponse.model_validate(updated, from_attributes=True)


@router.post(
    '/projects/{project_id}/versions/{version_id}/comments', response_model=CommentResponse
)
def create_comment(
    version_id: UUID,
    payload: CommentCreate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> CommentResponse:
    versions = DeliverableVersionsHandler(context.db, organization_id=context.organization_id)
    version = versions.find_in_project(context.project.id, version_id)
    if version is None or version.published_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    handler = CommentsHandler(context.db, organization_id=context.organization_id)
    comment = handler.create_item(
        {
            'organization_id': context.organization_id,
            'project_id': context.project.id,
            'version_id': version.id,
            'author_user_id': _user(context).id if context.is_staff else None,
            'author_client_id': context.client_id if not context.is_staff else None,
            'body': payload.body,
        }
    )
    AuditEventsHandler(context.db, organization_id=context.organization_id).append(
        project_id=context.project.id,
        deliverable_id=version.deliverable_id,
        version_id=version.id,
        actor_kind='client' if not context.is_staff else 'staff',
        actor_user_id=_user(context).id if context.is_staff else None,
        actor_client_id=context.client_id if not context.is_staff else None,
        event_type='comment.created',
        data={'comment_id': str(comment.id)},
    )
    return CommentResponse.model_validate(comment, from_attributes=True)


@router.get(
    '/projects/{project_id}/versions/{version_id}/comments', response_model=CommentListResponse
)
def list_comments(
    version_id: UUID,
    context: ProjectAccessContext = Depends(require_project_access),
) -> CommentListResponse:
    _ensure_client_can_view_version(version_id, context)
    comments = CommentsHandler(context.db, organization_id=context.organization_id).list_items(
        filters=[]
    )
    visible = [
        comment
        for comment in comments
        if comment.project_id == context.project.id and comment.version_id == version_id
    ]
    _append_access_audit(
        context,
        'project.comments_read',
        {'project_id': str(context.project.id), 'count': len(visible)},
        version_id=version_id,
    )
    return CommentListResponse.model_validate(
        [CommentResponse.model_validate(comment, from_attributes=True) for comment in visible]
    )


@router.post(
    '/projects/{project_id}/versions/{version_id}/decision', response_model=DecisionResponse
)
def submit_decision(
    version_id: UUID,
    payload: DecisionCreate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> DecisionResponse:
    if context.client_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    result = context.db.rpc(
        'submit_decision_atomic',
        {
            'p_project_id': str(context.project.id),
            'p_version_id': str(version_id),
            'p_deciding_client_id': str(context.client_id),
            'p_decision_kind': payload.decision,
        },
    ).execute()
    rpc_payload = _rpc_result(result)
    if rpc_payload.get('kind') not in {'created', 'idempotent'}:
        raise _map_rpc_error(rpc_payload)
    decisions = ApprovalDecisionsHandler(context.db, organization_id=context.organization_id)
    decision_id = UUID(rpc_payload['decision_id'])
    decision = decisions.get_item(decision_id)
    return DecisionResponse.model_validate(decision, from_attributes=True)


@router.get(
    '/projects/{project_id}/versions/{version_id}/decisions', response_model=DecisionListResponse
)
def list_decisions(
    version_id: UUID,
    context: ProjectAccessContext = Depends(require_project_access),
) -> DecisionListResponse:
    _ensure_client_can_view_version(version_id, context)
    decisions = ApprovalDecisionsHandler(
        context.db, organization_id=context.organization_id
    ).list_items(filters=[])
    visible = [
        decision
        for decision in decisions
        if decision.project_id == context.project.id
        and decision.version_id == version_id
        and (context.is_staff or decision.client_id == context.client_id)
    ]
    _append_access_audit(
        context,
        'project.decisions_read',
        {'project_id': str(context.project.id), 'count': len(visible)},
        version_id=version_id,
    )
    return DecisionListResponse.model_validate(
        [DecisionResponse.model_validate(decision, from_attributes=True) for decision in visible]
    )


@router.post('/projects/{project_id}/files/uploads', response_model=FileUploadResponse)
def create_file_upload(
    payload: FileUploadCreate,
    context: ProjectAccessContext = Depends(require_project_access),
) -> FileUploadResponse:
    _require_staff(context)
    versions = DeliverableVersionsHandler(context.db, organization_id=context.organization_id)
    deliverable = DeliverablesHandler(
        context.db,
        organization_id=context.organization_id,
    ).find_in_project(context.project.id, payload.deliverable_id)
    version = versions.find_in_project(context.project.id, payload.version_id)
    if deliverable is None or version is None or version.deliverable_id != deliverable.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    if version.published_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'kind': 'immutable_version', 'version_id': str(version.id)},
        )
    connector = get_cloudflare_connector('application/octet-stream')
    if connector.get_provider() != AssetProvider.R2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'kind': 'unsupported_upload_provider'},
        )
    asset_id = uuid4()
    storage_key = f'{context.organization_id}/projects/{context.project.id}/{asset_id}'
    upload_url = connector.generate_presigned_url(
        action='put_object',
        mime_type=payload.mime_type,
        key=storage_key,
    )
    AssetsHandler(context.db, organization_id=context.organization_id).create_pending_asset(
        asset_id=asset_id,
        user_id=_user(context).id,
        filename=payload.filename,
        storage_key=storage_key,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        provider=connector.get_provider().value,
    )
    return FileUploadResponse(asset_id=asset_id, storage_key=storage_key, upload_url=upload_url)


@router.post(
    '/projects/{project_id}/files/uploads/{asset_id}/complete',
    response_model=FileResponse,
)
def complete_file_upload(
    asset_id: UUID,
    payload: FileUploadComplete,
    context: ProjectAccessContext = Depends(require_project_access),
) -> FileResponse:
    _require_staff(context)
    assets = AssetsHandler(context.db, organization_id=context.organization_id)
    asset = assets.get_by_asset_id(asset_id)
    expected_prefix = f'{context.organization_id}/projects/{context.project.id}/'
    if not asset.storage_key.startswith(expected_prefix) or asset.status != 'pending':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    connector = get_cloudflare_connector('application/octet-stream')
    if connector.get_provider() != AssetProvider.R2 or asset.provider != AssetProvider.R2.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'kind': 'unsupported_upload_provider'},
        )
    object_metadata = connector.get_object_metadata(asset.storage_key)
    if object_metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Uploaded asset not found'
        )
    actual_size = object_metadata.get('size_bytes')
    actual_mime_type = object_metadata.get('mime_type')
    if actual_size != asset.size_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={'kind': 'asset_size_mismatch'},
        )
    if actual_mime_type != asset.mime_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={'kind': 'asset_content_type_mismatch'},
        )
    versions = DeliverableVersionsHandler(context.db, organization_id=context.organization_id)
    deliverable = DeliverablesHandler(
        context.db,
        organization_id=context.organization_id,
    ).find_in_project(context.project.id, payload.deliverable_id)
    version = versions.find_in_project(context.project.id, payload.version_id)
    if deliverable is None or version is None or version.deliverable_id != deliverable.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    if version.published_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'kind': 'immutable_version', 'version_id': str(version.id)},
        )
    etag = object_metadata.get('etag')
    if not isinstance(etag, str) or not etag:
        raise HTTPException(status_code=409, detail={'kind': 'upload_changed'})
    sealed_key = f'{expected_prefix}sealed/{uuid4()}'
    try:
        connector.finalize_upload(asset.storage_key, sealed_key, etag)
    except Exception as exc:
        raise HTTPException(status_code=409, detail={'kind': 'upload_changed'}) from exc
    sealed_metadata = connector.get_object_metadata(sealed_key)
    if (
        sealed_metadata is None
        or sealed_metadata.get('size_bytes') != asset.size_bytes
        or sealed_metadata.get('mime_type') != asset.mime_type
    ):
        raise HTTPException(status_code=409, detail={'kind': 'upload_changed'})
    files = DeliverableVersionFilesHandler(context.db, organization_id=context.organization_id)
    organization_id = context.organization_id
    file_payload: PublicDeliverableVersionFilesInsert = {
        'organization_id': organization_id,
        'project_id': context.project.id,
        'version_id': version.id,
        'asset_id': asset.id,
        'filename': asset.filename,
        'storage_key': sealed_key,
        'mime_type': asset.mime_type,
        'size_bytes': asset.size_bytes if asset.size_bytes is not None else 0,
        'position': payload.position,
    }
    try:
        file_record = files.create_item(file_payload)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={'kind': 'file_reference_conflict', 'reason': str(exc.detail)},
        ) from exc
    assets.complete_upload(asset_id=asset_id)
    return FileResponse.model_validate(file_record, from_attributes=True)


@router.get('/projects/{project_id}/versions/{version_id}/files', response_model=FileListResponse)
def list_version_files(
    version_id: UUID,
    context: ProjectAccessContext = Depends(require_project_access),
) -> FileListResponse:
    _ensure_client_can_view_version(version_id, context)
    files = DeliverableVersionFilesHandler(
        context.db, organization_id=context.organization_id
    ).list_items(filters=[])
    visible = [
        file
        for file in files
        if file.project_id == context.project.id and file.version_id == version_id
    ]
    _append_access_audit(
        context,
        'project.files_read',
        {'project_id': str(context.project.id), 'count': len(visible)},
        version_id=version_id,
    )
    return FileListResponse.model_validate(
        [FileResponse.model_validate(file, from_attributes=True) for file in visible]
    )


@router.get('/projects/{project_id}/files/{file_id}/link', response_model=FileLinkResponse)
def create_file_link(
    file_id: UUID,
    context: ProjectAccessContext = Depends(require_project_access),
) -> FileLinkResponse:
    files = DeliverableVersionFilesHandler(context.db, organization_id=context.organization_id)
    file_record = files.get_item(file_id)
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    expected_prefix = f'{context.organization_id}/projects/{context.project.id}/'
    if file_record.project_id != context.project.id or not file_record.storage_key.startswith(
        expected_prefix
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    _ensure_client_can_view_version(file_record.version_id, context)
    connector = get_cloudflare_connector('application/octet-stream')
    url = connector.generate_presigned_url(
        action='get_object',
        mime_type=file_record.mime_type,
        key=file_record.storage_key,
        expires_in=FILE_LINK_TTL_SECONDS,
    )
    AuditEventsHandler(context.db, organization_id=context.organization_id).append(
        project_id=context.project.id,
        deliverable_id=None,
        version_id=file_record.version_id,
        actor_kind='client' if context.client_id is not None else 'staff',
        actor_user_id=context.user.id if context.is_staff and context.user is not None else None,
        actor_client_id=context.client_id,
        event_type='file.link_issued',
        data={'file_id': str(file_id)},
    )
    return FileLinkResponse(
        file_id=file_id,
        url=url,
        expires_in_seconds=FILE_LINK_TTL_SECONDS,
    )
