import { useAuth } from '../components/auth/AuthProvider';
import {
  createClient,
  createDeliverable,
  createDraft,
  updateDraft,
  publishDraft,
  setProjectArchived,
  uploadVersionFile,
} from '../api/clientproof';
import type {
  CreateClientRequest,
  CreateDeliverableRequest,
  DraftRequest,
} from '../api/schemas/clientproof';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import {
  createComment,
  createDecision,
  createFileLink,
  createGrant,
  createProject,
  getProject,
  listAccessibleProjects,
  listClients,
  listComments,
  listDecisions,
  listDeliverables,
  listGrants,
  listOrganizationProjects,
  listVersionFiles,
  listVersions,
  revokeGrant,
} from '../api/clientproof';
import type {
  ApprovalDecision,
  Client,
  CreateCommentRequest,
  CreateDecisionRequest,
  CreateProjectRequest,
  Deliverable,
  DeliverableVersion,
  FileLink,
  Project,
  ProjectGrant,
  VersionFile,
} from '../api/schemas/clientproof';
import type { Comment } from '../api/schemas/clientproof';
import { useOrganization } from './useOrganization';

export type ClientProofErrorKind =
  | 'session'
  | 'no_access'
  | 'not_found'
  | 'conflict'
  | 'decision_conflict'
  | 'grant_conflict'
  | 'quota_conflict'
  | 'immutable_version'
  | 'revoked_grant'
  | 'archived_project'
  | 'validation'
  | 'unknown';

export class ClientProofError extends Error {
  kind: ClientProofErrorKind;
  status: number;

  constructor(error: unknown) {
    if (error instanceof ApiError) {
      super(error.message);
      this.status = error.status;
      this.kind = mapApiError(error);
    } else {
      super(error instanceof Error ? error.message : 'Unexpected error');
      this.status = 0;
      this.kind = 'unknown';
    }
  }
}

function mapApiError(error: ApiError): ClientProofErrorKind {
  if (error.status === 401) return 'session';
  if (error.status === 403) return 'no_access';
  if (error.status === 404) return 'not_found';
  if (error.status === 422) return 'validation';
  if (error.status === 409) {
    const body = error.body as {
      kind?: string;
      detail?: { kind?: string };
    } | null;
    const kind = body?.detail?.kind ?? body?.kind;
    if (
      kind === 'decision_conflict' ||
      kind === 'grant_conflict' ||
      kind === 'quota_conflict' ||
      kind === 'immutable_version' ||
      kind === 'revoked_grant' ||
      kind === 'archived_project'
    ) {
      return kind;
    }
  }
  return 'unknown';
}

const CLIENT_PROOF_ERROR_MESSAGES: Record<ClientProofErrorKind, string> = {
  session: 'Войдите в систему заново.',
  no_access: 'Доступ не предоставлен.',
  not_found: 'Запись не найдена.',
  conflict: 'Действие конфликтует с текущим состоянием.',
  decision_conflict: 'Решение уже зафиксировано. Обновите статус версии.',
  grant_conflict: 'Доступ этому клиенту выдать нельзя.',
  quota_conflict: 'Достигнут лимит активных проектов тарифа.',
  immutable_version: 'Опубликованная версия неизменяема.',
  revoked_grant: 'Доступ к проекту отозван.',
  archived_project: 'Проект заархивирован.',
  validation: 'Проверьте корректность данных.',
  unknown: 'Не удалось выполнить запрос.',
};

export function describeClientProofError(error: unknown) {
  return CLIENT_PROOF_ERROR_MESSAGES[toClientProofError(error).kind];
}

export function toClientProofError(error: unknown): ClientProofError {
  return error instanceof ClientProofError
    ? error
    : new ClientProofError(error);
}

export function isPendingProject(project: Project) {
  return project.status === 'in_review';
}

export function isOverdueProject(project: Project, now = new Date()) {
  return (
    isPendingProject(project) &&
    project.response_deadline_at !== null &&
    Date.parse(project.response_deadline_at) < now.getTime()
  );
}

export function useStaffProjects() {
  const { user: actor } = useAuth();
  const { organization } = useOrganization();
  const query = useQuery<Project[]>({
    queryKey: ['clientproof-staff-projects', organization?.id, actor?.id],
    queryFn: async () => {
      if (!organization) throw new Error('Organization is required');
      return listOrganizationProjects(organization.id);
    },
    enabled: !!organization,
  });
  return query;
}

export function useClientProjects() {
  const { user: actor } = useAuth();
  const query = useQuery<Project[]>({
    queryKey: ['clientproof-accessible-projects', actor?.id],
    queryFn: async () => listAccessibleProjects(),
  });
  return query;
}

export function useClients(organizationOverride?: string, permitted = true) {
  const { user: actor } = useAuth();
  const { organization } = useOrganization();
  const query = useQuery<Client[]>({
    queryKey: [
      'clientproof-clients',
      organizationOverride ?? organization?.id,
      actor?.id,
    ],
    queryFn: async () => {
      if (!organization && !organizationOverride)
        throw new Error('Organization is required');
      return listClients(organizationOverride ?? organization!.id);
    },
    enabled: permitted && !!(organizationOverride ?? organization?.id),
  });
  return query;
}

export function useCreateProject() {
  const { organization } = useOrganization();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateProjectRequest) => {
      if (!organization) throw new Error('Organization is required');
      return createProject(organization.id, payload);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['clientproof-staff-projects', organization?.id],
        }),
        queryClient.invalidateQueries({
          queryKey: ['clientproof-accessible-projects'],
        }),
      ]);
    },
  });
}

