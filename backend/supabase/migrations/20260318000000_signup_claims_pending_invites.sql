-- Replace handle_new_user() so that signup also claims any pending invites
-- (memberships rows with user_id = null and invited_email matching new.email).
-- If at least one pending invite is claimed, skip personal-org creation —
-- the user joins via the invitation instead.

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  new_org_id uuid;
  display_name text;
  accepted_invites_count integer;
begin
  insert into public.users (
    id,
    email,
    full_name,
    avatar_url,
    created_at,
    additional_data
  )
  values (
    new.id,
    new.email,
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url',
    now(),
    '{}'::jsonb
  )
  on conflict (id) do update set
    full_name = excluded.full_name,
    avatar_url = excluded.avatar_url,
    updated_at = now();

  update public.memberships
     set user_id = new.id,
         invited_email = null,
         invitation_id = null,
         invitation_expires_at = null,
         updated_at = now()
   where user_id is null
     and deleted_at is null
     and lower(invited_email) = lower(new.email)
     and (invitation_expires_at is null or invitation_expires_at >= now());

  get diagnostics accepted_invites_count = row_count;

  if accepted_invites_count > 0 then
    return new;
  end if;

  display_name := coalesce(
    nullif(new.raw_user_meta_data->>'full_name', ''),
    nullif(split_part(new.email, '@', 1), ''),
    'Personal'
  );

  insert into public.organizations (name)
  values (display_name || '''s Organization')
  returning id into new_org_id;

  insert into public.memberships (
    organization_id,
    user_id,
    role
  )
  values (
    new_org_id,
    new.id,
    'owner'
  );

  return new;
end;
$$;
