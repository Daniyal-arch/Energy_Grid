-- Core entities: sites and their legal deadlines.

create type site_state as enum (
  'unknown',
  'no_activity',
  'clearing',
  'earthworks',
  'construction',
  'complete'
);

create table sites (
  id            uuid primary key default gen_random_uuid(),
  mastr_id      text unique,
  name          text not null,
  geom          extensions.geometry(MultiPolygon, 4326) not null,
  capacity_mw   numeric(8, 2) not null,
  state         text not null,                       -- German federal state, e.g. 'Bayern'
  owner         text,
  status        site_state not null default 'unknown',
  status_since  date,
  aoi_method    text,                                -- 'osm_polygon' | 'capacity_buffer'
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index sites_geom_idx on sites using gist (geom);
create index sites_status_idx on sites (status);

create table deadlines (
  id            uuid primary key default gen_random_uuid(),
  site_id       uuid not null references sites (id) on delete cascade,
  source        text not null,                       -- e.g. 'eeg_auction_2024_2'
  deadline_date date not null,
  type          text not null,                       -- e.g. 'legal_completion', 'customer_schedule'
  created_at    timestamptz not null default now(),
  unique (site_id, source, type)
);

create index deadlines_site_idx on deadlines (site_id);

-- Centroid view for point-based APIs (weather lookups).
create view sites_with_centroid as
select
  s.*,
  extensions.st_y(extensions.st_centroid(s.geom)) as lat,
  extensions.st_x(extensions.st_centroid(s.geom)) as lon
from sites s;

-- updated_at maintenance
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

create trigger sites_set_updated_at
  before update on sites
  for each row execute function set_updated_at();

-- RLS: service-role key (pipelines, backend) bypasses RLS; authenticated users read-only.
alter table sites enable row level security;
alter table deadlines enable row level security;
create policy "authenticated read sites" on sites for select to authenticated using (true);
create policy "authenticated read deadlines" on deadlines for select to authenticated using (true);
