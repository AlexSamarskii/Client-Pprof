-- ClientProof domain tables. Authorization is enforced by backend handlers and
-- never by trusting ownership fields from request payloads. The REST surface is
-- deny-by-default: direct anon/authenticated access is revoked, RLS has no
-- client-facing policies, and service role retains transactional RPC access.

create table public.plan_entitlements (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone,
  plan_key text not null unique,
  active boolean not null default true,
  active_project_limit integer not null check (active_project_limit > 0)
);

insert into public.plan_entitlements (plan_key, active_project_limit)
values
  ('studio', 5),
  ('team', 25),
  ('agency', 100)
on conflict (plan_key) do update
set
  active = true,
  active_project_limit = excluded.active_project_limit,
  updated_at = now();

create table public.clients (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone,
  deleted_at timestamp with time zone default null,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  external_auth_user_id uuid not null references auth.users(id) on delete cascade,
  display_name text,
  email text,
  constraint clients_email_or_display_name_not_empty
    check ((email is null or email <> '') and (display_name is null or display_name <> '')),
  constraint clients_identity_unique
    unique (organization_id, external_auth_user_id)
);

create unique index clients_unique_id_tenant on public.clients (id, organization_id);

create unique index clients_unique_active_auth_user_per_org
  on public.clients (organization_id, external_auth_user_id)
  where deleted_at is null;
create index clients_organization_id_idx on public.clients (organization_id);
create index clients_external_auth_user_id_idx on public.clients (external_auth_user_id);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  client_id uuid not null,
  name text not null check (char_length(btrim(name)) > 0),
  description text,
  status text not null default 'draft'
    check (status in ('draft', 'in_review', 'approved', 'changes_requested')),
  response_deadline_at timestamp with time zone default null,
  archived_at timestamp with time zone default null,
  archived_by_user_id uuid,
  constraint projects_unique_tenant_id unique (organization_id, id),
  constraint projects_unique_id_tenant unique (id, organization_id),
  constraint projects_client_tenant
    foreign key (client_id, organization_id)
    references public.clients(id, organization_id)
    on delete cascade
);

create index projects_organization_id_idx on public.projects (organization_id);
create index projects_organization_client_id_idx on public.projects (organization_id, client_id);
create index projects_organization_status_idx on public.projects (organization_id, status);
create index projects_organization_active_idx on public.projects (organization_id)
  where archived_at is null;

create table public.deliverables (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone,
  organization_id uuid not null,
  project_id uuid not null,
  name text not null check (char_length(btrim(name)) > 0),
  description text,
  position integer not null default 1 check (position > 0),
  archived_at timestamp with time zone default null,
  constraint deliverables_unique_id_scope unique (id, project_id, organization_id),
  constraint deliverables_project_tenant
    foreign key (project_id, organization_id)
    references public.projects(id, organization_id)
    on delete cascade
);

create index deliverables_organization_project_idx on public.deliverables (organization_id, project_id);
create index deliverables_organization_active_idx on public.deliverables (organization_id, project_id)
  where archived_at is null;

create table public.deliverable_versions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone,
  organization_id uuid not null,
  project_id uuid not null,
  deliverable_id uuid not null,
  version_number integer not null check (version_number > 0),
  title text not null check (char_length(btrim(title)) > 0),
  content text not null,
  review_seq integer,
  published_at timestamp with time zone default null,
  published_by_user_id uuid,
  constraint deliverable_versions_unique_id_scope
    unique (id, project_id, organization_id),
  constraint deliverable_versions_deliverable_tenant
    foreign key (deliverable_id, project_id, organization_id)
    references public.deliverables(id, project_id, organization_id)
    on delete cascade,
  constraint deliverable_versions_draft_or_published
    check ((published_at is null) = (review_seq is null))
);

create unique index deliverable_versions_project_review_seq_idx
  on public.deliverable_versions (project_id, review_seq);
create unique index deliverable_versions_project_version_number_idx
  on public.deliverable_versions (project_id, version_number);
create index deliverable_versions_organization_project_idx
  on public.deliverable_versions (organization_id, project_id);
