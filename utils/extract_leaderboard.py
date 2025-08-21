import polars as pl
import json
from pathlib import Path
import re
import pandas as pd
import io
import sys
import os
import shutil
from typing import Tuple
from datetime import date, datetime
from pydoll.browser import Chrome as PydollChrome  # type: ignore
from pydoll.browser.options import ChromiumOptions as PydollOptions  # type: ignore

# Pydoll and HTTP fallback removed for manual-only flow

def _clean_html(html_string: str) -> str:
    """Removes HTML tags from a string."""
    if not isinstance(html_string, str):
        return html_string
    return re.sub(r'<.*?>', '', html_string)


def _find_date_in_config(component, search_string="last updated"):
    # Deprecated: kept only for backwards compatibility if needed elsewhere
    return None


def fetch_latest_leaderboard_df() -> Tuple[pl.DataFrame, str]:
    """Manually assisted download of the leaderboard from lmarena.ai (Pydoll only).

    Opens a visible Chromium window via Pydoll. Perform any required interactions
    yourself (solve Cloudflare/Turnstile challenge, remove style control). The
    script polls for the table and captures it automatically once visible.

    Returns:
        Tuple[pl.DataFrame, str]: DataFrame with columns [Model, Score, Votes, organization] and
        date string in the page footer (YYYY-MM-DD)
    """

    base_url = "https://lmarena.ai/leaderboard/text/overall-no-style-control"
    html = ""
    date_raw = ""

    print("  ↳ Launching Chromium via Pydoll (visible)…")
    try:
        import asyncio

        def _find_chromium_binary() -> tuple[str | None, list[str]]:
            tried: list[str] = []

            # 1) Look on PATH for common names
            for name in (
                "thorium-browser",
                "thorium",
                "google-chrome-stable",
                "google-chrome",
                "chromium",
                "chromium-browser",
            ):
                path = shutil.which(name)
                if path:
                    return path, tried
                tried.append(name)

            # 2) Known absolute paths
            for cand in (
                "/usr/bin/thorium-browser",
                "/opt/chromium.org/thorium/thorium-browser",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
                "/opt/google/chrome/chrome",
            ):
                if os.path.exists(cand):
                    return cand, tried
                tried.append(cand)

            return None, tried

        async def _run_pydoll(url: str) -> tuple[str, str]:
            options = PydollOptions()
            binary_override, tried = _find_chromium_binary()
            if binary_override:
                options.binary_location = binary_override
            else:
                raise RuntimeError("No valid Chromium/Chrome/Thorium binary found. Tried: " + ", ".join(tried))
            options.add_argument('--disable-dev-shm-usage')
            options.start_timeout = 20

            manual_wait_secs = 60

            async with PydollChrome(options=options) as browser:
                tab = await browser.start()
                bypass_ctx = getattr(tab, 'expect_and_bypass_cloudflare_captcha', None)
                if callable(bypass_ctx):
                    async with bypass_ctx():
                        await tab.go_to(url)
                else:
                    await tab.go_to(url)

                print("\nIf a Cloudflare/Turnstile challenge appears, solve it in the opened window.")
                print("Once solved, the script will detect the table automatically (waiting up to 60s).")

                # Manual mode: no auto-click loop; user resolves challenge directly
                table_found = False
                for _ in range(manual_wait_secs):
                    try:
                        try:
                            await tab.query("iframe[src*='leaderboard/text']")
                            await tab.switch_to_frame("iframe[src*='leaderboard/text']")
                        except Exception:
                            pass
                        node = await tab.find(tag_name='table', timeout=1, raise_exc=False)
                        if node is not None:
                            table_found = True
                            break
                    except Exception:
                        pass

                if not table_found:
                    return "", ""

                table_html = await tab.execute_script("return document.querySelector('table')?.outerHTML || ''")
                last_updated = await tab.execute_script("const n=[...document.querySelectorAll('*')].find(x=>/Last Updated/i.test(x.textContent||''));return n? (n.nextElementSibling?.textContent||n.textContent||''):'';")
                return str(table_html or ""), str(last_updated or "")

        html, date_raw = asyncio.run(_run_pydoll(base_url))
        if not html:
            print("    ❌ Pydoll did not capture the table.")
    except Exception as e:
        print(f"    ❌ Pydoll error: {e}")
        return None, None

    # Parse all tables on the page. The first one is the overall leaderboard.
    if not html:
        print("    ❌ Empty HTML content after manual capture.")
        return None, None
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
        # Try human-readable pattern inside the (possibly truncated) HTML or the date_raw captured
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