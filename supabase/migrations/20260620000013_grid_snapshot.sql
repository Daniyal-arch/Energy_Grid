-- Energy-Charts.info (Fraunhofer ISE) — zone-level live grid data: generation mix
-- per fuel, day-ahead price, and a carbon-intensity figure WE COMPUTE in the
-- ingestion transform() step from generation-mix x static emission factors (never
-- computed live by the agent or frontend — see ingestion/sources/energycharts.py).
-- Narrow-table pattern mirroring the project's (site_id, date, sensor, metric, value)
-- timeseries convention, widened to zone+hourly instead of site+daily.

create table grid_snapshot (
  zone       text not null,
  ts         timestamptz not null,
  metric     text not null,
  value      double precision not null,
  source     text not null,
  created_at timestamptz not null default now(),
  primary key (zone, ts, metric, source)
);

create index grid_snapshot_zone_ts_idx on grid_snapshot (zone, ts desc);

alter table grid_snapshot enable row level security;
create policy "authenticated read grid_snapshot" on grid_snapshot for select to authenticated using (true);

create table grid_exchange (
  zone          text not null,
  neighbor_zone text not null,
  ts            timestamptz not null,
  value_mw      double precision not null,
  source        text not null,
  created_at    timestamptz not null default now(),
  primary key (zone, neighbor_zone, ts, source)
);

create index grid_exchange_zone_ts_idx on grid_exchange (zone, ts desc);

alter table grid_exchange enable row level security;
create policy "authenticated read grid_exchange" on grid_exchange for select to authenticated using (true);
