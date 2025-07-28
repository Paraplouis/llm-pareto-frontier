import polars as pl
import json
from pathlib import Path
import re
from gradio_client import Client
import pandas as pd
import io
from contextlib import redirect_stdout
from tenacity import retry, wait_exponential, stop_after_attempt
import sys

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


def fetch_latest_leaderboard_df():
    """
    Fetches the latest leaderboard data from the Hugging Face Space using the Gradio client.
    """
    try:
        print("  ↳ Initializing Gradio client for lmarena-ai/chatbot-arena-leaderboard...")
        
        s = io.StringIO()
        with redirect_stdout(s):
            client = Client("lmarena-ai/chatbot-arena-leaderboard")
        output = s.getvalue().strip()
        if output:
            print(f"  ↳ {output}")

        print("  ↳ Calling the /update_leaderboard_and_plots endpoint...")
        @retry(wait=wait_exponential(multiplier=2, min=1, max=20), stop=stop_after_attempt(5))
        def _predict():
            return client.predict(
                category="Overall",
                filters=[],
                api_name="/update_leaderboard_and_plots"
            )

        result = _predict()
        
        leaderboard_payload = None
        if isinstance(result, tuple) and len(result) > 0:
            leaderboard_payload = result[0]

        # Extract the last updated date from the client's config
        last_updated_date = "Unknown"
        if hasattr(client, 'config'):
            for component in client.config.get("components", []):
                date = _find_date_in_config(component)
                if date:
                    last_updated_date = date
                    break

        if (leaderboard_payload and 
            isinstance(leaderboard_payload, dict) and 
            'value' in leaderboard_payload and
            isinstance(leaderboard_payload['value'], dict) and
            'headers' in leaderboard_payload['value'] and 
            'data' in leaderboard_payload['value']):
            
            headers = leaderboard_payload['value']['headers']
            data = leaderboard_payload['value']['data']
            
            df_pd = pd.DataFrame(data, columns=headers)

            df_pd['Model'] = df_pd['Model'].apply(_clean_html)
            
            df = pl.from_pandas(df_pd)
            
            df = df.rename({
                "Arena Score": "Score",
                "Votes": "Votes",
                "Organization": "organization"
            })
            
            df = df.select(["Model", "Score", "Votes", "organization"])

            print("  ↳ Leaderboard data loaded and parsed...")
            # The date is not available in the response, so we'll use a placeholder.
            return df, last_updated_date

        else:
            print("Could not find or parse the leaderboard dataframe from the Gradio result.")
            return None, None

    except Exception as e:
        print(f"    ❌ An error occurred: {e}")
        return None, None


if __name__ == '__main__':
    leaderboard_df, file_date = fetch_latest_leaderboard_df()
    if leaderboard_df is not None:
        output_path = Path(__file__).parent.parent / "data" / "rank_data.json"
        
        records = leaderboard_df.to_dicts()
        
        output_data = {"last_updated": file_date, "models": records}
        
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        print(f"  ✅ Successfully scraped LM Arena data, saved to data/rank_data.json")
    else:
        print("  ❌ Failed to extract data.")
        print("\n❌ DATA REFRESH FAILED")
        sys.exit(1)