create index deliverable_versions_reviewable_idx
  on public.deliverable_versions (project_id, review_seq desc)
  where review_seq is not null;

create function public.reject_row_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'this record is immutable'
    using errcode = '23514';
end;
$$;

create function public.prevent_mutable_published_version()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.published_at is not null then
    raise exception 'published deliverable versions are immutable'
      using errcode = '23514';
  end if;
  return coalesce(new, old);
end;
$$;

create trigger deliverable_versions_prevent_published_update
before update on public.deliverable_versions
for each row execute function public.prevent_mutable_published_version();

create trigger deliverable_versions_prevent_published_delete
before delete on public.deliverable_versions
for each row execute function public.prevent_mutable_published_version();

create trigger deliverable_versions_prevent_direct_publication
before insert on public.deliverable_versions
for each row
when (new.published_at is not null or new.review_seq is not null)
execute function public.reject_row_mutation();

create table public.project_grants (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone,
  organization_id uuid not null,
  project_id uuid not null,
  client_id uuid not null,
  status text not null default 'active'
    check (status in ('active', 'revoked')),
  revoked_at timestamp with time zone default null,
  revoked_by_user_id uuid,
  constraint project_grants_id_scope unique (id, project_id, organization_id),
  constraint project_grants_project_tenant
    foreign key (project_id, organization_id)
    references public.projects(id, organization_id)
    on delete cascade,
  constraint project_grants_client_tenant
    foreign key (client_id, organization_id)
    references public.clients(id, organization_id)
    on delete cascade,
  constraint project_grants_revocation_consistency
    check ((status = 'active') = (revoked_at is null))
);

create unique index project_grants_unique_active_per_project_client
  on public.project_grants (project_id, client_id)
  where status = 'active';
create index project_grants_organization_project_idx on public.project_grants (organization_id, project_id);
create index project_grants_client_idx on public.project_grants (client_id);

create table public.comments (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  organization_id uuid not null,
  project_id uuid not null,
  version_id uuid not null,
  author_user_id uuid,
  author_client_id uuid,
  body text not null check (char_length(btrim(body)) > 0),
  constraint comments_unique_id_scope unique (id, project_id, organization_id),
  constraint comments_version_tenant
    foreign key (version_id, project_id, organization_id)
    references public.deliverable_versions(id, project_id, organization_id)
    on delete cascade,
  constraint comments_author_exactly_one
    check ((author_user_id is null) <> (author_client_id is null)),
  constraint comments_staff_author
    foreign key (author_user_id) references auth.users(id) on delete set null,
  constraint comments_client_author_tenant
    foreign key (author_client_id, organization_id)
    references public.clients(id, organization_id) on delete cascade
);

create trigger comments_append_only_update
before update on public.comments
for each row execute function public.reject_row_mutation();

create trigger comments_append_only_delete
before delete on public.comments
for each row execute function public.reject_row_mutation();

create function public.prevent_draft_target_record()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not exists (
    select 1
    from public.deliverable_versions
    where id = new.version_id
      and published_at is not null
  ) then
    raise exception 'target record must reference a published version'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger comments_require_published_version
before insert on public.comments
for each row execute function public.prevent_draft_target_record();

create index comments_organization_project_idx on public.comments (organization_id, project_id);
create index comments_version_idx on public.comments (version_id, created_at);

create table public.approval_decisions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  organization_id uuid not null,
  project_id uuid not null,
  version_id uuid not null,
  client_id uuid not null,
  decision text not null
    check (decision in ('approved', 'changes_requested')),
  active boolean not null default true,
  constraint approval_decisions_unique_id_scope
    unique (id, project_id, organization_id),
  constraint approval_decisions_version_tenant
    foreign key (version_id, project_id, organization_id)
    references public.deliverable_versions(id, project_id, organization_id)
    on delete cascade,
  constraint approval_decisions_client_tenant
    foreign key (client_id, organization_id)
    references public.clients(id, organization_id) on delete cascade
);

create unique index approval_decisions_one_active_per_version
  on public.approval_decisions (version_id)
  where active;
