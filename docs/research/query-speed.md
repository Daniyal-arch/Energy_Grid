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

## Latest run

<!-- measured:start -->
Probed 2026-11-08T23:03:38+00:00 in the Lambda-sized container (2 vCPU, 3,008 MB) against `r2:r2://infraatlas-raw/lake/lake.duckdb`; 1081 tables in 8 shards. Times in ms (cold = the first run of each query in the process; warm = the median of 3 repeats); MB and GET requests read from R2 by the cold runs of the table's query set.

### Unseen queries (generated, no template, result cache off): 193 of 200 answered, p50 70.9 ms, p95 1,742 ms, max 3,386 ms

| # | table | kind | ms | rows | MB | error |
|---:|---|---|---:|---:|---:|---|
| 0 | `gem.gas_infrastructure_lng_terminals` | sum | 3,386 | 1 | 0.00 |  |
| 1 | `wave9.fr_emodnet_telecom_shom` | count | 2,546 | 0 | 0.59 |  |
| 2 | `wave10.eu_nrg_te_oilm` | sum | 1,425 | 1 | 2.92 |  |
| 3 | `wave10.wb_eg_gdp_puse_ko_pp` | top | 770 | 10 | 0.05 |  |
| 4 | `dams.barriers` | avg | 3,173 | 1 | 1.05 |  |
| 5 | `wave10.eu_road_eqs_lormot` | count | 259 | 8271 | 0.00 |  |
| 6 | `wave10.wb_is_rrs_pasg_km` | avg | 800 | 1 | 0.02 |  |
| 7 | `wave10.wb_eg_gdp_puse_ko_pp_kd` | top | 537 | 10 | 0.05 |  |
| 8 | `wave10.eu_cei_gsr020` | top | 7.5 | 10 | 0.00 |  |
| 9 | `wave10.eu_cei_srm020` | sum | 5.6 | 1 | 0.00 |  |
| 10 | `wave10.eu_env_ac_io10` | sum | 437 | 2383261020 | 0.03 |  |
| 11 | `mastr.catalog_values` | sum | 22.8 | 121813266 | 0.00 |  |
| 12 | `wave10.wb_eg_elc_petr_zs` | top | 362 | 10 | 0.06 |  |
| 13 | `wave10.wb_ny_adj_dngy_cd` | count | 6.7 | 4139 | 0.00 |  |
| 14 | `mastr.units_nuclear` | sum | 2,523 | 1 | 0.00 |  |
| 15 | `entsoe.load` | sum | 1,425 | 13336909049 | 0.22 |  |
| 16 | `gem.iron_steel_plant_capacities_and_status` | top | 0.7 | None | 0.00 | GuardError: gem.iron_steel_plant_capacities_and_status is licensed (Global Energ |
| 17 | `wave10.wb_ny_adj_dfor_gn_zs` | count | 4.9 | 9576 | 0.02 |  |
| 18 | `gem.coal_mines_historic_production_2018_2025` | top | 0.6 | None | 0.00 | GuardError: gem.coal_mines_historic_production_2018_2025 is licensed (Global Ene |
| 19 | `wave9.eu_broadband_nuts2` | top | 8.0 | 10 | 0.00 |  |
| 20 | `wave10.eu_ten00135` | sum | 5.5 | 6507822 | 0.00 |  |
| 21 | `wave9.gb_ssen_opendata` | avg | 1,496 | None | 0.00 | BinderException: Binder Error: Cannot mix values of type VARCHAR and DECIMAL(6,5 |
| 22 | `entsoe.load` | avg | 1,817 | 1 | 0.22 |  |
| 23 | `rollups.overture_power__lines_r7` | top | 716 | 0 | 0.00 |  |
| 24 | `ev_eu.be` | avg | 76.1 | 1 | 0.00 |  |
| 25 | `wave10.eu_env_ac_pepssp1` | sum | 4.7 | 65122164 | 0.00 |  |
| 26 | `wave10.wb_er_h2o_intr_pc` | sum | 223 | 1 | 0.06 |  |
| 27 | `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` | sum | 295 | 1 | 0.06 |  |
| 28 | `wave10.eu_ten00108` | count | 4.1 | 596 | 0.00 |  |
| 29 | `wave9.be_fluvius_consumption` | top | 13.2 | 10 | 0.00 |  |
| 30 | `wave10.eu_ten00122` | group | 7.2 | 1 | 0.00 |  |
| 31 | `wave10.eu_nrg_cb_pem` | group | 210 | 1 | 0.66 |  |
| 32 | `wave10.eu_nrg_ind_eff` | sum | 7.0 | 1 | 0.00 |  |
| 33 | `co2stop.dic_assess_traptype` | avg | 646 | 2 | 2.02 |  |
| 34 | `rollups.overture_power__lines_r7` | sum | 424 | 3 | 0.00 |  |
| 35 | `wave10.eu_road_eqs_zev` | group | 279 | 43 | 0.03 |  |
| 36 | `connect_eu.gb_dso` | count | 407 | 0 | 0.58 |  |
| 37 | `wave10.eu_nrg_cb_sff` | count | 6.4 | 82711 | 0.00 |  |
| 38 | `wave10.wb_ag_lnd_agri_k2` | avg | 297 | 1 | 0.03 |  |
| 39 | `wave9.gb_he_listed` | group | 1,403 | 0 | 9.58 |  |
| 40 | `main.emissions` | group | 305 | 50 | 0.35 |  |
| 41 | `euets.verified_emissions` | sum | 288 | 1248009360 | 0.59 |  |
| 42 | `wave10.eu_sdg_12_31` | avg | 5.6 | 1 | 0.00 |  |
| 43 | `wave10.eu_env_epea_cint` | top | 368 | 10 | 0.08 |  |
| 44 | `ev_eu.pl` | group | 75.0 | 0 | 0.00 |  |
| 45 | `wave10.eu_sdg_09_10` | avg | 4.2 | 1 | 0.00 |  |
| 46 | `co2stop.dic_geocgraph_area` | sum | 5.9 | 123 | 0.00 |  |
| 47 | `mastr.units_solar` | group | 2,377 | 0 | 17.17 |  |
| 48 | `wave10.gb_desnz_ghg_dataset` | top | 851 | 10 | 5.49 |  |
| 49 | `wave10.eu_nrg_te_oil` | avg | 11.9 | 1 | 0.00 |  |
| 50 | `wave10.wb_ie_ppn_tran_cd` | sum | 220 | 19223820 | 0.01 |  |
| 51 | `wave9.us_opportunity_zones` | sum | 2,144 | 1 | 56.70 |  |
| 52 | `mastr.units_hydro` | group | 363 | 2 | 1.97 |  |
| 53 | `wave10.gb_desnz_tfec_la` | sum | 5.2 | 7315 | 0.00 |  |
| 54 | `eia930.generation_by_fuel` | avg | 286 | 1 | 0.02 |  |
| 55 | `wave10.eu_nrg_ind_di` | count | 7.1 | 405 | 0.00 |  |
| 56 | `wave10.eu_env_ac_epite1` | avg | 6.7 | 1 | 0.00 |  |
| 57 | `wave10.wb_tm_val_mmtl_zs_un` | count | 4.8 | 9576 | 0.00 |  |
| 58 | `wave10.eu_road_eqs_lorroa` | group | 6.3 | 3 | 0.00 |  |
| 59 | `euets.eea_link` | group | 379 | 0 | 0.40 |  |
| 60 | `wave9.us_usgs_nwis_sites` | avg | 1,071 | 1 | 3.47 |  |
| 61 | `wave10.eu_ten00139` | group | 4.9 | 1 | 0.00 |  |
| 62 | `gem.iron_steel_blast_furnace_relinings` | sum | 6.7 | 1 | 0.00 |  |
| 63 | `ev_eu.ee` | sum | 14.5 | 1 | 0.00 |  |
| 64 | `entsoe.imbalance_price` | group | 123 | 2 | 0.00 |  |
| 65 | `wave9.us_natcarb` | avg | 1,014 | 1 | 3.12 |  |
| 66 | `wave10.eu_env_esst_ggcp` | count | 343 | 209400 | 0.14 |  |
| 67 | `wave10.wb_en_ghg_co2_pc_ce_ar5` | group | 284 | 1 | 0.07 |  |
| 68 | `wave10.wb_bx_klt_dinv_wd_gd_zs` | sum | 299 | 1 | 0.07 |  |
| 69 | `wave10.wb_it_net_user_fe_zs` | sum | 5.1 | 1 | 0.00 |  |
| 70 | `wave10.eu_ten00110` | group | 6.8 | 1 | 0.00 |  |
| 71 | `ev_eu.lu` | group | 107 | 0 | 0.00 |  |
| 72 | `wave10.wb_en_ghg_n2o_pi_mt_ce_ar5` | avg | 6.8 | 1 | 0.00 |  |
| 73 | `wave10.gb_census_cars` | count | 658 | 3180 | 0.54 |  |
| 74 | `wave9.us_eia_product_terminals` | group | 87.7 | 0 | 0.00 |  |
| 75 | `wave10.eu_nrg_ind_pehcf` | sum | 291 | 326180670 | 0.71 |  |
| 76 | `wave10.wb_ag_yld_crel_kg` | count | 292 | 9576 | 0.04 |  |
| 77 | `wave10.gb_desnz_elec_distribution` | sum | 4.1 | 25 | 0.00 |  |
| 78 | `wave9.us_nrc_operating_reactors` | sum | 6.6 | 93 | 0.00 |  |
| 79 | `gem.energy_ownership_cement_and_concrete_ownership` | group | 0.7 | None | 0.00 | GuardError: gem.energy_ownership_cement_and_concrete_ownership is licensed (Glob |
| 80 | `wave10.eu_rail_if_line_tr` | sum | 7.1 | 10130028 | 0.00 |  |
| 81 | `wave10.eu_env_ac_eptrf1` | count | 5.2 | 19520 | 0.00 |  |
| 82 | `wave10.eu_rail_eq_pa_nty` | top | 6.2 | 10 | 0.00 |  |
| 83 | `wave10.eu_road_eqs_trams` | avg | 7.0 | 1 | 0.00 |  |
| 84 | `wave10.eu_nrg_ind_pehcf` | sum | 304 | 1 | 0.71 |  |
| 85 | `wave10.gb_census_travel_distance` | sum | 4.9 | 14138916 | 0.00 |  |
| 86 | `wave10.wb_ny_gdp_ngas_rt_zs` | count | 294 | 9576 | 0.04 |  |
| 87 | `tyndp.projects` | count | 21.3 | 0 | 0.00 |  |
| 88 | `mastr.operators` | group | 671 | 2 | 0.05 |  |
| 89 | `wave10.eu_nrg_ind_psth2` | sum | 617 | 1 | 0.40 |  |
| 90 | `app.eu_lines` | top | 32.4 | 0 | 0.00 |  |
| 91 | `wave10.eu_nrg_cb_rw` | sum | 263 | 13934827 | 0.34 |  |
| 92 | `wave10.eu_env_watres_rb` | top | 331 | 10 | 0.07 |  |
| 93 | `wave10.wb_er_h2o_intr_pc` | group | 5.6 | 1 | 0.00 |  |
| 94 | `wave10.wb_eg_cft_accs_ur_zs` | sum | 316 | 11985455 | 0.02 |  |
| 95 | `co2stop.daughter_units_summary` | count | 6.2 | 21 | 0.00 |  |
| 96 | `wave10.wb_tx_val_fuel_zs_un` | sum | 7.4 | 1 | 0.00 |  |
| 97 | `wave10.wb_eg_elc_accs_ru_zs` | sum | 5.1 | 1 | 0.00 |  |
| 98 | `wave10.wb_ag_lnd_prcp_mm` | top | 263 | 10 | 0.01 |  |
| 99 | `wave10.eu_env_watuse_rb` | sum | 261 | 1 | 0.04 |  |
| 100 | `wave10.eu_env_epea_pap` | count | 352 | 12412 | 0.17 |  |
| 101 | `wave10.wb_sh_sta_smss_zs` | count | 4.8 | 9576 | 0.00 |  |
| 102 | `wave10.eu_nrg_cb_eim` | avg | 303 | 1 | 0.09 |  |
| 103 | `shapes.nuts` | top | 10.0 | 10 | 0.00 |  |
| 104 | `wave10.eu_road_eqs_lorton` | top | 8.7 | 10 | 0.00 |  |
| 105 | `history.connect_eu__se` | top | 6.5 | 10 | 0.00 |  |
| 106 | `wave9.us_eia_gas_processing` | sum | 12.8 | 1 | 0.00 |  |
| 107 | `gem.iron_steel_plant_production` | top | 0.8 | None | 0.00 | GuardError: gem.iron_steel_plant_production is licensed (Global Energy Monitor): |
| 108 | `wave10.eu_env_epea_pgg` | group | 303 | 1 | 0.05 |  |
| 109 | `wave10.eu_env_ac_mfain` | sum | 5.2 | 1 | 0.00 |  |
| 110 | `wave9.pt_ine_heating_freguesia` | sum | 326 | 1 | 0.17 |  |
| 111 | `wave9.rs_ems_connection_queue` | sum | 6.4 | 1 | 0.00 |  |
| 112 | `connect_eu.lu` | sum | 40.5 | 1 | 0.00 |  |
| 113 | `gem.gas_infrastructure_lng_terminals` | top | 0.6 | None | 0.00 | GuardError: gem.gas_infrastructure_lng_terminals is licensed (Global Energy Moni |
| 114 | `wave10.eu_env_ac_pefa05` | sum | 5.2 | 7126709 | 0.00 |  |
| 115 | `app.eu_plants` | sum | 81.9 | 1 | 0.00 |  |
| 116 | `wave9.eu_broadband_nuts2` | group | 6.0 | 2 | 0.00 |  |
| 117 | `wave10.eu_rail_eq_trset` | sum | 4.3 | 3020784 | 0.00 |  |
| 118 | `wave10.wb_eg_imp_cons_zs` | count | 290 | 9576 | 0.05 |  |
| 119 | `mastr.units_storage` | group | 463 | 2 | 0.05 |  |
| 120 | `wave10.eu_sdg_06_60` | avg | 6.2 | 1 | 0.00 |  |
| 121 | `gem.methane_emitters_lng_terminals` | avg | 24.4 | 1 | 0.00 |  |
| 122 | `wave10.eu_env_ac_pefa04` | avg | 241 | 1 | 0.52 |  |
| 123 | `history.pse_capacity__requests` | count | 6.0 | 886 | 0.00 |  |
| 124 | `wave10.wb_er_h2o_fwin_zs` | top | 363 | 10 | 0.04 |  |
| 125 | `wave9.eu_land_prices` | avg | 5.1 | 1 | 0.00 |  |
| 126 | `wave9.de_emodnet_telecom_bsh` | group | 11.7 | 0 | 0.00 |  |
| 127 | `wave10.eu_nrg_inf_epct` | avg | 7.4 | 1 | 0.00 |  |
| 128 | `wave9.world_ihfc_heat_flow` | avg | 879 | 1 | 1.18 |  |
| 129 | `wave9.eu_broadband_coverage` | group | 636 | 1 | 0.40 |  |
| 130 | `mastr.catalog_values` | top | 5.9 | 10 | 0.00 |  |
| 131 | `wave9.us_epa_aqs_annual` | group | 648 | 0 | 0.11 |  |
| 132 | `wave10.eu_env_ac_ghgfp` | top | 1,013 | 10 | 19.87 |  |
| 133 | `connect_eu.bg` | top | 46.4 | 0 | 0.00 |  |
| 134 | `wave10.eu_nrg_ind_esr` | sum | 6.5 | 816885 | 0.00 |  |
| 135 | `pse_capacity.requests` | sum | 6.9 | 886 | 0.00 |  |
| 136 | `ev_eu.de` | count | 103 | 6504 | 0.00 |  |
| 137 | `euets.verified_emissions` | sum | 5.9 | 1248009360 | 0.00 |  |
| 138 | `neso.constraint_breakdown` | top | 2,230 | 10 | 0.32 |  |
| 139 | `wave9.dk_district_heating` | count | 9.1 | 0 | 0.00 |  |
| 140 | `wave10.eu_rail_eq_locop` | avg | 5.5 | 1 | 0.00 |  |
| 141 | `wave10.eu_env_ac_cepsgc1` | group | 6.3 | 12 | 0.00 |  |
| 142 | `wave10.wb_en_ghg_all_pc_ce_ar5` | sum | 312 | 1 | 0.07 |  |
| 143 | `wave9.us_openei_urdb` | top | 410 | 58920 | 0.13 |  |
| 144 | `gem.methane_emitters_pipelines` | avg | 6.7 | 1 | 0.00 |  |
| 145 | `history.pse_capacity__full_substations` | group | 601 | 50 | 0.53 |  |
| 146 | `history.connect_eu__gb_dso` | sum | 272 | 1 | 0.58 |  |
| 147 | `gem.methane_emitters_lng_terminals` | count | 108 | 0 | 0.00 |  |
| 148 | `wave10.eu_env_ac_ghgfp` | sum | 986 | 1 | 16.22 |  |
| 149 | `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` | count | 4.8 | 9576 | 0.00 |  |
| 150 | `wave9.eur_overture_comm_lines` | sum | 11.5 | 58 | 0.00 |  |
| 151 | `wave10.wb_it_net_user_ma_zs` | sum | 216 | 3146898 | 0.02 |  |
| 152 | `entsog.points` | group | 7.4 | 3 | 0.00 |  |
| 153 | `wave10.eu_env_epea_pgg` | sum | 5.2 | 35089415 | 0.00 |  |
| 154 | `wave10.wb_eg_imp_cons_zs` | sum | 5.8 | 1 | 0.00 |  |
| 155 | `gem.oil_gas_extraction_field_level_main_data` | top | 0.9 | None | 0.00 | GuardError: gem.oil_gas_extraction_field_level_main_data is licensed (Global Ene |
| 156 | `connect_eu.ee` | count | 13.2 | 0 | 0.00 |  |
| 157 | `wave10.eu_nrg_ind_ioc` | group | 5.7 | 43 | 0.00 |  |
| 158 | `wave10.eu_sdg_13_70a` | top | 7.4 | 10 | 0.00 |  |
| 159 | `wave10.eu_sdg_09_60` | avg | 70.9 | 1 | 0.00 |  |
| 160 | `co2stop.dic_on_offshore` | avg | 5.9 | 3 | 0.00 |  |
| 161 | `wave10.eu_nrg_pc_203_c` | sum | 4.8 | 192495588 | 0.00 |  |
| 162 | `entsog.operator_point_directions` | sum | 5.8 | 1 | 0.00 |  |
| 163 | `wave9.us_nexrad` | avg | 62.1 | 1 | 0.00 |  |
| 164 | `history.registers__ie` | sum | 34.8 | 1 | 0.00 |  |
| 165 | `registers.pt` | count | 87.5 | 0 | 0.00 |  |
| 166 | `wave9.us_usgs_nshm` | count | 1,043 | 0 | 9.83 |  |
| 167 | `rollups.wave9__de_zensus_heating_r5` | sum | 60.7 | 3487 | 0.00 |  |
| 168 | `ev_eu.pt` | top | 55.3 | 0 | 0.00 |  |
| 169 | `wave10.eu_rail_eq_vans` | avg | 602 | 1 | 0.40 |  |
| 170 | `wave10.wb_ag_lnd_totl_ur_k2` | sum | 219 | 19223820 | 0.02 |  |
| 171 | `wave9.gb_ne_alc` | avg | 65.8 | 1 | 0.00 |  |
| 172 | `wave10.eu_cei_pc030` | sum | 5.9 | 3272322 | 0.00 |  |
| 173 | `wave9.us_noaa_mpa` | avg | 272 | 1 | 0.02 |  |
| 174 | `wave10.eu_road_eqs_roaene` | count | 6.3 | 4555 | 0.00 |  |
| 175 | `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` | group | 206 | 50 | 0.06 |  |
| 176 | `wave9.si_surs_heating_settlement` | avg | 9.6 | 1 | 0.00 |  |
| 177 | `outlines.fr_iris` | avg | 1,870 | 1 | 76.63 |  |
| 178 | `wave10.eu_cei_pc034` | count | 4.7 | 298 | 0.00 |  |
| 179 | `wave10.wb_ag_lnd_frst_zs` | sum | 7.0 | 19223820 | 0.00 |  |
| 180 | `wave10.wb_ny_adj_dco2_cd` | top | 326 | 10 | 0.06 |  |
| 181 | `wave10.eu_env_ac_pefafp` | top | 7.2 | 10 | 0.00 |  |
| 182 | `wave10.wb_ny_adj_svng_gn_zs` | sum | 274 | 19223820 | 0.04 |  |
| 183 | `outlines.us_places` | group | 1,058 | 1 | 15.50 |  |
| 184 | `wave10.eu_env_ac_ghgfp` | sum | 2,144 | 1 | 38.20 |  |
| 185 | `wave10.eu_cei_pc020` | avg | 573 | 1 | 0.40 |  |
| 186 | `wave10.eu_ten00108` | avg | 5.1 | 1 | 0.00 |  |
| 187 | `wave10.wb_en_ghg_ch4_bu_mt_ce_ar5` | avg | 324 | 1 | 0.06 |  |
| 188 | `wave10.wb_en_pop_slum_ur_zs` | count | 451 | 9576 | 0.02 |  |
| 189 | `wave10.eu_sdg_07_30` | top | 4.8 | 0 | 0.00 |  |
| 190 | `wave10.wb_en_fsh_thrd_no` | count | 275 | 9576 | 0.01 |  |
| 191 | `main.grid_capacity` | group | 1,742 | 50 | 1.89 |  |
| 192 | `wave10.eu_ten00030` | top | 7.5 | 10 | 0.00 |  |
| 193 | `wave10.eu_sdg_06_70` | top | 586 | 10 | 0.40 |  |
| 194 | `eia930.interchange` | group | 799 | 1 | 3.83 |  |
| 195 | `ev_eu.pl` | group | 52.3 | 0 | 0.00 |  |
| 196 | `wave9.gb_emr_cm_register` | group | 6.0 | 17 | 0.00 |  |
| 197 | `ree_nodes.nodes` | avg | 5.0 | 2814 | 0.00 |  |
| 198 | `wave10.eu_rail_eq_wagon` | group | 7.2 | 37 | 0.00 |  |
| 199 | `mastr.operators` | group | 669 | 50 | 0.32 |  |

### All dataset queries

| | queries | p50 | p95 | max |
|---|---:|---:|---:|---:|
| cold | 4077 | 3.4 | 735 | 54,234 |
| warm | 4069 | 2.3 | 171 | 16,310 |

### Data routes: cold p50/p95 15.3 / 1,858, warm p50/p95 14.1 / 844

| | cold | warm p50 | note |
|---|---:|---:|---|
| GET /api/health | 7.8 | 12.2 | status 200 |
| GET /api/catalog/search?q=solar%20capacity%20Germany | 1,858 | 5.1 | status 200 |
| GET /api/catalog/atb | 3.7 | 3.4 | status 200 |
| GET /api/places?q=Bavaria | 14.9 | 14.0 | status 200 |
| GET /api/places?q=Lyon | 14.2 | 14.1 | status 200 |
| GET /api/site?lon=11.58&lat=48.14&radius_km=50 | 303 | 48.5 | status 200 |
| GET /api/areas/resolve?q=Bavaria | 99.7 | 61.5 | status 200 |
| GET /api/areas/resolve?q=Berlin&level=city | 9.0 | 8.4 | status 200 |
| GET /api/shapes/admin1/DEU | 413 | 370 | status 200 |
| GET /api/quick | 9.3 | 3.3 | status 200 |
| GET /api/quick/profile?area=Germany | 15.3 | 11.0 | status 200 |
| GET /api/quick/top?area=Bavaria&n=10 | 64.5 | 60.9 | status 200 |
| GET /api/quick/totals?area=Europe | 1,760 | 80.9 | status 200 |
| GET /api/quick/published?area=France | 10.9 | 9.4 | status 200 |
| GET /api/quick/prices?area=Germany | 16.1 | 15.8 | status 200 |
| GET /api/report.json?lon=11.58&lat=48.14&radius_km=25&task=data_centre | 6.7 | 3.2 | status 422 |
| GET /api/feed/DEU.json | 3,307 | 774 | status 200 |
| POST /api/maps | 1,034 | 852 | status 200 |

### quick templates: cold p50/p95 51.9 / 2,046, warm p50/p95 3.4 / 652

| | cold | warm p50 | note |
|---|---:|---:|---|
| profile Germany | 2.6 | 1.5 | prepared (Tier 0) |
| profile Bavaria | 55.8 | 49.7 | prepared (Tier 0) |
| profile Berlin | 2,046 | 3.4 | prepared (Tier 0) |
| top Germany | 1.5 | 1.4 | prepared (Tier 0) |
| top Bavaria | 51.9 | 47.6 | prepared (Tier 0) |
| top France | 1.4 | 1.2 | prepared (Tier 0) |
| totals Europe | 975 | 643 |  |
| totals United States | 4.3 | 1.7 | prepared (Tier 0) |
| compare France; Germany | 610 | 652 |  |
| published Poland | 2.5 | 1.7 |  |
| prices Germany | 135 | 136 |  |

Tier 0 state: `{"hot_ready": true, "in_hot": true, "fingerprint_now": "0593519c48d5a165", "fingerprints_stored": [["0593519c48d5a165", 22365]], "checks": [{"name": "Germany", "area_id": "a_bbf226ffbb00", "keys": ["top:10:substations", "profile:10:plants", "totals:10:plants", "top:10:plants", "top:10:data_centres"], "ids_by_name": ["a_bbf226ffbb00"], "lookup": true}, {"name": "Bavaria", "area_id": "a_16f57dda3841", "keys": ["profile:10:plants", "top:10:data_centres", "top:10:plants", "top:10:substations", "totals:10:plants"], "ids_by_name": null, "lookup": true}, {"name": "Berlin", "area_id": "a_2e72c8cc188b", "keys": ["top:10:plants", "totals:10:plants", "top:10:substations", "profile:10:plants", "top:10:data_centres"], "ids_by_name": ["a_2e72c8cc188b"], "lookup": true}], "missing_flag": false}`

### resolve_area: cold p50/p95 417 / 3,064, warm p50/p95 15.6 / 132

| | cold | warm p50 | note |
|---|---:|---:|---|
| Germany | 0.4 | 14.2 |  |
| France | 13.7 | 12.8 |  |
| Poland | 20.0 | 12.8 |  |
| Spain | 29.4 | 11.7 |  |
| Italy | 21.3 | 13.7 |  |
| United States | 11.7 | 11.6 |  |
| Nordics | 48.1 | 12.1 |  |
| EU-27 | 264 | 125 |  |
| Bavaria | 138 | 131 |  |
| Lower Saxony | 3,064 | 57.0 |  |
| Catalonia | 207 | 202 |  |
| Lombardy | 5,726 | 50.0 |  |
| Texas | 1,560 | 58.3 |  |
| California | 981 | 23.4 |  |
| Scotland | 1,796 | 17.4 |  |
| Brittany | 3,597 | 268 |  |
| Masovian Voivodeship | 2,100 | 37.4 |  |
| North Rhine-Westphalia | 1,153 | 65.6 |  |
| Andalusia | 1,963 | 50.8 |  |
| Upper Bavaria | 10.0 | 10.2 | not resolved |
| Harris County | 2,258 | 21.5 |  |
| Cook County | 812 | 13.5 |  |
| Kreis Steinfurt | 780 | 18.1 |  |
| Greater Manchester | 530 | 26.1 |  |
| Cornwall | 936 | 13.6 |  |
| Berlin | 15.2 | 15.4 |  |
| Paris | 420 | 15.4 |  |
| Madrid | 417 | 14.7 |  |
| Rome | 2,147 | 21.2 |  |
| Warsaw | 449 | 18.6 |  |
| Toulouse | 404 | 16.0 |  |
| Lyon | 14.6 | 14.2 |  |
| Hamburg | 389 | 14.7 |  |
| Munich | 358 | 15.3 |  |
| Vienna | 372 | 15.3 |  |
| Amsterdam | 600 | 13.5 |  |
| Copenhagen | 551 | 12.2 |  |
| Dublin | 370 | 14.9 |  |
| Lisbon | 335 | 13.8 |  |
| Houston | 476 | 16.1 |  |
| Leeds | 349 | 14.0 |  |
| Manchester | 337 | 14.6 |  |
| Kreuzberg | 846 | 16.5 |  |
| Schwabing | 11.0 | 10.9 | not resolved |
| Montmartre | 2,282 | 14.1 |  |
| DE-LU | 21.0 | 13.8 |  |
| NO2 | 1,281 | 124 |  |
| IT-North | 18.3 | 12.0 |  |
| Sicily | 1,264 | 101 |  |
| Saxony-Anhalt | 2,794 | 41.7 |  |

### area_stats: cold p50/p95 4.7 / 53.7, warm p50/p95 2.4 / 54.4

| | cold | warm p50 | note |
|---|---:|---:|---|
| people (city) | 2.3 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| people (region) | 57.4 | 55.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| built_up (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| built_up (region) | 54.6 | 61.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| land_cover (city) | 2.5 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| land_cover (region) | 53.7 | 52.8 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| slope (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| slope (region) | 52.1 | 52.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| solar (city) | 2.5 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| solar (region) | 52.7 | 54.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| wind (city) | 2.4 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| wind (region) | 50.3 | 49.7 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| flood (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| flood (region) | 49.4 | 48.1 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| heat_demand (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| heat_demand (region) | 49.2 | 48.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_edo_cdi (city) | 2.4 | 2.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_edo_cdi (region) | 46.8 | 46.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_effis_danger (city) | 2.4 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_effis_danger (region) | 46.7 | 46.1 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_bathy (city) | 2.5 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_bathy (region) | 46.6 | 46.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_vessel_density (city) | 4.7 | 2.4 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_eu_emodnet_vessel_density (region) | 47.8 | 46.7 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_marinecadastre_ais (city) | 2.5 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_marinecadastre_ais (region) | 46.3 | 46.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_noaa_slr (city) | 2.4 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_noaa_slr (region) | 46.4 | 46.9 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_usfs_whp (city) | 2.4 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_us_usfs_whp (region) | 46.0 | 46.0 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_gebco (city) | 2.4 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_gebco (region) | 45.7 | 46.2 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_nex_gddp (city) | 2.4 | 2.3 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |
| w9_world_nex_gddp (region) | 46.1 | 45.9 | ImportError: libexpat.so.1: cannot open shared object file: No such file or directory |

### Every table (slowest cold p95 first)

| table | cold p50 | cold p95 | warm p50 | warm p95 | MB cold | GETs | notes |
|---|---:|---:|---:|---:|---:|---:|---|
| `wave9.gb_ea_flood_zones` | 5,473 | 54,234 | 4.2 | 105 | 2,341.82 | 1221 | city: TimeoutError: query stopped after 60 s; region: TimeoutError: query stopped after 60 s |
| `main.plants` | 5,503 | 47,898 | 619 | 855 | 674.91 | 945 | region: TimeoutError: query stopped after 60 s; country: TimeoutError: query stopped after 60 s |
| `outlines.geostat_grid` | 2,946 | 45,363 | 329 | 3,988 | 206.24 | 262 |  |
| `outlines.divisions` | 15,198 | 43,087 | 112 | 686 | 5,112.71 | 3339 |  |
| `us_lmp.day_ahead` | 60.4 | 30,415 | 27.8 | 61.3 | 113.87 | 292 |  |
| `main.outages` | 78.8 | 29,062 | 80.2 | 1,079 | 245.32 | 307 |  |
| `overture_transport.segments` | 13,209 | 17,551 | 11,829 | 12,167 | 1,385.41 | 311 | region: TimeoutError: query stopped after 60 s |
| `overture_power.lines` | 2,180 | 16,449 | 223 | 16,310 | 881.44 | 185 |  |
| `wave9.it_istat_sezioni` | 2,825 | 15,143 | 796 | 12,303 | 1,424.34 | 188 |  |
| `entsoe.unit_output` | 3,103 | 13,639 | 35.7 | 334 | 17.31 | 150 |  |
| `wave9.eu_kohesio_2014_2020` | 1,950 | 11,957 | 284 | 10,960 | 460.93 | 234 |  |
| `zoning.zones` | 4,182 | 10,178 | 1,058 | 1,059 | 79.99 | 36 | country: TimeoutError: query stopped after 60 s |
| `mastr.units_storage` | 702 | 8,458 | 40.8 | 565 | 327.04 | 193 | city: TimeoutError: query stopped after 60 s; region: TimeoutError: query stopped after 60 s |
| `wave9.de_zensus_heating` | 4,125 | 8,298 | 4,267 | 4,285 | 66.59 | 80 | region: TimeoutError: query stopped after 60 s |
| `overture_power.sites` | 584 | 7,820 | 48.2 | 6,714 | 209.04 | 123 | region: TimeoutError: query stopped after 60 s |
| `afdc.stations` | 30.6 | 7,687 | 18.7 | 750 | 20.47 | 39 |  |
| `wave10.eu_nrg_stk_oam` | 4,984 | 7,650 | 59.6 | 496 | 9.87 | 144 |  |
| `wave10.eu_nrg_ti_oilm` | 2,293 | 7,159 | 11.1 | 309 | 2.14 | 51 |  |
| `wave9.eur_overture_comm_lines` | 8.4 | 6,798 | 7.4 | 6,668 | 0.00 | 0 |  |
| `mastr.units_solar` | 4,885 | 5,339 | 91.2 | 711 | 233.38 | 192 | city: TimeoutError: query stopped after 60 s; region: TimeoutError: query stopped after 60 s |
| `aqueduct.baseline_annual` | 3,048 | 5,278 | 1,010 | 2,983 | 449.05 | 115 |  |
| `wave9.cz_zsj` | 122 | 5,207 | 84.7 | 5,254 | 80.41 | 51 |  |
| `outlines.uk_ons` | 629 | 5,104 | 521 | 1,997 | 194.28 | 69 |  |
| `zoning.hub_layers` | 14.2 | 5,095 | 9.2 | 13.6 | 1.03 | 47 |  |
| `entsoe.generation` | 2,620 | 4,983 | 78.2 | 424 | 3.49 | 126 |  |
| `wave10.eu_nrg_te_oilm` | 2,269 | 4,523 | 15.8 | 456 | 2.07 | 52 |  |
| `wave10.eu_nrg_cb_oil` | 337 | 4,296 | 12.0 | 284 | 3.03 | 26 |  |
| `entsoe.congestion_costs` | 31.2 | 4,262 | 5.0 | 8.5 | 1.16 | 23 |  |
| `wave10.eu_nrg_stk_oilm` | 572 | 3,755 | 18.1 | 474 | 3.81 | 18 |  |
| `outlines.us_tracts` | 869 | 3,724 | 805 | 1,313 | 138.40 | 23 |  |
| `wave9.eu_emodnet_mpa` | 624 | 3,650 | 628 | 3,456 | 349.45 | 91 |  |
| `wave10.eu_env_ac_aeint_r2` | 379 | 3,486 | 30.7 | 530 | 6.54 | 12 |  |
| `main.water_risk` | 2,144 | 3,416 | 747 | 2,453 | 347.89 | 65 |  |
| `wave10.eu_env_ac_pefasu` | 223 | 3,209 | 27.5 | 392 | 4.03 | 18 |  |
| `wave9.us_epa_repowering` | 559 | 3,198 | 295 | 534 | 26.07 | 30 |  |
| `outlines.adm2` | 363 | 3,079 | 255 | 1,173 | 138.90 | 75 |  |
| `wave9.at_zaehlsprengel` | 284 | 2,967 | 130 | 2,986 | 95.46 | 34 |  |
| `grw.solar` | 554 | 2,898 | 488 | 2,892 | 117.60 | 75 |  |
| `wave9.us_usgs_landslides` | 1,012 | 2,720 | 304 | 2,607 | 42.58 | 47 |  |
| `wave9.gb_he_listed` | 1,246 | 2,628 | 679 | 1,699 | 39.83 | 34 |  |
| `grw.wind` | 697 | 2,492 | 321 | 1,234 | 19.33 | 34 |  |
| `small_area_energy.poverty` | 15.6 | 2,471 | 6.9 | 24.7 | 4.21 | 24 |  |
| `wave9.us_usgs_mrds` | 383 | 2,254 | 34.8 | 475 | 25.12 | 18 |  |
| `wave10.eu_env_ac_egss2` | 304 | 2,200 | 19.7 | 382 | 2.97 | 13 |  |
| `wave9.us_noaa_storm_events` | 19.5 | 2,173 | 15.7 | 202 | 6.43 | 7 |  |
| `protected.padus` | 1,144 | 2,164 | 194 | 1,544 | 229.67 | 47 |  |
| `wave9.us_nyc_ll84` | 422 | 2,066 | 288 | 484 | 19.54 | 12 |  |
| `dams.reservoirs` | 1,132 | 2,044 | 766 | 1,037 | 194.96 | 64 |  |
| `outlines.fr_iris` | 441 | 2,044 | 470 | 1,423 | 159.54 | 44 |  |
| `aqueduct.basins` | 203 | 1,994 | 171 | 782 | 118.73 | 46 |  |
| `neso.constraint_breakdown` | 26.9 | 1,994 | 4.1 | 6.0 | 0.32 | 19 |  |
| `eia930.demand` | 1,800 | 1,970 | 43.2 | 93.3 | 37.41 | 42 |  |
| `wave9.eu_emodnet_msp_zoning` | 248 | 1,813 | 174 | 222 | 72.41 | 37 |  |
| `eia930.generation_by_fuel` | 2.0 | 1,782 | 1.6 | 17.6 | 4.24 | 5 |  |
| `small_area_energy.consumption` | 414 | 1,776 | 5.3 | 127 | 42.20 | 40 |  |
| `eaglei.outages` | 44.8 | 1,769 | 36.9 | 230 | 14.23 | 26 |  |
| `outlines.us_places` | 594 | 1,665 | 632 | 803 | 73.36 | 15 |  |
| `wave10.eu_env_ac_ainah_r2` | 459 | 1,642 | 41.5 | 411 | 33.51 | 20 |  |
| `wave9.eu_emodnet_substrate` | 161 | 1,577 | 135 | 556 | 85.61 | 36 |  |
| `protected.natura2000` | 102 | 1,562 | 81.7 | 1,592 | 32.31 | 17 |  |
| `wave10.eu_nrg_cb_oilm` | 212 | 1,546 | 14.1 | 266 | 2.34 | 7 |  |
| `outlines.nl_cbs` | 130 | 1,468 | 150 | 764 | 73.36 | 30 |  |
| `wave9.us_noaa_mpa` | 181 | 1,410 | 149 | 1,049 | 133.29 | 36 |  |
| `wave10.eu_env_ac_co2fp` | 1.9 | 1,397 | 1.8 | 57.0 | 22.31 | 19 |  |
| `wave9.us_opportunity_zones` | 101 | 1,373 | 66.5 | 92.5 | 56.70 | 29 |  |
| `wave9.fr_georisques_ssp` | 301 | 1,366 | 267 | 432 | 35.07 | 12 |  |
| `wave9.ie_seai_ber` | 672 | 1,365 | 27.6 | 796 | 5.31 | 9 |  |
| `wave9.world_ourairports` | 26.9 | 1,350 | 15.7 | 346 | 6.35 | 8 |  |
| `wave9.world_ihfc_heat_flow` | 13.7 | 1,316 | 12.5 | 198 | 5.38 | 10 |  |
| `wave9.us_epa_frs_cleanups` | 68.6 | 1,296 | 19.2 | 212 | 3.44 | 5 |  |
| `outlines.small_areas` | 261 | 1,285 | 262 | 670 | 93.18 | 36 |  |
| `entsoe.flows` | 1,055 | 1,266 | 9.6 | 42.5 | 19.99 | 38 |  |
| `eia930.interchange` | 2.1 | 1,266 | 1.9 | 19.1 | 4.38 | 7 |  |
| `outlines.us_cousub` | 644 | 1,214 | 522 | 716 | 101.13 | 18 |  |
| `entsoe.load` | 882 | 1,182 | 6.2 | 268 | 2.35 | 26 |  |
| `places.cities` | 45.4 | 1,153 | 13.0 | 62.0 | 2.46 | 6 |  |
| `history.wave9__gb_brownfield_register` | 9.3 | 1,129 | 8.4 | 25.5 | 5.79 | 5 |  |
| `wave10.eu_nrg_bal_s` | 219 | 1,086 | 14.2 | 301 | 2.74 | 5 |  |
| `wave10.eu_env_ac_io10` | 24.0 | 1,072 | 21.8 | 769 | 2.56 | 2 |  |
| `wave9.es_ine_secciones` | 71.6 | 1,050 | 61.8 | 112 | 66.72 | 33 |  |
| `wave9.ee_grid` | 10.0 | 1,039 | 5.9 | 10.4 | 2.26 | 6 |  |
| `wave9.us_smu_heat_flow` | 12.8 | 1,004 | 10.0 | 62.8 | 12.67 | 11 |  |
| `wave10.gb_desnz_ghg_dataset` | 14.2 | 1,003 | 9.2 | 504 | 5.62 | 4 |  |
| `wave10.eu_env_ac_ghgfp` | 312 | 995 | 1.6 | 34.4 | 22.05 | 15 |  |
| `wave9.be_elia_balancing` | 278 | 992 | 1.7 | 45.2 | 20.22 | 13 |  |
| `aqueduct.future_annual` | 16.0 | 963 | 9.5 | 13.1 | 7.83 | 7 |  |
| `wave10.eu_env_ac_pfcfp` | 2.3 | 954 | 2.2 | 33.4 | 1.58 | 14 |  |
| `dams.barriers` | 12.7 | 944 | 11.3 | 130 | 3.97 | 5 |  |
| `wave10.eu_env_ac_nf3sf6fp` | 2.4 | 944 | 2.0 | 17.0 | 1.86 | 11 |  |
| `co2stop.dic_geocgraph_area` | 2.1 | 927 | 1.5 | 2.1 | 0.12 | 3 |  |
| `atb.electricity` | 378 | 908 | 9.2 | 27.7 | 6.41 | 7 |  |
| `main.emissions` | 3.2 | 897 | 2.5 | 9.7 | 1.23 | 4 |  |
| `wave10.eu_env_ac_hfcfp` | 1.3 | 896 | 1.2 | 22.9 | 12.60 | 17 |  |
| `wave9.gb_srn` | 10.2 | 878 | 6.9 | 720 | 15.84 | 9 |  |
| `industrial.installations` | 34.6 | 870 | 35.9 | 543 | 13.46 | 9 |  |
| `osm.eu_lines` | 9.7 | 839 | 8.2 | 66.5 | 14.32 | 10 |  |
| `mastr.units_combustion` | 17.1 | 823 | 15.7 | 325 | 12.96 | 10 |  |
| `outlines.urban_centres` | 376 | 804 | 308 | 460 | 11.00 | 11 |  |
| `wave10.eu_env_ac_ch4fp` | 381 | 799 | 1.7 | 26.9 | 6.66 | 13 |  |
| `wave9.gb_brownfield_register` | 299 | 794 | 10.1 | 196 | 4.17 | 7 |  |
| `wave9.us_usaspending_doe` | 23.0 | 794 | 16.4 | 469 | 2.89 | 5 |  |
| `aqueduct.baseline_monthly` | 7.9 | 794 | 7.0 | 7.9 | 4.86 | 5 |  |
| `wave10.eu_nrg_ind_idooil` | 2.5 | 785 | 1.9 | 2.3 | 0.15 | 3 |  |
| `gem.iron_steel_blast_furnaces` | 2.4 | 785 | 1.9 | 2.3 | 0.06 | 2 |  |
| `wave9.us_usseabed` | 86.8 | 783 | 16.4 | 446 | 1.26 | 5 |  |
| `gem.integrated_power_power_facilities` | 220 | 778 | 228 | 232 | 9.02 | 5 |  |
| `wave9.us_eia_gas_pipelines` | 12.6 | 778 | 8.2 | 491 | 4.41 | 6 |  |
| `rollups.overture_transport__segments_r7` | 290 | 771 | 16.9 | 311 | 11.82 | 14 |  |
| `connect_eu.es_dso` | 11.4 | 770 | 3.7 | 20.4 | 0.19 | 2 |  |
| `history.connect_eu__mt` | 17.9 | 756 | 16.0 | 17.1 | 0.31 | 2 |  |
| `main.prices` | 465 | 752 | 118 | 215 | 3.42 | 6 |  |
| `wave10.eu_ten00030` | 2.1 | 744 | 1.6 | 2.0 | 0.40 | 2 |  |
| `gem.iron_steel_open_hearth_furnaces` | 1.8 | 742 | 1.8 | 1.9 | 0.06 | 2 |  |
| `wave9.us_boem_wind_leases` | 36.5 | 741 | 5.8 | 32.4 | 2.38 | 4 |  |
| `wave10.eu_env_air_no2` | 3.0 | 737 | 2.7 | 3.0 | 0.54 | 3 |  |
| `gem.oil_infrastructure_data` | 2.1 | 735 | 2.0 | 2.0 | 0.22 | 2 |  |
| `wave10.eu_sdg_09_50` | 2.2 | 733 | 1.6 | 2.1 | 0.07 | 2 |  |
| `wave10.gb_dft_evcd_rapid` | 2.2 | 732 | 1.2 | 2.1 | 1.80 | 2 |  |
| `wave10.eu_env_ac_rmefd` | 18.0 | 732 | 16.3 | 708 | 0.05 | 2 |  |
| `wave10.eu_road_eqs_motorc` | 2.3 | 727 | 1.5 | 2.2 | 0.03 | 2 |  |
| `wave9.rs_ems_connection_queue` | 2.6 | 725 | 1.7 | 2.3 | 0.03 | 2 |  |
| `gem.coal_terminals_terminals` | 36.1 | 713 | 24.9 | 25.5 | 0.06 | 2 |  |
| `gem.methane_emitters_pipelines` | 2.1 | 706 | 1.7 | 2.0 | 0.81 | 2 |  |
| `ev_eu.lt` | 10.8 | 704 | 2.7 | 14.4 | 0.04 | 2 |  |
| `ev_eu.pl` | 10.5 | 703 | 2.7 | 10.1 | 0.19 | 2 |  |
| `wave10.eu_sdg_12_10` | 2.2 | 699 | 1.6 | 2.0 | 0.00 | 1 |  |
| `ev_eu.se` | 11.1 | 696 | 3.6 | 12.9 | 0.28 | 2 |  |
| `entsog.operator_point_directions` | 8.7 | 694 | 6.4 | 8.2 | 0.13 | 2 |  |
| `wave9.dk_energinet_reserves` | 1.6 | 694 | 1.1 | 10.8 | 3.62 | 4 |  |
| `industrial.water_releases` | 22.2 | 691 | 16.1 | 207 | 3.61 | 4 |  |
| `wave9.eu_emodnet_military` | 8.7 | 691 | 4.6 | 304 | 2.35 | 3 |  |
| `ev_eu.be` | 10.2 | 685 | 3.2 | 10.2 | 0.35 | 2 |  |
| `wave9.ie_cso_saps_heating` | 12.5 | 683 | 11.0 | 55.9 | 10.34 | 6 |  |
| `hotmaps.industrial_sites` | 1.4 | 676 | 1.1 | 1.3 | 0.35 | 2 |  |
| `wave10.eu_env_ac_n2ofp` | 1.6 | 674 | 1.3 | 14.4 | 8.25 | 13 |  |
| `gem.coal_mines_change_log` | 1.5 | 674 | 1.2 | 1.4 | 0.03 | 2 |  |
| `wave9.gb_defra_aurn` | 16.0 | 669 | 9.3 | 13.5 | 0.09 | 2 |  |
| `wave10.eu_nrg_pc_202_v` | 4.3 | 668 | 2.4 | 3.2 | 0.54 | 3 |  |
| `wave10.eu_rail_eq_pa_csb` | 3.1 | 666 | 2.3 | 3.0 | 0.53 | 3 |  |
| `wave9.us_eia_crude_rail` | 10.5 | 665 | 6.5 | 9.4 | 0.04 | 3 |  |
| `history.connect_eu__de` | 1.5 | 664 | 1.1 | 1.5 | 0.06 | 2 |  |
| `history.registers__be` | 3.9 | 662 | 2.8 | 3.9 | 0.40 | 2 |  |
| `wave10.eu_cei_cie011` | 3.2 | 659 | 2.2 | 3.3 | 0.05 | 3 |  |
| `wave10.eu_nrg_ind_id3cf` | 3.3 | 658 | 2.9 | 3.2 | 0.81 | 4 |  |
| `wave9.gb_hnpd` | 8.8 | 657 | 5.0 | 9.5 | 0.28 | 3 |  |
| `wave10.eu_tran_hv_psmod` | 2.1 | 654 | 1.7 | 2.1 | 1.38 | 2 |  |
| `wave10.eu_road_eqs_carage` | 2.3 | 653 | 1.7 | 2.1 | 0.14 | 2 |  |
| `wave9.gb_npg_opendata` | 2.2 | 651 | 1.6 | 2.0 | 0.14 | 2 |  |
| `eredes_capacity.substations` | 2.3 | 651 | 2.2 | 2.3 | 0.06 | 2 |  |
| `co2stop.dic_status` | 648 | 648 | 1.5 | 1.5 | 0.03 | 2 |  |
| `wave10.eu_cei_srm030` | 3.2 | 647 | 2.2 | 3.0 | 0.04 | 3 |  |
| `entsog.points` | 3.2 | 643 | 2.6 | 3.1 | 0.10 | 2 |  |
| `history.eredes_capacity__substations` | 2.3 | 643 | 2.0 | 2.2 | 0.45 | 3 |  |
| `history.connect_eu__es_dso` | 12.1 | 643 | 4.1 | 24.1 | 0.16 | 2 |  |
| `history.connect_eu__cz` | 24.1 | 639 | 15.5 | 24.7 | 0.14 | 2 |  |
| `econnextion.requests` | 3.7 | 637 | 3.0 | 3.6 | 0.04 | 2 |  |
| `ghgrp.facilities` | 16.8 | 637 | 3.6 | 15.4 | 0.60 | 2 |  |
| `co2stop.storage_units_user_and_database_calc_storage` | 1.4 | 634 | 1.0 | 1.3 | 0.00 | 1 |  |
| `gem.gas_infrastructure_lng_terminals` | 28.6 | 634 | 27.3 | 28.1 | 0.30 | 2 |  |
| `wave10.eu_env_ac_epissp1` | 3.7 | 633 | 3.2 | 3.4 | 0.06 | 3 |  |
| `gem.methane_emitters_coal_mines_non_closed` | 98.1 | 627 | 26.5 | 26.9 | 0.27 | 2 |  |
| `wave9.us_nrc_operating_reactors` | 627 | 627 | 1.4 | 1.4 | 0.07 | 3 |  |
| `wave9.gr_admie_balancing` | 193 | 626 | 1.9 | 22.4 | 9.37 | 7 |  |
| `wave10.eu_sdg_13_21` | 2.1 | 623 | 1.5 | 2.0 | 0.21 | 2 |  |
| `wave10.eu_nrg_inf_bt` | 2.3 | 623 | 1.7 | 2.2 | 0.03 | 2 |  |
| `co2stop.dic_age` | 621 | 621 | 1.4 | 1.4 | 0.07 | 2 |  |
| `wave9.fr_enedis_interruptions` | 5.4 | 619 | 1.1 | 2.2 | 0.03 | 2 |  |
| `wave10.eu_nrg_ind_esr` | 3.0 | 619 | 2.1 | 2.9 | 0.40 | 3 |  |
| `wave10.eu_nrg_ind_rctcbt` | 2.1 | 617 | 1.9 | 2.2 | 0.04 | 2 |  |
| `industrial.air_releases` | 19.0 | 616 | 16.2 | 299 | 6.94 | 7 |  |
| `co2stop.hydrocarbon_formations` | 20.4 | 615 | 17.4 | 19.3 | 0.09 | 2 |  |
| `co2stop.dic_assess_type` | 615 | 615 | 1.7 | 1.7 | 0.04 | 2 |  |
| `gem.oil_gas_extraction_project_level_main_data` | 15.8 | 614 | 12.4 | 13.5 | 0.12 | 2 |  |
| `connect_eu.mt` | 16.4 | 614 | 15.6 | 16.8 | 0.15 | 2 |  |
| `ev_eu.dk` | 10.6 | 614 | 2.8 | 9.5 | 0.26 | 2 |  |
| `wave10.eu_road_eqs_busveh` | 3.2 | 614 | 2.3 | 3.1 | 0.34 | 3 |  |
| `rollups.overture_power__lines_r6` | 84.3 | 612 | 5.1 | 81.7 | 3.57 | 6 |  |
| `wave10.eu_sdg_13_11` | 3.1 | 612 | 2.4 | 3.0 | 0.53 | 3 |  |
| `eaglei.counties` | 3.0 | 611 | 1.4 | 3.0 | 0.08 | 2 |  |
| `gem.chemicals_plant_data` | 2.6 | 610 | 2.0 | 2.4 | 0.22 | 2 |  |
| `pse_capacity.requests` | 3.7 | 610 | 2.0 | 3.6 | 0.08 | 3 |  |
| `wave10.eu_sdg_07_10` | 3.1 | 608 | 2.3 | 3.0 | 0.54 | 3 |  |
| `registers.pt` | 16.9 | 607 | 4.4 | 16.3 | 0.10 | 2 |  |
| `wave10.eu_rail_if_line_tr` | 2.5 | 607 | 1.9 | 2.3 | 0.28 | 2 |  |
| `co2stop.dic_pred_lith` | 607 | 607 | 1.7 | 1.7 | 0.04 | 2 |  |
| `wave10.eu_env_ac_cur` | 2.3 | 605 | 1.5 | 2.0 | 0.06 | 3 |  |
| `connect_eu.cz` | 22.8 | 605 | 15.9 | 23.7 | 0.05 | 2 |  |
| `wave10.eu_cei_pc032` | 2.0 | 603 | 1.5 | 2.0 | 0.04 | 2 |  |
| `wave9.pl_pse_balancing` | 363 | 603 | 2.1 | 12.7 | 2.60 | 4 |  |
| `connect_eu.se` | 2.4 | 601 | 1.7 | 2.3 | 0.02 | 2 |  |
| `connect_eu.de` | 2.0 | 600 | 1.2 | 1.5 | 0.07 | 3 |  |
| `history.esb_heatmap__transformers` | 13.3 | 599 | 11.0 | 11.5 | 2.23 | 4 |  |
| `wave10.eu_cei_cie012` | 2.1 | 599 | 1.6 | 2.1 | 0.04 | 2 |  |
| `wave9.fr_ore_ev_commune` | 294 | 599 | 1.3 | 13.7 | 2.22 | 4 |  |
| `history.connect_eu__lt` | 16.6 | 598 | 15.9 | 16.1 | 0.06 | 2 |  |
| `wave10.eu_ten00138` | 2.3 | 598 | 2.2 | 2.8 | 1.70 | 2 |  |
| `rollups.overture_power__lines_r5` | 69.1 | 597 | 5.7 | 76.5 | 2.37 | 2 |  |
| `gem.methane_emitters_lng_terminals` | 19.1 | 597 | 12.9 | 13.0 | 0.16 | 3 |  |
| `entsoe.forecast_wind_solar` | 371 | 597 | 12.2 | 38.6 | 0.05 | 11 |  |
| `wave10.eu_ten00124` | 2.4 | 596 | 1.6 | 2.2 | 0.42 | 2 |  |
| `wave9.eu_emodnet_ports` | 6.1 | 596 | 2.7 | 6.2 | 0.78 | 3 |  |
| `wave9.us_epa_aqs_annual` | 12.2 | 596 | 10.3 | 171 | 3.62 | 4 |  |
| `gem.coal_mines_historical_production_non_china` | 2.5 | 594 | 2.3 | 2.5 | 0.07 | 2 |  |
| `ev_eu.fi` | 11.5 | 594 | 2.8 | 15.5 | 0.10 | 2 |  |
| `wave10.eu_env_ac_pefa05` | 3.5 | 592 | 2.5 | 3.3 | 0.06 | 3 |  |
| `co2stop.dgf_input` | 591 | 591 | 4.0 | 4.0 | 0.10 | 2 |  |
| `history.connect_eu__se` | 2.3 | 591 | 1.5 | 2.2 | 0.04 | 2 |  |
| `wave10.eu_sdg_06_10` | 2.3 | 589 | 1.6 | 2.2 | 0.02 | 2 |  |
| `wave10.eu_road_eqr_tracmot` | 3.2 | 588 | 2.2 | 3.0 | 0.71 | 4 |  |
| `wave10.eu_sdg_07_11` | 2.2 | 588 | 1.6 | 2.1 | 0.03 | 2 |  |
| `gem.gas_infrastructure_pipelines` | 1.9 | 587 | 1.5 | 1.8 | 0.40 | 2 |  |
| `gem.gas_finance_lng_terminals` | 2.6 | 587 | 2.1 | 2.6 | 0.06 | 2 |  |
| `wave9.be_fluvius_consumption` | 1.2 | 585 | 1.1 | 10.2 | 5.89 | 4 |  |
| `wave10.eu_nrg_ind_rcaebt` | 3.3 | 584 | 2.6 | 3.1 | 0.40 | 3 |  |
| `rollups.wave9__de_zensus_heating_r5` | 12.7 | 584 | 8.8 | 22.1 | 0.04 | 2 |  |
| `wave9.us_eia_product_terminals` | 12.4 | 583 | 2.7 | 13.3 | 0.11 | 2 |  |
| `wave9.eu_new_cars_fuel` | 2.3 | 583 | 1.9 | 2.2 | 0.02 | 1 |  |
| `co2stop.total_storecap_nolargestorage_countries` | 1.9 | 582 | 1.6 | 2.0 | 0.06 | 2 |  |
| `wave10.eu_road_eqr_trail` | 2.1 | 582 | 1.8 | 2.3 | 0.01 | 1 |  |
| `ev_eu.es` | 16.4 | 582 | 4.0 | 23.7 | 0.19 | 2 |  |
| `connect_eu.lt` | 17.6 | 581 | 15.4 | 21.2 | 0.07 | 2 |  |
| `co2stop.country_totals` | 1.5 | 581 | 1.1 | 1.4 | 0.07 | 2 |  |
| `history.pse_capacity__full_substations` | 1.8 | 581 | 1.8 | 1.8 | 0.02 | 2 |  |
| `wave10.eu_rail_eq_pa_cty` | 2.2 | 581 | 1.6 | 1.9 | 0.44 | 2 |  |
| `wave9.eu_cleanh2_electrolyser_mfg` | 578 | 578 | 1.0 | 1.0 | 0.14 | 2 |  |
| `wave10.eu_env_ac_epite1` | 2.0 | 578 | 1.5 | 1.9 | 0.03 | 2 |  |
| `wave10.eu_ten00137` | 3.1 | 578 | 2.2 | 3.1 | 0.54 | 3 |  |
| `euets.verified_emissions` | 30.8 | 578 | 28.5 | 112 | 4.07 | 3 |  |
| `co2stop.hydrocarbon_traps_temp` | 37.1 | 577 | 34.3 | 36.7 | 0.07 | 2 |  |
| `gem.coal_mines_historical_production_china` | 1.7 | 577 | 1.6 | 1.6 | 0.07 | 2 |  |
| `wave10.eu_sdg_11_60` | 3.0 | 576 | 2.1 | 3.0 | 0.31 | 3 |  |
| `co2stop.dic_content` | 575 | 575 | 1.7 | 1.7 | 0.00 | 1 |  |
| `entsoe.areas` | 1.4 | 573 | 1.2 | 1.4 | 0.00 | 1 |  |
| `history.registers__pt` | 16.8 | 572 | 5.0 | 16.8 | 0.19 | 3 |  |
| `ev_eu.cy` | 16.1 | 572 | 3.3 | 20.0 | 0.06 | 3 |  |
| `connect_eu.at` | 3.4 | 572 | 1.6 | 3.2 | 0.04 | 2 |  |
| `wave10.eu_road_eqr_carpda` | 2.3 | 571 | 1.8 | 2.2 | 0.02 | 1 |  |
| `gem.coal_mines_historic_production_2018_2025` | 2.5 | 571 | 1.9 | 2.5 | 0.22 | 3 |  |
| `wave10.eu_road_eqr_carmot` | 3.2 | 570 | 2.4 | 3.2 | 0.54 | 3 |  |
| `co2stop.dic_distrib_type` | 570 | 570 | 1.0 | 1.0 | 0.07 | 2 |  |
| `ev_eu.sk` | 16.7 | 569 | 3.8 | 22.9 | 0.09 | 2 |  |
| `wave10.gb_census_households` | 2.8 | 569 | 2.0 | 2.8 | 0.53 | 3 |  |
| `ev_eu.hr` | 16.7 | 568 | 4.0 | 22.1 | 0.10 | 2 |  |
| `wave10.eu_cei_pc031` | 3.5 | 567 | 2.1 | 2.9 | 0.05 | 3 |  |
| `co2stop.dic_methods` | 567 | 567 | 1.5 | 1.5 | 0.04 | 2 |  |
| `gem.iron_steel_plant_data` | 2.9 | 565 | 2.2 | 2.8 | 0.28 | 2 |  |
| `gem.iron_steel_basic_oxygen_furnaces` | 2.4 | 564 | 1.8 | 2.4 | 0.07 | 2 |  |
| `gem.iron_ore_mines_main_data` | 1.8 | 564 | 1.6 | 1.9 | 0.10 | 1 |  |
| `gem.iron_steel_direct_reduced_iron_furnaces` | 1.8 | 563 | 1.3 | 1.7 | 0.04 | 2 |  |
| `wave10.eu_cei_srm040` | 11.5 | 562 | 2.2 | 10.6 | 0.04 | 2 |  |
| `wave10.eu_nrg_ind_di` | 3.0 | 562 | 2.1 | 2.9 | 0.27 | 3 |  |
| `wave10.gb_dft_evcd_per_100k` | 562 | 562 | 1.5 | 1.5 | 0.62 | 3 |  |
| `eaglei.dqi` | 3.5 | 561 | 1.8 | 3.1 | 0.04 | 2 |  |
| `wave9.lv_csp_central_heating` | 6.7 | 561 | 5.6 | 499 | 0.02 | 1 |  |
| `wave10.eu_road_eqs_mopeds` | 3.3 | 560 | 2.5 | 3.2 | 0.41 | 3 |  |
| `wave10.eu_env_ac_rp` | 2.1 | 558 | 1.6 | 2.1 | 0.03 | 2 |  |
| `ev_eu.hu` | 10.6 | 557 | 2.6 | 13.4 | 0.16 | 2 |  |
| `gem.integrated_power_regions_area_and_countries` | 2.4 | 556 | 1.9 | 2.4 | 0.05 | 2 |  |
| `ev_eu.lv` | 16.0 | 556 | 3.5 | 20.8 | 0.07 | 2 |  |
| `co2stop.hydrocarbon_traps` | 37.5 | 555 | 34.1 | 36.2 | 0.16 | 2 |  |
| `wave10.eu_sdg_09_40` | 3.3 | 552 | 2.5 | 3.1 | 0.41 | 3 |  |
| `wave10.eu_tran_hv_ms_psmod` | 3.5 | 552 | 3.0 | 3.8 | 0.40 | 3 |  |
| `wave10.eu_ten00123` | 3.4 | 550 | 3.1 | 3.2 | 0.16 | 2 |  |
| `history.connect_eu__at` | 3.4 | 549 | 1.8 | 3.3 | 0.03 | 2 |  |
| `wave10.eu_ten00006` | 3.6 | 549 | 2.4 | 3.3 | 0.28 | 2 |  |
| `wave10.eu_rail_if_line_sp` | 3.2 | 548 | 2.4 | 3.0 | 0.53 | 3 |  |
| `gem.oil_gas_extraction_project_level_reserves_data` | 2.1 | 546 | 1.6 | 2.1 | 0.03 | 2 |  |
| `co2stop.total_storage_cap_aquif_hcfields` | 3.2 | 545 | 1.7 | 2.2 | 1.22 | 2 |  |
| `wave10.eu_env_ac_ainah_rd` | 274 | 545 | 22.4 | 181 | 3.92 | 3 |  |
| `wave10.eu_nrg_ti_oil` | 338 | 545 | 16.2 | 615 | 1.10 | 1 |  |
| `co2stop.dic_yes_no` | 540 | 540 | 1.4 | 1.4 | 0.07 | 2 |  |
| `osm.datacentres` | 165 | 539 | 22.5 | 40.0 | 1.24 | 5 |  |
| `connect_eu.ee` | 16.0 | 537 | 3.8 | 17.0 | 0.07 | 2 |  |
| `gem.iron_steel_induction_furnaces` | 2.3 | 534 | 1.8 | 2.2 | 0.02 | 2 |  |
| `co2stop.dic_geocapacity_countries` | 2.8 | 531 | 1.9 | 1.9 | 1.78 | 2 |  |
| `tri.releases` | 531 | 531 | 2.5 | 2.5 | 0.02 | 1 |  |
| `ev_eu.ro` | 16.5 | 530 | 3.7 | 19.9 | 0.07 | 3 |  |
| `gem.methane_emitters_oil_and_gas_reserves` | 22.2 | 530 | 21.1 | 21.5 | 0.11 | 2 |  |
| `ev_eu.nl` | 37.6 | 528 | 15.1 | 76.2 | 4.39 | 3 |  |
| `wave10.eu_nrg_te_oil` | 231 | 527 | 14.6 | 470 | 1.06 | 1 |  |
| `history.connect_eu__ee` | 16.1 | 522 | 3.3 | 15.3 | 0.54 | 3 |  |
| `outlines.aliases` | 81.2 | 517 | 62.1 | 65.7 | 3.39 | 4 |  |
| `mastr.units_wind` | 19.6 | 492 | 11.6 | 150 | 9.60 | 6 |  |
| `wave9.eu_tent_network` | 7.3 | 491 | 6.1 | 262 | 0.00 | 0 |  |
| `wave9.us_usgs_nwis_sites` | 281 | 489 | 44.5 | 490 | 10.61 | 7 |  |
| `wave9.se_svk_reserves` | 229 | 487 | 1.4 | 46.9 | 12.57 | 7 |  |
| `wave10.eu_nrg_ti_coifpm` | 16.7 | 480 | 16.5 | 417 | 0.00 | 0 |  |
| `wave10.eu_nrg_stk_oom` | 386 | 468 | 20.9 | 342 | 1.20 | 1 |  |
| `mastr.units_biomass` | 18.8 | 465 | 18.0 | 135 | 5.42 | 5 |  |
| `wave10.wb_eg_elc_rnew_zs` | 3.1 | 447 | 2.0 | 2.8 | 0.06 | 1 |  |
| `wave9.de_regelleistung` | 2.2 | 445 | 1.8 | 11.1 | 2.46 | 3 |  |
| `wave9.us_natcarb` | 339 | 439 | 18.4 | 330 | 5.74 | 9 |  |
| `ev_eu.fr` | 10.8 | 436 | 10.9 | 71.4 | 3.88 | 3 |  |
| `wave9.us_nrhp` | 52.8 | 428 | 19.3 | 344 | 6.96 | 6 |  |
| `power_plants_eu.ppm_plants` | 236 | 425 | 28.6 | 284 | 8.16 | 5 |  |
| `wave9.fi_statfin_heating_fuel_municipality` | 10.8 | 418 | 10.8 | 410 | 0.00 | 0 |  |
| `nl_capacity.areas` | 6.7 | 416 | 5.7 | 414 | 0.00 | 0 |  |
| `esb_heatmap.transformers` | 14.2 | 414 | 11.9 | 12.2 | 2.21 | 3 |  |
| `industrial.lcp` | 10.8 | 399 | 9.0 | 175 | 4.18 | 2 |  |
| `ev_eu.de` | 16.7 | 394 | 14.3 | 141 | 4.50 | 4 |  |
| `entsoe.prices` | 222 | 389 | 3.7 | 17.5 | 2.26 | 4 |  |
| `wave10.eu_nrg_ind_resovsh` | 3.0 | 379 | 2.9 | 3.0 | 0.03 | 1 |  |
| `wave10.wb_en_atm_pm25_mc_t2_zs` | 3.6 | 378 | 2.4 | 3.4 | 0.02 | 1 |  |
| `wave10.eu_env_esst_cepgg` | 46.2 | 377 | 4.6 | 48.0 | 0.13 | 1 |  |
| `app.eu_lines` | 7.8 | 375 | 5.2 | 374 | 0.00 | 0 |  |
| `gem.oil_gas_extraction_field_level_main_data` | 43.4 | 369 | 43.8 | 44.4 | 3.06 | 3 |  |
| `wave10.eu_env_ac_pefafp` | 3.8 | 365 | 3.4 | 357 | 0.00 | 0 |  |
| `wave10.wb_it_net_bbnd` | 3.6 | 364 | 2.0 | 3.5 | 0.03 | 1 |  |
| `wave9.de_bfee_abwaerme` | 208 | 364 | 12.0 | 14.7 | 2.36 | 3 |  |
| `wave9.si_surs_heating_settlement` | 7.3 | 364 | 5.4 | 372 | 0.00 | 0 |  |
| `wave9.gb_emr_cm_register` | 8.2 | 363 | 6.9 | 8.2 | 0.64 | 1 |  |
| `wave10.wb_en_ghg_ch4_tr_mt_ce_ar5` | 3.7 | 362 | 2.1 | 4.0 | 0.06 | 1 |  |
| `wave10.wb_ny_adj_dfor_gn_zs` | 3.6 | 360 | 2.1 | 3.4 | 0.03 | 1 |  |
| `wave10.wb_sp_urb_totl_in_zs` | 3.2 | 360 | 2.3 | 3.1 | 0.07 | 1 |  |
| `wave9.eu_emodnet_platforms` | 7.6 | 359 | 3.5 | 8.0 | 0.00 | 0 |  |
| `wave9.eu_emodnet_wwtp` | 12.2 | 358 | 10.3 | 59.5 | 1.78 | 1 |  |
| `wave10.wb_ie_ppn_tran_cd` | 3.3 | 354 | 2.0 | 3.0 | 0.01 | 1 |  |
| `wave9.eu_emodnet_port_goods` | 10.2 | 353 | 9.3 | 353 | 0.00 | 0 |  |
| `wave10.eu_env_ac_ccminv` | 4.3 | 351 | 2.4 | 3.3 | 0.06 | 1 |  |
| `wave10.wb_ny_adj_dfor_cd` | 3.9 | 350 | 2.4 | 4.0 | 0.03 | 1 |  |
| `wave10.wb_er_h2o_fwst_zs` | 4.2 | 350 | 2.5 | 4.2 | 0.04 | 1 |  |
| `wave10.eu_nrg_ind_pehap` | 23.0 | 343 | 5.4 | 22.2 | 0.19 | 1 |  |
| `wave9.eu_eea_wei` | 339 | 339 | 2.0 | 2.0 | 0.40 | 1 |  |
| `wave10.gb_desnz_co2_la` | 11.5 | 339 | 2.3 | 10.9 | 2.07 | 1 |  |
| `wave10.wb_ie_ppi_icti_cd` | 3.3 | 337 | 1.9 | 3.2 | 0.01 | 1 |  |
| `wave10.wb_en_ghg_n2o_wa_mt_ce_ar5` | 3.3 | 337 | 1.8 | 3.1 | 0.06 | 1 |  |
| `wave10.wb_er_fsh_aqua_mt` | 2.8 | 333 | 1.6 | 2.7 | 0.04 | 1 |  |
| `wave10.eu_nrg_te_sff` | 176 | 330 | 8.0 | 102 | 0.11 | 1 |  |
| `wave10.eu_env_ac_aibrid_r2` | 212 | 329 | 15.2 | 95.7 | 2.66 | 3 |  |
| `wave10.eu_nrg_ind_id` | 3.3 | 326 | 2.9 | 3.2 | 0.03 | 1 |  |
| `wave10.eu_env_ac_pepsns1` | 50.0 | 324 | 5.9 | 43.4 | 0.25 | 1 |  |
| `small_area_energy.renewables` | 7.0 | 322 | 4.9 | 6.9 | 0.51 | 1 |  |
| `wave10.wb_is_air_good_mt_k1` | 3.2 | 319 | 1.7 | 3.3 | 0.05 | 1 |  |
| `wave10.wb_er_h2o_fwtl_k3` | 3.1 | 316 | 2.0 | 2.7 | 0.04 | 1 |  |
| `wave10.wb_se_prm_cmpt_zs` | 3.1 | 316 | 1.6 | 2.9 | 0.04 | 1 |  |
| `wave10.eu_nrg_cb_rw` | 56.1 | 315 | 7.6 | 60.8 | 0.34 | 1 |  |
| `wave10.wb_eg_elc_nucl_zs` | 3.1 | 314 | 1.8 | 3.0 | 0.03 | 1 |  |
| `wave10.wb_eg_elc_accs_zs` | 3.5 | 310 | 2.1 | 3.7 | 0.03 | 1 |  |
| `wave10.eu_env_ac_pepsgg1` | 15.9 | 310 | 4.3 | 15.2 | 0.08 | 1 |  |
| `wave10.wb_it_cel_sets_p2` | 3.0 | 308 | 1.6 | 2.6 | 0.07 | 1 |  |
| `wave10.eu_nrg_te_gasm` | 14.9 | 307 | 14.1 | 314 | 0.26 | 1 |  |
| `wave10.wb_ny_adj_svnx_gn_zs` | 3.6 | 305 | 2.0 | 3.5 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_tot_zg_ar5` | 2.7 | 304 | 1.5 | 2.6 | 0.07 | 1 |  |
| `wave10.wb_en_ghg_co2_ip_mt_ce_ar5` | 3.7 | 304 | 2.2 | 3.9 | 0.07 | 1 |  |
| `wave10.eu_road_eqr_zev` | 2.6 | 304 | 1.9 | 2.5 | 0.03 | 1 |  |
| `wave10.wb_ag_lnd_arbl_zs` | 2.8 | 303 | 1.6 | 2.7 | 0.05 | 1 |  |
| `gem.energy_ownership_gas_plant_ownership` | 1.4 | 303 | 1.2 | 1.5 | 0.00 | 1 |  |
| `gem.energy_ownership_coal_plant_ownership` | 2.0 | 303 | 1.8 | 2.7 | 0.00 | 1 |  |
| `wave10.eu_nrg_cb_eim` | 4.1 | 301 | 4.0 | 4.0 | 0.09 | 1 |  |
| `wave10.wb_sh_med_cmhw_p3` | 3.2 | 301 | 1.8 | 2.8 | 0.01 | 1 |  |
| `wave10.wb_en_atm_pm25_mc_t3_zs` | 2.8 | 298 | 1.6 | 2.5 | 0.02 | 1 |  |
| `wave10.wb_it_net_user_ma_zs` | 3.6 | 298 | 2.2 | 3.3 | 0.02 | 1 |  |
| `wave9.gb_nged_opendata` | 19.4 | 298 | 19.2 | 42.2 | 0.83 | 1 |  |
| `wave10.wb_is_air_dprt` | 4.4 | 297 | 2.5 | 4.4 | 0.03 | 1 |  |
| `wave10.wb_ny_adj_dpem_gn_zs` | 2.7 | 297 | 1.5 | 2.6 | 0.05 | 1 |  |
| `wave10.wb_en_ghg_n2o_fe_mt_ce_ar5` | 4.1 | 297 | 1.9 | 3.2 | 0.05 | 1 |  |
| `wave10.wb_ag_lnd_irig_ag_zs` | 3.1 | 293 | 1.5 | 2.7 | 0.02 | 1 |  |
| `wave10.wb_bx_gsr_ccis_zs` | 3.2 | 293 | 2.2 | 3.8 | 0.05 | 1 |  |
| `wave10.wb_sh_sta_maln_zs` | 3.6 | 293 | 1.8 | 3.4 | 0.01 | 1 |  |
| `wave10.eu_env_ac_tax` | 4.2 | 291 | 3.9 | 4.1 | 0.04 | 1 |  |
| `wave10.eu_env_epea_trf` | 52.1 | 291 | 4.1 | 6.2 | 0.03 | 1 |  |
| `wave10.wb_eg_use_comm_fo_zs` | 4.0 | 290 | 1.6 | 3.1 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_co2_lu_df_mt_ce_ar5` | 2.5 | 290 | 1.5 | 2.5 | 0.03 | 1 |  |
| `wave10.wb_ny_gdp_totl_rt_zs` | 3.2 | 290 | 1.8 | 3.0 | 0.06 | 1 |  |
| `wave10.wb_en_ghg_co2_rt_gdp_kd` | 3.4 | 289 | 2.1 | 3.7 | 0.07 | 1 |  |
| `wave10.eu_nrg_cb_pem` | 35.0 | 289 | 6.8 | 33.0 | 0.66 | 1 |  |
| `wave10.eu_env_ac_mfain` | 5.1 | 289 | 3.9 | 4.8 | 0.10 | 1 |  |
| `wave10.eu_nrg_ind_peh` | 53.2 | 289 | 6.4 | 51.1 | 0.30 | 1 |  |
| `wave10.eu_env_ac_egss1` | 96.1 | 288 | 13.0 | 96.1 | 0.46 | 1 |  |
| `wave10.eu_nrg_cb_em` | 4.9 | 288 | 3.3 | 4.5 | 0.17 | 1 |  |
| `registers.cz` | 7.2 | 288 | 5.9 | 7.0 | 0.82 | 1 |  |
| `wave10.eu_env_epea_invap` | 17.9 | 288 | 5.4 | 16.7 | 0.09 | 1 |  |
| `wave10.wb_eg_use_comm_cl_zs` | 4.1 | 286 | 2.3 | 3.9 | 0.05 | 1 |  |
| `wave10.wb_sh_sta_smss_ru_zs` | 4.0 | 286 | 2.3 | 3.8 | 0.03 | 1 |  |
| `wave10.wb_en_ghg_all_pc_ce_ar5` | 3.5 | 286 | 1.6 | 3.2 | 0.07 | 1 |  |
| `wave10.wb_ag_lnd_agri_k2` | 3.1 | 285 | 1.8 | 3.0 | 0.03 | 1 |  |
| `wave10.gb_census_travel_method` | 3.7 | 284 | 2.5 | 3.6 | 0.03 | 1 |  |
| `wave10.wb_ie_ppn_icti_cd` | 4.1 | 284 | 2.4 | 4.1 | 0.01 | 1 |  |
| `wave10.wb_ag_lnd_frst_zs` | 3.7 | 283 | 2.2 | 3.6 | 0.06 | 1 |  |
| `wave10.wb_sh_sta_smss_ur_zs` | 2.7 | 282 | 1.6 | 2.6 | 0.03 | 1 |  |
| `wave10.wb_ic_frm_bnks_zs` | 2.6 | 281 | 1.5 | 2.5 | 0.02 | 1 |  |
| `wave9.ee_stat_heating_2011` | 15.4 | 281 | 3.6 | 14.2 | 0.06 | 1 |  |
| `wave10.wb_en_ghg_ch4_pi_mt_ce_ar5` | 3.7 | 280 | 2.2 | 3.7 | 0.05 | 1 |  |
| `egrid.plants` | 16.9 | 280 | 16.4 | 46.3 | 2.52 | 2 |  |
| `wave10.eu_env_ac_eptrf1` | 10.9 | 280 | 4.2 | 10.2 | 0.05 | 1 |  |
| `wave10.wb_en_ghg_n2o_bu_mt_ce_ar5` | 3.7 | 279 | 2.2 | 4.0 | 0.06 | 1 |  |
| `wave10.wb_sp_urb_totl` | 3.5 | 278 | 2.2 | 3.8 | 0.04 | 1 |  |
| `wave10.wb_en_urb_mcty_tl_zs` | 3.8 | 277 | 2.2 | 3.9 | 0.04 | 1 |  |
| `wave10.wb_bx_gsr_ccis_cd` | 3.5 | 277 | 2.2 | 3.8 | 0.05 | 1 |  |
| `wave10.wb_ny_adj_svnx_cd` | 3.8 | 277 | 2.2 | 3.8 | 0.04 | 1 |  |
| `wave10.wb_eg_elc_accs_ur_zs` | 4.0 | 276 | 2.3 | 3.9 | 0.03 | 1 |  |
| `shapes.nuts` | 7.8 | 276 | 3.9 | 265 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_eff` | 4.1 | 275 | 3.7 | 3.8 | 0.02 | 1 |  |
| `wave10.wb_ic_elc_durs` | 4.4 | 274 | 2.5 | 4.3 | 0.02 | 1 |  |
| `wave9.eu_household_income` | 6.2 | 274 | 5.7 | 5.7 | 0.26 | 1 |  |
| `wave10.wb_en_ghg_co2_lu_ol_mt_ce_ar5` | 3.4 | 274 | 1.9 | 3.4 | 0.03 | 1 |  |
| `wave9.world_ourairports_navaids` | 10.6 | 274 | 7.7 | 62.8 | 0.61 | 1 |  |
| `wave10.wb_eg_elc_petr_zs` | 3.9 | 274 | 2.3 | 3.9 | 0.06 | 1 |  |
| `wave10.wb_sh_sta_hygn_zs` | 3.8 | 273 | 2.2 | 3.5 | 0.02 | 1 |  |
| `wave10.wb_ag_lnd_agri_zs` | 4.1 | 272 | 2.2 | 3.7 | 0.06 | 1 |  |
| `wave10.wb_se_enr_prsc_fm_zs` | 4.4 | 271 | 2.4 | 4.5 | 0.03 | 1 |  |
| `wave10.wb_it_cel_sets` | 4.2 | 270 | 2.3 | 4.1 | 0.04 | 1 |  |
| `wave10.wb_ny_adj_dpem_cd` | 3.7 | 268 | 2.2 | 3.5 | 0.05 | 1 |  |
| `wave10.wb_sh_h2o_smdw_zs` | 3.9 | 268 | 2.3 | 3.8 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_all_mt_ce_ar5` | 4.1 | 267 | 2.3 | 4.6 | 0.07 | 1 |  |
| `wave9.eu_eea_aq_stats` | 42.2 | 266 | 36.7 | 39.6 | 0.39 | 1 |  |
| `wave10.wb_en_ghg_co2_pi_mt_ce_ar5` | 4.0 | 266 | 2.2 | 3.8 | 0.07 | 1 |  |
| `wave10.wb_sh_h2o_smdw_ur_zs` | 54.5 | 266 | 1.8 | 3.0 | 0.03 | 1 |  |
| `wave10.wb_is_rrs_pasg_km` | 3.4 | 265 | 1.8 | 3.2 | 0.02 | 1 |  |
| `wave9.eu_eshm20` | 64.9 | 264 | 12.3 | 61.3 | 1.21 | 1 |  |
| `wave9.us_usgs_nshm` | 71.9 | 264 | 32.1 | 219 | 9.82 | 5 |  |
| `wave10.wb_en_ghg_n2o_zg_ar5` | 3.7 | 264 | 2.2 | 3.7 | 0.07 | 1 |  |
| `wave10.wb_it_net_user_fe_zs` | 4.3 | 261 | 2.5 | 4.3 | 0.02 | 1 |  |
| `wave10.wb_tm_val_mmtl_zs_un` | 3.4 | 260 | 1.9 | 3.5 | 0.06 | 1 |  |
| `wave10.wb_it_net_secr_p6` | 3.1 | 259 | 1.8 | 3.0 | 0.04 | 1 |  |
| `wave10.eu_env_ac_sd` | 14.3 | 256 | 3.9 | 13.6 | 0.15 | 1 |  |
| `wave10.eu_nrg_cb_h` | 5.9 | 255 | 3.9 | 5.5 | 0.06 | 1 |  |
| `wave9.cz_csu_sldb_heating_energy` | 9.6 | 254 | 1.6 | 9.3 | 0.44 | 1 |  |
| `wave10.wb_en_ghg_co2_ic_mt_ce_ar5` | 3.2 | 254 | 1.8 | 3.2 | 0.07 | 1 |  |
| `wave9.eu_degree_days` | 3.7 | 250 | 2.4 | 3.4 | 0.21 | 1 |  |
| `wave10.gb_desnz_ghg_la` | 212 | 250 | 2.1 | 15.2 | 2.97 | 3 |  |
| `wave9.eu_land_prices` | 3.0 | 249 | 2.2 | 2.9 | 0.04 | 1 |  |
| `wave10.eu_nrg_ind_esc` | 6.7 | 249 | 3.8 | 6.2 | 0.15 | 1 |  |
| `wave9.pt_ine_heating_freguesia` | 3.9 | 240 | 1.4 | 3.9 | 0.17 | 1 |  |
| `wave10.eu_nrg_d_indq_n` | 154 | 236 | 13.2 | 154 | 0.78 | 1 |  |
| `wave10.wb_iq_cpa_pubs_xq` | 3.1 | 236 | 1.8 | 3.1 | 0.01 | 1 |  |
| `wave10.eu_nrg_ti_eh` | 23.7 | 236 | 4.7 | 23.4 | 0.03 | 1 |  |
| `wave10.wb_en_ghg_ch4_fe_mt_ce_ar5` | 3.6 | 234 | 2.0 | 3.5 | 0.06 | 1 |  |
| `wave10.eu_cei_srm020` | 11.8 | 232 | 3.8 | 8.2 | 0.11 | 1 |  |
| `wave10.eu_env_ac_mfadpo` | 7.1 | 231 | 3.6 | 6.7 | 0.16 | 1 |  |
| `wave9.eu_heat_pumps` | 4.6 | 230 | 3.1 | 4.1 | 0.03 | 1 |  |
| `wave10.eu_env_epea_cint` | 6.8 | 229 | 3.8 | 6.4 | 0.08 | 1 |  |
| `wave10.wb_en_ghg_n2o_ag_mt_ce_ar5` | 3.1 | 229 | 1.8 | 3.2 | 0.06 | 1 |  |
| `shapes.admin1` | 144 | 226 | 119 | 157 | 0.00 | 0 |  |
| `wave10.wb_ag_lnd_frst_k2` | 3.0 | 225 | 1.8 | 2.8 | 0.03 | 1 |  |
| `wave10.eu_env_air_emis_ind` | 3.3 | 225 | 3.0 | 3.2 | 0.02 | 1 |  |
| `wave10.wb_ny_adj_dco2_gn_zs` | 3.3 | 224 | 1.8 | 3.0 | 0.05 | 1 |  |
| `wave10.eu_env_ac_pefa04` | 53.4 | 223 | 8.3 | 51.0 | 0.52 | 1 |  |
| `wave10.wb_eg_elc_accs_ru_zs` | 3.3 | 220 | 1.8 | 3.0 | 0.03 | 1 |  |
| `wave10.eu_cei_gsr010` | 5.4 | 220 | 3.0 | 5.0 | 0.04 | 1 |  |
| `wave10.eu_nrg_pc_202_c` | 13.1 | 220 | 4.9 | 12.3 | 0.20 | 1 |  |
| `wave10.wb_en_pop_slum_ur_zs` | 3.2 | 220 | 1.8 | 3.1 | 0.02 | 1 |  |
| `wave10.wb_er_h2o_fwin_zs` | 3.1 | 219 | 1.8 | 3.0 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_all_lu_mt_ce_ar5` | 3.2 | 219 | 1.8 | 2.8 | 0.05 | 1 |  |
| `wave10.wb_ny_adj_svng_gn_zs` | 3.3 | 218 | 1.8 | 3.1 | 0.04 | 1 |  |
| `wave10.wb_en_pop_el5m_ru_zs` | 3.7 | 218 | 1.9 | 3.3 | 0.02 | 1 |  |
| `wave10.eu_env_epea_psp` | 22.7 | 218 | 3.3 | 21.1 | 0.05 | 1 |  |
| `wave10.wb_en_ghg_co2_pc_ce_ar5` | 3.2 | 218 | 1.9 | 3.1 | 0.07 | 1 |  |
| `wave10.wb_tx_val_mmtl_zs_un` | 3.2 | 217 | 1.8 | 3.0 | 0.06 | 1 |  |
| `wave10.wb_er_ptd_totl_zs` | 3.3 | 217 | 1.8 | 3.1 | 0.02 | 1 |  |
| `wave10.wb_sh_h2o_basw_ur_zs` | 3.7 | 216 | 1.9 | 3.6 | 0.04 | 1 |  |
| `wave10.wb_sp_urb_grow` | 3.0 | 215 | 1.8 | 2.8 | 0.07 | 1 |  |
| `wave9.gb_ons_income_msoa` | 2.7 | 215 | 1.3 | 2.7 | 0.10 | 1 |  |
| `wave10.wb_en_ghg_ch4_mt_ce_ar5` | 3.1 | 214 | 1.9 | 3.3 | 0.07 | 1 |  |
| `wave10.wb_is_shp_good_tu` | 3.1 | 214 | 1.8 | 3.0 | 0.02 | 1 |  |
| `power_plants_eu.jrc_units` | 20.8 | 213 | 11.7 | 41.8 | 0.25 | 1 |  |
| `wave10.wb_ag_lnd_totl_ru_k2` | 3.3 | 213 | 1.9 | 3.1 | 0.02 | 1 |  |
| `wave10.wb_eg_imp_cons_zs` | 3.1 | 212 | 1.8 | 2.9 | 0.05 | 1 |  |
| `wave10.wb_ie_ppn_engy_cd` | 3.1 | 212 | 1.8 | 3.0 | 0.02 | 1 |  |
| `wave10.eu_env_esst_gg` | 72.5 | 212 | 4.8 | 68.6 | 0.17 | 1 |  |
| `wave10.eu_nrg_chp_cpfe` | 18.2 | 211 | 4.6 | 16.1 | 0.31 | 1 |  |
| `wave10.eu_road_eqr_lormot` | 3.1 | 211 | 2.2 | 3.0 | 0.02 | 1 |  |
| `wave10.wb_sh_sta_pois_p5_ma` | 3.0 | 211 | 1.8 | 2.9 | 0.03 | 1 |  |
| `wave10.eu_nrg_ti_h2` | 4.4 | 210 | 3.0 | 4.2 | 0.01 | 1 |  |
| `main.grid_capacity` | 5.7 | 210 | 5.3 | 6.7 | 0.07 | 6 |  |
| `wave10.wb_en_atm_pm25_mc_t1_zs` | 3.0 | 210 | 1.8 | 2.9 | 0.02 | 1 |  |
| `wave10.wb_sh_sta_hygn_ur_zs` | 3.0 | 210 | 1.8 | 2.9 | 0.02 | 1 |  |
| `wave10.eu_nrg_stk_oil` | 7.6 | 209 | 3.4 | 7.0 | 0.10 | 1 |  |
| `wave10.wb_eg_elc_hyro_zs` | 3.5 | 209 | 1.9 | 3.3 | 0.06 | 1 |  |
| `wave10.wb_ny_adj_dngy_gn_zs` | 3.2 | 209 | 1.8 | 3.4 | 0.04 | 1 |  |
| `wave10.eu_env_epea_neep` | 4.2 | 209 | 3.6 | 3.7 | 0.03 | 1 |  |
| `wave10.eu_nrg_cb_e` | 6.5 | 209 | 3.4 | 5.9 | 0.12 | 1 |  |
| `wave10.eu_env_ac_rme` | 6.4 | 208 | 3.7 | 5.8 | 0.15 | 1 |  |
| `wave10.wb_sh_sta_odfc_zs` | 3.3 | 208 | 1.8 | 3.6 | 0.04 | 1 |  |
| `wave10.wb_ag_yld_crel_kg` | 3.3 | 206 | 1.8 | 3.1 | 0.04 | 1 |  |
| `wave10.wb_ny_adj_aedu_cd` | 3.4 | 206 | 1.9 | 3.4 | 0.05 | 1 |  |
| `wave10.eu_nrg_ind_re` | 4.2 | 205 | 3.2 | 3.8 | 0.11 | 1 |  |
| `wave10.eu_nrg_inf_epc` | 10.0 | 205 | 3.8 | 9.2 | 0.11 | 1 |  |
| `wave10.gb_census_travel_distance` | 2.9 | 204 | 1.9 | 2.9 | 0.03 | 1 |  |
| `wave10.eu_nrg_ind_cotd` | 3.4 | 202 | 3.3 | 3.4 | 0.04 | 1 |  |
| `wave10.eu_nrg_ind_ebmg` | 5.2 | 201 | 3.2 | 4.6 | 0.00 | 1 |  |
| `wave10.gb_census_heating` | 3.2 | 201 | 2.0 | 3.1 | 0.03 | 1 |  |
| `wave10.wb_en_ghg_n2o_mt_ce_ar5` | 3.3 | 200 | 1.8 | 3.0 | 0.07 | 1 |  |
| `wave10.wb_eg_use_elec_kh_pc` | 3.4 | 200 | 1.9 | 3.3 | 0.05 | 1 |  |
| `wave10.wb_en_clc_drsk_xq` | 3.4 | 199 | 1.9 | 3.5 | 0.01 | 1 |  |
| `wave10.wb_eg_fec_rnew_zs` | 3.8 | 199 | 1.9 | 3.5 | 0.03 | 1 |  |
| `wave10.wb_ny_adj_nnat_cd` | 3.6 | 198 | 1.9 | 3.3 | 0.04 | 1 |  |
| `wave10.wb_ny_gdp_minr_rt_zs` | 3.5 | 197 | 1.9 | 3.4 | 0.05 | 1 |  |
| `wave10.wb_eg_cft_accs_ur_zs` | 3.6 | 195 | 2.2 | 3.4 | 0.02 | 1 |  |
| `wave10.wb_er_h2o_intr_pc` | 3.3 | 195 | 1.8 | 3.3 | 0.06 | 1 |  |
| `wave10.eu_env_watabs_rb` | 3.8 | 195 | 1.5 | 3.6 | 0.10 | 1 |  |
| `wave10.eu_nrg_ind_urhcd` | 4.8 | 195 | 3.9 | 4.5 | 0.05 | 1 |  |
| `wave10.wb_ag_lnd_el5m_ur_k2` | 3.2 | 195 | 1.8 | 3.3 | 0.02 | 1 |  |
| `wave10.wb_si_pov_dday` | 3.4 | 194 | 1.9 | 3.3 | 0.02 | 1 |  |
| `wave10.wb_er_gdp_fwtl_m3_kd` | 3.1 | 194 | 1.8 | 3.3 | 0.06 | 1 |  |
| `wave10.eu_nrg_te_gas` | 48.4 | 193 | 5.3 | 48.0 | 0.03 | 1 |  |
| `wave10.wb_ip_ids_rsct` | 3.3 | 193 | 1.9 | 3.2 | 0.02 | 1 |  |
| `zoning.document_pages` | 7.4 | 193 | 7.3 | 13.5 | 0.00 | 1 |  |
| `wave10.wb_ny_adj_dmin_cd` | 3.6 | 192 | 1.9 | 3.5 | 0.04 | 1 |  |
| `wave10.wb_en_ghg_co2_wa_mt_ce_ar5` | 3.1 | 191 | 1.9 | 3.1 | 0.03 | 1 |  |
| `wave10.wb_sh_sta_bass_ur_zs` | 3.3 | 191 | 1.9 | 3.3 | 0.04 | 1 |  |
| `wave9.us_iso_as_prices` | 4.0 | 189 | 2.9 | 197 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_ag_mt_ce_ar5` | 3.5 | 186 | 1.9 | 3.3 | 0.04 | 1 |  |
| `rollups.overture_power__sites_r7` | 2.5 | 185 | 2.4 | 173 | 0.00 | 0 |  |
| `wave10.eu_nrg_ti_sff` | 7.7 | 178 | 6.8 | 111 | 0.00 | 0 |  |
| `rollups.overture_power__lines_r7` | 2.9 | 174 | 2.6 | 151 | 0.00 | 0 |  |
| `rollups.overture_power__sites_r6` | 2.7 | 152 | 2.2 | 126 | 0.00 | 0 |  |
| `rollups.overture_transport__segments_r6` | 10.2 | 146 | 3.5 | 124 | 0.00 | 0 |  |
| `wave9.gb_bus_heat_pumps_la` | 144 | 144 | 1.1 | 1.1 | 0.00 | 0 |  |
| `wave9.us_pjm_rpm` | 3.1 | 131 | 1.2 | 2.4 | 0.00 | 0 |  |
| `euets.eea_link` | 16.7 | 110 | 16.9 | 84.8 | 0.00 | 0 |  |
| `app.us_plants` | 16.8 | 105 | 2.5 | 102 | 0.00 | 0 |  |
| `wave10.eu_nrg_ti_bio` | 5.0 | 102 | 4.7 | 45.9 | 0.00 | 0 |  |
| `wave10.eu_env_ac_mfa` | 16.4 | 99.4 | 15.5 | 95.4 | 0.02 | 1 |  |
| `rollups.overture_power__sites_r5` | 3.6 | 98.5 | 3.5 | 96.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_ti_gasm` | 6.1 | 97.4 | 7.2 | 168 | 1.04 | 1 |  |
| `entsoe.imbalance_price` | 48.6 | 94.3 | 59.7 | 105 | 0.00 | 0 |  |
| `history.connect_eu__bg` | 2.7 | 90.8 | 2.4 | 11.5 | 0.00 | 0 |  |
| `eia860m.generators` | 15.6 | 89.9 | 12.4 | 91.5 | 0.06 | 1 |  |
| `hydrogen.projects` | 12.2 | 89.7 | 11.2 | 22.6 | 0.00 | 0 |  |
| `wave9.eu_emodnet_desalination` | 44.8 | 84.7 | 36.7 | 87.8 | 0.00 | 0 |  |
| `wave10.eu_env_esst_ggcp` | 5.6 | 83.5 | 5.2 | 79.5 | 0.26 | 1 |  |
| `wave9.gb_ne_alc` | 19.6 | 82.2 | 6.2 | 85.7 | 0.00 | 0 |  |
| `wave9.us_ira_energy_communities` | 66.7 | 80.5 | 53.9 | 64.2 | 0.00 | 0 |  |
| `wave9.world_ourairports_runways` | 7.6 | 80.3 | 6.7 | 79.1 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_pehcf` | 8.4 | 80.0 | 7.9 | 86.3 | 0.00 | 0 |  |
| `entsog.flows` | 19.6 | 77.8 | 19.5 | 62.4 | 0.00 | 0 |  |
| `mastr.units_hydro` | 14.8 | 76.2 | 18.1 | 67.8 | 1.21 | 1 |  |
| `wave10.eu_road_eqr_busveh` | 2.6 | 74.3 | 1.6 | 2.3 | 0.00 | 0 |  |
| `wave9.eu_heat_production` | 7.6 | 74.1 | 7.9 | 71.9 | 0.00 | 0 |  |
| `app.world_plants` | 21.1 | 72.7 | 4.6 | 70.4 | 0.00 | 0 |  |
| `wave10.eu_env_ac_aigg_q` | 2.5 | 71.7 | 2.5 | 15.8 | 0.00 | 0 |  |
| `rollups.mastr__units_solar_r6` | 3.1 | 69.1 | 2.8 | 46.5 | 0.00 | 0 |  |
| `rollups.overture_transport__segments_r5` | 3.5 | 63.9 | 3.0 | 59.3 | 0.00 | 0 |  |
| `wave10.eu_env_air_emis` | 10.2 | 63.0 | 10.1 | 63.1 | 0.00 | 0 |  |
| `wave9.us_boem_active_leases` | 11.9 | 61.9 | 8.9 | 58.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_ti_gas` | 5.8 | 61.7 | 5.7 | 60.9 | 0.00 | 0 |  |
| `rollups.wave9__de_zensus_heating_r7` | 16.0 | 61.6 | 14.8 | 53.6 | 0.00 | 0 |  |
| `rollups.mastr__units_solar_r7` | 4.0 | 59.8 | 2.2 | 40.5 | 0.00 | 0 |  |
| `wave10.eu_env_ac_epiap1` | 6.2 | 57.1 | 6.1 | 56.8 | 0.00 | 0 |  |
| `wave10.eu_ten00003` | 2.4 | 57.0 | 1.6 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_sffm` | 7.9 | 54.8 | 7.8 | 55.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_sff` | 6.3 | 53.9 | 6.0 | 55.8 | 0.00 | 0 |  |
| `app.eu_plants` | 15.6 | 52.4 | 2.3 | 33.1 | 0.00 | 0 |  |
| `wave9.eu_emodnet_pipelines` | 8.4 | 50.2 | 7.6 | 44.1 | 0.00 | 0 |  |
| `wave9.eu_egdi_minerals` | 36.4 | 49.8 | 33.1 | 42.4 | 0.00 | 0 |  |
| `wave9.us_fhwa_afc` | 32.2 | 49.4 | 19.7 | 44.8 | 0.00 | 0 |  |
| `wave10.eu_nrg_te_bio` | 4.8 | 48.1 | 4.3 | 45.5 | 0.00 | 0 |  |
| `rollups.mastr__units_storage_r7` | 3.5 | 47.9 | 2.6 | 23.0 | 0.00 | 0 |  |
| `app.data_centres` | 17.2 | 45.4 | 11.4 | 17.8 | 0.00 | 0 |  |
| `shapes.admin1_simplified` | 8.4 | 43.6 | 6.8 | 38.3 | 0.00 | 0 |  |
| `wave10.eu_env_ac_taxind2` | 6.8 | 43.1 | 5.9 | 43.1 | 0.00 | 0 |  |
| `connect.harmonised` | 8.6 | 40.8 | 8.4 | 52.3 | 0.00 | 0 |  |
| `ev_eu.cz` | 2.5 | 40.8 | 2.1 | 37.5 | 0.00 | 0 |  |
| `registers.gb` | 7.2 | 37.6 | 6.6 | 34.0 | 0.00 | 0 |  |
| `wave10.eu_env_esst_cepggcp` | 4.0 | 36.6 | 3.8 | 34.3 | 0.00 | 0 |  |
| `wave9.us_drought_monitor` | 10.7 | 35.3 | 8.8 | 31.4 | 0.00 | 0 |  |
| `osm.eu_buses` | 4.1 | 34.0 | 3.3 | 35.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_te_eh` | 5.6 | 33.8 | 5.2 | 33.5 | 0.00 | 0 |  |
| `ev_eu.at` | 5.0 | 32.8 | 4.6 | 28.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_pehnf` | 6.2 | 32.0 | 6.0 | 32.1 | 0.00 | 0 |  |
| `ev_eu.gb` | 5.6 | 31.0 | 5.0 | 30.1 | 0.00 | 0 |  |
| `rollups.mastr__units_storage_r6` | 2.7 | 29.8 | 2.6 | 23.9 | 0.00 | 0 |  |
| `wave9.eu_salt_caverns` | 10.3 | 29.8 | 7.3 | 16.2 | 0.00 | 0 |  |
| `entsoe.transfer_capacity` | 10.0 | 29.6 | 7.3 | 30.3 | 0.00 | 0 |  |
| `euets.installations` | 13.3 | 29.3 | 12.9 | 25.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_gasm` | 6.1 | 28.9 | 6.0 | 28.9 | 0.00 | 0 |  |
| `gem.coal_mines_closed_mines` | 19.3 | 28.4 | 18.8 | 21.5 | 0.00 | 0 |  |
| `gem.coal_mines_non_closed_mines` | 27.6 | 28.3 | 24.1 | 24.4 | 0.00 | 0 |  |
| `wave9.fi_paavo` | 8.5 | 27.4 | 5.9 | 22.1 | 0.00 | 0 |  |
| `wave9.us_usgs_water_use` | 5.1 | 26.3 | 2.5 | 10.7 | 0.00 | 0 |  |
| `wave9.us_eia_biodiesel` | 12.3 | 26.0 | 2.9 | 12.9 | 0.00 | 0 |  |
| `mastr.units_other` | 5.1 | 25.6 | 4.4 | 88.8 | 0.00 | 0 |  |
| `registers.ie` | 13.7 | 25.4 | 12.9 | 19.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_gas` | 3.9 | 25.2 | 4.0 | 23.7 | 0.00 | 0 |  |
| `shapes.bidding_zones` | 8.5 | 25.1 | 7.2 | 22.1 | 0.00 | 0 |  |
| `wave10.eu_env_ac_aibrid_rd` | 5.4 | 25.0 | 4.6 | 23.0 | 0.02 | 1 |  |
| `co2stop.hydrocarbon_traps1` | 24.2 | 24.9 | 23.4 | 24.1 | 0.00 | 0 |  |
| `mastr.units_nuclear` | 4.4 | 24.7 | 4.0 | 18.1 | 0.00 | 0 |  |
| `history.registers__se` | 5.7 | 24.6 | 4.5 | 22.4 | 0.00 | 0 |  |
| `wave9.us_epa_lmop_landfills` | 4.1 | 24.4 | 3.3 | 25.1 | 0.00 | 0 |  |
| `wave9.eu_jrc_coastal_flood` | 21.2 | 24.1 | 19.1 | 20.0 | 0.00 | 0 |  |
| `wave9.us_cpc_degree_days` | 4.4 | 23.9 | 3.6 | 18.8 | 0.00 | 0 |  |
| `co2stop.hydrocarbon_storage_units` | 17.9 | 23.8 | 16.5 | 17.5 | 0.00 | 0 |  |
| `rollups.wave9__de_zensus_heating_r6` | 12.0 | 23.8 | 11.0 | 22.5 | 0.00 | 0 |  |
| `tyndp.projects` | 2.5 | 23.8 | 2.2 | 23.3 | 0.00 | 0 |  |
| `entsoe.congestion_countertrading` | 4.4 | 23.1 | 4.2 | 7.1 | 0.00 | 0 |  |
| `history.registers__gb` | 5.8 | 23.1 | 5.3 | 12.0 | 0.00 | 0 |  |
| `gem.methane_emitters_oil_and_gas_extraction_areas` | 20.7 | 22.3 | 20.1 | 21.1 | 0.00 | 0 |  |
| `wave9.gb_ssen_opendata` | 4.4 | 21.7 | 3.6 | 20.2 | 0.00 | 0 |  |
| `registers.se` | 3.9 | 21.5 | 3.3 | 17.2 | 0.00 | 0 |  |
| `history.connect_eu__gb_dso` | 4.3 | 21.3 | 3.6 | 18.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_d_serq_n` | 5.4 | 21.3 | 5.1 | 20.0 | 0.00 | 0 |  |
| `registers.dk` | 3.8 | 21.1 | 2.4 | 9.8 | 0.00 | 0 |  |
| `connect_eu.gb_dso` | 4.2 | 20.8 | 3.7 | 16.9 | 0.00 | 0 |  |
| `entsoe.congestion_redispatch_cross_border` | 3.6 | 20.8 | 3.5 | 5.4 | 0.00 | 0 |  |
| `wave9.us_nexrad` | 12.1 | 20.7 | 12.9 | 21.1 | 0.00 | 0 |  |
| `capareseau.substations` | 3.7 | 20.4 | 3.2 | 17.9 | 0.00 | 0 |  |
| `rollups.mastr__units_solar_r5` | 2.4 | 19.9 | 2.1 | 19.5 | 0.00 | 0 |  |
| `entsoe.capacity` | 2.2 | 19.6 | 1.6 | 1.9 | 0.00 | 0 |  |
| `app.eu_prices` | 2.1 | 19.4 | 1.3 | 2.1 | 0.00 | 0 |  |
| `connect_eu.bg` | 3.5 | 19.2 | 2.3 | 11.5 | 0.00 | 0 |  |
| `connect_eu.dk` | 12.0 | 19.0 | 11.0 | 11.2 | 0.00 | 0 |  |
| `wave9.dk_district_heating` | 7.7 | 18.7 | 4.6 | 7.6 | 0.00 | 0 |  |
| `wave10.eu_env_epea_pgg` | 2.3 | 18.5 | 2.3 | 22.5 | 0.00 | 0 |  |
| `entsoe.units` | 2.4 | 17.9 | 2.1 | 10.8 | 0.00 | 0 |  |
| `iso_queues.requests` | 5.2 | 17.9 | 4.8 | 16.0 | 0.00 | 0 |  |
| `osm.eu_links` | 7.9 | 17.9 | 3.0 | 7.5 | 0.00 | 0 |  |
| `history.connect_eu__dk` | 11.9 | 17.4 | 11.1 | 11.2 | 0.00 | 0 |  |
| `app.eu_substations` | 15.3 | 17.3 | 8.2 | 18.4 | 0.00 | 0 |  |
| `wave9.us_eia_ethanol` | 2.6 | 17.3 | 2.3 | 11.5 | 0.00 | 0 |  |
| `ev_eu.ie` | 2.4 | 17.2 | 2.1 | 14.5 | 0.00 | 0 |  |
| `ev_eu.it` | 5.2 | 16.6 | 5.2 | 15.7 | 0.00 | 0 |  |
| `wave9.us_eia_gas_storage` | 2.6 | 16.6 | 2.1 | 9.0 | 0.00 | 0 |  |
| `wave10.eu_env_epea_pap` | 6.2 | 16.5 | 6.1 | 15.3 | 0.00 | 0 |  |
| `wave9.us_eia_refineries` | 5.4 | 16.5 | 3.5 | 15.5 | 0.00 | 0 |  |
| `connect_eu.lu` | 2.9 | 15.9 | 2.5 | 15.2 | 0.00 | 0 |  |
| `wave9.eu_emodnet_hydrocarbon_licences` | 8.5 | 15.8 | 7.6 | 12.6 | 0.00 | 0 |  |
| `wave10.gb_desnz_tfec_la` | 2.5 | 15.5 | 2.4 | 13.9 | 0.00 | 0 |  |
| `wave9.eu_emodnet_ocean_energy` | 3.1 | 15.5 | 2.4 | 13.0 | 0.00 | 0 |  |
| `rollups.mastr__units_storage_r5` | 10.1 | 15.4 | 3.5 | 13.7 | 0.00 | 0 |  |
| `uk_pi.releases` | 12.3 | 15.1 | 10.8 | 11.6 | 0.00 | 0 |  |
| `history.capareseau__substations` | 3.2 | 14.6 | 2.5 | 13.3 | 0.00 | 0 |  |
| `osm.cables` | 3.7 | 14.5 | 2.7 | 8.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_203_c` | 3.8 | 14.5 | 3.7 | 12.2 | 0.00 | 0 |  |
| `ev_eu.bg` | 1.8 | 14.4 | 1.6 | 8.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_10` | 2.5 | 14.3 | 1.9 | 2.3 | 0.00 | 0 |  |
| `lbnl_queue.requests` | 9.2 | 14.2 | 9.2 | 10.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_d_hhq` | 5.4 | 14.2 | 5.2 | 13.7 | 0.00 | 0 |  |
| `ev_eu.ee` | 2.5 | 13.8 | 2.0 | 12.1 | 0.00 | 0 |  |
| `wave9.eu_emodnet_aggregates` | 4.7 | 13.8 | 4.5 | 9.8 | 0.00 | 0 |  |
| `caiso.curtailment` | 5.0 | 13.5 | 4.9 | 11.5 | 0.00 | 0 |  |
| `history.registers__fr` | 4.5 | 13.5 | 4.3 | 11.3 | 0.00 | 0 |  |
| `entsoe.transmission_outages` | 1.8 | 13.4 | 1.7 | 12.7 | 0.00 | 0 |  |
| `ev_eu.pt` | 2.6 | 13.4 | 2.2 | 11.0 | 0.00 | 0 |  |
| `ev_eu.si` | 2.0 | 13.3 | 1.6 | 19.0 | 0.00 | 0 |  |
| `wave9.us_openei_urdb` | 13.3 | 13.3 | 11.8 | 11.8 | 0.00 | 0 |  |
| `history.connect_eu__lu` | 3.0 | 13.2 | 2.7 | 13.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_hptctc` | 2.8 | 13.2 | 2.8 | 11.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_bal_cv` | 6.9 | 13.1 | 6.4 | 12.1 | 0.00 | 0 |  |
| `wave9.us_eia_lng` | 3.6 | 13.1 | 2.8 | 12.8 | 0.00 | 0 |  |
| `wave9.us_epa_lmop` | 3.5 | 13.1 | 2.9 | 12.2 | 0.00 | 0 |  |
| `wave9.us_eia_gas_processing` | 3.4 | 13.0 | 2.4 | 10.3 | 0.00 | 0 |  |
| `wave9.us_eia_crude_pipelines` | 9.1 | 12.8 | 7.9 | 8.8 | 0.00 | 0 |  |
| `ev_eu.lu` | 2.1 | 12.7 | 1.6 | 11.0 | 0.00 | 0 |  |
| `wave9.us_usgs_geoelectric` | 7.9 | 12.6 | 7.9 | 11.3 | 0.00 | 0 |  |
| `ev_eu.gr` | 2.5 | 12.5 | 2.1 | 11.1 | 0.00 | 0 |  |
| `wave9.gb_npg_heatmap_substations` | 9.6 | 12.4 | 7.3 | 10.7 | 0.00 | 0 |  |
| `wave9.fr_emodnet_telecom_sigcables` | 4.5 | 12.3 | 3.0 | 8.4 | 0.00 | 0 |  |
| `wave9.gb_pins_dco` | 8.8 | 12.3 | 7.7 | 9.0 | 0.00 | 0 |  |
| `history.registers__dk` | 2.9 | 12.1 | 2.5 | 11.8 | 0.00 | 0 |  |
| `ev_eu.mt` | 2.2 | 12.0 | 1.8 | 14.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_d_traq` | 2.8 | 11.8 | 2.8 | 9.7 | 0.00 | 0 |  |
| `entsoe.congestion_redispatch_internal` | 8.3 | 11.6 | 6.3 | 12.4 | 0.00 | 0 |  |
| `wave9.eu_emodnet_nuclear` | 7.4 | 11.4 | 5.3 | 7.2 | 0.00 | 0 |  |
| `ei_review.series` | 2.4 | 11.2 | 2.4 | 8.3 | 0.00 | 0 |  |
| `wave9.us_eia_product_pipelines` | 8.4 | 11.0 | 7.2 | 9.9 | 0.00 | 0 |  |
| `wave9.us_eia_hgl_pipelines` | 8.9 | 10.8 | 7.9 | 9.1 | 0.00 | 0 |  |
| `wave9.us_blm_solar_dla` | 3.7 | 10.7 | 2.9 | 8.0 | 0.00 | 0 |  |
| `wave10.eu_env_ac_cepsgc1` | 3.0 | 10.4 | 2.9 | 9.0 | 0.00 | 0 |  |
| `wave9.eu_emodnet_wind_farms` | 3.8 | 10.4 | 3.4 | 8.5 | 0.00 | 0 |  |
| `wave9.fr_emodnet_telecom_shom` | 3.2 | 10.3 | 2.5 | 7.5 | 0.00 | 0 |  |
| `wave9.eu_network_costs` | 4.8 | 10.1 | 4.9 | 9.7 | 0.00 | 0 |  |
| `history.registers__ie` | 9.9 | 9.9 | 8.9 | 16.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ahbtc` | 4.0 | 9.9 | 3.9 | 10.2 | 0.00 | 0 |  |
| `wave10.eu_env_ac_pepssp1` | 2.6 | 9.8 | 2.5 | 7.8 | 0.00 | 0 |  |
| `wave10.gb_desnz_elec_la` | 2.7 | 9.7 | 2.3 | 8.4 | 0.00 | 0 |  |
| `wave9.gb_neso_etys` | 2.4 | 9.2 | 2.0 | 9.1 | 0.00 | 0 |  |
| `wave9.de_emodnet_telecom_bsh` | 5.3 | 9.1 | 3.4 | 7.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_urtd` | 4.2 | 8.4 | 3.8 | 8.1 | 0.00 | 0 |  |
| `entsoe.outages` | 6.1 | 8.3 | 6.4 | 7.8 | 0.00 | 0 |  |
| `wave10.eu_nrg_stk_gasm` | 4.5 | 8.2 | 4.2 | 7.7 | 0.00 | 0 |  |
| `wave9.cz_csu_sldb_heating_mode` | 1.7 | 8.0 | 1.7 | 7.5 | 0.00 | 0 |  |
| `wave9.es_emodnet_telecom_cica` | 3.1 | 8.0 | 2.5 | 6.9 | 0.00 | 0 |  |
| `wave9.mt_emodnet_telecom` | 2.1 | 7.8 | 1.9 | 6.0 | 0.00 | 0 |  |
| `wave10.eu_env_esst_ceprw` | 6.3 | 7.6 | 4.2 | 6.3 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_70` | 2.3 | 7.6 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_chdd_a` | 2.4 | 7.5 | 1.6 | 2.4 | 0.00 | 0 |  |
| `registers.fr` | 2.8 | 7.4 | 2.7 | 7.3 | 0.00 | 0 |  |
| `wave10.eu_env_esst_rw` | 2.4 | 7.4 | 2.3 | 6.9 | 0.00 | 0 |  |
| `neso_tec.projects` | 6.5 | 7.3 | 6.2 | 7.0 | 0.00 | 0 |  |
| `outlines.names` | 2.9 | 7.3 | 2.7 | 6.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ibmg` | 4.0 | 7.1 | 4.0 | 6.6 | 0.00 | 0 |  |
| `small_area_energy.heating` | 3.5 | 6.9 | 3.3 | 6.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_chddr2_m` | 4.8 | 6.8 | 4.4 | 6.4 | 0.00 | 0 |  |
| `wave10.eu_cei_gsr030` | 1.2 | 6.7 | 1.1 | 1.5 | 0.00 | 0 |  |
| `irena.generation` | 4.7 | 6.5 | 4.5 | 6.7 | 0.00 | 0 |  |
| `wave10.gb_desnz_gas_la` | 1.7 | 6.5 | 1.7 | 5.8 | 0.00 | 0 |  |
| `mastr.grid_connection_points` | 5.8 | 6.1 | 5.7 | 5.9 | 0.00 | 0 |  |
| `wave9.gr_elstat_heating_settlement` | 4.5 | 6.1 | 4.0 | 5.9 | 0.00 | 0 |  |
| `wave10.eu_rail_if_line_na` | 2.8 | 6.0 | 2.4 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_env_watres_rb` | 1.6 | 5.8 | 1.5 | 3.4 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_52` | 2.8 | 5.5 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ured` | 4.0 | 5.4 | 3.9 | 5.1 | 0.00 | 0 |  |
| `wave9.eu_air_passengers` | 4.8 | 5.4 | 3.0 | 4.1 | 0.00 | 0 |  |
| `wave10.eu_env_ac_cepsgh1` | 4.4 | 5.2 | 4.0 | 4.8 | 0.00 | 0 |  |
| `wave10.eu_env_ac_landfp` | 3.4 | 5.2 | 1.2 | 2.3 | 0.00 | 0 |  |
| `edgar.ghg_by_sector` | 1.6 | 5.1 | 1.6 | 4.0 | 0.00 | 0 |  |
| `history.registers__cz` | 2.6 | 5.0 | 1.9 | 4.5 | 0.00 | 0 |  |
| `irena.capacity` | 3.5 | 5.0 | 3.6 | 4.8 | 0.00 | 0 |  |
| `pse_capacity.full_substations` | 1.6 | 5.0 | 1.5 | 1.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_cosm` | 2.7 | 4.9 | 2.6 | 4.7 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_vans` | 2.8 | 4.9 | 1.7 | 2.5 | 0.00 | 0 |  |
| `wave9.eu_entsoe_balancing` | 2.1 | 4.9 | 1.9 | 4.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_psth2` | 3.2 | 4.8 | 1.8 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_nrg_chdd_m` | 3.5 | 4.7 | 3.4 | 4.3 | 0.00 | 0 |  |
| `wave9.gb_neso_constraint_costs` | 2.1 | 4.7 | 1.4 | 2.6 | 0.00 | 0 |  |
| `wave9.ie_cso_dc_consumption` | 2.6 | 4.7 | 2.4 | 4.1 | 0.00 | 0 |  |
| `cenace.pml` | 2.0 | 4.6 | 1.7 | 4.2 | 0.00 | 0 |  |
| `wave10.eu_cei_gsr020` | 3.5 | 4.6 | 1.7 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_eg_elc_rnwx_zs` | 2.7 | 4.6 | 2.6 | 4.2 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_tr_mt_ce_ar5` | 2.6 | 4.5 | 2.4 | 4.2 | 0.00 | 0 |  |
| `wave10.wb_er_fsh_prod_mt` | 2.8 | 4.5 | 2.8 | 4.2 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_bu_mt_ce_ar5` | 2.3 | 4.4 | 2.3 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_en_mam_thrd_no` | 2.6 | 4.4 | 2.5 | 4.7 | 0.00 | 0 |  |
| `aures.auctions` | 2.1 | 4.3 | 1.9 | 3.8 | 0.00 | 0 |  |
| `prepared.answers` | 3.7 | 4.3 | 0.8 | 1.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_epsc` | 4.1 | 4.3 | 4.3 | 4.5 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_ch4_zg_ar5` | 2.8 | 4.3 | 2.5 | 4.7 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_n2o_ip_mt_ce_ar5` | 2.5 | 4.3 | 2.5 | 4.4 | 0.00 | 0 |  |
| `jepx.spot` | 1.6 | 4.2 | 1.6 | 4.0 | 0.00 | 0 |  |
| `mastr_grid.operators` | 1.8 | 4.2 | 1.8 | 4.1 | 0.00 | 0 |  |
| `wave10.eu_env_wat_res` | 3.9 | 4.2 | 4.0 | 4.0 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_h2` | 3.3 | 4.2 | 3.3 | 3.9 | 0.40 | 2 |  |
| `wave10.wb_ag_lnd_el5m_ur_zs` | 2.2 | 4.2 | 2.2 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_en_clc_mdat_zs` | 2.3 | 4.2 | 2.3 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_ch4_ic_mt_ce_ar5` | 2.7 | 4.2 | 2.5 | 4.2 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_lu_mt_ce_ar5` | 2.5 | 4.2 | 2.4 | 4.3 | 0.00 | 0 |  |
| `wave10.wb_en_pop_el5m_ur_zs` | 2.5 | 4.2 | 2.5 | 4.1 | 0.00 | 0 |  |
| `wave10.wb_is_rrs_good_mt_k6` | 2.4 | 4.2 | 2.4 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_sh_h2o_basw_ru_zs` | 2.5 | 4.2 | 2.5 | 3.9 | 0.00 | 0 |  |
| `wave10.eu_cei_pc030` | 2.5 | 4.1 | 1.6 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_cei_pc040` | 2.2 | 4.1 | 1.3 | 1.7 | 0.00 | 0 |  |
| `wave10.gb_desnz_ren_generation_la` | 4.1 | 4.1 | 1.5 | 1.5 | 0.00 | 0 |  |
| `wave10.wb_eg_elc_fosl_zs` | 2.5 | 4.1 | 2.4 | 4.0 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_ch4_bu_mt_ce_ar5` | 2.5 | 4.1 | 2.4 | 4.1 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_n2o_pi_mt_ce_ar5` | 2.5 | 4.1 | 2.4 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_ictr_gn_zs` | 2.6 | 4.1 | 2.4 | 4.2 | 0.00 | 0 |  |
| `wave10.wb_tm_val_ictg_zs_un` | 2.3 | 4.1 | 2.3 | 4.1 | 0.00 | 0 |  |
| `wave9.eu_ev_stock_nuts2` | 2.7 | 4.1 | 2.7 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_ag_lnd_el5m_ru_zs` | 2.4 | 4.0 | 2.2 | 3.6 | 0.00 | 0 |  |
| `wave10.wb_eg_use_crnw_zs` | 2.4 | 4.0 | 2.4 | 4.0 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_zg_ar5` | 2.4 | 4.0 | 2.4 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_er_h2o_fwag_zs` | 2.4 | 4.0 | 2.5 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_er_h2o_intr_k3` | 2.5 | 4.0 | 2.5 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_ie_ppi_engy_cd` | 2.5 | 4.0 | 2.3 | 3.6 | 0.00 | 0 |  |
| `wave10.wb_it_mlt_main_p2` | 2.4 | 4.0 | 2.4 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_aedu_gn_zs` | 2.4 | 4.0 | 2.3 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_bass_ru_zs` | 2.5 | 4.0 | 2.4 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_odfc_ur_zs` | 2.4 | 4.0 | 2.3 | 3.8 | 0.00 | 0 |  |
| `wave9.ie_semo_imbalance` | 4.0 | 4.0 | 1.3 | 1.3 | 0.00 | 0 |  |
| `wave9.si_surs_electricity_municipality` | 2.5 | 4.0 | 2.3 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_eg_cft_accs_ru_zs` | 2.2 | 3.9 | 2.2 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_en_bir_thrd_no` | 2.4 | 3.9 | 2.4 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_ip_ids_nrct` | 2.4 | 3.9 | 2.4 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_is_rrs_totl_km` | 2.5 | 3.9 | 2.3 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_nv_agr_totl_zs` | 2.3 | 3.9 | 2.3 | 3.9 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_dkap_gn_zs` | 2.4 | 3.9 | 2.3 | 4.0 | 0.00 | 0 |  |
| `wave10.wb_ny_gdp_frst_rt_zs` | 2.4 | 3.9 | 2.3 | 4.3 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_bass_zs` | 2.3 | 3.9 | 2.2 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_wash_p5` | 2.4 | 3.9 | 2.4 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_sp_pop_grow` | 2.3 | 3.9 | 2.3 | 3.8 | 0.00 | 0 |  |
| `wave9.fr_odre_balancing_volumes` | 2.4 | 3.9 | 1.5 | 3.2 | 0.00 | 0 |  |
| `mastr.operators` | 3.8 | 3.8 | 3.7 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_eg_cft_accs_zs` | 2.3 | 3.8 | 2.3 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_eg_use_pcap_kg_oe` | 2.3 | 3.8 | 2.2 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_lu_os_mt_ce_ar5` | 2.6 | 3.8 | 2.5 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_dmin_gn_zs` | 2.2 | 3.8 | 2.3 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_pois_p5` | 2.3 | 3.8 | 2.3 | 3.8 | 0.00 | 0 |  |
| `netztransparenz.redispatch` | 1.2 | 3.7 | 1.2 | 3.9 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_lorton` | 2.3 | 3.7 | 1.6 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_ag_lnd_totl_k2` | 2.3 | 3.7 | 2.2 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_eg_elc_loss_zs` | 2.2 | 3.7 | 2.2 | 3.6 | 0.00 | 0 |  |
| `wave10.wb_eg_gdp_puse_ko_pp` | 2.3 | 3.7 | 2.2 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_ie_ppi_tran_cd` | 2.2 | 3.7 | 2.1 | 3.8 | 0.00 | 0 |  |
| `wave10.wb_it_net_bbnd_p2` | 2.3 | 3.7 | 2.2 | 3.7 | 0.00 | 0 |  |
| `wave10.wb_ny_gdp_ngas_rt_zs` | 2.2 | 3.7 | 2.2 | 3.8 | 0.00 | 0 |  |
| `wave10.eu_nrg_cb_bm` | 3.6 | 3.6 | 3.5 | 3.5 | 0.00 | 0 |  |
| `wave10.wb_ag_lnd_totl_ur_k2` | 2.3 | 3.6 | 2.2 | 3.6 | 0.00 | 0 |  |
| `wave10.wb_ip_tmk_nrct` | 2.2 | 3.6 | 2.3 | 3.5 | 0.00 | 0 |  |
| `wave10.wb_tx_val_fuel_zs_un` | 2.3 | 3.6 | 2.2 | 3.5 | 0.00 | 0 |  |
| `wave9.nl_cbs_solar` | 2.1 | 3.6 | 2.8 | 3.0 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_zev` | 3.4 | 3.5 | 3.3 | 3.5 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_nnat_gn_zs` | 2.1 | 3.5 | 2.1 | 3.5 | 0.00 | 0 |  |
| `wave10.wb_sh_h2o_basw_zs` | 2.1 | 3.5 | 2.2 | 3.7 | 0.00 | 0 |  |
| `wave9.dk_energinet_countertrade` | 1.6 | 3.5 | 1.6 | 3.6 | 0.00 | 0 |  |
| `history.netztransparenz__redispatch` | 1.3 | 3.4 | 1.3 | 3.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_stk_h2` | 2.5 | 3.4 | 1.6 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_rail_if_traff` | 2.6 | 3.4 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave10.wb_er_lnd_ptld_zs` | 2.3 | 3.4 | 2.2 | 3.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_fecf` | 2.5 | 3.3 | 2.5 | 3.1 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_mopeds` | 2.8 | 3.3 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave10.wb_sp_pop_totl` | 1.6 | 3.3 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave9.eu_water_abstraction` | 2.5 | 3.3 | 2.6 | 3.2 | 0.00 | 0 |  |
| `mastr.locations` | 3.0 | 3.2 | 3.1 | 3.4 | 0.00 | 0 |  |
| `wave10.eu_env_ac_epigg1` | 2.7 | 3.2 | 2.2 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_h2stpc` | 1.9 | 3.2 | 1.4 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_te_h2` | 2.1 | 3.2 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.gb_desnz_gas_distribution` | 3.2 | 3.2 | 1.0 | 1.0 | 0.00 | 0 |  |
| `wave10.gb_dft_evcd_devices` | 2.1 | 3.2 | 1.3 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_env_ac_mfabi` | 2.2 | 3.1 | 2.3 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_env_ac_mid` | 1.9 | 3.1 | 1.4 | 1.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_hpind` | 2.3 | 3.1 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_rail_if_line_ga` | 2.7 | 3.1 | 2.8 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_spurp` | 2.3 | 3.1 | 1.4 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_unlweig` | 2.6 | 3.1 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_ten00126` | 2.7 | 3.1 | 2.5 | 2.8 | 0.00 | 0 |  |
| `wave9.eu_renewable_capacity` | 2.5 | 3.1 | 2.5 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_env_epea_invgg` | 1.9 | 3.0 | 1.3 | 1.8 | 0.00 | 0 |  |
| `wave10.eu_nrg_chp_f` | 2.6 | 3.0 | 2.6 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_locon` | 2.2 | 3.0 | 2.1 | 2.9 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_lorroa` | 2.6 | 3.0 | 2.5 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_40` | 2.6 | 3.0 | 2.5 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_ten00121` | 2.5 | 3.0 | 2.6 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_ten00127` | 2.5 | 3.0 | 1.9 | 2.1 | 0.00 | 0 |  |
| `wave9.eu_wastewater_connected` | 2.6 | 3.0 | 2.6 | 2.8 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_busmot` | 2.6 | 2.9 | 2.4 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_frmod` | 2.5 | 2.9 | 1.8 | 2.4 | 0.00 | 0 |  |
| `zoning.documents` | 2.4 | 2.9 | 2.3 | 2.6 | 0.00 | 0 |  |
| `ree_nodes.nodes` | 2.4 | 2.8 | 2.4 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_cei_srm010` | 2.6 | 2.8 | 2.3 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_env_wat_cat` | 2.6 | 2.8 | 2.5 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_age_loa` | 1.8 | 2.8 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_loadcap` | 2.0 | 2.8 | 1.4 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_cpl` | 2.7 | 2.8 | 2.7 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_difec` | 2.1 | 2.8 | 2.1 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_stcs` | 1.9 | 2.8 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_semit` | 2.6 | 2.8 | 2.3 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_carmot` | 2.0 | 2.8 | 1.3 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_60` | 1.9 | 2.8 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_61` | 2.0 | 2.8 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_40` | 2.2 | 2.8 | 2.1 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_50` | 2.7 | 2.8 | 1.6 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_ten00106` | 2.0 | 2.8 | 1.9 | 2.7 | 0.00 | 0 |  |
| `wave10.eu_ten00108` | 2.3 | 2.8 | 1.4 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_ten00135` | 2.1 | 2.8 | 2.0 | 2.5 | 0.00 | 0 |  |
| `power_plants_eu.jrc_performance` | 1.4 | 2.7 | 1.2 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_cei_pc020` | 1.9 | 2.7 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_cei_wm020` | 1.8 | 2.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_env_wat_ind` | 2.4 | 2.7 | 1.9 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ioc` | 2.2 | 2.7 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_epct` | 2.6 | 2.7 | 2.6 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_lorrit` | 2.6 | 2.7 | 2.5 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_unlweig` | 2.1 | 2.7 | 2.1 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_semit` | 1.9 | 2.7 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_30` | 2.4 | 2.7 | 1.9 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_ms_frmod` | 2.1 | 2.7 | 2.1 | 2.5 | 0.00 | 0 |  |
| `wave10.gb_census_accommodation` | 1.8 | 2.7 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave9.eu_internet_households` | 2.2 | 2.7 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave9.gb_npg_curtailment_events` | 2.7 | 2.7 | 1.2 | 1.2 | 0.00 | 0 |  |
| `wave10.eu_env_ac_taxener` | 1.7 | 2.6 | 1.4 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_env_epea_invte` | 1.9 | 2.6 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_chp_n` | 2.5 | 2.6 | 2.2 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_stjpjss` | 2.2 | 2.6 | 2.2 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_204_v` | 2.0 | 2.6 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_locop` | 2.4 | 2.6 | 1.7 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_trset` | 2.0 | 2.6 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_rail_if_tracks` | 1.9 | 2.6 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_bussea` | 1.8 | 2.6 | 1.7 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_40` | 2.1 | 2.6 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_10` | 1.8 | 2.6 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_31` | 1.8 | 2.6 | 1.7 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_41` | 2.1 | 2.6 | 1.3 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_ten00122` | 2.4 | 2.6 | 2.2 | 2.4 | 0.00 | 0 |  |
| `wave10.gb_census_bedrooms` | 2.0 | 2.6 | 1.3 | 1.8 | 0.00 | 0 |  |
| `wave9.eu_broadband_coverage` | 2.2 | 2.6 | 1.7 | 2.6 | 0.00 | 0 |  |
| `wave9.eu_nuclear_capacity` | 2.2 | 2.6 | 2.2 | 2.6 | 0.00 | 0 |  |
| `wave9.fr_ademe_dpe` | 1.6 | 2.6 | 1.3 | 2.1 | 0.00 | 0 |  |
| `wave9.ro_transelectrica_zone_capacity` | 1.7 | 2.6 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ffgae` | 1.7 | 2.5 | 1.7 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ren` | 2.0 | 2.5 | 2.0 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_205_v` | 1.9 | 2.5 | 1.4 | 1.7 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_carhab` | 1.8 | 2.5 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_30` | 1.8 | 2.5 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_70` | 2.0 | 2.5 | 1.9 | 2.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_70a` | 1.8 | 2.5 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_ten00136` | 2.4 | 2.5 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_ten00141` | 1.9 | 2.5 | 1.8 | 2.6 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_ms_frmod6` | 2.5 | 2.5 | 1.8 | 2.5 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_fgas_ip_mt_ce_ar5` | 1.5 | 2.5 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave9.eu_broadband_nuts2` | 1.8 | 2.5 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_cei_gsr011` | 1.9 | 2.4 | 1.8 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_cei_pc035` | 1.8 | 2.4 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_bussea` | 2.1 | 2.4 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_lormot` | 2.2 | 2.4 | 2.2 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_trams` | 1.8 | 2.4 | 1.7 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_30` | 1.8 | 2.4 | 1.7 | 2.4 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_ch4_wa_mt_ce_ar5` | 1.5 | 2.4 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_lu_fl_mt_ce_ar5` | 1.5 | 2.4 | 1.5 | 2.4 | 0.00 | 0 |  |
| `wave10.wb_sh_dyn_mort` | 1.4 | 2.4 | 1.4 | 2.3 | 0.00 | 0 |  |
| `wave9.gr_elstat_heating_energy_regional_unit` | 2.1 | 2.4 | 2.0 | 2.3 | 0.00 | 0 |  |
| `wave9.ie_eirgrid_dispatch_down` | 1.2 | 2.4 | 1.1 | 2.3 | 0.00 | 0 |  |
| `wave9.sk_susr_energy_consumption_okres` | 1.1 | 2.4 | 1.0 | 3.1 | 0.00 | 0 |  |
| `gem.energy_ownership_bioenergy_power_ownership` | 1.8 | 2.3 | 1.7 | 2.3 | 0.00 | 0 |  |
| `gem.energy_ownership_gas_pipeline_ownership` | 2.2 | 2.3 | 1.7 | 2.3 | 0.00 | 0 |  |
| `gem.oil_gas_extraction_field_level_reserves_data` | 1.9 | 2.3 | 1.7 | 2.3 | 0.00 | 0 |  |
| `history.econnextion__requests` | 1.7 | 2.3 | 1.6 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_cei_wm011` | 1.8 | 2.3 | 1.7 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_env_epea_cfin` | 1.9 | 2.3 | 1.9 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_env_watuse_rb` | 1.1 | 2.3 | 1.0 | 2.3 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_e` | 2.2 | 2.3 | 2.0 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ei` | 1.9 | 2.3 | 1.4 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_fechm2` | 1.4 | 2.3 | 1.3 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_nrg_stk_oem` | 2.3 | 2.3 | 2.2 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_rail_if_lvlcros` | 1.5 | 2.3 | 1.5 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_21` | 1.5 | 2.3 | 1.5 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_ag_lnd_el5m_zs` | 1.4 | 2.3 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_eg_gdp_puse_ko_pp_kd` | 1.4 | 2.3 | 1.4 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_en_atm_pm25_mc_zs` | 1.5 | 2.3 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_ch4_ag_mt_ce_ar5` | 1.5 | 2.3 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_ch4_ip_mt_ce_ar5` | 1.4 | 2.3 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_fe_mt_ce_ar5` | 1.7 | 2.3 | 1.5 | 2.3 | 0.07 | 1 |  |
| `wave10.wb_en_ghg_co2_mt_ce_ar5` | 2.2 | 2.3 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_n2o_ic_mt_ce_ar5` | 1.5 | 2.3 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_en_hpt_thrd_no` | 1.4 | 2.3 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_dco2_cd` | 1.4 | 2.3 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_odfc_ru_zs` | 1.5 | 2.3 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_tm_val_fuel_zs_un` | 1.5 | 2.3 | 1.5 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_tx_val_ictg_zs_un` | 1.4 | 2.3 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave9.eu_rail_electrified` | 2.1 | 2.3 | 1.9 | 2.1 | 0.00 | 0 |  |
| `wave9.us_nrel_sharing_sun` | 1.4 | 2.3 | 1.2 | 2.0 | 0.00 | 0 |  |
| `gem.energy_ownership_oil_ngl_pipeline_ownership` | 1.7 | 2.2 | 1.7 | 2.2 | 0.00 | 0 |  |
| `ghsl.population` | 1.5 | 2.2 | 1.3 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_trams` | 1.4 | 2.2 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_20` | 1.4 | 2.2 | 1.3 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_20` | 1.3 | 2.2 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_09_60` | 1.7 | 2.2 | 1.5 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_11` | 2.1 | 2.2 | 1.4 | 1.9 | 0.00 | 0 |  |
| `wave10.gb_census_density` | 1.7 | 2.2 | 1.5 | 2.6 | 0.00 | 0 |  |
| `wave10.gb_census_tenure` | 1.5 | 2.2 | 1.5 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_ag_lnd_el5m_ru_k2` | 1.4 | 2.2 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_ag_lnd_prcp_mm` | 1.4 | 2.2 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_bx_klt_dinv_wd_gd_zs` | 1.4 | 2.2 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_eg_elc_coal_zs` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_en_atm_pm25_mc_m3` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_co2_rt_gdp_pp_kd` | 1.4 | 2.2 | 1.4 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_en_ghg_n2o_tr_mt_ce_ar5` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_en_pop_el5m_zs` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_er_h2o_fwdm_zs` | 1.5 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_er_h2o_fwtl_zs` | 1.4 | 2.2 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_er_mrn_ptmr_zs` | 1.4 | 2.2 | 1.4 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_ie_ppi_watr_cd` | 1.4 | 2.2 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_is_air_psgr` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_is_shp_gcnw_xq` | 1.4 | 2.2 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_it_mlt_main` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_it_net_secr` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_it_net_user_zs` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_dngy_cd` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_dres_gn_zs` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_svng_cd` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_ny_gdp_petr_rt_zs` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_sh_h2o_smdw_ru_zs` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_airp_p5` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_hygn_ru_zs` | 1.4 | 2.2 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_pois_p5_fe` | 1.4 | 2.2 | 1.6 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_sh_sta_smss_zs` | 1.4 | 2.2 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave9.eu_nonhousehold_prices` | 1.6 | 2.2 | 1.6 | 2.1 | 0.00 | 0 |  |
| `gem.energy_ownership_asset_ownership` | 1.6 | 2.1 | 1.4 | 1.8 | 0.00 | 0 |  |
| `gem.energy_ownership_steel_plant_ownership` | 1.8 | 2.1 | 1.8 | 2.2 | 0.00 | 0 |  |
| `gem.oil_gas_extraction_field_level_production_data` | 1.6 | 2.1 | 1.4 | 1.9 | 0.00 | 0 |  |
| `history.pse_capacity__requests` | 1.4 | 2.1 | 1.4 | 1.8 | 0.00 | 0 |  |
| `registers.be` | 1.6 | 2.1 | 1.5 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_env_ac_curm` | 1.7 | 2.1 | 1.6 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_env_ac_egss3` | 1.6 | 2.1 | 1.5 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_env_ac_epneis1` | 1.7 | 2.1 | 1.6 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_env_wat_bal` | 1.9 | 2.1 | 1.8 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_age` | 1.6 | 2.1 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_c` | 1.5 | 2.1 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_nrg_pc_203_v` | 1.7 | 2.1 | 1.6 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_pa_nty` | 1.6 | 2.1 | 1.5 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_roaene` | 2.0 | 2.1 | 1.6 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_spurp` | 1.8 | 2.1 | 1.4 | 1.7 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_40` | 2.0 | 2.1 | 1.3 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_ten00062` | 1.9 | 2.1 | 1.7 | 2.2 | 0.00 | 0 |  |
| `wave10.eu_ten00125` | 2.0 | 2.1 | 2.0 | 2.1 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_pstra` | 1.4 | 2.1 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.wb_ag_srf_totl_k2` | 1.3 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_eg_egy_prim_pp_kd` | 1.4 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_eg_elc_ngas_zs` | 1.3 | 2.1 | 1.3 | 2.2 | 0.00 | 0 |  |
| `wave10.wb_eg_elc_rnwx_kh` | 1.4 | 2.1 | 1.4 | 2.3 | 0.00 | 0 |  |
| `wave10.wb_eg_use_comm_gd_pp_kd` | 1.5 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_en_fsh_thrd_no` | 1.4 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_er_fsh_capt_mt` | 1.4 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_ic_frm_outg_zs` | 1.4 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_ip_tmk_rsct` | 1.4 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_ny_adj_dkap_cd` | 1.4 | 2.1 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_ny_gdp_coal_rt_zs` | 1.4 | 2.1 | 1.4 | 2.2 | 0.00 | 0 |  |
| `wave9.eu_water_use` | 1.8 | 2.1 | 1.7 | 2.1 | 0.00 | 0 |  |
| `wave9.gb_elexon_balancing` | 1.0 | 2.1 | 0.9 | 1.8 | 0.00 | 0 |  |
| `wave9.gb_epc_stats` | 2.1 | 2.1 | 1.1 | 1.1 | 0.00 | 0 |  |
| `wave9.gb_ulev_la` | 2.1 | 2.1 | 1.7 | 1.7 | 0.00 | 0 |  |
| `wave9.us_epa_agstar` | 2.1 | 2.1 | 1.0 | 1.0 | 0.00 | 0 |  |
| `gem.energy_ownership_cement_and_concrete_ownership` | 1.7 | 2.0 | 1.6 | 2.1 | 0.00 | 0 |  |
| `gem.energy_ownership_entity_ownership` | 1.8 | 2.0 | 1.5 | 1.8 | 0.00 | 0 |  |
| `gem_ownership.entity_ownership` | 2.0 | 2.0 | 1.5 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_cei_pc034` | 1.4 | 2.0 | 1.3 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_caremiss` | 1.4 | 2.0 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_31` | 1.4 | 2.0 | 1.4 | 2.0 | 0.00 | 0 |  |
| `wave10.eu_ten00139` | 1.5 | 2.0 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave10.wb_ie_ppn_watr_cd` | 1.5 | 2.0 | 1.4 | 2.1 | 0.00 | 0 |  |
| `wave9.cz_ceps_balancing` | 2.0 | 2.0 | 1.9 | 1.9 | 0.00 | 0 |  |
| `wave9.de_kba_districts` | 2.0 | 2.0 | 1.3 | 1.3 | 0.00 | 0 |  |
| `gem.energy_ownership_iron_mine_ownership` | 1.6 | 1.9 | 1.5 | 1.9 | 0.00 | 0 |  |
| `wave10.eu_cei_wm010` | 1.3 | 1.9 | 1.3 | 1.9 | 0.00 | 0 |  |
| `wave9.fr_ore_solar_commune` | 1.9 | 1.9 | 1.6 | 1.6 | 0.00 | 0 |  |
| `gem_ownership.asset_ownership` | 1.8 | 1.8 | 1.6 | 1.6 | 0.00 | 0 |  |
| `gem_ownership.cement_and_concrete_ownership` | 1.8 | 1.8 | 1.7 | 1.7 | 0.00 | 0 |  |
| `gem_ownership.iron_mine_ownership` | 1.8 | 1.8 | 1.7 | 1.7 | 0.00 | 0 |  |
| `entsog_tyndp.projects` | 1.2 | 1.7 | 1.1 | 1.4 | 0.00 | 0 |  |
| `gem.cement_final_data` | 1.4 | 1.7 | 1.4 | 1.6 | 0.00 | 0 |  |
| `gem.energy_ownership_all_entities` | 1.4 | 1.7 | 1.3 | 1.7 | 0.00 | 0 |  |
| `gem.energy_ownership_coal_mine_ownership` | 1.5 | 1.7 | 1.3 | 1.7 | 0.00 | 0 |  |
| `gem_ownership.steel_plant_ownership` | 1.7 | 1.7 | 1.7 | 1.7 | 0.00 | 0 |  |
| `wave10.eu_env_epea_invsp` | 1.3 | 1.7 | 1.3 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_d_cv` | 1.6 | 1.7 | 1.6 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_nrg_inf_lbpc` | 1.3 | 1.7 | 1.3 | 1.7 | 0.00 | 0 |  |
| `wave10.eu_nrg_stk_gas` | 1.6 | 1.7 | 1.6 | 1.7 | 0.00 | 0 |  |
| `wave10.eu_rail_eq_wagon` | 1.6 | 1.7 | 1.5 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_busmot` | 1.3 | 1.7 | 1.2 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_11_20` | 1.2 | 1.7 | 1.1 | 1.6 | 0.00 | 0 |  |
| `wave9.eu_energy_productivity` | 1.2 | 1.7 | 1.2 | 1.6 | 0.00 | 0 |  |
| `wave9.ie_cso_datacentres` | 1.5 | 1.7 | 1.3 | 1.7 | 0.00 | 0 |  |
| `eaglei.coverage` | 1.1 | 1.6 | 1.0 | 1.5 | 0.00 | 0 |  |
| `gem.iron_steel_electric_arc_furnaces` | 1.4 | 1.6 | 1.2 | 1.4 | 0.00 | 0 |  |
| `gem_ownership.coal_plant_ownership` | 1.6 | 1.6 | 1.4 | 1.4 | 0.00 | 0 |  |
| `wave10.eu_cei_pc050` | 1.1 | 1.6 | 1.1 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_cei_wm060` | 1.2 | 1.6 | 1.1 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_env_wat_pop` | 1.2 | 1.6 | 1.1 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_nrg_dhdc_n` | 1.3 | 1.6 | 1.2 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_busage` | 1.4 | 1.6 | 1.3 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_12_51` | 1.2 | 1.6 | 1.1 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_ten00110` | 1.2 | 1.6 | 1.1 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_ten00129` | 1.6 | 1.6 | 1.6 | 1.6 | 0.00 | 0 |  |
| `wave10.gb_desnz_ren_capacity_la` | 1.6 | 1.6 | 1.6 | 1.6 | 0.00 | 0 |  |
| `wave9.gb_desnz_subregional_fit` | 1.6 | 1.6 | 1.2 | 1.2 | 0.00 | 0 |  |
| `wave9.us_afdc_registrations` | 1.6 | 1.6 | 1.3 | 1.3 | 0.00 | 0 |  |
| `co2stop.daughter_units_summary` | 1.5 | 1.5 | 1.0 | 1.3 | 0.00 | 0 |  |
| `gem.gas_infrastructure_data` | 1.3 | 1.5 | 1.3 | 1.5 | 0.00 | 0 |  |
| `gem_ownership.bioenergy_power_ownership` | 1.5 | 1.5 | 1.5 | 1.5 | 0.00 | 0 |  |
| `gem_ownership.gas_pipeline_ownership` | 1.5 | 1.5 | 1.3 | 1.3 | 0.00 | 0 |  |
| `gem_ownership.oil___ngl_pipeline_ownership` | 1.5 | 1.5 | 1.4 | 1.4 | 0.00 | 0 |  |
| `wave10.eu_iww_eq_power_lo` | 1.1 | 1.5 | 1.1 | 1.4 | 0.00 | 0 |  |
| `wave10.eu_nrg_ind_ep` | 1.1 | 1.5 | 1.2 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqr_motors` | 1.2 | 1.5 | 1.2 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_road_eqs_trail` | 1.2 | 1.5 | 1.1 | 1.6 | 0.00 | 0 |  |
| `wave10.eu_sdg_06_50` | 1.1 | 1.5 | 1.1 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_07_50` | 1.3 | 1.5 | 1.2 | 1.5 | 0.00 | 0 |  |
| `wave10.eu_sdg_13_70` | 1.2 | 1.5 | 1.2 | 1.4 | 0.00 | 0 |  |
| `wave10.eu_tran_hv_frtra` | 1.1 | 1.5 | 1.1 | 1.5 | 0.00 | 0 |  |
| `wave9.us_eia861_reliability` | 1.5 | 1.5 | 1.2 | 1.2 | 0.00 | 0 |  |
| `gem.iron_steel_blast_furnace_relinings` | 1.3 | 1.4 | 1.1 | 1.4 | 0.00 | 0 |  |
| `gem.oil_gas_extraction_project_level_production_data` | 1.2 | 1.4 | 1.1 | 1.3 | 0.00 | 0 |  |
| `gem_ownership.all_entities` | 1.4 | 1.4 | 1.4 | 1.4 | 0.00 | 0 |  |
| `wave10.gb_census_cars` | 1.0 | 1.4 | 1.0 | 1.4 | 0.00 | 0 |  |
| `wave9.gb_dec_certificates` | 1.4 | 1.4 | 1.4 | 1.4 | 0.00 | 0 |  |
| `wave9.gb_dft_veh0142` | 1.4 | 1.4 | 1.4 | 1.4 | 0.00 | 0 |  |
| `wave9.gb_neso_tnuos` | 0.8 | 1.4 | 0.8 | 1.4 | 0.00 | 0 |  |
| `wave9.nl_cbs_datacentres` | 1.4 | 1.4 | 1.3 | 1.3 | 0.00 | 0 |  |
| `co2stop.sum_output` | 1.0 | 1.3 | 1.0 | 1.2 | 0.00 | 0 |  |
| `gem.coal_mines_historical_production_non_chin` | 1.1 | 1.3 | 1.1 | 1.3 | 0.00 | 0 |  |
| `gem.gas_finance_gas_power_plants` | 1.1 | 1.3 | 1.1 | 1.3 | 0.00 | 0 |  |
| `gem.iron_steel_plant_production` | 1.1 | 1.3 | 1.1 | 1.3 | 0.00 | 0 |  |
| `gem.methane_emitters_plumes` | 1.1 | 1.3 | 1.1 | 1.2 | 0.00 | 0 |  |
| `gem_ownership.coal_mine_ownership` | 1.3 | 1.3 | 1.1 | 1.1 | 0.00 | 0 |  |
| `wave9.us_eia861m_small_solar` | 1.3 | 1.3 | 1.3 | 1.3 | 0.00 | 0 |  |
| `gem.iron_ore_mines_prodconsmetcoalironore` | 1.0 | 1.2 | 0.9 | 1.1 | 0.00 | 0 |  |
| `gem.iron_steel_plant_capacities_and_status` | 1.1 | 1.2 | 1.0 | 1.2 | 0.00 | 0 |  |
| `gem_ownership.gas_plant_ownership` | 1.2 | 1.2 | 1.2 | 1.2 | 0.00 | 0 |  |
| `mastr.catalog_values` | 1.1 | 1.2 | 1.0 | 1.1 | 0.00 | 0 |  |
| `wave9.us_eia861_reliability_xlsx` | 1.2 | 1.2 | 1.0 | 1.0 | 0.00 | 0 |  |
| `co2stop.dic_availabledata` | 1.1 | 1.1 | 1.0 | 1.0 | 0.00 | 0 |  |
| `co2stop.dic_fault_extent` | 1.0 | 1.0 | 1.0 | 1.0 | 0.00 | 0 |  |
| `co2stop.dic_on_offshore` | 1.0 | 1.0 | 0.9 | 0.9 | 0.00 | 0 |  |
| `co2stop.dic_surfissues` | 1.0 | 1.0 | 1.0 | 1.0 | 0.00 | 0 |  |
| `wave10.gb_desnz_ren_sites_la` | 1.0 | 1.0 | 0.9 | 0.9 | 0.00 | 0 |  |
| `wave9.us_eia_recs_heat_pumps_state` | 1.0 | 1.0 | 1.0 | 1.0 | 0.00 | 0 |  |
| `co2stop.dic_geol_basin` | 0.9 | 0.9 | 0.9 | 0.9 | 0.00 | 0 |  |
| `eia930.bas` | 0.8 | 0.9 | 0.8 | 0.9 | 0.00 | 0 |  |
| `co2stop.dic_assess_traptype` | 0.8 | 0.8 | 0.8 | 0.8 | 0.00 | 0 |  |
| `wave10.gb_desnz_elec_distribution` | 0.8 | 0.8 | 0.8 | 0.8 | 0.00 | 0 |  |
| `wave9.nl_rdw_vehicles` | 0.8 | 0.8 | 0.8 | 0.8 | 0.00 | 0 |  |
<!-- measured:end -->
