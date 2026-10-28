import streamlit as st
import pandas as pd
import numpy as np
import requests
import sqlite3
import re
import altair as alt
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(page_title="Global Seismic Trends", page_icon="🌍", layout="wide")
DB_PATH = Path("earthquakes.db")
API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

st.markdown("""
<style>
.main {background: #0b1220;}
[data-testid="stAppViewContainer"] {background: linear-gradient(145deg,#0b1220,#111c31);}
[data-testid="stSidebar"] {background: #101a2b;}
h1,h2,h3 {color:#eaf2ff;}
div[data-testid="stMetric"] {background:#142238;border:1px solid #263a57;padding:14px;border-radius:14px;}
.small-muted {color:#9fb2ca;}
</style>
""", unsafe_allow_html=True)

st.title("🌍 Global Seismic Trends")
st.caption("Data-driven earthquake insights • USGS live data • Python, Pandas, Regex, SQL & Streamlit")

def country_from_place(place):
    """Best-effort Regex extraction from USGS place descriptions; not a verified geocoder."""
    if not isinstance(place, str) or not place.strip():
        return "Unknown"
    p = re.sub(r"\s+", " ", place).strip()
    # USGS places commonly use 'X km direction of Y'; retain the trailing named location.
    m = re.search(r"(?:of|near)\s+(.+)$", p, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return p

def prepare_data(features):
    rows = []
    for f in features:
        props = f.get("properties") or {}
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") or [None, None, None]
        ts = props.get("time")
        updated = props.get("updated")
        rows.append({
            "id": f.get("id"),
            "time": pd.to_datetime(ts, unit="ms", utc=True) if ts else pd.NaT,
            "updated": pd.to_datetime(updated, unit="ms", utc=True) if updated else pd.NaT,
            "longitude": coords[0] if len(coords)>0 else None,
            "latitude": coords[1] if len(coords)>1 else None,
            "depth_km": coords[2] if len(coords)>2 else None,
            "mag": props.get("mag"),
            "magType": props.get("magType"),
            "place": props.get("place"),
            "status": props.get("status"),
            "tsunami": props.get("tsunami", 0),
            "sig": props.get("sig"),
            "net": props.get("net"),
            "nst": props.get("nst"),
            "dmin": props.get("dmin"),
            "rms": props.get("rms"),
            "gap": props.get("gap"),
            "magError": props.get("magError"),
            "depthError": props.get("depthError"),
            "magNst": props.get("magNst"),
            "locationSource": props.get("locationSource"),
            "magSource": props.get("magSource"),
            "types": props.get("types"),
            "ids": props.get("ids"),
            "sources": props.get("sources"),
            "type": props.get("type"),
            "alert": props.get("alert"),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ["longitude","latitude","depth_km","mag","sig","nst","dmin","rms","gap","magError","depthError","magNst","tsunami"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["magType","place","status","net","locationSource","magSource","types","ids","sources","type","alert"]:
        df[col] = df[col].fillna("unknown").astype(str).str.strip()
    df["country_or_region"] = df["place"].map(country_from_place)
    df["year"] = df["time"].dt.year
    df["month"] = df["time"].dt.month
    df["day"] = df["time"].dt.day
    df["day_of_week"] = df["time"].dt.day_name()
    df["hour"] = df["time"].dt.hour
    df["depth_category"] = np.select(
        [df["depth_km"].lt(50), df["depth_km"].between(50,300,inclusive="both"), df["depth_km"].gt(300)],
        ["Shallow (<50 km)","Intermediate (50–300 km)","Deep (>300 km)"], default="Unknown"
    )
    df["strength_category"] = np.select(
        [df["mag"].ge(7), df["mag"].ge(5), df["mag"].ge(3)],
        ["Major (7+)","Strong (5–6.9)","Light/Moderate (3–4.9)"], default="Below 3 / unknown"
    )
    return df

def load_api(start, end, min_mag, max_events):
    params = {
        "format": "geojson",
        "starttime": start.isoformat(),
        "endtime": end.isoformat(),
        "minmagnitude": float(min_mag),
        "orderby": "time",
        "limit": int(max_events),
    }
    r = requests.get(API_URL, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    return prepare_data(payload.get("features", [])), payload.get("metadata", {})

def save_db(df):
    if df.empty:
        return
    out = df.copy()
    for c in ["time", "updated"]:
        if c in out:
            out[c] = out[c].astype(str)
    with sqlite3.connect(DB_PATH) as conn:
        out.to_sql("earthquakes", conn, if_exists="replace", index=False)

def read_db():
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql_query("SELECT * FROM earthquakes", conn)
        except Exception:
            return pd.DataFrame()
    for c in ["time","updated"]:
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce", utc=True)
    return df

def get_data():
    if "earthquake_data" in st.session_state:
        return st.session_state["earthquake_data"]
    return read_db()

with st.sidebar:
    st.header("⚙️ Data controls")
    today = date.today()
    default_start = today - timedelta(days=365*5)
    start = st.date_input("Start date", value=default_start, max_value=today)
    end = st.date_input("End date", value=today, max_value=today)
    min_mag = st.slider("Minimum magnitude", 0.0, 7.0, 2.5, 0.5)
    max_events = st.select_slider("Maximum events", options=[500,1000,2500,5000,10000,20000], value=10000)
    fetch = st.button("↻ Fetch USGS data", type="primary", use_container_width=True)
    st.caption("Large date ranges may be limited by the API event cap. Narrow the dates or raise the magnitude threshold if needed.")
    st.divider()
    uploaded = st.file_uploader("Or upload a CSV", type=["csv"])
    st.caption("CSV should contain USGS-style columns or exported app data.")

if fetch:
    if start > end:
        st.error("Start date must be before end date.")
    else:
        with st.spinner("Fetching earthquake events from USGS…"):
            try:
                df, metadata = load_api(start, end, min_mag, max_events)
                st.session_state["earthquake_data"] = df
                save_db(df)
                st.success(f"Loaded {len(df):,} events from USGS.")
                st.rerun()
            except requests.RequestException as e:
                st.error(f"USGS request failed: {e}. Check your internet connection and try again.")
            except Exception as e:
                st.error(f"Could not process data: {e}")

if uploaded is not None:
    try:
        raw = pd.read_csv(uploaded)
        # If uploaded file is an app export, use it directly; otherwise normalize common USGS CSV columns.
        if "time" in raw.columns and "mag" in raw.columns:
            raw["time"] = pd.to_datetime(raw["time"], errors="coerce", utc=True)
            for c in ["updated"]:
                if c in raw: raw[c] = pd.to_datetime(raw[c], errors="coerce", utc=True)
            st.session_state["earthquake_data"] = raw
            save_db(raw)
        else:
            st.warning("CSV loaded, but required columns 'time' and 'mag' were not found.")
    except Exception as e:
        st.error(f"CSV import failed: {e}")

df = get_data()
if df.empty:
    st.info("No dataset loaded yet. Use **Fetch USGS data** in the sidebar to load the latest events, or upload a CSV.")
    st.markdown("### What this app provides")
    c1,c2,c3 = st.columns(3)
    c1.metric("Data source", "USGS API")
    c2.metric("Analysis window", "Up to 5 years")
    c3.metric("Storage", "SQLite")
    st.markdown("""
    - Interactive global event map and magnitude/depth filters
    - Time-series and category analytics
    - Data-quality views using station count, RMS, and azimuthal gap
    - SQL query explorer and CSV export
    - Local SQLite database (`earthquakes.db`) for repeatable analysis
    """)
    st.stop()

# Ensure date type / normalized expected fields
if "time" in df:
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
if "mag" not in df:
    st.error("The loaded data does not contain a 'mag' column.")
    st.stop()
for c in ["depth_km","latitude","longitude","tsunami","sig","nst","rms","gap","year","month","day","hour"]:
    if c not in df: df[c] = np.nan
if "place" not in df: df["place"] = "Unknown"
if "status" not in df: df["status"] = "unknown"
if "magType" not in df: df["magType"] = "unknown"
if "net" not in df: df["net"] = "unknown"
if "depth_category" not in df:
    df["depth_category"] = np.select([df.depth_km.lt(50), df.depth_km.le(300)],["Shallow (<50 km)","Intermediate (50–300 km)"],default="Deep (>300 km)")
if "country_or_region" not in df:
    df["country_or_region"] = df["place"].map(country_from_place)
if "year" not in df: df["year"] = df["time"].dt.year
if "month" not in df: df["month"] = df["time"].dt.month
if "day_of_week" not in df: df["day_of_week"] = df["time"].dt.day_name()
if "hour" not in df: df["hour"] = df["time"].dt.hour

st.caption(f"Dataset: {len(df):,} records • Times shown in UTC • Storage: {'earthquakes.db' if DB_PATH.exists() else 'session data'}")
with st.expander("Filter the dashboard", expanded=True):
    f1,f2,f3,f4 = st.columns(4)
    mag_min = float(np.nanmin(df["mag"])) if df["mag"].notna().any() else 0
    mag_max = float(np.nanmax(df["mag"])) if df["mag"].notna().any() else 10
    if mag_min == mag_max: mag_max = mag_min + 0.1
    chosen_mag = f1.slider("Magnitude range", mag_min, mag_max, (mag_min,mag_max))
    depth_max = float(np.nanmax(df["depth_km"])) if df["depth_km"].notna().any() else 800
    chosen_depth = f2.slider("Depth (km)", 0.0, max(1.0,depth_max), (0.0,max(1.0,depth_max)))
    statuses = sorted(df["status"].dropna().astype(str).unique().tolist())
    chosen_status = f3.multiselect("Review status", statuses, default=statuses)
    alerts = sorted(df["alert"].dropna().astype(str).unique().tolist()) if "alert" in df else []
    chosen_alert = f4.multiselect("Alert level", alerts, default=alerts) if alerts else []

view = df[df["mag"].between(chosen_mag[0],chosen_mag[1],inclusive="both") & df["depth_km"].between(chosen_depth[0],chosen_depth[1],inclusive="both")].copy()
if chosen_status and "status" in view:
    view = view[view["status"].astype(str).isin(chosen_status)]
if chosen_alert and "alert" in view:
    view = view[view["alert"].astype(str).isin(chosen_alert)]

total = len(view)
strong = int((view["mag"] >= 5).sum())
tsunami_n = int((pd.to_numeric(view["tsunami"], errors="coerce").fillna(0) == 1).sum())
avg_mag = view["mag"].mean()
k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Earthquakes", f"{total:,}")
k2.metric("Magnitude 5+", f"{strong:,}")
k3.metric("Tsunami flag", f"{tsunami_n:,}")
k4.metric("Average magnitude", f"{avg_mag:.2f}" if pd.notna(avg_mag) else "—")
k5.metric("Max magnitude", f"{view['mag'].max():.1f}" if view["mag"].notna().any() else "—")

tab1,tab2,tab3,tab4,tab5 = st.tabs(["🌐 Overview","📈 Trends","🧪 Quality & Events","🗃️ SQL Explorer","📥 Data"])

with tab1:
    left,right = st.columns([1.55,1])
    with left:
        st.subheader("Global epicentres")
        mapdf = view.dropna(subset=["latitude","longitude"]).copy()
        if not mapdf.empty:
            mapdf = mapdf.rename(columns={"latitude":"lat","longitude":"lon"})
            st.map(mapdf[["lat","lon"]], size=8)
            st.caption("Map points show epicentres; dense regions may overlap.")
        else:
            st.info("No valid latitude/longitude coordinates in the current filter.")
    with right:
        st.subheader("Magnitude distribution")
        hist = view.dropna(subset=["mag"])[["mag"]]
        if not hist.empty:
            chart = alt.Chart(hist).mark_bar().encode(
                x=alt.X("mag:Q", bin=alt.Bin(maxbins=24), title="Magnitude"),
                y=alt.Y("count():Q", title="Events"),
                tooltip=[alt.Tooltip("count():Q",title="Events")]
            ).properties(height=290)
            st.altair_chart(chart, use_container_width=True)
        st.subheader("Depth categories")
        dep = view["depth_category"].fillna("Unknown").value_counts().rename_axis("Depth category").reset_index(name="Events")
        if not dep.empty:
            st.bar_chart(dep.set_index("Depth category"))
    st.subheader("Top 10 strongest events")
    cols = [c for c in ["time","mag","place","depth_km","status","tsunami","sig"] if c in view]
    st.dataframe(view.sort_values("mag",ascending=False)[cols].head(10), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Earthquakes over time")
    dated = view.dropna(subset=["time"]).copy()
    if not dated.empty:
        dated["month_start"] = dated["time"].dt.to_period("M").dt.to_timestamp()
        monthly = dated.groupby("month_start").size().rename("Earthquakes").reset_index()
        st.line_chart(monthly.set_index("month_start"))
        a,b = st.columns(2)
        with a:
            st.subheader("Events by year")
            yearly = dated.groupby(dated["time"].dt.year).size().rename("Earthquakes")
            st.bar_chart(yearly)
        with b:
            st.subheader("Events by weekday")
            order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            dow = dated["time"].dt.day_name().value_counts().reindex(order,fill_value=0)
            st.bar_chart(dow)
        st.subheader("Events by hour (UTC)")
        hourly = dated["time"].dt.hour.value_counts().sort_index().reindex(range(24),fill_value=0)
        st.bar_chart(hourly)
        if len(yearly) >= 2:
            growth = yearly.sort_index().pct_change().mul(100).round(2).rename("YoY growth (%)")
            st.write("Year-over-year change in event count")
            st.dataframe(growth.reset_index(names="Year"), hide_index=True, use_container_width=True)
    else:
        st.info("No valid timestamps in the filtered dataset.")
    st.subheader("Average magnitude by magnitude type")
    if "magType" in view:
        st.dataframe(view.groupby("magType",dropna=False)["mag"].agg(["count","mean"]).sort_values("mean",ascending=False).reset_index(), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Reporting and data-quality metrics")
    q1,q2 = st.columns(2)
    with q1:
        st.markdown("**Reviewed vs automatic**")
        st.bar_chart(view["status"].fillna("unknown").value_counts())
        st.markdown("**Most active reporting networks**")
        st.bar_chart(view["net"].fillna("unknown").value_counts().head(12))
    with q2:
        st.markdown("**Earthquake event types**")
        if "type" in view: st.bar_chart(view["type"].fillna("unknown").value_counts().head(12))
        st.markdown("**Tsunami-flagged events by year**")
        tsunami_df = view[pd.to_numeric(view["tsunami"],errors="coerce").fillna(0).eq(1)].dropna(subset=["time"])
        if not tsunami_df.empty: st.bar_chart(tsunami_df.groupby(tsunami_df["time"].dt.year).size())
        else: st.info("No tsunami-flagged events in this filter.")
    st.subheader("Potentially lower-quality location solutions")
    quality = view.copy()
    quality["rms"] = pd.to_numeric(quality["rms"],errors="coerce")
    quality["gap"] = pd.to_numeric(quality["gap"],errors="coerce")
    quality["quality_score_proxy"] = quality[["rms","gap"]].mean(axis=1, skipna=True)
    st.caption("Proxy only: high RMS and large azimuthal gap can indicate less constrained solutions; this is not an official USGS reliability score.")
    qcols = [c for c in ["time","mag","place","nst","rms","gap","quality_score_proxy"] if c in quality]
    st.dataframe(quality.sort_values("quality_score_proxy",ascending=False)[qcols].head(20), use_container_width=True, hide_index=True)
    st.subheader("High station coverage (nst > threshold)")
    threshold = st.number_input("Station count threshold", min_value=0, value=20, step=5)
    if "nst" in view:
        st.dataframe(view[pd.to_numeric(view["nst"],errors="coerce") > threshold][[c for c in ["time","mag","place","nst","rms","gap"] if c in view]].head(100), use_container_width=True, hide_index=True)

with tab4:
    st.subheader("SQL query explorer (SQLite)")
    st.caption("Queries run against the locally stored `earthquakes` table. Use SELECT queries only.")
    examples = {
        "Top 10 strongest earthquakes": "SELECT time, mag, place, depth_km, tsunami FROM earthquakes ORDER BY mag DESC LIMIT 10",
        "Top 10 deepest earthquakes": "SELECT time, mag, place, depth_km FROM earthquakes ORDER BY depth_km DESC LIMIT 10",
        "Year with most earthquakes": "SELECT year, COUNT(*) AS event_count FROM earthquakes GROUP BY year ORDER BY event_count DESC",
        "Average magnitude by magnitude type": "SELECT magType, COUNT(*) AS events, ROUND(AVG(mag), 2) AS avg_mag FROM earthquakes GROUP BY magType ORDER BY avg_mag DESC",
        "Tsunami flags by year": "SELECT year, SUM(CASE WHEN tsunami=1 THEN 1 ELSE 0 END) AS tsunami_flagged FROM earthquakes GROUP BY year ORDER BY year",
        "Reviewed vs automatic": "SELECT status, COUNT(*) AS events FROM earthquakes GROUP BY status ORDER BY events DESC",
        "High station coverage": "SELECT time, mag, place, nst FROM earthquakes WHERE nst > 20 ORDER BY nst DESC LIMIT 100",
    }
    choice = st.selectbox("Example query", list(examples))
    query = st.text_area("SQL", value=examples[choice], height=120)
    if st.button("Run SQL query"):
        if not query.strip().lower().startswith("select"):
            st.error("Only SELECT queries are allowed.")
        elif not DB_PATH.exists():
            st.warning("Fetch or save a dataset first so the SQLite database exists.")
        else:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    result = pd.read_sql_query(query, conn)
                st.dataframe(result, use_container_width=True, hide_index=True)
                st.download_button("Download query result CSV", result.to_csv(index=False).encode("utf-8"), "sql_result.csv", "text/csv")
            except Exception as e:
                st.error(f"SQL error: {e}")

with tab5:
    st.subheader("Dataset preview")
    st.write(f"Rows: **{len(view):,}** · Columns: **{len(view.columns)}**")
    st.dataframe(view.head(500), use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download filtered CSV", view.to_csv(index=False).encode("utf-8"), "earthquake_data.csv", "text/csv")
    st.subheader("Missing-value report")
    missing = view.isna().sum().sort_values(ascending=False).rename("Missing values").to_frame()
    missing["Missing %"] = (missing["Missing values"] / max(1,len(view)) * 100).round(1)
    st.dataframe(missing, use_container_width=True)
    st.subheader("Available columns")
    st.code(", ".join(view.columns.astype(str).tolist()))

st.divider()
st.caption("Source: USGS Earthquake Catalog API. This dashboard is for educational analysis and is not an official early-warning or hazard-prediction system. USGS alert, tsunami, RMS, gap, and significance fields are catalog attributes; casualties and economic losses are not included in this feed.")
