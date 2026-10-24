-- Run only against the empty database owned by run_local_acceptance.py.
-- Auth tables are installed by genuine GoTrue migrations, never a test adapter.
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema if not exists auth;
create schema if not exists storage;
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid
$$;
-- Unused upstream avatar schema prerequisites; these do not emulate R2.
create table storage.buckets (id text primary key, name text not null);
create table storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets(id), name text, owner uuid
);
alter table storage.objects enable row level security;
grant usage on schema public, auth to anon, authenticated, service_role;
