import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';
import { ApiError } from '@/api/client';
import { updateUser } from '@/api/users';
import { USER_QUERY_KEY } from '@/hooks/useUser';
import { useAuth } from '@/components/auth/AuthProvider';
import { useOrganization } from '@/hooks/useOrganization';

const MIN_LENGTH = 4;

export function SetUsernameModal() {
  const { user: authUser } = useAuth();
  const { organization } = useOrganization();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState('');
  const [error, setError] = useState<string | null>(null);

  const userId = authUser?.id ?? null;
  const organizationId = organization?.id ?? null;

  const mutation = useMutation({
    mutationFn: async (value: string) => {
      if (!organizationId || !userId) {
        throw new Error('Organization and user are required');
      }
      return updateUser(organizationId, userId, { username: value.trim() });
    },
    onSuccess: () => {
      if (organizationId && userId) {
        void queryClient.invalidateQueries({
          queryKey: [USER_QUERY_KEY, organizationId, userId],
        });
      }
      setError(null);
      setUsername('');
    },
    onError: (err: unknown) => {
      const body = err instanceof ApiError ? err.body : null;
      const detail =
        body && typeof body === 'object' && 'detail' in body
          ? body.detail
          : null;
      const message =
        typeof detail === 'string'
          ? detail
          : 'Не удалось сохранить имя. Попробуйте ещё раз.';
      setError(message);
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmed = username.trim();
    if (trimmed.length < MIN_LENGTH) {
      setError(
        `Имя должно содержать не менее четырёх символов (${trimmed.length}/${MIN_LENGTH}).`,
      );
      return;
    }
    mutation.mutate(trimmed);
  };

  return (
    <Modal
      isOpen={true}
      onClose={() => {}}
      backdropDarkness="md"
      contentClassName="max-w-md"
      closeOnEsc={false}
      closeOnBackdrop={false}
    >
      <form onSubmit={handleSubmit} className="p-6 space-y-4">
        <h2 className="text-lg font-semibold text-foreground">
          Укажите имя пользователя
        </h2>
        <p className="text-sm text-muted-foreground">
          Укажите уникальное имя пользователя длиной не менее четырёх символов.
        </p>
        <div className="space-y-2">
          <Label htmlFor="set-username-input">Имя пользователя</Label>
          <input
            id="set-username-input"
            type="text"
            autoComplete="username"
            className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              setError(null);
            }}
            placeholder="например, ivan_ivanov"
            disabled={mutation.isPending}
            minLength={MIN_LENGTH}
          />
          {error ? <p className="text-xs text-danger">{error}</p> : null}
        </div>
        <div className="flex justify-end">
          <Button
            type="submit"
            isDisabled={
              mutation.isPending || username.trim().length < MIN_LENGTH
            }
          >
            {mutation.isPending ? 'Сохранение…' : 'Сохранить имя'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
