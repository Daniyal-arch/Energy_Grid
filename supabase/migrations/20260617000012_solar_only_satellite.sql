-- Satellite construction detection is reliable only for SOLAR (a hectares-scale
-- field→panels land-cover change Sentinel's 10 m pixels resolve well). For compact/
-- industrial techs (wind hull-AOI dilution, biomass/combustion/storage buildings,
-- brownfield sites) Sentinel can't see the build, so we monitor those via
-- authoritative milestones (registry, permit, grid) instead — not pixels.
--
-- One-time cleanup: drop the unreliable non-solar satellite timeseries + detections
-- (frees the bulk of the DB) and reset their satellite status. (Planet/high-res could
-- be added later for these if it becomes available.)
set statement_timeout = 0;

delete from timeseries t using sites s
  where t.site_id = s.id and s.technology is distinct from 'solar';
delete from evidence e using sites s
  where e.site_id = s.id and s.technology is distinct from 'solar';
delete from detections d using sites s
  where d.site_id = s.id and s.technology is distinct from 'solar';
delete from backfilled_sites b using sites s
  where b.site_id = s.id and s.technology is distinct from 'solar';

update sites set status = 'unknown', status_since = null
  where technology is distinct from 'solar' and status <> 'unknown';
