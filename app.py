import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import requests
from bs4 import BeautifulSoup
import re
import time
import json
import io
from urllib.parse import quote_plus
import random

# curl_cffi is optional — graceful degradation if not installed
try:
    from curl_cffi import requests as cf_requests
    _CURL_CFFI_AVAILABLE = True
except ImportError:
    _CURL_CFFI_AVAILABLE = False

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Section 8 Wholesale Underwriter",
    layout="wide",
    page_icon="🏠",
)

st.markdown("""
<style>
/* ── Apple System Font ── */
* { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial, sans-serif !important; }

/* ── App background ── */
.stApp { background: #000000 !important; }
.main .block-container { background: #000000; padding: 2rem 2.5rem; max-width: 1500px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #1C1C1E !important; border-right: 1px solid #2C2C2E !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #8E8E93 !important; font-size: 10px !important; font-weight: 600 !important;
    letter-spacing: 0.08em !important; text-transform: uppercase !important; margin-top: 18px !important;
}

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #1C1C1E; border-radius: 14px; padding: 16px 20px; border: none;
    box-shadow: 0 1px 3px rgba(0,0,0,0.5);
}
div[data-testid="metric-container"] label {
    color: #8E8E93 !important; font-size: 10px !important; font-weight: 600 !important;
    letter-spacing: 0.07em !important; text-transform: uppercase !important;
}
div[data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 22px !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
div[data-testid="stMetricDelta"] { font-size: 11px !important; }

/* ── Flag banners ── */
.flag-critical {
    background: rgba(255,69,58,0.13); border-left: 3px solid #FF453A;
    border-radius: 10px; padding: 10px 14px; margin: 6px 0;
    color: #FF6961 !important; font-weight: 500; font-size: 13px;
}
.flag-inspect {
    background: rgba(255,159,10,0.13); border-left: 3px solid #FF9F0A;
    border-radius: 10px; padding: 10px 14px; margin: 6px 0;
    color: #FFB340 !important; font-weight: 500; font-size: 13px;
}
.flag-rehab {
    background: rgba(10,132,255,0.13); border-left: 3px solid #0A84FF;
    border-radius: 10px; padding: 10px 14px; margin: 6px 0;
    color: #409CFF !important; font-weight: 500; font-size: 13px;
}
.flag-ok {
    background: rgba(50,215,75,0.13); border-left: 3px solid #32D74B;
    border-radius: 10px; padding: 10px 14px; margin: 6px 0;
    color: #30DB5B !important; font-weight: 500; font-size: 13px;
}

/* ── Rent confidence pills ── */
.rent-high   { background: rgba(50,215,75,0.18);  color: #30DB5B; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.rent-medium { background: rgba(255,159,10,0.18); color: #FFB340; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.rent-low    { background: rgba(255,69,58,0.18);  color: #FF6961; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }

/* ── Section labels ── */
.section-label {
    color: #8E8E93; font-size: 10px; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase;
    border-bottom: 1px solid #2C2C2E; padding-bottom: 6px; margin: 18px 0 10px 0;
}

/* ── Info / success / warning override ── */
div[data-testid="stAlert"] { border-radius: 12px !important; }

/* ── Dataframe ── */
.stDataFrame { border-radius: 14px !important; overflow: hidden !important; border: none !important; }
iframe[data-testid="stDataFrame"] { border-radius: 14px !important; }

/* ── Buttons ── */
.stDownloadButton > button, .stButton > button {
    background: #0A84FF !important; color: #FFFFFF !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important; letter-spacing: -0.01em !important;
    padding: 8px 18px !important;
}
.stDownloadButton > button:hover, .stButton > button:hover { background: #0070D8 !important; }

/* ── Expanders ── */
details { background: #1C1C1E !important; border-radius: 14px !important; border: 1px solid #2C2C2E !important; margin-bottom: 8px !important; }
details summary { font-weight: 500 !important; color: #FFFFFF !important; padding: 14px 18px !important; }

/* ── Progress bar ── */
.stProgress > div > div { background: #0A84FF !important; border-radius: 4px !important; }
</style>
""", unsafe_allow_html=True)

