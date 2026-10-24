// @vitest-environment jsdom
import {
  act,
  cleanup,
  render,
  renderHook,
  screen,
  waitFor,
} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { createElement } from 'react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { Dashboard } from '../../src/routes/dashboard';
import { ProjectRoute } from '../../src/routes/project';
import { Projects } from '../../src/routes/projects';

const useUserMock = vi.hoisted(() => vi.fn());
const confirmationMocks = vi.hoisted(() => ({
  verifyOtp: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: ReactNode; to: string }) =>
    createElement('a', { href: to }, children),
  useParams: vi.fn(() => ({ projectId: 'project-1' })),
  useNavigate: () => confirmationMocks.navigate,
}));

const actorState = vi.hoisted(() => ({ id: 'actor-one' }));
const apiMocks = vi.hoisted(() =>
  Object.fromEntries(
    [
      'listAccessibleProjects',
      'listOrganizationProjects',
      'listClients',
      'createClient',
      'createProject',
      'getProject',
      'listDeliverables',
      'listVersions',
      'listGrants',
      'revokeGrant',
      'createGrant',
      'listComments',
      'createComment',
      'listDecisions',
      'createDecision',
      'listVersionFiles',
      'createFileLink',
      'createDeliverable',
      'createDraft',
      'updateDraft',
      'publishDraft',
      'setProjectArchived',
      'uploadVersionFile',
    ].map((name) => [name, vi.fn()]),
  ),
);
vi.mock('../../src/api/clientproof', () => apiMocks);
vi.mock('../../src/components/auth/AuthProvider', () => ({
  useAuth: () => ({ user: { id: actorState.id }, isLoading: false }),
}));

vi.mock('../../src/hooks/useOrganization', () => ({
  useOrganization: vi.fn(() => ({ organization: { id: 'organization-1' } })),
}));

vi.mock('../../src/supabase/client', () => ({
  supabase: {
    auth: {
      verifyOtp: confirmationMocks.verifyOtp,
      getSession: vi.fn(() =>
        Promise.resolve({
          data: { session: { access_token: 'synthetic-unit-token' } },
        }),
      ),
    },
  },
}));

vi.mock('../../src/hooks/useUser', () => ({
  useUser: useUserMock,
}));

const useClientProof = vi.hoisted(() => ({
  isOverdueProject: (project: {
    status: string;
    response_deadline_at: string | null;
  }) =>
    project.status === 'in_review' &&
    project.response_deadline_at !== null &&
    Date.parse(project.response_deadline_at) < Date.now(),
  isPendingProject: (project: { status: string }) =>
    project.status === 'in_review',
  toClientProofError: (error: { kind?: string } | null) => ({
    kind: error?.kind ?? 'unknown',
  }),
  describeClientProofError: (error: { kind?: string } | null) => {
    const kind = error?.kind ?? 'unknown';
    return (
      {
        no_access: 'Доступ не предоставлен.',
        quota_conflict: 'Достигнут лимит активных проектов тарифа.',
        decision_conflict: 'Решение уже зафиксировано. Обновите статус версии.',
        unknown: 'Не удалось выполнить запрос.',
      }[kind] ?? 'Не удалось выполнить запрос.'
    );
  },
  useClientProjects: vi.fn(),
  useStaffProjects: vi.fn(),
  useClients: vi.fn(),
  useCreateProject: vi.fn(),
  useProject: vi.fn(),
  useDeliverables: vi.fn(),
  useVersions: vi.fn(),
  useGrants: vi.fn(),
  useRevokeGrant: vi.fn(),
  useFileLink: vi.fn(),
  useComments: vi.fn(),
  useCreateComment: vi.fn(),
  useDecisions: vi.fn(),
  useCreateDecision: vi.fn(),
  useCreateGrant: vi.fn(),
  useVersionFiles: vi.fn(),
  useStaffActions: vi.fn(),
}));

vi.mock('../../src/hooks/useClientProof', () => useClientProof);

