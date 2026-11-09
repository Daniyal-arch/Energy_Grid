# Query speed: every dataset (brief 32)

How fast each dataset answers the standard query set, measured by
`backend/probes/probe_query_speed.py` in the Lambda-sized container (2 vCPU, 3,008 MB) against
the real lake on R2, with the fake model (`.github/workflows/backend-probe.yml`, job
`query-speed`, eight shards). The probe's own docstring lists the query set. The machine-read
copy for the CI speed check is `data/query_speed.json`.

## Before the tiers (run 42452845406, 2026-11-08)

Probed 2026-11-08T06:01:27+00:00 in the Lambda-sized container (2 vCPU, 3,008 MB) against `r2:r2://infraatlas-raw/lake/lake.duckdb`; 924 tables in 8 shards. Times in ms (cold = the first run of each query in the process; warm = the median of 3 repeats); MB and GET requests read from R2 by the cold runs of the table's query set.

### All dataset queries

| | queries | p50 | p95 | max |
|---|---:|---:|---:|---:|
| cold | 3409 | 382 | 2,072 | 46,533 |
| warm | 3396 | 269 | 692 | 15,998 |

### Data routes: cold p50/p95 16.9 / 23,621, warm p50/p95 19.9 / 392

| | cold | warm p50 | note |
|---|---:|---:|---|
| GET /api/health | 11.6 | 13.7 | status 200 |
| GET /api/catalog/search?q=solar%20capacity%20Germany | 1,869 | 4.3 | status 200 |
| GET /api/catalog/atb | 3.8 | 3.5 | status 200 |
| GET /api/places?q=Bavaria | 14.4 | 14.1 | status 200 |
| GET /api/places?q=Lyon | 14.8 | 15.0 | status 200 |
| GET /api/site?lon=11.58&lat=48.14&radius_km=50 | 317 | 48.4 | status 200 |
| GET /api/areas/resolve?q=Bavaria | 94.6 | 64.1 | status 200 |
| GET /api/areas/resolve?q=Berlin&level=city | 9.6 | 9.0 | status 200 |
| GET /api/shapes/admin1/DEU | 325 | 344 | status 200 |
| GET /api/quick | 9.1 | 3.0 | status 200 |
| GET /api/quick/profile?area=Germany | 40.7 | 31.2 | status 404 |
| GET /api/quick/top?area=Bavaria&n=10 | 381 | 383 | status 200 |
| GET /api/quick/totals?area=Europe | 27,994 | 50.6 | status 404 |
| GET /api/quick/published?area=France | 8.4 | 8.0 | status 404 |
| GET /api/quick/prices?area=Germany | 16.9 | 16.1 | status 200 |
| GET /api/report.json?lon=11.58&lat=48.14&radius_km=25&task=data_centre | 6.5 | 3.1 | status 422 |
| GET /api/feed/DEU.json | 23,621 | 328 | status 500 |
| POST /api/maps | 843 | 826 | status 200 |

### quick templates: cold p50/p95 418 / 6,611, warm p50/p95 404 / 3,814

| | cold | warm p50 | note |
|---|---:|---:|---|
| profile Germany | 452 | 449 | Data centres: CatalogException: Catalog Error: Table with name data_centres does not exist! |
| profile Bavaria | 3,853 | 3,870 | Data centres: CatalogException: Catalog Error: Table with name data_centres does not exist! |
| profile Berlin | 6,611 | 967 | Data centres: CatalogException: Catalog Error: Table with name data_centres does not exist! |
| top Germany | 231 | 231 |  |
| top Bavaria | 418 | 404 |  |
| top France | 232 | 238 | Data centres: CatalogException: Catalog Error: Table with name data_centres does not exist! |
| totals Europe | 1,063 | 935 | Data centres: CatalogException: Catalog Error: Table with name data_centres does not exist! |
| totals United States | 358 | 233 |  |
| compare France; Germany | 479 | 466 | Data centres: CatalogException: Catalog Error: Table with name data_centres does not exist! |
| published Poland | 0.6 | 0.5 | the coverage registry is not in this service |
| prices Germany | 231 | 234 |  |

### resolve_area: cold p50/p95 2,154 / 6,570, warm p50/p95 2,176 / 4,571

| | cold | warm p50 | note |
|---|---:|---:|---|
| Germany | 0.4 | 3,444 |  |
| France | 5,393 | 2,520 |  |
| Poland | 2,154 | 4,938 |  |
| Spain | 649 | 634 |  |
| Italy | 2,315 | 2,625 |  |
| United States | 676 | 659 |  |
| Nordics | 1,497 | 1,222 |  |
| EU-27 | 2,709 | 2,870 |  |
| Bavaria | 24,627 | 2,811 |  |
| Lower Saxony | 2,459 | 4,002 |  |
| Catalonia | 6,570 | 4,121 |  |
| Lombardy | 3,420 | 2,524 |  |
| Texas | 3,074 | 3,645 |  |
| California | 2,539 | 2,302 |  |
| Scotland | 3,608 | 2,786 |  |
| Brittany | 4,103 | 4,243 |  |
| Masovian Voivodeship | 3,902 | 2,796 |  |
| North Rhine-Westphalia | 2,554 | 2,589 |  |
| Andalusia | 2,847 | 2,546 |  |
| Upper Bavaria | 638 | 584 | not resolved |
| Harris County | 2,667 | 3,683 |  |
| Cook County | 3,958 | 3,494 |  |
| Kreis Steinfurt | 3,715 | 2,176 |  |
| Greater Manchester | 3,824 | 3,307 |  |
| Cornwall | 3,965 | 4,144 |  |
| Berlin | 2,422 | 1,344 |  |
| Paris | 1,326 | 1,318 |  |
| Madrid | 1,453 | 1,373 |  |
| Rome | 3,710 | 2,207 |  |
| Warsaw | 1,272 | 1,322 |  |
| Toulouse | 1,258 | 1,241 |  |
| Lyon | 1,351 | 1,333 |  |
| Hamburg | 1,464 | 1,373 |  |
| Munich | 1,348 | 1,399 |  |
| Vienna | 1,287 | 1,338 |  |
| Amsterdam | 1,278 | 1,304 |  |
| Copenhagen | 1,241 | 1,259 |  |
| Dublin | 1,294 | 1,254 |  |
| Lisbon | 1,336 | 1,365 |  |
| Houston | 1,297 | 1,336 |  |
| Leeds | 1,328 | 1,319 |  |
| Manchester | 1,266 | 1,412 |  |
| Kreuzberg | 2,127 | 2,346 |  |
| Schwabing | 691 | 630 | not resolved |
| Montmartre | 5,349 | 2,333 |  |
| DE-LU | 1,463 | 1,224 |  |
| NO2 | 21,726 | 21,047 |  |
| IT-North | 1,528 | 1,207 |  |
| Sicily | 3,112 | 3,012 |  |
| Saxony-Anhalt | 4,422 | 3,195 |  |

### area_stats: cold p50/p95 2.8 / 53.4, warm p50/p95 2.4 / 51.6

