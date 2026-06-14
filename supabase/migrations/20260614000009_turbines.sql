-- Individual wind turbines within a wind-farm site, for real 3D turbine models.
-- Each turbine carries its MaStR hub height and rotor diameter so the frontend can
-- place a correctly-scaled mesh per turbine (the sites.geom is only the farm hull).

create table turbines (
  id               uuid primary key default gen_random_uuid(),
  site_id          uuid not null references sites (id) on delete cascade,
  mastr_id         text unique,
  lat              double precision not null,
  lon              double precision not null,
  hub_height_m     numeric(6, 2),
  rotor_diameter_m numeric(6, 2),
  capacity_kw      numeric(10, 2),
  status           text,
  created_at       timestamptz not null default now()
);

create index turbines_site_idx on turbines (site_id);

alter table turbines enable row level security;
create policy "authenticated read turbines" on turbines for select to authenticated using (true);
