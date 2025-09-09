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
    json_data_str = ""
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

                # EXTRACT DATA using a robust script instead of relying on pandas
                json_data = await tab.execute_script("""
                    const table = document.querySelector('table');
                    if (!table) return null;
                    const rows = Array.from(table.querySelectorAll('tbody tr'));
                    const data = rows.map(row => {
                        const cells = Array.from(row.querySelectorAll('td'));
                        if (cells.length < 7) return null;

                        const modelCell = cells[2];
                        const modelLink = modelCell.querySelector('a');
                        const modelName = modelLink ? (modelLink.title || modelLink.textContent.trim()) : modelCell.textContent.trim();

                        return {
                            'Model': modelName,
                            'Score': cells[3].textContent.trim(),
                            'Votes': cells[5].textContent.trim(),
                            'organization': cells[6].textContent.trim(),
                        };
                    }).filter(Boolean);
                    return JSON.stringify(data);
                """)

                last_updated = await tab.execute_script("""
                    const el = Array.from(document.querySelectorAll('p, div, span')).find(el => el.textContent.includes('Last Updated'));
                    return el ? el.textContent : '';
                """)

                json_result_val = ""
                if isinstance(json_data, dict) and json_data.get('result', {}).get('result', {}).get('type') == 'string':
                    json_result_val = json_data['result']['result'].get('value', '[]')
                else:
                    json_result_val = str(json_data or '[]')

                last_updated_val = ""
                if isinstance(last_updated, dict) and last_updated.get('result', {}).get('result', {}).get('type') == 'string':
                    last_updated_val = last_updated['result']['result'].get('value', '')
                else:
                    last_updated_val = str(last_updated or "")

                return json_result_val, last_updated_val

        json_data_str, date_raw = asyncio.run(_run_pydoll(base_url))
        if not json_data_str:
            print("    ❌ Pydoll did not capture the table.")
    except Exception as e:
        print(f"    ❌ Pydoll error: {e}")
        return None, None

    # Parse the JSON data captured from the browser
    try:
        records = json.loads(json_data_str)
        if not records:
            print("    ❌ No model data was extracted from the page.")
            return None, None
        df_pd = pd.DataFrame(records)
    except json.JSONDecodeError:
        print("    ❌ Failed to parse JSON data from the browser.")
        return None, None


    # Clean and standardise column names we care about
    # This section is simplified as JSON extraction provides clean columns
    if "Score" not in df_pd.columns:
        # Simple fallback for score if name is different
        score_col_cand = [c for c in df_pd.columns if "score" in c.lower()]
        if score_col_cand:
            df_pd = df_pd.rename(columns={score_col_cand[0]: "Score"})
        else:
            df_pd['Score'] = 0 # Cannot proceed without score


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

    html_for_date_search = f"last updated: {date_raw}" # Use raw date string for parsing
    m_iso = re.search(r"last updated[\s:]*([0-9]{4}-[0-9]{2}-[0-9]{2})", html_for_date_search, flags=re.I)
    if m_iso:
        last_updated_date = m_iso.group(1)
    else:
        # Try human-readable pattern inside the (possibly truncated) HTML or the date_raw captured
        raw_match = re.search(r"last updated[\s:]*([A-Za-z]{3,9}[\s\xa0]+\d{1,2},[\s\xa0]+\d{4})", html_for_date_search, flags=re.I)
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
