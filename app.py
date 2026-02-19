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
/* Clean card look for metrics */
div[data-testid="metric-container"] {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 12px 16px;
    border: 1px solid #e9ecef;
}
/* Color‑coded inspection badges in the table */
.badge-critical  { color:#842029; background:#f8d7da; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
.badge-inspect   { color:#664d03; background:#fff3cd; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
.badge-good      { color:#0f5132; background:#d1e7dd; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }
/* Expander detail flags */
.flag-critical { background-color:#f8d7da; border-left:4px solid #dc3545; padding:8px 12px; border-radius:4px; margin:4px 0; }
.flag-inspect  { background-color:#fff3cd; border-left:4px solid #ffc107; padding:8px 12px; border-radius:4px; margin:4px 0; }
.flag-rehab    { background-color:#e2e3e5; border-left:4px solid #6c757d; padding:8px 12px; border-radius:4px; margin:4px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Section 8 Wholesale Underwriter")
st.caption("Upload a CSV → get zip-accurate Section 8 rents (HUD SAFMR) + DSCR-based wholesale offers")

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("💰 Financing")
    interest_rate    = st.number_input("Interest Rate (%)", value=7.5, step=0.1, min_value=1.0, max_value=20.0) / 100
    down_pct         = st.slider("Down Payment (%)", 10, 50, 20) / 100
    loan_term_years  = st.selectbox("Loan Term (Years)", [30, 20, 15], index=0)
    target_cashflow  = st.number_input("Target Buyer Cashflow ($/mo)", value=400, step=50)

    st.header("🧾 Expenses")
    tax_rate         = st.number_input("Property Tax (% of value/yr)", value=1.5, step=0.1, min_value=0.0) / 100
    insurance_rate   = st.number_input("Insurance (% of value/yr)",    value=0.75, step=0.05, min_value=0.0) / 100
    vacancy_rate     = st.number_input("Vacancy (%)",                   value=5.0, step=1.0, min_value=0.0) / 100
    maintenance_rate = st.number_input("Maintenance (% of rent/mo)",   value=5.0, step=1.0, min_value=0.0) / 100
    mgmt_rate        = st.number_input("Property Mgmt (%)",            value=0.0, step=1.0, min_value=0.0) / 100

    st.header("🏷️ Wholesale Deal")
    wholesale_fee    = st.number_input("Your Assignment Fee ($)", value=10000, step=500, min_value=0)
    closing_costs_pct= st.number_input("Closing Costs (% of purchase)", value=3.0, step=0.5, min_value=0.0) / 100

    st.header("🚩 Offer Flags")
    inspect_threshold = st.number_input(
        "Flag if DSCR max exceeds List Price by (%):",
        value=15, step=5, min_value=0,
        help="When the DSCR math supports a price much higher than list, it likely needs heavy rehab."
    )
    payment_standard = st.selectbox(
        "Section 8 Payment Standard",
        ["100% FMR (conservative)", "110% FMR (aggressive)"],
        help="PHAs set their own payment standards between 90–110% of FMR. 100% is the safe default."
    )
    use_110 = "110%" in payment_standard

    st.header("🔑 Rentcast API (optional)")
    rentcast_key = st.text_input(
        "Rentcast API Key",
        type="password",
        help=(
            "Optional — enables auto-fetching listing descriptions by address.\n\n"
            "Free tier: 50 calls/month at app.rentcast.io\n\n"
            "Without a key, include a 'Description' column in your CSV."
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


# ─────────────────────────────────────────────
# CENSUS ACS — FREE ZIP-LEVEL MARKET DATA
# No API key required. Used for anomaly-based condition detection.
# ─────────────────────────────────────────────
@st.cache_data(ttl=86400 * 30, show_spinner=False)
def get_census_zip_data(zip_code: str) -> dict:
    """
    Pull ACS 5-year estimates for a ZIP code from the Census Bureau API.
    Returns dict with median_home_value, total_units, vacancy_rate.
    Completely free, no API key required.
    Variables:
      B25077_001E = Median home value ($)
      B25002_001E = Total housing units
      B25002_003E = Vacant housing units
    """
    zip_str = str(zip_code).strip().zfill(5)
    url = (
        "https://api.census.gov/data/2022/acs/acs5"
        "?get=B25077_001E,B25002_001E,B25002_003E"
        f"&for=zip+code+tabulation+area:{zip_str}"
    )
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if len(data) >= 2:
                row = data[1]
                median_val  = int(row[0]) if row[0] and row[0] != "-666666666" else 0
                total_units = int(row[1]) if row[1] else 0
                vacant_units= int(row[2]) if row[2] else 0
                vacancy_pct = round((vacant_units / total_units * 100), 1) if total_units > 0 else 0
                return {
                    "median_home_value": median_val,
                    "total_units":       total_units,
                    "vacant_units":      vacant_units,
                    "vacancy_rate_pct":  vacancy_pct,
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
# DSCR OFFER CALCULATOR
# ─────────────────────────────────────────────
def calculate_dscr_offer(
    s8_rent: float,
    tax_r: float,
    ins_r: float,
    vac_r: float,
    maint_r: float,
    mgmt_r: float,
    interest: float,
    term_yrs: int,
    down_pct: float,
    target_cf: float,
    closing_pct: float,
    fee: float,
    list_price: float,
) -> dict:
    """
    Solve for the MAX BUYER PRICE where the deal cashflows >= target_cf/mo.

    KEY RULE: Max Buyer Price is ALWAYS capped at list_price.
    A buyer would never pay more than list price. If the DSCR math allows a
    higher price, that just means the deal has extra margin — it does NOT mean
    the buyer should pay more.

    Your Offer (to the seller) = min(max_buyer_price, list_price) - wholesale_fee - closing_costs
    This is what YOU submit as a wholesale contract price.

    Returns a dict with all intermediate numbers.
    """
    if s8_rent <= 0 or list_price <= 0:
        return {"viable": False}

    egi     = s8_rent * (1 - vac_r)          # effective gross income after vacancy
    var_exp = s8_rent * (maint_r + mgmt_r)    # variable % of rent expenses

    mo_rate = interest / 12
    n       = term_yrs * 12
    if mo_rate > 0:
        mort_factor = (mo_rate * (1 + mo_rate) ** n) / ((1 + mo_rate) ** n - 1)
    else:
        mort_factor = 1 / n

    # Solve: egi - var_exp - (tax/12)*P - (ins/12)*P - mort_factor*(1-down)*P = target_cf
    coeff = (tax_r / 12) + (ins_r / 12) + mort_factor * (1 - down_pct)
    num   = egi - var_exp - target_cf

    if num <= 0 or coeff <= 0:
        return {"viable": False}

    dscr_max = num / coeff  # what the DSCR math supports — could be > list_price

    # ── CAP: buyer never pays more than list price ──
    max_buyer_price = min(dscr_max, list_price)

    # Recalculate actual cashflow at the capped buyer price
    loan        = max_buyer_price * (1 - down_pct)
    mort_pmt    = npf.pmt(mo_rate, n, -loan) if mo_rate > 0 else loan / n
    taxes_mo    = (max_buyer_price * tax_r) / 12
    ins_mo      = (max_buyer_price * ins_r) / 12
    actual_cf   = egi - var_exp - taxes_mo - ins_mo - mort_pmt

    # ── Your wholesale offer to seller ──
    # Closing costs are based on the actual contract price (your offer to seller)
    # your_offer = max_buyer_price - fee - closing_costs_on_your_offer
    # Solving: offer + offer*closing_pct = max_buyer_price - fee
    # offer * (1 + closing_pct) = max_buyer_price - fee
    if closing_pct < 1:
        your_offer_gross = max_buyer_price - fee
        your_offer       = your_offer_gross / (1 + closing_pct)
        closing_amt      = your_offer * closing_pct
    else:
        return {"viable": False}

    # Extra margin when DSCR math supported more than list price
    dscr_headroom = max(0, dscr_max - list_price)

    return {
        "viable":           your_offer > 0,
        "dscr_max_price":   round(dscr_max, 2),      # what math supports (may exceed list)
        "max_buyer_price":  round(max_buyer_price, 2), # capped at list price
        "s8_rent":          s8_rent,
        "egi":              round(egi, 2),
        "var_expenses":     round(var_exp, 2),
        "taxes_mo":         round(taxes_mo, 2),
        "insurance_mo":     round(ins_mo, 2),
        "mortgage_pmt":     round(mort_pmt, 2),
        "actual_cf":        round(actual_cf, 2),
        "loan_amount":      round(loan, 2),
        "down_payment":     round(max_buyer_price * down_pct, 2),
        "closing_costs":    round(closing_amt, 2),
        "wholesale_fee":    fee,
        "your_offer":       round(your_offer, 2),
        "dscr_headroom":    round(dscr_headroom, 2),  # extra margin above list
    }


# ─────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────
st.markdown("---")
col_up, col_info = st.columns([2, 1])

with col_up:
    uploaded = st.file_uploader("Upload Property CSV / Excel", type=["csv", "xlsx"])
    st.caption(
        "**Required:** `Address` · `Zip` · `Bedrooms` · `List Price`  |  "
        "**Optional:** `Description` (skips Zillow scrape for that row)"
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

# Sample CSV
sample = pd.DataFrame({
    "Address":    ["3820 Guilford Ave, Indianapolis, IN 46205", "456 Oak Ave, Indianapolis, IN 46218"],
    "Zip":        [46205, 46218],
    "Bedrooms":   [3, 4],
    "List Price": [95000, 120000],
    "Description":["", ""],
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
        if cl in ("address","addr","streetaddress","propertyaddress"):   col_map[c] = "Address"
        elif cl in ("zip","zipcode","zip_code","postalcode","postal"):   col_map[c] = "Zip"
        elif cl in ("bedrooms","beds","bed","br","bdrms","bdrm"):        col_map[c] = "Bedrooms"
        elif cl in ("listprice","price","mlsamount","askingprice",
                    "listingprice","amount","saleprice","list"):          col_map[c] = "List Price"
        elif cl in ("description","desc","remarks","publicremarks",
                    "notes","listingremarks","agentremarks"):             col_map[c] = "Description"
    raw = raw.rename(columns=col_map)

    missing_req = [r for r in ["Address","Zip","Bedrooms","List Price"] if r not in raw.columns]
    if missing_req:
        st.error(f"Missing columns: {', '.join(missing_req)}")
        st.stop()

    for col in ["List Price","Bedrooms","Zip"]:
        raw[col] = raw[col].astype(str).str.replace(r"[$,]","",regex=True)
        raw[col] = pd.to_numeric(raw[col], errors="coerce").fillna(0)

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

        # 1. Section 8 rent
        s8_rent, rent_src = get_section8_rent(zip_str, beds, safmr_df)

        # 2. Description — CSV column first, then Rentcast API
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
            time.sleep(0.3)  # gentle rate limit for Rentcast free tier

        # 2b. Zillow listing signals (free — no API key, no bot detection)
        zillow_signals = fetch_zillow_listing_signals(addr)
        zil_condition, zil_signal_strs = analyze_zillow_signals(zillow_signals)

        # 3. Condition (from description keywords first, Zillow signals as fallback)
        condition, kw_hits = analyze_condition(description)

        list_price = float(row["List Price"])

        # 4. DSCR offer — list_price passed in so buyer price is always capped at it
        calc = calculate_dscr_offer(
            s8_rent=s8_rent,
            tax_r=tax_rate, ins_r=insurance_rate,
            vac_r=vacancy_rate, maint_r=maintenance_rate, mgmt_r=mgmt_rate,
            interest=interest_rate, term_yrs=loan_term_years,
            down_pct=down_pct, target_cf=target_cashflow,
            closing_pct=closing_costs_pct, fee=wholesale_fee,
            list_price=list_price,
        )

        # 5. Enforce minimum $10k below list for buyer price
        #    Your offer = buyer_price - fee - closing → buyer must pay ≥ $10k below list
        if calc.get("viable"):
            buyer_price = calc["max_buyer_price"]
            # If buyer price is within $10k of list, pull it back
            if buyer_price > list_price - 10000:
                calc["max_buyer_price"] = list_price - 10000
                # Recalculate your offer from the adjusted buyer price
                your_offer_gross = calc["max_buyer_price"] - wholesale_fee
                calc["your_offer"]    = round(your_offer_gross / (1 + closing_costs_pct), 2)
                calc["closing_costs"] = round(calc["your_offer"] * closing_costs_pct, 2)
                calc["down_payment"]  = round(calc["max_buyer_price"] * down_pct, 2)
                calc["loan_amount"]   = round(calc["max_buyer_price"] * (1 - down_pct), 2)
                if calc["your_offer"] <= 0:
                    calc["viable"] = False

        # 6. Free Census-based price anomaly detection (works for every property, no API key)
        price_signals = get_price_anomaly_signals(list_price, beds, zip_str)
        census_data   = get_census_zip_data(zip_str)

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

        # 7. Build inspection flags
        flags = []
        if condition == "Critical":
            flags.append("CRITICAL DISTRESS — inspect before offering")
        elif condition in ("Needs Work", "Likely Distressed"):
            reason = f"keywords: {', '.join(kw_hits[:3])}" if kw_hits else "price severely below zip median"
            flags.append(f"Rehab likely — {reason}")
        elif condition == "Possibly Distressed":
            flags.append("Price anomaly — well below zip median, verify condition")

        # Add Census price anomaly signals as flags
        for sig in price_signals:
            if sig not in " | ".join(flags):  # avoid duplication
                flags.append(sig)

        # Add Zillow listing signals as flags
        for sig in zil_signal_strs:
            if sig not in " | ".join(flags):
                flags.append(sig)

        # DSCR headroom flag
        if calc.get("viable"):
            headroom = calc.get("dscr_headroom", 0)
            if headroom >= list_price * (inspect_threshold / 100):
                flags.append(
                    f"INSPECT — DSCR supports ${calc['dscr_max_price']:,.0f} "
                    f"(${headroom:,.0f} above list) — likely needs heavy rehab, verify condition"
                )

        flag_str = " | ".join(flags)

        # Deal quality
        if not calc.get("viable"):
            quality = "No Deal"
        elif condition in ("Critical", "Likely Distressed") or "CRITICAL" in flag_str:
            quality = "Inspect First"
        elif flags:
            quality = "Caution"
        else:
            quality = "Green Light"

        rows_out.append({
            "Quality":              quality,
            "Address":              addr,
            "Zip":                  zip_str,
            "Beds":                 beds,
            "List Price":           list_price,
            "S8 Rent ($/mo)":       s8_rent,
            "Rent Source":          rent_src,
            "Zip Median Home Value":census_data.get("median_home_value", 0),
            "Zip Vacancy Rate (%)": census_data.get("vacancy_rate_pct", 0),
            "Price vs Zip Median":  f"{(list_price/census_data['median_home_value']*100):.0f}%" if census_data.get("median_home_value") else "N/A",
            "Your Offer":           calc.get("your_offer", 0),
            "Max Buyer Price":      calc.get("max_buyer_price", 0),
            "DSCR Max (uncapped)":  calc.get("dscr_max_price", 0),
            "Wholesale Fee":        calc.get("wholesale_fee", 0),
            "Closing Costs":        calc.get("closing_costs", 0),
            "Down Payment":         calc.get("down_payment", 0),
            "Loan Amount":          calc.get("loan_amount", 0),
            "Est. Buyer CF ($/mo)": calc.get("actual_cf", 0),
            "Monthly Mortgage":     calc.get("mortgage_pmt", 0),
            "Monthly Taxes":        calc.get("taxes_mo", 0),
            "Monthly Insurance":    calc.get("insurance_mo", 0),
            "Condition":            condition,
            "Distress Keywords":    ", ".join(kw_hits[:6]),
            "Inspection Flags":     flag_str,
            "Listing Description":  (description[:400] if description else ""),
            "Zillow Insight":       zillow_signals.get("flex_text", ""),
            "Days on Market":       zillow_signals.get("days_on_market", ""),
            "Price Reduction":      zillow_signals.get("price_reduction", ""),
            "Tax Assessed Value":   zillow_signals.get("tax_assessed_value", ""),
            "Desc Source":          desc_src,
        })

    progress.progress(100, text="Done ✅")
    results = pd.DataFrame(rows_out)

    # ── Summary metrics ──
    st.markdown("---")
    green  = results[results["Quality"] == "Green Light"]
    caution= results[results["Quality"] == "Caution"]
    insp   = results[results["Quality"] == "Inspect First"]
    nodeal = results[results["Quality"] == "No Deal"]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Analyzed", len(results))
    m2.metric("🟢 Green Light",  len(green),   help="Viable deal, no red flags")
    m3.metric("🟡 Caution",      len(caution), help="Viable but shows distress keywords")
    m4.metric("🔴 Inspect First",len(insp),    help="Offer >> list price or critical damage")
    m5.metric("⛔ No Deal",      len(nodeal),  help="Math doesn't work at target cashflow")

    # ── Results table ──
    st.markdown("### 📊 Results")

    quality_order = {"Green Light": 0, "Caution": 1, "Inspect First": 2, "No Deal": 3}
    results_sorted = results.copy()
    results_sorted["_sort"] = results_sorted["Quality"].map(quality_order)
    results_sorted = results_sorted.sort_values("_sort").drop(columns="_sort")

    display_cols = [
        "Quality", "Address", "Beds", "List Price",
        "Price vs Zip Median", "S8 Rent ($/mo)", "Your Offer", "Max Buyer Price",
        "Est. Buyer CF ($/mo)", "Condition", "Inspection Flags"
    ]

    def color_row(row):
        q = row.get("Quality", "")
        if q == "Green Light":   return ["background-color:#d1e7dd"] * len(row)
        if q == "Caution":       return ["background-color:#fff3cd"] * len(row)
        if q == "Inspect First": return ["background-color:#f8d7da"] * len(row)
        return                          ["background-color:#f8f9fa; color:#6c757d"] * len(row)

    st.dataframe(
        results_sorted[display_cols].style
            .apply(color_row, axis=1)
            .format({
                "List Price":           "${:,.0f}",
                "S8 Rent ($/mo)":       "${:,.0f}",
                "Your Offer":           "${:,.0f}",
                "Max Buyer Price":      "${:,.0f}",
                "Est. Buyer CF ($/mo)": "${:,.0f}",
            }),
        use_container_width=True,
        height=520,
    )

    # ── Deal detail expanders ──
    viable_sorted = results_sorted[results_sorted["Quality"] != "No Deal"]
    if not viable_sorted.empty:
        st.markdown("### 🔍 Deal Breakdown")
        for _, r in viable_sorted.iterrows():
            icon = {"Green Light":"🟢","Caution":"🟡","Inspect First":"🔴"}.get(r["Quality"],"⚪")
            spread = r["Your Offer"] - r["List Price"]
            label  = (
                f"{icon} {r['Address']}  |  "
                f"Your Offer: **${r['Your Offer']:,.0f}**  |  "
                f"List: ${r['List Price']:,.0f}  |  "
                f"Spread vs list: ${spread:+,.0f}"
            )
            with st.expander(label):
                # Row 1: Price stack
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("List Price",        f"${r['List Price']:,.0f}")
                c1.metric("S8 Rent",           f"${r['S8 Rent ($/mo)']:,.0f}/mo")
                c2.metric("Max Buyer Price",   f"${r['Max Buyer Price']:,.0f}",
                          help="Capped at list price − $10k minimum. This is what your end buyer pays.")
                c2.metric("DSCR Math Supports",f"${r['DSCR Max (uncapped)']:,.0f}",
                          help="What the DSCR formula alone supports — shown for context only.")
                c3.metric("Your Offer (to seller)", f"${r['Your Offer']:,.0f}",
                          help="Your wholesale contract price = Buyer price − fee − closing costs")
                c3.metric("Wholesale Fee",     f"${r['Wholesale Fee']:,.0f}")
                c4.metric("Down Payment",      f"${r['Down Payment']:,.0f}")
                c4.metric("Closing Costs",     f"${r['Closing Costs']:,.0f}")

                # Row 2: Monthly breakdown
                st.markdown("**Monthly Expense Breakdown (buyer's perspective at max buyer price)**")
                ec1, ec2, ec3, ec4 = st.columns(4)
                ec1.metric("S8 Rent In",   f"${r['S8 Rent ($/mo)']:,.0f}/mo")
                ec2.metric("Mortgage",     f"${r['Monthly Mortgage']:,.0f}/mo")
                ec3.metric("Taxes",        f"${r['Monthly Taxes']:,.0f}/mo")
                ec4.metric("Insurance",    f"${r['Monthly Insurance']:,.0f}/mo")
                st.metric("Est. Buyer Cashflow", f"${r['Est. Buyer CF ($/mo)']:,.0f}/mo",
                          help="After mortgage, taxes, insurance, vacancy, maintenance, mgmt")

                # ZIP market context (from Census ACS — free)
                st.markdown("**ZIP Market Context (US Census ACS)**")
                zc1, zc2, zc3 = st.columns(3)
                zc1.metric("Zip Median Home Value", f"${r['Zip Median Home Value']:,.0f}" if r['Zip Median Home Value'] else "N/A")
                zc2.metric("Price vs Zip Median",   r['Price vs Zip Median'])
                zc3.metric("Zip Vacancy Rate",       f"{r['Zip Vacancy Rate (%)']:.1f}%")

                # Condition & flags
                st.markdown(f"**Condition:** {r['Condition']}")
                if r["Inspection Flags"]:
                    flag_lower = r["Inspection Flags"].lower()
                    css = "flag-critical" if "critical" in flag_lower else ("flag-inspect" if "inspect" in flag_lower else "flag-rehab")
                    st.markdown(f"<div class='{css}'>⚠️ {r['Inspection Flags']}</div>", unsafe_allow_html=True)

                # Zillow listing signals
                zil_row1, zil_row2, zil_row3 = st.columns(3)
                if r.get("Days on Market"):
                    zil_row1.metric("Days on Market", r["Days on Market"])
                if r.get("Price Reduction"):
                    zil_row2.metric("Price Reduction", r["Price Reduction"])
                if r.get("Tax Assessed Value"):
                    zil_row3.metric("Tax Assessed Value", f"${r['Tax Assessed Value']:,.0f}" if isinstance(r['Tax Assessed Value'], (int, float)) and r['Tax Assessed Value'] else "N/A")
                if r.get("Zillow Insight"):
                    st.info(f"💡 **Zillow Insight:** {r['Zillow Insight']}")

                if r["Listing Description"]:
                    st.caption(f"📋 **Listing Description:** {r['Listing Description'][:400]}")
                st.caption(f"Rent source: {r['Rent Source']}  |  Description source: {r['Desc Source']}")

    # ── Exports ──
    st.markdown("---")
    st.markdown("### ⬇️ Export")
    ec1, ec2 = st.columns(2)

    with ec1:
        csv_all = results_sorted.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export ALL Properties (CSV)",
            csv_all,
            "section8_all_offers.csv",
            "text/csv",
            use_container_width=True,
        )

    with ec2:
        good = results_sorted[results_sorted["Quality"].isin(["Green Light","Caution"])]
        csv_good = good.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"Export Green Light + Caution Only ({len(good)} deals) (CSV)",
            csv_good,
            "section8_good_offers.csv",
            "text/csv",
            use_container_width=True,
            type="primary",
        )

else:
    st.markdown("### Ready — upload your property list to begin")
    st.markdown(
        "**Required CSV columns:** `Address` · `Zip` · `Bedrooms` · `List Price`\n\n"
        "**Optional:** `Description` — if you include this, the app skips Zillow scraping for that row "
        "and uses your text directly for condition analysis.\n\n"
        "Properties listed under **$20,000** are automatically excluded."
    )