const project = {
  id: 'project-1',
  organization_id: 'organization-1',
  client_id: 'client-1',
  name: 'Лендинг',
  description: null,
  status: 'in_review',
  response_deadline_at: new Date(Date.now() - 60_000).toISOString(),
  archived_at: null,
  created_at: '2026-03-20T10:00:00Z',
} as never;

const version = {
  id: 'version-1',
  deliverable_id: 'deliverable-1',
  version_number: 1,
  title: 'Первый вариант',
  content: 'Содержимое версии',
  review_seq: 1,
  published_at: '2026-03-20T11:00:00Z',
  created_at: '2026-03-20T10:30:00Z',
} as never;

function resetProjectHooks() {
  useClientProof.useProject.mockReturnValue({
    data: project,
    error: null,
    isPending: false,
  });
  useClientProof.useDeliverables.mockReturnValue({
    data: [],
    error: null,
    isPending: false,
  });
  useClientProof.useVersions.mockReturnValue({
    data: [version],
    error: null,
    isPending: false,
  });
  useClientProof.useComments.mockReturnValue({
    data: [],
    error: null,
    isPending: false,
  });
  useClientProof.useCreateComment.mockReturnValue({ mutateAsync: vi.fn() });
  useClientProof.useDecisions.mockReturnValue({
    data: [],
    error: null,
    isPending: false,
  });
  useClientProof.useCreateDecision.mockReturnValue({ mutateAsync: vi.fn() });
  useClientProof.useCreateGrant.mockReturnValue({ mutateAsync: vi.fn() });
  useClientProof.useVersionFiles.mockReturnValue({
    data: [],
    error: null,
    isPending: false,
  });
  useClientProof.useFileLink.mockReturnValue({
    links: {},
    createLink: vi.fn(),
    isPending: false,
  });
  useClientProof.useClients.mockReturnValue({
    data: [],
    error: null,
    isPending: false,
  });
  useClientProof.useGrants.mockReturnValue({
    data: [],
    error: null,
    isPending: false,
  });
  useClientProof.useRevokeGrant.mockReturnValue({ mutateAsync: vi.fn() });
  useClientProof.useStaffActions.mockReturnValue(
    Object.fromEntries(
      ['deliverable', 'draft', 'edit', 'publish', 'archive', 'upload'].map(
        (key) => [key, { mutateAsync: vi.fn(), isPending: false }],
      ),
    ),
  );
}

beforeEach(() => {
  useUserMock.mockReset();
  useUserMock.mockReturnValue({ role: 'admin', roleReady: true });
  useClientProof.useClientProjects.mockReset();
  useClientProof.useStaffProjects.mockReset();
  useClientProof.useClients.mockReset();
  useClientProof.useCreateProject.mockReset();
  useClientProof.useCreateGrant.mockReset();
});

afterEach(() => {
  cleanup();
});

