-- Expanded scope: all generation technologies across Germany (not just BW/BY solar).
-- Add the MaStR attributes the registry provides so the agent can cite them and the
-- dashboard can filter. `status` stays the satellite-derived construction state;
-- `mastr_status` is the registry's operational status (In Betrieb / In Planung / ...).

alter table sites
  add column technology               text,        -- solar | wind | biomass | hydro | geothermal | combustion | storage
  add column mastr_status             text,        -- registry operating status (German)
  add column commissioning_date       date,        -- Inbetriebnahmedatum
  add column planned_commissioning_date date,       -- GeplantesInbetriebnahmedatum
  add column municipality             text,        -- Gemeinde
  add column district                 text,        -- Landkreis
  add column unit_count               integer not null default 1;  -- >1 for clustered wind farms

create index sites_technology_idx on sites (technology);
create index sites_mastr_status_idx on sites (mastr_status);
