import {
  CreateClientSchema,
  CreateDeliverableSchema,
  DraftSchema,
  UploadSchema,
} from './schemas/clientproof';
import type {
  CreateClientRequest,
  CreateDeliverableRequest,
  DraftRequest,
} from './schemas/clientproof';
import { apiGet, apiPatch, apiPost } from './client';
import { z } from 'zod';
import {
  ClientSchema,
  CommentSchema,
  CreateCommentSchema,
  CreateDecisionSchema,
  CreateProjectSchema,
  DecisionSchema,
  DeliverableSchema,
  FileLinkSchema,
  FileSchema,
  GrantSchema,
  CreateGrantSchema,
  ProjectSchema,
  VersionSchema,
} from './schemas/clientproof';
import type {
  CreateCommentRequest,
  CreateDecisionRequest,
  CreateProjectRequest,
} from '@/api/schemas/clientproof';

const CLIENTPROOF_PREFIX = '/api/v1/clientproof';

export async function listAccessibleProjects() {
  return apiGet(`${CLIENTPROOF_PREFIX}/projects`, {}, z.array(ProjectSchema));
}

export async function listOrganizationProjects(organizationId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/organizations/${organizationId}/projects`,
    {},
    z.array(ProjectSchema),
  );
}

export async function listClients(organizationId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/organizations/${organizationId}/clients`,
    {},
    z.array(ClientSchema),
  );
}

export async function createProject(
  organizationId: string,
  payload: CreateProjectRequest,
) {
  const parsedPayload = CreateProjectSchema.parse(payload);
  return apiPost(
    `${CLIENTPROOF_PREFIX}/organizations/${organizationId}/projects`,
    { body: parsedPayload },
    ProjectSchema,
  );
}

export async function getProject(projectId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}`,
    {},
    ProjectSchema,
  );
}

export async function updateProject(
  projectId: string,
  payload: Partial<CreateProjectRequest>,
) {
  return apiPatch(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}`,
    { body: payload },
    ProjectSchema,
  );
}

export async function listDeliverables(projectId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/deliverables`,
    {},
    z.array(DeliverableSchema),
  );
}

export async function listVersions(projectId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions`,
    {},
    z.array(VersionSchema),
  );
}

export async function listGrants(projectId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/grants`,
    {},
    z.array(GrantSchema),
  );
}

export async function createGrant(
  projectId: string,
  payload: { client_id: string },
) {
  const parsedPayload = CreateGrantSchema.parse(payload);
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/grants`,
    { body: parsedPayload },
    GrantSchema,
  );
}

export async function revokeGrant(projectId: string, grantId: string) {
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/grants/${grantId}/revoke`,
    {},
    GrantSchema,
  );
}

export async function listComments(projectId: string, versionId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions/${versionId}/comments`,
    {},
    z.array(CommentSchema),
  );
}

export async function createComment(
  projectId: string,
  versionId: string,
  payload: CreateCommentRequest,
) {
  const parsedPayload = CreateCommentSchema.parse(payload);
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions/${versionId}/comments`,
    { body: parsedPayload },
    CommentSchema,
  );
}

export async function listDecisions(projectId: string, versionId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions/${versionId}/decisions`,
    {},
    z.array(DecisionSchema),
  );
}

export async function createDecision(
  projectId: string,
  versionId: string,
  payload: CreateDecisionRequest,
) {
  const parsedPayload = CreateDecisionSchema.parse(payload);
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions/${versionId}/decision`,
    { body: parsedPayload },
    DecisionSchema,
  );
}

export async function listVersionFiles(projectId: string, versionId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions/${versionId}/files`,
    {},
    z.array(FileSchema),
  );
}

export async function createFileLink(projectId: string, fileId: string) {
  return apiGet(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/files/${fileId}/link`,
    {},
    FileLinkSchema,
  );
}

export async function createClient(
  organizationId: string,
  payload: CreateClientRequest,
) {
  return apiPost(
    `${CLIENTPROOF_PREFIX}/organizations/${organizationId}/clients`,
    { body: CreateClientSchema.parse(payload) },
    ClientSchema,
  );
}
export async function createDeliverable(
  projectId: string,
  payload: CreateDeliverableRequest,
) {
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/deliverables`,
    { body: CreateDeliverableSchema.parse(payload) },
    DeliverableSchema,
  );
}
export async function createDraft(
  projectId: string,
  deliverableId: string,
  payload: DraftRequest,
) {
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/deliverables/${deliverableId}/versions`,
    { body: DraftSchema.parse(payload) },
    VersionSchema,
  );
}
export async function updateDraft(
  projectId: string,
  versionId: string,
  payload: DraftRequest,
) {
  return apiPatch(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions/${versionId}`,
    { body: DraftSchema.parse(payload) },
    VersionSchema,
  );
}
export async function publishDraft(projectId: string, versionId: string) {
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/versions/${versionId}/publish`,
    {},
    VersionSchema,
  );
}
export async function setProjectArchived(projectId: string, archived: boolean) {
  return apiPatch(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}`,
    { body: { archived } },
    ProjectSchema,
  );
}
export async function uploadVersionFile(
  projectId: string,
  version: { id: string; deliverable_id: string },
  file: File,
) {
  const upload = await apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/files/uploads`,
    {
      body: {
        deliverable_id: version.deliverable_id,
        version_id: version.id,
        filename: file.name,
        mime_type: file.type || 'application/octet-stream',
        size_bytes: file.size,
      },
    },
    UploadSchema,
  );
  const response = await fetch(upload.upload_url, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
  });
  if (!response.ok) throw new Error('upload failed');
  return apiPost(
    `${CLIENTPROOF_PREFIX}/projects/${projectId}/files/uploads/${upload.asset_id}/complete`,
    {
      body: {
        deliverable_id: version.deliverable_id,
        version_id: version.id,
        position: 1,
      },
    },
    FileSchema,
  );
}