describe('ClientProof UI', () => {
  test('staff dashboard shows pending and overdue projects', () => {
    useClientProof.useClientProjects.mockReturnValue({
      data: [project],
      error: null,
      isPending: false,
      isSuccess: true,
    });
    render(createElement(Dashboard));
    expect(
      screen.getByRole('heading', { name: 'Рабочая панель' }),
    ).toBeVisible();
    expect(
      screen.getByRole('heading', { name: 'Ожидают согласования' }),
    ).toBeVisible();
    expect(
      screen.getByRole('heading', { name: 'Просроченные ответы' }),
    ).toBeVisible();
    expect(
      screen.getAllByRole('link', { name: 'Открыть проект' }),
    ).toHaveLength(2);
  });

  test('dashboard exposes loading, empty, and access-error states', () => {
    useClientProof.useClientProjects.mockReturnValue({
      data: undefined,
      error: null,
      isPending: true,
    });
    render(createElement(Dashboard));
    expect(screen.getByRole('status')).toHaveTextContent('Загрузка…');
    cleanup();

    useClientProof.useClientProjects.mockReturnValue({
      data: [],
      error: null,
      isPending: false,
      isSuccess: true,
    });
    render(createElement(Dashboard));
    expect(screen.getByRole('status')).toHaveTextContent('Проектов пока нет.');
    cleanup();

    useClientProof.useClientProjects.mockReturnValue({
      data: undefined,
      error: { kind: 'no_access' },
      isPending: false,
      isSuccess: true,
    });
    render(createElement(Dashboard));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Доступ не предоставлен.',
    );
  });

  test('staff creates a project and surfaces a quota conflict', async () => {
    useClientProof.useClientProjects.mockReturnValue({
      data: [],
      error: null,
      isPending: false,
      isSuccess: true,
    });
    useClientProof.useClients.mockReturnValue({
      data: [{ id: 'client-1', display_name: 'Клиент', email: null }],
      error: null,
      isPending: false,
      isSuccess: true,
    });
    const createProject = vi.fn().mockRejectedValue({ kind: 'quota_conflict' });
    useClientProof.useCreateProject.mockReturnValue({
      mutateAsync: createProject,
    });
    const user = userEvent.setup();
    render(createElement(Projects));
    await user.selectOptions(screen.getByLabelText('Клиент'), 'client-1');
    await user.type(screen.getByLabelText('Название'), 'Новый проект');
    await user.click(screen.getByRole('button', { name: 'Создать проект' }));
    expect(createProject).toHaveBeenCalledWith(
      expect.objectContaining({ client_id: 'client-1', name: 'Новый проект' }),
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Достигнут лимит активных проектов тарифа.',
    );
  });

  test('project page posts a comment and submits an explicit approval', async () => {
    resetProjectHooks();
    useUserMock.mockReturnValue({ role: null, roleReady: true });
    const createComment = vi.fn().mockResolvedValue({});
    const createDecision = vi.fn().mockResolvedValue({});
    useClientProof.useCreateComment.mockReturnValue({
      mutateAsync: createComment,
    });
    useClientProof.useCreateDecision.mockReturnValue({
      mutateAsync: createDecision,
    });
    const user = userEvent.setup();
    render(createElement(ProjectRoute));
    await user.type(
      screen.getByLabelText('Новый комментарий'),
      'Пожалуйста, утвердите',
    );
    await user.click(
      screen.getByRole('button', { name: 'Добавить комментарий' }),
    );
    expect(createComment).toHaveBeenCalledWith({
      body: 'Пожалуйста, утвердите',
    });
    await user.click(screen.getByRole('button', { name: 'Принять' }));
    await user.click(
      screen.getByRole('button', { name: 'Подтвердить приёмку' }),
    );
    expect(createDecision).toHaveBeenCalledWith({ decision: 'approved' });
  });

  test('project page surfaces a decision conflict and keeps actions enabled', async () => {
    resetProjectHooks();
    useUserMock.mockReturnValue({ role: null, roleReady: true });
    const createDecision = vi
      .fn()
      .mockRejectedValue({ kind: 'decision_conflict' });
    useClientProof.useCreateDecision.mockReturnValue({
      mutateAsync: createDecision,
    });
    const user = userEvent.setup();
    render(createElement(ProjectRoute));
    await user.click(screen.getByRole('button', { name: 'На доработку' }));
    expect(createDecision).toHaveBeenCalledWith({
      decision: 'changes_requested',
    });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Решение уже зафиксировано. Обновите статус версии.',
    );
    expect(screen.getByRole('button', { name: 'На доработку' })).toBeEnabled();
  });

  test('staff grants project access to a selected client', async () => {
    resetProjectHooks();
    useClientProof.useClients.mockReturnValue({
      data: [{ id: 'client-1', display_name: 'Клиент', email: null }],
      error: null,
      isPending: false,
      isSuccess: true,
    });
    const createGrant = vi.fn().mockResolvedValue({});
    useClientProof.useCreateGrant.mockReturnValue({ mutateAsync: createGrant });
    const user = userEvent.setup();
    render(createElement(ProjectRoute));
    await user.selectOptions(
      screen.getByLabelText('Клиент для доступа'),
      'client-1',
    );
    await user.click(screen.getByRole('button', { name: 'Выдать доступ' }));
    expect(createGrant).toHaveBeenCalledWith({ client_id: 'client-1' });
  });
});

