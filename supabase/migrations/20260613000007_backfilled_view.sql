-- Which sites already have satellite timeseries — lets a large backfill resume by
-- skipping completed sites (distinct over timeseries is cheap via this view).
create view backfilled_sites as
select distinct site_id from timeseries;
