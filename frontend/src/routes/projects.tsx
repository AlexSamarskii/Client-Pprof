import { useOrganization } from '../hooks/useOrganization';
import { Link } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from '../components/ui/index.ts';
import type { ProjectStatus } from '../api/schemas/clientproof';
import {
  describeClientProofError,
  toClientProofError,
  useClients,
  useClientProjects,
  useCreateProject,
} from '../hooks/useClientProof';
import { useUser } from '../hooks/useUser';

const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: 'Черновик',
  in_review: 'В согласовании',
  approved: 'Принят',
  changes_requested: 'На доработке',
};

export function Projects() {
  const { role } = useUser();
  const { organization } = useOrganization();
  const clientProjects = useClientProjects();
  const isStaff =
    (role === 'owner' || role === 'admin') &&
    clientProjects.isSuccess &&
    clientProjects.data.every(
      (project) => project.organization_id === organization?.id,
    );
  const clients = useClients(undefined, isStaff);
  const createProject = useCreateProject();
  const [search, setSearch] = useState('');
  const [name, setName] = useState('');
  const [clientId, setClientId] = useState('');
  const [deadline, setDeadline] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const clientOptions = clients.data ?? [];
  const query = clientProjects;
  const projects = query.data ?? [];
  const error = query.error ? toClientProofError(query.error) : null;
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return needle
      ? projects.filter(
          (project) =>
            project.name.toLowerCase().includes(needle) ||
            (project.description ?? '').toLowerCase().includes(needle),
        )
      : projects;
  }, [projects, search]);

  const submitProject = async () => {
    if (!clientId) {
      setActionError('Выберите клиента');
      return;
    }
    try {
      setActionError(null);
      await createProject.mutateAsync({
        client_id: clientId,
        name,
        description: null,
        response_deadline_at: deadline
          ? new Date(deadline).toISOString()
          : null,
      });
      setName('');
      setDeadline('');
    } catch (caught) {
      setActionError(describeClientProofError(caught));
    }
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Проекты</h1>
      {query.isPending ? <div role="status">Загрузка…</div> : null}
      {error ? <div role="alert">{describeClientProofError(error)}</div> : null}
      {query.isSuccess && projects.length === 0 ? (
        <div role="status">Проекты не найдены.</div>
      ) : null}
      {isStaff && clients.isSuccess && clientOptions.length === 0 ? (
        <div role="status">Сначала добавьте клиента в разделе «Клиенты».</div>
      ) : null}
      {isStaff && clientOptions.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Новый проект</CardTitle>
            <CardDescription>
              Создание проверяет квоту тарифа на сервере.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void submitProject();
              }}
            >
              <div>
                <Label htmlFor="project-client">Клиент</Label>
                <select
                  id="project-client"
                  value={clientId}
                  onChange={(event) => setClientId(event.target.value)}
                >
                  <option value="">Выберите клиента</option>
                  {clientOptions.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.display_name ?? client.email ?? client.id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="project-name">Название</Label>
                <Input
                  id="project-name"
                  value={name}
                  isRequired
                  onChange={setName}
                />
              </div>
              <div>
                <Label htmlFor="project-deadline">Срок ответа</Label>
                <input
                  id="project-deadline"
                  type="datetime-local"
                  value={deadline}
                  onChange={(event) => setDeadline(event.target.value)}
                  className="h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <button type="submit" disabled={createProject.isPending}>
                {createProject.isPending ? 'Сохранение…' : 'Создать проект'}
              </button>
              {actionError ? <div role="alert">{actionError}</div> : null}
            </form>
          </CardContent>
        </Card>
      ) : null}
      <div>
        <Label htmlFor="project-search">Поиск проектов</Label>
        <Input
          id="project-search"
          type="search"
          value={search}
          onChange={setSearch}
        />
      </div>
      <div className="grid gap-4">
        {filtered.map((project) => (
          <Card key={project.id}>
            <CardHeader>
              <CardTitle>{project.name}</CardTitle>
              <CardDescription>
                {STATUS_LABELS[project.status]}
                {project.archived_at ? ' • архив' : ''}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link
                to="/projects/$projectId"
                params={{ projectId: project.id }}
                className="underline"
              >
                Открыть
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