describe('FastAPI conflict response compatibility', () => {
  test('reads nested detail.kind and preserves legacy flat payloads', async () => {
    const realHooks = await vi.importActual<
      typeof import('../../src/hooks/useClientProof')
    >('../../src/hooks/useClientProof');
    const { ApiError } = await import('../../src/api/client');
    for (const body of [
      { detail: { kind: 'decision_conflict' } },
      { kind: 'decision_conflict' },
    ]) {
      const error = new ApiError('Request failed', 409, body);
      expect(realHooks.toClientProofError(error).kind).toBe(
        'decision_conflict',
      );
      expect(realHooks.describeClientProofError(error)).toBe(
        'Решение уже зафиксировано. Обновите статус версии.',
      );
    }
  });
});

describe('project capability boundaries', () => {
  test('a personal organization owner stays a client in a granted agency project', () => {
    resetProjectHooks();
    useUserMock.mockImplementation((organizationId?: string) => ({
      role: organizationId === 'organization-1' ? null : 'owner',
      roleReady: true,
    }));
    render(createElement(ProjectRoute));
    expect(useUserMock).toHaveBeenCalledWith('organization-1');
    expect(screen.getByRole('button', { name: 'Принять' })).toBeVisible();
    expect(
      screen.queryByRole('region', { name: 'Работа с результатами' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Доступ клиентов')).not.toBeInTheDocument();
  });
  test('unresolved membership grants no decision or management capability', () => {
    resetProjectHooks();
    useUserMock.mockReturnValue({ role: null, roleReady: false });
    render(createElement(ProjectRoute));
    expect(
      screen.queryByRole('button', { name: 'Принять' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Доступ клиентов')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Создать результат' }),
    ).not.toBeInTheDocument();
  });
  test('ordinary staff can prepare results but cannot grant client access', () => {
    resetProjectHooks();
    useUserMock.mockReturnValue({ role: 'member', roleReady: true });
    render(createElement(ProjectRoute));
    expect(
      screen.getByRole('button', { name: 'Создать результат' }),
    ).toBeVisible();
    expect(screen.queryByText('Доступ клиентов')).not.toBeInTheDocument();
    expect(useClientProof.useGrants).toHaveBeenLastCalledWith(
      'project-1',
      false,
    );
  });
  test('staff deliverable creation reports server failure without success notice', async () => {
    resetProjectHooks();
    useUserMock.mockReturnValue({ role: 'admin', roleReady: true });
    const create = vi.fn().mockRejectedValue({ kind: 'no_access' });
    useClientProof.useStaffActions.mockReturnValue({
      deliverable: { mutateAsync: create, isPending: false },
    });
    render(createElement(ProjectRoute));
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Название результата'), 'Брендбук');
    await user.click(screen.getByRole('button', { name: 'Создать результат' }));
    expect(create).toHaveBeenCalledWith({ name: 'Брендбук' });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Доступ не предоставлен.',
    );
    expect(screen.queryByText('Результат создан.')).not.toBeInTheDocument();
  });
});

test('auth confirmation rejects external and malformed redirect targets', async () => {
  const { safeRedirect } =
    await import('../../src/components/auth/AuthConfirm');
  expect(safeRedirect('/projects/one?tab=history', 'https://portal.test')).toBe(
    '/projects/one?tab=history',
  );
  for (const path of [
    'https://foreign.test/x',
    '//foreign.test/x',
    '/\\foreign.test/x',
    'javascript:alert(1)',
    null,
  ]) {
    expect(safeRedirect(path, 'https://portal.test')).toBe('/');
  }
});

test('real query hooks isolate actors and invalidate persisted mutation views', async () => {
  const hooks = await vi.importActual<
    typeof import('../../src/hooks/useClientProof')
  >('../../src/hooks/useClientProof');
  const { QueryClient, QueryClientProvider } =
    await import('@tanstack/react-query');
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const invalidate = vi.spyOn(cache, 'invalidateQueries');
  for (const mock of Object.values(apiMocks))
    mock.mockReset().mockResolvedValue([]);
  apiMocks.createFileLink.mockResolvedValue({
    file_id: 'file-one',
    url: 'https://files.test/private',
    expires_in_seconds: 300,
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: cache }, children);
  }
  const { result, rerender } = renderHook(
    () => ({
      accessible: hooks.useClientProjects(),
      staff: hooks.useStaffProjects(),
      clients: hooks.useClients(),
      project: hooks.useProject('project-one'),
      deliverables: hooks.useDeliverables('project-one'),
      versions: hooks.useVersions('project-one'),
      grants: hooks.useGrants('project-one', true),
      comments: hooks.useComments('project-one', 'version-one'),
      decisions: hooks.useDecisions('project-one', 'version-one'),
      files: hooks.useVersionFiles('project-one', 'version-one'),
      createClient: hooks.useCreateClient(),
      createProject: hooks.useCreateProject(),
      grant: hooks.useCreateGrant('project-one'),
      revoke: hooks.useRevokeGrant('project-one'),
      comment: hooks.useCreateComment('project-one', 'version-one'),
      decision: hooks.useCreateDecision('project-one', 'version-one'),
      link: hooks.useFileLink('project-one'),
      actions: hooks.useStaffActions('project-one'),
    }),
    { wrapper: Wrapper },
  );
  await waitFor(() => expect(result.current.files.isSuccess).toBe(true));
  expect(apiMocks.listOrganizationProjects).toHaveBeenCalledWith(
    'organization-1',
  );
  expect(apiMocks.listVersions).toHaveBeenCalledWith('project-one');
  expect(
    cache.getQueryData(['clientproof-versions', 'project-one', 'actor-one']),
  ).toEqual([]);
  actorState.id = 'actor-two';
  rerender();
  await waitFor(() =>
    expect(
      cache.getQueryData(['clientproof-versions', 'project-one', 'actor-two']),
    ).toEqual([]),
  );
  await act(async () => {
    await result.current.createClient.mutateAsync({
      display_name: 'Клиент',
      email: 'client@example.test',
      external_auth_user_id: 'auth-id',
    });
    await result.current.createProject.mutateAsync({
      name: 'Проект',
      client_id: 'client-one',
    });
    await result.current.grant.mutateAsync({ client_id: 'client-one' });
    await result.current.revoke.mutateAsync('grant-one');
    await result.current.comment.mutateAsync({ body: 'Проверено' });
    await result.current.decision.mutateAsync({ decision: 'approved' });
    await result.current.link.createLink('file-one');
    await result.current.actions.deliverable.mutateAsync({ name: 'Результат' });
    await result.current.actions.draft.mutateAsync({
      deliverableId: 'deliverable-one',
      title: 'Версия',
      content: 'Текст',
    });
    await result.current.actions.edit.mutateAsync({
      versionId: 'version-one',
      title: 'Новая версия',
      content: 'Новый текст',
    });
    await result.current.actions.publish.mutateAsync('version-one');
    await result.current.actions.archive.mutateAsync(true);
    await result.current.actions.upload.mutateAsync({
      version: {
        id: 'version-one',
        deliverable_id: 'deliverable-one',
      } as never,
      file: new File(['content'], 'review.txt', { type: 'text/plain' }),
    });
  });
  expect(apiMocks.createDraft).toHaveBeenCalledWith(
    'project-one',
    'deliverable-one',
    { title: 'Версия', content: 'Текст' },
  );
  expect(apiMocks.publishDraft).toHaveBeenCalledWith(
    'project-one',
    'version-one',
  );
  expect(invalidate).toHaveBeenCalledWith({
    queryKey: ['clientproof-accessible-projects'],
  });
  expect(result.current.link.links['file-one'].expires_in_seconds).toBe(300);
  actorState.id = 'actor-one';
  rerender();
  expect(result.current.link.links).toEqual({});
  cache.clear();
});

test('shared API client sends authenticated JSON and preserves failure bodies', async () => {
  const api = await import('../../src/api/client');
  const { z } = await import('zod');
  vi.stubEnv('VITE_BACKEND_URL', 'http://127.0.0.1:18001');
  const fetchMock = vi
    .fn()
    .mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
  vi.stubGlobal('fetch', fetchMock);
  await expect(
    api.apiPost(
      '/resource',
      { body: { value: 1 } },
      z.object({ ok: z.boolean() }),
    ),
  ).resolves.toEqual({ ok: true });
  const options = fetchMock.mock.calls[0][1] as RequestInit;
  expect(new Headers(options.headers).get('Authorization')).toBe(
    'Bearer synthetic-unit-token',
  );
  expect(options.body).toBe('{"value":1}');
  fetchMock.mockResolvedValueOnce(
    new Response('{"detail":{"kind":"decision_conflict"}}', { status: 409 }),
  );
  await expect(
    api.apiPatch('/resource', { body: { value: 2 } }, z.unknown()),
  ).rejects.toMatchObject({
    status: 409,
    body: { detail: { kind: 'decision_conflict' } },
  });
  fetchMock.mockResolvedValueOnce(
    new Response('upstream unavailable', { status: 503 }),
  );
  await expect(
    api.apiGet('/resource', { auth: false }, z.unknown()),
  ).rejects.toMatchObject({ status: 503, body: 'upstream unavailable' });
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
  await expect(api.apiDelete('/resource', {}, z.null())).resolves.toBeNull();
  const form = new FormData();
  form.set('file', 'content');
  fetchMock.mockResolvedValueOnce(new Response('{}'));
  await api.apiPost('/upload', { body: form }, z.object({}));
  expect(
    new Headers((fetchMock.mock.calls.at(-1)?.[1] as RequestInit).headers).has(
      'Content-Type',
    ),
  ).toBe(false);
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('secondary project query truthfulness', () => {
  for (const [name, empty] of [
    ['useDeliverables', 'Результаты не добавлены.'],
    ['useVersionFiles', 'Файлов нет.'],
    ['useComments', 'Комментариев пока нет.'],
    ['useDecisions', 'Решений ещё нет.'],
    ['useGrants', 'Доступы не выданы.'],
  ] as const) {
    test(`${name} failure is an alert rather than an empty persisted resource`, () => {
      resetProjectHooks();
      useUserMock.mockReturnValue({ role: 'admin', roleReady: true });
      const view = render(createElement(ProjectRoute));
      expect(screen.getByText(empty)).toBeVisible();
      useClientProof[name].mockReturnValue({
        // Query errors retain the preceding successful result in the cache.
        data: [],
        isPending: false,
        error: { kind: 'no_access' },
      });
      view.rerender(createElement(ProjectRoute));
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Доступ не предоставлен.',
      );
      expect(screen.queryByText(empty)).not.toBeInTheDocument();
    });
    test(`${name} pending does not show an empty resource`, () => {
      resetProjectHooks();
      useUserMock.mockReturnValue({ role: 'admin', roleReady: true });
      useClientProof[name].mockReturnValue({
        data: undefined,
        isPending: true,
        error: null,
      });
      render(createElement(ProjectRoute));
      expect(screen.queryByText(empty)).not.toBeInTheDocument();
    });
  }
  test('successful empty history is distinct from unavailable history and no version selection', () => {
    resetProjectHooks();
    useUserMock.mockReturnValue({ role: null, roleReady: true });
    const view = render(createElement(ProjectRoute));
    expect(screen.getByText('Решений ещё нет.')).toBeVisible();
    useClientProof.useVersions.mockReturnValue({
      data: [],
      isPending: false,
      error: null,
    });
    view.rerender(createElement(ProjectRoute));
    expect(screen.queryByText('Решений ещё нет.')).not.toBeInTheDocument();
    expect(screen.getAllByText('Выберите опубликованную версию.')).toHaveLength(
      3,
    );
    expect(screen.getByRole('button', { name: 'Принять' })).toBeDisabled();
  });
  test('retained owner value with unresolved membership cannot expose management controls', () => {
    resetProjectHooks();
    useUserMock.mockReturnValue({ role: 'owner', roleReady: true });
    const view = render(createElement(ProjectRoute));
    expect(
      screen.getByRole('button', { name: 'Создать результат' }),
    ).toBeVisible();
    expect(screen.getByText('Доступ клиентов')).toBeVisible();
    useUserMock.mockReturnValue({
      role: 'owner',
      roleReady: false,
      roleError: true,
    });
    view.rerender(createElement(ProjectRoute));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Не удалось проверить доступ',
    );
    expect(
      screen.queryByRole('button', { name: 'Создать результат' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Доступ клиентов')).not.toBeInTheDocument();
    expect(useClientProof.useGrants).toHaveBeenLastCalledWith(
      'project-1',
      false,
    );
  });
});

test('real membership hook removes cached staff capabilities after a failed refetch', async () => {
  const actual = await vi.importActual<
    typeof import('../../src/hooks/useUser')
  >('../../src/hooks/useUser');
  const memberships = await import('../../src/api/memberships');
  const users = await import('../../src/api/users');
  const { ApiError } = await import('../../src/api/client');
  const { QueryClient, QueryClientProvider } =
    await import('@tanstack/react-query');
  const membership = vi
    .spyOn(memberships, 'getMyMembership')
    .mockResolvedValue({ role: 'owner' } as never);
  const user = vi
    .spyOn(users, 'getUser')
    .mockResolvedValue({ username: 'owner' } as never);
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: cache }, children);
  }
  const { result } = renderHook(() => actual.useUser('agency-one'), {
    wrapper: Wrapper,
  });
  await waitFor(() => expect(result.current.role).toBe('owner'));
  membership.mockRejectedValue(new ApiError('unavailable', 503, null));
  await act(async () => {
    await result.current.myMembershipQuery.refetch();
  });
  await waitFor(() => expect(result.current.role).toBeNull());
  expect(result.current.myMembershipQuery.data?.role).toBe('owner');
  expect(result.current.myMembership).toBeNull();
  expect(result.current.roleReady).toBe(false);
  expect(result.current.roleError).toBe(true);
  membership.mockRejectedValue(new ApiError('no membership', 403, null));
  await act(async () => {
    await result.current.myMembershipQuery.refetch();
  });
  await waitFor(() => expect(result.current.role).toBeNull());
  expect(result.current.myMembershipQuery.data?.role).toBe('owner');
  await waitFor(() => expect(result.current.roleReady).toBe(true));
  expect(result.current.roleError).toBe(false);
  membership.mockRestore();
  user.mockRestore();
  cache.clear();
});

test('confirmation failures expose actionable Russian copy rather than provider messages', async () => {
  const { AuthConfirm } = await import('../../src/components/auth/AuthConfirm');
  const previousUrl = window.location.href;
  for (const scenario of [
    {
      query: '?type=email',
      message: 'В ссылке отсутствует код подтверждения.',
    },
    {
      query: '?token_hash=synthetic&type=recovery',
      message: 'Некорректный тип подтверждения.',
    },
    {
      query: '?token_hash=synthetic&type=email',
      message: 'Не удалось подтвердить вход.',
    },
  ]) {
    window.history.replaceState({}, '', `/auth/confirm${scenario.query}`);
    confirmationMocks.verifyOtp.mockResolvedValue({
      error: new Error('Sensitive provider detail in English'),
    });
    render(createElement(AuthConfirm));
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(scenario.message),
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Запросите новое письмо',
    );
    expect(
      screen.queryByText('Sensitive provider detail in English'),
    ).not.toBeInTheDocument();
    cleanup();
  }
  window.history.replaceState({}, '', previousUrl);
});
