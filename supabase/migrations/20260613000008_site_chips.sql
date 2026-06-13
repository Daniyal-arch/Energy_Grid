-- Before/after satellite snapshot URLs per site (images live in Storage bucket `chips`).
alter table sites
  add column chip_before_url  text,
  add column chip_after_url   text,
  add column chip_before_date text,
  add column chip_after_date  text;

-- recreate the centroid view so the new columns surface to the API
drop view if exists sites_with_centroid;
create view sites_with_centroid as
select
  s.*,
  extensions.st_y(extensions.st_centroid(s.geom)) as lat,
  extensions.st_x(extensions.st_centroid(s.geom)) as lon
from sites s;
