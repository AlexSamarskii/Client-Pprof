import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteMembership,
  inviteMembership,
  listOrgMemberships,
  updateMembershipRole,
} from '@/api/memberships';
import type {
  InviteMembershipRequest,
  MembershipResponse,
  MembershipRole,
} from '@/api/schemas/memberships';
import { useOrganization } from '@/hooks/useOrganization';
import { useUser } from '@/hooks/useUser';

export const MEMBERSHIPS_QUERY_KEY = 'memberships';

function canManageTarget(
  actorRole: MembershipRole | null,
  targetRole: MembershipRole,
) {
  if (actorRole === 'owner') return true;
  if (actorRole === 'admin') return targetRole === 'member';
  return false;
}

function canAssignRole(actorRole: MembershipRole | null, role: MembershipRole) {
  if (actorRole === 'owner') return true;
  if (actorRole === 'admin') return role === 'member';
  return false;
}

export function useMemberships() {
  const { organization } = useOrganization();
  const { role } = useUser();
  const queryClient = useQueryClient();

  const organizationId = organization?.id ?? null;

  const membershipsQuery = useQuery<MembershipResponse[]>({
    queryKey: [MEMBERSHIPS_QUERY_KEY, organizationId],
    queryFn: async () => {
      if (!organizationId) {
        throw new Error('Organization ID is required');
      }
      return listOrgMemberships(organizationId);
    },
    enabled: !!organizationId,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const invalidateMemberships = async () => {
    if (!organizationId) return;
    await queryClient.invalidateQueries({
      queryKey: [MEMBERSHIPS_QUERY_KEY, organizationId],
    });
  };

  const updateRoleMutation = useMutation({
    mutationFn: async ({
      membershipId,
      nextRole,
    }: {
      membershipId: string;
      nextRole: MembershipRole;
    }) => {
      if (!organizationId) throw new Error('Organization ID is required');
      return updateMembershipRole(organizationId, membershipId, {
        role: nextRole,
      });
    },
    onSuccess: invalidateMemberships,
  });

  const inviteMutation = useMutation({
    mutationFn: async (payload: InviteMembershipRequest) => {
      if (!organizationId) throw new Error('Organization ID is required');
      return inviteMembership(organizationId, payload);
    },
    onSuccess: invalidateMemberships,
  });

  const removeMutation = useMutation({
    mutationFn: async (membershipId: string) => {
      if (!organizationId) throw new Error('Organization ID is required');
      return deleteMembership(organizationId, membershipId);
    },
    onSuccess: invalidateMemberships,
  });

  return {
    role,
    memberships: membershipsQuery.data ?? [],
    membershipsQuery,
    canManageTarget,
    canAssignRole,
    updateRole: updateRoleMutation.mutateAsync,
    invite: inviteMutation.mutateAsync,
    removeMembership: removeMutation.mutateAsync,
    isUpdatingRole: updateRoleMutation.isPending,
    isInviting: inviteMutation.isPending,
    isRemoving: removeMutation.isPending,
  };
}
