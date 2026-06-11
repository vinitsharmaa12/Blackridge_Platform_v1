-- PRD 004: insight job queue (on-demand + session-close triggers)

create table if not exists public.insight_jobs (
  id              uuid primary key default gen_random_uuid(),
  instrument_id   smallint not null references public.instruments(id),
  symbol          text not null,
  user_id         uuid,
  trigger_type    text not null check (trigger_type in ('on_demand', 'session_close')),
  session_date    date not null,
  status          text not null default 'queued'
                  check (status in ('queued', 'running', 'done', 'failed')),
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  completed_at    timestamptz,
  error           text
);

create index if not exists idx_insight_jobs_status_created
  on public.insight_jobs (status, created_at);

-- Idempotent triggers: one session-close per instrument/day; one on-demand per user/instrument/day
create unique index if not exists idx_insight_jobs_session_close_dedup
  on public.insight_jobs (instrument_id, session_date, trigger_type)
  where trigger_type = 'session_close';

create unique index if not exists idx_insight_jobs_on_demand_dedup
  on public.insight_jobs (instrument_id, session_date, trigger_type, user_id)
  where trigger_type = 'on_demand' and user_id is not null;

alter table public.insight_jobs enable row level security;

-- Service role writes; authenticated users may read their own on-demand jobs
create policy "read own insight jobs" on public.insight_jobs
  for select to authenticated
  using (user_id is null or user_id = auth.uid());

create policy "enqueue on_demand jobs" on public.insight_jobs
  for insert to authenticated
  with check (user_id = auth.uid() and trigger_type = 'on_demand');