| | cold | warm p50 | note |
|---|---:|---:|---|
| people (city) | 2.5 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| people (region) | 51.8 | 46.9 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| built_up (city) | 2.6 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| built_up (region) | 46.9 | 46.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| land_cover (city) | 2.4 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| land_cover (region) | 47.6 | 47.1 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| slope (city) | 2.6 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| slope (region) | 60.9 | 46.5 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| solar (city) | 2.5 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| solar (region) | 47.5 | 48.5 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| wind (city) | 2.7 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| wind (region) | 49.5 | 46.7 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| flood (city) | 2.5 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| flood (region) | 46.9 | 47.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| heat_demand (city) | 2.5 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| heat_demand (region) | 46.2 | 45.8 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_edo_cdi (city) | 2.4 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_edo_cdi (region) | 46.6 | 47.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_effis_danger (city) | 2.5 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_effis_danger (region) | 56.4 | 51.1 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_bathy (city) | 2.4 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_bathy (region) | 50.6 | 50.5 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_vessel_density (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_vessel_density (region) | 51.1 | 50.5 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_marinecadastre_ais (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_marinecadastre_ais (region) | 51.7 | 52.1 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_noaa_slr (city) | 2.5 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_noaa_slr (region) | 48.7 | 47.7 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_usfs_whp (city) | 2.5 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_usfs_whp (region) | 51.3 | 52.7 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_gebco (city) | 2.8 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_gebco (region) | 53.4 | 51.6 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_nex_gddp (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_nex_gddp (region) | 50.3 | 50.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |

### Every table (slowest cold p95 first)

| table | cold p50 | cold p95 | warm p50 | warm p95 | MB cold | GETs | notes |
|---|---:|---:|---:|---:|---:|---:|---|
| `power_plants_eu.ppm_plants` | 336 | 46,533 | 244 | 357 | 8.16 | 12 |  |
| `entsoe.imbalance_price` | 855 | 44,994 | 692 | 794 | 27.86 | 356 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `overture_power.lines` | 2,016 | 44,950 | 369 | 1,312 | 326.43 | 129 |  |
| `us_lmp.day_ahead` | 805 | 43,372 | 809 | 809 | 111.78 | 288 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `main.prices` | 1,073 | 38,392 | 1,136 | 1,179 | 123.71 | 306 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `outlines.divisions` | 6,971 | 35,773 | 1,568 | 4,469 | 868.25 | 487 |  |
| `ev_eu.de` | 398 | 33,632 | 237 | 406 | 4.41 | 11 |  |
| `main.plants` | 26,248 | 31,830 | 3,470 | 3,475 | 390.04 | 689 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ...LECT * FROM |
| `overture_transport.segments` | 9,297 | 25,380 | 6,555 | 6,886 | 1,345.57 | 265 | region: TimeoutError: query stopped after 60 s |
| `wave9.eu_kohesio_2014_2020` | 982 | 22,113 | 213 | 629 | 394.44 | 200 |  |
| `entsoe.unit_output` | 2,011 | 21,652 | 262 | 262 | 0.91 | 116 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `mastr.units_biomass` | 768 | 16,342 | 308 | 15,998 | 8.27 | 21 |  |
| `rollups.overture_power__sites_r7` | 546 | 16,150 | 287 | 15,901 | 8.23 | 14 |  |
| `wave9.cz_zsj` | 456 | 14,979 | 462 | 10,486 | 75.71 | 43 |  |
| `wave9.eur_overture_comm_lines` | 455 | 14,722 | 387 | 8,408 | 3.58 | 8 |  |
| `industrial.installations` | 1,659 | 14,594 | 451 | 14,443 | 13.43 | 15 |  |
| `mastr.units_combustion` | 429 | 13,598 | 315 | 13,688 | 6.49 | 11 |  |
| `mastr.units_storage` | 844 | 13,245 | 438 | 3,721 | 230.78 | 142 |  |
| `entsoe.generation` | 7,041 | 13,127 | 341 | 491 | 0.75 | 119 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `rollups.wave9__de_zensus_heating_r7` | 476 | 12,762 | 380 | 12,302 | 0.89 | 6 |  |
| `grw.wind` | 789 | 12,536 | 839 | 2,156 | 45.64 | 30 |  |
| `mastr.units_solar` | 6,246 | 11,400 | 384 | 1,324 | 378.31 | 366 | region: TimeoutError: query stopped after 60 s |
| `nl_capacity.areas` | 403 | 11,220 | 381 | 2,709 | 70.50 | 45 |  |
| `aqueduct.basins` | 858 | 10,792 | 812 | 1,003 | 130.09 | 50 |  |
| `rollups.overture_transport__segments_r7` | 529 | 10,470 | 284 | 10,392 | 9.22 | 14 |  |
| `wave9.at_zaehlsprengel` | 479 | 10,019 | 388 | 8,902 | 121.88 | 41 |  |
| `wave9.eu_emodnet_mpa` | 1,001 | 9,890 | 960 | 3,562 | 348.40 | 97 |  |
| `rollups.mastr__units_solar_r7` | 333 | 9,579 | 220 | 9,544 | 1.31 | 7 |  |
| `wave9.gb_ea_flood_zones` | 2,902 | 9,456 | 466 | 792 | 146.14 | 97 | country: TimeoutError: query stopped after 60 s |
| `wave9.it_istat_sezioni` | 422 | 8,466 | 416 | 3,136 | 243.60 | 108 |  |
| `industrial.water_releases` | 1,459 | 8,243 | 422 | 8,238 | 3.50 | 10 |  |
| `eaglei.outages` | 3,178 | 7,864 | 319 | 595 | 18.50 | 45 |  |
| `industrial.lcp` | 1,497 | 7,768 | 397 | 7,756 | 4.20 | 11 |  |
| `wave9.us_usgs_landslides` | 551 | 7,746 | 409 | 3,240 | 64.38 | 35 |  |
| `wave10.eu_env_ac_ainah_r2` | 2,331 | 7,698 | 339 | 817 | 33.51 | 24 |  |
| `wave9.us_epa_repowering` | 565 | 7,195 | 283 | 1,874 | 28.17 | 22 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... COUNT(*) F |
| `protected.padus` | 1,891 | 6,863 | 562 | 2,034 | 228.45 | 48 |  |
| `outlines.adm2` | 886 | 6,244 | 821 | 1,619 | 200.36 | 74 |  |
| `small_area_energy.poverty` | 496 | 6,208 | 317 | 780 | 4.33 | 49 |  |
| `protected.natura2000` | 557 | 6,168 | 430 | 6,187 | 32.43 | 22 |  |
| `wave9.us_usgs_mrds` | 549 | 5,922 | 426 | 1,867 | 34.17 | 30 |  |
| `industrial.air_releases` | 1,077 | 5,906 | 340 | 5,767 | 6.17 | 11 |  |
| `wave10.eu_nrg_ti_oilm` | 2,083 | 5,738 | 272 | 714 | 2.14 | 55 |  |
| `wave9.es_ine_secciones` | 371 | 5,692 | 338 | 613 | 66.69 | 38 |  |
| `mastr.units_hydro` | 384 | 5,540 | 238 | 5,590 | 2.96 | 9 |  |
| `iso_queues.requests` | 389 | 5,437 | 332 | 341 | 3.16 | 33 |  |
| `wave10.eu_nrg_stk_oam` | 3,861 | 5,389 | 255 | 599 | 1.81 | 111 |  |
| `outlines.geostat_grid` | 1,945 | 5,288 | 483 | 2,628 | 155.95 | 47 | region: TimeoutError: query stopped after 60 s |
| `aqueduct.baseline_annual` | 2,567 | 5,251 | 1,159 | 5,191 | 471.81 | 82 |  |
| `main.outages` | 1,339 | 5,157 | 632 | 1,357 | 21.40 | 35 | lookup: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modu |
| `aqueduct.future_annual` | 426 | 5,088 | 215 | 219 | 7.06 | 10 |  |
| `rollups.overture_power__sites_r6` | 650 | 5,069 | 216 | 5,034 | 4.97 | 13 |  |
| `wave10.eu_nrg_te_oilm` | 2,545 | 4,871 | 380 | 593 | 2.07 | 56 |  |
| `wave9.eu_emodnet_msp_zoning` | 652 | 4,766 | 405 | 658 | 71.62 | 41 |  |
| `wave10.eu_env_ac_pefasu` | 536 | 4,572 | 292 | 797 | 4.03 | 22 |  |
| `wave10.eu_nrg_cb_oil` | 560 | 4,480 | 306 | 731 | 2.64 | 23 |  |
| `rollups.overture_transport__segments_r6` | 536 | 4,373 | 296 | 4,341 | 3.90 | 12 |  |
| `grw.solar` | 790 | 4,161 | 760 | 4,078 | 112.98 | 52 |  |
| `wave10.eu_nrg_stk_oilm` | 857 | 4,157 | 286 | 634 | 3.81 | 22 |  |
| `wave9.eu_emodnet_substrate` | 722 | 4,133 | 723 | 1,077 | 97.20 | 41 |  |
| `entsoe.flows` | 1,972 | 4,099 | 269 | 281 | 2.34 | 33 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `main.water_risk` | 2,747 | 4,081 | 1,534 | 4,597 | 396.98 | 28 |  |
| `overture_power.sites` | 928 | 4,016 | 368 | 1,543 | 135.03 | 69 | region: TimeoutError: query stopped after 60 s |
| `wave10.eu_env_ac_hfcfp` | 530 | 3,793 | 269 | 323 | 12.61 | 20 |  |
| `wave9.gb_he_listed` | 524 | 3,788 | 402 | 2,226 | 29.84 | 21 |  |
| `outlines.small_areas` | 592 | 3,723 | 428 | 1,318 | 111.96 | 39 |  |
| `mastr.units_wind` | 831 | 3,682 | 291 | 3,667 | 6.07 | 20 |  |
| `outlines.fr_iris` | 374 | 3,632 | 334 | 816 | 107.13 | 48 |  |
| `small_area_energy.consumption` | 892 | 3,617 | 296 | 325 | 43.31 | 42 |  |
| `eia930.demand` | 1,437 | 3,554 | 283 | 337 | 14.12 | 24 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave10.eu_env_ac_co2fp` | 536 | 3,537 | 243 | 309 | 22.31 | 19 |  |
| `rollups.overture_power__lines_r7` | 601 | 3,496 | 289 | 3,513 | 5.36 | 13 |  |
| `rollups.mastr__units_solar_r6` | 384 | 3,490 | 298 | 3,489 | 0.44 | 7 |  |
| `osm.eu_lines` | 407 | 3,426 | 330 | 431 | 14.15 | 17 |  |
| `wave10.eu_env_ac_aeint_r2` | 609 | 3,404 | 298 | 669 | 6.56 | 17 |  |
| `wave10.eu_env_ac_nf3sf6fp` | 559 | 3,364 | 264 | 290 | 1.88 | 14 |  |
| `entsoe.congestion_countertrading` | 289 | 3,356 | 502 | 518 | 0.34 | 20 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave9.world_ourairports` | 401 | 3,320 | 266 | 812 | 6.35 | 15 |  |
| `app.world_plants` | 25.4 | 3,319 | 5.7 | 3,353 | 0.00 | 0 |  |
| `dams.reservoirs` | 482 | 3,251 | 510 | 1,474 | 134.76 | 44 |  |
| `rollups.overture_power__lines_r6` | 438 | 3,201 | 223 | 3,103 | 3.48 | 12 |  |
| `wave9.us_opportunity_zones` | 558 | 3,189 | 553 | 632 | 56.80 | 34 |  |
| `outlines.uk_ons` | 446 | 3,167 | 390 | 1,798 | 163.13 | 57 |  |
| `gem.integrated_power_power_facilities` | 1,243 | 3,148 | 404 | 3,130 | 2.23 | 7 | lookup: gem.integrated_power_power_facilities is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, no |
| `main.grid_capacity` | 1,209 | 3,090 | 1,111 | 1,120 | 1.92 | 37 |  |
| `wave9.us_noaa_mpa` | 399 | 3,068 | 343 | 1,175 | 133.37 | 43 |  |
| `entsoe.congestion_redispatch_cross_border` | 278 | 3,017 | 299 | 306 | 0.20 | 20 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `outlines.us_tracts` | 1,210 | 2,978 | 1,022 | 1,522 | 138.40 | 29 |  |
| `caiso.curtailment` | 299 | 2,924 | 293 | 297 | 4.80 | 21 |  |
| `neso.constraint_breakdown` | 277 | 2,900 | 275 | 285 | 0.32 | 21 |  |
| `wave9.dk_energinet_reserves` | 593 | 2,889 | 254 | 282 | 3.13 | 6 |  |
| `atb.electricity` | 809 | 2,835 | 295 | 309 | 6.36 | 11 |  |
| `entsoe.congestion_redispatch_internal` | 357 | 2,824 | 300 | 307 | 1.38 | 20 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave9.us_fhwa_afc` | 521 | 2,760 | 499 | 914 | 49.32 | 23 |  |
| `wave9.gb_ne_alc` | 459 | 2,756 | 432 | 773 | 53.51 | 24 |  |
| `wave9.us_nyc_ll84` | 713 | 2,715 | 208 | 332 | 19.59 | 16 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... (SELECT CO |
| `outlines.us_cousub` | 839 | 2,701 | 914 | 1,153 | 101.14 | 24 |  |
| `wave9.be_fluvius_consumption` | 538 | 2,698 | 273 | 307 | 5.91 | 7 |  |
| `wave9.us_noaa_storm_events` | 440 | 2,682 | 315 | 647 | 6.45 | 15 |  |
| `wave9.us_natcarb` | 545 | 2,664 | 440 | 1,667 | 9.21 | 13 |  |
| `entsoe.outages` | 274 | 2,639 | 279 | 280 | 16.49 | 15 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave9.eu_tent_network` | 574 | 2,577 | 448 | 1,094 | 20.78 | 17 |  |
| `wave9.de_zensus_heating` | 582 | 2,542 | 401 | 846 | 8.09 | 6 | region: TimeoutError: query stopped after 60 s |
| `wave9.fr_georisques_ssp` | 747 | 2,535 | 565 | 834 | 35.07 | 18 |  |
| `rollups.mastr__units_storage_r7` | 417 | 2,475 | 281 | 2,482 | 0.13 | 7 |  |
| `rollups.wave9__de_zensus_heating_r6` | 445 | 2,466 | 444 | 2,447 | 0.16 | 6 |  |
| `wave10.eu_env_ac_n2ofp` | 925 | 2,445 | 272 | 291 | 8.27 | 17 |  |
| `wave10.eu_env_ac_ghgfp` | 442 | 2,442 | 202 | 255 | 22.05 | 17 |  |
| `wave9.fi_paavo` | 507 | 2,369 | 440 | 989 | 25.56 | 16 |  |
| `wave9.fr_ore_ev_commune` | 574 | 2,313 | 280 | 292 | 2.22 | 6 |  |
| `wave9.ie_cso_saps_heating` | 871 | 2,278 | 279 | 363 | 10.46 | 10 |  |
| `entsoe.prices` | 1,725 | 2,241 | 280 | 292 | 11.85 | 16 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave9.gb_srn` | 528 | 2,235 | 423 | 951 | 15.87 | 15 |  |
| `wave10.eu_nrg_cb_oilm` | 556 | 2,233 | 286 | 512 | 2.34 | 11 |  |
| `wave10.eu_env_ac_egss2` | 463 | 2,204 | 218 | 664 | 2.97 | 17 |  |
| `wave9.gr_admie_balancing` | 570 | 2,186 | 258 | 280 | 9.37 | 9 |  |
| `wave10.eu_env_ac_ch4fp` | 891 | 2,164 | 266 | 313 | 6.66 | 15 |  |
| `shapes.admin1_simplified` | 573 | 2,135 | 452 | 600 | 13.26 | 13 |  |
| `aqueduct.baseline_monthly` | 531 | 2,128 | 302 | 322 | 4.83 | 9 |  |
| `dams.barriers` | 434 | 2,072 | 239 | 546 | 3.99 | 12 |  |
| `entsoe.congestion_costs` | 217 | 2,060 | 220 | 245 | 0.07 | 17 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave9.de_regelleistung` | 580 | 2,051 | 310 | 356 | 2.48 | 6 |  |
| `entsoe.forecast_wind_solar` | 1,258 | 2,045 | 224 | 243 | 14.11 | 26 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `entsoe.transfer_capacity` | 319 | 2,037 | 290 | 306 | 7.23 | 14 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `outlines.us_places` | 914 | 1,964 | 690 | 946 | 73.37 | 21 |  |
| `wave9.eu_emodnet_pipelines` | 372 | 1,923 | 341 | 530 | 25.43 | 18 |  |
| `entsoe.capacity` | 234 | 1,853 | 224 | 226 | 0.05 | 15 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `rollups.overture_power__sites_r5` | 441 | 1,826 | 221 | 1,898 | 2.41 | 11 |  |
| `wave9.us_eia_gas_pipelines` | 392 | 1,814 | 237 | 809 | 4.41 | 12 |  |
| `wave10.eu_env_ac_pfcfp` | 548 | 1,809 | 267 | 302 | 1.60 | 17 |  |
| `wave9.us_epa_frs_cleanups` | 344 | 1,791 | 226 | 517 | 3.45 | 11 |  |
| `entsoe.load` | 747 | 1,790 | 219 | 225 | 0.29 | 26 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `shapes.admin1` | 680 | 1,786 | 648 | 2,003 | 78.40 | 6 |  |
| `wave9.se_svk_reserves` | 554 | 1,779 | 255 | 325 | 12.58 | 9 |  |
| `outlines.nl_cbs` | 416 | 1,769 | 417 | 912 | 75.79 | 31 |  |
| `wave10.eu_nrg_bal_s` | 452 | 1,752 | 257 | 564 | 2.74 | 9 |  |
| `euets.verified_emissions` | 545 | 1,732 | 253 | 387 | 4.09 | 8 |  |
| `wave9.us_boem_active_leases` | 571 | 1,715 | 401 | 747 | 5.16 | 11 |  |
| `rollups.overture_power__lines_r5` | 422 | 1,650 | 257 | 1,673 | 1.76 | 7 |  |
| `history.esb_heatmap__transformers` | 445 | 1,621 | 434 | 487 | 2.23 | 9 |  |
| `wave9.ee_grid` | 386 | 1,617 | 239 | 395 | 2.27 | 12 |  |
| `wave9.pl_pse_balancing` | 456 | 1,589 | 211 | 214 | 2.60 | 6 |  |
| `wave9.eu_eshm20` | 448 | 1,545 | 440 | 1,556 | 1.21 | 6 |  |
| `wave9.ie_seai_ber` | 1,256 | 1,541 | 237 | 808 | 5.31 | 12 |  |
| `wave9.us_usgs_nshm` | 552 | 1,517 | 492 | 898 | 9.84 | 11 |  |
| `wave9.gb_brownfield_register` | 468 | 1,503 | 342 | 489 | 4.17 | 12 |  |
| `rollups.mastr__units_solar_r5` | 432 | 1,451 | 282 | 1,467 | 0.14 | 7 |  |
| `rollups.mastr__units_storage_r6` | 408 | 1,442 | 279 | 1,435 | 0.11 | 7 |  |
| `outlines.aliases` | 488 | 1,428 | 358 | 391 | 3.34 | 7 |  |
| `history.wave9__gb_brownfield_register` | 382 | 1,410 | 376 | 385 | 4.17 | 9 |  |
| `gem.coal_mines_historical_production_china` | 478 | 1,402 | 280 | 283 | 0.04 | 3 | lookup: gem.coal_mines_historical_production_china is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returne |
| `wave9.us_epa_aqs_annual` | 383 | 1,395 | 251 | 694 | 3.64 | 11 |  |
| `wave9.us_boem_wind_leases` | 479 | 1,386 | 420 | 449 | 2.27 | 8 |  |
| `ev_eu.at` | 326 | 1,371 | 244 | 1,388 | 0.41 | 7 |  |
| `wave10.eu_cei_pc034` | 704 | 1,286 | 274 | 277 | 0.01 | 5 |  |
| `ev_eu.fr` | 398 | 1,214 | 306 | 409 | 3.73 | 9 |  |
| `places.cities` | 390 | 1,214 | 224 | 624 | 2.37 | 10 |  |
| `wave10.eu_env_ac_aibrid_r2` | 527 | 1,213 | 291 | 366 | 2.67 | 7 |  |
| `app.eu_lines` | 160 | 1,210 | 163 | 1,224 | 0.00 | 0 |  |
| `main.emissions` | 538 | 1,208 | 275 | 281 | 1.21 | 7 |  |
| `wave9.si_surs_heating_settlement` | 565 | 1,186 | 490 | 837 | 0.67 | 4 |  |
| `wave10.eu_env_ac_io10` | 574 | 1,176 | 302 | 840 | 2.59 | 7 |  |
| `connect_eu.es_dso` | 437 | 1,163 | 274 | 500 | 0.13 | 7 |  |
| `rollups.overture_transport__segments_r5` | 384 | 1,151 | 282 | 1,151 | 1.35 | 7 |  |
| `egrid.plants` | 651 | 1,132 | 378 | 388 | 2.55 | 11 |  |
| `wave9.us_drought_monitor` | 388 | 1,126 | 384 | 397 | 2.30 | 8 |  |
| `gem.oil_gas_extraction_field_level_main_data` | 535 | 1,122 | 428 | 432 | 0.12 | 6 | lookup: gem.oil_gas_extraction_field_level_main_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be retur |
| `rollups.mastr__units_storage_r5` | 435 | 1,104 | 278 | 1,140 | 0.07 | 7 |  |
| `history.connect_eu__es_dso` | 423 | 1,080 | 314 | 447 | 0.13 | 7 |  |
| `wave9.de_bfee_abwaerme` | 538 | 1,079 | 273 | 300 | 2.36 | 6 |  |
| `entsog.flows` | 262 | 1,077 | 219 | 228 | 10.72 | 8 | lookup: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modu |
| `wave9.us_nrhp` | 501 | 1,058 | 300 | 762 | 6.96 | 13 |  |
| `wave9.us_usgs_nwis_sites` | 392 | 1,056 | 256 | 1,050 | 10.33 | 13 |  |
| `co2stop.storage_units_user_and_database_calc_storage` | 334 | 1,053 | 265 | 274 | 0.00 | 3 |  |
| `wave9.us_openei_urdb` | 1,034 | 1,034 | 279 | 279 | 0.13 | 3 |  |
| `shapes.nuts` | 311 | 1,032 | 289 | 1,028 | 0.00 | 6 |  |
| `mastr.operators` | 279 | 948 | 288 | 291 | 0.40 | 5 |  |
| `wave10.eu_env_ac_rmefd` | 551 | 941 | 269 | 929 | 1.67 | 5 |  |
| `wave9.fi_statfin_heating_fuel_municipality` | 430 | 915 | 227 | 910 | 0.99 | 4 |  |
| `euets.eea_link` | 373 | 910 | 380 | 901 | 0.40 | 6 |  |
| `wave10.eu_nrg_ti_oil` | 614 | 880 | 297 | 748 | 1.10 | 5 |  |
| `wave9.lv_csp_central_heating` | 552 | 874 | 292 | 836 | 0.51 | 4 |  |
| `outlines.urban_centres` | 712 | 871 | 647 | 805 | 10.84 | 12 |  |
| `wave10.eu_env_ac_ainah_rd` | 627 | 863 | 253 | 440 | 3.93 | 7 |  |
| `outlines.names` | 795 | 858 | 394 | 445 | 1.53 | 9 |  |
| `esb_heatmap.transformers` | 435 | 858 | 439 | 471 | 2.23 | 9 |  |
| `co2stop.total_storecap_nolargestorage_countries` | 277 | 844 | 267 | 269 | 0.01 | 3 |  |
| `euets.installations` | 329 | 833 | 291 | 315 | 5.45 | 7 |  |
| `mastr.units_nuclear` | 478 | 826 | 281 | 462 | 0.05 | 9 |  |
| `mastr.locations` | 277 | 826 | 281 | 298 | 0.80 | 5 |  |
| `neso_tec.projects` | 233 | 821 | 213 | 222 | 0.32 | 8 |  |
| `entsog.points` | 330 | 815 | 285 | 315 | 0.03 | 5 |  |
| `ev_eu.nl` | 375 | 806 | 220 | 395 | 3.37 | 9 |  |
| `wave10.eu_cei_gsr010` | 270 | 803 | 274 | 280 | 0.05 | 5 |  |
| `gem_ownership.gas_pipeline_ownership` | 798 | 798 | 265 | 265 | 0.76 | 2 |  |
| `connect.harmonised` | 403 | 793 | 288 | 433 | 3.66 | 9 |  |
| `rollups.wave9__de_zensus_heating_r5` | 381 | 791 | 381 | 820 | 0.03 | 6 |  |
| `wave10.wb_it_net_secr_p6` | 277 | 780 | 259 | 282 | 0.04 | 4 |  |
| `wave10.eu_env_ac_pefafp` | 466 | 779 | 214 | 770 | 0.37 | 5 |  |
| `eia860m.generators` | 588 | 746 | 286 | 287 | 2.06 | 6 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... (SELECT CO |
| `wave10.eu_nrg_stk_oom` | 560 | 744 | 292 | 775 | 1.20 | 5 |  |
| `ev_eu.cz` | 450 | 736 | 269 | 733 | 0.19 | 7 |  |
| `wave10.eu_nrg_te_oil` | 569 | 735 | 309 | 720 | 1.06 | 5 |  |
| `wave10.wb_sh_sta_odfc_zs` | 445 | 721 | 284 | 286 | 0.04 | 4 |  |
| `wave9.us_eia861m_small_solar` | 706 | 706 | 209 | 209 | 0.00 | 2 |  |
| `small_area_energy.heating` | 210 | 700 | 206 | 218 | 1.96 | 8 |  |
| `wave10.wb_en_ghg_all_lu_mt_ce_ar5` | 535 | 700 | 266 | 269 | 0.05 | 4 |  |
| `wave10.eu_env_epea_neep` | 284 | 699 | 273 | 286 | 0.04 | 5 |  |
| `ree_nodes.nodes` | 212 | 697 | 232 | 243 | 0.31 | 5 |  |
| `wave9.eu_emodnet_port_goods` | 414 | 694 | 281 | 692 | 0.55 | 7 |  |
| `mastr.catalog_values` | 216 | 692 | 211 | 221 | 0.05 | 5 |  |
| `registers.gb` | 408 | 677 | 277 | 457 | 0.80 | 8 |  |
| `wave10.wb_en_ghg_ch4_fe_mt_ce_ar5` | 297 | 676 | 278 | 297 | 0.06 | 4 |  |
| `wave9.eu_heat_production` | 422 | 676 | 296 | 375 | 0.83 | 5 |  |
| `wave9.us_cpc_degree_days` | 277 | 663 | 264 | 277 | 0.08 | 3 |  |
| `wave10.wb_sh_h2o_smdw_ru_zs` | 198 | 660 | 203 | 212 | 0.03 | 4 |  |
| `mastr.units_other` | 375 | 659 | 224 | 469 | 0.18 | 9 |  |
| `wave10.eu_nrg_ind_ebmg` | 271 | 658 | 273 | 275 | 0.01 | 5 |  |
| `wave10.eu_nrg_ti_coifpm` | 572 | 656 | 279 | 675 | 0.89 | 5 |  |
| `wave10.eu_nrg_inf_epc` | 279 | 655 | 292 | 295 | 0.11 | 5 |  |
| `wave10.eu_nrg_ind_id3cf` | 228 | 650 | 206 | 215 | 0.02 | 5 |  |
| `wave10.eu_nrg_pc_202_c` | 236 | 649 | 230 | 242 | 0.21 | 5 |  |
| `wave10.wb_eg_elc_fosl_zs` | 281 | 647 | 281 | 296 | 0.06 | 4 |  |
| `wave10.eu_cei_gsr030` | 334 | 645 | 273 | 280 | 0.01 | 5 |  |
| `mastr.grid_connection_points` | 245 | 643 | 214 | 216 | 0.79 | 5 |  |
| `entsog_tyndp.projects` | 276 | 642 | 279 | 294 | 0.03 | 4 |  |
| `wave10.wb_ag_lnd_el5m_ur_k2` | 284 | 642 | 268 | 278 | 0.02 | 4 |  |
| `wave10.wb_en_ghg_co2_ic_mt_ce_ar5` | 274 | 641 | 256 | 285 | 0.07 | 4 |  |
| `shapes.bidding_zones` | 403 | 641 | 392 | 413 | 0.07 | 5 |  |
| `wave10.wb_sh_sta_wash_p5` | 274 | 635 | 269 | 272 | 0.01 | 4 |  |
| `gem_ownership.iron_mine_ownership` | 625 | 625 | 272 | 272 | 0.22 | 2 |  |
| `afdc.stations` | 506 | 625 | 447 | 447 | 0.04 | 6 | lookup: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modu |
| `wave10.wb_ag_lnd_frst_k2` | 261 | 625 | 263 | 265 | 0.04 | 4 |  |
| `wave10.eu_nrg_stk_gasm` | 278 | 625 | 272 | 297 | 0.06 | 5 |  |
| `wave10.eu_nrg_chddr2_m` | 339 | 623 | 272 | 312 | 1.19 | 5 |  |
| `wave10.wb_is_shp_good_tu` | 267 | 621 | 270 | 274 | 0.02 | 4 |  |
| `gem.energy_ownership_iron_mine_ownership` | 210 | 619 | 208 | 213 | 0.19 | 3 | lookup: gem.energy_ownership_iron_mine_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, |
| `wave10.wb_is_rrs_good_mt_k6` | 266 | 618 | 271 | 274 | 0.02 | 4 |  |
| `osm.eu_links` | 431 | 617 | 258 | 440 | 0.23 | 8 |  |
| `wave10.wb_eg_elc_loss_zs` | 250 | 616 | 252 | 268 | 0.06 | 4 |  |
| `pse_capacity.full_substations` | 277 | 616 | 278 | 280 | 0.00 | 3 |  |
| `wave9.us_epa_lmop_landfills` | 398 | 615 | 275 | 418 | 0.21 | 8 |  |
| `co2stop.hydrocarbon_formations` | 265 | 611 | 266 | 268 | 0.03 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... COUNT(*) F |
| `connect_eu.at` | 280 | 610 | 271 | 285 | 0.00 | 3 |  |
| `wave9.us_eia_crude_pipelines` | 401 | 609 | 397 | 406 | 0.05 | 6 |  |
| `ev_eu.cy` | 408 | 608 | 278 | 419 | 0.01 | 7 |  |
| `co2stop.dic_assess_type` | 607 | 607 | 276 | 276 | 0.00 | 2 |  |
| `wave10.eu_env_ac_mfa` | 354 | 606 | 306 | 353 | 2.05 | 5 |  |
| `gem.gas_infrastructure_data` | 264 | 605 | 255 | 258 | 0.07 | 3 | lookup: gem.gas_infrastructure_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; of |
| `wave10.eu_cei_pc031` | 256 | 605 | 252 | 257 | 0.01 | 5 |  |
| `wave9.gb_neso_etys` | 422 | 604 | 279 | 449 | 0.09 | 7 |  |
| `wave10.eu_env_wat_res` | 274 | 604 | 280 | 286 | 0.04 | 5 |  |
| `ghsl.population` | 263 | 603 | 224 | 238 | 0.12 | 5 |  |
| `wave10.wb_en_ghg_n2o_ip_mt_ce_ar5` | 303 | 603 | 267 | 267 | 0.07 | 4 |  |
| `history.capareseau__substations` | 396 | 602 | 278 | 419 | 0.28 | 7 |  |
| `gem.energy_ownership_coal_plant_ownership` | 519 | 600 | 267 | 271 | 0.03 | 4 | lookup: gem.energy_ownership_coal_plant_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned |
| `registers.ie` | 404 | 600 | 410 | 432 | 0.03 | 6 |  |
| `wave10.wb_er_h2o_fwdm_zs` | 250 | 599 | 208 | 213 | 0.04 | 4 |  |
| `gem_ownership.all_entities` | 598 | 598 | 264 | 264 | 1.61 | 2 |  |
| `wave10.wb_sh_h2o_basw_ur_zs` | 267 | 598 | 283 | 284 | 0.04 | 4 |  |
| `co2stop.dic_distrib_type` | 597 | 597 | 320 | 320 | 0.00 | 2 |  |
| `wave10.eu_env_ac_epissp1` | 266 | 597 | 254 | 255 | 0.01 | 5 |  |
| `wave9.us_eia861_reliability` | 596 | 596 | 309 | 309 | 0.06 | 2 |  |
| `wave9.eu_network_costs` | 285 | 596 | 278 | 286 | 0.12 | 5 |  |
| `wave10.wb_en_ghg_n2o_pi_mt_ce_ar5` | 260 | 596 | 253 | 259 | 0.06 | 4 |  |
| `wave9.us_eia_ethanol` | 428 | 595 | 261 | 458 | 0.02 | 7 |  |
| `wave10.eu_nrg_stk_oil` | 276 | 594 | 272 | 281 | 0.10 | 5 |  |
| `wave10.wb_en_bir_thrd_no` | 320 | 593 | 274 | 278 | 0.01 | 4 |  |
| `co2stop.hydrocarbon_storage_units` | 280 | 592 | 274 | 280 | 0.09 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... COUNT(*) F |
| `wave10.wb_eg_elc_coal_zs` | 284 | 591 | 268 | 276 | 0.04 | 4 |  |
| `wave10.wb_en_ghg_co2_ag_mt_ce_ar5` | 278 | 591 | 275 | 294 | 0.05 | 4 |  |
| `wave10.wb_en_ghg_n2o_bu_mt_ce_ar5` | 234 | 591 | 211 | 212 | 0.06 | 4 |  |
| `history.registers__se` | 471 | 591 | 270 | 446 | 0.45 | 8 |  |
| `wave10.wb_er_h2o_intr_pc` | 265 | 591 | 286 | 290 | 0.06 | 4 |  |
| `wave10.wb_eg_elc_rnwx_kh` | 272 | 591 | 261 | 283 | 0.03 | 4 |  |
| `wave9.gb_dec_certificates` | 590 | 590 | 268 | 268 | 0.01 | 2 |  |
| `wave9.cz_csu_sldb_heating_energy` | 296 | 589 | 280 | 299 | 0.44 | 3 |  |
| `wave9.gr_elstat_heating_energy_regional_unit` | 283 | 589 | 280 | 284 | 0.01 | 5 |  |
| `entsoe.transmission_outages` | 259 | 588 | 260 | 267 | 0.15 | 4 | lookup: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modu |
| `ev_eu.si` | 388 | 588 | 292 | 414 | 0.04 | 7 |  |
| `gem.energy_ownership_oil_ngl_pipeline_ownership` | 206 | 588 | 210 | 243 | 0.31 | 3 | lookup: gem.energy_ownership_oil_ngl_pipeline_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be re |
| `wave10.eu_nrg_cb_gasm` | 328 | 586 | 276 | 283 | 0.33 | 5 |  |
| `wave9.eu_emodnet_wwtp` | 425 | 586 | 294 | 461 | 1.78 | 8 |  |
| `ev_eu.se` | 434 | 584 | 295 | 440 | 0.24 | 7 |  |
| `gem.gas_finance_lng_terminals` | 260 | 584 | 270 | 273 | 0.03 | 3 | lookup: gem.gas_finance_lng_terminals is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows;  |
| `wave10.wb_en_ghg_co2_lu_fl_mt_ce_ar5` | 318 | 582 | 271 | 274 | 0.04 | 4 |  |
| `wave9.eu_land_prices` | 298 | 582 | 278 | 330 | 0.04 | 5 |  |
| `wave9.eu_emodnet_platforms` | 430 | 581 | 326 | 535 | 0.14 | 8 |  |
| `gem.iron_ore_mines_prodconsmetcoalironore` | 260 | 581 | 265 | 285 | 0.01 | 3 | top10: GuardError: gem.iron_ore_mines_prodconsmetcoalironore is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may  |
| `wave10.eu_env_ac_egss3` | 554 | 581 | 266 | 268 | 0.01 | 5 |  |
| `wave10.eu_nrg_cb_pem` | 303 | 580 | 299 | 312 | 0.66 | 5 |  |
| `eia930.bas` | 271 | 580 | 277 | 288 | 0.00 | 3 |  |
| `wave10.eu_nrg_ind_rctcbt` | 300 | 580 | 273 | 292 | 0.01 | 5 |  |
| `wave10.eu_nrg_ti_gasm` | 460 | 580 | 290 | 490 | 0.54 | 5 |  |
| `wave10.wb_sh_h2o_smdw_ur_zs` | 271 | 580 | 261 | 272 | 0.03 | 4 |  |
| `wave9.us_nrel_sharing_sun` | 280 | 579 | 285 | 292 | 0.20 | 3 |  |
| `wave9.fr_enedis_interruptions` | 279 | 578 | 271 | 280 | 0.02 | 3 |  |
| `history.pse_capacity__requests` | 277 | 578 | 261 | 262 | 0.04 | 4 |  |
| `ev_eu.ee` | 370 | 576 | 238 | 386 | 0.04 | 7 |  |
| `wave10.wb_ny_adj_dmin_cd` | 376 | 576 | 273 | 279 | 0.04 | 4 |  |
| `osm.eu_buses` | 398 | 576 | 284 | 502 | 0.92 | 8 |  |
| `wave9.eu_emodnet_wind_farms` | 385 | 576 | 224 | 399 | 0.91 | 8 |  |
| `wave9.world_ourairports_runways` | 444 | 576 | 286 | 584 | 1.48 | 7 |  |
| `wave10.eu_nrg_dhdc_cpl` | 275 | 576 | 281 | 337 | 0.03 | 5 |  |
| `wave10.eu_env_ac_rme` | 318 | 576 | 274 | 281 | 0.15 | 5 |  |
| `wave10.eu_cei_srm020` | 282 | 574 | 279 | 284 | 0.12 | 5 |  |
| `wave10.wb_er_gdp_fwtl_m3_kd` | 275 | 574 | 274 | 278 | 0.06 | 4 |  |
| `wave10.wb_tm_val_mmtl_zs_un` | 288 | 574 | 275 | 291 | 0.06 | 4 |  |
| `wave9.gb_npg_opendata` | 280 | 574 | 271 | 282 | 0.01 | 4 |  |
| `wave10.eu_env_ac_taxind2` | 360 | 574 | 278 | 349 | 0.60 | 5 |  |
| `connect_eu.gb_dso` | 389 | 573 | 298 | 437 | 0.59 | 7 |  |
| `wave10.wb_sh_h2o_basw_zs` | 260 | 572 | 251 | 254 | 0.05 | 4 |  |
| `wave9.eu_water_abstraction` | 277 | 571 | 292 | 313 | 0.08 | 5 |  |
| `wave9.us_usgs_geoelectric` | 468 | 571 | 453 | 454 | 0.15 | 5 |  |
| `wave9.dk_energinet_countertrade` | 390 | 571 | 280 | 283 | 0.02 | 3 |  |
| `wave9.eu_air_passengers` | 292 | 570 | 276 | 288 | 0.06 | 5 |  |
| `wave9.eu_degree_days` | 260 | 570 | 265 | 266 | 0.21 | 5 |  |
| `history.connect_eu__at` | 344 | 570 | 286 | 300 | 0.00 | 4 |  |
| `wave10.wb_en_ghg_n2o_ag_mt_ce_ar5` | 265 | 570 | 274 | 275 | 0.07 | 4 |  |
| `wave10.eu_nrg_ind_ioc` | 271 | 570 | 275 | 279 | 0.05 | 5 |  |
| `ev_eu.hu` | 426 | 570 | 291 | 446 | 0.10 | 7 |  |
| `gem.coal_mines_change_log` | 262 | 570 | 254 | 271 | 0.01 | 3 | lookup: gem.coal_mines_change_log is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; offe |
| `wave10.wb_is_rrs_pasg_km` | 276 | 570 | 280 | 285 | 0.02 | 4 |  |
| `wave10.eu_nrg_inf_epct` | 277 | 569 | 275 | 281 | 0.02 | 5 |  |
| `wave9.eu_emodnet_military` | 427 | 569 | 416 | 632 | 2.33 | 9 |  |
| `ev_eu.lv` | 404 | 568 | 283 | 429 | 0.03 | 7 |  |
| `aures.auctions` | 288 | 568 | 278 | 282 | 0.09 | 5 |  |
| `wave9.fr_emodnet_telecom_shom` | 414 | 568 | 278 | 436 | 0.41 | 8 |  |
| `wave10.eu_env_air_emis` | 330 | 568 | 301 | 308 | 0.29 | 5 |  |
| `wave9.ro_transelectrica_zone_capacity` | 273 | 568 | 270 | 289 | 0.00 | 3 |  |
| `wave10.wb_en_ghg_n2o_mt_ce_ar5` | 280 | 568 | 272 | 280 | 0.07 | 4 |  |
| `gem_ownership.gas_plant_ownership` | 568 | 568 | 268 | 268 | 0.02 | 2 |  |
| `gem.energy_ownership_all_entities` | 274 | 567 | 266 | 276 | 1.61 | 3 | lookup: gem.energy_ownership_all_entities is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not ro |
| `wave10.wb_sh_sta_smss_zs` | 278 | 567 | 264 | 266 | 0.04 | 4 |  |
| `wave10.eu_cei_srm030` | 290 | 567 | 261 | 270 | 0.01 | 5 |  |
| `wave10.wb_er_h2o_intr_k3` | 266 | 567 | 272 | 274 | 0.01 | 4 |  |
| `wave10.eu_env_ac_pepssp1` | 292 | 566 | 270 | 273 | 0.07 | 5 |  |
| `co2stop.dic_status` | 566 | 566 | 315 | 315 | 0.00 | 2 |  |
| `wave10.eu_nrg_cb_e` | 278 | 566 | 272 | 275 | 0.12 | 5 |  |
| `wave10.eu_nrg_ind_eff` | 330 | 566 | 280 | 283 | 0.02 | 5 |  |
| `ev_eu.gb` | 417 | 566 | 297 | 467 | 0.50 | 7 |  |
| `wave10.wb_ny_adj_aedu_cd` | 286 | 565 | 272 | 277 | 0.05 | 4 |  |
| `gem.coal_terminals_terminals` | 565 | 565 | 212 | 212 | 0.04 | 2 | lookup: gem.coal_terminals_terminals is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; o |
| `wave10.wb_ny_adj_dkap_gn_zs` | 288 | 565 | 263 | 270 | 0.05 | 4 |  |
| `wave10.eu_nrg_bal_cv` | 277 | 564 | 279 | 285 | 0.26 | 5 |  |
| `wave10.eu_nrg_ind_ren` | 320 | 564 | 275 | 282 | 0.02 | 5 |  |
| `wave10.wb_eg_imp_cons_zs` | 281 | 564 | 267 | 268 | 0.05 | 4 |  |
| `wave10.wb_sp_pop_grow` | 260 | 563 | 258 | 277 | 0.08 | 4 |  |
| `connect_eu.lt` | 420 | 562 | 409 | 419 | 0.03 | 6 |  |
| `wave10.eu_env_ac_cepsgh1` | 276 | 562 | 274 | 280 | 0.02 | 5 |  |
| `wave10.wb_eg_elc_hyro_zs` | 333 | 562 | 276 | 292 | 0.06 | 4 |  |
| `wave10.eu_nrg_pc_205_v` | 273 | 562 | 257 | 269 | 0.02 | 5 |  |
| `irena.capacity` | 282 | 562 | 257 | 259 | 0.30 | 5 |  |
| `wave10.eu_nrg_ind_peh` | 301 | 562 | 279 | 318 | 0.30 | 5 |  |
| `wave10.wb_ag_lnd_totl_k2` | 284 | 561 | 285 | 293 | 0.03 | 4 |  |
| `wave10.wb_er_h2o_fwag_zs` | 312 | 561 | 249 | 258 | 0.04 | 4 |  |
| `gem.methane_emitters_pipelines` | 273 | 561 | 264 | 272 | 0.77 | 3 | lookup: gem.methane_emitters_pipelines is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; |
| `co2stop.dic_assess_traptype` | 561 | 561 | 273 | 273 | 0.00 | 2 |  |
| `wave9.us_usgs_water_use` | 281 | 561 | 270 | 298 | 0.76 | 3 |  |
| `wave10.wb_en_pop_el5m_ru_zs` | 282 | 561 | 268 | 276 | 0.02 | 4 |  |
| `ev_eu.sk` | 417 | 560 | 298 | 425 | 0.07 | 7 |  |
| `wave10.eu_cei_pc030` | 310 | 560 | 277 | 294 | 0.02 | 5 |  |
| `wave10.eu_env_ac_cepsgc1` | 322 | 560 | 269 | 300 | 0.09 | 5 |  |
| `wave9.us_nrc_operating_reactors` | 560 | 560 | 270 | 270 | 0.02 | 2 |  |
| `wave9.eu_heat_pumps` | 268 | 560 | 261 | 275 | 0.03 | 5 |  |
| `co2stop.dic_age` | 559 | 559 | 271 | 271 | 0.00 | 2 |  |
| `uk_pi.releases` | 394 | 559 | 395 | 418 | 0.38 | 5 |  |
| `wave10.wb_eg_fec_rnew_zs` | 285 | 559 | 277 | 306 | 0.03 | 4 |  |
| `wave9.us_eia_biodiesel` | 439 | 558 | 272 | 444 | 0.01 | 7 |  |
| `gem.iron_steel_basic_oxygen_furnaces` | 330 | 558 | 268 | 280 | 0.03 | 3 | lookup: gem.iron_steel_basic_oxygen_furnaces is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not |
| `wave10.eu_nrg_ind_idooil` | 275 | 558 | 263 | 272 | 0.03 | 5 |  |
| `wave10.eu_nrg_ind_pehnf` | 323 | 558 | 271 | 286 | 0.12 | 5 |  |
| `history.connect_eu__gb_dso` | 395 | 558 | 280 | 412 | 0.58 | 7 |  |
| `co2stop.dic_methods` | 558 | 558 | 295 | 295 | 0.00 | 2 |  |
| `gem.iron_steel_plant_production` | 260 | 558 | 251 | 264 | 0.03 | 3 | lookup: gem.iron_steel_plant_production is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows |
| `connect_eu.de` | 263 | 557 | 274 | 283 | 0.01 | 4 |  |
| `mastr_grid.operators` | 278 | 557 | 282 | 296 | 0.09 | 4 |  |
| `wave10.eu_nrg_ind_fechm2` | 273 | 557 | 272 | 292 | 0.01 | 5 |  |
| `gem_ownership.coal_mine_ownership` | 557 | 557 | 273 | 273 | 0.58 | 2 |  |
| `wave10.wb_en_ghg_co2_zg_ar5` | 259 | 557 | 250 | 250 | 0.07 | 4 |  |
| `wave9.gr_elstat_heating_settlement` | 304 | 557 | 283 | 284 | 0.98 | 4 |  |
| `wave10.wb_sh_sta_bass_ur_zs` | 445 | 557 | 273 | 308 | 0.04 | 4 |  |
| `co2stop.dic_availabledata` | 556 | 556 | 245 | 245 | 0.00 | 2 |  |
| `osm.datacentres` | 464 | 556 | 430 | 486 | 0.45 | 6 |  |
| `wave10.eu_nrg_te_h2` | 283 | 556 | 270 | 296 | 0.01 | 5 |  |
| `ev_eu.bg` | 396 | 556 | 276 | 443 | 0.06 | 7 |  |
| `history.connect_eu__se` | 303 | 556 | 268 | 269 | 0.01 | 5 |  |
| `wave10.wb_bx_klt_dinv_wd_gd_zs` | 268 | 556 | 264 | 268 | 0.07 | 4 |  |
| `wave10.wb_eg_cft_accs_ru_zs` | 272 | 556 | 271 | 280 | 0.03 | 4 |  |
| `wave10.wb_ny_gdp_minr_rt_zs` | 448 | 556 | 276 | 282 | 0.05 | 4 |  |
| `wave10.wb_eg_cft_accs_ur_zs` | 277 | 556 | 272 | 281 | 0.03 | 4 |  |
| `gem.energy_ownership_coal_mine_ownership` | 278 | 555 | 273 | 273 | 0.51 | 3 | lookup: gem.energy_ownership_coal_mine_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, |
| `wave10.wb_sh_sta_odfc_ur_zs` | 258 | 555 | 274 | 274 | 0.04 | 4 |  |
| `co2stop.hydrocarbon_traps` | 280 | 555 | 272 | 284 | 0.13 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... (SELECT CO |
| `wave10.eu_nrg_dhdc_c` | 279 | 555 | 273 | 278 | 0.01 | 5 |  |
| `wave10.eu_env_esst_gg` | 319 | 555 | 280 | 333 | 0.17 | 5 |  |
| `wave10.eu_nrg_pc_203_c` | 292 | 555 | 277 | 284 | 0.35 | 5 |  |
| `wave9.gb_hnpd` | 426 | 555 | 417 | 447 | 0.20 | 6 |  |
| `gem_ownership.coal_plant_ownership` | 554 | 554 | 212 | 212 | 0.02 | 2 |  |
| `wave10.wb_eg_gdp_puse_ko_pp` | 258 | 554 | 257 | 259 | 0.05 | 4 |  |
| `history.netztransparenz__redispatch` | 290 | 554 | 273 | 281 | 0.42 | 3 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `gem.iron_steel_plant_capacities_and_status` | 263 | 554 | 272 | 277 | 0.06 | 3 | lookup: gem.iron_steel_plant_capacities_and_status is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returne |
| `wave9.us_epa_agstar` | 554 | 554 | 263 | 263 | 0.03 | 2 |  |
| `gem_ownership.asset_ownership` | 554 | 554 | 279 | 279 | 0.82 | 2 |  |
| `wave10.eu_nrg_te_sff` | 403 | 554 | 272 | 473 | 0.11 | 5 |  |
| `gem.gas_infrastructure_pipelines` | 270 | 554 | 266 | 276 | 0.38 | 3 | top10: GuardError: gem.gas_infrastructure_pipelines is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be return |
| `wave9.cz_ceps_balancing` | 554 | 554 | 271 | 271 | 1.04 | 2 |  |
| `wave10.eu_nrg_cb_sffm` | 332 | 554 | 280 | 315 | 0.44 | 5 |  |
| `wave10.eu_nrg_cb_eim` | 303 | 553 | 276 | 279 | 0.09 | 5 |  |
| `wave10.eu_cei_pc020` | 287 | 553 | 276 | 276 | 0.01 | 5 |  |
| `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` | 272 | 553 | 271 | 281 | 0.04 | 4 |  |
| `eredes_capacity.substations` | 271 | 553 | 272 | 285 | 0.05 | 3 |  |
| `wave9.pt_ine_heating_freguesia` | 255 | 553 | 273 | 284 | 0.17 | 3 |  |
| `wave10.eu_env_esst_ceprw` | 308 | 553 | 282 | 286 | 0.03 | 5 |  |
| `wave10.eu_env_ac_pefa04` | 323 | 553 | 279 | 322 | 0.52 | 5 |  |
| `wave10.eu_nrg_te_eh` | 307 | 553 | 283 | 294 | 0.03 | 5 |  |
| `wave10.wb_en_ghg_n2o_wa_mt_ce_ar5` | 271 | 553 | 272 | 273 | 0.06 | 4 |  |
| `wave10.wb_ny_adj_dres_gn_zs` | 316 | 552 | 273 | 290 | 0.05 | 4 |  |
| `wave10.wb_ny_adj_aedu_gn_zs` | 269 | 552 | 254 | 262 | 0.04 | 4 |  |
| `gem.coal_mines_non_closed_mines` | 453 | 552 | 438 | 470 | 0.67 | 5 | lookup: gem.coal_mines_non_closed_mines is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows |
| `wave9.us_eia_lng` | 432 | 552 | 274 | 444 | 0.01 | 7 |  |
| `ev_eu.lu` | 401 | 552 | 289 | 416 | 0.04 | 7 |  |
| `gem.iron_steel_direct_reduced_iron_furnaces` | 269 | 552 | 261 | 270 | 0.02 | 3 | lookup: gem.iron_steel_direct_reduced_iron_furnaces is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be return |
| `wave10.eu_env_esst_cepggcp` | 336 | 552 | 282 | 369 | 0.11 | 5 |  |
| `wave10.wb_ag_lnd_totl_ru_k2` | 279 | 551 | 265 | 280 | 0.02 | 4 |  |
| `wave10.wb_it_net_user_zs` | 276 | 551 | 263 | 265 | 0.05 | 4 |  |
| `wave10.eu_nrg_dhdc_e` | 305 | 551 | 259 | 278 | 0.02 | 5 |  |
| `wave9.eu_emodnet_desalination` | 278 | 551 | 290 | 291 | 0.31 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... COUNT(*) F |
| `gem.energy_ownership_entity_ownership` | 258 | 551 | 248 | 256 | 0.90 | 3 | lookup: gem.energy_ownership_entity_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, no |
| `gem.oil_gas_extraction_field_level_production_data` | 259 | 550 | 258 | 260 | 0.21 | 3 | lookup: gem.oil_gas_extraction_field_level_production_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be |
| `gem.coal_mines_historical_production_non_chin` | 279 | 550 | 263 | 271 | 0.05 | 3 | lookup: gem.coal_mines_historical_production_non_chin is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be retu |
| `wave9.eu_ev_stock_nuts2` | 268 | 550 | 273 | 277 | 0.06 | 5 |  |
| `wave10.wb_it_net_bbnd` | 269 | 550 | 274 | 274 | 0.03 | 4 |  |
| `wave10.wb_sh_sta_hygn_ur_zs` | 265 | 550 | 266 | 267 | 0.02 | 4 |  |
| `gem.coal_mines_historical_production_non_china` | 268 | 550 | 274 | 274 | 0.06 | 3 | lookup: gem.coal_mines_historical_production_non_china is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be ret |
| `wave10.wb_si_pov_dday` | 274 | 550 | 272 | 287 | 0.02 | 4 |  |
| `gem.gas_finance_gas_power_plants` | 275 | 549 | 268 | 279 | 0.05 | 3 | lookup: gem.gas_finance_gas_power_plants is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not row |
| `wave10.eu_env_ac_epiap1` | 299 | 549 | 277 | 312 | 0.16 | 5 |  |
| `wave10.eu_nrg_chp_n` | 275 | 549 | 254 | 254 | 0.02 | 5 |  |
| `wave10.eu_nrg_ind_ei` | 283 | 549 | 258 | 265 | 0.02 | 5 |  |
| `wave10.eu_env_ac_sd` | 322 | 549 | 268 | 291 | 0.15 | 5 |  |
| `gem.iron_steel_plant_data` | 356 | 549 | 272 | 274 | 0.26 | 3 | lookup: gem.iron_steel_plant_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; offe |
| `wave10.wb_ny_gdp_totl_rt_zs` | 287 | 549 | 268 | 272 | 0.06 | 4 |  |
| `wave10.eu_nrg_ind_ffgae` | 308 | 549 | 276 | 277 | 0.01 | 5 |  |
| `wave10.eu_env_ac_epigg1` | 279 | 549 | 270 | 282 | 0.02 | 5 |  |
| `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` | 268 | 549 | 267 | 268 | 0.07 | 4 |  |
| `co2stop.hydrocarbon_traps1` | 262 | 548 | 252 | 256 | 0.06 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... (SELECT CO |
| `wave10.wb_ny_adj_nnat_cd` | 323 | 548 | 271 | 285 | 0.04 | 4 |  |
| `wave9.us_eia_product_terminals` | 411 | 548 | 271 | 429 | 0.10 | 7 |  |
| `wave10.wb_is_rrs_totl_km` | 280 | 548 | 255 | 283 | 0.02 | 4 |  |
| `ev_eu.be` | 430 | 548 | 283 | 502 | 0.35 | 7 |  |
| `wave10.wb_en_ghg_co2_lu_ol_mt_ce_ar5` | 277 | 548 | 278 | 285 | 0.03 | 4 |  |
| `wave10.wb_ny_adj_dngy_gn_zs` | 290 | 548 | 269 | 270 | 0.04 | 4 |  |
| `wave9.us_eia_product_pipelines` | 397 | 548 | 403 | 414 | 0.05 | 6 |  |
| `wave10.eu_nrg_ind_resovsh` | 268 | 548 | 249 | 257 | 0.03 | 5 |  |
| `wave10.eu_nrg_inf_bt` | 292 | 548 | 265 | 267 | 0.01 | 5 |  |
| `eaglei.coverage` | 275 | 548 | 274 | 276 | 0.01 | 4 |  |
| `wave10.eu_nrg_cb_em` | 257 | 548 | 260 | 265 | 0.17 | 5 |  |
| `wave10.wb_er_ptd_totl_zs` | 274 | 547 | 259 | 259 | 0.02 | 4 |  |
| `history.registers__pt` | 412 | 547 | 303 | 425 | 0.08 | 8 |  |
| `wave9.eu_emodnet_nuclear` | 434 | 546 | 437 | 442 | 0.02 | 6 |  |
| `wave9.us_eia_crude_rail` | 405 | 546 | 412 | 422 | 0.01 | 6 |  |
| `eaglei.counties` | 334 | 546 | 268 | 268 | 0.03 | 4 |  |
| `wave10.wb_sh_h2o_smdw_zs` | 245 | 546 | 227 | 234 | 0.04 | 4 |  |
| `wave9.eu_emodnet_hydrocarbon_licences` | 389 | 546 | 275 | 404 | 1.38 | 8 |  |
| `wave10.wb_it_mlt_main_p2` | 301 | 545 | 270 | 279 | 0.07 | 4 |  |
| `connect_eu.se` | 268 | 545 | 269 | 276 | 0.00 | 4 |  |
| `wave10.eu_env_epea_cint` | 276 | 545 | 267 | 271 | 0.08 | 5 |  |
| `registers.pt` | 426 | 545 | 276 | 434 | 0.08 | 8 |  |
| `wave9.eu_new_cars_fuel` | 310 | 545 | 270 | 283 | 0.02 | 5 |  |
| `wave9.rs_ems_connection_queue` | 288 | 545 | 271 | 288 | 0.01 | 4 |  |
| `wave10.eu_nrg_ind_fecf` | 272 | 545 | 278 | 281 | 0.09 | 5 |  |
| `wave10.eu_nrg_pc_204_v` | 270 | 545 | 274 | 276 | 0.02 | 5 |  |
| `wave10.wb_tx_val_fuel_zs_un` | 249 | 545 | 255 | 276 | 0.06 | 4 |  |
| `wave10.wb_en_ghg_ch4_zg_ar5` | 325 | 544 | 269 | 270 | 0.07 | 4 |  |
| `wave10.eu_nrg_ind_ahbtc` | 274 | 544 | 267 | 297 | 0.03 | 5 |  |
| `ev_eu.mt` | 451 | 544 | 284 | 469 | 0.01 | 7 |  |
| `history.connect_eu__lu` | 432 | 544 | 264 | 445 | 0.02 | 7 |  |
| `wave10.wb_en_pop_slum_ur_zs` | 276 | 544 | 261 | 266 | 0.03 | 4 |  |
| `edgar.ghg_by_sector` | 335 | 544 | 275 | 280 | 1.78 | 4 |  |
| `wave10.wb_en_ghg_co2_wa_mt_ce_ar5` | 319 | 544 | 280 | 285 | 0.03 | 4 |  |
| `wave9.eu_emodnet_ports` | 415 | 544 | 288 | 432 | 0.08 | 8 |  |
| `eia930.generation_by_fuel` | 238 | 544 | 247 | 252 | 0.02 | 3 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `ev_eu.dk` | 434 | 544 | 277 | 447 | 0.20 | 7 |  |
| `hotmaps.industrial_sites` | 283 | 544 | 263 | 270 | 0.31 | 3 |  |
| `wave9.gb_npg_heatmap_substations` | 392 | 544 | 392 | 401 | 0.10 | 6 |  |
| `wave9.us_blm_solar_dla` | 432 | 543 | 277 | 444 | 0.22 | 7 |  |
| `wave10.wb_eg_use_elec_kh_pc` | 275 | 543 | 270 | 281 | 0.06 | 4 |  |
| `wave9.us_eia_gas_processing` | 423 | 543 | 266 | 460 | 0.05 | 7 |  |
| `wave10.eu_env_epea_psp` | 293 | 543 | 265 | 292 | 0.05 | 5 |  |
| `history.registers__ie` | 412 | 542 | 404 | 419 | 0.03 | 6 |  |
| `wave10.wb_er_fsh_prod_mt` | 277 | 542 | 271 | 286 | 0.05 | 4 |  |
| `gem.methane_emitters_plumes` | 269 | 542 | 268 | 281 | 0.23 | 3 | lookup: gem.methane_emitters_plumes is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; of |
| `wave10.eu_nrg_inf_stcs` | 274 | 542 | 272 | 282 | 0.01 | 5 |  |
| `wave10.eu_cei_pc035` | 239 | 542 | 211 | 216 | 0.01 | 5 |  |
| `wave9.us_eia_recs_heat_pumps_state` | 542 | 542 | 257 | 257 | 0.00 | 2 |  |
| `wave10.wb_ny_adj_dco2_gn_zs` | 264 | 542 | 264 | 270 | 0.05 | 4 |  |
| `registers.fr` | 309 | 541 | 275 | 277 | 1.96 | 4 |  |
| `capareseau.substations` | 423 | 541 | 267 | 437 | 0.27 | 7 |  |
| `gem.iron_steel_blast_furnace_relinings` | 250 | 541 | 251 | 257 | 0.01 | 3 | lookup: gem.iron_steel_blast_furnace_relinings is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, n |
| `gem.oil_gas_extraction_project_level_main_data` | 449 | 541 | 428 | 439 | 0.09 | 5 | lookup: gem.oil_gas_extraction_project_level_main_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be ret |
| `wave10.wb_ip_ids_nrct` | 272 | 541 | 269 | 270 | 0.02 | 4 |  |
| `eaglei.dqi` | 280 | 541 | 275 | 292 | 0.01 | 4 |  |
| `ev_eu.it` | 329 | 540 | 216 | 341 | 0.56 | 7 |  |
| `wave10.eu_nrg_ind_hpind` | 250 | 540 | 259 | 281 | 0.01 | 5 |  |
| `gem.energy_ownership_cement_and_concrete_ownership` | 262 | 540 | 264 | 265 | 0.36 | 3 | lookup: gem.energy_ownership_cement_and_concrete_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be |
| `wave10.eu_cei_pc050` | 488 | 540 | 271 | 273 | 0.01 | 5 |  |
| `gem_ownership.bioenergy_power_ownership` | 540 | 540 | 260 | 260 | 0.73 | 2 |  |
| `wave10.wb_tm_val_fuel_zs_un` | 283 | 540 | 277 | 304 | 0.06 | 4 |  |
| `wave10.wb_ny_adj_dkap_cd` | 280 | 540 | 266 | 272 | 0.05 | 4 |  |
| `history.pse_capacity__full_substations` | 265 | 540 | 266 | 275 | 0.00 | 3 |  |
| `wave10.eu_cei_wm060` | 281 | 540 | 275 | 277 | 0.01 | 5 |  |
| `wave10.wb_er_lnd_ptld_zs` | 299 | 540 | 253 | 254 | 0.02 | 4 |  |
| `wave10.eu_nrg_inf_h2stpc` | 291 | 539 | 258 | 259 | 0.01 | 5 |  |
| `gem.oil_infrastructure_data` | 262 | 539 | 260 | 264 | 0.18 | 3 | top10: GuardError: gem.oil_infrastructure_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, n |
| `wave10.wb_nv_agr_totl_zs` | 325 | 539 | 269 | 270 | 0.07 | 4 |  |
| `history.registers__cz` | 277 | 539 | 270 | 277 | 0.77 | 6 |  |
| `wave10.eu_nrg_cb_cosm` | 286 | 539 | 273 | 280 | 0.10 | 5 |  |
| `wave10.wb_ie_ppi_icti_cd` | 302 | 539 | 269 | 284 | 0.01 | 4 |  |
| `wave10.eu_env_ac_curm` | 269 | 539 | 270 | 270 | 0.00 | 5 |  |
| `gem.iron_steel_open_hearth_furnaces` | 258 | 539 | 294 | 336 | 0.01 | 3 | lookup: gem.iron_steel_open_hearth_furnaces is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not  |
| `wave10.eu_env_ac_epneis1` | 298 | 539 | 268 | 271 | 0.01 | 5 |  |
| `wave10.eu_env_epea_invsp` | 268 | 539 | 269 | 270 | 0.01 | 5 |  |
| `wave10.wb_en_ghg_ch4_ag_mt_ce_ar5` | 265 | 539 | 263 | 267 | 0.07 | 4 |  |
| `wave10.wb_sh_sta_bass_ru_zs` | 267 | 538 | 266 | 277 | 0.04 | 4 |  |
| `wave9.gb_defra_aurn` | 430 | 538 | 430 | 436 | 0.05 | 5 |  |
| `wave10.eu_nrg_chp_f` | 278 | 538 | 276 | 296 | 0.03 | 5 |  |
| `wave10.wb_en_clc_drsk_xq` | 273 | 538 | 276 | 278 | 0.01 | 4 |  |
| `gem.energy_ownership_gas_plant_ownership` | 534 | 538 | 262 | 265 | 0.02 | 4 | lookup: gem.energy_ownership_gas_plant_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, |
| `ev_eu.fi` | 431 | 538 | 271 | 443 | 0.09 | 7 |  |
| `gem.methane_emitters_lng_terminals` | 439 | 538 | 432 | 448 | 0.10 | 5 | top10: GuardError: gem.methane_emitters_lng_terminals is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be retu |
| `gem.cement_final_data` | 257 | 538 | 251 | 266 | 0.39 | 3 | lookup: gem.cement_final_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; offendin |
| `wave10.wb_it_mlt_main` | 264 | 538 | 277 | 281 | 0.04 | 4 |  |
| `wave10.wb_eg_elc_rnwx_zs` | 314 | 537 | 271 | 286 | 0.06 | 4 |  |
| `wave10.wb_ny_gdp_frst_rt_zs` | 266 | 537 | 273 | 281 | 0.06 | 4 |  |
| `co2stop.country_totals` | 329 | 537 | 265 | 266 | 0.00 | 3 |  |
| `wave10.eu_nrg_ind_pehap` | 287 | 537 | 264 | 282 | 0.19 | 5 |  |
| `wave10.eu_env_ac_landfp` | 276 | 537 | 281 | 282 | 0.00 | 3 |  |
| `co2stop.dic_geol_basin` | 282 | 537 | 277 | 278 | 0.01 | 4 |  |
| `wave10.wb_tm_val_ictg_zs_un` | 298 | 537 | 274 | 308 | 0.04 | 4 |  |
| `wave10.wb_en_ghg_n2o_ic_mt_ce_ar5` | 266 | 537 | 268 | 273 | 0.06 | 4 |  |
| `wave10.wb_ie_ppi_tran_cd` | 267 | 537 | 253 | 256 | 0.02 | 4 |  |
| `entsoe.units` | 416 | 536 | 283 | 438 | 0.03 | 7 |  |
| `wave9.eu_broadband_nuts2` | 270 | 536 | 270 | 314 | 0.03 | 5 |  |
| `wave9.ie_semo_imbalance` | 536 | 536 | 268 | 268 | 0.01 | 2 |  |
| `wave10.wb_en_ghg_ch4_mt_ce_ar5` | 352 | 536 | 262 | 279 | 0.07 | 4 |  |
| `wave10.eu_nrg_ind_ep` | 219 | 536 | 210 | 239 | 0.01 | 5 |  |
| `ei_review.series` | 278 | 536 | 204 | 241 | 1.50 | 4 |  |
| `wave10.wb_en_ghg_co2_ip_mt_ce_ar5` | 307 | 536 | 211 | 211 | 0.07 | 4 |  |
| `wave10.wb_ie_ppn_watr_cd` | 289 | 536 | 266 | 272 | 0.01 | 4 |  |
| `wave10.eu_nrg_ind_re` | 276 | 536 | 271 | 273 | 0.11 | 5 |  |
| `wave10.eu_nrg_ind_urhcd` | 218 | 536 | 211 | 213 | 0.05 | 5 |  |
| `wave10.wb_sh_sta_pois_p5_ma` | 266 | 536 | 274 | 279 | 0.03 | 4 |  |
| `ghgrp.facilities` | 429 | 536 | 277 | 446 | 0.55 | 7 |  |
| `wave10.eu_nrg_ind_epsc` | 295 | 536 | 265 | 270 | 0.03 | 5 |  |
| `tyndp.projects` | 422 | 535 | 436 | 524 | 0.07 | 8 |  |
| `wave10.wb_ny_gdp_coal_rt_zs` | 264 | 535 | 268 | 270 | 0.04 | 4 |  |
| `entsoe.areas` | 270 | 535 | 277 | 312 | 0.00 | 4 |  |
| `wave10.wb_ny_adj_svng_gn_zs` | 273 | 535 | 272 | 275 | 0.04 | 4 |  |
| `wave9.eu_eea_wei` | 535 | 535 | 265 | 265 | 0.40 | 2 |  |
| `wave10.wb_en_atm_pm25_mc_t1_zs` | 270 | 535 | 260 | 270 | 0.02 | 4 |  |
| `wave10.wb_ag_lnd_el5m_ru_zs` | 274 | 535 | 271 | 273 | 0.02 | 4 |  |
| `wave10.wb_sh_h2o_basw_ru_zs` | 275 | 535 | 269 | 296 | 0.04 | 4 |  |
| `gem.energy_ownership_steel_plant_ownership` | 318 | 534 | 274 | 278 | 0.38 | 3 | lookup: gem.energy_ownership_steel_plant_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returne |
| `history.connect_eu__lt` | 425 | 534 | 416 | 421 | 0.03 | 6 |  |
| `wave10.wb_en_ghg_ch4_bu_mt_ce_ar5` | 280 | 534 | 278 | 280 | 0.06 | 4 |  |
| `wave10.eu_nrg_ind_difec` | 297 | 534 | 270 | 272 | 0.07 | 5 |  |
| `wave10.wb_er_h2o_fwin_zs` | 266 | 534 | 265 | 270 | 0.04 | 4 |  |
| `wave9.eu_egdi_minerals` | 216 | 534 | 215 | 219 | 1.70 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... COUNT(*) F |
| `connect_eu.bg` | 416 | 533 | 254 | 440 | 0.04 | 7 |  |
| `wave10.eu_nrg_ti_h2` | 311 | 533 | 272 | 272 | 0.01 | 5 |  |
| `wave10.wb_sp_urb_grow` | 276 | 533 | 274 | 276 | 0.08 | 4 |  |
| `wave10.wb_en_ghg_co2_tr_mt_ce_ar5` | 278 | 533 | 268 | 307 | 0.07 | 4 |  |
| `wave10.wb_it_net_bbnd_p2` | 256 | 533 | 254 | 256 | 0.05 | 4 |  |
| `gem.iron_ore_mines_main_data` | 261 | 532 | 267 | 273 | 0.10 | 3 | lookup: gem.iron_ore_mines_main_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; o |
| `wave10.wb_ny_gdp_ngas_rt_zs` | 262 | 532 | 260 | 268 | 0.04 | 4 |  |
| `wave10.wb_eg_use_comm_gd_pp_kd` | 315 | 532 | 271 | 285 | 0.05 | 4 |  |
| `wave10.eu_cei_cie011` | 254 | 532 | 255 | 257 | 0.01 | 5 |  |
| `wave10.eu_nrg_cb_rw` | 329 | 532 | 272 | 386 | 0.34 | 5 |  |
| `wave10.wb_ag_yld_crel_kg` | 272 | 532 | 266 | 272 | 0.04 | 4 |  |
| `netztransparenz.redispatch` | 261 | 532 | 267 | 267 | 0.42 | 3 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave10.eu_env_epea_invte` | 305 | 531 | 275 | 284 | 0.01 | 5 |  |
| `wave10.eu_env_ac_mfadpo` | 300 | 531 | 271 | 274 | 0.16 | 5 |  |
| `wave10.wb_ie_ppi_engy_cd` | 264 | 531 | 272 | 276 | 0.02 | 4 |  |
| `wave10.wb_en_atm_pm25_mc_zs` | 268 | 531 | 270 | 274 | 0.02 | 4 |  |
| `wave10.eu_cei_wm010` | 278 | 531 | 273 | 296 | 0.01 | 5 |  |
| `wave10.wb_er_fsh_capt_mt` | 273 | 531 | 265 | 275 | 0.05 | 4 |  |
| `wave9.eu_cleanh2_electrolyser_mfg` | 530 | 530 | 279 | 279 | 0.00 | 2 |  |
| `wave10.wb_is_air_psgr` | 266 | 530 | 264 | 265 | 0.04 | 4 |  |
| `ev_eu.lt` | 428 | 530 | 268 | 469 | 0.03 | 7 |  |
| `wave10.eu_cei_srm010` | 290 | 530 | 278 | 281 | 0.00 | 5 |  |
| `wave10.eu_nrg_stk_oem` | 270 | 530 | 269 | 275 | 0.03 | 5 |  |
| `wave9.mt_emodnet_telecom` | 414 | 530 | 254 | 426 | 0.01 | 7 |  |
| `gem.methane_emitters_coal_mines_non_closed` | 406 | 530 | 386 | 390 | 0.25 | 5 | lookup: gem.methane_emitters_coal_mines_non_closed is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returne |
| `wave10.wb_en_mam_thrd_no` | 271 | 530 | 277 | 293 | 0.01 | 4 |  |
| `wave9.ee_stat_heating_2011` | 273 | 530 | 266 | 283 | 0.06 | 4 |  |
| `wave10.eu_env_wat_pop` | 294 | 530 | 267 | 279 | 0.01 | 5 |  |
| `history.connect_eu__de` | 269 | 530 | 263 | 272 | 0.01 | 4 |  |
| `wave10.wb_eg_elc_nucl_zs` | 270 | 529 | 267 | 278 | 0.03 | 4 |  |
| `wave10.wb_sh_sta_bass_zs` | 258 | 529 | 258 | 264 | 0.05 | 4 |  |
| `wave10.wb_ag_lnd_agri_k2` | 260 | 529 | 268 | 282 | 0.04 | 4 |  |
| `wave10.wb_ny_adj_ictr_gn_zs` | 280 | 529 | 266 | 272 | 0.04 | 4 |  |
| `wave9.eu_wastewater_connected` | 283 | 529 | 274 | 278 | 0.03 | 5 |  |
| `registers.se` | 379 | 529 | 210 | 390 | 0.47 | 8 |  |
| `co2stop.dic_geocgraph_area` | 265 | 529 | 274 | 284 | 0.00 | 3 |  |
| `wave10.wb_ic_frm_outg_zs` | 260 | 529 | 266 | 268 | 0.01 | 4 |  |
| `wave10.eu_env_air_emis_ind` | 312 | 529 | 272 | 275 | 0.03 | 5 |  |
| `wave10.wb_iq_cpa_pubs_xq` | 274 | 529 | 267 | 268 | 0.02 | 4 |  |
| `wave10.eu_nrg_ind_ibmg` | 276 | 528 | 262 | 271 | 0.01 | 5 |  |
| `wave10.wb_en_ghg_co2_pc_ce_ar5` | 312 | 528 | 270 | 272 | 0.07 | 4 |  |
| `wave10.wb_ie_ppn_engy_cd` | 262 | 528 | 266 | 275 | 0.02 | 4 |  |
| `ev_eu.es` | 342 | 528 | 219 | 345 | 0.17 | 7 |  |
| `wave10.eu_env_watabs_rb` | 277 | 527 | 274 | 276 | 0.10 | 3 |  |
| `wave9.gb_epc_stats` | 527 | 527 | 261 | 261 | 0.01 | 2 |  |
| `wave10.eu_nrg_chp_cpfe` | 325 | 527 | 296 | 297 | 0.31 | 5 |  |
| `wave9.gb_ons_income_msoa` | 263 | 527 | 258 | 263 | 0.10 | 3 |  |
| `wave10.wb_er_h2o_fwtl_zs` | 264 | 527 | 282 | 285 | 0.04 | 4 |  |
| `wave10.eu_nrg_d_hhq` | 285 | 527 | 280 | 320 | 0.20 | 5 |  |
| `gem_ownership.oil___ngl_pipeline_ownership` | 526 | 526 | 249 | 249 | 0.34 | 2 |  |
| `history.connect_eu__bg` | 424 | 526 | 277 | 463 | 0.04 | 7 |  |
| `wave10.wb_eg_use_pcap_kg_oe` | 302 | 526 | 245 | 249 | 0.06 | 4 |  |
| `wave10.eu_nrg_ind_pehcf` | 354 | 526 | 230 | 377 | 0.71 | 5 |  |
| `wave10.wb_sh_dyn_mort` | 273 | 526 | 279 | 284 | 0.03 | 4 |  |
| `wave10.eu_cei_srm040` | 292 | 526 | 212 | 220 | 0.02 | 5 |  |
| `wave10.wb_eg_use_crnw_zs` | 292 | 526 | 274 | 282 | 0.05 | 4 |  |
| `wave10.wb_en_ghg_ch4_wa_mt_ce_ar5` | 282 | 526 | 267 | 274 | 0.07 | 4 |  |
| `registers.be` | 275 | 525 | 271 | 272 | 0.01 | 4 |  |
| `wave10.wb_ag_lnd_prcp_mm` | 271 | 525 | 266 | 271 | 0.01 | 4 |  |
| `wave10.wb_ag_lnd_agri_zs` | 228 | 525 | 211 | 212 | 0.06 | 4 |  |
| `wave10.wb_sh_sta_odfc_ru_zs` | 329 | 525 | 264 | 281 | 0.04 | 4 |  |
| `wave9.eu_internet_households` | 280 | 524 | 269 | 277 | 0.03 | 5 |  |
| `wave9.us_epa_lmop` | 420 | 524 | 280 | 442 | 0.07 | 7 |  |
| `wave10.wb_ip_ids_rsct` | 288 | 524 | 271 | 279 | 0.02 | 4 |  |
| `wave10.wb_sh_sta_airp_p5` | 259 | 524 | 265 | 268 | 0.01 | 4 |  |
| `wave10.eu_env_epea_pap` | 279 | 523 | 261 | 275 | 0.17 | 5 |  |
| `wave9.eu_water_use` | 285 | 523 | 256 | 266 | 0.02 | 5 |  |
| `wave10.eu_env_esst_ggcp` | 328 | 523 | 253 | 340 | 0.14 | 5 |  |
| `wave10.wb_ip_tmk_nrct` | 255 | 523 | 264 | 268 | 0.02 | 4 |  |
| `history.registers__gb` | 418 | 523 | 277 | 460 | 0.80 | 8 |  |
| `wave10.eu_env_watres_rb` | 248 | 523 | 251 | 255 | 0.08 | 3 |  |
| `ev_eu.gr` | 434 | 522 | 263 | 438 | 0.32 | 7 |  |
| `wave9.gb_npg_curtailment_events` | 522 | 522 | 264 | 264 | 0.00 | 2 |  |
| `wave10.eu_nrg_d_traq` | 340 | 522 | 284 | 289 | 0.09 | 5 |  |
| `wave10.wb_en_ghg_fgas_ip_mt_ce_ar5` | 217 | 522 | 202 | 241 | 0.06 | 4 |  |
| `wave9.fr_emodnet_telecom_sigcables` | 392 | 522 | 280 | 446 | 0.06 | 8 |  |
| `gem.iron_steel_induction_furnaces` | 209 | 522 | 208 | 230 | 0.02 | 3 | lookup: gem.iron_steel_induction_furnaces is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not ro |
| `power_plants_eu.jrc_performance` | 289 | 522 | 263 | 264 | 0.07 | 4 |  |
| `wave10.eu_nrg_pc_203_v` | 295 | 521 | 267 | 275 | 0.01 | 5 |  |
| `wave10.wb_en_clc_mdat_zs` | 256 | 521 | 254 | 270 | 0.01 | 4 |  |
| `wave10.wb_tx_val_mmtl_zs_un` | 273 | 520 | 273 | 275 | 0.06 | 4 |  |
| `ev_eu.pl` | 430 | 520 | 273 | 438 | 0.18 | 7 |  |
| `wave10.wb_ag_lnd_el5m_ru_k2` | 306 | 520 | 274 | 276 | 0.02 | 4 |  |
| `wave10.eu_nrg_ind_ured` | 273 | 520 | 267 | 269 | 0.05 | 5 |  |
| `wave10.wb_eg_elc_accs_ru_zs` | 279 | 520 | 266 | 279 | 0.03 | 4 |  |
| `wave10.wb_en_ghg_co2_pi_mt_ce_ar5` | 215 | 520 | 206 | 216 | 0.07 | 4 |  |
| `wave9.gb_desnz_subregional_fit` | 520 | 520 | 255 | 255 | 0.08 | 2 |  |
| `wave10.eu_env_air_no2` | 264 | 520 | 249 | 253 | 0.01 | 5 |  |
| `eia930.interchange` | 212 | 519 | 208 | 208 | 0.02 | 3 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave10.wb_en_ghg_co2_lu_os_mt_ce_ar5` | 284 | 519 | 265 | 276 | 0.02 | 4 |  |
| `wave9.eu_rail_electrified` | 278 | 518 | 261 | 271 | 0.01 | 5 |  |
| `wave10.wb_en_pop_el5m_ur_zs` | 254 | 518 | 246 | 250 | 0.02 | 4 |  |
| `wave9.ie_cso_datacentres` | 254 | 518 | 252 | 257 | 0.00 | 4 |  |
| `wave10.eu_env_ac_pefa05` | 268 | 517 | 257 | 259 | 0.02 | 5 |  |
| `wave9.gb_bus_heat_pumps_la` | 517 | 517 | 258 | 258 | 0.00 | 2 |  |
| `wave9.gb_pins_dco` | 380 | 517 | 384 | 394 | 0.09 | 6 |  |
| `wave10.eu_nrg_ti_eh` | 234 | 516 | 228 | 241 | 0.03 | 5 |  |
| `wave10.wb_ag_lnd_el5m_ur_zs` | 259 | 516 | 251 | 262 | 0.02 | 4 |  |
| `wave10.wb_en_hpt_thrd_no` | 266 | 516 | 265 | 265 | 0.01 | 4 |  |
| `wave10.wb_en_ghg_n2o_tr_mt_ce_ar5` | 208 | 514 | 202 | 212 | 0.07 | 4 |  |
| `power_plants_eu.jrc_units` | 388 | 512 | 382 | 413 | 0.25 | 6 |  |
| `wave10.eu_env_ac_aibrid_rd` | 277 | 512 | 257 | 270 | 0.19 | 5 |  |
| `wave10.wb_sh_sta_pois_p5` | 262 | 511 | 251 | 266 | 0.03 | 4 |  |
| `wave10.wb_ny_adj_svng_cd` | 214 | 511 | 205 | 209 | 0.04 | 4 |  |
| `wave10.eu_env_ac_mid` | 232 | 510 | 204 | 213 | 0.01 | 5 |  |
| `connect_eu.lu` | 432 | 509 | 257 | 433 | 0.02 | 7 |  |
| `wave10.wb_en_ghg_co2_bu_mt_ce_ar5` | 269 | 509 | 260 | 262 | 0.07 | 4 |  |
| `co2stop.dic_on_offshore` | 509 | 509 | 256 | 256 | 0.00 | 2 |  |
| `wave9.nl_cbs_solar` | 275 | 509 | 269 | 277 | 0.14 | 4 |  |
| `pse_capacity.requests` | 289 | 507 | 246 | 248 | 0.04 | 4 |  |
| `gem.gas_infrastructure_lng_terminals` | 393 | 507 | 379 | 383 | 0.17 | 5 | lookup: gem.gas_infrastructure_lng_terminals is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not |
| `wave10.wb_en_ghg_ch4_ic_mt_ce_ar5` | 265 | 507 | 252 | 259 | 0.06 | 4 |  |
| `wave9.fr_ore_solar_commune` | 506 | 506 | 207 | 207 | 0.02 | 2 |  |
| `wave10.eu_env_wat_bal` | 281 | 505 | 266 | 268 | 0.02 | 5 |  |
| `wave10.wb_ag_lnd_frst_zs` | 211 | 504 | 212 | 216 | 0.06 | 4 |  |
| `wave10.wb_ny_adj_dmin_gn_zs` | 263 | 504 | 255 | 258 | 0.04 | 4 |  |
| `wave10.wb_bx_gsr_ccis_zs` | 299 | 504 | 213 | 213 | 0.06 | 4 |  |
| `wave10.wb_ny_adj_nnat_gn_zs` | 247 | 502 | 250 | 258 | 0.05 | 4 |  |
| `co2stop.dic_yes_no` | 501 | 501 | 210 | 210 | 0.00 | 2 |  |
| `wave10.eu_nrg_ti_bio` | 346 | 500 | 228 | 324 | 0.09 | 5 |  |
| `econnextion.requests` | 209 | 499 | 212 | 215 | 0.01 | 5 |  |
| `gem.iron_steel_electric_arc_furnaces` | 220 | 495 | 213 | 215 | 0.06 | 3 | lookup: gem.iron_steel_electric_arc_furnaces is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not |
| `connect_eu.ee` | 340 | 495 | 215 | 342 | 0.02 | 8 |  |
| `wave10.eu_nrg_ind_cotd` | 220 | 495 | 216 | 227 | 0.04 | 5 |  |
| `history.connect_eu__dk` | 383 | 495 | 388 | 395 | 0.08 | 6 |  |
| `wave9.cz_csu_sldb_heating_mode` | 262 | 493 | 254 | 298 | 0.27 | 3 |  |
| `wave10.wb_sh_sta_hygn_zs` | 215 | 493 | 218 | 258 | 0.02 | 4 |  |
| `wave10.wb_eg_cft_accs_zs` | 267 | 492 | 254 | 264 | 0.03 | 4 |  |
| `co2stop.total_storage_cap_aquif_hcfields` | 246 | 491 | 208 | 213 | 0.01 | 3 |  |
| `wave10.eu_nrg_ind_hptctc` | 255 | 490 | 228 | 251 | 0.03 | 5 |  |
| `wave9.be_elia_balancing` | 490 | 490 | 207 | 207 | 0.04 | 2 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave10.wb_er_h2o_fwst_zs` | 217 | 490 | 212 | 213 | 0.04 | 4 |  |
| `wave10.wb_ag_lnd_arbl_zs` | 221 | 490 | 225 | 231 | 0.06 | 4 |  |
| `wave9.eu_jrc_coastal_flood` | 388 | 487 | 373 | 390 | 1.47 | 6 |  |
| `gem.iron_steel_blast_furnaces` | 206 | 487 | 204 | 216 | 0.05 | 3 | lookup: gem.iron_steel_blast_furnaces is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows;  |
| `wave10.eu_env_ac_egss1` | 310 | 487 | 261 | 309 | 0.46 | 5 |  |
| `wave9.eu_nonhousehold_prices` | 267 | 486 | 256 | 287 | 0.02 | 5 |  |
| `wave10.wb_ag_lnd_totl_ur_k2` | 272 | 484 | 255 | 257 | 0.02 | 4 |  |
| `wave10.wb_en_atm_pm25_mc_t3_zs` | 218 | 484 | 211 | 218 | 0.02 | 4 |  |
| `registers.cz` | 227 | 484 | 216 | 216 | 0.82 | 5 |  |
| `history.connect_eu__cz` | 379 | 482 | 382 | 393 | 0.01 | 6 |  |
| `wave10.wb_it_cel_sets_p2` | 209 | 482 | 212 | 214 | 0.07 | 4 |  |
| `wave10.wb_en_urb_mcty_tl_zs` | 210 | 482 | 217 | 220 | 0.05 | 4 |  |
| `wave9.de_kba_districts` | 481 | 481 | 209 | 209 | 0.04 | 2 |  |
| `connect_eu.mt` | 393 | 480 | 389 | 391 | 0.10 | 6 |  |
| `gem_ownership.entity_ownership` | 480 | 480 | 285 | 285 | 0.90 | 2 |  |
| `wave10.wb_ny_adj_svnx_cd` | 216 | 479 | 214 | 229 | 0.04 | 4 |  |
| `wave10.wb_en_ghg_ch4_tr_mt_ce_ar5` | 287 | 479 | 209 | 212 | 0.06 | 4 |  |
| `gem.integrated_power_regions_area_and_countries` | 280 | 478 | 215 | 230 | 0.02 | 3 | lookup: gem.integrated_power_regions_area_and_countries is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be re |
| `wave10.wb_ny_adj_dfor_cd` | 222 | 478 | 209 | 213 | 0.04 | 4 |  |
| `wave10.wb_eg_gdp_puse_ko_pp_kd` | 203 | 476 | 210 | 210 | 0.05 | 4 |  |
| `wave10.eu_nrg_pc_202_v` | 212 | 476 | 207 | 228 | 0.01 | 5 |  |
| `wave9.ie_eirgrid_dispatch_down` | 216 | 475 | 208 | 209 | 0.12 | 3 |  |
| `ev_eu.ie` | 366 | 474 | 219 | 398 | 0.07 | 7 |  |
| `history.registers__dk` | 385 | 474 | 213 | 395 | 0.28 | 7 |  |
| `co2stop.dic_content` | 474 | 474 | 211 | 211 | 0.00 | 2 |  |
| `wave10.wb_en_ghg_co2_rt_gdp_kd` | 224 | 473 | 208 | 209 | 0.07 | 4 |  |
| `gem.chemicals_plant_data` | 204 | 473 | 198 | 225 | 0.09 | 3 | lookup: gem.chemicals_plant_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; offen |
| `wave10.wb_en_ghg_ch4_pi_mt_ce_ar5` | 231 | 472 | 211 | 215 | 0.06 | 4 |  |
| `gem.energy_ownership_gas_pipeline_ownership` | 204 | 471 | 201 | 212 | 0.75 | 3 | lookup: gem.energy_ownership_gas_pipeline_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be return |
| `wave10.eu_env_epea_trf` | 219 | 471 | 212 | 228 | 0.03 | 5 |  |
| `wave10.eu_nrg_te_gasm` | 450 | 471 | 226 | 426 | 0.41 | 5 |  |
| `wave10.wb_en_ghg_tot_zg_ar5` | 208 | 471 | 216 | 220 | 0.07 | 4 |  |
| `co2stop.sum_output` | 205 | 470 | 210 | 220 | 0.00 | 3 |  |
| `wave9.fr_odre_balancing_volumes` | 222 | 470 | 210 | 242 | 0.01 | 3 |  |
| `entsog.operator_point_directions` | 209 | 470 | 210 | 217 | 0.11 | 3 | lookup: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modu |
| `wave9.gb_ulev_la` | 470 | 470 | 230 | 230 | 0.05 | 2 |  |
| `wave10.wb_ny_adj_dngy_cd` | 218 | 470 | 212 | 229 | 0.04 | 4 |  |
| `wave10.eu_nrg_te_gas` | 279 | 470 | 239 | 275 | 0.04 | 5 |  |
| `wave9.us_nexrad` | 376 | 470 | 380 | 386 | 0.02 | 6 |  |
| `connect_eu.dk` | 386 | 469 | 376 | 381 | 0.08 | 6 |  |
| `wave10.wb_sh_sta_smss_ur_zs` | 221 | 469 | 218 | 219 | 0.03 | 4 |  |
| `wave10.wb_se_enr_prsc_fm_zs` | 215 | 468 | 211 | 212 | 0.03 | 4 |  |
| `wave9.us_pjm_rpm` | 207 | 468 | 205 | 207 | 0.01 | 3 |  |
| `history.connect_eu__ee` | 332 | 468 | 212 | 343 | 0.02 | 8 |  |
| `history.eredes_capacity__substations` | 203 | 468 | 212 | 217 | 0.05 | 3 |  |
| `wave10.eu_nrg_ind_stjpjss` | 286 | 467 | 201 | 215 | 0.01 | 5 |  |
| `wave9.us_eia_hgl_pipelines` | 405 | 467 | 329 | 346 | 0.04 | 6 |  |
| `ev_eu.pt` | 372 | 467 | 218 | 408 | 0.40 | 7 |  |
| `wave10.wb_is_air_good_mt_k1` | 213 | 466 | 208 | 210 | 0.05 | 4 |  |
| `wave10.eu_nrg_chdd_m` | 207 | 466 | 203 | 228 | 0.05 | 5 |  |
| `wave10.eu_nrg_d_indq_n` | 451 | 466 | 231 | 411 | 0.78 | 5 |  |
| `wave10.eu_nrg_ind_psth2` | 232 | 466 | 213 | 228 | 0.01 | 5 |  |
| `wave10.wb_ag_lnd_irig_ag_zs` | 208 | 466 | 215 | 215 | 0.02 | 4 |  |
| `wave9.eu_salt_caverns` | 342 | 466 | 343 | 346 | 0.15 | 6 |  |
| `wave10.eu_env_ac_pepsgg1` | 227 | 465 | 220 | 229 | 0.08 | 5 |  |
| `wave10.wb_ny_adj_dpem_cd` | 227 | 465 | 215 | 216 | 0.05 | 4 |  |
| `wave10.eu_nrg_ti_sff` | 416 | 464 | 226 | 450 | 0.17 | 5 |  |
| `wave10.eu_nrg_d_serq_n` | 210 | 464 | 209 | 219 | 0.22 | 5 |  |
| `wave10.wb_ny_adj_dpem_gn_zs` | 210 | 463 | 210 | 211 | 0.05 | 4 |  |
| `ev_eu.hr` | 411 | 463 | 215 | 396 | 0.04 | 7 |  |
| `gem.energy_ownership_bioenergy_power_ownership` | 202 | 463 | 203 | 211 | 0.72 | 3 | lookup: gem.energy_ownership_bioenergy_power_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be ret |
| `co2stop.dgf_input` | 463 | 463 | 208 | 208 | 0.04 | 2 |  |
| `wave10.eu_nrg_dhdc_n` | 209 | 463 | 211 | 211 | 0.01 | 5 |  |
| `ev_eu.ro` | 340 | 462 | 215 | 355 | 0.05 | 7 |  |
| `wave10.wb_eg_use_comm_cl_zs` | 214 | 462 | 213 | 215 | 0.05 | 4 |  |
| `wave10.eu_nrg_ind_di` | 264 | 462 | 203 | 205 | 0.01 | 5 |  |
| `wave10.wb_is_air_dprt` | 207 | 462 | 213 | 215 | 0.03 | 4 |  |
| `tri.releases` | 462 | 462 | 215 | 215 | 0.02 | 2 |  |
| `wave10.eu_env_wat_cat` | 237 | 462 | 213 | 221 | 0.03 | 5 |  |
| `wave9.nl_cbs_datacentres` | 462 | 462 | 210 | 210 | 0.00 | 2 |  |
| `wave9.gb_nged_opendata` | 355 | 461 | 338 | 363 | 0.83 | 6 |  |
| `wave10.eu_nrg_d_cv` | 214 | 460 | 204 | 208 | 0.02 | 5 |  |
| `gem.methane_emitters_oil_and_gas_reserves` | 342 | 460 | 346 | 373 | 0.10 | 5 | lookup: gem.methane_emitters_oil_and_gas_reserves is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned |
| `wave10.wb_eg_elc_accs_ur_zs` | 210 | 460 | 214 | 217 | 0.03 | 4 |  |
| `wave10.wb_it_cel_sets` | 217 | 460 | 214 | 217 | 0.04 | 4 |  |
| `wave10.wb_ie_ppi_watr_cd` | 243 | 460 | 220 | 221 | 0.01 | 4 |  |
| `gem.methane_emitters_oil_and_gas_extraction_areas` | 382 | 459 | 381 | 392 | 0.27 | 5 | lookup: gem.methane_emitters_oil_and_gas_extraction_areas is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be  |
| `small_area_energy.renewables` | 217 | 459 | 212 | 228 | 0.52 | 6 |  |
| `history.connect_eu__mt` | 382 | 458 | 378 | 395 | 0.10 | 6 |  |
| `wave10.wb_sh_sta_hygn_ru_zs` | 217 | 458 | 211 | 219 | 0.02 | 4 |  |
| `wave9.gb_neso_tnuos` | 267 | 457 | 207 | 218 | 0.01 | 3 |  |
| `wave9.gb_ssen_opendata` | 221 | 457 | 216 | 223 | 0.19 | 4 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... COUNT(*) F |
| `wave10.eu_env_epea_invap` | 225 | 457 | 221 | 229 | 0.09 | 5 |  |
| `wave10.wb_ny_adj_dco2_cd` | 203 | 456 | 198 | 209 | 0.06 | 4 |  |
| `wave10.eu_cei_wm020` | 211 | 456 | 217 | 220 | 0.01 | 5 |  |
| `wave9.eu_nuclear_capacity` | 263 | 456 | 219 | 233 | 0.01 | 5 |  |
| `wave10.wb_en_ghg_co2_lu_df_mt_ce_ar5` | 212 | 456 | 211 | 211 | 0.03 | 4 |  |
| `gem.coal_mines_closed_mines` | 456 | 456 | 213 | 213 | 0.12 | 2 | lookup: gem.coal_mines_closed_mines is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not rows; of |
| `wave10.wb_er_fsh_aqua_mt` | 223 | 456 | 208 | 212 | 0.04 | 4 |  |
| `wave10.eu_env_epea_cfin` | 205 | 456 | 213 | 222 | 0.02 | 5 |  |
| `wave10.eu_env_ac_taxener` | 316 | 455 | 222 | 235 | 0.02 | 5 |  |
| `wave9.ie_cso_dc_consumption` | 212 | 455 | 210 | 213 | 0.01 | 4 |  |
| `lbnl_queue.requests` | 218 | 455 | 218 | 230 | 1.15 | 5 |  |
| `cenace.pml` | 219 | 455 | 214 | 219 | 0.29 | 4 |  |
| `registers.dk` | 323 | 454 | 219 | 372 | 0.29 | 7 |  |
| `wave10.wb_eg_use_comm_fo_zs` | 265 | 453 | 204 | 210 | 0.04 | 4 |  |
| `connect_eu.cz` | 382 | 453 | 384 | 400 | 0.01 | 6 |  |
| `wave10.wb_eg_elc_petr_zs` | 267 | 453 | 211 | 211 | 0.06 | 4 |  |
| `wave9.gb_dft_veh0142` | 453 | 453 | 212 | 212 | 0.02 | 2 |  |
| `wave10.eu_nrg_cb_h` | 226 | 452 | 232 | 290 | 0.07 | 5 |  |
| `wave10.wb_it_net_user_fe_zs` | 210 | 452 | 220 | 222 | 0.02 | 4 |  |
| `jepx.spot` | 226 | 452 | 223 | 224 | 0.45 | 4 |  |
| `wave10.eu_nrg_chdd_a` | 227 | 452 | 208 | 210 | 0.01 | 5 |  |
| `wave10.wb_it_net_secr` | 260 | 452 | 197 | 199 | 0.02 | 4 |  |
| `wave10.wb_en_ghg_all_pc_ce_ar5` | 244 | 452 | 223 | 227 | 0.07 | 4 |  |
| `wave10.wb_en_ghg_co2_mt_ce_ar5` | 239 | 451 | 196 | 201 | 0.07 | 4 |  |
| `wave10.eu_cei_pc032` | 210 | 451 | 204 | 220 | 0.01 | 5 |  |
| `wave10.eu_env_ac_ccminv` | 214 | 451 | 212 | 218 | 0.06 | 5 |  |
| `wave10.wb_sp_urb_totl` | 214 | 451 | 212 | 220 | 0.04 | 4 |  |
| `wave10.wb_en_ghg_n2o_fe_mt_ce_ar5` | 216 | 450 | 210 | 222 | 0.05 | 4 |  |
| `wave10.wb_er_mrn_ptmr_zs` | 205 | 450 | 213 | 219 | 0.02 | 4 |  |
| `wave10.eu_env_ac_eptrf1` | 223 | 450 | 226 | 232 | 0.05 | 5 |  |
| `co2stop.hydrocarbon_traps_temp` | 223 | 449 | 217 | 220 | 0.04 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ... COUNT(*) F |
| `wave9.de_emodnet_telecom_bsh` | 376 | 449 | 255 | 383 | 0.13 | 8 |  |
| `wave10.eu_cei_cie012` | 213 | 449 | 201 | 203 | 0.01 | 5 |  |
| `wave10.wb_ic_elc_durs` | 232 | 448 | 214 | 221 | 0.02 | 4 |  |
| `gem.coal_mines_historic_production_2018_2025` | 202 | 447 | 210 | 216 | 0.14 | 3 | lookup: gem.coal_mines_historic_production_2018_2025 is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be retur |
| `wave10.eu_env_ac_mfain` | 216 | 447 | 215 | 219 | 0.10 | 5 |  |
| `wave10.eu_nrg_inf_lbpc` | 253 | 447 | 211 | 227 | 0.01 | 5 |  |
| `wave10.eu_nrg_cb_bm` | 210 | 446 | 217 | 218 | 0.04 | 5 |  |
| `wave9.us_eia861_reliability_xlsx` | 446 | 446 | 212 | 212 | 0.06 | 2 |  |
| `wave10.wb_ny_gdp_petr_rt_zs` | 220 | 446 | 202 | 206 | 0.05 | 4 |  |
| `wave10.eu_nrg_ti_gas` | 246 | 446 | 220 | 267 | 0.08 | 5 |  |
| `wave10.eu_nrg_ind_urtd` | 216 | 446 | 214 | 225 | 0.08 | 5 |  |
| `wave10.eu_env_ac_mfabi` | 212 | 445 | 206 | 207 | 0.09 | 5 |  |
| `wave9.eu_eea_aq_stats` | 215 | 445 | 212 | 214 | 0.39 | 3 | city: BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(7,5) in BETWEEN clause - an explicit cast is required

LINE 1: ...(SELECT COU |
| `wave10.eu_env_esst_rw` | 223 | 445 | 212 | 216 | 0.03 | 5 |  |
| `wave10.wb_en_atm_pm25_mc_m3` | 222 | 445 | 213 | 262 | 0.07 | 4 |  |
| `history.registers__fr` | 223 | 445 | 216 | 220 | 1.97 | 5 |  |
| `wave10.wb_se_prm_cmpt_zs` | 242 | 444 | 211 | 225 | 0.04 | 4 |  |
| `wave10.wb_sp_urb_totl_in_zs` | 207 | 444 | 207 | 213 | 0.07 | 4 |  |
| `wave10.eu_nrg_te_bio` | 300 | 444 | 223 | 284 | 0.07 | 5 |  |
| `wave10.eu_env_ac_cur` | 270 | 444 | 207 | 207 | 0.01 | 5 |  |
| `wave9.us_eia_gas_storage` | 379 | 443 | 229 | 405 | 0.05 | 8 |  |
| `gem.oil_gas_extraction_project_level_production_data` | 210 | 443 | 208 | 214 | 0.01 | 3 | lookup: gem.oil_gas_extraction_project_level_production_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may  |
| `wave10.eu_cei_pc040` | 214 | 442 | 212 | 214 | 0.01 | 5 |  |
| `wave10.eu_cei_gsr011` | 218 | 442 | 209 | 213 | 0.01 | 5 |  |
| `wave10.eu_env_ac_rp` | 208 | 442 | 198 | 208 | 0.02 | 5 |  |
| `wave10.wb_bx_gsr_ccis_cd` | 216 | 442 | 231 | 239 | 0.05 | 4 |  |
| `wave10.wb_en_ghg_ch4_ip_mt_ce_ar5` | 203 | 442 | 207 | 211 | 0.04 | 4 |  |
| `co2stop.dic_surfissues` | 441 | 441 | 217 | 217 | 0.00 | 2 |  |
| `wave10.eu_env_ac_pepsns1` | 251 | 441 | 223 | 265 | 0.25 | 5 |  |
| `osm.cables` | 320 | 441 | 216 | 352 | 0.19 | 8 |  |
| `wave9.gb_emr_cm_register` | 273 | 441 | 217 | 217 | 0.64 | 5 |  |
| `wave10.wb_en_ghg_co2_fe_mt_ce_ar5` | 216 | 440 | 218 | 220 | 0.06 | 4 |  |
| `wave9.gb_elexon_balancing` | 440 | 440 | 212 | 212 | 0.01 | 2 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `wave10.wb_eg_egy_prim_pp_kd` | 224 | 440 | 220 | 229 | 0.04 | 4 |  |
| `wave10.wb_en_ghg_all_mt_ce_ar5` | 214 | 439 | 210 | 211 | 0.07 | 4 |  |
| `gem.energy_ownership_asset_ownership` | 206 | 438 | 215 | 216 | 0.82 | 3 | lookup: gem.energy_ownership_asset_ownership is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be returned, not |
| `wave10.eu_nrg_ind_id` | 220 | 438 | 213 | 217 | 0.04 | 5 |  |
| `wave10.eu_nrg_ind_rcaebt` | 290 | 438 | 209 | 222 | 0.01 | 5 |  |
| `wave10.eu_env_epea_invgg` | 253 | 438 | 211 | 227 | 0.01 | 5 |  |
| `wave9.world_ourairports_navaids` | 332 | 438 | 257 | 380 | 0.61 | 8 |  |
| `wave10.wb_ny_adj_dfor_gn_zs` | 221 | 438 | 210 | 213 | 0.04 | 4 |  |
| `wave10.eu_env_ac_aigg_q` | 238 | 438 | 217 | 233 | 0.12 | 5 |  |
| `wave9.fr_ademe_dpe` | 211 | 438 | 212 | 213 | 0.00 | 3 |  |
| `wave9.eu_energy_productivity` | 228 | 437 | 215 | 220 | 0.01 | 5 |  |
| `wave10.wb_eg_elc_accs_zs` | 213 | 437 | 212 | 217 | 0.03 | 4 |  |
| `wave10.eu_cei_wm011` | 213 | 437 | 215 | 220 | 0.01 | 5 |  |
| `wave10.wb_eg_elc_rnew_zs` | 214 | 437 | 210 | 214 | 0.06 | 4 |  |
| `history.econnextion__requests` | 270 | 436 | 219 | 227 | 0.01 | 5 |  |
| `wave9.si_surs_electricity_municipality` | 222 | 436 | 214 | 227 | 0.03 | 4 |  |
| `wave9.es_emodnet_telecom_cica` | 370 | 436 | 226 | 378 | 0.01 | 7 |  |
| `wave9.us_iso_as_prices` | 436 | 436 | 210 | 210 | 0.07 | 2 | lookup: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modu |
| `wave10.wb_ic_frm_bnks_zs` | 208 | 436 | 204 | 214 | 0.02 | 4 |  |
| `wave10.eu_nrg_stk_h2` | 233 | 436 | 216 | 218 | 0.01 | 5 |  |
| `wave10.eu_env_epea_pgg` | 235 | 434 | 205 | 242 | 0.05 | 5 |  |
| `co2stop.dic_geocapacity_countries` | 242 | 434 | 208 | 210 | 0.00 | 4 |  |
| `wave10.wb_sh_sta_maln_zs` | 210 | 434 | 211 | 226 | 0.02 | 4 |  |
| `wave10.wb_ny_adj_svnx_gn_zs` | 216 | 433 | 215 | 226 | 0.04 | 4 |  |
| `wave10.eu_env_wat_ind` | 215 | 433 | 201 | 212 | 0.03 | 5 |  |
| `co2stop.dic_pred_lith` | 432 | 432 | 207 | 207 | 0.00 | 2 |  |
| `irena.generation` | 218 | 432 | 210 | 210 | 0.38 | 5 |  |
| `wave10.eu_env_esst_cepgg` | 258 | 432 | 221 | 261 | 0.13 | 5 |  |
| `wave9.eu_entsoe_balancing` | 431 | 431 | 211 | 211 | 0.07 | 2 | top10: InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import, due to the following Python exception:
ModuleNotFoundError: No modul |
| `gem.oil_gas_extraction_field_level_reserves_data` | 212 | 431 | 203 | 206 | 0.14 | 3 | lookup: gem.oil_gas_extraction_field_level_reserves_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be r |
| `hydrogen.projects` | 382 | 431 | 389 | 427 | 0.03 | 6 |  |
| `wave10.wb_en_pop_el5m_zs` | 280 | 431 | 204 | 212 | 0.02 | 4 |  |
| `wave10.eu_env_ac_tax` | 215 | 430 | 217 | 220 | 0.04 | 5 |  |
| `wave10.wb_sh_sta_smss_ru_zs` | 218 | 430 | 215 | 223 | 0.03 | 4 |  |
| `wave9.gb_neso_constraint_costs` | 227 | 430 | 209 | 218 | 0.01 | 3 |  |
| `wave10.wb_tx_val_ictg_zs_un` | 219 | 430 | 219 | 220 | 0.04 | 4 |  |
| `wave9.sk_susr_energy_consumption_okres` | 212 | 430 | 207 | 208 | 0.04 | 3 |  |
| `co2stop.dic_fault_extent` | 429 | 429 | 210 | 210 | 0.00 | 2 |  |
| `wave9.us_afdc_registrations` | 429 | 429 | 213 | 213 | 0.00 | 2 |  |
| `co2stop.daughter_units_summary` | 220 | 429 | 209 | 215 | 0.00 | 3 |  |
| `wave10.wb_en_fsh_thrd_no` | 200 | 428 | 203 | 221 | 0.01 | 4 |  |
| `gem_ownership.steel_plant_ownership` | 428 | 428 | 198 | 198 | 0.38 | 2 |  |
| `wave10.eu_nrg_ind_esr` | 201 | 428 | 209 | 214 | 0.01 | 5 |  |
| `wave10.eu_nrg_cb_h2` | 224 | 428 | 207 | 209 | 0.01 | 5 |  |
| `wave10.wb_en_atm_pm25_mc_t2_zs` | 213 | 426 | 212 | 212 | 0.02 | 4 |  |
| `wave10.wb_sh_med_cmhw_p3` | 225 | 426 | 211 | 214 | 0.01 | 4 |  |
| `wave9.eu_emodnet_ocean_energy` | 368 | 426 | 219 | 375 | 0.06 | 8 |  |
| `wave10.wb_it_net_user_ma_zs` | 239 | 425 | 212 | 219 | 0.02 | 4 |  |
| `wave10.eu_cei_gsr020` | 213 | 425 | 211 | 212 | 0.01 | 5 |  |
| `wave10.wb_ag_lnd_el5m_zs` | 202 | 424 | 202 | 205 | 0.02 | 4 |  |
| `wave9.eu_renewable_capacity` | 232 | 424 | 210 | 216 | 0.04 | 5 |  |
| `wave10.eu_env_watuse_rb` | 221 | 423 | 206 | 219 | 0.04 | 3 |  |
| `wave10.eu_nrg_cb_sff` | 313 | 422 | 232 | 308 | 0.35 | 5 |  |
| `wave10.eu_nrg_ind_esc` | 217 | 422 | 228 | 233 | 0.16 | 5 |  |
| `wave10.eu_nrg_cb_gas` | 250 | 422 | 216 | 254 | 0.29 | 5 |  |
| `wave9.us_eia_refineries` | 377 | 421 | 216 | 390 | 0.02 | 8 |  |
| `history.registers__be` | 220 | 421 | 205 | 216 | 0.01 | 5 |  |
| `wave10.wb_er_h2o_fwtl_k3` | 312 | 420 | 208 | 210 | 0.04 | 4 |  |
| `wave10.wb_ip_tmk_rsct` | 244 | 420 | 199 | 213 | 0.02 | 4 |  |
| `wave10.eu_env_ac_epite1` | 218 | 419 | 208 | 209 | 0.01 | 5 |  |
| `wave9.nl_rdw_vehicles` | 419 | 419 | 210 | 210 | 0.00 | 2 |  |
| `wave10.wb_sh_sta_pois_p5_fe` | 208 | 419 | 230 | 237 | 0.03 | 4 |  |
| `wave10.wb_ie_ppn_tran_cd` | 258 | 418 | 210 | 214 | 0.02 | 4 |  |
| `wave9.eu_household_income` | 254 | 417 | 215 | 234 | 0.26 | 5 |  |
| `gem_ownership.cement_and_concrete_ownership` | 417 | 417 | 206 | 206 | 0.36 | 2 |  |
| `wave10.wb_en_ghg_n2o_zg_ar5` | 206 | 415 | 210 | 226 | 0.07 | 4 |  |
| `wave10.wb_ie_ppn_icti_cd` | 209 | 414 | 215 | 222 | 0.01 | 4 |  |
| `gem.oil_gas_extraction_project_level_reserves_data` | 211 | 413 | 212 | 215 | 0.01 | 3 | lookup: gem.oil_gas_extraction_project_level_reserves_data is licensed (Global Energy Monitor): only aggregates (sum, count, avg, ...) with GROUP BY keys may be |
| `wave9.eu_emodnet_aggregates` | 325 | 411 | 209 | 349 | 0.77 | 8 |  |
| `wave10.wb_eg_elc_ngas_zs` | 203 | 409 | 202 | 206 | 0.05 | 4 |  |
| `wave10.wb_ag_srf_totl_k2` | 204 | 407 | 202 | 217 | 0.02 | 4 |  |
| `wave10.wb_sp_pop_totl` | 228 | 406 | 196 | 205 | 0.04 | 4 |  |
| `wave10.wb_is_shp_gcnw_xq` | 220 | 402 | 200 | 216 | 0.03 | 4 |  |
| `wave10.eu_nrg_stk_gas` | 278 | 399 | 216 | 221 | 0.02 | 5 |  |
| `app.eu_plants` | 19.8 | 241 | 1.7 | 233 | 0.00 | 0 |  |
| `app.eu_substations` | 125 | 233 | 126 | 235 | 0.00 | 0 |  |
| `app.us_plants` | 21.3 | 217 | 2.4 | 220 | 0.00 | 0 |  |
| `app.eu_prices` | 2.3 | 27.5 | 1.4 | 2.1 | 0.00 | 0 |  |

## Before the tiers, second pass with the unseen benchmark (run 42454909363, hot.duckdb off)

The same lake (MaStR 2026-10-13 snapshot deleted, orphans registered) with hot.duckdb switched off and views still on globs. The 5 unanswered unseen queries are licence-guard refusals (GEM tables a user may only see aggregated), not failures. Slowest unseen: `main.outages` grouped (25 s, 243 MB: one wide unsorted file), `small_area_energy.poverty`, `wave9.at_zaehlsprengel`, `wave10.eu_env_ac_ainah_r2` (4-7 s each, whole files read).

Probed 2026-11-08T06:31:06+00:00 in the Lambda-sized container (2 vCPU, 3,008 MB) against `r2:r2://infraatlas-raw/lake/lake.duckdb`; 925 tables in 8 shards. Times in ms (cold = the first run of each query in the process; warm = the median of 3 repeats); MB and GET requests read from R2 by the cold runs of the table's query set.

#### Unseen queries (generated, no template, result cache off): 195 of 200 answered, p50 833 ms, p95 1,767 ms, max 25,361 ms

| # | table | kind | ms | rows | MB | error |
|---:|---|---|---:|---:|---:|---|
| 0 | `wave9.eu_emodnet_nuclear` | avg | 785 | 1 | 0.02 |  |
| 1 | `wave10.eu_env_ac_hfcfp` | top | 2,031 | 10 | 12.61 |  |
| 2 | `wave10.eu_env_epea_invap` | avg | 544 | 1 | 0.00 |  |
| 3 | `wave10.eu_env_ac_ainah_rd` | avg | 1,402 | 1 | 3.93 |  |
| 4 | `wave10.wb_en_ghg_fgas_ip_mt_ce_ar5` | sum | 890 | 19223820 | 0.06 |  |
| 5 | `wave10.wb_it_net_user_fe_zs` | avg | 820 | 1 | 0.02 |  |
| 6 | `pse_capacity.full_substations` | count | 485 | 69 | 0.00 |  |
| 7 | `registers.be` | top | 913 | 10 | 0.01 |  |
| 8 | `wave9.us_eia_lng` | count | 723 | 0 | 0.01 |  |
| 9 | `history.connect_eu__de` | sum | 885 | 52 | 0.00 |  |
| 10 | `wave9.gb_npg_curtailment_events` | group | 727 | 0 | 0.00 |  |
| 11 | `wave9.eu_rail_electrified` | count | 834 | 2651 | 0.01 |  |
| 12 | `gem_ownership.all_entities` | sum | 844 | 27707 | 1.61 |  |
| 13 | `wave10.wb_eg_elc_petr_zs` | group | 734 | 50 | 0.06 |  |
| 14 | `wave10.wb_en_ghg_co2_pc_ce_ar5` | group | 771 | 1 | 0.07 |  |
| 15 | `wave9.us_nexrad` | avg | 939 | 1 | 0.02 |  |
| 16 | `wave10.eu_env_ac_ainah_r2` | top | 4,958 | 10 | 33.54 |  |
| 17 | `wave10.eu_env_wat_pop` | count | 919 | 0 | 0.00 |  |
| 18 | `ev_eu.se` | sum | 904 | 1 | 0.24 |  |
| 19 | `wave9.at_zaehlsprengel` | sum | 5,422 | 682024 | 61.28 |  |
| 20 | `wave10.wb_se_enr_prsc_fm_zs` | count | 822 | 9576 | 0.03 |  |
| 21 | `wave10.eu_env_ac_epiap1` | top | 584 | 10 | 0.00 |  |
| 22 | `edgar.ghg_by_sector` | top | 824 | 10 | 1.78 |  |
| 23 | `wave10.eu_nrg_ind_difec` | top | 937 | 10 | 0.07 |  |
| 24 | `wave10.wb_sh_sta_pois_p5` | avg | 805 | 1 | 0.03 |  |
| 25 | `wave10.eu_nrg_ind_esc` | sum | 892 | 1 | 0.15 |  |
| 26 | `wave9.eu_emodnet_wind_farms` | count | 757 | 0 | 0.91 |  |
| 27 | `gem.gas_infrastructure_pipelines` | count | 808 | 16 | 0.38 |  |
| 28 | `connect_eu.dk` | avg | 812 | 1 | 0.08 |  |
| 29 | `ghsl.population` | sum | 751 | 8613475975 | 0.12 |  |
| 30 | `wave10.eu_env_ac_taxener` | sum | 750 | 1 | 0.02 |  |
| 31 | `wave10.eu_env_ac_mfain` | sum | 942 | 1 | 0.10 |  |
| 32 | `rollups.wave9__de_zensus_heating_r7` | top | 740 | 10 | 0.89 |  |
| 33 | `wave9.eu_emodnet_aggregates` | top | 894 | 0 | 0.76 |  |
| 34 | `wave10.wb_eg_cft_accs_zs` | avg | 776 | 1 | 0.03 |  |
| 35 | `entsoe.areas` | sum | 829 | 86 | 0.00 |  |
| 36 | `wave10.wb_en_ghg_n2o_ag_mt_ce_ar5` | count | 854 | 9576 | 0.06 |  |
| 37 | `wave10.wb_en_ghg_co2_rt_gdp_kd` | sum | 822 | 19223820 | 0.07 |  |
| 38 | `eia930.generation_by_fuel` | group | 1,291 | 16 | 4.01 |  |
| 39 | `wave10.wb_sh_sta_pois_p5_ma` | count | 996 | 9576 | 0.03 |  |
| 40 | `wave10.eu_cei_wm010` | group | 765 | 28 | 0.00 |  |
| 41 | `wave9.eu_emodnet_wwtp` | group | 651 | 0 | 0.00 |  |
| 42 | `wave10.eu_nrg_chdd_m` | sum | 797 | 1 | 0.05 |  |
| 43 | `shapes.admin1` | count | 1,105 | 1 | 0.00 |  |
| 44 | `ev_eu.fi` | avg | 561 | 1 | 0.00 |  |
| 45 | `wave10.wb_eg_use_comm_gd_pp_kd` | top | 800 | 10 | 0.05 |  |
| 46 | `wave10.eu_nrg_ind_rcaebt` | sum | 758 | 1 | 0.01 |  |
| 47 | `wave10.eu_nrg_ti_coifpm` | group | 1,044 | 2 | 0.89 |  |
| 48 | `wave10.wb_ny_adj_aedu_cd` | sum | 833 | 1 | 0.05 |  |
| 49 | `wave10.wb_ny_adj_dco2_gn_zs` | sum | 638 | 19223820 | 0.00 |  |
| 50 | `wave10.wb_ny_adj_aedu_gn_zs` | top | 796 | 10 | 0.04 |  |
| 51 | `wave10.wb_sh_h2o_smdw_ru_zs` | count | 835 | 9576 | 0.03 |  |
| 52 | `wave10.wb_eg_use_comm_cl_zs` | top | 816 | 10 | 0.05 |  |
| 53 | `places.cities` | avg | 973 | 1 | 0.60 |  |
| 54 | `gem.energy_ownership_asset_ownership` | group | 0.7 | None | 0.00 | GuardError: gem.energy_ownership_asset_ownership is licensed (Global Energy Moni |
| 55 | `wave10.eu_cei_gsr030` | top | 934 | 10 | 0.00 |  |
| 56 | `osm.eu_buses` | avg | 788 | 1 | 0.92 |  |
| 57 | `wave9.ie_cso_dc_consumption` | top | 909 | 10 | 0.01 |  |
| 58 | `wave9.fr_odre_balancing_volumes` | group | 866 | 0 | 0.01 |  |
| 59 | `wave10.eu_nrg_ind_fecf` | count | 862 | 20298 | 0.09 |  |
| 60 | `wave9.fr_emodnet_telecom_shom` | avg | 568 | 1 | 0.00 |  |
| 61 | `wave10.eu_cei_pc031` | sum | 865 | 1109385 | 0.00 |  |
| 62 | `wave10.wb_ic_elc_durs` | avg | 798 | 1 | 0.02 |  |
| 63 | `ev_eu.gb` | sum | 1,007 | 1 | 0.50 |  |
| 64 | `rollups.overture_transport__segments_r5` | sum | 1,723 | 49632 | 1.35 |  |
| 65 | `wave10.wb_en_pop_el5m_ur_zs` | top | 900 | 10 | 0.02 |  |
| 66 | `wave10.wb_ny_gdp_frst_rt_zs` | avg | 877 | 1 | 0.06 |  |
| 67 | `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` | count | 914 | 9576 | 0.04 |  |
| 68 | `wave9.at_zaehlsprengel` | count | 846 | 0 | 0.07 |  |
| 69 | `wave10.eu_env_epea_cfin` | sum | 810 | 1 | 0.02 |  |
| 70 | `gem.chemicals_plant_data` | group | 0.7 | None | 0.00 | GuardError: gem.chemicals_plant_data is licensed (Global Energy Monitor): only a |
| 71 | `ev_eu.bg` | top | 955 | 0 | 0.06 |  |
| 72 | `wave9.us_eia_product_pipelines` | count | 775 | 0 | 0.05 |  |
| 73 | `wave10.eu_nrg_inf_epc` | top | 906 | 10 | 0.11 |  |
| 74 | `registers.se` | group | 778 | 0 | 0.47 |  |
| 75 | `wave10.wb_sh_sta_maln_zs` | group | 582 | 1 | 0.00 |  |
| 76 | `wave10.wb_en_clc_drsk_xq` | sum | 840 | 19223820 | 0.01 |  |
| 77 | `wave10.wb_se_enr_prsc_fm_zs` | sum | 747 | 1 | 0.03 |  |
| 78 | `industrial.air_releases` | avg | 1,308 | 1 | 1.86 |  |
| 79 | `history.registers__gb` | count | 1,004 | 0 | 0.80 |  |
| 80 | `wave10.wb_sh_dyn_mort` | top | 782 | 10 | 0.03 |  |
| 81 | `wave10.wb_sh_sta_smss_zs` | sum | 957 | 1 | 0.04 |  |
| 82 | `gem.iron_steel_plant_capacities_and_status` | count | 789 | 0 | 0.06 |  |
| 83 | `wave10.eu_env_ac_pefafp` | avg | 854 | 1 | 0.37 |  |
| 84 | `wave10.wb_en_ghg_co2_tr_mt_ce_ar5` | avg | 834 | 1 | 0.07 |  |
| 85 | `wave10.wb_sh_sta_odfc_ru_zs` | group | 789 | 1 | 0.04 |  |
| 86 | `history.connect_eu__es_dso` | top | 806 | 0 | 0.13 |  |
| 87 | `wave10.eu_cei_wm010` | count | 963 | 154 | 0.00 |  |
| 88 | `wave10.eu_cei_gsr011` | sum | 735 | 992343 | 0.01 |  |
| 89 | `wave10.wb_en_ghg_ch4_zg_ar5` | count | 900 | 9576 | 0.07 |  |
| 90 | `gem.gas_infrastructure_data` | count | 848 | 23 | 0.07 |  |
| 91 | `wave10.wb_en_ghg_n2o_ip_mt_ce_ar5` | avg | 880 | 1 | 0.07 |  |
| 92 | `wave10.wb_bx_klt_dinv_wd_gd_zs` | count | 557 | 9576 | 0.00 |  |
| 93 | `wave10.eu_env_ac_pefafp` | group | 765 | 50 | 0.37 |  |
| 94 | `wave10.wb_ny_adj_dngy_cd` | sum | 762 | 1 | 0.04 |  |
| 95 | `wave10.wb_ag_lnd_totl_ru_k2` | avg | 1,022 | 1 | 0.02 |  |
| 96 | `wave10.wb_en_ghg_n2o_wa_mt_ce_ar5` | count | 785 | 9576 | 0.06 |  |
| 97 | `wave10.eu_env_esst_gg` | group | 918 | 0 | 0.17 |  |
| 98 | `history.connect_eu__es_dso` | group | 971 | 0 | 0.13 |  |
| 99 | `mastr.grid_connection_points` | sum | 863 | 11989310 | 0.53 |  |
| 100 | `rollups.wave9__de_zensus_heating_r5` | avg | 927 | 1 | 0.03 |  |
| 101 | `wave10.wb_er_h2o_fwst_zs` | top | 743 | 10 | 0.04 |  |
| 102 | `wave10.wb_ie_ppi_watr_cd` | sum | 756 | 19223820 | 0.01 |  |
| 103 | `history.esb_heatmap__transformers` | avg | 1,028 | 1 | 0.02 |  |
| 104 | `wave10.wb_ny_adj_nnat_cd` | sum | 760 | 1 | 0.04 |  |
| 105 | `wave10.wb_ag_lnd_irig_ag_zs` | count | 872 | 9576 | 0.02 |  |
| 106 | `atb.electricity` | top | 1,830 | 10 | 6.36 |  |
| 107 | `history.connect_eu__se` | avg | 877 | 1 | 0.00 |  |
| 108 | `wave10.eu_cei_srm020` | top | 825 | 10 | 0.11 |  |
| 109 | `history.esb_heatmap__transformers` | avg | 788 | 1 | 0.02 |  |
| 110 | `history.connect_eu__es_dso` | count | 497 | 0 | 0.00 |  |
| 111 | `gem.coal_mines_historic_production_2018_2025` | avg | 962 | 1 | 0.14 |  |
| 112 | `wave10.eu_nrg_chdd_a` | count | 804 | 992 | 0.01 |  |
| 113 | `wave9.us_boem_wind_leases` | avg | 941 | 1 | 0.02 |  |
| 114 | `main.outages` | group | 25,361 | 50 | 243.28 |  |
| 115 | `wave10.eu_nrg_stk_oilm` | avg | 1,235 | 1 | 3.68 |  |
| 116 | `pse_capacity.requests` | top | 818 | 886 | 0.04 |  |
| 117 | `wave9.pt_ine_heating_freguesia` | top | 799 | 10 | 0.17 |  |
| 118 | `gem_ownership.all_entities` | top | 752 | 27707 | 1.61 |  |
| 119 | `gem.energy_ownership_steel_plant_ownership` | group | 0.8 | None | 0.00 | GuardError: gem.energy_ownership_steel_plant_ownership is licensed (Global Energ |
| 120 | `entsoe.load` | top | 3,379 | 10 | 10.12 |  |
| 121 | `wave10.eu_cei_cie011` | avg | 940 | 1 | 0.01 |  |
| 122 | `wave9.de_kba_districts` | sum | 801 | 448 | 0.04 |  |
| 123 | `ev_eu.de` | avg | 834 | 1 | 0.02 |  |
| 124 | `wave10.wb_en_ghg_n2o_ip_mt_ce_ar5` | top | 842 | 10 | 0.07 |  |
| 125 | `co2stop.dic_geocapacity_countries` | top | 784 | 27 | 0.00 |  |
| 126 | `wave10.eu_env_ac_rme` | count | 488 | 24606 | 0.00 |  |
| 127 | `wave10.wb_sh_sta_hygn_zs` | top | 1,034 | 10 | 0.02 |  |
| 128 | `gem_ownership.steel_plant_ownership` | sum | 557 | 20817 | 0.00 |  |
| 129 | `wave9.eu_cleanh2_electrolyser_mfg` | sum | 931 | 11 | 0.00 |  |
| 130 | `app.data_centres` | sum | 381 | 0 | 0.00 |  |
| 131 | `wave10.eu_nrg_pc_202_v` | top | 572 | 10 | 0.00 |  |
| 132 | `wave10.wb_ie_ppi_engy_cd` | top | 826 | 10 | 0.02 |  |
| 133 | `mastr.units_other` | count | 764 | 0 | 0.11 |  |
| 134 | `ev_eu.nl` | group | 1,259 | 0 | 2.12 |  |
| 135 | `wave10.wb_sh_sta_smss_zs` | group | 917 | 50 | 0.04 |  |
| 136 | `wave10.wb_sh_h2o_smdw_ur_zs` | count | 768 | 3310 | 0.03 |  |
| 137 | `wave10.wb_tx_val_fuel_zs_un` | group | 937 | 1 | 0.06 |  |
| 138 | `caiso.curtailment` | top | 2,968 | 10 | 4.79 |  |
| 139 | `rollups.mastr__units_solar_r5` | avg | 829 | 1 | 0.13 |  |
| 140 | `wave10.eu_nrg_dhdc_c` | sum | 836 | 1700378 | 0.01 |  |
| 141 | `entsog_tyndp.projects` | top | 597 | 180 | 0.00 |  |
| 142 | `small_area_energy.poverty` | group | 6,567 | 3 | 3.70 |  |
| 143 | `history.eredes_capacity__substations` | avg | 944 | 470 | 0.05 |  |
| 144 | `registers.dk` | group | 837 | 0 | 0.29 |  |
| 145 | `ev_eu.pl` | top | 966 | 0 | 0.18 |  |
| 146 | `wave10.wb_er_gdp_fwtl_m3_kd` | group | 814 | 1 | 0.06 |  |
| 147 | `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` | top | 572 | 10 | 0.00 |  |
| 148 | `wave10.eu_env_esst_cepggcp` | sum | 531 | 1 | 0.00 |  |
| 149 | `wave10.eu_nrg_cb_sff` | group | 762 | 2 | 0.34 |  |
| 150 | `rollups.overture_power__lines_r6` | avg | 1,262 | 1 | 3.18 |  |
| 151 | `history.netztransparenz__redispatch` | count | 1,023 | 40118 | 0.42 |  |
| 152 | `connect_eu.de` | sum | 753 | 52 | 0.00 |  |
| 153 | `wave10.wb_en_ghg_n2o_bu_mt_ce_ar5` | top | 910 | 10 | 0.06 |  |
| 154 | `ev_eu.bg` | group | 787 | 0 | 0.06 |  |
| 155 | `gem.oil_gas_extraction_project_level_production_data` | group | 0.9 | None | 0.00 | GuardError: gem.oil_gas_extraction_project_level_production_data is licensed (Gl |
| 156 | `wave10.eu_env_ac_epigg1` | sum | 877 | 1 | 0.02 |  |
| 157 | `wave10.wb_ag_lnd_agri_zs` | top | 793 | 10 | 0.06 |  |
| 158 | `wave10.wb_en_ghg_ch4_ip_mt_ce_ar5` | group | 771 | 50 | 0.04 |  |
| 159 | `ev_eu.cy` | sum | 986 | 1 | 0.01 |  |
| 160 | `wave10.eu_nrg_d_serq_n` | count | 937 | 133670 | 0.22 |  |
| 161 | `ghsl.population` | group | 910 | 50 | 0.12 |  |
| 162 | `app.data_centres` | top | 379 | 0 | 0.00 |  |
| 163 | `wave10.wb_is_rrs_totl_km` | top | 799 | 10 | 0.02 |  |
| 164 | `history.connect_eu__gb_dso` | group | 814 | 0 | 0.58 |  |
| 165 | `wave10.wb_eg_egy_prim_pp_kd` | avg | 773 | 1 | 0.04 |  |
| 166 | `wave10.wb_ny_adj_aedu_cd` | avg | 492 | 1 | 0.00 |  |
| 167 | `history.registers__fr` | count | 1,010 | 141589 | 1.96 |  |
| 168 | `wave10.wb_si_pov_dday` | group | 790 | 1 | 0.02 |  |
| 169 | `protected.natura2000` | group | 1,767 | 1 | 32.43 |  |
| 170 | `esb_heatmap.transformers` | avg | 797 | 1 | 0.02 |  |
| 171 | `co2stop.dic_distrib_type` | top | 765 | 4 | 0.00 |  |
| 172 | `outlines.uk_ons` | sum | 860 | 1 | 0.13 |  |
| 173 | `wave10.eu_nrg_ind_resovsh` | sum | 900 | 1 | 0.03 |  |
| 174 | `wave10.eu_nrg_ind_re` | sum | 762 | 1 | 0.11 |  |
| 175 | `osm.eu_links` | avg | 909 | 1 | 0.11 |  |
| 176 | `connect_eu.cz` | group | 546 | 0 | 0.00 |  |
| 177 | `iso_queues.requests` | group | 2,885 | 11 | 1.67 |  |
| 178 | `wave9.gb_ea_flood_zones` | group | 2,576 | 0 | 4.10 |  |
| 179 | `co2stop.dic_pred_lith` | top | 789 | 3 | 0.00 |  |
| 180 | `wave10.eu_nrg_d_traq` | sum | 545 | 22932067 | 0.00 |  |
| 181 | `gem.energy_ownership_steel_plant_ownership` | group | 0.9 | None | 0.00 | GuardError: gem.energy_ownership_steel_plant_ownership is licensed (Global Energ |
| 182 | `wave9.de_regelleistung` | group | 1,070 | 3 | 0.03 |  |
| 183 | `wave9.eu_emodnet_wind_farms` | count | 995 | 0 | 0.91 |  |
| 184 | `gem.iron_ore_mines_main_data` | sum | 741 | 980 | 0.10 |  |
| 185 | `wave10.wb_sh_sta_bass_zs` | group | 899 | 1 | 0.05 |  |
| 186 | `wave9.fr_ore_ev_commune` | count | 742 | 773782 | 0.02 |  |
| 187 | `rollups.overture_power__sites_r7` | top | 1,483 | 10 | 8.22 |  |
| 188 | `wave9.es_emodnet_telecom_cica` | top | 838 | 0 | 0.01 |  |
| 189 | `wave10.wb_en_ghg_n2o_ag_mt_ce_ar5` | sum | 854 | 19223820 | 0.06 |  |
| 190 | `gem.iron_steel_plant_capacities_and_status` | count | 792 | 0 | 0.06 |  |
| 191 | `wave10.eu_nrg_ind_idooil` | sum | 958 | 1 | 0.03 |  |
| 192 | `wave9.eu_emodnet_aggregates` | group | 820 | 0 | 0.76 |  |
| 193 | `wave10.wb_sh_h2o_smdw_ur_zs` | top | 626 | 10 | 0.00 |  |
| 194 | `gem.iron_steel_plant_production` | avg | 798 | 1 | 0.03 |  |
| 195 | `wave10.eu_nrg_stk_oem` | group | 828 | 1 | 0.03 |  |
| 196 | `wave10.eu_cei_srm010` | sum | 844 | 234048 | 0.00 |  |
| 197 | `wave10.eu_env_esst_rw` | top | 732 | 10 | 0.03 |  |
| 198 | `gem_ownership.steel_plant_ownership` | top | 760 | 20817 | 0.38 |  |
| 199 | `history.registers__dk` | count | 980 | 0 | 0.28 |  |

#### All dataset queries

| | queries | p50 | p95 | max |
|---|---:|---:|---:|---:|
| cold | 3496 | 354 | 1,537 | 55,940 |
| warm | 3488 | 264 | 714 | 16,904 |

#### Data routes: cold p50/p95 15.1 / 3,044, warm p50/p95 14.4 / 592

| | cold | warm p50 | note |
|---|---:|---:|---|
| GET /api/health | 11.6 | 12.2 | status 200 |
| GET /api/catalog/search?q=solar%20capacity%20Germany | 1,930 | 4.2 | status 200 |
| GET /api/catalog/atb | 3.9 | 3.1 | status 200 |
| GET /api/places?q=Bavaria | 15.1 | 12.9 | status 200 |
| GET /api/places?q=Lyon | 13.2 | 14.4 | status 200 |
| GET /api/site?lon=11.58&lat=48.14&radius_km=50 | 596 | 47.7 | status 200 |
| GET /api/areas/resolve?q=Bavaria | 89.9 | 59.5 | status 200 |
| GET /api/areas/resolve?q=Berlin&level=city | 8.2 | 7.7 | status 200 |
| GET /api/shapes/admin1/DEU | 280 | 260 | status 200 |
| GET /api/quick | 8.8 | 3.2 | status 200 |
| GET /api/quick/profile?area=Germany | 31.9 | 29.7 | status 200 |
| GET /api/quick/top?area=Bavaria&n=10 | 406 | 389 | status 200 |
| GET /api/quick/totals?area=Europe | 3,044 | 46.3 | status 200 |
| GET /api/quick/published?area=France | 7.4 | 7.5 | status 200 |
| GET /api/quick/prices?area=Germany | 14.9 | 14.2 | status 200 |
| GET /api/report.json?lon=11.58&lat=48.14&radius_km=25&task=data_centre | 6.4 | 3.0 | status 422 |
| GET /api/feed/DEU.json | 4,156 | 480 | status 200 |
| POST /api/maps | 972 | 618 | status 200 |

#### quick templates: cold p50/p95 648 / 3,918, warm p50/p95 669 / 3,981

| | cold | warm p50 | note |
|---|---:|---:|---|
| profile Germany | 1,142 | 1,016 |  |
| profile Bavaria | 3,918 | 3,993 |  |
| profile Berlin | 3,834 | 2,020 |  |
| top Germany | 497 | 511 |  |
| top Bavaria | 648 | 669 |  |
| top France | 492 | 487 |  |
| totals Europe | 2,023 | 1,995 |  |
| totals United States | 498 | 492 |  |
| compare France; Germany | 1,981 | 1,996 |  |
| published Poland | 0.8 | 0.5 |  |
| prices Germany | 512 | 485 |  |

#### resolve_area: cold p50/p95 1,594 / 3,724, warm p50/p95 1,722 / 3,706

| | cold | warm p50 | note |
|---|---:|---:|---|
| Germany | 0.4 | 2,625 |  |
| France | 1,594 | 1,460 |  |
| Poland | 1,895 | 2,092 |  |
| Spain | 488 | 519 |  |
| Italy | 1,782 | 1,988 |  |
| United States | 502 | 550 |  |
| Nordics | 982 | 994 |  |
| EU-27 | 2,140 | 1,897 |  |
| Bavaria | 2,555 | 2,413 |  |
| Lower Saxony | 2,318 | 2,222 |  |
| Catalonia | 3,724 | 3,706 |  |
| Lombardy | 2,521 | 1,884 |  |
| Texas | 2,810 | 2,437 |  |
| California | 2,144 | 2,223 |  |
| Scotland | 2,955 | 2,508 |  |
| Brittany | 3,672 | 4,521 |  |
| Masovian Voivodeship | 3,800 | 2,036 |  |
| North Rhine-Westphalia | 1,775 | 2,401 |  |
| Andalusia | 2,288 | 2,106 |  |
| Upper Bavaria | 502 | 523 | not resolved |
| Harris County | 2,546 | 2,260 |  |
| Cook County | 2,041 | 2,368 |  |
| Kreis Steinfurt | 2,476 | 1,884 |  |
| Greater Manchester | 2,578 | 2,531 |  |
| Cornwall | 2,865 | 3,365 |  |
| Berlin | 1,063 | 1,089 |  |
| Paris | 1,064 | 1,019 |  |
| Madrid | 1,134 | 1,106 |  |
| Rome | 1,961 | 2,085 |  |
| Warsaw | 1,028 | 1,019 |  |
| Toulouse | 1,031 | 1,084 |  |
| Lyon | 1,114 | 1,088 |  |
| Hamburg | 1,074 | 1,043 |  |
| Munich | 1,055 | 1,087 |  |
| Vienna | 996 | 1,037 |  |
| Amsterdam | 1,039 | 1,028 |  |
| Copenhagen | 989 | 1,020 |  |
| Dublin | 1,056 | 1,071 |  |
| Lisbon | 1,200 | 1,057 |  |
| Houston | 1,056 | 1,100 |  |
| Leeds | 1,006 | 1,064 |  |
| Manchester | 1,075 | 1,278 |  |
| Kreuzberg | 1,655 | 1,700 |  |
| Schwabing | 549 | 586 | not resolved |
| Montmartre | 2,563 | 2,354 |  |
| DE-LU | 1,202 | 966 |  |
| NO2 | 15,004 | 14,103 |  |
| IT-North | 947 | 945 |  |
| Sicily | 2,114 | 2,733 |  |
| Saxony-Anhalt | 3,437 | 2,716 |  |

#### area_stats: cold p50/p95 2.9 / 57.8, warm p50/p95 2.5 / 53.6

| | cold | warm p50 | note |
|---|---:|---:|---|
| people (city) | 2.3 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| people (region) | 52.1 | 47.6 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| built_up (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| built_up (region) | 47.8 | 47.9 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| land_cover (city) | 2.6 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| land_cover (region) | 170 | 49.8 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| slope (city) | 2.9 | 2.5 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| slope (region) | 47.6 | 59.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| solar (city) | 2.7 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| solar (region) | 48.4 | 46.5 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| wind (city) | 2.3 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| wind (region) | 46.6 | 46.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| flood (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| flood (region) | 47.5 | 47.7 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| heat_demand (city) | 2.5 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| heat_demand (region) | 48.2 | 48.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_edo_cdi (city) | 2.6 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_edo_cdi (region) | 47.7 | 47.1 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_effis_danger (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_effis_danger (region) | 47.6 | 49.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_bathy (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_bathy (region) | 57.8 | 50.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_vessel_density (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_vessel_density (region) | 49.3 | 50.7 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_marinecadastre_ais (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_marinecadastre_ais (region) | 52.3 | 52.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_noaa_slr (city) | 2.7 | 2.5 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_noaa_slr (region) | 52.1 | 49.6 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_usfs_whp (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_usfs_whp (region) | 49.8 | 47.6 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_gebco (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_gebco (region) | 49.0 | 53.6 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_nex_gddp (city) | 2.6 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_nex_gddp (region) | 170 | 53.8 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |

(The per-table list of this pass is in the run artifact `query-speed-report`; the first pass above lists every table.)

## Final measurements and each miss (run 42538661868, 2026-11-09, hot.duckdb on)

Run in the Lambda-sized container with `hot.duckdb` ready in every shard (7-10 s after start:
`fast` now holds views over the 474 hot tables only and the lake answers the rest by DuckDB's
search path; a view per lake table had bound each table's Parquet files on R2 and delayed
`hot.duckdb` by 500-570 s). Warm = median of 3 repeats. Tier counts below are computed from
the shard records: a table is Tier 1 when none of its queries read bytes from R2.

| path | p50 | p95 | target | result |
|---|---:|---:|---|---|
| Tier 0, prepared `quick` answers (warm) | 2.9 ms | 543 ms (all templates) | p50 under 50 ms | met |
| Tier 1, hot tables (476 tables, 1,876 queries, warm) | 2.2 ms | 25.6 ms | p50 under 20 ms, p95 under 100 ms | met |
| Tier 2, lake, city (101 queries, warm) | 76.6 ms | 1,943 ms | p50 under 300 ms, p95 under 1 s | p50 met, p95 missed |
| Tier 2, lake, region (97 queries, warm) | 112 ms | 2,033 ms | p50 under 300 ms, p95 under 1 s | p50 met, p95 missed |
| `quick`, every template (warm) | 2.9 ms | 543 ms | p95 under 100 ms | missed |
| `resolve_area` (warm) | 11.4 ms | 96.5 ms | p95 under 100 ms | met |
| Unseen queries, 200 generated, result cache off | 301 ms | 2,157 ms | report | before the tiers: 833 / 1,767 ms |

Same unseen queries with `hot.duckdb` off (run 42540701111): p50 452 ms; per query the ratio
hot on / hot off has a median of 0.96, so `hot.duckdb` does not slow the lake queries beside it.
Between runs on different GitHub runners the same query varies by about 1.4x (an earlier run
gave p50 70.9 ms); compare within one run.

Repeat after the prepared rebuild and the new `hot.duckdb` (run 42556287354, 2026-11-09, file
ready in 6-22 s on all eight shards): Tier 1 warm 2.5 / 27.6 ms (1,876 queries), Tier 2 city
84.8 / 2,978 ms, Tier 2 region 96.8 / 2,004 ms, `quick` warm 4.0 / 715 ms, `resolve_area` warm
14.5 / 103 ms, unseen 385 / 1,973 ms (192 of 200 answered). Same misses as above; `resolve_area`
p95 sits 3 ms over the 100 ms target on this runner. The CI speed check then failed on
`shapes.nuts` (region query, `ST_Intersects` over 1,798 outlines, no R2 bytes): 303-316 ms
against a baseline of 189 ms; the CI runs before the `hot.duckdb` rebuild gave 254-265 ms with the
same code, and this probe ran slower everywhere (health route 14.5 to 24.2 ms). The cause was not
found; `data/query_speed.json` is rebaselined from this run (the current `hot.duckdb`).

Each miss:

- **`quick` p95 (543 ms):** the templates that are not prepared answers run live: `totals
  Europe` (543 ms, a sum over every country's rows), `compare France; Germany` (494 ms, two
  profiles), `prices Germany` (119 ms, the newest prices from the lake). The prepared
  templates (profile, top, totals by area) answer in 1.2-3.4 ms; Bavaria's profile 50 ms.
- **Prepared coverage (4,568 of about 9,600 areas):** the rebuild of 2026-11-09 (run
  42540733343, 16 shards) stopped at each shard's time budget: 4,568 areas and 22,840 answers
  (178 countries, 49 US states, 2,265 regions; the rest cities and smaller areas). A shard
  prepares about one area per 14 s, 757 s of that waiting for H3 cells of detailed outlines.
  Areas not prepared are answered live (Tier 1 or 2).
- **Tier 2 city and region p95 (about 2 s):** 21 of 198 lake area queries take over 1 s. Two
  causes. Whole files read on each query: `wave9.it_istat_sezioni` (407 MB a query, 7 s),
  `overture_power.lines` (213 MB, 3.8 s), `overture_power.sites` (71 MB, 3.5 s),
  `main.water_risk` and `aqueduct.baseline_annual` (100 MB, 1.8-2 s): their row groups are not
  sorted by place, so no group can be skipped; they were not among the 41 tables of the Step 4
  rewrite (chosen by bytes read in the first probe). Exact polygon tests with no bytes read:
  `wave9.cz_zsj` (8.1 s), `protected.natura2000` (2.8 s), `wave9.at_zaehlsprengel` (2.6 s),
  `grw.solar` (2.1 s): the boundary cells' rows are tested against detailed outlines on 2 CPUs.
  Next steps: add the first group to the rewrite (sort by H3 cell, `bbox` column) and keep a
  simplified-plus-exact two-step test for the polygon tables.
- **`area_stats`:** the raster measures now answer (every earlier run failed on a missing
  `libexpat` in the image). Slowest: NEX-GDDP climate (32-35 s, a global NetCDF-derived
  raster read over HTTP), land cover by region (18.5 s), people by region (10 s). `resolve_area`
  keeps the population it summed for an area, so a repeat costs nothing; the first resolve of a
  large region still reads the raster. The flood raster `lake/flood/eu_classes.tif` answers
  HTTP 404 on R2: the key is missing (to restore from the raster build).
- **Unseen queries:** 192 of 200 answered. Six refusals by the licence guard (GEM tables,
  aggregated use only); one mixed-type error in a generated filter (`wave9.gb_ssen_opendata`:
  text compared with a number, a generator case, not an engine fault); one stopped at the 60 s
  limit: a group-by over every row of `entsoe.imbalance_price` (27 MB read cold, CPU-bound on
  2 CPUs; the same query took 123 ms in a run where the file was already cached, 91 s in
  another). It needs a rollup by zone and category, or the agent's per-zone filter.

## Latest run

<!-- measured:start -->
Probed 2026-11-09T00:13:39+00:00 in the Lambda-sized container (2 vCPU, 3,008 MB) against `r2:r2://infraatlas-raw/lake/lake.duckdb`; 1081 tables in 8 shards. Times in ms (cold = the first run of each query in the process; warm = the median of 3 repeats); MB and GET requests read from R2 by the cold runs of the table's query set.

### Unseen queries (generated, no template, result cache off): 192 of 200 answered, p50 324 ms, p95 2,157 ms, max 4,604 ms

| # | table | kind | ms | rows | MB | error |
|---:|---|---|---:|---:|---:|---|
| 0 | `gem.gas_infrastructure_lng_terminals` | sum | 2,685 | 1 | 0.00 |  |
| 1 | `wave9.fr_emodnet_telecom_shom` | count | 3,151 | 0 | 0.00 |  |
| 2 | `wave10.eu_nrg_te_oilm` | sum | 1,560 | 1 | 2.92 |  |
| 3 | `wave10.wb_eg_gdp_puse_ko_pp` | top | 783 | 10 | 0.05 |  |
| 4 | `dams.barriers` | avg | 3,688 | 1 | 1.05 |  |
| 5 | `wave10.eu_road_eqs_lormot` | count | 475 | 8271 | 0.00 |  |
| 6 | `wave10.wb_is_rrs_pasg_km` | avg | 981 | 1 | 0.02 |  |
| 7 | `wave10.wb_eg_gdp_puse_ko_pp_kd` | top | 838 | 10 | 0.05 |  |
| 8 | `wave10.eu_cei_gsr020` | top | 7.7 | 10 | 0.00 |  |
| 9 | `wave10.eu_cei_srm020` | sum | 639 | 1 | 0.11 |  |
| 10 | `wave10.eu_env_ac_io10` | sum | 658 | 2383261020 | 0.03 |  |
| 11 | `mastr.catalog_values` | sum | 12.0 | 121813266 | 0.00 |  |
| 12 | `wave10.wb_eg_elc_petr_zs` | top | 426 | 10 | 0.06 |  |
| 13 | `wave10.wb_ny_adj_dngy_cd` | count | 409 | 4139 | 0.04 |  |
| 14 | `mastr.units_nuclear` | sum | 2,146 | 1 | 0.00 |  |
| 15 | `entsoe.load` | sum | 4,031 | 13336909049 | 0.22 |  |
| 16 | `gem.iron_steel_plant_capacities_and_status` | top | 0.6 | None | 0.00 | GuardError: gem.iron_steel_plant_capacities_and_status is licensed (Global Energ |
| 17 | `wave10.wb_ny_adj_dfor_gn_zs` | count | 530 | 9576 | 0.03 |  |
| 18 | `gem.coal_mines_historic_production_2018_2025` | top | 0.6 | None | 0.00 | GuardError: gem.coal_mines_historic_production_2018_2025 is licensed (Global Ene |
| 19 | `wave9.eu_broadband_nuts2` | top | 12.9 | 10 | 0.00 |  |
| 20 | `wave10.eu_ten00135` | sum | 8.0 | 6507822 | 0.00 |  |
| 21 | `wave9.gb_ssen_opendata` | avg | 1,892 | None | 0.00 | BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(6,5 |
| 22 | `entsoe.load` | avg | 3,451 | 1 | 0.22 |  |
| 23 | `rollups.overture_power__lines_r7` | top | 278 | 0 | 0.00 |  |
| 24 | `ev_eu.be` | avg | 58.0 | 1 | 0.00 |  |
| 25 | `wave10.eu_env_ac_pepssp1` | sum | 520 | 65122164 | 0.06 |  |
| 26 | `wave10.wb_er_h2o_intr_pc` | sum | 452 | 1 | 0.06 |  |
| 27 | `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` | sum | 609 | 1 | 0.06 |  |
| 28 | `wave10.eu_ten00108` | count | 6.6 | 596 | 0.00 |  |
| 29 | `wave9.be_fluvius_consumption` | top | 24.9 | 10 | 0.00 |  |
| 30 | `wave10.eu_ten00122` | group | 8.9 | 1 | 0.00 |  |
| 31 | `wave10.eu_nrg_cb_pem` | group | 778 | 1 | 0.66 |  |
| 32 | `wave10.eu_nrg_ind_eff` | sum | 443 | 1 | 0.02 |  |
| 33 | `co2stop.dic_assess_traptype` | avg | 6.9 | 2 | 0.00 |  |
| 34 | `rollups.overture_power__lines_r7` | sum | 237 | 3 | 0.00 |  |
| 35 | `wave10.eu_road_eqs_zev` | group | 597 | 43 | 0.03 |  |
| 36 | `connect_eu.gb_dso` | count | 648 | 0 | 0.58 |  |
| 37 | `wave10.eu_nrg_cb_sff` | count | 10.3 | 82711 | 0.00 |  |
| 38 | `wave10.wb_ag_lnd_agri_k2` | avg | 645 | 1 | 0.03 |  |
| 39 | `wave9.gb_he_listed` | group | 2,839 | 0 | 9.58 |  |
| 40 | `main.emissions` | group | 737 | 50 | 0.37 |  |
| 41 | `euets.verified_emissions` | sum | 841 | 1248009360 | 0.08 |  |
| 42 | `wave10.eu_sdg_12_31` | avg | 6.4 | 1 | 0.00 |  |
| 43 | `wave10.eu_env_epea_cint` | top | 594 | 10 | 0.08 |  |
| 44 | `ev_eu.pl` | group | 91.7 | 0 | 0.00 |  |
| 45 | `wave10.eu_sdg_09_10` | avg | 7.4 | 1 | 0.00 |  |
| 46 | `co2stop.dic_geocgraph_area` | sum | 7.7 | 123 | 0.00 |  |
| 47 | `mastr.units_solar` | group | 3,521 | 0 | 17.17 |  |
| 48 | `wave10.gb_desnz_ghg_dataset` | top | 1,349 | 10 | 5.51 |  |
| 49 | `wave10.eu_nrg_te_oil` | avg | 554 | 1 | 1.06 |  |
| 50 | `wave10.wb_ie_ppn_tran_cd` | sum | 431 | 19223820 | 0.01 |  |
| 51 | `wave9.us_opportunity_zones` | sum | 2,349 | 1 | 56.70 |  |
| 52 | `mastr.units_hydro` | group | 549 | 2 | 1.97 |  |
| 53 | `wave10.gb_desnz_tfec_la` | sum | 432 | 7315 | 1.79 |  |
| 54 | `eia930.generation_by_fuel` | avg | 544 | 1 | 0.02 |  |
| 55 | `wave10.eu_nrg_ind_di` | count | 6.5 | 405 | 0.00 |  |
| 56 | `wave10.eu_env_ac_epite1` | avg | 6.6 | 1 | 0.00 |  |
| 57 | `wave10.wb_tm_val_mmtl_zs_un` | count | 518 | 9576 | 0.06 |  |
| 58 | `wave10.eu_road_eqs_lorroa` | group | 6.8 | 3 | 0.00 |  |
| 59 | `euets.eea_link` | group | 685 | 0 | 0.40 |  |
| 60 | `wave9.us_usgs_nwis_sites` | avg | 1,229 | 1 | 3.49 |  |
| 61 | `wave10.eu_ten00139` | group | 8.1 | 1 | 0.00 |  |
| 62 | `gem.iron_steel_blast_furnace_relinings` | sum | 8.1 | 1 | 0.00 |  |
| 63 | `ev_eu.ee` | sum | 13.9 | 1 | 0.00 |  |
| 64 | `entsoe.imbalance_price` | group | 78,878 | None | 27.33 | TimeoutError: query stopped after 60 s |
| 65 | `wave9.us_natcarb` | avg | 1,332 | 1 | 2.28 |  |
| 66 | `wave10.eu_env_esst_ggcp` | count | 491 | 209400 | 0.14 |  |
| 67 | `wave10.wb_en_ghg_co2_pc_ce_ar5` | group | 677 | 1 | 0.07 |  |
| 68 | `wave10.wb_bx_klt_dinv_wd_gd_zs` | sum | 445 | 1 | 0.07 |  |
| 69 | `wave10.wb_it_net_user_fe_zs` | sum | 380 | 1 | 0.02 |  |
| 70 | `wave10.eu_ten00110` | group | 8.3 | 1 | 0.00 |  |
| 71 | `ev_eu.lu` | group | 65.4 | 0 | 0.00 |  |
| 72 | `wave10.wb_en_ghg_n2o_pi_mt_ce_ar5` | avg | 7.1 | 1 | 0.00 |  |
| 73 | `wave10.gb_census_cars` | count | 7.2 | 3180 | 0.00 |  |
| 74 | `wave9.us_eia_product_terminals` | group | 91.7 | 0 | 0.00 |  |
| 75 | `wave10.eu_nrg_ind_pehcf` | sum | 612 | 326180670 | 0.71 |  |
| 76 | `wave10.wb_ag_yld_crel_kg` | count | 438 | 9576 | 0.04 |  |
| 77 | `wave10.gb_desnz_elec_distribution` | sum | 8.6 | 25 | 0.00 |  |
| 78 | `wave9.us_nrc_operating_reactors` | sum | 8.0 | 93 | 0.00 |  |
| 79 | `gem.energy_ownership_cement_and_concrete_ownership` | group | 0.7 | None | 0.00 | GuardError: gem.energy_ownership_cement_and_concrete_ownership is licensed (Glob |
| 80 | `wave10.eu_rail_if_line_tr` | sum | 7.2 | 10130028 | 0.00 |  |
| 81 | `wave10.eu_env_ac_eptrf1` | count | 543 | 19520 | 0.05 |  |
| 82 | `wave10.eu_rail_eq_pa_nty` | top | 7.3 | 10 | 0.00 |  |
| 83 | `wave10.eu_road_eqs_trams` | avg | 9.6 | 1 | 0.00 |  |
| 84 | `wave10.eu_nrg_ind_pehcf` | sum | 438 | 1 | 0.71 |  |
| 85 | `wave10.gb_census_travel_distance` | sum | 375 | 14138916 | 0.03 |  |
| 86 | `wave10.wb_ny_gdp_ngas_rt_zs` | count | 550 | 9576 | 0.04 |  |
| 87 | `tyndp.projects` | count | 10.1 | 0 | 0.00 |  |
| 88 | `mastr.operators` | group | 1,104 | 2 | 0.32 |  |
| 89 | `wave10.eu_nrg_ind_psth2` | sum | 7.6 | 1 | 0.00 |  |
| 90 | `app.eu_lines` | top | 36.3 | 0 | 0.00 |  |
| 91 | `wave10.eu_nrg_cb_rw` | sum | 662 | 13934827 | 0.34 |  |
| 92 | `wave10.eu_env_watres_rb` | top | 542 | 10 | 0.07 |  |
| 93 | `wave10.wb_er_h2o_intr_pc` | group | 380 | 1 | 0.06 |  |
| 94 | `wave10.wb_eg_cft_accs_ur_zs` | sum | 579 | 11985455 | 0.02 |  |
| 95 | `co2stop.daughter_units_summary` | count | 11.5 | 21 | 0.00 |  |
| 96 | `wave10.wb_tx_val_fuel_zs_un` | sum | 7.3 | 1 | 0.00 |  |
| 97 | `wave10.wb_eg_elc_accs_ru_zs` | sum | 597 | 1 | 0.03 |  |
| 98 | `wave10.wb_ag_lnd_prcp_mm` | top | 426 | 10 | 0.01 |  |
| 99 | `wave10.eu_env_watuse_rb` | sum | 588 | 1 | 0.04 |  |
| 100 | `wave10.eu_env_epea_pap` | count | 436 | 12412 | 0.17 |  |
| 101 | `wave10.wb_sh_sta_smss_zs` | count | 8.0 | 9576 | 0.00 |  |
| 102 | `wave10.eu_nrg_cb_eim` | avg | 572 | 1 | 0.09 |  |
| 103 | `shapes.nuts` | top | 9.7 | 10 | 0.00 |  |
| 104 | `wave10.eu_road_eqs_lorton` | top | 7.4 | 10 | 0.00 |  |
| 105 | `history.connect_eu__se` | top | 11.1 | 10 | 0.00 |  |
| 106 | `wave9.us_eia_gas_processing` | sum | 15.0 | 1 | 0.00 |  |
| 107 | `gem.iron_steel_plant_production` | top | 0.7 | None | 0.00 | GuardError: gem.iron_steel_plant_production is licensed (Global Energy Monitor): |
| 108 | `wave10.eu_env_epea_pgg` | group | 540 | 1 | 0.05 |  |
| 109 | `wave10.eu_env_ac_mfain` | sum | 391 | 1 | 0.10 |  |
| 110 | `wave9.pt_ine_heating_freguesia` | sum | 555 | 1 | 0.17 |  |
| 111 | `wave9.rs_ems_connection_queue` | sum | 7.2 | 1 | 0.00 |  |
| 112 | `connect_eu.lu` | sum | 15.7 | 1 | 0.00 |  |
| 113 | `gem.gas_infrastructure_lng_terminals` | top | 0.8 | None | 0.00 | GuardError: gem.gas_infrastructure_lng_terminals is licensed (Global Energy Moni |
| 114 | `wave10.eu_env_ac_pefa05` | sum | 6.6 | 7126709 | 0.00 |  |
| 115 | `app.eu_plants` | sum | 54.9 | 1 | 0.00 |  |
| 116 | `wave9.eu_broadband_nuts2` | group | 8.4 | 2 | 0.00 |  |
| 117 | `wave10.eu_rail_eq_trset` | sum | 7.5 | 3020784 | 0.00 |  |
| 118 | `wave10.wb_eg_imp_cons_zs` | count | 583 | 9576 | 0.05 |  |
| 119 | `mastr.units_storage` | group | 574 | 2 | 0.05 |  |
| 120 | `wave10.eu_sdg_06_60` | avg | 6.2 | 1 | 0.00 |  |
| 121 | `gem.methane_emitters_lng_terminals` | avg | 35.6 | 1 | 0.00 |  |
| 122 | `wave10.eu_env_ac_pefa04` | avg | 452 | 1 | 0.52 |  |
| 123 | `history.pse_capacity__requests` | count | 8.8 | 886 | 0.00 |  |
| 124 | `wave10.wb_er_h2o_fwin_zs` | top | 442 | 10 | 0.04 |  |
| 125 | `wave9.eu_land_prices` | avg | 408 | 1 | 0.04 |  |
| 126 | `wave9.de_emodnet_telecom_bsh` | group | 13.2 | 0 | 0.00 |  |
| 127 | `wave10.eu_nrg_inf_epct` | avg | 8.2 | 1 | 0.00 |  |
| 128 | `wave9.world_ihfc_heat_flow` | avg | 1,119 | 1 | 1.20 |  |
| 129 | `wave9.eu_broadband_coverage` | group | 8.3 | 1 | 0.00 |  |
| 130 | `mastr.catalog_values` | top | 7.1 | 10 | 0.00 |  |
| 131 | `wave9.us_epa_aqs_annual` | group | 1,037 | 0 | 0.11 |  |
| 132 | `wave10.eu_env_ac_ghgfp` | top | 324 | 10 | 1.31 |  |
| 133 | `connect_eu.bg` | top | 50.8 | 0 | 0.00 |  |
| 134 | `wave10.eu_nrg_ind_esr` | sum | 7.9 | 816885 | 0.00 |  |
| 135 | `pse_capacity.requests` | sum | 6.9 | 886 | 0.00 |  |
| 136 | `ev_eu.de` | count | 87.1 | 6504 | 0.00 |  |
| 137 | `euets.verified_emissions` | sum | 9.8 | 1248009360 | 0.00 |  |
| 138 | `neso.constraint_breakdown` | top | 4,310 | 10 | 0.32 |  |
| 139 | `wave9.dk_district_heating` | count | 10.8 | 0 | 0.00 |  |
| 140 | `wave10.eu_rail_eq_locop` | avg | 7.8 | 1 | 0.00 |  |
| 141 | `wave10.eu_env_ac_cepsgc1` | group | 9.8 | 12 | 0.00 |  |
| 142 | `wave10.wb_en_ghg_all_pc_ce_ar5` | sum | 539 | 1 | 0.07 |  |
| 143 | `wave9.us_openei_urdb` | top | 910 | 58920 | 0.13 |  |
| 144 | `gem.methane_emitters_pipelines` | avg | 6.7 | 1 | 0.00 |  |
| 145 | `history.pse_capacity__full_substations` | group | 9.0 | 50 | 0.00 |  |
| 146 | `history.connect_eu__gb_dso` | sum | 578 | 1 | 0.58 |  |
| 147 | `gem.methane_emitters_lng_terminals` | count | 66.3 | 0 | 0.00 |  |
| 148 | `wave10.eu_env_ac_ghgfp` | sum | 724 | 1 | 15.27 |  |
| 149 | `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` | count | 431 | 9576 | 0.04 |  |
| 150 | `wave9.eur_overture_comm_lines` | sum | 13.1 | 58 | 0.00 |  |
| 151 | `wave10.wb_it_net_user_ma_zs` | sum | 646 | 3146898 | 0.02 |  |
| 152 | `entsog.points` | group | 7.3 | 3 | 0.00 |  |
| 153 | `wave10.eu_env_epea_pgg` | sum | 9.4 | 35089415 | 0.00 |  |
| 154 | `wave10.wb_eg_imp_cons_zs` | sum | 7.3 | 1 | 0.00 |  |
| 155 | `gem.oil_gas_extraction_field_level_main_data` | top | 0.8 | None | 0.00 | GuardError: gem.oil_gas_extraction_field_level_main_data is licensed (Global Ene |
| 156 | `connect_eu.ee` | count | 19.5 | 0 | 0.00 |  |
| 157 | `wave10.eu_nrg_ind_ioc` | group | 9.2 | 43 | 0.00 |  |
| 158 | `wave10.eu_sdg_13_70a` | top | 8.6 | 10 | 0.00 |  |
| 159 | `wave10.eu_sdg_09_60` | avg | 7.2 | 1 | 0.00 |  |
| 160 | `co2stop.dic_on_offshore` | avg | 8.3 | 3 | 0.00 |  |
| 161 | `wave10.eu_nrg_pc_203_c` | sum | 8.6 | 192495588 | 0.00 |  |
| 162 | `entsog.operator_point_directions` | sum | 7.2 | 1 | 0.00 |  |
| 163 | `wave9.us_nexrad` | avg | 49.2 | 1 | 0.00 |  |
| 164 | `history.registers__ie` | sum | 50.1 | 1 | 0.00 |  |
| 165 | `registers.pt` | count | 76.1 | 0 | 0.00 |  |
| 166 | `wave9.us_usgs_nshm` | count | 998 | 0 | 9.83 |  |
| 167 | `rollups.wave9__de_zensus_heating_r5` | sum | 51.3 | 3487 | 0.00 |  |
| 168 | `ev_eu.pt` | top | 40.9 | 0 | 0.00 |  |
| 169 | `wave10.eu_rail_eq_vans` | avg | 7.4 | 1 | 0.00 |  |
| 170 | `wave10.wb_ag_lnd_totl_ur_k2` | sum | 415 | 19223820 | 0.02 |  |
| 171 | `wave9.gb_ne_alc` | avg | 56.4 | 1 | 0.00 |  |
| 172 | `wave10.eu_cei_pc030` | sum | 8.5 | 3272322 | 0.00 |  |
| 173 | `wave9.us_noaa_mpa` | avg | 762 | 1 | 0.16 |  |
| 174 | `wave10.eu_road_eqs_roaene` | count | 7.8 | 4555 | 0.00 |  |
| 175 | `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` | group | 646 | 50 | 0.06 |  |
| 176 | `wave9.si_surs_heating_settlement` | avg | 446 | 1 | 0.66 |  |
| 177 | `outlines.fr_iris` | avg | 1,903 | 1 | 75.18 |  |
| 178 | `wave10.eu_cei_pc034` | count | 6.1 | 298 | 0.00 |  |
| 179 | `wave10.wb_ag_lnd_frst_zs` | sum | 7.3 | 19223820 | 0.00 |  |
| 180 | `wave10.wb_ny_adj_dco2_cd` | top | 426 | 10 | 0.06 |  |
| 181 | `wave10.eu_env_ac_pefafp` | top | 385 | 10 | 0.37 |  |
| 182 | `wave10.wb_ny_adj_svng_gn_zs` | sum | 572 | 19223820 | 0.04 |  |
| 183 | `outlines.us_places` | group | 2,157 | 1 | 15.50 |  |
| 184 | `wave10.eu_env_ac_ghgfp` | sum | 1,625 | 1 | 38.27 |  |
| 185 | `wave10.eu_cei_pc020` | avg | 7.8 | 1 | 0.00 |  |
| 186 | `wave10.eu_ten00108` | avg | 6.6 | 1 | 0.00 |  |
| 187 | `wave10.wb_en_ghg_ch4_bu_mt_ce_ar5` | avg | 630 | 1 | 0.06 |  |
| 188 | `wave10.wb_en_pop_slum_ur_zs` | count | 441 | 9576 | 0.02 |  |
| 189 | `wave10.eu_sdg_07_30` | top | 8.1 | 0 | 0.00 |  |
| 190 | `wave10.wb_en_fsh_thrd_no` | count | 722 | 9576 | 0.01 |  |
| 191 | `main.grid_capacity` | group | 4,604 | 50 | 1.89 |  |
| 192 | `wave10.eu_ten00030` | top | 10.1 | 10 | 0.00 |  |
| 193 | `wave10.eu_sdg_06_70` | top | 8.8 | 10 | 0.00 |  |
| 194 | `eia930.interchange` | group | 821 | 1 | 3.83 |  |
| 195 | `ev_eu.pl` | group | 42.4 | 0 | 0.00 |  |
| 196 | `wave9.gb_emr_cm_register` | group | 577 | 17 | 0.64 |  |
| 197 | `ree_nodes.nodes` | avg | 8.6 | 2814 | 0.00 |  |
| 198 | `wave10.eu_rail_eq_wagon` | group | 9.9 | 37 | 0.00 |  |
| 199 | `mastr.operators` | group | 1,438 | 50 | 0.32 |  |

### All dataset queries

| | queries | p50 | p95 | max |
|---|---:|---:|---:|---:|
| cold | 4078 | 4.3 | 853 | 55,684 |
| warm | 4063 | 2.7 | 164 | 18,689 |

### Data routes: cold p50/p95 12.6 / 1,685, warm p50/p95 10.0 / 766

| | cold | warm p50 | note |
|---|---:|---:|---|
| GET /api/health | 5.4 | 9.1 | status 200 |
| GET /api/catalog/search?q=solar%20capacity%20Germany | 1,388 | 3.0 | status 200 |
| GET /api/catalog/atb | 2.7 | 2.0 | status 200 |
| GET /api/places?q=Bavaria | 11.9 | 10.0 | status 200 |
| GET /api/places?q=Lyon | 9.8 | 10.0 | status 200 |
| GET /api/site?lon=11.58&lat=48.14&radius_km=50 | 230 | 36.7 | status 200 |
| GET /api/areas/resolve?q=Bavaria | 87.0 | 48.5 | status 200 |
| GET /api/areas/resolve?q=Berlin&level=city | 6.8 | 5.8 | status 200 |
| GET /api/shapes/admin1/DEU | 293 | 296 | status 200 |
| GET /api/quick | 6.7 | 2.1 | status 200 |
| GET /api/quick/profile?area=Germany | 12.6 | 8.0 | status 200 |
| GET /api/quick/top?area=Bavaria&n=10 | 50.9 | 48.8 | status 200 |
| GET /api/quick/totals?area=Europe | 1,685 | 70.4 | status 200 |
| GET /api/quick/published?area=France | 9.5 | 7.2 | status 200 |
| GET /api/quick/prices?area=Germany | 12.9 | 14.3 | status 200 |
| GET /api/report.json?lon=11.58&lat=48.14&radius_km=25&task=data_centre | 4.9 | 2.2 | status 422 |
| GET /api/feed/DEU.json | 4,641 | 802 | status 200 |
| POST /api/maps | 592 | 636 | status 200 |

### quick templates: cold p50/p95 42.4 / 1,732, warm p50/p95 2.9 / 543

| | cold | warm p50 | note |
|---|---:|---:|---|
| profile Germany | 3.0 | 1.4 | prepared (Tier 0) |
| profile Bavaria | 47.0 | 41.2 | prepared (Tier 0) |
| profile Berlin | 1,732 | 2.9 | prepared (Tier 0) |
| top Germany | 1.4 | 1.4 | prepared (Tier 0) |
| top Bavaria | 42.4 | 38.6 | prepared (Tier 0) |
| top France | 1.4 | 1.2 | prepared (Tier 0) |
| totals Europe | 876 | 543 |  |
| totals United States | 6.1 | 1.7 | prepared (Tier 0) |
| compare France; Germany | 515 | 494 |  |
| published Poland | 2.5 | 1.6 |  |
| prices Germany | 105 | 119 |  |

Tier 0 state: `{"hot_ready": true, "in_hot": true, "fingerprint_now": "0593519c48d5a165", "fingerprints_stored": [["0593519c48d5a165", 22365]], "checks": [{"name": "Germany", "area_id": "a_bbf226ffbb00", "keys": ["top:10:substations", "profile:10:plants", "totals:10:plants", "top:10:plants", "top:10:data_centres"], "ids_by_name": ["a_bbf226ffbb00"], "lookup": true}, {"name": "Bavaria", "area_id": "a_16f57dda3841", "keys": ["profile:10:plants", "top:10:data_centres", "top:10:plants", "top:10:substations", "totals:10:plants"], "ids_by_name": null, "lookup": true}, {"name": "Berlin", "area_id": "a_2e72c8cc188b", "keys": ["top:10:plants", "totals:10:plants", "top:10:substations", "profile:10:plants", "top:10:data_centres"], "ids_by_name": ["a_2e72c8cc188b"], "lookup": true}], "missing_flag": false}`

### resolve_area: cold p50/p95 1,045 / 16,277, warm p50/p95 11.4 / 96.5

| | cold | warm p50 | note |
|---|---:|---:|---|
| Germany | 0.3 | 10.0 |  |
| France | 12.5 | 9.7 |  |
| Poland | 39.0 | 10.7 |  |
| Spain | 9.7 | 10.8 |  |
| Italy | 11.0 | 10.4 |  |
| United States | 237 | 19.3 |  |
| Nordics | 3,351 | 10.8 |  |
| EU-27 | 10,492 | 97.1 |  |
| Bavaria | 11.9 | 10.6 |  |
| Lower Saxony | 10,276 | 13.5 |  |
| Catalonia | 11.1 | 11.1 |  |
| Lombardy | 8,199 | 11.8 |  |
| Texas | 2,234 | 12.6 |  |
| California | 16,277 | 12.1 |  |
| Scotland | 1,812 | 12.2 |  |
| Brittany | 7,968 | 17.4 |  |
| Masovian Voivodeship | 9,241 | 11.2 |  |
| North Rhine-Westphalia | 8,688 | 12.0 |  |
| Andalusia | 7,138 | 20.8 |  |
| Upper Bavaria | 9.4 | 9.8 | not resolved |
| Harris County | 1,188 | 11.2 |  |
| Cook County | 1,343 | 9.5 |  |
| Kreis Steinfurt | 1,138 | 9.9 |  |
| Greater Manchester | 1,013 | 30.4 |  |
| Cornwall | 1,741 | 11.9 |  |
| Berlin | 12.1 | 11.2 |  |
| Paris | 1,045 | 11.5 |  |
| Madrid | 929 | 11.4 |  |
| Rome | 1,823 | 11.8 |  |
| Warsaw | 1,177 | 10.7 |  |
| Toulouse | 544 | 12.0 |  |
| Lyon | 11.2 | 11.4 |  |
| Hamburg | 1,162 | 11.9 |  |
| Munich | 521 | 10.9 |  |
| Vienna | 553 | 10.9 |  |
| Amsterdam | 554 | 11.1 |  |
| Copenhagen | 858 | 10.9 |  |
| Dublin | 671 | 11.5 |  |
| Lisbon | 955 | 11.0 |  |
| Houston | 547 | 11.7 |  |
| Leeds | 902 | 10.5 |  |
| Manchester | 520 | 10.9 |  |
| Kreuzberg | 1,363 | 12.6 |  |
| Schwabing | 10.1 | 10.8 | not resolved |
| Montmartre | 2,984 | 11.3 |  |
| DE-LU | 33,140 | 11.1 |  |
| NO2 | 1,364 | 99.3 |  |
| IT-North | 17,916 | 11.1 |  |
| Sicily | 3,270 | 21.9 |  |
| Saxony-Anhalt | 4,289 | 12.3 |  |

### area_stats: cold p50/p95 862 / 17,310, warm p50/p95 99.8 / 18,510

| | cold | warm p50 | note |
|---|---:|---:|---|
| people (city) | 290 | 18.1 |  |
| people (region) | 10,069 | 9,986 |  |
| built_up (city) | 1,115 | 9.0 |  |
| built_up (region) | 5,525 | 2,319 |  |
| land_cover (city) | 2,024 | 616 |  |
| land_cover (region) | 17,310 | 18,510 |  |
| slope (city) | 2,592 | 399 |  |
| slope (region) | 1,350 | 189 |  |
| solar (city) | 1,028 | 9.1 |  |
| solar (region) | 600 | 437 |  |
| wind (city) | 2,012 | 10.9 |  |
| wind (region) | 6,025 | 1,979 |  |
| flood (city) | 873 | 876 | r2://infraatlas-raw/lake/flood/eu_classes.tif: HTTP response code: 404; r2://infraatlas-raw/lake/flood/world_classes.tif: HTTP response code: 404 |
| flood (region) | 919 | 913 | r2://infraatlas-raw/lake/flood/eu_classes.tif: HTTP response code: 404; r2://infraatlas-raw/lake/flood/world_classes.tif: HTTP response code: 404 |
| heat_demand (city) | 1,131 | 230 |  |
| heat_demand (region) | 2,102 | 1,233 |  |
| w9_eu_edo_cdi (city) | 952 | 14.9 |  |
| w9_eu_edo_cdi (region) | 440 | 105 |  |
| w9_eu_effis_danger (city) | 862 | 8.4 |  |
| w9_eu_effis_danger (region) | 83.6 | 95.6 |  |
| w9_eu_emodnet_bathy (city) | 634 | 7.3 |  |
| w9_eu_emodnet_bathy (region) | 74.3 | 83.5 |  |
| w9_eu_emodnet_vessel_density (city) | 658 | 6.6 |  |
| w9_eu_emodnet_vessel_density (region) | 106 | 112 |  |
| w9_us_marinecadastre_ais (city) | 585 | 6.8 |  |
| w9_us_marinecadastre_ais (region) | 101 | 101 |  |
| w9_us_noaa_slr (city) | 645 | 7.5 |  |
| w9_us_noaa_slr (region) | 90.1 | 90.7 |  |
| w9_us_usfs_whp (city) | 544 | 6.7 |  |
| w9_us_usfs_whp (region) | 103 | 99.8 |  |
| w9_world_gebco (city) | 654 | 6.2 |  |
| w9_world_gebco (region) | 68.8 | 77.1 |  |
| w9_world_nex_gddp (city) | 39,666 | 31,887 |  |
| w9_world_nex_gddp (region) | 32,718 | 34,648 |  |

### Every table (slowest cold p95 first)

| table | cold p50 | cold p95 | warm p50 | warm p95 | MB cold | GETs | notes |
|---|---:|---:|---:|---:|---:|---:|---|
| `outlines.geostat_grid` | 2,334 | 55,684 | 295 | 3,076 | 182.11 | 108 |  |
| `outlines.divisions` | 9,753 | 53,357 | 118 | 724 | 6,143.71 | 3746 |  |
| `wave9.gb_ea_flood_zones` | 40,022 | 53,045 | 4.6 | 99.6 | 8,310.75 | 4194 |  |
| `main.plants` | 18,278 | 51,778 | 98.1 | 437 | 685.09 | 999 | region: TimeoutError: query stopped after 60 s; country: TimeoutError: query stopped after 60 s |
| `overture_power.sites` | 2,484 | 51,676 | 58.0 | 3,539 | 280.80 | 129 |  |
| `zoning.zones` | 4,262 | 33,613 | 874 | 1,261 | 928.13 | 332 |  |
| `overture_transport.segments` | 17,440 | 28,903 | 276 | 18,689 | 1,385.41 | 311 | region: TimeoutError: query stopped after 60 s |
| `main.outages` | 1,068 | 28,884 | 78.7 | 1,066 | 248.58 | 278 |  |
| `overture_power.lines` | 2,387 | 26,638 | 102 | 3,848 | 840.29 | 173 |  |
| `zoning.hub_layers` | 9.2 | 14,935 | 6.1 | 9.2 | 1.03 | 47 |  |
| `wave9.it_istat_sezioni` | 4,667 | 13,841 | 769 | 8,464 | 1,425.13 | 191 |  |
| `wave9.eu_kohesio_2014_2020` | 2,197 | 11,283 | 349 | 11,280 | 461.46 | 236 |  |
| `mastr.units_solar` | 6,069 | 10,656 | 70.6 | 559 | 241.62 | 228 | city: TimeoutError: query stopped after 60 s; region: TimeoutError: query stopped after 60 s |
| `entsoe.unit_output` | 3,124 | 9,767 | 27.4 | 222 | 17.92 | 138 |  |
| `iso_queues.requests` | 30.9 | 8,627 | 9.2 | 29.0 | 3.14 | 30 |  |
| `small_area_energy.poverty` | 17.1 | 8,614 | 9.3 | 25.9 | 4.28 | 44 |  |
| `wave9.de_zensus_heating` | 4,189 | 8,528 | 4,236 | 4,320 | 66.72 | 81 | region: TimeoutError: query stopped after 60 s |
| `wave9.cz_zsj` | 536 | 8,060 | 148 | 8,081 | 75.85 | 39 |  |
| `neso.constraint_breakdown` | 4.9 | 5,996 | 3.4 | 4.1 | 0.32 | 19 |  |
| `caiso.curtailment` | 11.8 | 5,831 | 5.3 | 10.8 | 5.05 | 19 |  |
| `mastr.units_storage` | 791 | 5,741 | 28.9 | 796 | 321.39 | 174 | city: TimeoutError: query stopped after 60 s; region: TimeoutError: query stopped after 60 s |
| `wave9.eur_overture_comm_lines` | 9.0 | 5,697 | 7.9 | 5,695 | 0.00 | 0 |  |
| `entsoe.congestion_redispatch_internal` | 12.8 | 5,649 | 7.0 | 13.0 | 1.42 | 19 |  |
| `eaglei.outages` | 2,410 | 5,409 | 23.3 | 40.0 | 18.51 | 42 |  |
| `entsoe.generation` | 3,816 | 5,168 | 22.5 | 212 | 2.67 | 124 |  |
| `afdc.stations` | 55.0 | 5,041 | 17.6 | 538 | 19.64 | 26 |  |
| `wave10.eu_nrg_te_oilm` | 2,453 | 5,002 | 12.9 | 360 | 2.18 | 53 |  |
| `wave10.eu_nrg_ti_oilm` | 1,795 | 4,760 | 12.6 | 354 | 2.14 | 51 |  |
| `entsoe.congestion_countertrading` | 26.1 | 4,693 | 5.5 | 7.2 | 0.34 | 19 |  |
| `wave9.eu_emodnet_mpa` | 580 | 4,409 | 612 | 3,251 | 349.45 | 91 |  |
| `wave10.eu_nrg_stk_oam` | 3,436 | 4,375 | 43.8 | 402 | 2.00 | 109 |  |
| `wave10.eu_nrg_cb_oil` | 526 | 4,345 | 16.5 | 455 | 2.64 | 19 |  |
| `wave10.eu_nrg_stk_oilm` | 747 | 4,289 | 15.4 | 369 | 3.81 | 18 |  |
| `wave9.us_noaa_mpa` | 206 | 4,069 | 134 | 3,218 | 133.29 | 36 |  |
| `entsoe.congestion_redispatch_cross_border` | 38.0 | 3,888 | 7.3 | 12.9 | 0.19 | 19 |  |
| `entsoe.flows` | 1,972 | 3,864 | 5.7 | 56.6 | 21.92 | 49 |  |
| `entsoe.load` | 1,116 | 3,744 | 5.4 | 345 | 2.42 | 34 |  |
| `entsoe.transfer_capacity` | 31.4 | 3,717 | 8.4 | 31.2 | 7.42 | 12 |  |
| `wave10.eu_env_ac_aeint_r2` | 589 | 3,573 | 33.6 | 517 | 6.56 | 13 |  |
| `aqueduct.baseline_annual` | 2,284 | 3,363 | 637 | 1,831 | 448.27 | 89 |  |
| `outlines.nl_cbs` | 137 | 3,336 | 118 | 1,268 | 72.53 | 26 |  |
| `outlines.uk_ons` | 498 | 3,267 | 574 | 3,246 | 191.16 | 53 |  |
| `wave10.eu_env_ac_pefasu` | 439 | 3,238 | 26.0 | 425 | 4.03 | 18 |  |
| `outlines.fr_iris` | 942 | 3,236 | 520 | 1,059 | 141.18 | 35 |  |
| `outlines.us_tracts` | 760 | 3,118 | 628 | 1,299 | 138.40 | 23 |  |
| `entsoe.outages` | 9.3 | 3,001 | 6.7 | 9.0 | 16.48 | 12 |  |
| `entsoe.forecast_wind_solar` | 601 | 2,832 | 9.6 | 24.4 | 14.11 | 23 |  |
| `protected.natura2000` | 399 | 2,803 | 138 | 2,797 | 32.35 | 18 |  |
| `main.grid_capacity` | 11.6 | 2,763 | 11.1 | 12.1 | 1.90 | 17 |  |
| `wave9.us_epa_repowering` | 637 | 2,744 | 385 | 501 | 24.34 | 20 |  |
| `outlines.small_areas` | 583 | 2,570 | 360 | 1,041 | 93.18 | 36 |  |
| `wave9.at_zaehlsprengel` | 588 | 2,564 | 98.3 | 2,571 | 95.46 | 34 |  |
| `wave9.us_usgs_landslides` | 1,159 | 2,540 | 346 | 2,264 | 39.84 | 45 |  |
| `outlines.adm2` | 230 | 2,512 | 224 | 492 | 136.24 | 66 |  |
| `entsoe.prices` | 362 | 2,501 | 7.1 | 25.2 | 14.09 | 16 |  |
| `eia930.demand` | 1,486 | 2,471 | 42.6 | 94.6 | 37.33 | 43 |  |
| `grw.solar` | 646 | 2,405 | 262 | 2,111 | 112.26 | 48 |  |
| `dams.reservoirs` | 1,284 | 2,384 | 757 | 1,147 | 189.81 | 48 |  |
| `main.water_risk` | 1,491 | 2,277 | 808 | 2,033 | 347.43 | 48 |  |
| `grw.wind` | 465 | 2,214 | 254 | 1,252 | 19.12 | 25 |  |
| `protected.padus` | 1,376 | 2,132 | 211 | 1,534 | 229.74 | 48 |  |
| `wave10.eu_env_ac_egss2` | 475 | 2,049 | 19.0 | 447 | 2.97 | 13 |  |
| `small_area_energy.consumption` | 447 | 2,037 | 4.0 | 59.7 | 43.29 | 36 |  |
| `wave10.eu_env_ac_ainah_r2` | 487 | 1,990 | 48.9 | 438 | 33.51 | 20 |  |
| `aqueduct.basins` | 451 | 1,865 | 164 | 675 | 118.86 | 47 |  |
| `wave9.eu_emodnet_msp_zoning` | 171 | 1,723 | 150 | 187 | 72.41 | 37 |  |
| `wave10.eu_env_ac_co2fp` | 466 | 1,652 | 2.2 | 37.0 | 22.31 | 17 |  |
| `wave9.us_usgs_mrds` | 635 | 1,636 | 39.6 | 634 | 25.17 | 20 |  |
| `mastr.units_combustion` | 17.6 | 1,627 | 13.5 | 259 | 12.96 | 10 |  |
| `wave10.eu_nrg_cb_oilm` | 437 | 1,613 | 15.9 | 287 | 2.34 | 7 |  |
| `wave10.gb_desnz_ghg_dataset` | 548 | 1,603 | 22.0 | 894 | 5.50 | 4 |  |
| `wave9.world_ourairports` | 25.6 | 1,589 | 19.3 | 352 | 6.35 | 8 |  |
| `outlines.us_places` | 668 | 1,558 | 625 | 1,215 | 73.36 | 15 |  |
| `wave10.eu_nrg_bal_s` | 703 | 1,522 | 12.5 | 257 | 2.74 | 5 |  |
| `wave9.world_ihfc_heat_flow` | 36.8 | 1,498 | 22.3 | 326 | 5.29 | 6 |  |
| `euets.installations` | 61.9 | 1,489 | 21.2 | 49.1 | 5.45 | 3 |  |
| `wave9.ie_seai_ber` | 679 | 1,463 | 32.5 | 789 | 5.31 | 9 |  |
| `entsog.flows` | 81.9 | 1,429 | 30.5 | 67.5 | 10.73 | 6 |  |
| `outlines.us_cousub` | 741 | 1,392 | 677 | 952 | 101.13 | 18 |  |
| `wave9.eu_emodnet_substrate` | 161 | 1,369 | 140 | 722 | 85.61 | 36 |  |
| `wave9.us_noaa_storm_events` | 38.8 | 1,344 | 15.1 | 160 | 6.45 | 8 |  |
| `wave9.fr_georisques_ssp` | 370 | 1,307 | 303 | 365 | 35.07 | 12 |  |
| `wave9.us_epa_frs_cleanups` | 70.5 | 1,307 | 16.5 | 215 | 3.44 | 5 |  |
| `wave9.gb_he_listed` | 828 | 1,295 | 568 | 1,347 | 39.86 | 35 |  |
| `wave9.us_opportunity_zones` | 100 | 1,293 | 78.6 | 93.4 | 56.70 | 29 |  |
| `wave9.us_nyc_ll84` | 624 | 1,271 | 378 | 618 | 19.59 | 14 |  |
| `wave10.eu_env_ac_ch4fp` | 851 | 1,259 | 1.9 | 21.0 | 6.66 | 13 |  |
| `wave10.eu_env_ac_io10` | 604 | 1,142 | 24.2 | 756 | 2.58 | 3 |  |
| `wave9.ee_grid` | 10.4 | 1,127 | 9.5 | 11.7 | 2.26 | 6 |  |
| `wave9.us_usaspending_doe` | 790 | 1,123 | 33.6 | 773 | 2.85 | 4 |  |
| `industrial.installations` | 433 | 1,118 | 40.4 | 597 | 13.42 | 8 |  |
| `neso_tec.projects` | 6.2 | 1,068 | 5.7 | 6.6 | 0.32 | 4 |  |
| `small_area_energy.heating` | 8.1 | 1,064 | 5.7 | 12.2 | 1.95 | 3 |  |
| `wave9.es_ine_secciones` | 163 | 1,058 | 107 | 175 | 66.85 | 34 |  |
| `wave9.be_elia_balancing` | 475 | 1,050 | 2.2 | 59.9 | 20.22 | 13 |  |
| `wave10.eu_env_ac_pfcfp` | 580 | 964 | 2.7 | 31.3 | 1.60 | 15 |  |
| `wave10.eu_env_ac_ghgfp` | 403 | 948 | 1.9 | 42.5 | 22.99 | 16 |  |
| `wave10.eu_env_ac_nf3sf6fp` | 648 | 942 | 2.7 | 19.8 | 1.88 | 12 |  |
| `dams.barriers` | 18.5 | 924 | 14.5 | 132 | 3.99 | 6 |  |
| `wave10.eu_env_ac_eptrf1` | 8.8 | 903 | 3.8 | 8.0 | 0.05 | 1 |  |
| `lbnl_queue.requests` | 14.7 | 885 | 8.2 | 8.9 | 1.15 | 1 |  |
| `wave9.world_ourairports_runways` | 11.7 | 861 | 9.3 | 114 | 1.48 | 1 |  |
| `small_area_energy.renewables` | 6.7 | 856 | 4.6 | 6.3 | 0.51 | 1 |  |
| `wave9.gr_admie_balancing` | 634 | 856 | 1.6 | 18.3 | 9.37 | 7 |  |
| `gem_ownership.entity_ownership` | 853 | 853 | 1.6 | 1.6 | 0.90 | 1 |  |
| `aqueduct.future_annual` | 608 | 853 | 12.2 | 13.8 | 7.06 | 6 |  |
| `atb.electricity` | 569 | 852 | 11.9 | 35.2 | 6.36 | 7 |  |
| `zoning.document_pages` | 221 | 837 | 12.0 | 15.4 | 2.52 | 5 |  |
| `wave10.wb_ag_lnd_irig_ag_zs` | 3.2 | 826 | 2.1 | 3.1 | 0.02 | 1 |  |
| `wave10.eu_env_ac_hfcfp` | 425 | 826 | 2.4 | 41.0 | 12.61 | 18 |  |
| `eia930.generation_by_fuel` | 558 | 818 | 2.1 | 15.8 | 4.25 | 6 |  |
| `wave10.eu_nrg_ind_urhcd` | 3.9 | 817 | 2.9 | 3.5 | 0.05 | 1 |  |
| `wave9.lv_csp_central_heating` | 561 | 816 | 9.4 | 817 | 0.51 | 1 |  |
| `osm.eu_lines` | 22.4 | 806 | 10.0 | 74.2 | 14.14 | 10 |  |
| `euets.verified_emissions` | 422 | 803 | 27.7 | 126 | 4.08 | 4 |  |
| `wave9.gb_srn` | 430 | 797 | 10.0 | 487 | 15.86 | 10 |  |
| `wave10.wb_ny_adj_nnat_cd` | 3.1 | 787 | 1.8 | 3.1 | 0.04 | 1 |  |
| `wave9.us_eia_gas_pipelines` | 11.9 | 775 | 7.9 | 472 | 4.41 | 6 |  |
| `places.cities` | 43.8 | 760 | 11.2 | 42.8 | 2.37 | 4 |  |
| `wave10.eu_nrg_te_gas` | 36.8 | 755 | 4.4 | 36.3 | 0.03 | 1 |  |
| `wave9.gb_brownfield_register` | 558 | 753 | 11.3 | 191 | 4.17 | 7 |  |
| `ev_eu.at` | 14.7 | 746 | 4.2 | 24.0 | 0.40 | 1 |  |
| `wave9.cz_csu_sldb_heating_energy` | 7.2 | 737 | 1.6 | 6.9 | 0.44 | 1 |  |
| `gem.integrated_power_power_facilities` | 420 | 730 | 231 | 248 | 9.04 | 6 |  |
| `wave9.us_smu_heat_flow` | 251 | 724 | 10.1 | 55.3 | 12.70 | 13 |  |
| `wave9.fi_statfin_heating_fuel_municipality` | 386 | 706 | 18.0 | 702 | 0.99 | 1 |  |
| `wave9.us_natcarb` | 434 | 706 | 27.1 | 570 | 5.75 | 10 |  |
| `wave10.eu_env_ac_ainah_rd` | 558 | 704 | 18.8 | 142 | 3.92 | 3 |  |
| `wave9.eu_eshm20` | 55.0 | 703 | 11.5 | 52.8 | 1.21 | 1 |  |
| `wave10.eu_env_ac_n2ofp` | 616 | 702 | 2.4 | 24.8 | 8.27 | 15 |  |
| `wave10.eu_nrg_pc_202_c` | 10.3 | 699 | 3.6 | 9.1 | 0.20 | 1 |  |
| `wave10.wb_en_urb_mcty_tl_zs` | 3.4 | 696 | 2.1 | 3.4 | 0.04 | 1 |  |
| `egrid.plants` | 21.9 | 693 | 20.3 | 60.2 | 2.54 | 4 |  |
| `wave10.gb_census_heating` | 3.2 | 693 | 2.3 | 2.9 | 0.03 | 1 |  |
| `wave10.wb_ag_lnd_el5m_ru_zs` | 4.4 | 687 | 2.7 | 4.0 | 0.02 | 1 |  |
| `wave10.eu_nrg_d_indq_n` | 200 | 686 | 10.6 | 125 | 0.78 | 1 |  |
| `wave10.eu_cei_srm020` | 8.4 | 683 | 3.3 | 6.4 | 0.11 | 1 |  |
| `wave10.eu_env_air_emis_ind` | 3.8 | 679 | 2.7 | 2.8 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_n2o_bu_mt_ce_ar5` | 3.8 | 677 | 2.2 | 3.5 | 0.06 | 1 |  |
| `gem_ownership.oil___ngl_pipeline_ownership` | 675 | 675 | 1.8 | 1.8 | 0.34 | 1 |  |
| `power_plants_eu.ppm_plants` | 220 | 675 | 20.0 | 246 | 8.16 | 5 |  |
| `wave10.eu_env_ac_mfadpo` | 11.8 | 674 | 5.4 | 9.3 | 0.16 | 1 |  |
| `registers.gb` | 20.0 | 672 | 7.0 | 40.5 | 0.80 | 1 |  |
| `wave9.eu_water_abstraction` | 6.9 | 672 | 4.4 | 6.1 | 0.08 | 1 |  |
| `edgar.ghg_by_sector` | 9.0 | 671 | 2.9 | 6.8 | 1.78 | 1 |  |
| `wave10.eu_nrg_cb_h` | 5.2 | 670 | 3.3 | 4.5 | 0.06 | 1 |  |
| `wave10.wb_er_h2o_fwin_zs` | 4.9 | 670 | 3.2 | 4.9 | 0.04 | 1 |  |
| `wave10.wb_ny_adj_dmin_cd` | 3.1 | 665 | 1.7 | 3.0 | 0.04 | 1 |  |
| `wave10.wb_eg_cft_accs_ur_zs` | 3.3 | 664 | 1.8 | 2.7 | 0.02 | 1 |  |
| `history.registers__fr` | 12.4 | 663 | 3.8 | 9.5 | 1.96 | 1 |  |
| `wave10.eu_nrg_ti_oil` | 494 | 660 | 18.6 | 483 | 1.10 | 1 |  |
| `wave9.us_epa_aqs_annual` | 21.2 | 658 | 20.0 | 301 | 3.64 | 5 |  |
| `wave10.wb_ag_lnd_agri_zs` | 3.9 | 657 | 2.3 | 3.6 | 0.06 | 1 |  |
| `wave10.wb_ag_lnd_el5m_ur_k2` | 3.1 | 656 | 1.9 | 3.7 | 0.02 | 1 |  |
| `industrial.water_releases` | 288 | 655 | 19.8 | 228 | 3.49 | 3 |  |
| `wave10.eu_env_ac_mfain` | 5.1 | 653 | 3.5 | 4.0 | 0.10 | 1 |  |
| `wave10.eu_nrg_ind_id` | 2.9 | 650 | 2.4 | 2.7 | 0.03 | 1 |  |
| `wave10.gb_desnz_tfec_la` | 16.3 | 650 | 2.5 | 13.3 | 1.79 | 1 |  |
| `esb_heatmap.transformers` | 22.1 | 650 | 12.2 | 12.4 | 2.23 | 4 |  |
| `wave10.eu_env_epea_trf` | 5.5 | 649 | 3.7 | 4.9 | 0.03 | 1 |  |
| `wave9.eu_air_passengers` | 5.2 | 649 | 3.4 | 4.9 | 0.06 | 1 |  |
| `history.registers__se` | 13.7 | 646 | 4.2 | 22.3 | 0.44 | 1 |  |
| `wave10.wb_ip_tmk_rsct` | 4.1 | 643 | 2.7 | 4.1 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_n2o_zg_ar5` | 3.8 | 642 | 2.2 | 3.5 | 0.07 | 1 |  |
| `wave10.eu_env_ac_pefa04` | 46.3 | 642 | 7.9 | 41.5 | 0.52 | 1 |  |
| `wave9.ie_cso_saps_heating` | 634 | 641 | 9.9 | 69.7 | 10.45 | 8 |  |
| `wave9.gb_nged_opendata` | 27.7 | 638 | 20.3 | 44.2 | 0.83 | 1 |  |
| `uk_pi.releases` | 16.8 | 638 | 12.7 | 14.4 | 0.38 | 1 |  |
| `wave10.gb_census_travel_method` | 3.5 | 637 | 2.3 | 3.5 | 0.03 | 1 |  |
| `wave10.eu_env_ac_cepsgh1` | 5.3 | 636 | 4.2 | 5.0 | 0.02 | 1 |  |
| `wave9.eu_eea_aq_stats` | 39.7 | 633 | 31.4 | 37.0 | 0.39 | 1 |  |
| `ei_review.series` | 8.4 | 632 | 2.6 | 7.8 | 1.50 | 1 |  |
| `wave10.eu_nrg_stk_oom` | 407 | 632 | 15.9 | 397 | 1.20 | 1 |  |
| `wave10.eu_nrg_ind_cotd` | 3.0 | 631 | 2.8 | 2.9 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_co2_wa_mt_ce_ar5` | 2.9 | 630 | 1.8 | 2.7 | 0.03 | 1 |  |
| `ev_eu.it` | 14.7 | 630 | 4.9 | 14.1 | 0.55 | 1 |  |
| `mastr.grid_connection_points` | 5.1 | 629 | 4.8 | 4.8 | 0.53 | 2 |  |
| `wave9.cz_ceps_balancing` | 628 | 628 | 2.3 | 2.3 | 1.04 | 1 |  |
| `wave10.wb_en_ghg_co2_pi_mt_ce_ar5` | 4.1 | 627 | 2.2 | 3.8 | 0.07 | 1 |  |
| `wave10.wb_eg_use_elec_kh_pc` | 3.2 | 625 | 1.9 | 3.5 | 0.05 | 1 |  |
| `wave10.wb_sp_urb_totl` | 3.5 | 624 | 2.2 | 3.4 | 0.04 | 1 |  |
| `wave10.eu_env_epea_neep` | 3.4 | 624 | 3.0 | 3.2 | 0.03 | 1 |  |
| `wave9.gb_emr_cm_register` | 8.4 | 623 | 6.7 | 8.0 | 0.64 | 1 |  |
| `wave10.eu_env_epea_invap` | 14.4 | 623 | 4.8 | 13.3 | 0.09 | 1 |  |
| `gem.energy_ownership_bioenergy_power_ownership` | 2.3 | 623 | 1.8 | 2.2 | 0.72 | 1 |  |
| `wave10.eu_env_ac_pepsgg1` | 13.1 | 623 | 4.0 | 11.9 | 0.08 | 1 |  |
| `wave10.wb_en_ghg_ch4_fe_mt_ce_ar5` | 3.3 | 623 | 1.9 | 3.0 | 0.06 | 1 |  |
| `wave10.wb_eg_elc_accs_ur_zs` | 3.8 | 622 | 2.4 | 3.7 | 0.03 | 1 |  |
| `gem_ownership.bioenergy_power_ownership` | 621 | 621 | 1.7 | 1.7 | 0.73 | 1 |  |
| `wave10.wb_ny_adj_aedu_cd` | 3.0 | 620 | 1.8 | 2.9 | 0.05 | 1 |  |
| `wave10.wb_it_cel_sets_p2` | 3.7 | 619 | 2.2 | 3.2 | 0.07 | 1 |  |
| `wave10.eu_nrg_ti_eh` | 18.7 | 619 | 3.5 | 15.7 | 0.03 | 1 |  |
| `wave10.wb_ny_gdp_minr_rt_zs` | 4.0 | 619 | 1.8 | 3.3 | 0.05 | 1 |  |
| `wave10.wb_ic_elc_durs` | 3.4 | 619 | 2.2 | 3.4 | 0.02 | 1 |  |
| `wave10.wb_it_net_user_fe_zs` | 3.8 | 619 | 2.2 | 3.3 | 0.02 | 1 |  |
| `wave9.ee_stat_heating_2011` | 11.8 | 618 | 3.7 | 10.7 | 0.06 | 1 |  |
| `wave10.eu_nrg_te_eh` | 33.0 | 618 | 5.1 | 32.0 | 0.03 | 1 |  |
| `wave10.wb_si_pov_dday` | 2.9 | 617 | 1.7 | 2.6 | 0.02 | 1 |  |
| `wave10.eu_nrg_bal_cv` | 13.4 | 616 | 7.9 | 12.3 | 0.25 | 1 |  |
| `wave10.wb_ag_lnd_totl_ru_k2` | 2.9 | 616 | 1.8 | 2.8 | 0.02 | 1 |  |
| `wave10.eu_nrg_ind_peh` | 40.1 | 616 | 5.6 | 38.6 | 0.30 | 1 |  |
| `irena.capacity` | 5.2 | 614 | 3.7 | 5.0 | 0.30 | 1 |  |
| `wave10.eu_nrg_cb_eim` | 3.8 | 614 | 3.5 | 3.6 | 0.09 | 1 |  |
| `wave10.eu_nrg_chddr2_m` | 11.4 | 613 | 7.7 | 13.3 | 1.19 | 1 |  |
| `wave9.dk_energinet_reserves` | 568 | 612 | 2.1 | 17.3 | 3.13 | 4 |  |
| `gem.energy_ownership_gas_plant_ownership` | 281 | 612 | 2.2 | 2.8 | 0.02 | 2 |  |
| `main.emissions` | 416 | 612 | 2.9 | 11.5 | 1.21 | 4 |  |
| `mastr.units_biomass` | 28.6 | 612 | 21.1 | 156 | 5.43 | 6 |  |
| `wave10.wb_bx_gsr_ccis_cd` | 3.6 | 612 | 2.3 | 3.5 | 0.05 | 1 |  |
| `wave10.wb_er_h2o_intr_pc` | 2.9 | 611 | 1.7 | 2.6 | 0.06 | 1 |  |
| `wave10.wb_sh_sta_hygn_zs` | 3.4 | 611 | 2.1 | 3.5 | 0.02 | 1 |  |
| `wave10.wb_ip_ids_rsct` | 2.9 | 610 | 1.8 | 3.0 | 0.02 | 1 |  |
| `aqueduct.baseline_monthly` | 535 | 609 | 8.4 | 13.9 | 4.83 | 5 |  |
| `gem.oil_gas_extraction_field_level_production_data` | 2.4 | 609 | 2.0 | 2.1 | 0.21 | 1 |  |
| `industrial.air_releases` | 245 | 609 | 13.8 | 248 | 6.16 | 4 |  |
| `wave10.wb_ny_adj_dfor_cd` | 3.4 | 608 | 2.1 | 3.5 | 0.03 | 1 |  |
| `wave10.wb_ag_lnd_totl_k2` | 4.3 | 608 | 2.8 | 4.1 | 0.03 | 1 |  |
| `gem.energy_ownership_oil_ngl_pipeline_ownership` | 2.2 | 608 | 1.8 | 2.2 | 0.31 | 1 |  |
| `wave10.wb_eg_elc_petr_zs` | 3.7 | 606 | 2.2 | 3.7 | 0.06 | 1 |  |
| `wave10.wb_ie_ppi_icti_cd` | 2.8 | 606 | 1.7 | 2.7 | 0.01 | 1 |  |
| `wave10.wb_en_ghg_co2_ip_mt_ce_ar5` | 3.4 | 606 | 2.2 | 3.5 | 0.07 | 1 |  |
| `wave10.wb_sh_h2o_basw_ur_zs` | 3.6 | 606 | 1.8 | 3.0 | 0.04 | 1 |  |
| `wave10.wb_en_pop_el5m_ru_zs` | 2.9 | 604 | 1.7 | 2.7 | 0.02 | 1 |  |
| `registers.cz` | 7.3 | 604 | 5.6 | 7.2 | 0.82 | 1 |  |
| `wave10.wb_en_ghg_co2_ag_mt_ce_ar5` | 3.0 | 604 | 1.8 | 2.8 | 0.04 | 1 |  |
| `wave10.wb_eg_elc_hyro_zs` | 3.2 | 604 | 1.9 | 3.0 | 0.06 | 1 |  |
| `wave10.eu_env_epea_cfin` | 4.4 | 603 | 3.5 | 4.1 | 0.01 | 1 |  |
| `gem.oil_gas_extraction_field_level_main_data` | 389 | 603 | 48.1 | 50.3 | 3.05 | 3 |  |
| `wave10.eu_nrg_ind_esc` | 5.6 | 602 | 3.5 | 5.0 | 0.15 | 1 |  |
| `wave10.eu_nrg_ind_eff` | 3.5 | 600 | 3.2 | 3.4 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_all_mt_ce_ar5` | 3.6 | 600 | 2.3 | 3.6 | 0.07 | 1 |  |
| `wave9.gr_elstat_heating_settlement` | 11.1 | 600 | 7.4 | 10.8 | 0.98 | 1 |  |
| `wave9.eu_land_prices` | 2.7 | 600 | 2.8 | 3.2 | 0.04 | 1 |  |
| `wave9.world_ourairports_navaids` | 10.4 | 599 | 6.3 | 51.7 | 0.61 | 1 |  |
| `wave10.wb_en_atm_pm25_mc_t2_zs` | 3.5 | 599 | 2.2 | 3.2 | 0.02 | 1 |  |
| `mastr_grid.operators` | 15.8 | 598 | 2.2 | 4.2 | 0.09 | 1 |  |
| `wave10.wb_ie_ppn_icti_cd` | 3.8 | 598 | 2.1 | 3.6 | 0.01 | 1 |  |
| `wave10.eu_env_ac_rme` | 5.4 | 598 | 3.5 | 4.8 | 0.15 | 1 |  |
| `wave10.wb_er_h2o_fwst_zs` | 3.7 | 597 | 2.2 | 3.5 | 0.04 | 1 |  |
| `wave9.us_openei_urdb` | 596 | 596 | 14.0 | 14.0 | 0.13 | 2 |  |
| `wave10.eu_nrg_cb_pem` | 28.4 | 596 | 6.1 | 26.8 | 0.66 | 1 |  |
| `wave10.eu_env_ac_epiap1` | 108 | 595 | 6.4 | 55.7 | 0.15 | 1 |  |
| `wave10.wb_ny_adj_dpem_cd` | 3.4 | 595 | 2.1 | 3.3 | 0.05 | 1 |  |
| `wave10.wb_en_ghg_n2o_mt_ce_ar5` | 3.0 | 595 | 1.8 | 2.8 | 0.07 | 1 |  |
| `wave9.us_nrhp` | 38.3 | 594 | 17.5 | 266 | 6.96 | 6 |  |
| `wave10.wb_is_air_dprt` | 3.5 | 594 | 2.1 | 3.4 | 0.03 | 1 |  |
| `wave10.wb_er_gdp_fwtl_m3_kd` | 2.7 | 594 | 1.6 | 2.6 | 0.06 | 1 |  |
| `wave9.eu_household_income` | 6.3 | 593 | 5.3 | 5.4 | 0.26 | 1 |  |
| `wave10.wb_sh_h2o_basw_ru_zs` | 4.2 | 593 | 2.8 | 4.0 | 0.04 | 1 |  |
| `wave10.wb_sh_sta_odfc_ur_zs` | 4.5 | 593 | 2.7 | 4.2 | 0.04 | 1 |  |
| `wave10.wb_en_clc_drsk_xq` | 3.3 | 592 | 1.9 | 3.0 | 0.01 | 1 |  |
| `wave10.eu_env_esst_gg` | 122 | 591 | 4.3 | 52.5 | 0.17 | 1 |  |
| `wave10.eu_env_ac_mfabi` | 5.5 | 590 | 3.9 | 5.1 | 0.09 | 1 |  |
| `wave9.pt_ine_heating_freguesia` | 3.6 | 590 | 1.4 | 3.3 | 0.17 | 1 |  |
| `gem_ownership.iron_mine_ownership` | 590 | 590 | 2.3 | 2.3 | 0.22 | 1 |  |
| `wave10.wb_is_rrs_pasg_km` | 3.1 | 590 | 1.7 | 2.6 | 0.02 | 1 |  |
| `wave10.wb_ny_adj_svnx_cd` | 3.9 | 588 | 2.2 | 3.4 | 0.04 | 1 |  |
| `wave10.eu_nrg_ind_ahbtc` | 9.5 | 588 | 4.1 | 9.0 | 0.03 | 1 |  |
| `wave10.eu_env_ac_tax` | 3.7 | 587 | 3.5 | 3.6 | 0.04 | 1 |  |
| `wave10.wb_eg_egy_prim_pp_kd` | 4.4 | 587 | 2.7 | 4.2 | 0.04 | 1 |  |
| `gem.energy_ownership_entity_ownership` | 1.9 | 587 | 1.8 | 1.9 | 0.90 | 1 |  |
| `wave10.wb_it_net_bbnd` | 2.9 | 586 | 1.8 | 2.8 | 0.03 | 1 |  |
| `wave10.wb_ag_lnd_frst_zs` | 3.7 | 586 | 2.2 | 3.4 | 0.06 | 1 |  |
| `wave10.wb_sh_sta_bass_ur_zs` | 3.0 | 585 | 1.8 | 2.8 | 0.04 | 1 |  |
| `wave10.eu_nrg_ti_coifpm` | 405 | 584 | 11.1 | 403 | 0.89 | 1 |  |
| `wave10.eu_nrg_d_hhq` | 14.7 | 583 | 5.0 | 13.3 | 0.20 | 1 |  |
| `wave10.wb_sh_sta_odfc_zs` | 2.8 | 583 | 1.6 | 2.6 | 0.04 | 1 |  |
| `wave10.eu_env_ac_aibrid_r2` | 498 | 582 | 12.1 | 71.3 | 2.66 | 3 |  |
| `wave10.wb_se_enr_prsc_fm_zs` | 3.8 | 582 | 2.1 | 3.6 | 0.03 | 1 |  |
| `wave9.us_usseabed` | 399 | 581 | 14.8 | 351 | 1.28 | 6 |  |
| `wave10.wb_sh_h2o_smdw_zs` | 3.9 | 581 | 2.3 | 3.8 | 0.04 | 1 |  |
| `wave10.wb_eg_use_comm_cl_zs` | 3.7 | 581 | 2.1 | 3.6 | 0.05 | 1 |  |
| `wave10.wb_tm_val_mmtl_zs_un` | 2.9 | 580 | 1.8 | 2.8 | 0.06 | 1 |  |
| `wave10.eu_env_epea_pgg` | 29.6 | 580 | 4.8 | 28.5 | 0.05 | 1 |  |
| `wave9.pl_pse_balancing` | 517 | 579 | 2.4 | 12.3 | 2.60 | 4 |  |
| `wave10.wb_it_cel_sets` | 3.8 | 579 | 2.2 | 3.4 | 0.04 | 1 |  |
| `gem_ownership.asset_ownership` | 579 | 579 | 2.1 | 2.1 | 0.82 | 1 |  |
| `wave10.eu_env_ac_egss1` | 73.5 | 579 | 11.9 | 72.6 | 0.46 | 1 |  |
| `wave10.wb_ny_gdp_petr_rt_zs` | 4.1 | 578 | 2.6 | 3.9 | 0.05 | 1 |  |
| `wave9.fr_ore_ev_commune` | 487 | 577 | 1.9 | 16.5 | 2.22 | 4 |  |
| `wave10.eu_nrg_ind_epsc` | 4.1 | 577 | 4.1 | 4.2 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_ch4_pi_mt_ce_ar5` | 3.6 | 576 | 2.2 | 3.5 | 0.05 | 1 |  |
| `wave10.eu_env_ac_ccminv` | 5.4 | 576 | 3.5 | 4.4 | 0.06 | 1 |  |
| `gem.energy_ownership_coal_plant_ownership` | 284 | 575 | 2.2 | 3.1 | 0.02 | 2 |  |
| `wave10.eu_env_air_emis` | 60.7 | 575 | 9.7 | 59.8 | 0.29 | 1 |  |
| `wave10.wb_er_mrn_ptmr_zs` | 4.2 | 574 | 2.7 | 3.9 | 0.02 | 1 |  |
| `wave10.eu_env_ac_pefafp` | 559 | 574 | 5.9 | 622 | 0.37 | 1 |  |
| `wave10.wb_en_ghg_co2_lu_ol_mt_ce_ar5` | 3.1 | 573 | 1.8 | 2.9 | 0.03 | 1 |  |
| `wave9.eu_emodnet_hydrocarbon_licences` | 11.7 | 570 | 7.5 | 12.3 | 1.37 | 1 |  |
| `wave10.wb_ny_adj_dkap_gn_zs` | 4.2 | 570 | 2.6 | 4.0 | 0.05 | 1 |  |
| `wave10.eu_nrg_d_traq` | 20.2 | 570 | 5.3 | 19.2 | 0.09 | 1 |  |
| `wave10.eu_nrg_stk_gasm` | 8.4 | 569 | 4.7 | 7.9 | 0.05 | 1 |  |
| `ev_eu.gb` | 19.0 | 569 | 5.2 | 35.4 | 0.50 | 1 |  |
| `wave10.eu_nrg_stk_oem` | 4.3 | 568 | 4.1 | 4.2 | 0.03 | 1 |  |
| `wave10.eu_nrg_pc_203_c` | 26.2 | 568 | 6.3 | 23.6 | 0.34 | 1 |  |
| `wave10.gb_desnz_co2_la` | 13.8 | 568 | 2.0 | 12.2 | 2.07 | 1 |  |
| `wave10.wb_sp_pop_totl` | 4.1 | 567 | 2.6 | 4.1 | 0.04 | 1 |  |
| `wave9.us_usgs_nwis_sites` | 473 | 566 | 32.4 | 470 | 10.61 | 7 |  |
| `wave10.wb_eg_fec_rnew_zs` | 3.3 | 566 | 1.8 | 3.2 | 0.03 | 1 |  |
| `wave9.eu_heat_production` | 141 | 566 | 13.9 | 138 | 0.83 | 1 |  |
| `wave10.wb_ag_srf_totl_k2` | 4.2 | 563 | 3.0 | 3.8 | 0.02 | 1 |  |
| `wave10.wb_sh_sta_smss_ru_zs` | 3.6 | 563 | 2.2 | 3.6 | 0.03 | 1 |  |
| `wave10.wb_ny_gdp_frst_rt_zs` | 3.9 | 562 | 2.7 | 4.1 | 0.06 | 1 |  |
| `wave10.eu_env_watabs_rb` | 3.4 | 562 | 1.4 | 3.3 | 0.10 | 1 |  |
| `outlines.urban_centres` | 292 | 560 | 288 | 355 | 10.83 | 6 |  |
| `wave10.wb_sh_h2o_smdw_ru_zs` | 4.1 | 560 | 2.6 | 4.0 | 0.03 | 1 |  |
| `wave10.eu_env_ac_rmefd` | 416 | 559 | 14.8 | 546 | 1.67 | 1 |  |
| `wave10.wb_en_ghg_co2_fe_mt_ce_ar5` | 4.2 | 559 | 2.7 | 4.1 | 0.05 | 1 |  |
| `wave10.eu_nrg_ind_ured` | 5.6 | 558 | 4.0 | 5.2 | 0.05 | 1 |  |
| `wave10.wb_it_mlt_main_p2` | 4.4 | 558 | 2.8 | 4.7 | 0.06 | 1 |  |
| `wave10.wb_ny_adj_svng_cd` | 4.3 | 557 | 2.7 | 4.1 | 0.04 | 1 |  |
| `wave10.wb_eg_use_crnw_zs` | 4.1 | 556 | 2.8 | 4.2 | 0.05 | 1 |  |
| `wave10.eu_nrg_ind_difec` | 5.3 | 556 | 4.0 | 4.9 | 0.07 | 1 |  |
| `wave10.eu_nrg_cb_gasm` | 28.7 | 556 | 6.5 | 28.1 | 0.33 | 1 |  |
| `wave9.eu_entsoe_balancing` | 4.9 | 556 | 2.5 | 4.9 | 0.07 | 1 |  |
| `wave10.wb_sh_sta_wash_p5` | 4.3 | 555 | 2.7 | 4.1 | 0.01 | 1 |  |
| `wave10.eu_nrg_ti_gasm` | 196 | 552 | 10.0 | 240 | 0.54 | 1 |  |
| `wave10.wb_eg_cft_accs_ru_zs` | 3.9 | 552 | 2.6 | 4.2 | 0.03 | 1 |  |
| `wave10.wb_eg_elc_ngas_zs` | 4.4 | 552 | 2.7 | 4.0 | 0.05 | 1 |  |
| `wave10.wb_eg_elc_fosl_zs` | 4.2 | 551 | 2.7 | 4.2 | 0.06 | 1 |  |
| `wave10.wb_tx_val_ictg_zs_un` | 4.4 | 549 | 2.7 | 4.3 | 0.04 | 1 |  |
| `wave10.wb_ag_lnd_el5m_zs` | 4.6 | 549 | 2.7 | 4.0 | 0.01 | 1 |  |
| `wave10.eu_nrg_ind_pehnf` | 31.4 | 548 | 5.8 | 30.5 | 0.12 | 1 |  |
| `wave10.eu_nrg_te_h2` | 6.8 | 548 | 4.2 | 5.8 | 0.01 | 1 |  |
| `wave10.eu_nrg_ind_ibmg` | 7.3 | 547 | 3.9 | 6.7 | 0.00 | 1 |  |
| `wave10.eu_nrg_cb_sffm` | 54.6 | 547 | 8.0 | 52.6 | 0.43 | 1 |  |
| `wave10.eu_env_esst_rw` | 15.4 | 546 | 4.3 | 14.3 | 0.03 | 1 |  |
| `wave10.eu_env_esst_ceprw` | 7.1 | 546 | 4.1 | 6.4 | 0.03 | 1 |  |
| `wave10.wb_en_atm_pm25_mc_m3` | 4.5 | 546 | 2.7 | 4.2 | 0.07 | 1 |  |
| `wave10.wb_ip_ids_nrct` | 4.2 | 545 | 2.7 | 4.0 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` | 4.2 | 544 | 2.8 | 4.1 | 0.04 | 1 |  |
| `wave10.eu_env_esst_cepgg` | 56.2 | 543 | 4.6 | 52.7 | 0.13 | 1 |  |
| `wave10.eu_nrg_te_oil` | 510 | 543 | 17.5 | 517 | 1.06 | 1 |  |
| `wave10.wb_ny_adj_ictr_gn_zs` | 4.1 | 543 | 2.6 | 4.1 | 0.04 | 1 |  |
| `wave10.wb_sh_sta_pois_p5_fe` | 4.2 | 542 | 2.7 | 4.1 | 0.03 | 1 |  |
| `eia860m.generators` | 93.0 | 542 | 17.4 | 108 | 2.05 | 2 |  |
| `wave10.wb_en_ghg_ch4_ip_mt_ce_ar5` | 4.6 | 542 | 2.8 | 4.2 | 0.04 | 1 |  |
| `wave10.wb_ie_ppi_watr_cd` | 10.0 | 542 | 2.9 | 4.3 | 0.01 | 1 |  |
| `wave10.wb_en_pop_el5m_zs` | 4.1 | 541 | 2.6 | 4.0 | 0.02 | 1 |  |
| `wave10.wb_er_fsh_prod_mt` | 4.2 | 541 | 2.8 | 4.3 | 0.05 | 1 |  |
| `wave10.eu_env_wat_res` | 4.3 | 540 | 3.9 | 4.0 | 0.04 | 1 |  |
| `wave10.wb_en_fsh_thrd_no` | 4.1 | 540 | 2.7 | 4.1 | 0.01 | 1 |  |
| `wave10.wb_en_ghg_co2_mt_ce_ar5` | 4.2 | 540 | 2.6 | 3.8 | 0.07 | 1 |  |
| `wave10.wb_tm_val_ictg_zs_un` | 4.3 | 540 | 2.6 | 4.4 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_n2o_tr_mt_ce_ar5` | 4.3 | 539 | 2.6 | 4.1 | 0.06 | 1 |  |
| `wave10.wb_en_ghg_n2o_ip_mt_ce_ar5` | 4.2 | 539 | 2.6 | 4.2 | 0.07 | 1 |  |
| `wave10.wb_er_h2o_fwdm_zs` | 4.3 | 538 | 2.7 | 4.0 | 0.04 | 1 |  |
| `connect_eu.gb_dso` | 28.4 | 538 | 6.3 | 36.0 | 0.58 | 1 |  |
| `wave10.gb_desnz_elec_la` | 9.6 | 538 | 2.5 | 8.4 | 0.81 | 1 |  |
| `gem.energy_ownership_all_entities` | 3.2 | 537 | 2.5 | 3.0 | 1.61 | 1 |  |
| `wave10.wb_ny_adj_dco2_cd` | 4.2 | 537 | 2.7 | 4.1 | 0.06 | 1 |  |
| `wave10.wb_sh_sta_bass_ru_zs` | 4.1 | 536 | 2.8 | 4.1 | 0.04 | 1 |  |
| `wave10.wb_is_rrs_good_mt_k6` | 4.5 | 536 | 2.7 | 4.2 | 0.02 | 1 |  |
| `wave10.wb_is_shp_gcnw_xq` | 4.6 | 536 | 2.8 | 4.0 | 0.03 | 1 |  |
| `mastr.units_hydro` | 17.0 | 535 | 12.3 | 66.9 | 1.97 | 2 |  |
| `wave10.wb_sh_sta_hygn_ru_zs` | 5.2 | 535 | 3.6 | 4.9 | 0.02 | 1 |  |
| `wave10.wb_eg_gdp_puse_ko_pp_kd` | 4.4 | 535 | 2.7 | 4.8 | 0.05 | 1 |  |
| `wave10.wb_it_net_secr` | 4.2 | 535 | 2.6 | 3.9 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_co2_tr_mt_ce_ar5` | 4.1 | 535 | 2.8 | 4.1 | 0.07 | 1 |  |
| `wave10.wb_ny_adj_dngy_cd` | 4.2 | 535 | 2.6 | 4.0 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_fgas_ip_mt_ce_ar5` | 4.2 | 535 | 2.7 | 4.0 | 0.05 | 1 |  |
| `wave10.gb_census_tenure` | 4.0 | 534 | 2.8 | 4.2 | 0.04 | 1 |  |
| `wave10.eu_env_watuse_rb` | 4.1 | 534 | 2.0 | 4.2 | 0.04 | 1 |  |
| `wave10.wb_ie_ppi_engy_cd` | 4.2 | 534 | 2.8 | 4.1 | 0.02 | 1 |  |
| `power_plants_eu.jrc_performance` | 4.4 | 533 | 2.3 | 4.3 | 0.07 | 1 |  |
| `wave10.wb_en_ghg_co2_lu_df_mt_ce_ar5` | 3.1 | 533 | 2.0 | 3.0 | 0.03 | 1 |  |
| `wave10.wb_nv_agr_totl_zs` | 4.1 | 533 | 2.6 | 4.3 | 0.07 | 1 |  |
| `wave10.wb_en_ghg_ch4_bu_mt_ce_ar5` | 3.9 | 532 | 2.6 | 3.8 | 0.06 | 1 |  |
| `wave10.wb_en_ghg_ch4_zg_ar5` | 4.6 | 531 | 2.9 | 4.2 | 0.07 | 1 |  |
| `wave10.wb_en_mam_thrd_no` | 4.3 | 531 | 2.8 | 4.1 | 0.01 | 1 |  |
| `wave10.wb_er_h2o_intr_k3` | 4.5 | 531 | 2.7 | 4.3 | 0.01 | 1 |  |
| `gem_ownership.coal_mine_ownership` | 530 | 530 | 2.2 | 2.2 | 0.58 | 1 |  |
| `wave10.eu_nrg_cb_cosm` | 9.1 | 528 | 4.6 | 8.4 | 0.10 | 1 |  |
| `wave10.eu_env_ac_aigg_q` | 32.9 | 528 | 4.5 | 31.1 | 0.12 | 1 |  |
| `wave10.eu_env_epea_pap` | 13.1 | 528 | 5.6 | 12.2 | 0.17 | 1 |  |
| `wave10.wb_en_bir_thrd_no` | 4.1 | 527 | 2.8 | 4.0 | 0.01 | 1 |  |
| `wave10.wb_eg_elc_rnwx_zs` | 4.3 | 525 | 2.7 | 4.1 | 0.05 | 1 |  |
| `registers.se` | 19.8 | 523 | 6.4 | 30.3 | 0.47 | 1 |  |
| `wave10.wb_eg_use_comm_fo_zs` | 3.5 | 523 | 2.2 | 3.4 | 0.04 | 1 |  |
| `history.wave9__gb_brownfield_register` | 12.0 | 522 | 8.0 | 19.6 | 4.17 | 4 |  |
| `eia930.interchange` | 492 | 522 | 2.0 | 19.8 | 4.33 | 6 |  |
| `shapes.admin1` | 192 | 521 | 154 | 206 | 0.00 | 0 |  |
| `history.registers__cz` | 8.2 | 520 | 3.7 | 8.2 | 0.77 | 1 |  |
| `wave10.wb_er_fsh_aqua_mt` | 3.6 | 519 | 2.1 | 3.3 | 0.04 | 1 |  |
| `netztransparenz.redispatch` | 6.0 | 519 | 2.3 | 5.9 | 0.42 | 1 |  |
| `wave10.wb_ag_lnd_arbl_zs` | 3.6 | 519 | 2.1 | 3.2 | 0.05 | 1 |  |
| `wave10.eu_nrg_ind_fecf` | 6.4 | 518 | 4.9 | 5.9 | 0.09 | 1 |  |
| `wave10.wb_en_ghg_co2_bu_mt_ce_ar5` | 3.8 | 512 | 2.4 | 3.5 | 0.07 | 1 |  |
| `wave10.wb_ny_adj_dpem_gn_zs` | 3.3 | 508 | 2.2 | 3.2 | 0.05 | 1 |  |
| `main.prices` | 450 | 505 | 85.9 | 173 | 3.29 | 5 | count: TimeoutError: query stopped after 60 s |
| `industrial.lcp` | 279 | 505 | 19.6 | 283 | 4.20 | 3 |  |
| `wave10.eu_nrg_ti_gas` | 47.9 | 504 | 5.8 | 48.2 | 0.08 | 1 |  |
| `gem.energy_ownership_cement_and_concrete_ownership` | 2.4 | 503 | 2.0 | 2.4 | 0.36 | 1 |  |
| `wave10.eu_env_epea_psp` | 26.6 | 500 | 5.0 | 25.7 | 0.05 | 1 |  |
| `wave9.si_surs_heating_settlement` | 493 | 498 | 7.2 | 476 | 0.66 | 1 |  |
| `wave10.eu_nrg_te_sff` | 175 | 497 | 8.3 | 118 | 0.11 | 1 |  |
| `wave10.eu_nrg_cb_em` | 6.3 | 496 | 3.8 | 5.5 | 0.17 | 1 |  |
| `wave9.eu_emodnet_wwtp` | 31.4 | 495 | 14.6 | 66.9 | 1.78 | 1 |  |
| `wave10.eu_env_ac_sd` | 17.5 | 490 | 5.2 | 17.3 | 0.15 | 1 |  |
| `gem.energy_ownership_gas_pipeline_ownership` | 2.5 | 489 | 1.9 | 2.5 | 0.75 | 1 |  |
| `wave10.wb_en_ghg_co2_lu_fl_mt_ce_ar5` | 4.0 | 487 | 2.8 | 3.9 | 0.04 | 1 |  |
| `wave10.eu_nrg_ind_resovsh` | 3.6 | 487 | 3.3 | 3.4 | 0.03 | 1 |  |
| `wave10.wb_eg_imp_cons_zs` | 4.4 | 486 | 3.0 | 4.8 | 0.05 | 1 |  |
| `wave10.eu_road_eqs_zev` | 3.7 | 485 | 3.1 | 3.8 | 0.03 | 1 |  |
| `gem.oil_gas_extraction_field_level_reserves_data` | 2.3 | 484 | 1.8 | 2.3 | 0.13 | 1 |  |
| `wave10.eu_nrg_chp_cpfe` | 20.4 | 483 | 6.2 | 19.5 | 0.31 | 1 |  |
| `wave10.wb_ny_adj_svnx_gn_zs` | 3.4 | 480 | 2.3 | 3.3 | 0.04 | 1 |  |
| `wave10.eu_nrg_ind_re` | 5.1 | 478 | 4.6 | 5.6 | 0.11 | 1 |  |
| `wave10.wb_eg_gdp_puse_ko_pp` | 3.8 | 478 | 2.3 | 3.7 | 0.05 | 1 |  |
| `connect.harmonised` | 61.2 | 475 | 15.5 | 80.0 | 3.65 | 2 |  |
| `history.registers__gb` | 15.1 | 475 | 6.6 | 14.9 | 0.80 | 1 |  |
| `wave10.wb_eg_elc_nucl_zs` | 4.4 | 474 | 2.9 | 4.5 | 0.03 | 1 |  |
| `wave9.dk_energinet_countertrade` | 3.6 | 474 | 2.0 | 3.6 | 0.02 | 1 |  |
| `irena.generation` | 5.6 | 471 | 4.1 | 5.8 | 0.38 | 1 |  |
| `jepx.spot` | 5.0 | 471 | 2.1 | 5.5 | 0.45 | 1 |  |
| `wave10.eu_nrg_ind_pehap` | 24.1 | 469 | 4.7 | 22.2 | 0.19 | 1 |  |
| `wave10.wb_sh_sta_smss_ur_zs` | 3.3 | 469 | 2.2 | 3.0 | 0.03 | 1 |  |
| `wave10.wb_is_rrs_totl_km` | 4.7 | 468 | 3.1 | 3.6 | 0.02 | 1 |  |
| `cenace.pml` | 3.8 | 467 | 1.9 | 3.6 | 0.29 | 1 |  |
| `wave10.wb_en_ghg_tot_zg_ar5` | 3.4 | 466 | 2.1 | 3.3 | 0.07 | 1 |  |
| `wave10.wb_it_net_user_ma_zs` | 3.4 | 466 | 2.1 | 3.3 | 0.02 | 1 |  |
| `wave10.wb_is_shp_good_tu` | 4.3 | 465 | 2.9 | 4.2 | 0.02 | 1 |  |
| `wave10.wb_ny_adj_dngy_gn_zs` | 4.3 | 465 | 2.6 | 4.2 | 0.04 | 1 |  |
| `wave10.eu_road_eqs_lormot` | 4.4 | 465 | 4.0 | 4.2 | 0.03 | 1 |  |
| `gem.energy_ownership_steel_plant_ownership` | 2.4 | 463 | 1.9 | 2.4 | 0.38 | 1 |  |
| `wave10.eu_env_ac_pepsns1` | 111 | 462 | 6.2 | 52.6 | 0.25 | 1 |  |
| `osm.datacentres` | 82.7 | 461 | 24.1 | 31.6 | 0.45 | 2 |  |
| `wave10.eu_env_ac_aibrid_rd` | 85.4 | 460 | 5.0 | 20.1 | 0.19 | 1 |  |
| `registers.fr` | 22.3 | 458 | 5.3 | 14.0 | 1.96 | 1 |  |
| `wave10.wb_eg_elc_loss_zs` | 3.6 | 457 | 2.3 | 3.7 | 0.06 | 1 |  |
| `wave10.wb_eg_elc_coal_zs` | 4.6 | 456 | 2.6 | 4.4 | 0.04 | 1 |  |
| `history.esb_heatmap__transformers` | 15.7 | 456 | 14.9 | 15.5 | 2.23 | 4 |  |
| `wave10.eu_nrg_ti_h2` | 5.3 | 455 | 4.4 | 6.0 | 0.01 | 1 |  |
| `wave10.wb_is_air_good_mt_k1` | 3.4 | 454 | 2.1 | 3.2 | 0.05 | 1 |  |
| `wave10.wb_ny_adj_nnat_gn_zs` | 4.2 | 454 | 2.6 | 3.8 | 0.05 | 1 |  |
| `wave10.wb_ny_adj_dco2_gn_zs` | 4.7 | 454 | 3.3 | 4.3 | 0.05 | 1 |  |
| `wave10.wb_sh_h2o_smdw_ur_zs` | 4.3 | 451 | 2.7 | 4.2 | 0.03 | 1 |  |
| `wave10.wb_er_h2o_fwag_zs` | 3.8 | 451 | 2.5 | 3.8 | 0.04 | 1 |  |
| `gem_ownership.steel_plant_ownership` | 451 | 451 | 1.8 | 1.8 | 0.38 | 1 |  |
| `mastr.locations` | 3.8 | 450 | 3.7 | 3.8 | 0.53 | 2 |  |
| `tri.releases` | 450 | 450 | 2.9 | 2.9 | 0.02 | 1 |  |
| `mastr.units_wind` | 32.4 | 450 | 23.1 | 250 | 9.63 | 8 |  |
| `wave10.wb_ny_adj_aedu_gn_zs` | 3.7 | 449 | 2.4 | 3.9 | 0.04 | 1 |  |
| `wave10.wb_eg_elc_accs_zs` | 3.6 | 449 | 2.2 | 3.4 | 0.03 | 1 |  |
| `wave10.wb_sh_h2o_basw_zs` | 3.5 | 449 | 2.3 | 3.6 | 0.05 | 1 |  |
| `gem_ownership.cement_and_concrete_ownership` | 449 | 449 | 1.9 | 1.9 | 0.36 | 1 |  |
| `wave10.eu_nrg_inf_epc` | 14.3 | 446 | 4.8 | 13.4 | 0.11 | 1 |  |
| `wave10.wb_ip_tmk_nrct` | 3.9 | 446 | 2.3 | 3.6 | 0.02 | 1 |  |
| `wave9.nl_cbs_solar` | 4.9 | 446 | 3.0 | 4.6 | 0.14 | 1 |  |
| `wave10.wb_ie_ppi_tran_cd` | 3.5 | 446 | 2.4 | 3.3 | 0.01 | 1 |  |
| `wave10.wb_sp_urb_totl_in_zs` | 3.1 | 445 | 2.2 | 3.0 | 0.07 | 1 |  |
| `wave10.wb_en_pop_slum_ur_zs` | 4.0 | 444 | 2.5 | 4.3 | 0.02 | 1 |  |
| `wave9.eu_eea_wei` | 444 | 444 | 1.8 | 1.8 | 0.40 | 1 |  |
| `wave9.se_svk_reserves` | 353 | 444 | 2.4 | 49.3 | 12.57 | 7 |  |
| `power_plants_eu.jrc_units` | 26.0 | 444 | 18.5 | 34.3 | 0.25 | 1 |  |
| `wave10.wb_en_ghg_co2_zg_ar5` | 3.4 | 443 | 2.2 | 3.5 | 0.07 | 1 |  |
| `wave10.wb_iq_cpa_pubs_xq` | 4.3 | 443 | 3.2 | 4.3 | 0.01 | 1 |  |
| `wave10.wb_en_ghg_all_lu_mt_ce_ar5` | 4.3 | 443 | 2.6 | 4.0 | 0.05 | 1 |  |
| `wave10.wb_en_pop_el5m_ur_zs` | 3.7 | 442 | 2.3 | 3.8 | 0.02 | 1 |  |
| `wave10.wb_ag_lnd_totl_ur_k2` | 3.7 | 442 | 2.5 | 3.6 | 0.02 | 1 |  |
| `wave9.eu_emodnet_port_goods` | 23.8 | 442 | 8.5 | 280 | 0.66 | 1 |  |
| `wave9.eu_ev_stock_nuts2` | 3.9 | 442 | 2.8 | 3.7 | 0.05 | 1 |  |
| `wave10.gb_desnz_gas_la` | 6.0 | 441 | 1.9 | 5.4 | 0.57 | 1 |  |
| `wave10.wb_eg_elc_accs_ru_zs` | 4.3 | 441 | 2.8 | 4.2 | 0.03 | 1 |  |
| `wave10.wb_it_net_bbnd_p2` | 3.8 | 440 | 2.4 | 3.8 | 0.05 | 1 |  |
| `wave10.wb_sp_pop_grow` | 3.8 | 440 | 2.5 | 3.9 | 0.07 | 1 |  |
| `wave10.eu_nrg_stk_oil` | 8.6 | 439 | 5.4 | 8.2 | 0.10 | 1 |  |
| `wave10.wb_en_ghg_co2_ic_mt_ce_ar5` | 4.5 | 438 | 3.1 | 4.6 | 0.07 | 1 |  |
| `wave10.wb_tx_val_fuel_zs_un` | 3.8 | 438 | 2.3 | 3.5 | 0.05 | 1 |  |
| `wave10.wb_en_ghg_co2_lu_os_mt_ce_ar5` | 3.2 | 438 | 2.1 | 3.3 | 0.02 | 1 |  |
| `gem_ownership.gas_pipeline_ownership` | 438 | 438 | 1.9 | 1.9 | 0.76 | 1 |  |
| `wave10.wb_en_ghg_ch4_ic_mt_ce_ar5` | 3.4 | 438 | 2.1 | 3.3 | 0.06 | 1 |  |
| `wave10.gb_desnz_ghg_la` | 266 | 437 | 2.3 | 17.7 | 2.97 | 3 |  |
| `gem.energy_ownership_asset_ownership` | 2.6 | 436 | 2.1 | 2.9 | 0.82 | 1 |  |
| `wave10.wb_eg_elc_rnew_zs` | 3.9 | 436 | 2.1 | 3.4 | 0.06 | 1 |  |
| `wave10.wb_ie_ppn_engy_cd` | 4.3 | 436 | 2.8 | 4.3 | 0.02 | 1 |  |
| `wave10.wb_en_atm_pm25_mc_t1_zs` | 4.1 | 436 | 2.5 | 3.9 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_n2o_fe_mt_ce_ar5` | 3.2 | 435 | 2.1 | 3.3 | 0.05 | 1 |  |
| `wave9.de_bfee_abwaerme` | 293 | 435 | 12.8 | 16.9 | 2.36 | 3 |  |
| `wave10.wb_sh_sta_hygn_ur_zs` | 3.9 | 435 | 2.6 | 3.8 | 0.02 | 1 |  |
| `wave10.wb_ny_adj_dmin_gn_zs` | 3.9 | 434 | 2.4 | 4.0 | 0.04 | 1 |  |
| `wave10.eu_road_eqr_zev` | 3.4 | 434 | 2.5 | 3.2 | 0.03 | 1 |  |
| `wave10.wb_en_ghg_ch4_mt_ce_ar5` | 4.2 | 434 | 2.4 | 3.9 | 0.07 | 1 |  |
| `gem.energy_ownership_iron_mine_ownership` | 3.1 | 434 | 2.5 | 3.1 | 0.19 | 1 |  |
| `wave9.eu_heat_pumps` | 27.5 | 433 | 4.5 | 5.6 | 0.03 | 1 |  |
| `euets.eea_link` | 33.7 | 433 | 15.1 | 53.9 | 0.40 | 1 |  |
| `history.netztransparenz__redispatch` | 6.5 | 432 | 2.4 | 6.2 | 0.42 | 1 |  |
| `wave10.wb_er_h2o_fwtl_zs` | 4.2 | 432 | 2.7 | 4.3 | 0.04 | 1 |  |
| `wave10.wb_ic_frm_bnks_zs` | 3.2 | 432 | 2.1 | 3.4 | 0.02 | 1 |  |
| `wave9.gb_ons_income_msoa` | 3.5 | 432 | 2.2 | 3.4 | 0.10 | 1 |  |
| `wave9.cz_csu_sldb_heating_mode` | 7.2 | 432 | 2.1 | 7.3 | 0.26 | 1 |  |
| `wave9.eu_degree_days` | 6.6 | 432 | 3.6 | 5.4 | 0.21 | 1 |  |
| `wave10.wb_en_clc_mdat_zs` | 3.5 | 430 | 2.2 | 4.0 | 0.01 | 1 |  |
| `wave10.wb_ag_lnd_agri_k2` | 4.0 | 430 | 2.6 | 3.9 | 0.03 | 1 |  |
| `wave10.wb_se_prm_cmpt_zs` | 3.4 | 430 | 2.2 | 3.3 | 0.04 | 1 |  |
| `wave10.eu_env_epea_cint` | 9.0 | 430 | 5.6 | 8.9 | 0.08 | 1 |  |
| `wave10.wb_ag_lnd_frst_k2` | 3.8 | 430 | 2.5 | 4.2 | 0.03 | 1 |  |
| `wave9.be_fluvius_consumption` | 368 | 428 | 2.4 | 18.4 | 5.90 | 5 |  |
| `wave10.eu_cei_gsr010` | 80.1 | 428 | 4.4 | 6.9 | 0.04 | 1 |  |
| `wave10.wb_sh_sta_bass_zs` | 3.9 | 428 | 2.4 | 3.8 | 0.05 | 1 |  |
| `wave10.eu_nrg_cb_rw` | 66.1 | 427 | 7.8 | 66.6 | 0.34 | 1 |  |
| `wave10.wb_ny_adj_svng_gn_zs` | 3.8 | 427 | 2.4 | 4.0 | 0.04 | 1 |  |
| `wave10.wb_sh_sta_pois_p5` | 3.9 | 426 | 2.4 | 3.8 | 0.03 | 1 |  |
| `wave10.wb_en_ghg_n2o_ic_mt_ce_ar5` | 4.6 | 426 | 2.9 | 4.2 | 0.06 | 1 |  |
| `gem.methane_emitters_oil_and_gas_extraction_areas` | 34.0 | 426 | 24.3 | 24.8 | 0.27 | 1 |  |
| `wave10.eu_nrg_cb_h2` | 3.8 | 426 | 3.7 | 4.0 | 0.01 | 1 |  |
| `wave9.eu_network_costs` | 8.2 | 426 | 4.8 | 8.4 | 0.12 | 1 |  |
| `wave10.eu_nrg_cb_e` | 7.4 | 426 | 4.7 | 7.8 | 0.12 | 1 |  |
| `wave10.wb_ag_lnd_el5m_ur_zs` | 3.8 | 426 | 2.5 | 3.6 | 0.02 | 1 |  |
| `gem_ownership.coal_plant_ownership` | 425 | 425 | 2.3 | 2.3 | 0.02 | 1 |  |
| `wave10.wb_ag_yld_crel_kg` | 4.5 | 425 | 2.9 | 5.1 | 0.04 | 1 |  |
| `wave10.eu_nrg_ind_ebmg` | 6.1 | 425 | 4.0 | 6.4 | 0.00 | 1 |  |
| `wave10.wb_eg_use_pcap_kg_oe` | 3.9 | 425 | 2.3 | 3.6 | 0.06 | 1 |  |
| `wave10.wb_er_ptd_totl_zs` | 4.7 | 425 | 3.4 | 4.2 | 0.02 | 1 |  |
| `wave10.eu_nrg_te_gasm` | 190 | 425 | 8.5 | 258 | 0.41 | 1 |  |
| `wave10.wb_ny_gdp_ngas_rt_zs` | 3.8 | 424 | 2.6 | 3.8 | 0.04 | 1 |  |
| `wave10.wb_sh_sta_maln_zs` | 3.9 | 424 | 2.8 | 4.1 | 0.01 | 1 |  |
| `mastr.operators` | 5.9 | 424 | 5.9 | 7.5 | 0.27 | 2 |  |
| `ev_eu.de` | 82.6 | 423 | 11.4 | 112 | 4.46 | 4 |  |
| `wave10.wb_er_lnd_ptld_zs` | 3.6 | 423 | 2.4 | 3.6 | 0.02 | 1 |  |
| `wave10.wb_en_ghg_n2o_wa_mt_ce_ar5` | 3.9 | 422 | 2.7 | 4.0 | 0.06 | 1 |  |
| `wave10.wb_sh_sta_pois_p5_ma` | 4.0 | 422 | 2.7 | 4.2 | 0.03 | 1 |  |
| `wave10.wb_en_ghg_co2_pc_ce_ar5` | 4.2 | 422 | 2.8 | 4.4 | 0.07 | 1 |  |
| `wave10.gb_census_travel_distance` | 4.2 | 422 | 3.0 | 4.2 | 0.03 | 1 |  |
| `wave10.wb_sp_urb_grow` | 4.3 | 421 | 2.8 | 4.6 | 0.07 | 1 |  |
| `wave10.wb_tm_val_fuel_zs_un` | 4.2 | 421 | 2.8 | 4.0 | 0.06 | 1 |  |
| `wave10.wb_sh_sta_smss_zs` | 4.3 | 420 | 2.9 | 4.3 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_n2o_pi_mt_ce_ar5` | 3.7 | 420 | 2.3 | 3.6 | 0.06 | 1 |  |
| `wave10.wb_en_ghg_co2_rt_gdp_kd` | 3.0 | 420 | 2.0 | 3.0 | 0.07 | 1 |  |
| `wave10.wb_en_ghg_n2o_ag_mt_ce_ar5` | 4.2 | 420 | 2.9 | 4.1 | 0.06 | 1 |  |
| `wave10.eu_road_eqr_lormot` | 4.4 | 419 | 3.8 | 4.9 | 0.02 | 1 |  |
| `wave10.wb_ic_frm_outg_zs` | 4.2 | 419 | 2.7 | 4.2 | 0.01 | 1 |  |
| `wave10.wb_it_net_secr_p6` | 4.2 | 418 | 3.1 | 4.4 | 0.04 | 1 |  |
| `wave10.wb_ny_gdp_totl_rt_zs` | 4.1 | 418 | 2.4 | 4.0 | 0.06 | 1 |  |
| `wave10.wb_tx_val_mmtl_zs_un` | 4.5 | 418 | 2.8 | 4.4 | 0.06 | 1 |  |
| `wave10.wb_er_h2o_fwtl_k3` | 3.2 | 418 | 2.1 | 3.1 | 0.04 | 1 |  |
| `wave10.eu_env_ac_mfa` | 76.7 | 417 | 14.0 | 75.1 | 2.05 | 1 |  |
| `wave10.wb_eg_cft_accs_zs` | 4.2 | 416 | 2.8 | 3.9 | 0.02 | 1 |  |
| `nl_capacity.areas` | 8.4 | 416 | 8.6 | 424 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_sff` | 108 | 416 | 11.1 | 108 | 0.34 | 1 |  |
| `wave9.de_regelleistung` | 396 | 415 | 3.1 | 17.6 | 2.48 | 4 |  |
| `ev_eu.nl` | 61.1 | 414 | 12.4 | 60.6 | 3.37 | 3 |  |
| `wave10.wb_en_ghg_all_pc_ce_ar5` | 3.2 | 412 | 2.1 | 3.0 | 0.07 | 1 |  |
| `wave9.us_usgs_nshm` | 321 | 411 | 44.2 | 307 | 9.83 | 6 |  |
| `wave10.eu_nrg_ind_pehcf` | 163 | 408 | 14.3 | 165 | 0.71 | 1 |  |
| `wave10.eu_nrg_d_serq_n` | 16.4 | 407 | 5.1 | 15.9 | 0.22 | 1 |  |
| `wave10.eu_nrg_cb_bm` | 3.9 | 406 | 3.3 | 3.8 | 0.04 | 1 |  |
| `wave10.eu_env_watres_rb` | 3.7 | 406 | 2.0 | 3.2 | 0.07 | 1 |  |
| `wave10.eu_env_esst_ggcp` | 128 | 406 | 5.5 | 62.8 | 0.14 | 1 |  |
| `wave10.eu_env_ac_cepsgc1` | 19.1 | 406 | 5.8 | 18.2 | 0.09 | 1 |  |
| `wave10.eu_nrg_chdd_m` | 4.2 | 405 | 3.5 | 4.1 | 0.05 | 1 |  |
| `wave10.wb_er_fsh_capt_mt` | 4.3 | 404 | 2.8 | 4.2 | 0.05 | 1 |  |
| `wave10.wb_en_ghg_ch4_tr_mt_ce_ar5` | 3.3 | 404 | 2.1 | 3.0 | 0.06 | 1 |  |
| `wave10.wb_ny_adj_dfor_gn_zs` | 3.3 | 404 | 2.1 | 3.3 | 0.03 | 1 |  |
| `osm.eu_buses` | 19.8 | 404 | 6.5 | 46.7 | 0.92 | 2 |  |
| `wave10.eu_nrg_cb_gas` | 48.0 | 402 | 7.2 | 47.3 | 0.29 | 1 |  |
| `wave10.wb_en_atm_pm25_mc_t3_zs` | 3.7 | 402 | 2.2 | 3.2 | 0.02 | 1 |  |
| `wave10.wb_sh_med_cmhw_p3` | 3.7 | 402 | 2.9 | 4.0 | 0.01 | 1 |  |
| `wave10.wb_bx_gsr_ccis_zs` | 3.5 | 400 | 2.2 | 3.2 | 0.05 | 1 |  |
| `wave10.wb_ie_ppn_tran_cd` | 3.3 | 399 | 2.2 | 3.3 | 0.01 | 1 |  |
| `wave10.eu_env_ac_taxind2` | 89.4 | 398 | 12.2 | 89.5 | 0.60 | 1 |  |
| `gem.energy_ownership_coal_mine_ownership` | 2.9 | 398 | 2.3 | 2.8 | 0.51 | 1 |  |
| `gem_ownership.all_entities` | 398 | 398 | 2.4 | 2.4 | 1.61 | 1 |  |
| `wave10.wb_eg_elc_rnwx_kh` | 4.7 | 397 | 2.8 | 4.4 | 0.03 | 1 |  |
| `wave9.us_iso_as_prices` | 306 | 396 | 4.0 | 248 | 0.07 | 1 |  |
| `wave10.wb_bx_klt_dinv_wd_gd_zs` | 4.6 | 396 | 2.7 | 4.3 | 0.07 | 1 |  |
| `wave10.wb_sh_sta_odfc_ru_zs` | 4.1 | 396 | 2.8 | 4.0 | 0.04 | 1 |  |
| `wave10.wb_ag_lnd_el5m_ru_k2` | 4.0 | 396 | 2.6 | 4.0 | 0.02 | 1 |  |
| `wave10.eu_env_ac_pepssp1` | 16.4 | 395 | 4.8 | 15.6 | 0.06 | 1 |  |
| `wave10.eu_nrg_ind_urtd` | 7.2 | 393 | 3.6 | 6.4 | 0.08 | 1 |  |
| `app.eu_lines` | 9.7 | 393 | 7.8 | 380 | 0.00 | 0 |  |
| `wave10.eu_env_esst_cepggcp` | 71.3 | 389 | 6.7 | 70.0 | 0.10 | 1 |  |
| `wave10.eu_nrg_ti_sff` | 216 | 388 | 12.1 | 274 | 0.17 | 1 |  |
| `wave10.wb_ag_lnd_prcp_mm` | 4.7 | 388 | 2.6 | 4.1 | 0.01 | 1 |  |
| `wave9.eu_jrc_coastal_flood` | 35.7 | 385 | 35.0 | 35.3 | 1.46 | 1 |  |
| `wave9.sk_susr_energy_consumption_okres` | 5.0 | 384 | 2.0 | 3.7 | 0.04 | 1 |  |
| `wave10.wb_en_hpt_thrd_no` | 4.0 | 384 | 2.7 | 4.1 | 0.01 | 1 |  |
| `wave9.fr_ore_solar_commune` | 383 | 383 | 2.6 | 2.6 | 0.02 | 1 |  |
| `wave10.wb_it_mlt_main` | 4.4 | 383 | 2.7 | 4.2 | 0.03 | 1 |  |
| `wave10.wb_ny_adj_dres_gn_zs` | 4.3 | 383 | 2.8 | 4.3 | 0.05 | 1 |  |
| `wave10.eu_nrg_ind_stjpjss` | 4.7 | 382 | 4.2 | 4.5 | 0.00 | 1 |  |
| `ev_eu.fr` | 119 | 380 | 18.5 | 122 | 3.90 | 4 |  |
| `history.connect_eu__gb_dso` | 28.9 | 380 | 6.3 | 30.0 | 0.58 | 1 |  |
| `wave10.wb_en_ghg_ch4_ag_mt_ce_ar5` | 4.6 | 378 | 2.8 | 4.4 | 0.06 | 1 |  |
| `wave10.wb_sh_dyn_mort` | 4.6 | 378 | 3.0 | 4.7 | 0.03 | 1 |  |
| `wave10.wb_ny_gdp_coal_rt_zs` | 4.5 | 378 | 2.9 | 4.4 | 0.04 | 1 |  |
| `gem_ownership.gas_plant_ownership` | 377 | 377 | 2.2 | 2.2 | 0.02 | 1 |  |
| `wave9.eu_egdi_minerals` | 62.5 | 376 | 58.3 | 69.1 | 1.70 | 1 |  |
| `wave10.wb_en_atm_pm25_mc_zs` | 4.6 | 374 | 2.9 | 4.3 | 0.02 | 1 |  |
| `wave10.eu_nrg_ti_bio` | 93.0 | 374 | 8.2 | 93.3 | 0.08 | 1 |  |
| `wave10.wb_en_ghg_ch4_wa_mt_ce_ar5` | 4.4 | 372 | 2.7 | 4.3 | 0.07 | 1 |  |
| `wave10.wb_sh_sta_airp_p5` | 4.4 | 372 | 2.8 | 4.4 | 0.01 | 1 |  |
| `wave10.wb_ie_ppn_watr_cd` | 4.0 | 371 | 2.7 | 3.9 | 0.01 | 1 |  |
| `wave10.wb_is_air_psgr` | 3.9 | 371 | 2.6 | 3.9 | 0.04 | 1 |  |
| `wave10.wb_eg_use_comm_gd_pp_kd` | 4.5 | 369 | 2.8 | 4.7 | 0.05 | 1 |  |
| `wave10.eu_nrg_te_bio` | 96.9 | 369 | 7.7 | 93.0 | 0.07 | 1 |  |
| `wave10.eu_nrg_ind_hptctc` | 24.8 | 369 | 5.0 | 22.9 | 0.02 | 1 |  |
| `wave10.wb_it_net_user_zs` | 4.4 | 368 | 2.7 | 4.4 | 0.05 | 1 |  |
| `wave10.wb_ny_adj_dkap_cd` | 4.4 | 366 | 2.8 | 4.2 | 0.05 | 1 |  |
| `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` | 4.0 | 365 | 2.6 | 4.1 | 0.06 | 1 |  |
| `wave9.ie_eirgrid_dispatch_down` | 4.1 | 358 | 2.0 | 3.9 | 0.12 | 1 |  |
| `wave9.eu_renewable_capacity` | 5.5 | 353 | 4.2 | 5.2 | 0.04 | 1 |  |
| `rollups.overture_power__sites_r7` | 9.0 | 272 | 5.3 | 261 | 0.00 | 0 |  |
| `rollups.overture_transport__segments_r7` | 3.6 | 247 | 3.5 | 235 | 0.00 | 0 |  |
| `rollups.overture_power__sites_r6` | 4.2 | 209 | 4.3 | 153 | 0.00 | 0 |  |
| `wave9.eu_tent_network` | 8.3 | 204 | 6.7 | 193 | 0.00 | 0 |  |
| `wave10.eu_ten00108` | 2.4 | 199 | 1.7 | 2.2 | 0.00 | 0 |  |
| `shapes.nuts` | 3.8 | 195 | 2.6 | 189 | 0.00 | 0 |  |
| `rollups.overture_power__lines_r7` | 4.2 | 168 | 4.1 | 155 | 0.00 | 0 |  |
| `wave9.gb_pins_dco` | 8.9 | 161 | 7.7 | 8.8 | 0.00 | 0 |  |
| `wave9.ie_cso_dc_consumption` | 3.9 | 140 | 2.2 | 3.3 | 0.00 | 0 |  |
| `rollups.overture_power__lines_r6` | 4.6 | 125 | 3.8 | 123 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_mopeds` | 2.4 | 122 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_spurp` | 2.3 | 112 | 1.6 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_carmot` | 2.2 | 110 | 1.8 | 2.3 | 0.00 | 0 |  |
| `wave9.gb_ssen_opendata` | 7.1 | 110 | 6.3 | 34.6 | 0.00 | 0 |  |
| `rollups.overture_transport__segments_r6` | 5.3 | 106 | 2.4 | 95.6 | 0.00 | 0 |  |
| `ev_eu.ee` | 3.4 | 105 | 3.0 | 15.9 | 0.00 | 0 |  |
| `connect_eu.es_dso` | 3.4 | 100 | 2.9 | 19.9 | 0.00 | 0 |  |
| `app.us_plants` | 18.5 | 99.1 | 3.0 | 100 | 0.00 | 0 |  |
| `wave9.fi_paavo` | 10.2 | 98.0 | 9.2 | 28.3 | 0.00 | 0 |  |
| `wave9.gb_ne_alc` | 11.8 | 95.3 | 9.0 | 70.6 | 0.00 | 0 |  |
| `entsoe.imbalance_price` | 57.5 | 91.4 | 52.2 | 103 | 0.00 | 0 | count: TimeoutError: query stopped after 60 s |
| `rollups.overture_power__sites_r5` | 3.4 | 90.5 | 3.4 | 82.2 | 0.00 | 0 |  |
| `wave10.eu_rail_if_traff` | 2.3 | 88.3 | 1.7 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_cei_pc040` | 2.4 | 83.5 | 1.6 | 2.1 | 0.00 | 0 |  |
| `wave9.eu_nuclear_capacity` | 2.6 | 82.0 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_40` | 2.3 | 77.4 | 1.8 | 2.3 | 0.00 | 0 |  |
| `rollups.mastr__units_solar_r7` | 3.5 | 76.2 | 2.4 | 53.2 | 0.00 | 0 |  |
| `rollups.mastr__units_solar_r6` | 14.8 | 73.4 | 2.6 | 44.7 | 0.00 | 0 |  |
| `wave9.eu_emodnet_desalination` | 37.4 | 71.8 | 29.0 | 82.8 | 0.00 | 0 |  |
| `rollups.overture_power__lines_r5` | 3.0 | 69.7 | 2.4 | 59.7 | 0.00 | 0 |  |
| `wave9.fr_odre_balancing_volumes` | 3.5 | 67.3 | 1.5 | 2.7 | 0.00 | 0 |  |
| `wave9.us_ira_energy_communities` | 46.4 | 65.8 | 37.9 | 54.4 | 0.00 | 0 |  |
| `app.world_plants` | 20.5 | 64.9 | 4.1 | 62.4 | 0.00 | 0 |  |
| `rollups.overture_transport__segments_r5` | 3.5 | 64.1 | 3.2 | 61.2 | 0.00 | 0 |  |
| `shapes.admin1_simplified` | 13.0 | 63.6 | 11.9 | 63.0 | 0.00 | 0 |  |
| `hydrogen.projects` | 17.0 | 63.4 | 17.2 | 28.3 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_50` | 2.3 | 63.4 | 1.6 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_cei_gsr011` | 2.6 | 62.6 | 1.7 | 2.5 | 0.00 | 0 |  |
| `rollups.wave9__de_zensus_heating_r7` | 20.3 | 59.1 | 13.8 | 55.5 | 0.00 | 0 |  |
| `app.data_centres` | 24.7 | 57.9 | 22.6 | 50.3 | 0.00 | 0 |  |
| `wave9.us_fhwa_afc` | 36.1 | 49.4 | 29.1 | 47.2 | 0.00 | 0 |  |
| `app.eu_substations` | 27.0 | 48.6 | 18.5 | 32.9 | 0.00 | 0 |  |
| `wave9.us_boem_active_leases` | 8.9 | 48.4 | 8.6 | 47.7 | 0.00 | 0 |  |
| `mastr.units_other` | 6.7 | 48.2 | 6.0 | 47.0 | 0.00 | 0 |  |
| `wave9.eu_emodnet_pipelines` | 10.2 | 47.0 | 9.9 | 44.0 | 0.00 | 0 |  |
| `connect_eu.lu` | 7.9 | 46.0 | 5.8 | 38.3 | 0.00 | 0 |  |
| `tyndp.projects` | 4.2 | 44.9 | 3.9 | 41.0 | 0.00 | 0 |  |
| `co2stop.hydrocarbon_storage_units` | 33.6 | 42.3 | 33.6 | 35.3 | 0.00 | 0 |  |
| `wave9.us_boem_wind_leases` | 13.1 | 41.8 | 9.9 | 37.3 | 0.00 | 0 |  |
| `co2stop.hydrocarbon_traps` | 36.1 | 41.3 | 34.4 | 37.2 | 0.00 | 0 |  |
| `wave9.gb_defra_aurn` | 18.9 | 41.1 | 17.9 | 26.2 | 0.00 | 0 |  |
| `wave9.us_cpc_degree_days` | 5.2 | 38.3 | 5.1 | 22.8 | 0.00 | 0 |  |
| `us_lmp.day_ahead` | 16.2 | 37.4 | 14.5 | 42.1 | 0.00 | 0 | count: TimeoutError: query stopped after 60 s |
| `ghgrp.facilities` | 3.8 | 36.9 | 3.6 | 28.2 | 0.00 | 0 |  |
| `ev_eu.cz` | 2.8 | 36.3 | 2.2 | 23.1 | 0.00 | 0 |  |
| `ev_eu.si` | 2.8 | 35.4 | 2.7 | 22.7 | 0.00 | 0 |  |
| `gem.coal_mines_closed_mines` | 29.9 | 35.0 | 24.5 | 24.7 | 0.00 | 0 |  |
| `rollups.wave9__de_zensus_heating_r6` | 16.2 | 34.4 | 16.6 | 26.8 | 0.00 | 0 |  |
| `mastr.units_nuclear` | 10.1 | 34.2 | 5.4 | 28.3 | 0.00 | 0 |  |
| `wave9.us_drought_monitor` | 12.4 | 32.3 | 8.4 | 28.1 | 0.00 | 0 |  |
| `gem.oil_gas_extraction_project_level_main_data` | 24.7 | 32.0 | 22.5 | 23.1 | 0.00 | 0 |  |
| `ev_eu.pl` | 2.9 | 31.9 | 2.8 | 18.5 | 0.00 | 0 |  |
| `co2stop.hydrocarbon_formations` | 20.7 | 31.7 | 20.5 | 22.5 | 0.00 | 0 |  |
| `wave10.gb_desnz_ren_generation_la` | 31.7 | 31.7 | 1.5 | 1.5 | 0.00 | 0 |  |
| `rollups.mastr__units_storage_r6` | 4.3 | 31.3 | 2.9 | 28.8 | 0.00 | 0 |  |
| `gem.methane_emitters_coal_mines_non_closed` | 22.8 | 31.1 | 20.7 | 22.1 | 0.00 | 0 |  |
| `wave9.us_eia_gas_processing` | 3.9 | 30.3 | 3.0 | 14.5 | 0.00 | 0 |  |
| `rollups.mastr__units_storage_r5` | 3.4 | 30.2 | 3.1 | 28.2 | 0.00 | 0 |  |
| `history.connect_eu__cz` | 14.4 | 30.1 | 14.0 | 23.0 | 0.00 | 0 |  |
| `app.eu_plants` | 14.1 | 29.7 | 2.0 | 30.0 | 0.00 | 0 |  |
| `wave9.eu_internet_households` | 2.7 | 29.4 | 2.2 | 2.6 | 0.00 | 0 |  |
| `gem.coal_terminals_terminals` | 21.5 | 29.2 | 20.1 | 21.3 | 0.00 | 0 |  |
| `co2stop.hydrocarbon_traps_temp` | 26.9 | 28.6 | 26.4 | 27.8 | 0.00 | 0 |  |
| `wave10.gb_census_bedrooms` | 2.2 | 28.2 | 1.6 | 2.1 | 0.00 | 0 |  |
| `ev_eu.dk` | 3.3 | 27.6 | 3.0 | 19.0 | 0.00 | 0 |  |
| `history.registers__ie` | 18.8 | 27.3 | 18.1 | 19.1 | 0.00 | 0 |  |
| `wave9.eu_emodnet_ocean_energy` | 6.6 | 27.2 | 4.3 | 23.3 | 0.00 | 0 |  |
| `ev_eu.sk` | 3.6 | 27.1 | 2.7 | 22.6 | 0.00 | 0 |  |
| `connect_eu.cz` | 14.4 | 27.0 | 14.0 | 21.1 | 0.00 | 0 |  |
| `rollups.wave9__de_zensus_heating_r5` | 18.6 | 27.0 | 17.7 | 24.9 | 0.00 | 0 |  |
| `history.capareseau__substations` | 5.0 | 26.7 | 4.3 | 25.6 | 0.00 | 0 |  |
| `gem.coal_mines_non_closed_mines` | 26.3 | 26.4 | 23.3 | 25.6 | 0.00 | 0 |  |
| `gem.methane_emitters_oil_and_gas_reserves` | 18.9 | 25.7 | 17.3 | 18.5 | 0.00 | 0 |  |
| `wave9.us_eia_product_terminals` | 3.2 | 25.6 | 3.0 | 22.7 | 0.00 | 0 |  |
| `ev_eu.lv` | 3.1 | 25.4 | 2.6 | 23.7 | 0.00 | 0 |  |
| `rollups.mastr__units_solar_r5` | 3.5 | 25.4 | 3.3 | 30.4 | 0.00 | 0 |  |
| `gem.methane_emitters_lng_terminals` | 23.4 | 25.1 | 22.7 | 25.4 | 0.00 | 0 |  |
| `co2stop.hydrocarbon_traps1` | 24.1 | 25.0 | 23.4 | 24.1 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_hpind` | 2.4 | 25.0 | 1.7 | 2.3 | 0.00 | 0 |  |
| `capareseau.substations` | 4.2 | 24.8 | 3.3 | 17.9 | 0.00 | 0 |  |
| `connect_eu.lt` | 18.5 | 24.7 | 17.9 | 21.8 | 0.00 | 0 |  |
| `ev_eu.hu` | 2.9 | 24.3 | 3.1 | 22.8 | 0.00 | 0 |  |
| `history.connect_eu__es_dso` | 3.7 | 24.2 | 3.0 | 15.1 | 0.00 | 0 |  |
| `gem.gas_infrastructure_lng_terminals` | 23.1 | 23.6 | 21.8 | 22.3 | 0.00 | 0 |  |
| `ev_eu.fi` | 3.4 | 23.2 | 2.8 | 19.6 | 0.00 | 0 |  |
| `ev_eu.cy` | 2.7 | 23.0 | 2.7 | 22.8 | 0.00 | 0 |  |
| `wave9.eu_emodnet_wind_farms` | 4.4 | 22.9 | 3.2 | 9.1 | 0.00 | 0 |  |
| `wave9.us_epa_lmop_landfills` | 4.3 | 22.9 | 3.6 | 20.8 | 0.00 | 0 |  |
| `wave9.us_nexrad` | 14.6 | 22.7 | 12.8 | 26.3 | 0.00 | 0 |  |
| `ev_eu.se` | 3.3 | 22.6 | 2.8 | 14.2 | 0.00 | 0 |  |
| `ev_eu.lu` | 3.1 | 22.5 | 2.9 | 23.7 | 0.00 | 0 |  |
| `history.connect_eu__mt` | 14.2 | 22.3 | 13.3 | 13.8 | 0.00 | 0 |  |
| `wave9.us_epa_lmop` | 3.4 | 22.0 | 2.6 | 11.2 | 0.00 | 0 |  |
| `app.eu_prices` | 2.4 | 21.9 | 1.6 | 2.1 | 0.00 | 0 |  |
| `shapes.bidding_zones` | 9.8 | 21.9 | 8.8 | 18.5 | 0.00 | 0 |  |
| `entsoe.units` | 3.4 | 21.7 | 2.9 | 28.3 | 0.00 | 0 |  |
| `rollups.mastr__units_storage_r7` | 4.0 | 21.7 | 1.8 | 24.7 | 0.00 | 0 |  |
| `wave10.eu_cei_srm040` | 2.8 | 21.3 | 2.7 | 19.6 | 0.00 | 0 |  |
| `entsoe.congestion_costs` | 2.0 | 21.2 | 1.8 | 2.7 | 0.00 | 0 |  |
| `ev_eu.ro` | 2.7 | 20.9 | 2.4 | 16.7 | 0.00 | 0 |  |
| `entsoe.capacity` | 2.3 | 20.7 | 2.4 | 2.7 | 0.00 | 0 |  |
| `ev_eu.ie` | 3.4 | 20.5 | 3.0 | 20.4 | 0.00 | 0 |  |
| `connect_eu.ee` | 3.1 | 20.4 | 2.4 | 14.8 | 0.00 | 0 |  |
| `ev_eu.es` | 2.8 | 20.4 | 2.4 | 19.0 | 0.00 | 0 |  |
| `history.registers__pt` | 4.3 | 20.3 | 3.8 | 20.3 | 0.00 | 0 |  |
| `osm.cables` | 9.3 | 19.7 | 2.7 | 14.3 | 0.00 | 0 |  |
| `history.connect_eu__lt` | 19.2 | 19.5 | 18.2 | 19.8 | 0.00 | 0 |  |
| `wave9.us_eia_gas_storage` | 4.1 | 19.3 | 3.6 | 18.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_e` | 2.3 | 19.2 | 2.1 | 2.3 | 0.00 | 0 |  |
| `wave9.us_eia_crude_rail` | 12.6 | 19.2 | 11.6 | 18.2 | 0.00 | 0 |  |
| `history.connect_eu__bg` | 3.5 | 19.1 | 2.6 | 12.1 | 0.00 | 0 |  |
| `wave9.us_eia_ethanol` | 3.8 | 19.0 | 3.1 | 22.2 | 0.00 | 0 |  |
| `wave9.gb_hnpd` | 10.4 | 18.7 | 9.6 | 17.1 | 0.00 | 0 |  |
| `ev_eu.bg` | 3.7 | 18.5 | 2.9 | 18.5 | 0.00 | 0 |  |
| `ev_eu.hr` | 2.8 | 18.3 | 2.4 | 19.4 | 0.00 | 0 |  |
| `ev_eu.lt` | 3.0 | 18.2 | 2.4 | 18.2 | 0.00 | 0 |  |
| `registers.ie` | 12.1 | 17.9 | 10.1 | 13.8 | 0.00 | 0 |  |
| `prepared.answers` | 4.6 | 17.5 | 1.3 | 1.6 | 0.00 | 0 |  |
| `ev_eu.pt` | 4.0 | 17.3 | 3.4 | 16.7 | 0.00 | 0 |  |
| `wave9.dk_district_heating` | 8.3 | 17.3 | 3.2 | 7.0 | 0.00 | 0 |  |
| `wave9.eu_salt_caverns` | 9.8 | 17.2 | 8.8 | 14.3 | 0.00 | 0 |  |
| `registers.pt` | 3.6 | 16.3 | 3.1 | 14.2 | 0.00 | 0 |  |
| `connect_eu.dk` | 14.6 | 16.2 | 15.0 | 15.7 | 0.00 | 0 |  |
| `history.connect_eu__dk` | 15.5 | 16.1 | 15.7 | 17.7 | 0.00 | 0 |  |
| `history.registers__dk` | 4.4 | 15.9 | 3.7 | 16.0 | 0.00 | 0 |  |
| `connect_eu.mt` | 14.1 | 15.8 | 14.2 | 14.9 | 0.00 | 0 |  |
| `wave9.eu_emodnet_nuclear` | 8.8 | 15.7 | 7.4 | 8.4 | 0.00 | 0 |  |
| `wave9.us_eia_refineries` | 3.5 | 15.6 | 3.1 | 21.7 | 0.00 | 0 |  |
| `wave9.us_usgs_geoelectric` | 12.6 | 15.5 | 9.6 | 14.4 | 0.00 | 0 |  |
| `ev_eu.be` | 3.4 | 15.0 | 2.8 | 14.8 | 0.00 | 0 |  |
| `wave9.eu_emodnet_aggregates` | 4.4 | 14.8 | 4.0 | 11.4 | 0.00 | 0 |  |
| `registers.dk` | 4.3 | 14.6 | 2.7 | 13.7 | 0.00 | 0 |  |
| `connect_eu.bg` | 3.9 | 14.5 | 2.4 | 12.3 | 0.00 | 0 |  |
| `history.connect_eu__ee` | 2.7 | 14.5 | 2.4 | 14.0 | 0.00 | 0 |  |
| `osm.eu_links` | 6.2 | 14.5 | 2.8 | 6.4 | 0.00 | 0 |  |
| `history.connect_eu__lu` | 3.5 | 14.4 | 2.8 | 12.8 | 0.00 | 0 |  |
| `outlines.names` | 5.9 | 13.7 | 5.7 | 9.0 | 0.00 | 0 |  |
| `ev_eu.gr` | 2.9 | 13.6 | 2.2 | 12.2 | 0.00 | 0 |  |
| `ev_eu.mt` | 2.7 | 13.2 | 2.2 | 12.5 | 0.00 | 0 |  |
| `wave9.us_eia_lng` | 3.8 | 13.2 | 2.3 | 17.4 | 0.00 | 0 |  |
| `wave9.eu_emodnet_ports` | 3.8 | 13.1 | 3.4 | 10.9 | 0.00 | 0 |  |
| `wave9.us_eia_biodiesel` | 3.3 | 13.0 | 2.1 | 13.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_chp_f` | 2.7 | 12.7 | 2.4 | 2.4 | 0.00 | 0 |  |
| `wave9.gb_npg_heatmap_substations` | 8.7 | 12.2 | 8.3 | 10.9 | 0.00 | 0 |  |
| `wave9.eu_emodnet_military` | 4.1 | 12.0 | 3.7 | 10.5 | 0.00 | 0 |  |
| `wave9.eu_emodnet_platforms` | 3.6 | 12.0 | 2.8 | 7.3 | 0.00 | 0 |  |
| `wave9.fr_emodnet_telecom_sigcables` | 3.7 | 11.8 | 2.8 | 8.5 | 0.00 | 0 |  |
| `wave9.us_eia_hgl_pipelines` | 9.6 | 11.8 | 8.9 | 10.1 | 0.00 | 0 |  |
| `wave9.de_emodnet_telecom_bsh` | 4.4 | 11.6 | 3.4 | 8.7 | 0.00 | 0 |  |
| `entsoe.transmission_outages` | 2.6 | 11.4 | 1.9 | 12.7 | 0.00 | 0 |  |
| `wave9.mt_emodnet_telecom` | 3.4 | 11.2 | 2.9 | 10.1 | 0.00 | 0 |  |
| `wave9.us_blm_solar_dla` | 2.7 | 11.1 | 2.1 | 7.2 | 0.00 | 0 |  |
| `wave9.us_usgs_water_use` | 3.9 | 10.6 | 1.9 | 11.7 | 0.00 | 0 |  |
| `wave9.us_eia_product_pipelines` | 8.8 | 10.2 | 8.3 | 9.5 | 0.00 | 0 |  |
| `wave9.us_eia_crude_pipelines` | 8.1 | 9.7 | 8.1 | 9.8 | 0.00 | 0 |  |
| `outlines.aliases` | 3.7 | 9.5 | 3.6 | 7.1 | 0.00 | 0 |  |
| `wave9.es_emodnet_telecom_cica` | 3.3 | 9.4 | 2.2 | 9.0 | 0.00 | 0 |  |
| `wave9.gb_neso_etys` | 3.4 | 9.4 | 2.8 | 14.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_204_v` | 2.6 | 9.3 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_10` | 2.9 | 8.7 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave9.fr_emodnet_telecom_shom` | 3.1 | 8.6 | 2.1 | 6.9 | 0.00 | 0 |  |
| `aures.auctions` | 4.0 | 7.6 | 3.8 | 7.6 | 0.00 | 0 |  |
| `wave10.eu_rail_if_line_tr` | 3.1 | 6.6 | 2.9 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_cei_wm020` | 2.2 | 6.0 | 1.9 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_lorrit` | 2.6 | 5.7 | 2.3 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_ten00139` | 2.2 | 5.5 | 2.1 | 2.9 | 0.00 | 0 |  |
| `entsog.operator_point_directions` | 4.2 | 5.4 | 3.9 | 5.1 | 0.00 | 0 |  |
| `wave10.eu_cei_gsr020` | 3.6 | 5.0 | 2.1 | 2.8 | 0.00 | 0 |  |
| `wave9.us_eia861_reliability` | 4.7 | 4.7 | 1.8 | 1.8 | 0.00 | 0 |  |
| `wave10.eu_cei_pc030` | 2.0 | 4.6 | 1.3 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_env_ac_egss3` | 2.9 | 4.6 | 3.0 | 4.1 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_trset` | 2.4 | 4.6 | 1.7 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_vans` | 2.4 | 4.3 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_ten00126` | 2.7 | 4.3 | 2.4 | 2.5 | 0.00 | 0 |  |
| `wave9.de_kba_districts` | 4.3 | 4.3 | 1.6 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ren` | 2.4 | 4.2 | 1.8 | 2.4 | 0.00 | 0 |  |
| `wave10.gb_census_accommodation` | 2.6 | 4.2 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_cei_wm011` | 2.4 | 4.1 | 1.6 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_env_wat_cat` | 2.7 | 4.1 | 2.3 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_lorton` | 2.5 | 4.1 | 1.6 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_ten00106` | 2.8 | 4.0 | 1.8 | 2.7 | 0.00 | 0 |  |
| `pse_capacity.full_substations` | 1.2 | 3.9 | 1.1 | 1.2 | 0.00 | 0 |  |
| `wave10.eu_env_epea_invgg` | 2.2 | 3.9 | 1.7 | 2.1 | 0.00 | 0 |  |
| `wave9.gb_elexon_balancing` | 1.9 | 3.9 | 1.8 | 3.4 | 0.00 | 0 |  |
| `history.registers__be` | 2.6 | 3.8 | 2.0 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_age_loa` | 2.6 | 3.8 | 1.6 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_chdd_a` | 2.4 | 3.8 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_stk_h2` | 2.1 | 3.8 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_spurp` | 2.1 | 3.8 | 1.3 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_unlweig` | 2.7 | 3.8 | 1.9 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_carhab` | 2.6 | 3.8 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_env_ac_mid` | 2.2 | 3.7 | 1.8 | 2.0 | 0.00 | 0 |  |
| `wave10.gb_dft_evcd_devices` | 2.0 | 3.7 | 1.3 | 1.7 | 0.00 | 0 |  |
| `wave9.ie_semo_imbalance` | 3.7 | 3.7 | 1.2 | 1.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_bt` | 2.9 | 3.6 | 2.4 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ioc` | 3.0 | 3.5 | 2.7 | 3.3 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_31` | 2.7 | 3.5 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_ten00127` | 2.5 | 3.5 | 2.3 | 2.4 | 0.00 | 0 |  |
| `wave9.gb_neso_constraint_costs` | 3.1 | 3.5 | 1.3 | 2.3 | 0.00 | 0 |  |
| `wave9.us_epa_agstar` | 3.5 | 3.5 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.dgf_input` | 3.4 | 3.4 | 3.0 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_env_ac_epigg1` | 2.3 | 3.4 | 1.9 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_loadcap` | 2.5 | 3.4 | 1.7 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_21` | 2.3 | 3.4 | 2.2 | 3.2 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_61` | 2.3 | 3.4 | 2.3 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_ten00062` | 2.9 | 3.4 | 2.8 | 3.2 | 0.00 | 0 |  |
| `wave10.eu_ten00141` | 2.7 | 3.4 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.gb_desnz_ren_capacity_la` | 3.4 | 3.4 | 1.7 | 1.7 | 0.00 | 0 |  |
| `wave9.us_pjm_rpm` | 2.7 | 3.4 | 1.1 | 1.8 | 0.00 | 0 |  |
| `history.econnextion__requests` | 3.1 | 3.3 | 2.4 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_cei_pc034` | 2.2 | 3.3 | 2.3 | 3.2 | 0.00 | 0 |  |
| `wave10.eu_cei_pc035` | 2.4 | 3.3 | 1.7 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_31` | 2.3 | 3.3 | 2.4 | 3.2 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_40` | 2.6 | 3.3 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.gb_desnz_gas_distribution` | 3.3 | 3.3 | 1.2 | 1.2 | 0.00 | 0 |  |
| `wave9.rs_ems_connection_queue` | 3.3 | 3.3 | 2.5 | 3.0 | 0.00 | 0 |  |
| `wave9.si_surs_electricity_municipality` | 2.3 | 3.3 | 2.2 | 2.9 | 0.00 | 0 |  |
| `connect_eu.se` | 2.3 | 3.2 | 2.0 | 2.9 | 0.00 | 0 |  |
| `entsog.points` | 2.4 | 3.2 | 2.3 | 3.1 | 0.00 | 0 |  |
| `registers.be` | 2.3 | 3.2 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_env_ac_epneis1` | 2.5 | 3.2 | 2.6 | 3.3 | 0.00 | 0 |  |
| `wave10.eu_env_ac_landfp` | 2.7 | 3.2 | 1.1 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_env_wat_bal` | 2.7 | 3.2 | 2.7 | 3.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_chp_n` | 3.0 | 3.2 | 2.2 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_d_cv` | 3.1 | 3.2 | 3.0 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_c` | 2.2 | 3.2 | 2.1 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_h2stpc` | 2.4 | 3.2 | 1.9 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_stk_gas` | 3.1 | 3.2 | 3.0 | 3.3 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_roaene` | 2.6 | 3.2 | 2.4 | 3.3 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_20` | 2.4 | 3.2 | 2.3 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_30` | 2.7 | 3.2 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_11` | 2.4 | 3.2 | 1.7 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_21` | 2.3 | 3.2 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_ten00136` | 2.1 | 3.2 | 1.3 | 2.0 | 0.00 | 0 |  |
| `wave9.gb_npg_opendata` | 3.2 | 3.2 | 2.4 | 2.8 | 0.00 | 0 |  |
| `gem.iron_steel_plant_data` | 2.6 | 3.1 | 2.1 | 2.4 | 0.00 | 0 |  |
| `ghsl.population` | 2.2 | 3.1 | 2.2 | 3.0 | 0.00 | 0 |  |
| `history.connect_eu__at` | 2.0 | 3.1 | 2.3 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_cei_gsr030` | 2.1 | 3.1 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_cei_pc020` | 2.3 | 3.1 | 2.2 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_cei_pc050` | 2.2 | 3.1 | 2.2 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_cei_wm010` | 2.2 | 3.1 | 2.2 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_env_ac_curm` | 2.2 | 3.1 | 2.3 | 3.2 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_age` | 2.2 | 3.1 | 2.2 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_cpl` | 2.7 | 3.1 | 2.3 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_fechm2` | 2.5 | 3.1 | 2.0 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_epct` | 2.7 | 3.1 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_lbpc` | 2.5 | 3.1 | 2.4 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_stcs` | 2.1 | 3.1 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_rail_if_line_ga` | 2.8 | 3.1 | 2.7 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_rail_if_line_na` | 2.5 | 3.1 | 1.9 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_busmot` | 2.4 | 3.1 | 2.3 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_lorroa` | 2.7 | 3.1 | 2.8 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_60` | 2.3 | 3.1 | 2.2 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_60` | 2.4 | 3.1 | 2.2 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_41` | 2.1 | 3.1 | 1.6 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_ten00030` | 2.4 | 3.1 | 2.3 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_ten00121` | 2.8 | 3.1 | 2.8 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_frmod` | 2.4 | 3.1 | 1.8 | 2.2 | 0.00 | 0 |  |
| `wave9.eu_rail_electrified` | 2.7 | 3.1 | 2.2 | 2.4 | 0.00 | 0 |  |
| `wave9.us_nrel_sharing_sun` | 2.2 | 3.1 | 1.9 | 3.1 | 0.00 | 0 |  |
| `history.connect_eu__se` | 2.2 | 3.0 | 2.0 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_cei_srm010` | 2.9 | 3.0 | 2.5 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_env_ac_taxener` | 2.3 | 3.0 | 2.0 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_env_epea_invsp` | 2.4 | 3.0 | 2.3 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_n` | 2.4 | 3.0 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_psth2` | 2.1 | 3.0 | 1.5 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_wagon` | 3.0 | 3.0 | 2.8 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_rail_if_lvlcros` | 2.3 | 3.0 | 2.4 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_trail` | 2.7 | 3.0 | 2.6 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_busage` | 2.5 | 3.0 | 2.3 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_busmot` | 2.7 | 3.0 | 2.6 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_40` | 2.2 | 3.0 | 1.6 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_20` | 2.2 | 3.0 | 2.2 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_10` | 2.3 | 3.0 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_70` | 2.7 | 3.0 | 1.9 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_40` | 2.8 | 3.0 | 2.8 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_ten00129` | 2.9 | 3.0 | 2.8 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_frtra` | 2.2 | 3.0 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_psmod` | 2.5 | 3.0 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave9.eu_energy_productivity` | 2.3 | 3.0 | 2.2 | 2.8 | 0.00 | 0 |  |
| `wave9.eu_new_cars_fuel` | 3.0 | 3.0 | 2.8 | 2.8 | 0.00 | 0 |  |
| `wave9.gb_dft_veh0142` | 3.0 | 3.0 | 1.3 | 1.3 | 0.00 | 0 |  |
| `eaglei.coverage` | 2.1 | 2.9 | 1.9 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_env_epea_invte` | 2.1 | 2.9 | 2.1 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ffgae` | 2.6 | 2.9 | 1.6 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_203_v` | 2.2 | 2.9 | 2.1 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_205_v` | 2.3 | 2.9 | 1.7 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_locon` | 2.2 | 2.9 | 2.2 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_pa_cty` | 2.1 | 2.9 | 2.0 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_busveh` | 2.3 | 2.9 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_semit` | 2.7 | 2.9 | 2.6 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_trams` | 2.0 | 2.9 | 1.9 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_semit` | 2.7 | 2.9 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_trams` | 2.1 | 2.9 | 2.0 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_unlweig` | 2.3 | 2.9 | 1.5 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_10` | 2.2 | 2.9 | 2.2 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_70` | 2.2 | 2.9 | 1.3 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_30` | 2.1 | 2.9 | 1.6 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_51` | 2.1 | 2.9 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_ten00125` | 2.9 | 2.9 | 2.9 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_ten00135` | 2.4 | 2.9 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave10.gb_dft_evcd_rapid` | 2.3 | 2.9 | 2.1 | 2.7 | 0.00 | 0 |  |
| `wave9.eu_broadband_nuts2` | 2.1 | 2.9 | 1.9 | 2.7 | 0.00 | 0 |  |
| `wave9.eu_wastewater_connected` | 2.5 | 2.9 | 2.4 | 2.6 | 0.00 | 0 |  |
| `wave9.eu_water_use` | 2.4 | 2.9 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave9.fr_enedis_interruptions` | 1.8 | 2.9 | 1.7 | 2.8 | 0.00 | 0 |  |
| `ree_nodes.nodes` | 2.7 | 2.8 | 2.6 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_env_ac_cur` | 2.0 | 2.8 | 2.0 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_env_ac_epissp1` | 2.6 | 2.8 | 2.3 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_idooil` | 2.7 | 2.8 | 2.6 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_rcaebt` | 2.1 | 2.8 | 2.1 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_rctcbt` | 2.7 | 2.8 | 2.6 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_pa_nty` | 2.4 | 2.8 | 2.2 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_carpda` | 2.6 | 2.8 | 2.6 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_bussea` | 2.5 | 2.8 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_carage` | 2.3 | 2.8 | 2.2 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_11` | 2.3 | 2.8 | 2.2 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_50` | 2.4 | 2.8 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_50` | 2.3 | 2.8 | 2.2 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_20` | 2.1 | 2.8 | 2.1 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_10` | 2.2 | 2.8 | 1.5 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_ten00003` | 2.4 | 2.8 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_ten00006` | 2.0 | 2.8 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_ten00110` | 2.1 | 2.8 | 2.0 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_ten00124` | 2.6 | 2.8 | 2.3 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_ten00138` | 2.0 | 2.8 | 2.0 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_ms_frmod` | 2.4 | 2.8 | 2.3 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_pstra` | 2.7 | 2.8 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave10.gb_census_cars` | 2.1 | 2.8 | 2.0 | 2.8 | 0.00 | 0 |  |
| `wave9.eu_nonhousehold_prices` | 2.2 | 2.8 | 2.1 | 2.6 | 0.00 | 0 |  |
| `wave9.gb_bus_heat_pumps_la` | 2.8 | 2.8 | 1.1 | 1.1 | 0.00 | 0 |  |
| `eaglei.dqi` | 1.9 | 2.7 | 1.9 | 2.5 | 0.00 | 0 |  |
| `entsog_tyndp.projects` | 2.2 | 2.7 | 2.1 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_cei_cie012` | 2.3 | 2.7 | 2.2 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_cei_wm060` | 2.3 | 2.7 | 2.0 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_env_wat_pop` | 2.1 | 2.7 | 2.1 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_power_lo` | 2.0 | 2.7 | 1.9 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_id3cf` | 2.4 | 2.7 | 2.3 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_rail_if_tracks` | 2.6 | 2.7 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_bussea` | 1.9 | 2.7 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_motors` | 2.2 | 2.7 | 2.2 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_caremiss` | 1.9 | 2.7 | 2.0 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_motorc` | 2.0 | 2.7 | 2.0 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_trail` | 2.2 | 2.7 | 2.1 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_50` | 2.0 | 2.7 | 2.0 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_52` | 2.6 | 2.7 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_70` | 2.2 | 2.7 | 2.1 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_ms_frmod6` | 2.1 | 2.7 | 1.6 | 2.0 | 0.00 | 0 |  |
| `wave9.gb_neso_tnuos` | 1.8 | 2.7 | 1.7 | 2.3 | 0.00 | 0 |  |
| `zoning.documents` | 2.6 | 2.7 | 2.5 | 2.6 | 0.00 | 0 |  |
| `connect_eu.at` | 1.8 | 2.6 | 1.7 | 2.4 | 0.00 | 0 |  |
| `econnextion.requests` | 2.4 | 2.6 | 2.2 | 2.4 | 0.00 | 0 |  |
| `gem.gas_infrastructure_pipelines` | 2.3 | 2.6 | 2.2 | 2.5 | 0.00 | 0 |  |
| `gem.iron_steel_electric_arc_furnaces` | 2.0 | 2.6 | 2.1 | 2.4 | 0.00 | 0 |  |
| `gem.methane_emitters_plumes` | 2.2 | 2.6 | 2.1 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_cei_pc032` | 2.0 | 2.6 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_env_ac_epite1` | 2.0 | 2.6 | 1.9 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_env_ac_pefa05` | 2.0 | 2.6 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_env_air_no2` | 2.2 | 2.6 | 2.2 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ei` | 2.3 | 2.6 | 1.8 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ep` | 2.1 | 2.6 | 2.0 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_pa_csb` | 1.9 | 2.6 | 1.9 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_mopeds` | 2.0 | 2.6 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_30` | 2.5 | 2.6 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_10` | 1.9 | 2.6 | 1.8 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_70a` | 2.0 | 2.6 | 1.9 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_ten00123` | 2.6 | 2.6 | 2.4 | 2.5 | 0.00 | 0 |  |
| `wave9.ie_cso_datacentres` | 2.4 | 2.6 | 2.0 | 2.6 | 0.00 | 0 |  |
| `wave9.ro_transelectrica_zone_capacity` | 1.7 | 2.6 | 1.6 | 2.4 | 0.00 | 0 |  |
| `eredes_capacity.substations` | 2.4 | 2.5 | 2.3 | 2.4 | 0.00 | 0 |  |
| `gem.coal_mines_historical_production_non_chin` | 2.0 | 2.5 | 2.0 | 2.2 | 0.00 | 0 |  |
| `gem.gas_finance_gas_power_plants` | 2.2 | 2.5 | 2.1 | 2.5 | 0.00 | 0 |  |
| `gem.gas_finance_lng_terminals` | 2.1 | 2.5 | 2.1 | 2.4 | 0.00 | 0 |  |
| `gem.iron_steel_direct_reduced_iron_furnaces` | 2.0 | 2.5 | 2.0 | 2.2 | 0.00 | 0 |  |
| `gem.iron_steel_plant_capacities_and_status` | 2.1 | 2.5 | 2.0 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_cei_cie011` | 1.8 | 2.5 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_cei_pc031` | 1.8 | 2.5 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_env_ac_rp` | 2.1 | 2.5 | 2.1 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_env_wat_ind` | 2.2 | 2.5 | 1.9 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_rail_if_line_sp` | 2.0 | 2.5 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_carmot` | 1.9 | 2.5 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_tracmot` | 1.7 | 2.5 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_busveh` | 1.8 | 2.5 | 1.9 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_40` | 1.9 | 2.5 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_ten00122` | 2.4 | 2.5 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave9.gb_ulev_la` | 2.5 | 2.5 | 2.2 | 2.2 | 0.00 | 0 |  |
| `wave9.us_eia861_reliability_xlsx` | 2.5 | 2.5 | 1.9 | 1.9 | 0.00 | 0 |  |
| `eaglei.counties` | 1.7 | 2.4 | 1.7 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_di` | 1.8 | 2.4 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_esr` | 1.8 | 2.4 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_202_v` | 1.8 | 2.4 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_60` | 1.8 | 2.4 | 1.7 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_ten00137` | 1.8 | 2.4 | 1.8 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_ms_psmod` | 2.1 | 2.4 | 2.0 | 2.3 | 0.00 | 0 |  |
| `wave10.gb_census_density` | 2.0 | 2.4 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave9.gr_elstat_heating_energy_regional_unit` | 2.3 | 2.4 | 2.3 | 2.4 | 0.00 | 0 |  |
| `wave9.us_nrc_operating_reactors` | 2.4 | 2.4 | 2.3 | 2.3 | 0.00 | 0 |  |
| `gem.coal_mines_historical_production_non_china` | 2.1 | 2.3 | 1.9 | 2.2 | 0.00 | 0 |  |
| `gem.iron_ore_mines_prodconsmetcoalironore` | 2.1 | 2.3 | 1.9 | 2.2 | 0.00 | 0 |  |
| `gem.iron_steel_blast_furnace_relinings` | 1.8 | 2.3 | 1.4 | 1.5 | 0.00 | 0 |  |
| `gem.oil_infrastructure_data` | 1.9 | 2.3 | 1.8 | 2.0 | 0.00 | 0 |  |
| `hotmaps.industrial_sites` | 1.9 | 2.3 | 1.8 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_cei_srm030` | 1.8 | 2.3 | 1.7 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_11` | 1.8 | 2.3 | 1.8 | 2.3 | 0.00 | 0 |  |
| `wave9.fr_ademe_dpe` | 1.9 | 2.3 | 1.6 | 2.2 | 0.00 | 0 |  |
| `wave9.nl_cbs_datacentres` | 2.3 | 2.3 | 1.3 | 1.3 | 0.00 | 0 |  |
| `co2stop.storage_units_user_and_database_calc_storage` | 1.8 | 2.2 | 1.7 | 2.0 | 0.00 | 0 |  |
| `co2stop.sum_output` | 1.8 | 2.2 | 1.8 | 2.2 | 0.00 | 0 |  |
| `pse_capacity.requests` | 1.8 | 2.2 | 1.7 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_locop` | 2.1 | 2.2 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave9.gb_epc_stats` | 2.2 | 2.2 | 1.1 | 1.1 | 0.00 | 0 |  |
| `wave9.gb_npg_curtailment_events` | 2.2 | 2.2 | 1.2 | 1.2 | 0.00 | 0 |  |
| `co2stop.country_totals` | 1.9 | 2.1 | 1.7 | 1.9 | 0.00 | 0 |  |
| `co2stop.daughter_units_summary` | 1.9 | 2.1 | 1.8 | 2.0 | 0.00 | 0 |  |
| `connect_eu.de` | 1.9 | 2.1 | 1.9 | 1.9 | 0.00 | 0 |  |
| `gem.coal_mines_change_log` | 1.8 | 2.1 | 1.7 | 2.0 | 0.00 | 0 |  |
| `gem.iron_steel_basic_oxygen_furnaces` | 1.9 | 2.1 | 1.8 | 2.1 | 0.00 | 0 |  |
| `gem.iron_steel_blast_furnaces` | 1.9 | 2.1 | 1.7 | 2.1 | 0.00 | 0 |  |
| `gem.oil_gas_extraction_project_level_production_data` | 1.9 | 2.1 | 1.9 | 2.1 | 0.00 | 0 |  |
| `history.connect_eu__de` | 1.9 | 2.1 | 1.9 | 1.9 | 0.00 | 0 |  |
| `history.pse_capacity__full_substations` | 1.9 | 2.1 | 1.9 | 2.0 | 0.00 | 0 |  |
| `history.pse_capacity__requests` | 1.6 | 2.1 | 1.6 | 1.8 | 0.00 | 0 |  |
| `wave9.eu_broadband_coverage` | 2.0 | 2.1 | 1.4 | 1.9 | 0.00 | 0 |  |
| `co2stop.dic_geol_basin` | 1.8 | 2.0 | 1.9 | 2.0 | 0.00 | 0 |  |
| `gem.chemicals_plant_data` | 1.9 | 2.0 | 1.7 | 1.9 | 0.00 | 0 |  |
| `wave10.gb_census_households` | 1.6 | 2.0 | 1.5 | 1.9 | 0.00 | 0 |  |
| `co2stop.dic_age` | 1.9 | 1.9 | 1.4 | 1.4 | 0.00 | 0 |  |
| `co2stop.total_storecap_nolargestorage_countries` | 1.8 | 1.9 | 1.6 | 1.7 | 0.00 | 0 |  |
| `entsoe.areas` | 1.8 | 1.9 | 1.7 | 1.8 | 0.00 | 0 |  |
| `gem.coal_mines_historic_production_2018_2025` | 1.8 | 1.9 | 1.6 | 1.8 | 0.00 | 0 |  |
| `gem.integrated_power_regions_area_and_countries` | 1.6 | 1.9 | 1.6 | 1.8 | 0.00 | 0 |  |
| `gem.iron_ore_mines_main_data` | 1.7 | 1.9 | 1.6 | 1.8 | 0.00 | 0 |  |
| `history.eredes_capacity__substations` | 1.8 | 1.9 | 1.7 | 1.9 | 0.00 | 0 |  |
| `wave10.gb_desnz_ren_sites_la` | 1.9 | 1.9 | 1.9 | 1.9 | 0.00 | 0 |  |
| `wave10.gb_dft_evcd_per_100k` | 1.9 | 1.9 | 1.7 | 1.7 | 0.00 | 0 |  |
| `wave9.eu_cleanh2_electrolyser_mfg` | 1.9 | 1.9 | 1.8 | 1.8 | 0.00 | 0 |  |
| `wave9.gb_desnz_subregional_fit` | 1.9 | 1.9 | 1.8 | 1.8 | 0.00 | 0 |  |
| `wave9.us_afdc_registrations` | 1.9 | 1.9 | 1.7 | 1.7 | 0.00 | 0 |  |
| `co2stop.dic_assess_traptype` | 1.8 | 1.8 | 1.7 | 1.7 | 0.00 | 0 |  |
| `co2stop.dic_fault_extent` | 1.8 | 1.8 | 1.8 | 1.8 | 0.00 | 0 |  |
| `co2stop.dic_surfissues` | 1.8 | 1.8 | 1.8 | 1.8 | 0.00 | 0 |  |
| `eia930.bas` | 1.7 | 1.8 | 1.6 | 1.8 | 0.00 | 0 |  |
| `gem.cement_final_data` | 1.6 | 1.8 | 1.5 | 1.6 | 0.00 | 0 |  |
| `gem.gas_infrastructure_data` | 1.7 | 1.8 | 1.5 | 1.7 | 0.00 | 0 |  |
| `gem.iron_steel_induction_furnaces` | 1.7 | 1.8 | 1.5 | 1.7 | 0.00 | 0 |  |
| `wave10.gb_desnz_elec_distribution` | 1.8 | 1.8 | 1.7 | 1.7 | 0.00 | 0 |  |
| `wave9.us_eia_recs_heat_pumps_state` | 1.8 | 1.8 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.dic_assess_type` | 1.7 | 1.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.dic_distrib_type` | 1.7 | 1.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.dic_geocgraph_area` | 1.5 | 1.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.dic_methods` | 1.7 | 1.7 | 1.7 | 1.7 | 0.00 | 0 |  |
| `co2stop.dic_status` | 1.7 | 1.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.total_storage_cap_aquif_hcfields` | 1.5 | 1.7 | 1.4 | 1.6 | 0.00 | 0 |  |
| `gem.coal_mines_historical_production_china` | 1.6 | 1.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `gem.iron_steel_open_hearth_furnaces` | 1.7 | 1.7 | 1.5 | 1.7 | 0.00 | 0 |  |
| `gem.methane_emitters_pipelines` | 1.6 | 1.7 | 1.5 | 1.7 | 0.00 | 0 |  |
| `mastr.catalog_values` | 1.7 | 1.7 | 1.7 | 1.7 | 0.00 | 0 |  |
| `wave9.gb_dec_certificates` | 1.7 | 1.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `wave9.us_eia861m_small_solar` | 1.7 | 1.7 | 1.7 | 1.7 | 0.00 | 0 |  |
| `gem.oil_gas_extraction_project_level_reserves_data` | 1.5 | 1.6 | 1.4 | 1.5 | 0.00 | 0 |  |
| `wave9.nl_rdw_vehicles` | 1.6 | 1.6 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.dic_content` | 1.5 | 1.5 | 1.6 | 1.6 | 0.00 | 0 |  |
| `co2stop.dic_geocapacity_countries` | 1.5 | 1.5 | 1.4 | 1.5 | 0.00 | 0 |  |
| `co2stop.dic_pred_lith` | 1.5 | 1.5 | 1.5 | 1.5 | 0.00 | 0 |  |
| `gem.iron_steel_plant_production` | 1.4 | 1.5 | 1.3 | 1.4 | 0.00 | 0 |  |
| `co2stop.dic_availabledata` | 1.4 | 1.4 | 1.3 | 1.3 | 0.00 | 0 |  |
| `co2stop.dic_yes_no` | 1.3 | 1.3 | 1.3 | 1.3 | 0.00 | 0 |  |
| `co2stop.dic_on_offshore` | 1.2 | 1.2 | 1.2 | 1.2 | 0.00 | 0 |  |
<!-- measured:end -->
