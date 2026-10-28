# Global Seismic Trends: Data-Driven Earthquake Insights

A Streamlit application for exploring global earthquake events from the USGS Earthquake Catalog API.

## Features
- Fetch earthquake events for a chosen date range and minimum magnitude.
- Five-year analysis window by default, with configurable event cap.
- Pandas cleaning, datetime parsing, numeric coercion, and Regex-based best-effort place extraction.
- Derived year/month/day/hour, weekday, depth category, and strength category.
- Interactive map, magnitude distribution, monthly/yearly trends, weekday/hour analysis.
- Tsunami flags, reporting status/network, event types, and data-quality views.
- SQLite persistence (`earthquakes.db`), SQL explorer, and CSV export/import.

## Run on Windows
1. Install Python 3.10–3.13 recommended for widest package compatibility.
2. Extract this folder.
3. Open Command Prompt in this folder.
4. Run:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   streamlit run app.py
   ```
5. Your browser opens the dashboard. Press **Fetch USGS data** in the sidebar.

If `py` does not work, use `python -m venv .venv` and the matching activation command.

## Data notes and limitations
- The USGS API is an external service and requires internet access.
- Large date ranges may hit the requested event cap; increase magnitude or narrow the date range if you need a smaller response.
- `country_or_region` uses Regex heuristics on USGS place text. It is not a verified country/continent geocoder; use a geocoding dataset/service for authoritative country and continent analytics.
- The USGS earthquake feed does not generally provide casualty totals or economic losses. Those analyst tasks require an additional trusted disaster-impact dataset, and should not be fabricated.
- Alert fields may be null; null means no alert value was supplied, not necessarily zero risk.
- This is an educational analytics dashboard, not a prediction or early-warning tool.

## Assignment coverage
Includes magnitude/depth ranking, time analysis, status/type/network counts, tsunami-flagged events by year, station coverage, RMS/gap quality review, CSV export, and SQL examples. Some requested analyses (continent aggregates, verified country rankings, casualties, economic loss, distance between events) need additional geospatial or disaster-impact data for scientifically valid results.
