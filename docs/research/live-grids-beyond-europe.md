# Live grids, brief 30 Track 3.4 (2026-11-05)

## Built
- Alberta: scripts/probe_aeso.py, scripts/fetch_aeso.py -> alberta.json
  CSD servlet http://ets.aeso.ca/ets_web/ip/Market/Reports/CSDReportServlet (HTTP only; HTTPS handshake fails).
  Passthrough summary (AIL, TNG, NAI), per-group MC/TNG/DCR + TOTAL, interchange BC/MT/SK (export +), 231 assets.
  Terms aeso.ca/legal: "The material may be used and copied for non-commercial, personal or educational
  purposes, provided that the material is not modified and that copyright notices are not deleted. Any other
  use of this material without the AESO's written permission is prohibited."  -> NON-COMMERCIAL ONLY.
  Test: AIL 11428, TNG 11703 (sum groups = TOTAL), NAI 275 (BC 250, MT 25, SK 0).
- South Korea: scripts/probe_kpx.py, scripts/fetch_kpx.py -> korea.json
  new.kpx.or.kr powerinfoSubmain.es / powerSource.es (mid=a10606030000), robots allows.
  Gen from page var ictArr; placeholder rows regDate "0" skipped. BTM/PPA solar = KPX estimates.
  Licence: data.go.kr dataset 15106744 (KPX generation by source) "이용허락범위 제한 없음"; site footer "ALL RIGHTS RESERVED".
  Test: demand 58584 MW, sum of 13 columns 58584.1 MW at 00:55 KST.

## Blocked
- Turkey EPİAŞ: 401 AUTH002 / 406 "TGT required" -> needs account (EPIAS_USERNAME/PASSWORD). probe_epias.py
- Chile CEN: SIP API 403 "Authentication parameters missing" (user_key via portal.api.coordinador.cl registration);
  charts are Qlik mashups. A user_key is embedded in the website's JS — NOT used (not issued to us). probe_coordinador.py
- India Grid-India/Vidyut Pravah/MERIT: connection reset / 503 from cloud (same as GitHub runners, brief 17). probe_grid_india.py
