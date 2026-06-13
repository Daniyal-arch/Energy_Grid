-- The sites_with_centroid view froze its column list when created (a `select s.*`
-- view does not pick up columns added later). Recreate it so the new MaStR fields
-- (technology, mastr_status, commissioning_date, ...) are exposed to API consumers.

drop view if exists sites_with_centroid;

create view sites_with_centroid as
select
  s.*,
  extensions.st_y(extensions.st_centroid(s.geom)) as lat,
  extensions.st_x(extensions.st_centroid(s.geom)) as lon
from sites s;
