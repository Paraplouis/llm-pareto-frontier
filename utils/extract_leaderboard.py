import pandas as pd
import json
from pathlib import Path
import pickle
from huggingface_hub import hf_hub_download
from huggingface_hub.utils import HfHubHTTPError
import re


def fetch_latest_leaderboard_df():
    """
    Fetches the latest leaderboard data from the Hugging Face Space.

    This function finds the most recent elo_results_*.pkl file,
    downloads it, and extracts the leaderboard DataFrame.

    Returns:
        pandas.DataFrame: The latest leaderboard data, or None if fetching fails.
    """
    try:
        repo_id = "lmarena-ai/chatbot-arena-leaderboard"
        from huggingface_hub import list_repo_files

        all_files = list_repo_files(repo_id, repo_type="space")
        
        elo_files = [f for f in all_files if f.startswith("elo_results_") and f.endswith(".pkl")]
        
        if not elo_files:
            print("No elo_results_*.pkl files found in the repository.")
            return None
            
        latest_file = sorted(elo_files, key=lambda x: re.search(r"(\d{8}|\d{4})", x).group(0), reverse=True)[0]
        print(f"Found latest leaderboard file: {latest_file}")

        downloaded_file_path = hf_hub_download(
            repo_id=repo_id,
            repo_type="space",
            filename=latest_file
        )

        with open(downloaded_file_path, "rb") as f:
            data = pickle.load(f)
        
        # The data structure can vary. Let's find the correct key for the leaderboard.
        df = None
        if "full" in data and "leaderboard_table_df" in data["full"]:
            df = data["full"]["leaderboard_table_df"]
        elif "text" in data and "full" in data["text"] and "leaderboard_table_df" in data["text"]["full"]:
            df = data["text"]["full"]["leaderboard_table_df"]
        elif "text" in data and "leaderboard_table_df" in data["text"]:
            df = data["text"]["leaderboard_table_df"]
        
        if df is not None:
            # The model name is in the index of the DataFrame
            df['Model'] = df.index
            df = df.rename(columns={
                "rating": "Score",
                "num_battles": "Votes",
                "final_ranking": "Rank (UB)",
            })
            df['95% CI'] = df.apply(lambda row: [row['rating_q025'], row['rating_q975']], axis=1)
            df['Score'] = pd.to_numeric(df['Score'], errors='coerce')
            df['Votes'] = pd.to_numeric(df['Votes'], errors='coerce')

            print("Data fetched and processed successfully.")
            return df
        else:
            print("Could not find 'leaderboard_table_df' in the pickle file.")
            # For debugging, print the structure if we can't find the data
            print("DEBUG: Pickle file keys:", data.keys())
            for key in data.keys():
                if isinstance(data[key], dict):
                    print(f"DEBUG: Keys in data['{key}']:", data[key].keys())
            return None

    except HfHubHTTPError as e:
        print(f"HTTP Error fetching file list from Hugging Face Hub: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == '__main__':
    leaderboard_df = fetch_latest_leaderboard_df()
    if leaderboard_df is not None:
        output_path = Path(__file__).parent.parent / "data" / "rank_data.json"
        
        records = leaderboard_df.to_dict(orient='records')
        
        with open(output_path, "w") as f:
            json.dump(records, f, indent=2)
        print(f"✅ Successfully scraped and processed LLM Arena data")
    else:
        print("Failed to extract data.") 