import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import type { MembershipRole } from '@/api/schemas/memberships';
import { useMemberships } from '@/hooks/useMemberships';
import { useOrgMembers } from '@/hooks/useOrgMembers';
import { useOrganization } from '@/hooks/useOrganization';
import { supabase } from '@/supabase/client';
import { getAppOrigin } from '@/utils/app-url';

const ROLE_OPTIONS: MembershipRole[] = ['owner', 'admin', 'member'];

function roleLabel(role: MembershipRole) {
  return { owner: 'Владелец', admin: 'Администратор', member: 'Сотрудник' }[
    role
  ];
}

function createInviteRedirectUrl(
  organizationId: string,
  invitationId: string,
  organizationName: string | undefined,
) {
  const url = new URL('/auth/confirm', getAppOrigin());
  url.searchParams.set('type', 'email');
  url.searchParams.set('invite_org_id', organizationId);
  url.searchParams.set('invite_token', invitationId);
  url.searchParams.set('redirect', '/');
  if (organizationName) {
    url.searchParams.set('invite_org_name', organizationName);
  }
  return url.toString();
}

export function Members() {
  const { organization } = useOrganization();
  const {
    role: currentRole,
    memberships,
    canManageTarget,
    canAssignRole,
    updateRole,
    invite,
    removeMembership,
    isUpdatingRole,
    isInviting,
    isRemoving,
  } = useMemberships();
  const { usersById } = useOrgMembers();

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<MembershipRole>('member');
  const [feedback, setFeedback] = useState<string | null>(null);

  const allowedInviteRoles = useMemo(
    () => ROLE_OPTIONS.filter((role) => canAssignRole(currentRole, role)),
    [canAssignRole, currentRole],
  );

  const inviteRoleOptions = useMemo(
    () =>
      allowedInviteRoles.map((role) => ({
        value: role,
        label: roleLabel(role),
      })),
    [allowedInviteRoles],
  );

  const canInvite = currentRole === 'owner' || currentRole === 'admin';

  const activeMembers = memberships.filter(
    (m) => m.user_id !== null && m.user_id !== undefined,
  );
  const pendingInvites = memberships.filter(
    (m) => (m.user_id === null || m.user_id === undefined) && m.invitation_id,
  );

  const handleInvite = async () => {
    setFeedback(null);
    const normalizedEmail = inviteEmail.trim().toLowerCase();
    if (!normalizedEmail) {
      setFeedback('Укажите электронную почту для приглашения.');
      return;
    }
    if (!organization?.id) {
      setFeedback('Агентство не выбрано.');
      return;
    }
    try {
      const invitedMembership = await invite({
        email: normalizedEmail,
        role: inviteRole,
      });
      if (!invitedMembership.invitation_id) {
        throw new Error('Приглашение создано без идентификатора.');
      }
      const redirectUrl = createInviteRedirectUrl(
        organization.id,
        invitedMembership.invitation_id,
        organization.name,
      );
      const sendResult = await supabase.auth.signInWithOtp({
        email: normalizedEmail,
        options: {
          emailRedirectTo: redirectUrl,
          data: {
            invited: true,
            org_name: organization.name,
          },
        },
      });
      if (sendResult.error) {
        throw new Error('invitation delivery failed');
      }
      setInviteEmail('');
      setInviteRole(allowedInviteRoles[0] ?? 'member');
      setFeedback(`Приглашение отправлено на ${normalizedEmail}.`);
    } catch {
      setFeedback(
        'Не удалось отправить приглашение. Проверьте адрес и права доступа, затем повторите попытку.',
      );
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto flex flex-col gap-6">
      {canInvite && (
        <Card>
          <CardHeader>
            <CardTitle>Пригласить участника</CardTitle>
            <CardDescription>
              Пригласите сотрудника: ссылка из письма добавит его в агентство{' '}
              {organization?.name ?? 'агентство'}.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label htmlFor="invite-email">Электронная почта</Label>
              <Input
                id="invite-email"
                type="email"
                value={inviteEmail}
                placeholder="teammate@example.com"
                onChange={setInviteEmail}
              />
            </div>
            <Select
              id="invite-role"
              label="Роль"
              value={inviteRole}
              onChange={(value) => setInviteRole(value as MembershipRole)}
              options={inviteRoleOptions}
            />
            {feedback && (
              <p className="text-sm text-muted-foreground">{feedback}</p>
            )}
            <div>
              <Button
                isDisabled={isInviting || !inviteEmail.trim()}
                onClick={() => {
                  void handleInvite();
                }}
              >
                {isInviting ? 'Отправка…' : 'Отправить приглашение'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Участники</CardTitle>
          <CardDescription>Сотрудники с доступом к агентству.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {activeMembers.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Участников пока нет.
            </p>
          )}
          {activeMembers.map((m) => {
            const canManage = canManageTarget(currentRole, m.role);
            const memberLabel =
              (m.user_id && usersById.get(m.user_id)) ?? m.user_id;
            const roleSelectOptions = ROLE_OPTIONS.filter((role) =>
              canAssignRole(currentRole, role),
            ).map((role) => ({ value: role, label: roleLabel(role) }));
            // Always include the current role so the select has a stable value
            // even when the actor cannot reassign it.
            if (!roleSelectOptions.some((opt) => opt.value === m.role)) {
              roleSelectOptions.unshift({
                value: m.role,
                label: roleLabel(m.role),
              });
            }
            return (
              <div
                key={m.id}
                className="flex items-center justify-between gap-3 border border-border rounded-md p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{memberLabel}</p>
                  <p className="text-xs text-muted-foreground">
                    Роль: {roleLabel(m.role)}
                  </p>
                </div>
                <div className="flex items-end gap-2">
                  <Select
                    id={`member-role-${m.id}`}
                    label=""
                    value={m.role}
                    onChange={(value) => {
                      void updateRole({
                        membershipId: m.id,
                        nextRole: value as MembershipRole,
                      });
                    }}
                    options={roleSelectOptions}
                    isDisabled={!canManage || isUpdatingRole}
                    className="w-32"
                  />
                  <Button
                    variant="destructive"
                    size="sm"
                    isDisabled={!canManage || isRemoving}
                    onClick={() => {
                      void removeMembership(m.id);
                    }}
                  >
                    Удалить
                  </Button>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {pendingInvites.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Ожидающие приглашения</CardTitle>
            <CardDescription>
              Приглашённые сотрудники, которые ещё не приняли приглашение.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {pendingInvites.map((m) => {
              const canManage = canManageTarget(currentRole, m.role);
              return (
                <div
                  key={m.id}
                  className="flex items-center justify-between gap-3 border border-border rounded-md p-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">
                      {m.invited_email}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Роль: {roleLabel(m.role)}
                      {m.invitation_expires_at &&
                        ` · действительно до ${new Date(m.invitation_expires_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    isDisabled={!canManage || isRemoving}
                    onClick={() => {
                      void removeMembership(m.id);
                    }}
                  >
                    Отозвать
                  </Button>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
