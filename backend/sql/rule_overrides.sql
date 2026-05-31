create table if not exists ips_rule_overrides (
  rule_id text primary key,
  source_file text not null,
  rule_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
