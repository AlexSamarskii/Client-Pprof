import { useEffect, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { supabase } from '@/supabase/client';
import { acceptMembershipInvite } from '@/api/memberships';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export function safeRedirect(value: string | null, origin: string): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return '/';
  try {
    return new URL(value, origin).origin === origin ? value : '/';
  } catch {
    return '/';
  }
}

function getSearchParam(param: string) {
  return new URLSearchParams(window.location.search).get(param);
}

export function AuthConfirm() {
  const navigate = useNavigate();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isAlive = true;

    const handleConfirm = async () => {
      let publicFailure =
        'Не удалось подтвердить вход. Запросите новое письмо и повторите попытку.';
      try {
        const tokenHash = getSearchParam('token_hash');
        const type = getSearchParam('type');

        if (!tokenHash) {
          setErrorMessage(
            'В ссылке отсутствует код подтверждения. Запросите новое письмо для входа.',
          );
          return;
        }
        if (type !== 'email') {
          setErrorMessage(
            'Некорректный тип подтверждения. Запросите новое письмо для входа.',
          );
          return;
        }

        const result = await supabase.auth.verifyOtp({
          token_hash: tokenHash,
          type: 'email',
        });
        if (result.error) {
          throw new Error('confirmation failed');
        }

        const inviteOrganizationId = getSearchParam('invite_org_id');
        const inviteToken = getSearchParam('invite_token');
        if (inviteOrganizationId && inviteToken) {
          publicFailure =
            'Не удалось принять приглашение. Обратитесь к администратору агентства за новым приглашением.';
          await acceptMembershipInvite(inviteOrganizationId, {
            invitation_id: inviteToken,
          });
        }

        const redirectTo = safeRedirect(
          getSearchParam('redirect'),
          window.location.origin,
        );
        if (redirectTo !== '/') {
          window.location.assign(redirectTo);
          return;
        }

        await navigate({ to: '/' });
      } catch {
        if (!isAlive) {
          return;
        }
        setErrorMessage(publicFailure);
      }
    };

    void handleConfirm();

    return () => {
      isAlive = false;
    };
  }, [navigate]);

  return (
    <div className="p-6 max-w-lg mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Выполняется вход…</CardTitle>
          <CardDescription>
            {errorMessage
              ? 'Не удалось войти.'
              : 'Подождите, пока мы завершим вход.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {errorMessage ? (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Если вход не завершился, запросите новое письмо.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
