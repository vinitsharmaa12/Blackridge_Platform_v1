-- Drop auth.users FK on insight_jobs.user_id.
-- RLS policies enforce ownership; dev JWT users may not exist in auth.users.

alter table public.insight_jobs
  drop constraint if exists insight_jobs_user_id_fkey;
