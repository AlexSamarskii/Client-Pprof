create or replace function public.set_project_archived_atomic(
  p_project_id uuid,
  p_organization_id uuid,
  p_archived boolean,
  p_actor_user_id uuid
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  locked_project public.projects;
  effective_limit integer;
  active_project_count integer;
  new_archived_at timestamptz;
begin
  perform pg_advisory_xact_lock(
    hashtextextended('clientproof:org:' || p_organization_id::text, 0)
  );

  select *
  into locked_project
  from public.projects
  where id = p_project_id
    and organization_id = p_organization_id;

  if not found then
    return jsonb_build_object('kind', 'not_found');
  end if;

  if p_archived then
    if locked_project.archived_at is not null then
      return jsonb_build_object('kind', 'unchanged');
    end if;

    new_archived_at := now();
    update public.projects
    set archived_at = new_archived_at,
        archived_by_user_id = p_actor_user_id,
        updated_at = new_archived_at
    where id = locked_project.id
      and organization_id = locked_project.organization_id;

    insert into public.audit_events (
      organization_id, project_id, actor_kind, actor_user_id, actor_client_id,
      event_type, data
    )
    values (
      locked_project.organization_id,
      locked_project.id,
      'staff',
      p_actor_user_id,
      null,
      'project.archived',
      jsonb_build_object('project_id', locked_project.id)
    );

    return jsonb_build_object('kind', 'archived', 'archived_at', new_archived_at);
  end if;

  if locked_project.archived_at is null then
    return jsonb_build_object('kind', 'unchanged');
  end if;

  select coalesce(p.active_project_limit, 0)
  into effective_limit
  from public.organizations o
  left join public.plan_entitlements p
    on p.active and p.plan_key = o.billing_plan_key
  where o.id = locked_project.organization_id
    and o.billing_is_paid;

  if effective_limit is null then
    return jsonb_build_object('kind', 'quota_conflict', 'limit', 0);
  end if;

  select count(*)
  into active_project_count
  from public.projects
  where organization_id = locked_project.organization_id
    and archived_at is null
    and id <> locked_project.id;

  if active_project_count >= effective_limit then
    return jsonb_build_object(
      'kind', 'quota_conflict',
      'limit', effective_limit,
      'active_count', active_project_count
    );
  end if;

  update public.projects
  set archived_at = null,
      archived_by_user_id = null,
      updated_at = now()
  where id = locked_project.id
    and organization_id = locked_project.organization_id;

  insert into public.audit_events (
    organization_id, project_id, actor_kind, actor_user_id, actor_client_id,
    event_type, data
  )
  values (
    locked_project.organization_id,
    locked_project.id,
    'staff',
    p_actor_user_id,
    null,
    'project.unarchived',
    jsonb_build_object('project_id', locked_project.id)
  );

  return jsonb_build_object('kind', 'unarchived');
end;
$$;

revoke execute on function public.set_project_archived_atomic(
  uuid, uuid, boolean, uuid
) from public, anon, authenticated;
grant execute on function public.set_project_archived_atomic(
  uuid, uuid, boolean, uuid
) to service_role;
