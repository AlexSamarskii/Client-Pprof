import { z } from 'zod';

import { apiGet, apiPatch } from './client';
import {
  OrganizationSchema,
  OrganizationUpdateRequestSchema,
} from './schemas/organizations';
import type { OrganizationUpdateRequest } from './schemas/organizations';

const uuidSchema = z.uuid();

const organizationsListSchema = z.array(OrganizationSchema);

export async function listOrganizations() {
  return apiGet('/api/v1/org', {}, organizationsListSchema);
}

export async function getOrganization(organizationId: string) {
  const parsedOrganizationId = uuidSchema.parse(organizationId);
  return apiGet(`/api/v1/org/${parsedOrganizationId}`, {}, OrganizationSchema);
}

export async function updateOrganization(
  organizationId: string,
  payload: OrganizationUpdateRequest,
) {
  const parsedOrganizationId = uuidSchema.parse(organizationId);
  const parsedPayload = OrganizationUpdateRequestSchema.parse(payload);
  return apiPatch(
    `/api/v1/org/${parsedOrganizationId}`,
    { body: parsedPayload },
    OrganizationSchema,
  );
}