# ── Page header ──
st.markdown("""
<div style="padding: 32px 0 20px 0;">
  <div style="font-size:11px; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:#8E8E93; margin-bottom:6px;">WHOLESALE UNDERWRITER</div>
  <div style="font-size:34px; font-weight:700; letter-spacing:-0.03em; color:#FFFFFF; line-height:1.1;">Section 8 Deal Analyzer</div>
  <div style="font-size:15px; color:#8E8E93; margin-top:6px; font-weight:400;">HUD SAFMR · Multi-source rent validation · DSCR pricing · Investor metrics</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("Financing")
    interest_rate    = st.number_input("Interest Rate (%)", value=7.5, step=0.1, min_value=1.0, max_value=20.0) / 100
    down_pct         = st.slider("Down Payment (%)", 10, 50, 20) / 100
    loan_term_years  = st.selectbox("Loan Term (Years)", [30, 20, 15], index=0)
    target_cashflow  = st.number_input("Target Buyer Cashflow ($/mo)", value=400, step=50)

    st.header("Expenses")
    tax_rate         = st.number_input("Property Tax (% of value/yr)", value=1.5, step=0.1, min_value=0.0) / 100
    insurance_rate   = st.number_input("Insurance (% of value/yr)",    value=0.75, step=0.05, min_value=0.0) / 100
    vacancy_rate     = st.number_input("Vacancy (%)",                   value=5.0, step=1.0, min_value=0.0) / 100
    maintenance_rate = st.number_input("Maintenance (% of rent/mo)",   value=5.0, step=1.0, min_value=0.0) / 100
    mgmt_rate        = st.number_input("Property Mgmt (%)",            value=10.0, step=1.0, min_value=0.0,
                                       help="Section 8 requires specialized PM. Industry standard: 8–12%.") / 100
    capex_rate       = st.number_input("CapEx Reserve (% of rent/mo)", value=10.0, step=1.0, min_value=0.0,
                                       help="Capital expenditures: roof, HVAC, appliances. Industry standard: 10% of rent.") / 100
    utility_allowance= st.number_input("Utility Allowance ($/mo)",     value=100, step=25, min_value=0,
                                       help="PHA deducts this from the voucher when tenant pays utilities. Max $100 is conservative. Adjust per market.")

    st.header("Wholesale Deal")
    wholesale_fee    = st.number_input("Your Assignment Fee ($)", value=10000, step=500, min_value=0)
    closing_costs_pct= st.number_input("Closing Costs (% of purchase)", value=3.0, step=0.5, min_value=0.0) / 100

    st.header("Section 8 Settings")
    payment_standard = st.selectbox(
        "Payment Standard",
        ["100% FMR (conservative)", "110% FMR (aggressive)"],
        help="PHAs set their own payment standards between 90–110% of FMR. 100% is the safe default."
    )
    use_110 = "110%" in payment_standard
    rent_growth_rate = st.number_input("Annual Rent Growth (%)", value=3.0, step=0.5, min_value=0.0,
                                       help="HUD adjusts FMRs annually via the Annual Adjustment Factor. Historical avg: 2–4%.") / 100

    st.header("Offer Flags")
    inspect_threshold = st.number_input(
        "Flag if DSCR max exceeds List Price by (%):",
        value=15, step=5, min_value=0,
        help="When the DSCR math supports a price much higher than list, it likely needs heavy rehab."
    )

    st.header("Rentcast API (optional)")
    rentcast_key = st.text_input(
        "Rentcast API Key",
        type="password",
        help=(
            "Optional — enables auto-fetching listing descriptions AND rent estimates by address.\n\n"
            "Free tier: 50 calls/month at app.rentcast.io\n\n"
            "With a key: rent validated against market comps for higher accuracy."
        ),
    )

# ─────────────────────────────────────────────
# HUD SAFMR DATA  (zip‑code level, FY2026)
# ─────────────────────────────────────────────
SAFMR_URL = "https://www.huduser.gov/portal/datasets/fmr/fmr2026/fy2026_safmrs.xlsx"
COUNTY_FMR_URL = "https://www.huduser.gov/portal/datasets/fmr/fmr2025/fy2025_safmrs_revised.xlsx"

@st.cache_data(ttl=86400 * 7, show_spinner=False)
def load_safmr() -> pd.DataFrame:
    """Download HUD FY2026 Small Area FMR table (zip‑level). ~4 MB, cached 7 days."""
    hdrs = {"User-Agent": "Mozilla/5.0 (compatible; Section8Calc/1.0)"}
    try:
        resp = requests.get(SAFMR_URL, headers=hdrs, timeout=40)
        resp.raise_for_status()
        df = pd.read_excel(io.BytesIO(resp.content))
        # Normalize column names — the Excel has newlines in headers
        df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
        # Rename to clean names
        rename = {}
        for c in df.columns:
            cl = c.upper()
            if "ZIP" in cl:
                rename[c] = "zip"
            elif "0BR" in cl and "90" not in cl and "110" not in cl:
                rename[c] = "fmr_0br"
            elif "1BR" in cl and "90" not in cl and "110" not in cl:
                rename[c] = "fmr_1br"
            elif "2BR" in cl and "90" not in cl and "110" not in cl:
                rename[c] = "fmr_2br"
            elif "3BR" in cl and "90" not in cl and "110" not in cl:
                rename[c] = "fmr_3br"
            elif "4BR" in cl and "90" not in cl and "110" not in cl:
                rename[c] = "fmr_4br"
            elif "0BR" in cl and "110" in cl:
                rename[c] = "ps110_0br"
            elif "1BR" in cl and "110" in cl:
                rename[c] = "ps110_1br"
            elif "2BR" in cl and "110" in cl:
                rename[c] = "ps110_2br"
            elif "3BR" in cl and "110" in cl:
                rename[c] = "ps110_3br"
            elif "4BR" in cl and "110" in cl:
                rename[c] = "ps110_4br"
        df = df.rename(columns=rename)
        df["zip"] = df["zip"].astype(str).str.zfill(5)
        return df
    except Exception as e:
        st.warning(f"Could not load HUD SAFMR data: {e}. Using estimated rents.")
        return pd.DataFrame()


def get_section8_rent(zip_code: str, beds: int, safmr_df: pd.DataFrame) -> tuple[int, str]:
    """
    Look up HUD Small Area FMR for this exact zip code.
    Returns (monthly_rent, source_label).
    Falls back to a national median estimate if zip not found.
    """
    beds = max(0, min(4, int(beds)))
    br_col    = f"fmr_{beds}br"
    ps110_col = f"ps110_{beds}br"

    zip_str = str(zip_code).strip().split("-")[0].zfill(5)

    if not safmr_df.empty:
        row = safmr_df[safmr_df["zip"] == zip_str]
        if not row.empty:
            if use_110 and ps110_col in row.columns:
                val = int(row[ps110_col].iloc[0])
                return val, f"HUD SAFMR FY2026 (110% PS, zip {zip_str})"
            elif br_col in row.columns:
                val = int(row[br_col].iloc[0])
                return val, f"HUD SAFMR FY2026 (100% FMR, zip {zip_str})"

    # National median fallback by bedroom
    fallback = {0: 950, 1: 1100, 2: 1350, 3: 1650, 4: 1950}
    return fallback.get(beds, 1350), "Estimated (zip not in SAFMR dataset)"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rentcast_rent_avm(address: str, beds: int, sqft: int, api_key: str) -> int:
    """
    Call Rentcast's /v1/avm/rent/long-term endpoint to get a market rent estimate.
    Returns integer rent estimate, or 0 if unavailable.
    Uses same API key as listing description — no extra cost on free tier.
    """
    if not api_key or not api_key.strip():
        return 0
    try:
        params = {"address": address, "bedrooms": beds}
        if sqft > 0:
            params["squareFootage"] = sqft
        resp = requests.get(
            "https://api.rentcast.io/v1/avm/rent/long-term",
            params=params,
            headers={"X-Api-Key": api_key.strip(), "Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            rent = data.get("rent", 0)
            return int(rent) if rent else 0
    except Exception:
        pass
    return 0


def get_rent_consensus(
    safmr_rent: int,
    census_rent: int,
    rentcast_rent: int,
    beds: int,
    zip_str: str,
) -> tuple[int, str, str]:
    """
    Cross-reference the HUD SAFMR against market rent sources and return the
    most accurate estimate with a confidence level and reasoning.

    The rent reasonableness rule: PHAs will NOT approve a contract rent above
    comparable unassisted units in the same neighborhood — even if SAFMR is higher.
    So if market evidence consistently shows rents below SAFMR, we must flag this
    and adjust downward.

    Returns: (effective_rent, confidence_level, reasoning_note)
    """
    sources = {"SAFMR": safmr_rent}
    if census_rent > 200:
        sources["Census ACS"] = census_rent
    if rentcast_rent > 200:
        sources["Rentcast AVM"] = rentcast_rent

    if len(sources) == 1:
        # Only SAFMR available — baseline confidence
        return safmr_rent, "Medium", "HUD SAFMR only — no market comps to validate"

    market_vals = [v for k, v in sources.items() if k != "SAFMR"]
    avg_market  = sum(market_vals) / len(market_vals)
    gap_pct     = (safmr_rent - avg_market) / safmr_rent if safmr_rent > 0 else 0

    if gap_pct > 0.25:
        # Market rents are more than 25% below SAFMR — rent reasonableness will likely cap
        effective = round(avg_market / 25) * 25  # round to nearest $25
        note = (
            f"⚠ Rent reasonableness risk — SAFMR ${safmr_rent:,} is {gap_pct:.0%} above "
            f"market comps (avg ${avg_market:,.0f}). PHA may cap contract rent near market rate."
        )
        return effective, "Low", note
    elif gap_pct > 0.12:
        # Moderate gap — use SAFMR but warn
        note = (
            f"SAFMR ${safmr_rent:,} is {gap_pct:.0%} above market avg (${avg_market:,.0f}). "
            f"Verify rent reasonableness with local PHA before locking in offer."
        )
        return safmr_rent, "Medium", note
    else:
        # Sources agree — high confidence
        source_list = ", ".join(f"{k} ${v:,}" for k, v in sources.items())
        note = f"All sources agree within 12% — {source_list}"
        return safmr_rent, "High", note


# ─────────────────────────────────────────────
# CENSUS ACS — FREE ZIP-LEVEL MARKET DATA
# No API key required. Used for anomaly-based condition detection.
# ─────────────────────────────────────────────
@st.cache_data(ttl=86400 * 30, show_spinner=False)
def get_census_zip_data(zip_code: str) -> dict:
    """
    Pull ACS 5-year estimates for a ZIP code from the Census Bureau API.
    Returns dict with median_home_value, vacancy_rate, AND median rent by bedrooms.
    Completely free, no API key required.
    Variables:
      B25077_001E = Median home value ($)
      B25002_001E = Total housing units
      B25002_003E = Vacant housing units
      B25031_002E = Median rent, no bedroom (studio)
      B25031_003E = Median rent, 1 bedroom
      B25031_004E = Median rent, 2 bedrooms
      B25031_005E = Median rent, 3 bedrooms
      B25031_006E = Median rent, 4 bedrooms
    """
    zip_str = str(zip_code).strip().zfill(5)
    url = (
        "https://api.census.gov/data/2022/acs/acs5"
        "?get=B25077_001E,B25002_001E,B25002_003E,"
        "B25031_002E,B25031_003E,B25031_004E,B25031_005E,B25031_006E"
        f"&for=zip+code+tabulation+area:{zip_str}"
    )
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if len(data) >= 2:
                row = data[1]
                def safe_int(v): return int(v) if v and str(v) not in ("-666666666", "-1") else 0
                median_val   = safe_int(row[0])
                total_units  = safe_int(row[1])
                vacant_units = safe_int(row[2])
                vacancy_pct  = round((vacant_units / total_units * 100), 1) if total_units > 0 else 0
                # Median rent by bedroom: index 3=studio,4=1BR,5=2BR,6=3BR,7=4BR
                rent_by_beds = {
                    0: safe_int(row[3]),
                    1: safe_int(row[4]),
                    2: safe_int(row[5]),
                    3: safe_int(row[6]),
                    4: safe_int(row[7]),
                }
                return {
                    "median_home_value": median_val,
                    "total_units":       total_units,
                    "vacant_units":      vacant_units,
                    "vacancy_rate_pct":  vacancy_pct,
                    "median_rent_by_beds": rent_by_beds,
                }
    except Exception:
        pass
    return {}


def get_price_anomaly_signals(list_price: float, beds: int, zip_code: str) -> list[str]:
    """
    Use free Census ACS data to detect distress signals from price alone.
    Returns list of flag strings. Empty list = no anomalies.
    """
    signals = []
    census = get_census_zip_data(zip_code)
    if not census or census.get("median_home_value", 0) == 0:
        return signals

    med = census["median_home_value"]
    vacancy = census["vacancy_rate_pct"]

    # Signal 1: List price drastically below zip median → likely distressed
    ratio = list_price / med if med > 0 else 1
    if ratio < 0.30:
        signals.append(
            f"Price {ratio*100:.0f}% of zip median (${med:,.0f}) — severely below market, likely major rehab needed"
        )
    elif ratio < 0.50:
        signals.append(
            f"Price {ratio*100:.0f}% of zip median (${med:,.0f}) — well below market, possible distress"
        )

    # Signal 2: High vacancy rate in the zip
    if vacancy >= 20:
        signals.append(
            f"ZIP has {vacancy:.1f}% vacancy rate — high distress area, verify rental demand"
        )
    elif vacancy >= 12:
        signals.append(
            f"ZIP has {vacancy:.1f}% vacancy rate — above average, check Section 8 demand"
        )

    return signals


# ─────────────────────────────────────────────
# ZILLOW SEARCH API  — FREE, no bot detection
#
# Zillow's async-create-search-page-state PUT endpoint returns
# full search results JSON from any IP with no PerimeterX challenge.
# Returns: flexFieldText (agent snippet), daysOnZillow, priceReduction,
#          taxAssessedValue, beds/baths/sqft, detailUrl, zpid.
#
# NOTE: The individual homedetails page (which has full description) IS
# blocked by PerimeterX JS challenge — only the search results are accessible.
# We use what we can get: flexFieldText + listing signals for condition detection.
# ─────────────────────────────────────────────

def _geocode_city_bbox(address: str) -> dict | None:
    """
    Use Nominatim (OpenStreetMap) to get lat/lng for the address,
    then build a small bounding box for the Zillow search.
    Returns {"north","south","east","west"} or None.
    Free, no key needed.
    """
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "Section8Calc/1.0 (wholesale underwriter)"},
            timeout=8,
        )
        if r.status_code == 200 and r.json():
            hit = r.json()[0]
            lat = float(hit["lat"])
            lng = float(hit["lon"])
            delta = 0.03   # ~3 km radius
            return {"north": lat + delta, "south": lat - delta,
                    "east":  lng + delta, "west":  lng - delta,
                    "lat": lat, "lng": lng}
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def _zillow_search_area(north: float, south: float, east: float, west: float) -> list:
    """
    Call Zillow's async-create-search-page-state PUT endpoint.
    Returns list of raw listing dicts. Cached 1 hour per bounding box.
    This endpoint has NO bot detection — returns 200 from any IP.
    """
    if not _CURL_CFFI_AVAILABLE:
        try:
            resp = requests.put(
                "https://www.zillow.com/async-create-search-page-state",
                json={
                    "searchQueryState": {
                        "pagination": {},
                        "isMapVisible": True,
                        "mapBounds": {"north": north, "south": south,
                                      "east": east, "west": west},
                        "isListVisible": True,
                    },
                    "wants": {"cat1": ["listResults"]},
                    "requestId": 2,
                    "isDebugRequest": False,
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Referer": "https://www.zillow.com/",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                return (data.get("cat1", {})
                            .get("searchResults", {})
                            .get("listResults", []))
        except Exception:
            pass
        return []

    # Use curl_cffi for better TLS impersonation
    try:
        r = cf_requests.put(
            "https://www.zillow.com/async-create-search-page-state",
            json={
                "searchQueryState": {
                    "pagination": {},
                    "isMapVisible": True,
                    "mapBounds": {"north": north, "south": south,
                                  "east": east, "west": west},
                    "isListVisible": True,
                },
                "wants": {"cat1": ["listResults"]},
                "requestId": 2,
                "isDebugRequest": False,
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Referer": "https://www.zillow.com/",
            },
            impersonate="chrome131",
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return (data.get("cat1", {})
                        .get("searchResults", {})
                        .get("listResults", []))
    except Exception:
        pass
    return []


def fetch_zillow_listing_signals(address: str) -> dict:
    """
    Look up a property on Zillow via the free search API.
    Matches by street number + street name from the address string.
    Returns dict with: flex_text, days_on_market, price_reduction,
                       tax_assessed_value, beds, baths, sqft, zpid, detail_url.
    Returns {} if not found.
    """
    # Parse address components
    parts = address.strip().split(",")
    street_part = parts[0].strip() if parts else address
    # Extract street number (first token)
    tokens = street_part.split()
    if not tokens:
        return {}
    street_num = tokens[0]
    # Street name (next 1-2 tokens, lowercased for fuzzy match)
    street_name = " ".join(tokens[1:3]).lower() if len(tokens) > 1 else ""

    # Geocode the address to get bounding box
    bbox = _geocode_city_bbox(address)
    if not bbox:
        return {}

    # Search Zillow in that bounding box
    listings = _zillow_search_area(
        north=bbox["north"], south=bbox["south"],
        east=bbox["east"],  west=bbox["west"],
    )

    if not listings:
        return {}

    # Find the matching listing
    for listing in listings:
        addr_street = listing.get("addressStreet", "")
        # Match by street number and partial street name
        if street_num in addr_street and street_name.split()[0] in addr_street.lower():
            hdi = listing.get("hdpData", {}).get("homeInfo", {})
            return {
                "flex_text":          listing.get("flexFieldText", ""),
                "content_type":       listing.get("contentType", ""),
                "days_on_market":     hdi.get("daysOnZillow", 0),
                "price_reduction":    listing.get("priceReduction", ""),
                "price_change":       hdi.get("priceChange", 0),
                "tax_assessed_value": hdi.get("taxAssessedValue", 0),
                "beds":               hdi.get("bedrooms", 0),
                "baths":              hdi.get("bathrooms", 0),
                "sqft":               hdi.get("livingArea", 0),
                "zpid":               hdi.get("zpid", ""),
                "detail_url":         listing.get("detailUrl", ""),
                "broker":             listing.get("brokerName", ""),
                "home_type":          hdi.get("homeType", ""),
                "is_non_owner":       hdi.get("isNonOwnerOccupied", False),
                "status":             listing.get("statusText", ""),
            }
    return {}


# ─────────────────────────────────────────────
# DISTRESS KEYWORDS
# ─────────────────────────────────────────────
CRITICAL_KW = [
    "fire damage","fire-damaged","burned","condemned","structural issue",
    "foundation problem","black mold","severe water damage","gutted","down to studs",
    "unsafe","tear down","land value only","total rehab","gut rehab","uninhabitable",
    "major foundation","collapsed","cave-in",
]
MODERATE_KW = [
    "tlc","handyman","investor special","as-is","as is","needs work",
    "fixer","fixer-upper","fixer upper","contractor special","bring your ideas",
    "blank canvas","rehab","cash only","sold as is","needs updating",
    "some updates needed","great bones","needs repairs","priced to sell",
    "motivated seller","below market","quick sale","diamond in the rough",
]

def analyze_condition(text: str) -> tuple[str, list]:
    """Returns (condition_label, [matched_keywords])"""
    if not text or len(text.strip()) < 10:
        return "Unknown", []
    t = text.lower()
    crits = [kw for kw in CRITICAL_KW if kw in t]
    mods  = [kw for kw in MODERATE_KW if kw in t]
    if crits:
        return "Critical",   crits + mods
    if mods:
        return "Needs Work",  mods
    return "Good", []


def analyze_zillow_signals(zs: dict) -> tuple[str, list[str]]:
    """
    Analyze Zillow search listing signals (free data).
    Returns (condition_label_or_empty, [signal_strings]).
    condition is only set if clear distress signals found.
    """
    if not zs:
        return "", []

    signals = []
    condition = ""

    # 1. flexFieldText — agent-written one-liner (homeInsight type)
    flex = zs.get("flex_text", "")
    ctype = zs.get("content_type", "")
    if flex and ctype == "homeInsight":
        # Run keyword analysis on the snippet
        cond_from_flex, kws = analyze_condition(flex)
        if cond_from_flex in ("Critical", "Needs Work"):
            condition = cond_from_flex
            signals.append(f"Zillow insight: \"{flex}\" → {', '.join(kws[:3])}")
        elif flex.strip():
            signals.append(f"Zillow insight: \"{flex}\"")

    # 2. Price cut signal
    price_change = zs.get("price_change", 0) or 0
    price_reduction_str = zs.get("price_reduction", "")
    if price_change < -5000:
        signals.append(f"Price reduced {price_reduction_str} — motivated seller signal")
        if not condition:
            condition = "Needs Work"

    # 3. Days on market (stale listing = distress signal)
    dom = zs.get("days_on_market", 0) or 0
    if dom >= 90:
        signals.append(f"On market {dom} days — long DOM, likely overpriced or has issues")
        if not condition:
            condition = "Needs Work"
    elif dom >= 45:
        signals.append(f"On market {dom} days")

    # 4. Tax assessed value vs list price
    tax_val = zs.get("tax_assessed_value", 0) or 0
    # (list_price not available here; caller will cross-reference)

    return condition, signals


# ─────────────────────────────────────────────
# LISTING DESCRIPTION — RENTCAST API
#
# We tested every free scraping approach (Zillow, Redfin, Realtor.com,
# Google, Bing, DuckDuckGo) — all return 200 but serve bot-detection pages
# or 403/429 errors. There is no reliable free scraping path in 2025/2026.
#
# RENTCAST is the only clean, affordable solution:
#   - Free tier: 50 calls/month (app.rentcast.io)
#   - Returns full listing details including public remarks/description
#   - Without a key: user must include 'Description' column in their CSV
# ─────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rentcast_listing(address: str, api_key: str) -> dict:
    """
    Call Rentcast's /v1/listings/sale endpoint to get active listing data.
    Returns dict with 'description', 'beds', 'baths', 'sqft', etc.
    """
    if not api_key or not api_key.strip():
        return {}
    try:
        resp = requests.get(
            "https://api.rentcast.io/v1/listings/sale",
            params={"address": address, "limit": 1, "status": "Active"},
            headers={"X-Api-Key": api_key.strip(), "Accept": "application/json"},
            timeout=12,
        )
        if resp.status_code == 200:
            data = resp.json()
            listings = data if isinstance(data, list) else data.get("listings", [])
            if listings:
                listing = listings[0]
                # Rentcast returns remarks in multiple possible fields
                desc = (
                    listing.get("description", "")
                    or listing.get("publicRemarks", "")
                    or listing.get("remarks", "")
                    or listing.get("listingDescription", "")
                )
                return {
                    "description": desc,
                    "beds":  listing.get("bedrooms", ""),
                    "baths": listing.get("bathrooms", ""),
                    "sqft":  listing.get("squareFootage", ""),
                    "year_built": listing.get("yearBuilt", ""),
                    "source": "Rentcast API",
                }
        elif resp.status_code == 401:
            st.warning("⚠️ Rentcast API key is invalid. Check your key at app.rentcast.io")
        elif resp.status_code == 429:
            st.warning("⚠️ Rentcast API rate limit reached. Upgrade plan or wait for reset.")
    except Exception:
        pass
    return {}


def get_listing_description(address: str, api_key: str = "") -> tuple[str, str]:
    """
    Fetch listing description.
    If Rentcast API key provided → use it.
    Otherwise → return empty (user must include Description in CSV).
    Returns (description, source_label).
    """
    if not address or not address.strip():
        return "", "No address"

    if api_key and api_key.strip():
        result = fetch_rentcast_listing(address, api_key)
        desc = result.get("description", "")
        if desc:
            return desc, "Rentcast API"
        # Rentcast found the property but no description field
        return "", "Rentcast API (no description returned)"

    # No API key — user must supply description in CSV
    return "", "No API key — add Description column to CSV"


# ─────────────────────────────────────────────
# ESTIMATED REPAIRS
# Based on condition label + sqft (if known).
# These are rough wholesale ranges, not contractor bids.
# ─────────────────────────────────────────────
def estimate_repairs(condition: str, sqft: float = 0, list_price: float = 0) -> tuple[int, int, str]:
    """
    Returns (low_estimate, high_estimate, repair_tier_label).
    Estimates are per-sqft ranges based on condition tier.
    If sqft unknown, uses list_price-based heuristic fallback.
    """
    # Per-sqft repair cost ranges by condition
    # Source: typical wholesale/rehab industry ranges
    tiers = {
        "Good":             (0,    5,    "Light / Cosmetic"),
        "Needs Work":       (10,   30,   "Moderate Rehab"),
        "Critical":         (35,   65,   "Heavy / Full Rehab"),
        "Likely Distressed":(25,   55,   "Probable Major Rehab"),
        "Possibly Distressed":(8,  25,   "Unknown — Inspect"),
        "Unknown":          (5,    20,   "Unknown — Inspect"),
    }
    low_psf, high_psf, label = tiers.get(condition, (5, 20, "Unknown — Inspect"))

    if sqft > 0:
        low  = round(low_psf  * sqft / 1000) * 1000   # round to nearest $1k
        high = round(high_psf * sqft / 1000) * 1000
    elif list_price > 0:
        # Fallback: use % of list price when sqft unknown
        fallback_pcts = {
            "Good":               (0.00, 0.03),
            "Needs Work":         (0.05, 0.15),
            "Critical":           (0.20, 0.40),
            "Likely Distressed":  (0.15, 0.30),
            "Possibly Distressed":(0.05, 0.15),
            "Unknown":            (0.03, 0.10),
        }
        lo_pct, hi_pct = fallback_pcts.get(condition, (0.03, 0.10))
        low  = round(list_price * lo_pct / 1000) * 1000
        high = round(list_price * hi_pct / 1000) * 1000
    else:
        low, high = 0, 0

    return low, high, label


# ─────────────────────────────────────────────
# DSCR OFFER CALCULATOR
# ─────────────────────────────────────────────
def calculate_dscr_offer(
    s8_rent: float,
    tax_r: float,
    ins_r: float,
    vac_r: float,
    maint_r: float,
    mgmt_r: float,
    capex_r: float,
    utility_allowance: float,
    interest: float,
    term_yrs: int,
    down_pct: float,
    target_cf: float,
    closing_pct: float,
    fee: float,
    list_price: float,
    repair_mid: float = 0,
) -> dict:
    """
    Solve for the MAX BUYER PRICE where the deal cashflows >= target_cf/mo.

    Expense model (in order of how they reduce cashflow):
      1. Utility allowance — PHA deducts this from voucher; landlord receives less
      2. Vacancy — units aren't always rented
      3. Maintenance + Property Mgmt — % of effective (post-utility) rent
      4. CapEx reserve — % of gross rent set aside for capital expenditures
      5. Taxes, Insurance — % of purchase price
      6. Mortgage — payment on loan amount

    KEY RULE: Max Buyer Price ALWAYS capped at list_price.
    Returns full dict with DSCR ratio, CoC, RTV, GRM, break-even rent, 5-yr projection.
    """
    if s8_rent <= 0 or list_price <= 0:
        return {"viable": False}

    # Effective rent = what landlord actually receives after utility allowance deduction
    eff_rent = max(0, s8_rent - utility_allowance)
    egi      = eff_rent * (1 - vac_r)           # after vacancy
    var_exp  = eff_rent * (maint_r + mgmt_r)     # maintenance + mgmt on effective rent
    capex_mo = s8_rent  * capex_r               # CapEx on gross rent (set-aside regardless of vacancy)

    mo_rate = interest / 12
    n       = term_yrs * 12
    if mo_rate > 0:
        mort_factor = (mo_rate * (1 + mo_rate) ** n) / ((1 + mo_rate) ** n - 1)
    else:
        mort_factor = 1 / n

    # Solve for P (max buyer price):
    # egi - var_exp - capex_mo - (tax/12)*P - (ins/12)*P - mort_factor*(1-down)*P = target_cf
    coeff = (tax_r / 12) + (ins_r / 12) + mort_factor * (1 - down_pct)
    num   = egi - var_exp - capex_mo - target_cf

    if num <= 0 or coeff <= 0:
        return {"viable": False}

    dscr_max        = num / coeff
    max_buyer_price = min(dscr_max, list_price)

    # Recalculate actuals at capped buyer price
    loan        = max_buyer_price * (1 - down_pct)
    mort_pmt    = npf.pmt(mo_rate, n, -loan) if mo_rate > 0 else loan / n
    taxes_mo    = (max_buyer_price * tax_r) / 12
    ins_mo      = (max_buyer_price * ins_r) / 12
    actual_cf   = egi - var_exp - capex_mo - taxes_mo - ins_mo - mort_pmt

    # DSCR ratio — NOI / Debt Service (lenders want ≥ 1.15 for Section 8)
    noi         = egi - var_exp - capex_mo - taxes_mo - ins_mo
    dscr_ratio  = round(noi / mort_pmt, 2) if mort_pmt > 0 else 0

    # Your wholesale offer to seller
    if closing_pct < 1:
        your_offer_gross = max_buyer_price - fee
        your_offer       = your_offer_gross / (1 + closing_pct)
        closing_amt      = your_offer * closing_pct
    else:
        return {"viable": False}

    # ── Investor metrics ──
    down_payment = max_buyer_price * down_pct
    # Rent-to-Value: monthly rent / purchase price × 100 (target ≥ 0.8%)
    rtv_pct = (s8_rent / max_buyer_price * 100) if max_buyer_price > 0 else 0
    # GRM: price / annual rent (target ≤ 9)
    grm = max_buyer_price / (s8_rent * 12) if s8_rent > 0 else 0
    # Cash-on-Cash: annual CF / total cash invested (down + closing + repairs)
    total_cash_invested = down_payment + closing_amt + repair_mid
    annual_cf = actual_cf * 12
    coc_pct   = (annual_cf / total_cash_invested * 100) if total_cash_invested > 0 else 0

    # Break-even rent (minimum S8 rent to hit $0 cashflow at this buyer price)
    # (R - U)*(1-vac)*((1-(maint+mgmt)) - R*capex = taxes + ins + mort
    # Let A = (1-vac_r)*(1 - maint_r - mgmt_r)
    A = (1 - vac_r) * (1 - maint_r - mgmt_r)
    fixed_mo = taxes_mo + ins_mo + mort_pmt
    # R*A - U*A - R*capex_r = fixed_mo  →  R*(A - capex_r) = fixed_mo + U*A
    be_denom = A - capex_r
    break_even_rent = round((fixed_mo + utility_allowance * A) / be_denom) if be_denom > 0 else 0

    dscr_headroom = max(0, dscr_max - list_price)

    return {
        "viable":             your_offer > 0,
        "dscr_max_price":     round(dscr_max, 2),
        "max_buyer_price":    round(max_buyer_price, 2),
        "s8_rent":            s8_rent,
        "eff_rent":           round(eff_rent, 2),
        "egi":                round(egi, 2),
        "var_expenses":       round(var_exp, 2),
        "capex_mo":           round(capex_mo, 2),
        "taxes_mo":           round(taxes_mo, 2),
        "insurance_mo":       round(ins_mo, 2),
        "mortgage_pmt":       round(mort_pmt, 2),
        "actual_cf":          round(actual_cf, 2),
        "loan_amount":        round(loan, 2),
        "down_payment":       round(down_payment, 2),
        "closing_costs":      round(closing_amt, 2),
        "wholesale_fee":      fee,
        "your_offer":         round(your_offer, 2),
        "dscr_headroom":      round(dscr_headroom, 2),
        # New investor metrics
        "dscr_ratio":         dscr_ratio,
        "rtv_pct":            round(rtv_pct, 2),
        "grm":                round(grm, 2),
        "coc_pct":            round(coc_pct, 1),
        "total_cash_invested":round(total_cash_invested, 2),
        "break_even_rent":    break_even_rent,
        "annual_cf":          round(annual_cf, 2),
        "noi":                round(noi, 2),
    }


# ─────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────
st.markdown("---")
col_up, col_info = st.columns([2, 1])

with col_up:
    uploaded = st.file_uploader("Upload Property CSV / Excel", type=["csv", "xlsx"])
    st.caption(
        "**Required:** `Address` (or `Street` + `City` + `State`) · `Zip` · `Bedrooms` · `List Price`  |  "
        "**Optional:** `Sqft` · `Agent Name` · `Agent Email` · `Description`"
    )

with col_info:
    st.info(
        "**How it works**\n"
        "1. Pulls HUD FY2026 **Small Area FMR** — real zip-level rents\n"
        "2. Gets listing description via **Rentcast API** or your CSV column\n"
        "3. DSCR math → max buyer price (≤ list − $10k) → your net offer\n"
        "4. Flags distressed listings & inspection-needed deals\n"
        "5. Export all deals or good-only filtered CSV"
    )
    st.info(
        "**Property Condition Detection — 4 layers:**\n\n"
        "1. ✅ **Free auto:** Zillow listing signals (agent insight, days on market, "
        "price reductions) via Zillow's public search API — no key needed\n\n"
        "2. ✅ **Free always:** Census ACS median home value + vacancy rate by ZIP "
        "— flags properties priced far below zip median as likely distressed\n\n"
        "3. ✅ **Free if you export from MLS/PropStream:** Add a `Description` column "
        "to your CSV — app reads it directly for keyword analysis\n\n"
        "4. 🔑 **Rentcast API** (optional, 50 free calls/mo) — auto-fetches listing "
        "description by address without needing a CSV column",
        icon="ℹ️"
    )

# Sample CSV — shows split address format with agent info and sqft
sample = pd.DataFrame({
    "Street":      ["3820 Guilford Ave", "456 Oak Ave"],
    "City":        ["Indianapolis", "Indianapolis"],
    "State":       ["IN", "IN"],
    "Zip":         [46205, 46218],
    "Bedrooms":    [3, 4],
    "Sqft":        [1250, 1600],
    "List Price":  [95000, 120000],
    "Agent Name":  ["Jane Smith", "Bob Johnson"],
    "Agent Email": ["jane@realty.com", "bob@realty.com"],
    "Agent Phone": ["317-555-0101", "317-555-0202"],
    "Description": ["", ""],
})
st.download_button("⬇️ Download Sample CSV", sample.to_csv(index=False).encode(),
                   "sample_properties.csv", "text/csv")

# ── Load SAFMR once ──
with st.spinner("Loading HUD SAFMR rent data (one-time, cached 7 days)…"):
    safmr_df = load_safmr()

if not safmr_df.empty:
    st.success(f"✅ HUD SAFMR loaded — {len(safmr_df):,} zip codes with zip-level Section 8 rents")
else:
    st.warning("⚠️ Could not load HUD SAFMR. Using national estimates.")

# ── Process uploaded file ──
if uploaded:
    raw = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    raw.columns = [c.strip() for c in raw.columns]

    # Flexible column mapping
    col_map = {}
    for c in raw.columns:
        cl = c.lower().replace(" ", "").replace("_", "")
        if cl in ("address","addr","streetaddress","propertyaddress","street","streetaddr"):
            col_map[c] = "Street"
        elif cl in ("city","cityname"):                                   col_map[c] = "City"
        elif cl in ("state","st","statecode"):                            col_map[c] = "State"
        elif cl in ("zip","zipcode","zip_code","postalcode","postal"):    col_map[c] = "Zip"
        elif cl in ("bedrooms","beds","bed","br","bdrms","bdrm"):         col_map[c] = "Bedrooms"
        elif cl in ("listprice","price","mlsamount","askingprice",
                    "listingprice","amount","saleprice","list"):           col_map[c] = "List Price"
        elif cl in ("description","desc","remarks","publicremarks",
                    "notes","listingremarks","agentremarks"):              col_map[c] = "Description"
        elif cl in ("sqft","squarefeet","squarefootage","livingarea",
                    "livingsqft","sf","size"):                             col_map[c] = "Sqft"
        elif cl in ("agentname","agent","agentfirstname","listingagent",
                    "realtorname","brokeragent"):                          col_map[c] = "Agent Name"
        elif cl in ("agentemail","email","agentcontact",
                    "realtoremail","brokeragemail"):                       col_map[c] = "Agent Email"
        elif cl in ("agentphone","phone","agentcell","agentmobile",
                    "realtorphone","brokerphone","phonenumber","cell"):    col_map[c] = "Agent Phone"
    raw = raw.rename(columns=col_map)

    # ── Build full Address from split columns if needed ──
    # If the CSV has Street + City + State + Zip as separate columns, combine them.
    # If the CSV already has a combined "Street" (or "Address") column with city/state
    # embedded (e.g. "123 Main St, Orlando, FL 32801"), that works too.
    if "Street" in raw.columns and "Address" not in raw.columns:
        city_part  = raw["City"].astype(str).str.strip()  if "City"  in raw.columns else ""
        state_part = raw["State"].astype(str).str.strip() if "State" in raw.columns else ""
        zip_part   = raw["Zip"].astype(str).str.strip()   if "Zip"   in raw.columns else ""
        # Build: "123 Main St, Orlando, FL 32801"
        raw["Address"] = (
            raw["Street"].astype(str).str.strip()
            + raw.apply(lambda r: f", {r['City']}"  if "City"  in raw.columns and str(r.get("City","")).strip()  else "", axis=1)
            + raw.apply(lambda r: f", {r['State']}" if "State" in raw.columns and str(r.get("State","")).strip() else "", axis=1)
            + raw.apply(lambda r: f" {r['Zip']}"    if "Zip"   in raw.columns and str(r.get("Zip","")).strip()   else "", axis=1)
        )
    elif "Street" in raw.columns:
        # "Street" is really the full address
        raw = raw.rename(columns={"Street": "Address"})

    # If Zip wasn't its own column but was embedded in Address, try to extract it
    if "Zip" not in raw.columns and "Address" in raw.columns:
        zip_extracted = raw["Address"].str.extract(r'(\d{5})(?:-\d{4})?$')[0]
        raw["Zip"] = zip_extracted.fillna("00000")

    missing_req = [r for r in ["Address","Zip","Bedrooms","List Price"] if r not in raw.columns]
    if missing_req:
        st.error(f"Missing columns: {', '.join(missing_req)}")
        st.stop()

    for col in ["List Price","Bedrooms","Zip"]:
        raw[col] = raw[col].astype(str).str.replace(r"[$,]","",regex=True)
        raw[col] = pd.to_numeric(raw[col], errors="coerce").fillna(0)

    if "Sqft" in raw.columns:
        raw["Sqft"] = raw["Sqft"].astype(str).str.replace(r"[$,]","",regex=True)
        raw["Sqft"] = pd.to_numeric(raw["Sqft"], errors="coerce").fillna(0)

    # ── Filter sub-$20k ──
    below_20k = raw[raw["List Price"] < 20000]
    raw = raw[raw["List Price"] >= 20000].reset_index(drop=True)

    if len(below_20k):
        st.warning(f"⚠️ Skipped {len(below_20k)} properties listed under $20,000 (not analyzed).")

    if raw.empty:
        st.error("No valid properties remaining after filtering.")
        st.stop()

    st.success(f"Loaded **{len(raw)}** properties. Running analysis…")

    # ── Enrichment loop ──
    progress = st.progress(0, text="Starting…")
    rows_out = []

    for i, row in raw.iterrows():
        n_done = i + 1
        addr = str(row.get("Address", "")).strip()
        progress.progress(int(n_done / len(raw) * 100),
                          text=f"({n_done}/{len(raw)}) {addr[:55]}…")

        zip_str = str(int(row["Zip"])).zfill(5)
        beds    = int(row["Bedrooms"]) if row["Bedrooms"] > 0 else 3

        # Pass-through fields (agent info, sqft from CSV or Zillow)
        agent_name  = str(row.get("Agent Name",  "")).strip() if "Agent Name"  in raw.columns else ""
        agent_email = str(row.get("Agent Email", "")).strip() if "Agent Email" in raw.columns else ""
        agent_phone = str(row.get("Agent Phone", "")).strip() if "Agent Phone" in raw.columns else ""
        csv_sqft    = float(row["Sqft"]) if "Sqft" in raw.columns and row["Sqft"] > 0 else 0

        # 1. Section 8 rent — HUD SAFMR (primary)
        s8_rent_safmr, rent_src_base = get_section8_rent(zip_str, beds, safmr_df)

        # 1a. Sqft adjustment to Section 8 rent
        sqft_note = ""
        s8_rent   = s8_rent_safmr
        rent_src  = rent_src_base
        if csv_sqft > 0:
            hud_sqft_standard = {0: 600, 1: 750, 2: 900, 3: 1100, 4: 1300}
            standard  = hud_sqft_standard.get(min(beds, 4), 900)
            sqft_ratio = csv_sqft / standard if standard > 0 else 1.0
            if sqft_ratio < 0.70:
                adj_pct  = -0.08
                sqft_note = f"Sqft {csv_sqft:.0f} is {(1-sqft_ratio)*100:.0f}% below HUD standard ({standard} sqft) — rent adjusted -8%"
            elif sqft_ratio < 0.85:
                adj_pct  = -0.04
                sqft_note = f"Sqft {csv_sqft:.0f} slightly below HUD standard ({standard} sqft) — rent adjusted -4%"
            elif sqft_ratio > 1.40:
                adj_pct  = 0.07
                sqft_note = f"Sqft {csv_sqft:.0f} well above HUD standard ({standard} sqft) — rent adjusted +7%"
            elif sqft_ratio > 1.20:
                adj_pct  = 0.04
                sqft_note = f"Sqft {csv_sqft:.0f} above HUD standard ({standard} sqft) — rent adjusted +4%"
            else:
                adj_pct  = 0.0
            if adj_pct != 0.0:
                s8_rent  = round(s8_rent_safmr * (1 + adj_pct))
                rent_src = rent_src_base + f" (sqft adj {adj_pct:+.0%})"

        # 1b. Zillow listing signals (free — no API key, no bot detection)
        zillow_signals = fetch_zillow_listing_signals(addr)
        zil_condition, zil_signal_strs = analyze_zillow_signals(zillow_signals)
        sqft = csv_sqft if csv_sqft > 0 else (zillow_signals.get("sqft") or 0)

        # 1c. Census rent by bedrooms + Rentcast AVM — validate SAFMR
        census_data   = get_census_zip_data(zip_str)
        census_rent   = (census_data.get("median_rent_by_beds") or {}).get(min(beds, 4), 0)
        rentcast_rent = fetch_rentcast_rent_avm(addr, beds, int(sqft), rentcast_key)

        # 1d. Rent consensus — cross-reference all sources, flag reasonableness risk
        s8_rent_final, rent_confidence, rent_note = get_rent_consensus(
            safmr_rent=s8_rent,
            census_rent=census_rent,
            rentcast_rent=rentcast_rent,
            beds=beds,
            zip_str=zip_str,
        )
        s8_rent = s8_rent_final  # use the validated rent for all calculations

        # 2. Description — CSV first, then Rentcast API
        has_csv_desc = (
            "Description" in raw.columns
            and pd.notnull(row.get("Description"))
            and len(str(row.get("Description","")).strip()) > 10
        )
        if has_csv_desc:
            description = str(row["Description"]).strip()
            desc_src    = "CSV"
        else:
            description, desc_src = get_listing_description(addr, rentcast_key)
            time.sleep(0.3)

        # 3. Condition analysis
        condition, kw_hits = analyze_condition(description)

        list_price = float(row["List Price"])

        # 4. Estimated repairs (needed before DSCR calc for CoC)
        repair_low, repair_high, repair_tier = estimate_repairs(condition, sqft, list_price)
        repair_mid_val = (repair_low + repair_high) / 2
        repair_range_str = f"${repair_low:,.0f} – ${repair_high:,.0f}" if (repair_low or repair_high) else "Unknown"

        # 5. DSCR offer — uses all expense inputs including CapEx and utility allowance
        calc = calculate_dscr_offer(
            s8_rent=s8_rent,
            tax_r=tax_rate, ins_r=insurance_rate,
            vac_r=vacancy_rate, maint_r=maintenance_rate, mgmt_r=mgmt_rate,
            capex_r=capex_rate, utility_allowance=utility_allowance,
            interest=interest_rate, term_yrs=loan_term_years,
            down_pct=down_pct, target_cf=target_cashflow,
            closing_pct=closing_costs_pct, fee=wholesale_fee,
            list_price=list_price,
            repair_mid=repair_mid_val,
        )

        # 6. Enforce minimum $10k below list for buyer price
        if calc.get("viable"):
            buyer_price = calc["max_buyer_price"]
            if buyer_price > list_price - 10000:
                calc["max_buyer_price"] = list_price - 10000
                your_offer_gross = calc["max_buyer_price"] - wholesale_fee
                calc["your_offer"]    = round(your_offer_gross / (1 + closing_costs_pct), 2)
                calc["closing_costs"] = round(calc["your_offer"] * closing_costs_pct, 2)
                calc["down_payment"]  = round(calc["max_buyer_price"] * down_pct, 2)
                calc["loan_amount"]   = round(calc["max_buyer_price"] * (1 - down_pct), 2)
                if calc["your_offer"] <= 0:
                    calc["viable"] = False

        # 7. Census price anomaly detection
        price_signals = get_price_anomaly_signals(list_price, beds, zip_str)

        # Merge condition from all sources (description > Zillow signals > Census price anomaly)
        if condition == "Unknown":
            # Try Zillow listing signals first (most specific)
            if zil_condition in ("Critical", "Needs Work"):
                condition = zil_condition
            elif price_signals:
                # Fall back to Census price anomaly detection
                if any("severely" in s or "major rehab" in s for s in price_signals):
                    condition = "Likely Distressed"
                else:
                    condition = "Possibly Distressed"
            elif zil_condition:
                condition = zil_condition

        # 8. Build flags
        flags = []
        if condition == "Critical":
            flags.append("CRITICAL DISTRESS — inspect before offering")
        elif condition in ("Needs Work", "Likely Distressed"):
            reason = f"keywords: {', '.join(kw_hits[:3])}" if kw_hits else "price severely below zip median"
            flags.append(f"Rehab likely — {reason}")
        elif condition == "Possibly Distressed":
            flags.append("Price anomaly — well below zip median, verify condition")

        for sig in price_signals:
            if sig not in " | ".join(flags):
                flags.append(sig)
        for sig in zil_signal_strs:
            if sig not in " | ".join(flags):
                flags.append(sig)

        if calc.get("viable"):
            headroom = calc.get("dscr_headroom", 0)
            if headroom >= list_price * (inspect_threshold / 100):
                flags.append(
                    f"INSPECT — DSCR supports ${calc['dscr_max_price']:,.0f} "
                    f"(${headroom:,.0f} above list) — likely needs heavy rehab, verify condition"
                )
            # DSCR lender ratio warning
            if calc.get("dscr_ratio", 0) > 0 and calc["dscr_ratio"] < 1.15:
                flags.append(
                    f"DSCR {calc['dscr_ratio']:.2f}x — below lender minimum 1.15x for Section 8 loans"
                )
            # Rent-to-Value flag
            rtv = calc.get("rtv_pct", 0)
            if rtv > 0 and rtv < 0.7:
                flags.append(
                    f"Low rent-to-value {rtv:.2f}% — Section 8 investors target ≥ 0.8%"
                )

        # Rent confidence flag
        if rent_confidence == "Low":
            flags.append(rent_note)
        elif rent_confidence == "Medium" and "risk" in rent_note.lower():
            flags.append(rent_note)

        # HQS fail risk flag
        if condition in ("Critical", "Needs Work", "Likely Distressed"):
            flags.append(
                f"High HQS inspection risk — Section 8 inspections fail 20–40% of the time "
                f"for properties in '{condition}' condition. Budget for re-inspection and remediation."
            )

        flag_str = " | ".join(flags)

        # Deal quality — RTV < 0.6% forces No Deal
        rtv = calc.get("rtv_pct", 0)
        if not calc.get("viable") or rtv > 0 and rtv < 0.6:
            quality = "No Deal"
        elif condition in ("Critical", "Likely Distressed") or "CRITICAL" in flag_str:
            quality = "Inspect First"
        elif flags:
            quality = "Caution"
        else:
            quality = "Green Light"

        # Sqft note for export
        if not sqft_note and sqft > 0:
            sqft_note = f"{sqft:.0f} sqft"

        # 5-year rent projection (for export and expander)
        proj_5yr = []
        _r = s8_rent
        for yr in range(1, 6):
            _eff  = max(0, _r - utility_allowance)
            _egi  = _eff * (1 - vacancy_rate)
            _vexp = _eff * (maintenance_rate + mgmt_rate)
            _capx = _r * capex_rate
            _fixed = (calc.get("taxes_mo", 0) * (1.02 ** (yr - 1))
                    + calc.get("insurance_mo", 0) * (1.02 ** (yr - 1))
                    + calc.get("mortgage_pmt", 0))
            _cf   = _egi - _vexp - _capx - _fixed
            proj_5yr.append({"year": yr, "rent": round(_r), "cf": round(_cf)})
            _r = round(_r * (1 + rent_growth_rate))

        rows_out.append({
            # ── Identifiers ──
            "Quality":               quality,
            "Address":               addr,
            "Zip":                   zip_str,
            "Beds":                  beds,
            "Sqft":                  int(sqft) if sqft else "",
            "Agent Name":            agent_name,
            "Agent Email":           agent_email,
            "Agent Phone":           agent_phone,

            # ── Section 8 Rent ──
            "Section 8 Rent ($/mo)": s8_rent,
            "Rent Confidence":       rent_confidence,
            "Rent Note":             rent_note,
            "SAFMR Rent":            s8_rent_safmr,
            "Census Rent":           census_rent if census_rent > 0 else "",
            "Rentcast AVM Rent":     rentcast_rent if rentcast_rent > 0 else "",
            "Rent Source":           rent_src,
            "Sqft Rent Note":        sqft_note,
            "Utility Allowance":     utility_allowance,
            "Effective Rent":        calc.get("eff_rent", s8_rent - utility_allowance),

            # ── Wholesale Offer Stack ──
            "List Price":            list_price,
            "Your Max Offer":        calc.get("your_offer", 0),
            "Buyer Max Purchase":    calc.get("max_buyer_price", 0),
            "DSCR Max (uncapped)":   calc.get("dscr_max_price", 0),
            "Your Wholesale Fee":    calc.get("wholesale_fee", 0),
            "Buyer Closing Costs":   calc.get("closing_costs", 0),
            "Buyer Down Payment":    calc.get("down_payment", 0),
            "Buyer Loan Amount":     calc.get("loan_amount", 0),

            # ── Investor Metrics ──
            "DSCR Ratio":            calc.get("dscr_ratio", 0),
            "Rent-to-Value (%)":     calc.get("rtv_pct", 0),
            "GRM":                   calc.get("grm", 0),
            "Cash-on-Cash (%)":      calc.get("coc_pct", 0),
            "Total Cash to Close":   calc.get("total_cash_invested", 0),
            "Annual Cash Flow":      calc.get("annual_cf", 0),
            "Break-even Rent":       calc.get("break_even_rent", 0),

            # ── Monthly Cash Flow ──
            "Est Buyer CF ($/mo)":   calc.get("actual_cf", 0),
            "Monthly Mortgage":      calc.get("mortgage_pmt", 0),
            "Monthly Taxes":         calc.get("taxes_mo", 0),
            "Monthly Insurance":     calc.get("insurance_mo", 0),
            "Monthly CapEx":         calc.get("capex_mo", 0),
            "Monthly Mgmt+Maint":    calc.get("var_expenses", 0),

            # ── Repairs ──
            "Est Repairs":           repair_range_str,
            "Repair Low ($)":        repair_low,
            "Repair High ($)":       repair_high,
            "Repair Tier":           repair_tier,

            # ── Market Context ──
            "Zip Median Home Value": census_data.get("median_home_value", 0),
            "Zip Vacancy Rate (%)":  census_data.get("vacancy_rate_pct", 0),
            "Price vs Zip Median":   f"{(list_price/census_data['median_home_value']*100):.0f}%" if census_data.get("median_home_value") else "N/A",

            # ── Condition ──
            "Condition":             condition,
            "Distress Keywords":     ", ".join(kw_hits[:6]),
            "Inspection Flags":      flag_str,

            # ── Listing Data ──
            "Listing Description":   (description[:400] if description else ""),
            "Zillow Insight":        zillow_signals.get("flex_text", ""),
            "Days on Market":        zillow_signals.get("days_on_market", ""),
            "Price Reduction":       zillow_signals.get("price_reduction", ""),
            "Tax Assessed Value":    zillow_signals.get("tax_assessed_value", ""),
            "Desc Source":           desc_src,

            # ── 5-Year Projection (JSON for display) ──
            "_proj_5yr":             proj_5yr,
        })

    progress.progress(100, text="Analysis complete")
    results = pd.DataFrame(rows_out)

    # ── Summary scorecards ──
    quality_order = {"Green Light": 0, "Caution": 1, "Inspect First": 2, "No Deal": 3}
    results_sorted = results.copy()
    results_sorted["_sort"] = results_sorted["Quality"].map(quality_order)
    results_sorted = results_sorted.sort_values("_sort").drop(columns=["_sort","_proj_5yr"], errors="ignore")

    green   = results[results["Quality"] == "Green Light"]
    caution = results[results["Quality"] == "Caution"]
    insp    = results[results["Quality"] == "Inspect First"]
    nodeal  = results[results["Quality"] == "No Deal"]
    viable  = results[results["Quality"].isin(["Green Light","Caution"])]

    st.markdown('<div class="section-label">Portfolio Overview</div>', unsafe_allow_html=True)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Analyzed",      len(results))
    m2.metric("Green Light",   len(green),   help="Viable — no red flags")
    m3.metric("Caution",       len(caution), help="Viable — has distress signals")
    m4.metric("Inspect First", len(insp),    help="Critical damage or DSCR far above list")
    m5.metric("No Deal",       len(nodeal),  help="Math doesn't work at target cashflow")
    if len(viable) > 0:
        avg_coc = viable["Cash-on-Cash (%)"].mean()
        m6.metric("Avg CoC (viable)", f"{avg_coc:.1f}%", help="Average cash-on-cash return across Green + Caution deals")

    # ── Results table ──
    st.markdown('<div class="section-label">Results</div>', unsafe_allow_html=True)

    display_cols = [
        "Quality", "Address", "Beds", "Sqft", "List Price", "Section 8 Rent ($/mo)",
        "Rent Confidence", "Your Max Offer", "Buyer Max Purchase",
        "DSCR Ratio", "Rent-to-Value (%)", "Cash-on-Cash (%)", "GRM",
        "Est Repairs", "Est Buyer CF ($/mo)", "Condition",
    ]
    display_cols = [c for c in display_cols if c in results_sorted.columns]

    def color_row(row):
        q = row.get("Quality", "")
        if q == "Green Light":   return ["background-color:#0d3320; color:#34d073; font-weight:500"] * len(row)
        if q == "Caution":       return ["background-color:#2d2000; color:#f5a623; font-weight:500"] * len(row)
        if q == "Inspect First": return ["background-color:#2d0d0d; color:#ff6b6b; font-weight:500"] * len(row)
        return                          ["background-color:#111111; color:#555555"] * len(row)

    fmt = {
        "List Price":             "${:,.0f}",
        "Section 8 Rent ($/mo)":  "${:,.0f}",
        "Your Max Offer":         "${:,.0f}",
        "Buyer Max Purchase":     "${:,.0f}",
        "Est Buyer CF ($/mo)":    "${:,.0f}",
        "DSCR Ratio":             "{:.2f}x",
        "Rent-to-Value (%)":      "{:.2f}%",
        "Cash-on-Cash (%)":       "{:.1f}%",
        "GRM":                    "{:.1f}",
    }
    st.dataframe(
        results_sorted[display_cols].style
            .apply(color_row, axis=1)
            .format({k: v for k, v in fmt.items() if k in display_cols}),
        use_container_width=True,
        height=540,
    )

    # ── Deal detail expanders ──
    viable_for_exp = [r for _, r in results.iterrows() if r["Quality"] != "No Deal"]
    viable_for_exp.sort(key=lambda r: quality_order.get(r["Quality"], 9))

    if viable_for_exp:
        st.markdown('<div class="section-label">Deal Breakdown</div>', unsafe_allow_html=True)
        for r in viable_for_exp:
            q_color = {"Green Light":"#34d073","Caution":"#f5a623","Inspect First":"#ff6b6b"}.get(r["Quality"],"#8E8E93")
            spread  = r["Your Max Offer"] - r["List Price"]
            sqft_lbl = f" · {int(r['Sqft'])} sqft" if r.get("Sqft") else ""
            conf_pill = r.get("Rent Confidence","")
            label = (
                f"{'🟢' if r['Quality']=='Green Light' else '🟡' if r['Quality']=='Caution' else '🔴'} "
                f"{r['Address']}{sqft_lbl}  ·  "
                f"Your Offer ${r['Your Max Offer']:,.0f}  ·  "
                f"List ${r['List Price']:,.0f}  ·  "
                f"Spread ${spread:+,.0f}  ·  "
                f"CoC {r.get('Cash-on-Cash (%)','—'):.1f}%  ·  "
                f"RTV {r.get('Rent-to-Value (%)','—'):.2f}%"
            )
            with st.expander(label):

                # ── Rent intelligence block ──
                conf     = r.get("Rent Confidence", "")
                conf_css = {"High":"rent-high","Medium":"rent-medium","Low":"rent-low"}.get(conf,"rent-medium")
                st.markdown(
                    f'<div class="section-label">Section 8 Rent Intelligence '
                    f'<span class="{conf_css}">{conf} Confidence</span></div>',
                    unsafe_allow_html=True
                )
                ra, rb, rc, rd = st.columns(4)
                ra.metric("S8 Rent Used",      f"${r['Section 8 Rent ($/mo)']:,.0f}/mo",
                          help="Final rent used in all calculations after sqft + consensus adjustments")
                rb.metric("HUD SAFMR",         f"${r.get('SAFMR Rent', 0):,.0f}/mo",
                          help="Raw HUD FY2026 Small Area FMR for this ZIP + bedroom count")
                rc.metric("Census Median Rent", f"${r['Census Rent']:,.0f}/mo" if r.get("Census Rent") else "N/A",
                          help="ACS 5-yr median rent for this bedroom size in this ZIP — free market validation")
                rd.metric("Rentcast AVM",       f"${r['Rentcast AVM Rent']:,.0f}/mo" if r.get("Rentcast AVM Rent") else "No key",
                          help="Rentcast market rent estimate — most accurate when API key provided")
                if r.get("Rent Note"):
                    note_css = "flag-critical" if conf == "Low" else "flag-inspect" if conf == "Medium" else "flag-ok"
                    st.markdown(f'<div class="{note_css}">{r["Rent Note"]}</div>', unsafe_allow_html=True)
                if r.get("Sqft Rent Note"):
                    st.caption(f"Sqft adjustment: {r['Sqft Rent Note']}")

                # ── Investor metrics ──
                st.markdown('<div class="section-label">Investor Metrics</div>', unsafe_allow_html=True)
                im1, im2, im3, im4, im5 = st.columns(5)
                dscr = r.get("DSCR Ratio", 0)
                dscr_delta = "✓ Lender OK" if dscr >= 1.15 else "⚠ Below 1.15 min"
                im1.metric("DSCR Ratio",        f"{dscr:.2f}x",      delta=dscr_delta,
                           help="NOI / Debt Service. Section 8 lenders require ≥ 1.15x")
                rtv = r.get("Rent-to-Value (%)", 0)
                rtv_delta = "✓ Strong" if rtv >= 1.0 else "✓ OK" if rtv >= 0.8 else "⚠ Low"
                im2.metric("Rent-to-Value",     f"{rtv:.2f}%",       delta=rtv_delta,
                           help="Monthly rent / purchase price. Target ≥ 0.8%, ideal ≥ 1%")
                coc = r.get("Cash-on-Cash (%)", 0)
                coc_delta = "✓ Strong" if coc >= 8 else "✓ OK" if coc >= 6 else "⚠ Low"
                im3.metric("Cash-on-Cash",      f"{coc:.1f}%",       delta=coc_delta,
                           help="Annual CF / Total cash invested (down + closing + repairs). Target ≥ 7%")
                grm = r.get("GRM", 0)
                grm_delta = "✓ Good" if grm <= 7 else "OK" if grm <= 9 else "⚠ High"
                im4.metric("GRM",               f"{grm:.1f}",        delta=grm_delta,
                           help="Gross Rent Multiplier = Price / Annual rent. Target ≤ 9")
                im5.metric("Break-even Rent",   f"${r.get('Break-even Rent',0):,.0f}/mo",
                           help="Minimum monthly rent to cover all expenses at zero cashflow")

                # ── Price stack ──
                st.markdown('<div class="section-label">Offer Stack</div>', unsafe_allow_html=True)
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("List Price",            f"${r['List Price']:,.0f}")
                p2.metric("Buyer Max Purchase",    f"${r['Buyer Max Purchase']:,.0f}",
                          help="Capped at list − $10k. What your end buyer pays.")
                p3.metric("Your Max Offer",        f"${r['Your Max Offer']:,.0f}",
                          help="Your wholesale contract price to seller = Buyer price − fee − closing")
                p4.metric("Your Wholesale Fee",    f"${r['Your Wholesale Fee']:,.0f}")
                pp1, pp2, pp3, _ = st.columns(4)
                pp1.metric("Down Payment",         f"${r['Buyer Down Payment']:,.0f}")
                pp2.metric("Loan Amount",          f"${r['Buyer Loan Amount']:,.0f}")
                pp3.metric("Closing Costs",        f"${r['Buyer Closing Costs']:,.0f}")

                # ── Monthly cash flow ──
                st.markdown('<div class="section-label">Monthly Cash Flow</div>', unsafe_allow_html=True)
                mf1, mf2, mf3, mf4, mf5, mf6 = st.columns(6)
                mf1.metric("S8 Rent",        f"${r['Section 8 Rent ($/mo)']:,.0f}")
                mf2.metric("Mortgage",       f"−${r['Monthly Mortgage']:,.0f}")
                mf3.metric("Taxes",          f"−${r['Monthly Taxes']:,.0f}")
                mf4.metric("Insurance",      f"−${r['Monthly Insurance']:,.0f}")
                mf5.metric("CapEx Reserve",  f"−${r.get('Monthly CapEx',0):,.0f}",
                           help="10% of gross rent set aside for capital expenditures (roof, HVAC, etc.)")
                mf6.metric("Mgmt + Maint",   f"−${r.get('Monthly Mgmt+Maint',0):,.0f}")
                cf_val = r.get("Est Buyer CF ($/mo)", 0)
                cf_color = "#34d073" if cf_val >= 400 else "#f5a623" if cf_val >= 200 else "#ff6b6b"
                st.markdown(
                    f'<div style="background:#1C1C1E;border-radius:12px;padding:14px 20px;margin:8px 0;">'
                    f'<span style="color:#8E8E93;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;">NET MONTHLY CASHFLOW</span>'
                    f'<div style="color:{cf_color};font-size:28px;font-weight:700;letter-spacing:-0.02em;margin-top:4px;">'
                    f'${cf_val:+,.0f}/mo</div>'
                    f'<div style="color:#8E8E93;font-size:11px;margin-top:2px;">'
                    f'${r.get("Annual Cash Flow",0):,.0f}/yr · Total cash to close ${r.get("Total Cash to Close",0):,.0f}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # ── 5-Year rent & CF projection ──
                proj = r.get("_proj_5yr") or []  # might be in original results obj
                if not proj:
                    # Recompute if needed (when from results_sorted which dropped _proj_5yr)
                    _r2 = r.get("Section 8 Rent ($/mo)", 0)
                    proj = []
                    for yr in range(1, 6):
                        _eff = max(0, _r2 - utility_allowance)
                        _egi = _eff * (1 - vacancy_rate)
                        _vexp = _eff * (maintenance_rate + mgmt_rate)
                        _capx = _r2 * capex_rate
                        _fixed = (r.get("Monthly Taxes",0) * (1.02**(yr-1))
                                + r.get("Monthly Insurance",0) * (1.02**(yr-1))
                                + r.get("Monthly Mortgage",0))
                        _cf = _egi - _vexp - _capx - _fixed
                        proj.append({"year": yr, "rent": round(_r2), "cf": round(_cf)})
                        _r2 = round(_r2 * (1 + rent_growth_rate))

                if proj:
                    st.markdown('<div class="section-label">5-Year Projection</div>', unsafe_allow_html=True)
                    pcols = st.columns(5)
                    for i, p in enumerate(proj):
                        cf_sign = "+" if p["cf"] >= 0 else ""
                        pcols[i].metric(
                            f"Year {p['year']}",
                            f"${p['rent']:,}/mo",
                            delta=f"{cf_sign}${p['cf']:,} CF",
                        )

                # ── Repairs + property ──
                st.markdown('<div class="section-label">Property & Repairs</div>', unsafe_allow_html=True)
                rp1, rp2, rp3 = st.columns(3)
                rp1.metric("Sqft",        str(int(r["Sqft"])) if r.get("Sqft") else "Unknown")
                rp2.metric("Est. Repairs", r.get("Est Repairs", "Unknown"),
                           help="Based on condition + sqft. Rough wholesale range — not a contractor bid.")
                rp3.metric("Repair Tier",  r.get("Repair Tier", "—"))

                # Agent info
                if r.get("Agent Name") or r.get("Agent Email") or r.get("Agent Phone"):
                    st.markdown('<div class="section-label">Agent</div>', unsafe_allow_html=True)
                    ag1, ag2, ag3 = st.columns(3)
                    if r.get("Agent Name"):  ag1.caption(f"**Agent:** {r['Agent Name']}")
                    if r.get("Agent Email"): ag2.caption(f"**Email:** {r['Agent Email']}")
                    if r.get("Agent Phone"): ag3.caption(f"**Phone:** {r['Agent Phone']}")

                # ── Market context ──
                st.markdown('<div class="section-label">ZIP Market Context</div>', unsafe_allow_html=True)
                zc1, zc2, zc3 = st.columns(3)
                zc1.metric("Zip Median Value", f"${r['Zip Median Home Value']:,.0f}" if r.get("Zip Median Home Value") else "N/A")
                zc2.metric("Price vs Median",  r.get("Price vs Zip Median","N/A"))
                zc3.metric("Zip Vacancy Rate", f"{r['Zip Vacancy Rate (%)']:.1f}%")

                # ── Flags ──
                if r.get("Inspection Flags"):
                    st.markdown('<div class="section-label">Flags</div>', unsafe_allow_html=True)
                    for flag in r["Inspection Flags"].split(" | "):
                        if not flag.strip(): continue
                        fl = flag.lower()
                        css = "flag-critical" if "critical" in fl else \
                              "flag-inspect"  if any(x in fl for x in ["inspect","dscr","lender","hqs","risk"]) else \
                              "flag-rehab"    if any(x in fl for x in ["rehab","repair","work","distress"]) else \
                              "flag-rehab"
                        st.markdown(f'<div class="{css}">{flag}</div>', unsafe_allow_html=True)

                # ── Zillow + listing data ──
                zil_dom = r.get("Days on Market")
                zil_pr  = r.get("Price Reduction")
                zil_tv  = r.get("Tax Assessed Value")
                if zil_dom or zil_pr or zil_tv:
                    st.markdown('<div class="section-label">Zillow Signals</div>', unsafe_allow_html=True)
                    zc1, zc2, zc3 = st.columns(3)
                    if zil_dom: zc1.metric("Days on Market", zil_dom)
                    if zil_pr:  zc2.metric("Price Reduction", zil_pr)
                    if zil_tv and isinstance(zil_tv,(int,float)) and zil_tv:
                        zc3.metric("Tax Assessed Value", f"${zil_tv:,.0f}")
                if r.get("Zillow Insight"):
                    st.markdown(
                        f'<div class="flag-rehab">💡 {r["Zillow Insight"]}</div>',
                        unsafe_allow_html=True
                    )
                if r.get("Listing Description"):
                    st.caption(f"Description: {r['Listing Description'][:400]}")
                st.caption(f"Rent: {r['Rent Source']}  ·  Description: {r['Desc Source']}")

    # ── Exports ──
    st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)
    export_cols = [c for c in results_sorted.columns if not c.startswith("_")]
    ec1, ec2 = st.columns(2)
    with ec1:
        csv_all = results_sorted[export_cols].to_csv(index=False).encode("utf-8")
        st.download_button("Download All Properties", csv_all,
                           "section8_all_offers.csv", "text/csv",
                           use_container_width=True)
    with ec2:
        good = results_sorted[results_sorted["Quality"].isin(["Green Light","Caution"])]
        csv_good = good[export_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            f"Download Green Light + Caution ({len(good)} deals)",
            csv_good, "section8_good_offers.csv", "text/csv",
            use_container_width=True, type="primary",
        )

else:
    st.markdown('<div class="section-label">Get Started</div>', unsafe_allow_html=True)
    st.markdown(
        "Upload a CSV or Excel file with your property list to begin.\n\n"
        "**Required:** `Address` (or `Street` + `City` + `State`) · `Zip` · `Bedrooms` · `List Price`\n\n"
        "**Optional:** `Sqft` · `Agent Name` · `Agent Email` · `Agent Phone` · `Description`\n\n"
        "**Rent is validated against 3 sources:** HUD SAFMR · Census ACS median rent · "
        "Rentcast AVM (if API key provided). Low-confidence rent gets a reasonableness flag.\n\n"
        "**Export includes:** S8 Rent · Rent Confidence · DSCR Ratio · Cash-on-Cash · "
        "Rent-to-Value · GRM · Break-even Rent · Est. Repairs · All agent pass-through fields."
    )
