-- `backfilled_sites` was a view: `select distinct site_id from timeseries`. Once
-- timeseries grew to millions of rows that DISTINCT became a seq-scan and timed
-- out the --skip-existing resume check. Replace it with a small table the GEE
-- loader stamps once per site (so the resume check is a fast ~1.4k-row read).

drop view if exists backfilled_sites;

create table backfilled_sites (
  site_id       uuid primary key references sites (id) on delete cascade,
  backfilled_at timestamptz not null default now()
);

-- one-time seed from existing timeseries (disable the statement timeout just for
-- this heavy distinct, which the REST role would otherwise cancel)
set statement_timeout = 0;
insert into backfilled_sites (site_id)
select distinct site_id from timeseries
on conflict (site_id) do nothing;

alter table backfilled_sites enable row level security;
create policy "authenticated read backfilled_sites" on backfilled_sites
  for select to authenticated using (true);
