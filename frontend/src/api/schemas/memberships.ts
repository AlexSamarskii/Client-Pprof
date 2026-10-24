import { z } from 'zod';

export const MembershipRoleSchema = z.enum(['owner', 'admin', 'member']);
export type MembershipRole = z.infer<typeof MembershipRoleSchema>;

export const MembershipSchema = z.object({
  id: z.uuid(),
  created_at: z.iso.datetime({ offset: true }),
  updated_at: z.iso.datetime({ offset: true }).nullable().optional(),
  deleted_at: z.iso.datetime({ offset: true }).nullable().optional(),

  organization_id: z.uuid(),
  user_id: z.uuid().nullable().optional(),
  role: MembershipRoleSchema,

  invited_by_id: z.uuid().nullable().optional(),
  invited_email: z.email().nullable().optional(),
  invitation_id: z.string().nullable().optional(),
  invitation_expires_at: z.iso.datetime({ offset: true }).nullable().optional(),

  additional_data: z.record(z.string(), z.unknown()),
});

export type MembershipResponse = z.infer<typeof MembershipSchema>;

export const MembershipRoleUpdateSchema = z.object({
  role: MembershipRoleSchema,
});

export type UpdateMembershipRoleRequest = z.infer<
  typeof MembershipRoleUpdateSchema
>;

export const InviteMembershipRequestSchema = z.object({
  email: z.email(),
  role: MembershipRoleSchema.default('member'),
});

export type InviteMembershipRequest = z.infer<
  typeof InviteMembershipRequestSchema
>;

export const AcceptMembershipInviteRequestSchema = z.object({
  invitation_id: z.string().min(1),
});

export type AcceptMembershipInviteRequest = z.infer<
  typeof AcceptMembershipInviteRequestSchema
>;
