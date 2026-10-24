import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthProvider';
import { useOrganization } from '@/hooks/useOrganization';
import { useUser } from '@/hooks/useUser';
import { updateUser } from '@/api/users';
import { getMyMembership } from '@/api/memberships';
import { Button } from '@/components/ui/button';
import { SignOutButton } from '@/components/auth/SignOutButton';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

function normalizeOptionalText(value: string) {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return null;
  }
  return trimmed;
}

export function Accounts() {
  const auth = useAuth();
  const { organization, organizationsQuery } = useOrganization();
  const { user, userQuery } = useUser();
  const activeOrganizationId = organization?.id ?? null;
  const userId = auth.user?.id ?? null;

  const membershipQuery = useQuery({
    queryKey: ['membership', activeOrganizationId],
    enabled:
      auth.isLoading === false &&
      auth.user !== null &&
      activeOrganizationId !== null,
    queryFn: async () => {
      if (!activeOrganizationId) {
        throw new Error('Missing organization id');
      }
      return getMyMembership(activeOrganizationId);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!userId || !activeOrganizationId) {
        throw new Error('Missing user id');
      }
      return updateUser(activeOrganizationId, userId, payloadToSave);
    },
    onSuccess: async () => {
      await userQuery.refetch();
      setIsDirty(false);
    },
  });

  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [isDirty, setIsDirty] = useState(false);

  const initialFormState = useMemo(() => {
    return {
      username: user?.username ?? '',
      full_name: user?.full_name ?? '',
      avatar_url: user?.avatar_url ?? '',
    };
  }, [user?.username, user?.full_name, user?.avatar_url]);

  useEffect(() => {
    setUsername(initialFormState.username);
    setFullName(initialFormState.full_name);
    setAvatarUrl(initialFormState.avatar_url);
    setIsDirty(false);
  }, [initialFormState]);

  const payloadToSave = useMemo(() => {
    const next = {
      username: normalizeOptionalText(username),
      full_name: normalizeOptionalText(fullName),
      avatar_url: normalizeOptionalText(avatarUrl),
    };

    const previous = {
      username: user?.username ?? null,
      full_name: user?.full_name ?? null,
      avatar_url: user?.avatar_url ?? null,
    };

    const payload: Record<string, unknown> = {};
    // Username is required app-wide (enforced by SetUsernameModal). Never send
    // a clear: drop username from the payload if the user has emptied it.
    if (next.username !== previous.username && next.username !== null) {
      payload.username = next.username;
    }
    if (next.full_name !== previous.full_name)
      payload.full_name = next.full_name;
    if (next.avatar_url !== previous.avatar_url)
      payload.avatar_url = next.avatar_url;
    return payload;
  }, [avatarUrl, fullName, username, user]);

  const usernameError = useMemo(() => {
    const trimmed = username.trim();
    if (trimmed === '') return 'Укажите имя пользователя.';
    if (trimmed.length < 3)
      return `Имя должно содержать не менее трёх символов (${trimmed.length}/3).`;
    return null;
  }, [username]);

  const cardStatus = useMemo((): {
    message: string;
    isError: boolean;
  } | null => {
    if (auth.isLoading) return { message: 'Загрузка сеанса…', isError: false };
    if (!auth.user) return { message: 'Войдите в систему.', isError: true };
    if (organizationsQuery.isLoading) {
      return { message: 'Загрузка агентств…', isError: false };
    }
    if (organizationsQuery.isError) {
      return { message: 'Не удалось загрузить агентства.', isError: true };
    }
    if (!activeOrganizationId) {
      return { message: 'Агентство не выбрано.', isError: false };
    }
    if (membershipQuery.isLoading) {
      return { message: 'Проверка участия…', isError: false };
    }
    if (membershipQuery.isError) {
      return { message: 'Не удалось проверить участие.', isError: true };
    }
    if (userQuery.isLoading) {
      return { message: 'Загрузка профиля…', isError: false };
    }
    if (userQuery.isError) {
      return { message: 'Не удалось загрузить профиль.', isError: true };
    }
    if (!user) return null;
    return null;
  }, [
    auth.isLoading,
    auth.user,
    activeOrganizationId,
    organizationsQuery.isLoading,
    organizationsQuery.isError,
    membershipQuery.isLoading,
    membershipQuery.isError,
    userQuery.isLoading,
    userQuery.isError,
    user,
  ]);

  const showForm = user != null && cardStatus === null;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Профиль</CardTitle>
          <CardDescription>Просмотр и изменение профиля.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {cardStatus && (
            <p
              className={
                cardStatus.isError
                  ? 'text-sm text-destructive'
                  : 'text-sm text-muted-foreground'
              }
            >
              {cardStatus.message}
            </p>
          )}
          {showForm && (
            <>
              <div className="grid gap-2">
                <Label>Агентство</Label>
                <p className="text-sm text-muted-foreground">
                  {organization?.name ?? 'Неизвестно'}
                </p>
                <p className="text-sm text-muted-foreground break-all">
                  {activeOrganizationId}
                </p>
              </div>

              <div className="grid gap-2">
                <Label>Участие</Label>
                <p className="text-sm text-muted-foreground">
                  Роль: {membershipQuery.data?.role ?? 'Неизвестно'}
                </p>
                <p className="text-sm text-muted-foreground break-all">
                  {membershipQuery.data?.id ?? 'Неизвестно'}
                </p>
              </div>

              <div className="grid gap-2">
                <Label>Идентификатор</Label>
                <p className="text-sm text-muted-foreground break-all">
                  {user.id}
                </p>
              </div>

              <div className="grid gap-2">
                <Label>Создано</Label>
                <p className="text-sm text-muted-foreground">
                  {user.created_at}
                </p>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="username">Имя пользователя</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(value) => {
                    setUsername(value);
                    setIsDirty(true);
                  }}
                  placeholder="вашеимя"
                  isRequired
                />
                {usernameError && (
                  <p className="text-xs text-destructive">{usernameError}</p>
                )}
              </div>

              <div className="grid gap-2">
                <Label htmlFor="full_name">Полное имя</Label>
                <Input
                  id="full_name"
                  value={fullName}
                  onChange={(value) => {
                    setFullName(value);
                    setIsDirty(true);
                  }}
                  placeholder="Иван Иванов"
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="avatar_url">Ссылка на аватар</Label>
                <Input
                  id="avatar_url"
                  type="url"
                  value={avatarUrl}
                  onChange={(value) => {
                    setAvatarUrl(value);
                    setIsDirty(true);
                  }}
                  placeholder="https://…"
                />
              </div>

              {updateMutation.isError && (
                <p className="text-sm text-destructive">
                  Не удалось сохранить изменения.
                </p>
              )}
              {updateMutation.isSuccess && (
                <p className="text-sm text-muted-foreground">Сохранено.</p>
              )}
            </>
          )}
        </CardContent>
        <CardFooter className="justify-between">
          <SignOutButton scope="local" />
          <Button
            isDisabled={
              !user ||
              updateMutation.isPending ||
              isDirty === false ||
              Object.keys(payloadToSave).length === 0
            }
            onClick={() => {
              updateMutation.mutate();
            }}
          >
            {updateMutation.isPending ? 'Сохранение…' : 'Сохранить'}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
