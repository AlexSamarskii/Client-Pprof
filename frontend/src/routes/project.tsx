import { Link, useParams } from '@tanstack/react-router';
import { useId, useMemo, useState } from 'react';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from '../components/ui/index.ts';
import type { DecisionKind } from '../api/schemas/clientproof';
import {
  describeClientProofError,
  toClientProofError,
  useClients,
  useComments,
  useCreateGrant,
  useCreateComment,
  useCreateDecision,
  useDeliverables,
  useDecisions,
  useFileLink,
  useGrants,
  useProject,
  useRevokeGrant,
  useVersionFiles,
  useStaffActions,
  useVersions,
} from '../hooks/useClientProof';
import { useUser } from '../hooks/useUser';

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString('ru-RU') : '—';
}

export function ProjectRoute() {
  const routeParams = useParams({ strict: false });
  const projectId = routeParams.projectId ?? '';
  const projectQuery = useProject(projectId);
  const { role, roleReady, roleError } = useUser(
    projectQuery.data?.organization_id ?? null,
  );
  const isStaff = roleReady && role !== null;
  const canManageGrants = roleReady && (role === 'owner' || role === 'admin');
  const deliverablesQuery = useDeliverables(projectId);
  const versionsQuery = useVersions(projectId);
  const clientsQuery = useClients(
    projectQuery.data?.organization_id,
    canManageGrants,
  );
  const grantsQuery = useGrants(projectId, canManageGrants);
  const revokeGrantMutation = useRevokeGrant(projectId);
  const createGrant = useCreateGrant(projectId);
  const fileLinkMutation = useFileLink(projectId);
  const [selectedVersionId, setSelectedVersionId] = useState('');
  const [commentBody, setCommentBody] = useState('');
  const [commentError, setCommentError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [grantError, setGrantError] = useState<string | null>(null);
  const [fileLinkError, setFileLinkError] = useState<string | null>(null);
  const [grantClientId, setGrantClientId] = useState('');
  const [confirmingApproval, setConfirmingApproval] = useState(false);
  const commentFieldId = useId();

  const publishedVersions = useMemo(
    () =>
      (versionsQuery.data ?? [])
        .filter((version) => version.published_at !== null)
        .sort((first, second) =>
          (second.published_at ?? '').localeCompare(first.published_at ?? ''),
        ),
    [versionsQuery.data],
  );
  const versionId = selectedVersionId || publishedVersions[0]?.id || '';
  const selectedVersion = publishedVersions.find(
    (version) => version.id === versionId,
  );
  const commentsQuery = useComments(projectId, versionId);
  const decisionsQuery = useDecisions(projectId, versionId);
  const filesQuery = useVersionFiles(projectId, versionId);
  const createComment = useCreateComment(projectId, versionId);
  const createDecision = useCreateDecision(projectId, versionId);
  const clientOptions = clientsQuery.data ?? [];
  const clientNameById = useMemo(() => {
    return new Map(
      (clientsQuery.data ?? []).map((client) => [
        client.id,
        client.display_name ?? client.email ?? client.id,
      ]),
    );
  }, [clientsQuery.data]);

  if (projectQuery.isPending || versionsQuery.isPending) {
    return <div role="status">Загрузка проекта…</div>;
  }
  if (projectQuery.error || versionsQuery.error) {
    const error = toClientProofError(projectQuery.error ?? versionsQuery.error);
    return <div role="alert">{describeClientProofError(error)}</div>;
  }
  const project = projectQuery.data;

  const submitGrant = async () => {
    if (!grantClientId) {
      setGrantError('Выберите клиента');
      return;
    }
    try {
      setGrantError(null);
      await createGrant.mutateAsync({ client_id: grantClientId });
      setGrantClientId('');
    } catch (caught) {
      setGrantError(describeClientProofError(caught));
    }
  };

  const createFileLink = async (fileId: string) => {
    try {
      setFileLinkError(null);
      await fileLinkMutation.createLink(fileId);
    } catch (caught) {
      setFileLinkError(describeClientProofError(caught));
    }
  };

  const revokeGrant = async (grantId: string) => {
    try {
      setGrantError(null);
      await revokeGrantMutation.mutateAsync(grantId);
    } catch (caught) {
      setGrantError(describeClientProofError(caught));
    }
  };

  const submitComment = async () => {
    if (!versionId || commentBody.trim().length === 0) return;
    try {
      setCommentError(null);
      await createComment.mutateAsync({ body: commentBody.trim() });
      setCommentBody('');
    } catch (caught) {
      setCommentError(describeClientProofError(caught));
    }
  };

  const submitDecision = async (decision: DecisionKind) => {
    if (!versionId) return;
    try {
      setDecisionError(null);
      setConfirmingApproval(false);
      await createDecision.mutateAsync({ decision });
    } catch (caught) {
      setDecisionError(describeClientProofError(caught));
    }
  };

  return (
    <div className="space-y-6 p-6">
      <Link to="/projects" className="underline">
        К проектам
      </Link>
      {roleError ? (
        <p role="alert">
          Не удалось проверить доступ. Обновите страницу, чтобы повторить
          проверку. Действия недоступны.
        </p>
      ) : null}
      {isStaff && !deliverablesQuery.error && !deliverablesQuery.isPending ? (
        <StaffEditor
          projectId={projectId}
          versions={versionsQuery.data}
          deliverables={deliverablesQuery.data}
          archived={!!project.archived_at}
        />
      ) : null}
      <header>
        <h1 className="text-2xl font-semibold">{project.name}</h1>
        <p className="text-sm text-muted-foreground">
          Статус:{' '}
          {
            {
              draft: 'Черновик',
              in_review: 'В согласовании',
              approved: 'Принят',
              changes_requested: 'На доработке',
            }[project.status]
          }
          . Срок ответа: {formatDateTime(project.response_deadline_at)}
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Результаты</CardTitle>
          <CardDescription>
            Комментарии и решения привязаны к версии.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {deliverablesQuery.isPending ? (
            <div role="status">Загрузка…</div>
          ) : null}
          {deliverablesQuery.error ? (
            <p role="alert">
              Не удалось загрузить результаты.{' '}
              {describeClientProofError(deliverablesQuery.error)} Обновите
              страницу для повторной загрузки.
            </p>
          ) : null}
          {!deliverablesQuery.isPending && !deliverablesQuery.error ? (
            <>
              {deliverablesQuery.data.length === 0 ? (
                <div role="status">Результаты не добавлены.</div>
              ) : (
                <ul>
                  {deliverablesQuery.data.map((deliverable) => (
                    <li key={deliverable.id}>{deliverable.name}</li>
                  ))}
                </ul>
              )}
            </>
          ) : null}
          <div>
            <Label htmlFor={`version-${commentFieldId}`}>Версия</Label>
            <select
              id={`version-${commentFieldId}`}
              value={versionId}
              onChange={(event) => setSelectedVersionId(event.target.value)}
            >
              {publishedVersions.length === 0 ? (
                <option value="">Нет опубликованных версий</option>
              ) : null}
              {publishedVersions.map((version) => (
                <option key={version.id} value={version.id}>
                  {version.title} (v{version.version_number})
                </option>
              ))}
            </select>
          </div>
          {selectedVersion ? (
            <article>
              <h2 className="text-lg font-semibold">{selectedVersion.title}</h2>
              <pre className="whitespace-pre-wrap">
                {selectedVersion.content}
              </pre>
            </article>
          ) : (
            <div role="status">Опубликованная версия не выбрана.</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Файлы</CardTitle>
          <CardDescription>
            Ссылки выдаются на сервере и ограничены по времени.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {versionId ? (
            <>
              {filesQuery.isPending ? (
                <div role="status">Загрузка файлов…</div>
              ) : null}
              {filesQuery.error ? (
                <p role="alert">
                  Не удалось загрузить файлы.{' '}
                  {describeClientProofError(filesQuery.error)} Обновите страницу
                  для повторной загрузки.
                </p>
              ) : null}
            </>
          ) : (
            <p role="status">Выберите опубликованную версию.</p>
          )}
          {!!versionId && !filesQuery.isPending && !filesQuery.error ? (
            <>
              {filesQuery.data.length === 0 ? (
                <div role="status">Файлов нет.</div>
              ) : (
                <ul className="space-y-2">
                  {filesQuery.data.map((file) => (
                    <li
                      key={file.id}
                      className="flex flex-wrap items-center gap-2"
                    >
                      <span>{file.filename}</span>
                      <Button
                        variant="outline"
                        size="sm"
                        isDisabled={fileLinkMutation.isPending}
                        onClick={() => void createFileLink(file.id)}
                      >
                        Получить ссылку
                      </Button>
                      {Object.hasOwn(fileLinkMutation.links, file.id) ? (
                        <a
                          href={fileLinkMutation.links[file.id].url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          Открыть
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : null}
          {fileLinkError ? <div role="alert">{fileLinkError}</div> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Комментарии</CardTitle>
          <CardDescription>
            Лента относится только к выбранной версии.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {versionId ? (
            <>
              {commentsQuery.isPending ? (
                <div role="status">Загрузка комментариев…</div>
              ) : null}
              {commentsQuery.error ? (
                <p role="alert">
                  Не удалось загрузить комментарии.{' '}
                  {describeClientProofError(commentsQuery.error)} Обновите
                  страницу для повторной загрузки.
                </p>
              ) : null}
            </>
          ) : (
            <p role="status">Выберите опубликованную версию.</p>
          )}
          {!!versionId && !commentsQuery.isPending && !commentsQuery.error ? (
            <>
              {commentsQuery.data.length === 0 ? (
                <div role="status">Комментариев пока нет.</div>
              ) : (
                <ul className="space-y-3">
                  {commentsQuery.data.map((comment) => (
                    <li key={comment.id}>
                      <div className="text-sm text-muted-foreground">
                        {formatDateTime(comment.created_at)}
                      </div>
                      <p>{comment.body}</p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : null}
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void submitComment();
            }}
          >
            <Label htmlFor={`comment-${commentFieldId}`}>
              Новый комментарий
            </Label>
            <Input
              id={`comment-${commentFieldId}`}
              value={commentBody}
              isRequired
              onChange={setCommentBody}
            />
            <button
              type="submit"
              disabled={
                createComment.isPending ||
                !versionId ||
                commentsQuery.isPending ||
                !!commentsQuery.error
              }
            >
              {createComment.isPending ? 'Сохранение…' : 'Добавить комментарий'}
            </button>
            {commentError ? <div role="alert">{commentError}</div> : null}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Решение по версии</CardTitle>
          <CardDescription>
            Действие применяется к версии{' '}
            {selectedVersion ? `«${selectedVersion.title}»` : '—'}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <>
            {versionId ? (
              <>
                {decisionsQuery.isPending ? (
                  <div role="status">Загрузка решений…</div>
                ) : null}
                {decisionsQuery.error ? (
                  <p role="alert">
                    Не удалось загрузить решения.{' '}
                    {describeClientProofError(decisionsQuery.error)} Обновите
                    страницу для повторной загрузки.
                  </p>
                ) : null}
              </>
            ) : (
              <p role="status">Выберите опубликованную версию.</p>
            )}
            {!!versionId &&
            !decisionsQuery.isPending &&
            !decisionsQuery.error ? (
              <>
                {decisionsQuery.data.length === 0 ? (
                  <div role="status">Решений ещё нет.</div>
                ) : (
                  <ul>
                    {decisionsQuery.data.map((decision) => (
                      <li key={decision.id}>
                        {decision.decision === 'approved'
                          ? 'Принято'
                          : 'На доработку'}{' '}
                        • {decision.active ? 'активное' : 'история'} •{' '}
                        {formatDateTime(decision.created_at)}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            ) : null}
          </>
          {roleReady && !isStaff ? (
            <>
              {!confirmingApproval ? (
                <Button
                  isDisabled={
                    !versionId ||
                    decisionsQuery.isPending ||
                    !!decisionsQuery.error
                  }
                  onClick={() => setConfirmingApproval(true)}
                >
                  Принять
                </Button>
              ) : (
                <div className="space-y-2">
                  <p>Подтвердите приёмку конкретной версии.</p>
                  <Button
                    type="button"
                    isDisabled={
                      createDecision.isPending ||
                      !versionId ||
                      decisionsQuery.isPending ||
                      !!decisionsQuery.error
                    }
                    onClick={() => void submitDecision('approved')}
                  >
                    {createDecision.isPending
                      ? 'Сохранение…'
                      : 'Подтвердить приёмку'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setConfirmingApproval(false)}
                  >
                    Отмена
                  </Button>
                </div>
              )}
              <Button
                variant="secondary"
                isDisabled={
                  createDecision.isPending ||
                  !versionId ||
                  decisionsQuery.isPending ||
                  !!decisionsQuery.error
                }
                onClick={() => void submitDecision('changes_requested')}
              >
                {createDecision.isPending ? 'Сохранение…' : 'На доработку'}
              </Button>
              {decisionError ? <div role="alert">{decisionError}</div> : null}
            </>
          ) : null}
        </CardContent>
      </Card>

      {canManageGrants ? (
        <Card>
          <CardHeader>
            <CardTitle>Доступ клиентов</CardTitle>
            <CardDescription>
              Отзыв grant прекращает доступ немедленно.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {clientsQuery.isPending ? (
              <p role="status">Загрузка клиентов…</p>
            ) : null}
            {clientsQuery.error ? (
              <p role="alert">
                Не удалось загрузить клиентов.{' '}
                {describeClientProofError(clientsQuery.error)}
              </p>
            ) : null}
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void submitGrant();
              }}
            >
              <div>
                <Label htmlFor="grant-client">Клиент для доступа</Label>
                <select
                  id="grant-client"
                  value={grantClientId}
                  onChange={(event) => setGrantClientId(event.target.value)}
                >
                  <option value="">Выберите клиента</option>
                  {clientOptions.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.display_name ?? client.email ?? client.id}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                type="submit"
                isDisabled={
                  createGrant.isPending ||
                  clientsQuery.isPending ||
                  !!clientsQuery.error
                }
              >
                {createGrant.isPending ? 'Сохранение…' : 'Выдать доступ'}
              </Button>
              {grantError ? <div role="alert">{grantError}</div> : null}
            </form>
            {grantsQuery.isPending ? <div role="status">Загрузка…</div> : null}
            {grantsQuery.error ? (
              <p role="alert">
                Не удалось загрузить доступы.{' '}
                {describeClientProofError(grantsQuery.error)} Обновите страницу
                для повторной загрузки.
              </p>
            ) : null}
            {!grantsQuery.isPending && !grantsQuery.error ? (
              <>
                {grantsQuery.data.length === 0 ? (
                  <div role="status">Доступы не выданы.</div>
                ) : (
                  <ul className="space-y-2">
                    {grantsQuery.data.map((grant) => (
                      <li
                        key={grant.id}
                        className="flex flex-wrap items-center gap-2"
                      >
                        <span>
                          {clientNameById.get(grant.client_id) ??
                            grant.client_id}
                        </span>
                        <span>
                          {grant.status === 'active' ? 'Действует' : 'Отозван'}
                        </span>
                        {grant.status === 'active' ? (
                          <Button
                            variant="destructive"
                            size="sm"
                            isDisabled={revokeGrantMutation.isPending}
                            onClick={() => void revokeGrant(grant.id)}
                          >
                            Отозвать
                          </Button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function StaffEditor({
  projectId,
  versions,
  deliverables,
  archived,
}: {
  projectId: string;
  versions: import('../api/schemas/clientproof').DeliverableVersion[];
  deliverables: import('../api/schemas/clientproof').Deliverable[];
  archived: boolean;
}) {
  const actions = useStaffActions(projectId);
  const [name, setName] = useState('');
  const [deliverableId, setDeliverableId] = useState('');
  const [draftId, setDraftId] = useState('');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const draft = versions.find((v) => v.id === draftId && !v.published_at);
  const busy = Object.values(actions).some((a) => a.isPending);
  const perform = async (action: () => Promise<unknown>, message: string) => {
    setError('');
    setNotice('');
    try {
      await action();
      setNotice(message);
    } catch (e) {
      setError(describeClientProofError(e));
    }
  };
  return (
    <section
      aria-label="Работа с результатами"
      className="space-y-4 rounded-md border p-4"
    >
      <h2 className="text-xl font-semibold">Подготовка результата</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void perform(
            () => actions.deliverable.mutateAsync({ name }),
            'Результат создан.',
          );
        }}
      >
        <label htmlFor="deliverable-name">Название результата</label>
        <input
          className="border p-2"
          id="deliverable-name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button disabled={busy}>Создать результат</button>
      </form>
      <label htmlFor="draft-deliverable">Результат для версии</label>
      <select
        id="draft-deliverable"
        value={deliverableId}
        onChange={(e) => setDeliverableId(e.target.value)}
      >
        <option value="">Выберите результат</option>
        {deliverables.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
      <label htmlFor="edit-draft">Черновик для редактирования</label>
      <select
        id="edit-draft"
        value={draftId}
        onChange={(e) => {
          setDraftId(e.target.value);
          const v = versions.find((v) => v.id === e.target.value);
          setTitle(v?.title ?? '');
          setContent(v?.content ?? '');
        }}
      >
        <option value="">Новая версия</option>
        {versions
          .filter((v) => !v.published_at)
          .map((v) => (
            <option key={v.id} value={v.id}>
              {v.title}
            </option>
          ))}
      </select>
      <form
        className="grid gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void perform(async () => {
            const v = draft
              ? await actions.edit.mutateAsync({
                  versionId: draft.id,
                  title,
                  content,
                })
              : await actions.draft.mutateAsync({
                  deliverableId,
                  title,
                  content,
                });
            setDraftId(v.id);
          }, 'Черновик сохранён.');
        }}
      >
        <label htmlFor="version-title">Название версии</label>
        <input
          className="border p-2"
          id="version-title"
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <label htmlFor="version-content">Содержимое версии</label>
        <textarea
          className="border p-2"
          id="version-content"
          required
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <button disabled={busy || (!draft && !deliverableId)}>
          {draft ? 'Сохранить черновик' : 'Создать черновик'}
        </button>
      </form>
      {draft ? (
        <>
          <label htmlFor="draft-file">Файл к черновику</label>
          <input
            id="draft-file"
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <button
            disabled={busy || !file}
            onClick={() => {
              if (file)
                void perform(
                  () => actions.upload.mutateAsync({ version: draft, file }),
                  'Файл загружен.',
                );
            }}
          >
            Загрузить файл
          </button>
          <button
            disabled={busy}
            onClick={() =>
              void perform(async () => {
                await actions.publish.mutateAsync(draft.id);
                setDraftId('');
                setTitle('');
                setContent('');
              }, 'Версия опубликована.')
            }
          >
            Опубликовать версию
          </button>
        </>
      ) : null}
      <button
        disabled={busy}
        onClick={() =>
          void perform(
            () => actions.archive.mutateAsync(!archived),
            archived ? 'Проект возвращён из архива.' : 'Проект архивирован.',
          )
        }
      >
        {archived ? 'Вернуть из архива' : 'Архивировать проект'}
      </button>
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
    </section>
  );
}
