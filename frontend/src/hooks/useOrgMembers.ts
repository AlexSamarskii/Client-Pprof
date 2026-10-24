import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { getUser } from '@/api/users';
import { useMemberships } from '@/hooks/useMemberships';
import { useOrganization } from '@/hooks/useOrganization';

export interface OrgMemberOption {
  id: string;
  label: string;
}

function memberLabelFromUser(user: {
  full_name?: string | null;
  username?: string | null;
  email: string;
}): string {
  const username = user.username?.trim();
  if (username) {
    return `${username} (${user.email})`;
  }
  const fullName = user.full_name?.trim();
  if (fullName) return fullName;
  return user.email;
}

export function useOrgMembers() {
  const { organization } = useOrganization();
  const { memberships, membershipsQuery } = useMemberships();

  const userIds = useMemo(() => {
    const ids = memberships
      .map((membership) => membership.user_id)
      .filter((userId): userId is string => Boolean(userId));
    return [...new Set(ids)];
  }, [memberships]);

  const userQueries = useQueries({
    queries: userIds.map((userId) => ({
      queryKey: ['users', organization?.id, userId],
      queryFn: async () => {
        if (!organization?.id) {
          throw new Error('Organization ID is required');
        }
        return getUser(organization.id, userId);
      },
      enabled: Boolean(organization?.id),
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    })),
  });

  const usersById = useMemo(() => {
    const map = new Map<string, string>();
    userQueries.forEach((query, index) => {
      if (query.data) {
        const user = query.data;
        map.set(userIds[index], memberLabelFromUser(user));
      }
    });
    return map;
  }, [userIds, userQueries]);

  const memberOptions = useMemo<OrgMemberOption[]>(() => {
    return userIds
      .map((userId) => ({
        id: userId,
        label: usersById.get(userId) ?? `User ${userId.slice(0, 8)}`,
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [userIds, usersById]);

  const isLoadingMembers =
    membershipsQuery.isLoading || userQueries.some((q) => q.isLoading);

  return { memberOptions, usersById, isLoadingMembers };
}
