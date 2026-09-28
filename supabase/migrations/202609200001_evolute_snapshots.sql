-- Uma única revisão do Evolução por usuário autenticado.
create table if not exists public.evolute_snapshots (
  user_id uuid primary key references auth.users(id) on delete cascade,
  data jsonb not null default '{}'::jsonb,
  revision bigint not null default 0 check (revision >= 0),
  updated_at timestamptz not null default now()
);

alter table public.evolute_snapshots enable row level security;
alter table public.evolute_snapshots force row level security;

revoke all on table public.evolute_snapshots from anon, authenticated;
grant select, insert, update on table public.evolute_snapshots to authenticated;

drop policy if exists "evolute owner reads own snapshot" on public.evolute_snapshots;
create policy "evolute owner reads own snapshot" on public.evolute_snapshots
  for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists "evolute owner inserts own snapshot" on public.evolute_snapshots;
create policy "evolute owner inserts own snapshot" on public.evolute_snapshots
  for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists "evolute owner updates own snapshot" on public.evolute_snapshots;
create policy "evolute owner updates own snapshot" on public.evolute_snapshots
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create or replace function public.sync_evolute_snapshot(p_data jsonb, p_base_revision bigint)
returns table(conflict boolean, revision bigint, data jsonb)
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_user_id uuid := (select auth.uid());
  v_row public.evolute_snapshots%rowtype;
begin
  if v_user_id is null then
    raise exception 'Autenticação obrigatória';
  end if;

  insert into public.evolute_snapshots as snapshot (user_id, data, revision, updated_at)
  values (v_user_id, p_data, 1, now())
  on conflict (user_id) do update
    set data = excluded.data,
        revision = snapshot.revision + 1,
        updated_at = now()
    where snapshot.revision <= coalesce(p_base_revision, 0)
  returning * into v_row;

  if found then
    return query select false, v_row.revision, v_row.data;
    return;
  end if;

  select * into v_row from public.evolute_snapshots where user_id = v_user_id;
  return query select true, v_row.revision, v_row.data;
end;
$$;

revoke all on function public.sync_evolute_snapshot(jsonb, bigint) from public, anon;
grant execute on function public.sync_evolute_snapshot(jsonb, bigint) to authenticated;