export function useProject(projectId: string) {
  const { user: actor } = useAuth();
  return useQuery<Project>({
    queryKey: ['clientproof-project', projectId, actor?.id],
    enabled: !!projectId,
    queryFn: async () => getProject(projectId),
  });
}

export function useDeliverables(projectId: string) {
  const { user: actor } = useAuth();
  return useQuery<Deliverable[]>({
    queryKey: ['clientproof-deliverables', projectId, actor?.id],
    queryFn: async () => listDeliverables(projectId),
  });
}

export function useVersions(projectId: string) {
  const { user: actor } = useAuth();
  return useQuery<DeliverableVersion[]>({
    queryKey: ['clientproof-versions', projectId, actor?.id],
    queryFn: async () => listVersions(projectId),
  });
}

export function useGrants(projectId: string, enabled: boolean) {
  const { user: actor } = useAuth();
  return useQuery<ProjectGrant[]>({
    queryKey: ['clientproof-grants', projectId, actor?.id],
    queryFn: async () => listGrants(projectId),
    enabled,
  });
}

export function useRevokeGrant(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (grantId: string) => revokeGrant(projectId, grantId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['clientproof-grants', projectId],
      });
    },
  });
}

export function useCreateGrant(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { client_id: string }) =>
      createGrant(projectId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['clientproof-grants', projectId],
      });
    },
  });
}

export function useComments(projectId: string, versionId: string | null) {
  const { user: actor } = useAuth();
  return useQuery<Comment[]>({
    queryKey: ['clientproof-comments', projectId, versionId, actor?.id],
    queryFn: async () => {
      if (!versionId) throw new Error('Version is required');
      return listComments(projectId, versionId);
    },
    enabled: !!versionId,
  });
}

export function useCreateComment(projectId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateCommentRequest) =>
      createComment(projectId, versionId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['clientproof-comments', projectId, versionId],
      });
    },
  });
}

export function useDecisions(projectId: string, versionId: string | null) {
  const { user: actor } = useAuth();
  return useQuery<ApprovalDecision[]>({
    queryKey: ['clientproof-decisions', projectId, versionId, actor?.id],
    queryFn: async () => {
      if (!versionId) throw new Error('Version is required');
      return listDecisions(projectId, versionId);
    },
    enabled: !!versionId,
  });
}

export function useCreateDecision(projectId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateDecisionRequest) =>
      createDecision(projectId, versionId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['clientproof-decisions', projectId, versionId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['clientproof-project', projectId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['clientproof-versions', projectId],
        }),
      ]);
    },
  });
}

export function useVersionFiles(projectId: string, versionId: string | null) {
  const { user: actor } = useAuth();
  return useQuery<VersionFile[]>({
    queryKey: ['clientproof-files', projectId, versionId, actor?.id],
    queryFn: async () => {
      if (!versionId) throw new Error('Version is required');
      return listVersionFiles(projectId, versionId);
    },
    enabled: !!versionId,
  });
}

export function useFileLink(projectId: string) {
  const { user: actor } = useAuth();
  const scope = `${projectId}:${actor?.id ?? ''}`;
  const [linkState, setLinks] = useState<{
    scope: string;
    values: Record<string, FileLink>;
  }>({ scope, values: {} });
  const mutation = useMutation({
    mutationFn: async (fileId: string) => createFileLink(projectId, fileId),
    onSuccess: (link) => {
      setLinks((previous) => ({
        scope,
        values: {
          ...(previous.scope === scope ? previous.values : {}),
          [link.file_id]: link,
        },
      }));
    },
  });
  return {
    links: linkState.scope === scope ? linkState.values : {},
    createLink: mutation.mutateAsync,
    isPending: mutation.isPending,
  };
}

export function useCreateClient() {
  const { organization } = useOrganization();
  const cache = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateClientRequest) => {
      if (!organization) throw new Error('organization required');
      return createClient(organization.id, payload);
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['clientproof-clients'] });
    },
  });
}
export function useStaffActions(projectId: string) {
  const cache = useQueryClient();
  const refresh = async () => {
    await Promise.all(
      [
        'clientproof-project',
        'clientproof-deliverables',
        'clientproof-versions',
        'clientproof-files',
        'clientproof-accessible-projects',
        'clientproof-staff-projects',
      ].map((key) => cache.invalidateQueries({ queryKey: [key] })),
    );
  };
  const deliverable = useMutation({
    mutationFn: (data: CreateDeliverableRequest) =>
      createDeliverable(projectId, data),
    onSuccess: refresh,
  });
  const draft = useMutation({
    mutationFn: (data: DraftRequest & { deliverableId: string }) =>
      createDraft(projectId, data.deliverableId, {
        title: data.title,
        content: data.content,
      }),
    onSuccess: refresh,
  });
  const edit = useMutation({
    mutationFn: (data: DraftRequest & { versionId: string }) =>
      updateDraft(projectId, data.versionId, {
        title: data.title,
        content: data.content,
      }),
    onSuccess: refresh,
  });
  const publish = useMutation({
    mutationFn: (id: string) => publishDraft(projectId, id),
    onSuccess: refresh,
  });
  const archive = useMutation({
    mutationFn: (archived: boolean) => setProjectArchived(projectId, archived),
    onSuccess: refresh,
  });
  const upload = useMutation({
    mutationFn: (data: { version: DeliverableVersion; file: File }) =>
      uploadVersionFile(projectId, data.version, data.file),
    onSuccess: refresh,
  });
  return { deliverable, draft, edit, publish, archive, upload };
}
