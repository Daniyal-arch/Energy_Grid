-- Observation and analysis tables: timeseries, evidence, detections, weather, power_output.

-- Narrow time-series table. One row per (site, day, sensor, metric).
create table timeseries (
  id        bigint generated always as identity primary key,
  site_id   uuid not null references sites (id) on delete cascade,
  date      date not null,
  sensor    text not null,                 -- 's2' | 's1'
  metric    text not null,                 -- 'ndvi' | 'bsi' | 'vh_db'
  value     double precision not null,
  scene_id  text,                          -- provenance: source scene
  unique (site_id, date, sensor, metric)
);

create index timeseries_site_date_idx on timeseries (site_id, date);

-- Evidence: provenance records the agent cites. Chips live in Storage, URL only here.
create table evidence (
  id          uuid primary key default gen_random_uuid(),
  site_id     uuid not null references sites (id) on delete cascade,
  scene_id    text not null,
  sensor      text not null,
  acquired_at date not null,
  chip_url    text,
  metrics     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

create index evidence_site_idx on evidence (site_id, acquired_at);

-- Detections: every state-machine transition, linked to evidence.
create table detections (
  id           uuid primary key default gen_random_uuid(),
  site_id      uuid not null references sites (id) on delete cascade,
  detected_at  date not null,
  from_state   site_state not null,
  to_state     site_state not null,
  confidence   text not null,              -- 'low' | 'medium' | 'high'
  evidence_ids uuid[] not null default '{}',
  created_at   timestamptz not null default now()
);

create index detections_site_idx on detections (site_id, detected_at);
create index detections_recent_idx on detections (created_at desc);

-- Daily weather per site (DWD via Bright Sky). Used for observation masking.
create table weather (
  id       bigint generated always as identity primary key,
  site_id  uuid not null references sites (id) on delete cascade,
  date     date not null,
  rain_mm  double precision,
  snow     boolean not null default false,
  temp_c   double precision,               -- daily mean
  unique (site_id, date)
);

create index weather_site_date_idx on weather (site_id, date);

-- Power output (ENTSO-E per-unit / SMARD regional). Cross-check for 'complete'.
create table power_output (
  id        bigint generated always as identity primary key,
  plant_id  text not null,                 -- EIC code or MaStR unit id
  site_id   uuid references sites (id) on delete set null,
  date      date not null,
  mwh       double precision not null,
  source    text not null,                 -- 'entsoe' | 'smard'
  unique (plant_id, date, source)
);

create index power_output_site_idx on power_output (site_id, date);

alter table timeseries enable row level security;
alter table evidence enable row level security;
alter table detections enable row level security;
alter table weather enable row level security;
alter table power_output enable row level security;
create policy "authenticated read timeseries" on timeseries for select to authenticated using (true);
create policy "authenticated read evidence" on evidence for select to authenticated using (true);
create policy "authenticated read detections" on detections for select to authenticated using (true);
create policy "authenticated read weather" on weather for select to authenticated using (true);
create policy "authenticated read power_output" on power_output for select to authenticated using (true);
