create table if not exists login_log (
  id bigint generated always as identity primary key,
  email text not null,
  name text,
  role text,
  logged_in_at timestamptz default now()
);
create index if not exists idx_login_log_at on login_log (logged_in_at desc);
