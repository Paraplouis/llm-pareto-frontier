import polars as pl
import json
from pathlib import Path
import pickle
from huggingface_hub import hf_hub_download, list_repo_files
from huggingface_hub.utils import HfHubHTTPError
import re
import requests


def fetch_latest_leaderboard_df():
    """
    Fetches the latest leaderboard data from the Hugging Face Space.

    This function finds the most recent elo_results_*.pkl file,
    downloads it, and extracts the leaderboard DataFrame.
    It also fetches data from the lm-sys/FastChat GitHub repository to
    identify and filter out inactive/deprecated models.

    Returns:
        (pl.DataFrame, str): A tuple containing the leaderboard polars DataFrame and the file date.
    """
    try:
        # Fetch and parse monitor_md.py to find deprecated models
        inactive_models = []
        try:
            url = "https://raw.githubusercontent.com/lm-sys/FastChat/main/fastchat/serve/monitor/monitor_md.py"
            response = requests.get(url)
            response.raise_for_status()
            monitor_content = response.text
            
            match = re.search(r"deprecated_model_name\s*=\s*\[([^\]]+)\]", monitor_content, re.DOTALL)
            if match:
                models_str = match.group(1)
                inactive_models = [model.strip().strip('"\'') for model in models_str.split(',') if model.strip() and not model.startswith("#")]
                print(f"Found {len(inactive_models)} deprecated models to exclude.")
        except Exception as e:
            print(f"Could not fetch or parse monitor_md.py to find deprecated models: {e}")

        repo_id = "lmarena-ai/chatbot-arena-leaderboard"
        
        all_files = list_repo_files(repo_id, repo_type="space")
        
        elo_files = [f for f in all_files if f.startswith("elo_results_") and f.endswith(".pkl")]
        
        if not elo_files:
            print("No elo_results_*.pkl files found in the repository.")
            return None, None
            
        latest_file = sorted(elo_files, key=lambda x: re.search(r"(\d{8}|\d{4})", x).group(0), reverse=True)[0]
        print(f"Found latest leaderboard file: {latest_file}")
        
        # Extract date from filename
        file_date = None
        file_date_match = re.search(r"(\d{8})", latest_file)
        if file_date_match:
            date_str = file_date_match.group(1)
            file_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        downloaded_file_path = hf_hub_download(
            repo_id=repo_id,
            repo_type="space",
            filename=latest_file
        )

        with open(downloaded_file_path, "rb") as f:
            data = pickle.load(f)
        
        # The data structure can vary. Let's find the correct key for the leaderboard.
        df_pd = None
        if "full" in data and "leaderboard_table_df" in data["full"]:
            df_pd = data["full"]["leaderboard_table_df"]
        elif "text" in data and "full" in data["text"] and "leaderboard_table_df" in data["text"]["full"]:
            df_pd = data["text"]["full"]["leaderboard_table_df"]
        elif "text" in data and "leaderboard_table_df" in data["text"]:
            df_pd = data["text"]["leaderboard_table_df"]
        
        if df_pd is not None:
            # The model name is in the index of the pandas DataFrame
            df_pd['Model'] = df_pd.index
            
            # Convert pandas DataFrame to polars DataFrame
            df = pl.from_pandas(df_pd)

            # Filter out inactive models
            if inactive_models:
                initial_count = len(df)
                df = df.filter(~pl.col('Model').is_in(inactive_models))
                print(f"Filtered out {initial_count - len(df)} inactive models.")

            df = df.rename({
                "rating": "Score",
                "num_battles": "Votes",
                "final_ranking": "Rank (UB)",
            })

            df = df.with_columns([
                pl.struct([pl.col('rating_q025'), pl.col('rating_q975')]).alias('95% CI'),
                pl.col('Score').cast(pl.Float64, strict=False),
                pl.col('Votes').cast(pl.Int64, strict=False)
            ])

            print("Data fetched and processed successfully.")
            return df, file_date
        else:
            print("Could not find 'leaderboard_table_df' in the pickle file.")
            # For debugging, print the structure if we can't find the data
            print("DEBUG: Pickle file keys:", data.keys())
            for key in data.keys():
                if isinstance(data[key], dict):
                    print(f"DEBUG: Keys in data['{key}']:", data[key].keys())
            return None, None

    except HfHubHTTPError as e:
        print(f"HTTP Error fetching file list from Hugging Face Hub: {e}")
        return None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None


if __name__ == '__main__':
    leaderboard_df, file_date = fetch_latest_leaderboard_df()
    if leaderboard_df is not None:
        output_path = Path(__file__).parent.parent / "data" / "rank_data.json"
        
        records = leaderboard_df.to_dicts()
        
        output_data = {"last_updated": file_date, "models": records}
        
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"✅ Successfully scraped and processed LM Arena data")
    else:
        print("Failed to extract data.") 