import { z } from 'zod';

const isoDateTime = z.iso.datetime({ offset: true });
const uuid = z.uuid();

export const ProjectStatusSchema = z.enum([
  'draft',
  'in_review',
  'approved',
  'changes_requested',
]);

export const DecisionKindSchema = z.enum(['approved', 'changes_requested']);

export const ProjectSchema = z.object({
  id: uuid,
  organization_id: uuid,
  client_id: uuid,
  name: z.string().min(1),
  description: z.string().nullable(),
  status: ProjectStatusSchema,
  response_deadline_at: isoDateTime.nullable(),
  archived_at: isoDateTime.nullable(),
  created_at: isoDateTime,
});

export const ClientSchema = z.object({
  id: uuid,
  organization_id: uuid,
  external_auth_user_id: uuid,
  display_name: z.string().nullable(),
  email: z.string().email().nullable(),
  created_at: isoDateTime,
});

export const DeliverableSchema = z.object({
  id: uuid,
  project_id: uuid,
  name: z.string().min(1),
  description: z.string().nullable(),
  position: z.number().int().min(1),
  archived_at: isoDateTime.nullable(),
  created_at: isoDateTime,
});

export const VersionSchema = z.object({
  id: uuid,
  deliverable_id: uuid,
  version_number: z.number().int().min(1),
  title: z.string().min(1),
  content: z.string().min(1),
  review_seq: z.number().int().min(1).nullable(),
  published_at: isoDateTime.nullable(),
  created_at: isoDateTime,
});

export const GrantSchema = z.object({
  id: uuid,
  project_id: uuid,
  client_id: uuid,
  status: z.enum(['active', 'revoked']),
  revoked_at: isoDateTime.nullable(),
  created_at: isoDateTime,
});

export const CommentSchema = z.object({
  id: uuid,
  version_id: uuid,
  author_user_id: uuid.nullable(),
  author_client_id: uuid.nullable(),
  body: z.string().min(1),
  created_at: isoDateTime,
});

export const DecisionSchema = z.object({
  id: uuid,
  version_id: uuid,
  client_id: uuid,
  decision: DecisionKindSchema,
  active: z.boolean(),
  created_at: isoDateTime,
});

export const FileSchema = z.object({
  id: uuid,
  version_id: uuid,
  filename: z.string().min(1),
  mime_type: z.string().min(3),
  size_bytes: z.number().int().min(0),
  position: z.number().int().min(1),
  created_at: isoDateTime,
});

export const FileLinkSchema = z.object({
  file_id: uuid,
  url: z.string().url(),
  expires_in_seconds: z.number().int().positive(),
});

export type Project = z.infer<typeof ProjectSchema>;
export type ProjectStatus = z.infer<typeof ProjectStatusSchema>;
export type Client = z.infer<typeof ClientSchema>;
export type Deliverable = z.infer<typeof DeliverableSchema>;
export type DeliverableVersion = z.infer<typeof VersionSchema>;
export type ProjectGrant = z.infer<typeof GrantSchema>;
export type Comment = z.infer<typeof CommentSchema>;
export type ApprovalDecision = z.infer<typeof DecisionSchema>;
export type VersionFile = z.infer<typeof FileSchema>;
export type FileLink = z.infer<typeof FileLinkSchema>;

export type DecisionKind = z.infer<typeof DecisionKindSchema>;

export type CreateProjectRequest = z.infer<typeof CreateProjectSchema>;
export type CreateCommentRequest = z.infer<typeof CreateCommentSchema>;
export type CreateDecisionRequest = z.infer<typeof CreateDecisionSchema>;

export const CreateProjectSchema = z.object({
  client_id: uuid,
  name: z.string().min(1).max(255),
  description: z.string().nullable().optional(),
  response_deadline_at: z
    .string()
    .refine((value) => !Number.isNaN(Date.parse(value)), 'invalid datetime')
    .nullable()
    .optional(),
});

export const CreateGrantSchema = z.object({
  client_id: uuid,
});

export const CreateCommentSchema = z.object({
  body: z.string().min(1),
});

export const CreateDecisionSchema = z.object({
  decision: DecisionKindSchema,
});

export const CreateClientSchema = z.object({
  external_auth_user_id: uuid,
  display_name: z.string().min(1).max(255),
  email: z.email(),
});
export const CreateDeliverableSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().nullable().optional(),
  position: z.number().int().positive().optional(),
});
export const DraftSchema = z.object({
  title: z.string().min(1).max(255),
  content: z.string().min(1),
});
export const UploadSchema = z.object({
  asset_id: uuid,
  storage_key: z.string(),
  upload_url: z.url(),
});
export type CreateClientRequest = z.infer<typeof CreateClientSchema>;
export type CreateDeliverableRequest = z.infer<typeof CreateDeliverableSchema>;
export type DraftRequest = z.infer<typeof DraftSchema>;
