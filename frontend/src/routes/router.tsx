import { useEffect } from 'react';
import { useAuth } from '@/components/auth/AuthProvider';
import { createRootRoute, createRoute, redirect } from '@tanstack/react-router';
import { Outlet } from '@tanstack/react-router';
import { Clients } from './clients';
import { useParams } from '@tanstack/react-router';
import { useProject, useClientProjects } from '@/hooks/useClientProof';
import { useOrganization } from '@/hooks/useOrganization';
import { About } from './about';
import { Login } from './login';
import { Accounts } from './accounts';
import { Members } from './members';
import { Pricing } from './pricing';
import { AuthConfirmRoute } from './auth-confirm';
import { Dashboard } from './dashboard';
import { ProjectRoute } from './project';
import { Projects } from './projects';
import { supabase } from '@/supabase/client';
import { LeftNav, type NavigationItem } from '@/components/layout/LeftNav';
import { SetUsernameModal } from '@/components/SetUsernameModal';
import { useUser } from '@/hooks/useUser';

const BASE_NAVIGATION: NavigationItem[] = [
  { label: 'Рабочая панель', to: '/dashboard' },
  { label: 'Проекты', to: '/projects' },
];

function useCapabilities() {
  const { user: actor } = useAuth();
  const personaKey = `clientproof-client-view:${actor?.id ?? 'anonymous'}`;
  const { organization } = useOrganization();
  const projects = useClientProjects();
  const params = useParams({ strict: false });
  const project = useProject(params.projectId ?? '');
  const { role, roleReady } = useUser(
    params.projectId ? (project.data?.organization_id ?? null) : undefined,
  );
  const clientView = params.projectId
    ? !!project.data && project.data.organization_id !== organization?.id
    : (projects.data ?? []).some((p) => p.organization_id !== organization?.id);
  const confirmedClient =
    !!params.projectId && !!project.data && roleReady && role === null;
  useEffect(() => {
    if (confirmedClient && actor) sessionStorage.setItem(personaKey, 'client');
  }, [confirmedClient, actor, personaKey]);
  // Retain the chosen client context when the final project grant disappears.
  const rememberedClient = sessionStorage.getItem(personaKey) === 'client';
  return {
    role,
    ready: roleReady && projects.isSuccess,
    clientView: clientView || rememberedClient,
  };
}
function Administration({
  children,
  billing = false,
  profile = false,
}: {
  children: React.ReactNode;
  billing?: boolean;
  profile?: boolean;
}) {
  const { role, ready, clientView } = useCapabilities();
  if (!ready) return <p role="status">Проверка доступа…</p>;
  let permitted = role === 'owner' || role === 'admin';
  if (billing) permitted = role === 'owner';
  if (profile) permitted = role !== null;
  if (clientView || !permitted)
    return <p role="alert">Доступ не предоставлен.</p>;
  return <>{children}</>;
}

function RootLayout() {
  return (
    <>
      <Outlet />
      {/* <TanStackRouterDevtools /> */}
    </>
  );
}

export const ROOT_ROUTE = createRootRoute({
  component: RootLayout,
});

function ProtectedShell() {
  const { user, userQuery } = useUser();
  const { role, ready, clientView } = useCapabilities();
  const navigation = [...BASE_NAVIGATION];
  if (ready && !clientView) {
    navigation.push({ label: 'Профиль', to: '/accounts' });
    if (role === 'owner' || role === 'admin') {
      navigation.push(
        { label: 'Клиенты', to: '/clients' },
        { label: 'Участники', to: '/members' },
      );
    }
    if (role === 'owner') navigation.push({ label: 'Тарифы', to: '/upgrade' });
  }
  // Force every authenticated user to set a username before using the app.
  // Modal is non-dismissable; it disappears once SetUsernameModal's mutation
  // succeeds and useUser's cache invalidates.
  const needsUsername =
    ready &&
    !clientView &&
    userQuery.isSuccess &&
    user !== null &&
    (user.username === null ||
      user.username === undefined ||
      user.username.trim() === '');

  return (
    <div className="min-h-screen flex bg-background">
      <LeftNav navigation={navigation} />
      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
      {needsUsername && <SetUsernameModal />}
    </div>
  );
}

const protectedLayout = createRoute({
  getParentRoute: () => ROOT_ROUTE,
  id: 'protected',
  beforeLoad: async ({ location }) => {
    const result = await supabase.auth.getSession();
    if (result.error || !result.data.session) {
      return redirect({
        to: '/login',
        search: {
          redirect: location.href,
        },
      });
    }
  },
  component: ProtectedShell,
});

const home = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/',
  component: Dashboard,
});

const dashboard = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/dashboard',
  component: Dashboard,
});

const projects = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/projects',
  component: Projects,
});

const clients = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/clients',
  component: () => (
    <Administration>
      <Clients />
    </Administration>
  ),
});

const project = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/projects/$projectId',
  component: ProjectRoute,
});

const about = createRoute({
  getParentRoute: () => ROOT_ROUTE,
  path: '/about',
  component: About,
});

const login = createRoute({
  getParentRoute: () => ROOT_ROUTE,
  path: '/login',
  component: Login,
});

const accounts = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/accounts',
  component: () => (
    <Administration profile>
      <Accounts />
    </Administration>
  ),
});

const members = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/members',
  component: () => (
    <Administration>
      <Members />
    </Administration>
  ),
});

const pricing = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/upgrade',
  component: () => (
    <Administration billing>
      <Pricing />
    </Administration>
  ),
});

const authConfirm = createRoute({
  getParentRoute: () => ROOT_ROUTE,
  path: '/auth/confirm',
  component: AuthConfirmRoute,
});

export const ROUTES = [
  protectedLayout.addChildren([
    home,
    dashboard,
    projects,
    project,
    clients,
    accounts,
    members,
    pricing,
  ]),
  about,
  login,
  authConfirm,
];
