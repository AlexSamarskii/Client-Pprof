import { Link } from '@tanstack/react-router';
import { useMemo } from 'react';
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../components/ui/index.ts';
import type { Project } from '../api/schemas/clientproof';
import {
  describeClientProofError,
  isOverdueProject,
  isPendingProject,
  toClientProofError,
  useClientProjects,
} from '../hooks/useClientProof';

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString('ru-RU') : 'не задан';
}

function ProjectCard({ project }: { project: Project }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{project.name}</CardTitle>
        <CardDescription>
          Статус:{' '}
          {
            {
              draft: 'Черновик',
              in_review: 'В согласовании',
              approved: 'Принят',
              changes_requested: 'На доработке',
            }[project.status]
          }
          . Срок ответа: {formatDate(project.response_deadline_at)}
        </CardDescription>
      </CardHeader>
      <Link
        to="/projects/$projectId"
        params={{ projectId: project.id }}
        className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground outline-none underline-offset-4 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background hover:underline"
      >
        Открыть проект
      </Link>
    </Card>
  );
}

export function Dashboard() {
  const clientProjects = useClientProjects();
  const query = clientProjects;
  const projects = query.data ?? [];
  const pending = useMemo(() => projects.filter(isPendingProject), [projects]);
  const overdue = useMemo(
    () => projects.filter((project) => isOverdueProject(project)),
    [projects],
  );
  const error = query.error ? toClientProofError(query.error) : null;

  if (query.isPending) return <div role="status">Загрузка…</div>;
  if (error) return <div role="alert">{describeClientProofError(error)}</div>;
  if (projects.length === 0) return <div role="status">Проектов пока нет.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Рабочая панель</h1>
      <section aria-label="Ожидают согласования">
        <h2 className="text-xl font-semibold">Ожидают согласования</h2>
        {pending.length === 0 ? (
          <p>Нет проектов в согласовании.</p>
        ) : (
          <div className="grid gap-4">
            {pending.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </section>
      <section aria-label="Просроченные ответы">
        <h2 className="text-xl font-semibold">Просроченные ответы</h2>
        {overdue.length === 0 ? (
          <p>Просроченных проектов нет.</p>
        ) : (
          <div className="grid gap-4">
            {overdue.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </section>
      {(['draft', 'approved', 'changes_requested'] as const).map((status) => (
        <section
          key={status}
          aria-label={
            {
              draft: 'Черновики',
              approved: 'Принятые проекты',
              changes_requested: 'На доработке',
            }[status]
          }
        >
          <h2 className="text-xl font-semibold">
            {
              {
                draft: 'Черновики',
                approved: 'Принятые проекты',
                changes_requested: 'На доработке',
              }[status]
            }
          </h2>
          {projects.filter((project) => project.status === status).length ===
          0 ? (
            <p>Нет проектов.</p>
          ) : (
            projects
              .filter((project) => project.status === status)
              .map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))
          )}
        </section>
      ))}
    </div>
  );
}