create index approval_decisions_organization_project_idx
  on public.approval_decisions (organization_id, project_id);
create index approval_decisions_version_history_idx
  on public.approval_decisions (version_id, created_at);

create trigger approval_decisions_append_only_update
before update on public.approval_decisions
for each row execute function public.reject_row_mutation();

create trigger approval_decisions_append_only_delete
before delete on public.approval_decisions
for each row execute function public.reject_row_mutation();

create trigger approval_decisions_require_published_version
before insert on public.approval_decisions
for each row execute function public.prevent_draft_target_record();

create unique index assets_unique_id_tenant on public.assets (id, organization_id);

create table public.deliverable_version_files (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone,
  organization_id uuid not null,
  project_id uuid not null,
  version_id uuid not null,
  asset_id uuid not null,
  filename text not null check (char_length(btrim(filename)) > 0),
  storage_key text not null unique,
  mime_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  position integer not null check (position > 0),
  is_public boolean not null default false,
  constraint deliverable_version_files_private_by_default
    check (is_public = false),
  constraint deliverable_version_files_size_limit
    check (size_bytes <= 2147483648),
  constraint deliverable_version_files_mime_type_not_empty
    check (char_length(btrim(mime_type)) > 0),
  constraint deliverable_version_files_private_storage_key
    check (
      storage_key like (
        organization_id::text || '/projects/' || project_id::text || '/%'
      )
    ),
  constraint deliverable_version_files_unique_id_scope
    unique (id, project_id, organization_id),
  constraint deliverable_version_files_asset_tenant
    foreign key (asset_id, organization_id)
    references public.assets(id, organization_id)
    on delete restrict,
  constraint deliverable_version_files_version_tenant
    foreign key (version_id, project_id, organization_id)
    references public.deliverable_versions(id, project_id, organization_id)
    on delete cascade
);

create function public.prevent_mutable_published_file()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if exists (
    select 1
    from public.deliverable_versions
    where id = old.version_id
      and published_at is not null
  ) then
    raise exception 'published file references are immutable'
      using errcode = '23514';
  end if;
  return coalesce(new, old);
end;
$$;

create trigger deliverable_version_files_prevent_published_update
before update on public.deliverable_version_files
for each row execute function public.prevent_mutable_published_file();

create trigger deliverable_version_files_prevent_published_delete
before delete on public.deliverable_version_files
for each row execute function public.prevent_mutable_published_file();

create index deliverable_version_files_organization_project_idx
  on public.deliverable_version_files (organization_id, project_id);
create index deliverable_version_files_version_position_idx
  on public.deliverable_version_files (version_id, position);
create index deliverable_version_files_asset_idx on public.deliverable_version_files (asset_id);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  occurred_at timestamp with time zone not null default now(),
  organization_id uuid not null,
  project_id uuid not null,
  deliverable_id uuid,
  version_id uuid,
  actor_kind text not null
    check (actor_kind in ('staff', 'client', 'system')),
  actor_user_id uuid,
  actor_client_id uuid,
  event_type text not null check (char_length(btrim(event_type)) > 0),
  data jsonb not null default '{}'::jsonb,
  constraint audit_events_actor_exactly_one
    check (
      (actor_kind = 'system' and actor_user_id is null and actor_client_id is null)
      or (actor_kind = 'staff' and actor_user_id is not null and actor_client_id is null)
      or (actor_kind = 'client' and actor_user_id is null and actor_client_id is not null)
    ),
  constraint audit_events_tenant_context
    foreign key (organization_id, project_id)
    references public.projects(organization_id, id)
    on delete cascade,
  constraint audit_events_version_context
    foreign key (version_id, project_id, organization_id)
    references public.deliverable_versions(id, project_id, organization_id)
    on delete cascade
);

create trigger audit_events_append_only_update
before update on public.audit_events
for each row execute function public.reject_row_mutation();

create trigger audit_events_append_only_delete
before delete on public.audit_events
for each row execute function public.reject_row_mutation();

create index audit_events_organization_project_occurred_idx
  on public.audit_events (organization_id, project_id, occurred_at desc);
