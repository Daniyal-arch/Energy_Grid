-- ENTSO-E per-unit registry: the ~90 large generation units (>=100 MW) published
-- for Germany, with name + capacity + type. Joined to our sites where we can match
-- them — independent grid confirmation that a large plant is operational.

create table grid_units (
  eic         text primary key,
  name        text,
  capacity_mw numeric(10, 2),
  psr_type    text,
  site_id     uuid references sites (id) on delete set null,
  source      text not null default 'entsoe',
  updated_at  timestamptz not null default now()
);

create index grid_units_site_idx on grid_units (site_id);

alter table grid_units enable row level security;
create policy "authenticated read grid_units" on grid_units for select to authenticated using (true);
