# DuckDB patterns

Capacity by type in one country (app table):

    SELECT fuel, round(sum(mw)) AS mw, count(*) AS plants
    FROM app.eu_plants WHERE country = 'ES' GROUP BY fuel ORDER BY mw DESC

Plants within 50 km of a point (haversine, km):

    SELECT name, fuel, mw,
           2 * 6371.0088 * asin(sqrt(pow(sin(radians(lat - 52.37) / 2), 2)
             + cos(radians(52.37)) * cos(radians(lat)) * pow(sin(radians(lon - 4.90) / 2), 2))) AS km
    FROM app.eu_plants QUALIFY km <= 50 ORDER BY mw DESC

Newest snapshot of a register:

    SELECT * FROM mastr.units_solar WHERE snapshot = (SELECT max(snapshot) FROM mastr.units_solar)

Share of a total, computed in SQL:

    SELECT fuel, sum(mw) / sum(sum(mw)) OVER () * 100 AS pct FROM app.eu_plants
    WHERE country = 'DE' GROUP BY fuel
