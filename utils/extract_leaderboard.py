import polars as pl
import json
from pathlib import Path
import re
import pandas as pd
from tenacity import retry, wait_exponential, stop_after_attempt
import certifi
import io
import sys
from typing import Tuple
from datetime import date, datetime
from cloudscraper import create_scraper
try:
    from playwright.sync_api import sync_playwright  # type: ignore
except ImportError:  # noqa: F401
    sync_playwright = None  # type: ignore

def _clean_html(html_string: str) -> str:
    """Removes HTML tags from a string."""
    if not isinstance(html_string, str):
        return html_string
    return re.sub(r'<.*?>', '', html_string)


def _find_date_in_config(component, search_string="last updated"):
    """Recursively search for a date string in a component's properties."""
    if isinstance(component, dict):
        props = component.get("props", {})
        if isinstance(props, dict):
            value = props.get("value")
            if isinstance(value, str) and search_string in value.lower():
                match = re.search(r'\d{4}-\d{2}-\d{2}', value)
                if match:
                    return match.group(0)

        if "children" in props and props["children"]:
            for child in props["children"]:
                found = _find_date_in_config(child, search_string)
                if found:
                    return found
    return None


def fetch_latest_leaderboard_df(use_headless: bool = True) -> Tuple[pl.DataFrame, str]:
    """Download the latest leaderboard from lmarena.ai.

    The site is behind Cloudflare, so we use cloudscraper to negotiate the challenge automatically.

    Returns:
        Tuple[pl.DataFrame, str]: DataFrame with columns [Model, Score, Votes, organization] and
        date string in the page footer (YYYY-MM-DD)
    """

    base_url = "https://lmarena.ai/leaderboard/text"
    date_raw = ""

    if use_headless:
        print("  ↳ Launching headless Chromium (Playwright)…")
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=[
                    "--no-sandbox", "--disable-dev-shm-usage"
                ])

                context = browser.new_context(user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ))

                page = context.new_page()
                # Block only images to keep JS/CSS (needed for Cloudflare challenge)
                page.route(r"**/*.{png,jpg,jpeg,svg,webp}", lambda route: route.abort())

                # Let the Cloudflare JS challenge run (wait for network to go idle)
                # Pre-solve Cloudflare with CloudScraper and reuse its cookies/UA
                _scraper = create_scraper(browser={'browser': 'firefox', 'platform': 'linux', 'mobile': False})
                _scraper.get(base_url, timeout=30, verify=certifi.where())
                ua = _scraper.headers.get('User-Agent', (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ))

                context = browser.new_context(user_agent=ua)
                for c in _scraper.cookies:
                    context.add_cookies([{
                        'name': c.name,
                        'value': c.value,
                        'domain': c.domain.lstrip('.'),
                        'path': c.path,
                        'expires': -1,
                        'httpOnly': False,
                        'secure': True,
                    }])
                page = context.new_page()
                page.route(r"**/*.{png,jpg,jpeg,svg,webp}", lambda route: route.abort())

                for attempt in range(3):  # first load + up to 2 reloads
                    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)

                    # Accept cookie banner if present
                    try:
                        page.get_by_role("button", name="Accept Cookies").click(timeout=3000)
                    except Exception:
                        pass

                    # Open the dropdown (label usually shows "Default") and pick the no-style option
                    try:
                        page.locator("button:has-text('Default')").first.click()
                    except Exception:
                        try:
                            page.get_by_role("combobox").click()
                        except Exception:
                            pass

                    page.locator("text=Remove Style Control").first.click()

                    page.wait_for_timeout(1500)  # allow table JS to refresh
                    page.wait_for_selector("table tr", timeout=20000)

                    top_score_txt = page.locator("table tr td:nth-child(4)").first.inner_text().strip()
                    if top_score_txt.isdigit() and int(top_score_txt) >= 1460:
                        break  # got the style-control-OFF table
                    page.wait_for_timeout(1000)
                    # reload and try again
                # capture table HTML and date
                _full_html = page.content()
                html = page.locator("table").first.evaluate("el => el.outerHTML")
                try:
                    date_raw = page.locator("text=Last Updated").first.evaluate("el => el.nextElementSibling.textContent")
                except Exception:
                    date_raw = ""
                browser.close()
        except Exception as e:
            print(f"    ⚠️ Playwright path failed: {e}\n    ↳ Falling back to CloudScraper…")
            use_headless = False  # fallback

    if not use_headless:
        print("  ↳ Downloading leaderboard HTML via CloudScraper…")
        scraper = create_scraper(browser={
            'browser': 'firefox',
            'platform': 'linux',
            'mobile': False
        })

        @retry(wait=wait_exponential(multiplier=2, min=2, max=30), stop=stop_after_attempt(4))
        def _get_html():
            resp = scraper.get(base_url, timeout=30, verify=certifi.where())
            resp.raise_for_status()
            return resp.text
        try:
            html = _get_html()
        except Exception as e:
            print(f"    ❌ Failed to fetch leaderboard HTML: {e}")
            return None, None

    # Parse all tables on the page. The first one is the overall leaderboard.
    tables = pd.read_html(io.StringIO(html))
    if not tables:
        print("    ❌ pandas.read_html found no tables in the page.")
        return None, None

    df_pd = tables[0]

    # Clean and standardise column names we care about
    expected_cols = {c.lower(): c for c in df_pd.columns}
    if "arena score" in expected_cols:
        score_col = expected_cols["arena score"]
    elif "score" in expected_cols:
        score_col = expected_cols["score"]
    else:
        score_col = df_pd.columns[1]  # fallback to 2nd col
    votes_col = expected_cols.get("votes", None)
    org_col = expected_cols.get("organization", None)

    df_pd["Model"] = df_pd["Model"].apply(_clean_html)

    rename_map = {score_col: "Score"}
    if votes_col:
        rename_map[votes_col] = "Votes"
    if org_col:
        rename_map[org_col] = "organization"

    df_pd = df_pd.rename(columns=rename_map)

    if "Votes" in df_pd.columns:
        df_pd["Votes"] = (
            df_pd["Votes"]
            .astype(str)
            .str.replace(r"[^\d]", "", regex=True)   # drop NB-spaces, commas, etc.
        )

    keep_cols = [c for c in ["Model", "Score", "Votes", "organization"] if c in df_pd.columns]
    df = pl.from_pandas(df_pd[keep_cols])

    # Extract the "Last updated" date.
    last_updated_date: str | None = None

    m_iso = re.search(r"last updated[\s:]*([0-9]{4}-[0-9]{2}-[0-9]{2})", html, flags=re.I)
    if m_iso:
        last_updated_date = m_iso.group(1)
    else:
        # Try human-readable pattern inside the (possibly truncated) HTML or the date_raw captured via Playwright
        raw_match = re.search(r"last updated[\s:]*([A-Za-z]{3,9}[\s\xa0]+\d{1,2},[\s\xa0]+\d{4})", html, flags=re.I)
        raw = raw_match.group(1) if raw_match else date_raw
        if raw:
            for fmt in ("%b %d, %Y", "%B %d, %Y"):
                try:
                    last_updated_date = datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

    if not last_updated_date:
        last_updated_date = date.today().isoformat()

    print("  ↳ Leaderboard data loaded and parsed…")
    return df, last_updated_date


if __name__ == '__main__':
    leaderboard_df, file_date = fetch_latest_leaderboard_df()
    if leaderboard_df is not None:
        output_path = Path(__file__).parent.parent / "data" / "rank_data.json"

        records = leaderboard_df.to_dicts()

        output_data = {"last_updated": file_date, "models": records}

        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print("  ✅ Successfully scraped LM Arena data, saved to data/rank_data.json")
    else:
        print("  ❌ Failed to extract data.")
        print("\n❌ DATA REFRESH FAILED")
        sys.exit(1)