create index audit_events_version_idx on public.audit_events (version_id);

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'approval_decisions',
    'audit_events',
    'clients',
    'comments',
    'deliverable_version_files',
    'deliverable_versions',
    'deliverables',
    'plan_entitlements',
    'project_grants',
    'projects'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('alter table public.%I force row level security', table_name);
    execute format('revoke all privileges on public.%I from anon, authenticated', table_name);
    execute format(
      'create policy clientproof_service_role_only_%I on public.%I for all to service_role using (true) with check (true)',
      table_name,
      table_name
    );
    execute format(
      'grant select, insert, update, delete on public.%I to service_role',
      table_name
    );
  end loop;
end
$$;

create function public.create_project_atomic(
  p_organization_id uuid,
  p_client_id uuid,
  p_project_name text,
  p_project_description text,
  p_response_deadline timestamptz
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  effective_limit integer;
  active_project_count integer;
  new_project_id uuid;
begin
  if btrim(coalesce(p_project_name, '')) = '' then
    return jsonb_build_object('kind', 'validation_error', 'field', 'name');
  end if;
  if p_response_deadline <= now() then
    return jsonb_build_object('kind', 'validation_error', 'field', 'response_deadline_at');
  end if;

  perform pg_advisory_xact_lock(hashtextextended('clientproof:org:' || p_organization_id::text, 0));

  select coalesce(p.active_project_limit, 0)
  into effective_limit
  from public.organizations o
  left join public.plan_entitlements p
    on p.active and p.plan_key = o.billing_plan_key
  where o.id = p_organization_id
    and o.billing_is_paid;

  if effective_limit is null then
    return jsonb_build_object('kind', 'quota_conflict', 'limit', 0);
  end if;

  select count(*)
  into active_project_count
  from public.projects
  where organization_id = p_organization_id
    and archived_at is null;

  if active_project_count >= effective_limit then
    return jsonb_build_object(
      'kind', 'quota_conflict',
      'limit', effective_limit,
      'active_count', active_project_count
    );
  end if;

  insert into public.projects (
    organization_id, client_id, name, description, response_deadline_at
  )
  values (
    p_organization_id,
    p_client_id,
    btrim(p_project_name),
    p_project_description,
    p_response_deadline
  )
  returning id into new_project_id;

  insert into public.audit_events (
    organization_id, project_id, actor_kind, actor_user_id, actor_client_id, event_type, data
  )
  values (
    p_organization_id,
    new_project_id,
    'system',
    null,
    null,
    'project.created',
    jsonb_build_object('project_id', new_project_id)
  );

  return jsonb_build_object('kind', 'created', 'project_id', new_project_id);
end;
$$;

create function public.publish_version_atomic(
  p_project_id uuid,
  p_version_id uuid,
  p_actor_user_id uuid
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  locked_project public.projects;
  locked_version public.deliverable_versions;
begin
  select *
  into locked_project
  from public.projects
  where id = p_project_id
  for update;

  if locked_project.id is null then
    return jsonb_build_object('kind', 'not_found');
  end if;
  if locked_project.archived_at is not null then
    return jsonb_build_object('kind', 'archived_project');
  end if;

  select *
  into locked_version
  from public.deliverable_versions as version
  where version.id = p_version_id
    and version.project_id = p_project_id
  for update;

  if locked_version.id is null then
    return jsonb_build_object('kind', 'not_found');
  end if;
  if locked_version.published_at is not null then
    return jsonb_build_object('kind', 'already_published', 'version_id', locked_version.id);
  end if;

  update public.deliverable_versions
  set
    review_seq = coalesce(
      (select max(review_seq) from public.deliverable_versions where project_id = p_project_id),
      0
    ) + 1,
    published_at = now(),
    published_by_user_id = p_actor_user_id
  where id = locked_version.id;

  update public.projects
  set status = 'in_review', updated_at = now()
  where id = locked_project.id;
  if p_actor_user_id is null then
    insert into public.audit_events (
      organization_id, project_id, deliverable_id, version_id,
      actor_kind, actor_user_id, actor_client_id, event_type, data
    )
    values (
      locked_version.organization_id,
      locked_version.project_id,
      locked_version.deliverable_id,
      locked_version.id,
      'system',
      null,
      null,
      'version.published',
      jsonb_build_object('version_id', locked_version.id)
    );
  else
    insert into public.audit_events (
      organization_id, project_id, deliverable_id, version_id,
      actor_kind, actor_user_id, actor_client_id, event_type, data
    )
    values (
      locked_version.organization_id,
      locked_version.project_id,
      locked_version.deliverable_id,
      locked_version.id,
      'staff',
      p_actor_user_id,
      null,
      'version.published',
      jsonb_build_object('version_id', locked_version.id)
    );
  end if;

  return jsonb_build_object('kind', 'published', 'version_id', locked_version.id);
end;
$$;

create function public.submit_decision_atomic(
  p_project_id uuid,
  p_version_id uuid,
  p_deciding_client_id uuid,
  p_decision_kind text
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  locked_version public.deliverable_versions;
  locked_project public.projects;
  locked_grant public.project_grants;
  existing_decision public.approval_decisions;
  new_decision_id uuid;
  resulting_status text;
begin
  if p_decision_kind not in ('approved', 'changes_requested') then
    return jsonb_build_object('kind', 'validation_error', 'field', 'decision');
  end if;

  select *
  into locked_project
  from public.projects
  where id = p_project_id
  for update;

  select *
  into locked_version
  from public.deliverable_versions
  where id = p_version_id
    and project_id = p_project_id
  for update;

  if locked_version.id is null or locked_project.id is null then
    return jsonb_build_object('kind', 'not_found');
  end if;

  select *
  into locked_grant
  from public.project_grants
  where project_id = p_project_id
    and client_id = p_deciding_client_id
    and status = 'active'
  for update;

  if locked_grant.id is null then
    return jsonb_build_object('kind', 'access_denied');
  end if;

  select *
  into existing_decision
  from public.approval_decisions
  where version_id = p_version_id
    and active
  for update;

  if existing_decision.id is not null then
    if existing_decision.client_id = p_deciding_client_id
      and existing_decision.decision = p_decision_kind then
      return jsonb_build_object(
        'kind', 'idempotent',
        'decision_id', existing_decision.id,
        'decision', existing_decision.decision
      );
    end if;
    return jsonb_build_object(
      'kind', 'decision_conflict',
      'decision_id', existing_decision.id,
      'decision', existing_decision.decision
    );
  end if;

  if locked_project.status <> 'in_review' or locked_version.review_seq is null then
    return jsonb_build_object('kind', 'invalid_review_state', 'project_status', locked_project.status);
  end if;

  insert into public.approval_decisions (
    organization_id, project_id, version_id, client_id, decision
  )
  values (
    locked_version.organization_id,
    locked_version.project_id,
    locked_version.id,
    p_deciding_client_id,
    p_decision_kind
  )
  returning id into new_decision_id;

  resulting_status := p_decision_kind;
  update public.projects
  set status = resulting_status, updated_at = now()
  where id = locked_project.id;

  insert into public.audit_events (
    organization_id, project_id, deliverable_id, version_id,
    actor_kind, actor_user_id, actor_client_id, event_type, data
  )
  values (
    locked_version.organization_id,
    locked_version.project_id,
    locked_version.deliverable_id,
    locked_version.id,
    'client',
    null,
    p_deciding_client_id,
    'decision.' || p_decision_kind,
    jsonb_build_object('decision_id', new_decision_id)
  );

  return jsonb_build_object('kind', 'created', 'decision_id', new_decision_id);
end;
$$;

revoke execute on function public.create_project_atomic(uuid, uuid, text, text, timestamptz) from public, anon, authenticated;
revoke execute on function public.publish_version_atomic(uuid, uuid, uuid) from public, anon, authenticated;
revoke execute on function public.submit_decision_atomic(uuid, uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.create_project_atomic(uuid, uuid, text, text, timestamptz) to service_role;
grant execute on function public.publish_version_atomic(uuid, uuid, uuid) to service_role;
grant execute on function public.submit_decision_atomic(uuid, uuid, uuid, text) to service_role;
