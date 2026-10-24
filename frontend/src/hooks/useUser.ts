import { ApiError } from '../api/client';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../components/auth/AuthProvider';
import { useOrganization } from './useOrganization';
import { getUser } from '../api/users';
import { getMyMembership } from '../api/memberships';
import type { UserResponse } from '../api/schemas/users';
import type {
  MembershipResponse,
  MembershipRole,
} from '../api/schemas/memberships';

export const USER_QUERY_KEY = 'users';
export const MY_MEMBERSHIP_QUERY_KEY = 'my-membership';

export function useUser(organizationOverride?: string | null) {
  const auth = useAuth();
  const { organization } = useOrganization();

  const userId = auth.user?.id ?? null;
  const organizationId =
    organizationOverride === undefined
      ? (organization?.id ?? null)
      : organizationOverride;

  const userQuery = useQuery<UserResponse>({
    queryKey: [USER_QUERY_KEY, organizationId, userId],
    queryFn: async () => {
      if (!organizationId || !userId) {
        throw new Error('Organization and user are required');
      }
      return getUser(organizationId, userId);
    },
    enabled:
      auth.isLoading === false &&
      auth.user !== null &&
      !!organizationId &&
      !!userId,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const myMembershipQuery = useQuery<MembershipResponse>({
    queryKey: [MY_MEMBERSHIP_QUERY_KEY, organizationId, userId],
    queryFn: async () => {
      if (!organizationId) {
        throw new Error('Organization is required');
      }
      return getMyMembership(organizationId);
    },
    enabled:
      auth.isLoading === false &&
      auth.user !== null &&
      !!organizationId &&
      !!userId,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const user = userQuery.data ?? null;
  const myMembership =
    myMembershipQuery.isSuccess && !myMembershipQuery.isFetching
      ? myMembershipQuery.data
      : null;
  const role: MembershipRole | null = myMembership?.role ?? null;

  return {
    user,
    userQuery,
    myMembership,
    myMembershipQuery,
    role,
    roleReady:
      !myMembershipQuery.isFetching &&
      (myMembershipQuery.isSuccess ||
        (myMembershipQuery.error instanceof ApiError &&
          [403, 404].includes(myMembershipQuery.error.status))),
    roleLoading: myMembershipQuery.isFetching,
    roleError:
      myMembershipQuery.isError &&
      !(
        myMembershipQuery.error instanceof ApiError &&
        [403, 404].includes(myMembershipQuery.error.status)
      ),
  };
}
