import polars as pl
import json
from pathlib import Path
import re
from huggingface_hub import HfApi, hf_hub_download
import pandas as pd
import pickle
from datetime import datetime
import sys
import requests

def _clean_html(html_string: str) -> str:
    """Removes HTML tags from a string."""
    if not isinstance(html_string, str):
        return html_string
    return re.sub(r'<.*?>', '', html_string)


def get_latest_elo_file_date(repo_id="lmarena-ai/lmarena-leaderboard"):
    """
    Get the latest elo_results_*.pkl file date from the repository.
    """
    try:
        print(f"  ↳ Checking for latest elo_results_*.pkl files in {repo_id}...")
        
        api = HfApi()
        
        # Get repository information
        repo_info = api.repo_info(repo_id=repo_id, repo_type="space")
        
        # Get the latest commit sha
        latest_commit = repo_info.sha
        
        # List files in the repository
        files = api.list_repo_files(repo_id=repo_id, repo_type="space")
        
        # Find all elo_results_*.pkl files
        elo_files = [f for f in files if f.startswith('elo_results_') and f.endswith('.pkl')]
        
        # Also look for leaderboard_table_*.csv files as fallback
        csv_files = [f for f in files if f.startswith('leaderboard_table_') and f.endswith('.csv')]
        
        if not elo_files and not csv_files:
            print("  ❌ No elo_results_*.pkl or leaderboard_table_*.csv files found in repository")
            return None
            
        # Extract dates from filenames and find the latest
        latest_date = None
        latest_file = None
        file_type = None
        
        # Check pkl files first (preferred)
        for file in elo_files:
            # Extract date from filename like elo_results_20250801.pkl
            match = re.search(r'elo_results_(\d{8})\.pkl', file)
            if match:
                date_str = match.group(1)
                # Convert to datetime for comparison
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if latest_date is None or file_date > latest_date:
                    latest_date = file_date
                    latest_file = file
                    file_type = 'pkl'
        
        # Check CSV files as fallback
        for file in csv_files:
            # Extract date from filename like leaderboard_table_20250801.csv
            match = re.search(r'leaderboard_table_(\d{8})\.csv', file)
            if match:
                date_str = match.group(1)
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if latest_date is None or file_date > latest_date:
                    latest_date = file_date
                    latest_file = file
                    file_type = 'csv'
        
        if latest_file:
            print(f"  ↳ Latest file found: {latest_file} ({file_type}) (date: {latest_date.strftime('%Y-%m-%d')})")
            return latest_file, latest_date.strftime('%Y-%m-%d'), file_type
        else:
            print("  ❌ No valid elo_results_*.pkl or leaderboard_table_*.csv files with date patterns found")
            return None
            
    except Exception as e:
        print(f"  ❌ Error checking for latest elo file: {e}")
        return None


def check_if_update_needed():
    """
    Check if we need to update data based on comparing current data date with latest available.
    """
    try:
        # Get current data date
        current_data_path = Path(__file__).parent.parent / "data" / "rank_data.json"
        current_date = None
        
        if current_data_path.exists():
            with open(current_data_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
                current_date = current_data.get('last_updated')
        
        # Get latest available date
        latest_info = get_latest_elo_file_date()
        if not latest_info:
            return False, None, None, None
            
        latest_file, latest_date, file_type = latest_info
        
        if current_date:
            current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
            
            if latest_dt > current_dt:
                print(f"  ↳ New data available: {latest_date} (current: {current_date})")
                return True, latest_file, latest_date, file_type
            else:
                print(f"  ↳ Data is up to date: {current_date}")
                return False, latest_file, latest_date, file_type
        else:
            print("  ↳ No current data found, will download latest")
            return True, latest_file, latest_date, file_type
            
    except Exception as e:
        print(f"  ❌ Error checking update status: {e}")
        return False, None, None, None


def download_and_process_elo_file(filename, repo_id="lmarena-ai/lmarena-leaderboard"):
    """
    Download and process an elo_results_*.pkl file from the repository.
    """
    try:
        print(f"  ↳ Downloading {filename} from {repo_id}...")
        
        # Download the file
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="space"
        )
        
        print(f"  ↳ Processing {filename}...")
        
        # Load the pickle file with error handling for Plotly objects
        with open(file_path, 'rb') as f:
            try:
                data = pickle.load(f)
            except Exception as e:
                print(f"  ↳ Warning: Error loading pickle file directly: {e}")
                # Try to load with a different approach
                f.seek(0)
                try:
                    # Read the file in binary mode and try to extract basic data
                    data = pickle.load(f)
                except Exception as e2:
                    print(f"  ❌ Unable to load pickle file: {e2}")
                    return None
        
        # The data structure might vary, let's inspect it carefully
        print(f"  ↳ Data type: {type(data)}")
        
        df_pd = None
        
        if isinstance(data, dict):
            print(f"  ↳ Available keys in data: {list(data.keys())}")
            
            # Look for common data structures
            possible_keys = [
                'leaderboard_table_df', 
                'elo_rating_final', 
                'leaderboard_table', 
                'results',
                'elo_results',
                'final_results'
            ]
            
            for key in possible_keys:
                if key in data:
                    print(f"  ↳ Found data under key: {key}")
                    try:
                        if key == 'elo_rating_final':
                            # Handle elo_rating_final structure
                            elo_data = data[key]
                            records = []
                            
                            for model, rating_data in elo_data.items():
                                if isinstance(rating_data, dict):
                                    # Extract rating information
                                    rating = rating_data.get('rating', rating_data.get('elo', 0))
                                    num_battles = rating_data.get('num_battles', rating_data.get('votes', 0))
                                    
                                    records.append({
                                        'Model': str(model),
                                        'Score': int(float(rating)) if rating else 0,
                                        'Votes': int(num_battles) if num_battles else 0,
                                        'organization': 'Unknown'  # We'll need to map this later
                                    })
                                
                            df_pd = pd.DataFrame(records)
                            break
                            
                        elif hasattr(data[key], 'to_pandas') or hasattr(data[key], 'to_dict'):
                            # Handle DataFrame-like objects
                            if hasattr(data[key], 'to_pandas'):
                                df_pd = data[key].to_pandas()
                            elif hasattr(data[key], 'to_dict'):
                                dict_data = data[key].to_dict()
                                df_pd = pd.DataFrame(dict_data)
                            break
                            
                        elif isinstance(data[key], pd.DataFrame):
                            df_pd = data[key]
                            break
                            
                        elif isinstance(data[key], dict):
                            # Try to convert dict to DataFrame
                            try:
                                df_pd = pd.DataFrame(data[key])
                                break
                            except:
                                continue
                                
                    except Exception as e:
                        print(f"  ↳ Error processing {key}: {e}")
                        continue
            
            # If we still don't have data, try to look for CSV-like data
            if df_pd is None:
                for key, value in data.items():
                    if isinstance(value, str) and 'leaderboard_table' in key.lower():
                        # Try to find CSV data referenced in the file
                        csv_filename = value if value.endswith('.csv') else f"{value}.csv"
                        try:
                            csv_path = hf_hub_download(
                                repo_id=repo_id,
                                filename=csv_filename,
                                repo_type="space"
                            )
                            df_pd = pd.read_csv(csv_path)
                            print(f"  ↳ Loaded data from CSV: {csv_filename}")
                            break
                        except:
                            continue
                            
        else:
            print(f"  ↳ Unexpected data format: {type(data)}")
            return None
        
        if df_pd is None or df_pd.empty:
            print("  ❌ No valid data found in the pickle file")
            return None
        
        print(f"  ↳ DataFrame shape: {df_pd.shape}")
        print(f"  ↳ DataFrame columns: {list(df_pd.columns)}")
        
        # Clean HTML from model names
        if 'Model' in df_pd.columns:
            df_pd['Model'] = df_pd['Model'].apply(_clean_html)
        elif 'model' in df_pd.columns:
            df_pd = df_pd.rename(columns={'model': 'Model'})
            df_pd['Model'] = df_pd['Model'].apply(_clean_html)
        
        # Convert to Polars DataFrame
        df = pl.from_pandas(df_pd)
        
        # Ensure we have the required columns with flexible mapping
        required_columns = ["Model", "Score", "Votes", "organization"]
        available_columns = df.columns
        
        print(f"  ↳ Available columns: {available_columns}")
        
        # Map column names if they're different
        column_mapping = {}
        for col in required_columns:
            if col not in available_columns:
                # Try to find similar column names
                possible_names = {
                    'Score': ['score', 'elo', 'rating', 'arena_score', 'Arena Score'],
                    'Votes': ['votes', 'num_battles', 'battles', 'count'],
                    'organization': ['organization', 'org', 'company', 'provider', 'Organization'],
                    'Model': ['model', 'name', 'model_name', 'Model']
                }
                
                if col in possible_names:
                    for possible_name in possible_names[col]:
                        if possible_name in available_columns:
                            column_mapping[possible_name] = col
                            break
        
        if column_mapping:
            print(f"  ↳ Column mapping: {column_mapping}")
            df = df.rename(column_mapping)
        
        # Select only the columns we need (that exist)
        final_columns = [col for col in required_columns if col in df.columns]
        df = df.select(final_columns)
        
        # Add missing columns with default values
        for col in required_columns:
            if col not in df.columns:
                if col == 'organization':
                    df = df.with_columns(pl.lit('Unknown').alias('organization'))
                elif col == 'Votes':
                    df = df.with_columns(pl.lit(0).alias('Votes'))
                elif col == 'Score':
                    df = df.with_columns(pl.lit(1000).alias('Score'))
        
        print(f"  ↳ Processed {len(df)} models from {filename}")
        return df
        
    except Exception as e:
        print(f"  ❌ Error downloading/processing {filename}: {e}")
        import traceback
        traceback.print_exc()
        return None


def download_and_process_csv_file(filename, repo_id="lmarena-ai/lmarena-leaderboard"):
    """
    Download and process a leaderboard_table_*.csv file from the repository.
    """
    try:
        print(f"  ↳ Downloading {filename} from {repo_id}...")
        
        # Download the file
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="space"
        )
        
        print(f"  ↳ Processing {filename}...")
        
        # Load the CSV file
        df_pd = pd.read_csv(file_path)
        
        print(f"  ↳ CSV shape: {df_pd.shape}")
        print(f"  ↳ CSV columns: {list(df_pd.columns)}")
        
        # Clean HTML from model names if needed
        if 'Model' in df_pd.columns:
            df_pd['Model'] = df_pd['Model'].apply(_clean_html)
        elif 'model' in df_pd.columns:
            df_pd = df_pd.rename(columns={'model': 'Model'})
            df_pd['Model'] = df_pd['Model'].apply(_clean_html)
        
        # Convert to Polars DataFrame
        df = pl.from_pandas(df_pd)
        
        # Ensure we have the required columns with flexible mapping
        required_columns = ["Model", "Score", "Votes", "organization"]
        available_columns = df.columns
        
        print(f"  ↳ Available columns: {available_columns}")
        
        # Map column names if they're different
        column_mapping = {}
        for col in required_columns:
            if col not in available_columns:
                # Try to find similar column names
                possible_names = {
                    'Score': ['score', 'elo', 'rating', 'arena_score', 'Arena Score'],
                    'Votes': ['votes', 'num_battles', 'battles', 'count'],
                    'organization': ['organization', 'org', 'company', 'provider', 'Organization'],
                    'Model': ['model', 'name', 'model_name', 'Model']
                }
                
                if col in possible_names:
                    for possible_name in possible_names[col]:
                        if possible_name in available_columns:
                            column_mapping[possible_name] = col
                            break
        
        if column_mapping:
            print(f"  ↳ Column mapping: {column_mapping}")
            df = df.rename(column_mapping)
        
        # Select only the columns we need (that exist)
        final_columns = [col for col in required_columns if col in df.columns]
        df = df.select(final_columns)
        
        # Add missing columns with default values
        for col in required_columns:
            if col not in df.columns:
                if col == 'organization':
                    df = df.with_columns(pl.lit('Unknown').alias('organization'))
                elif col == 'Votes':
                    df = df.with_columns(pl.lit(0).alias('Votes'))
                elif col == 'Score':
                    df = df.with_columns(pl.lit(1000).alias('Score'))
        
        print(f"  ↳ Processed {len(df)} models from {filename}")
        return df
        
    except Exception as e:
        print(f"  ❌ Error downloading/processing {filename}: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_latest_leaderboard_df():
    """
    Main function to fetch the latest leaderboard data using the new strategy.
    """
    try:
        print("  ↳ Checking for updates in lmarena-ai/lmarena-leaderboard...")
        
        # Check if we need to update
        needs_update, latest_file, latest_date, file_type = check_if_update_needed()
        
        if not needs_update:
            print("  ✅ Data is already up to date")
            return None, latest_date
        
        if not latest_file:
            print("  ❌ No elo files found to download")
            return None, None
        
        # Download and process the latest file
        if file_type == 'pkl':
            df = download_and_process_elo_file(latest_file)
        elif file_type == 'csv':
            df = download_and_process_csv_file(latest_file)
        else:
            print(f"  ❌ Unknown file type: {file_type}")
            return None, None
        
        if df is not None:
            print("  ✅ Successfully downloaded and processed latest data")
            return df, latest_date
        else:
            print("  ❌ Failed to process downloaded data, trying CSV fallback...")
            # If pickle processing failed, try CSV processing as a fallback
            if file_type == 'pkl':
                # Look for corresponding CSV file (elo_results_20250801.pkl -> leaderboard_table_20250801.csv)
                import re
                match = re.search(r'elo_results_(\d{8})\.pkl', latest_file)
                if match:
                    date_str = match.group(1)
                    csv_filename = f"leaderboard_table_{date_str}.csv"
                    print(f"  ↳ Trying CSV fallback: {csv_filename}")
                    df = download_and_process_csv_file(csv_filename)
                    if df is not None:
                        print("  ✅ Successfully processed CSV fallback data")
                        return df, latest_date
                
                print("  ❌ Failed to process CSV fallback data")
                return None, None
            else:
                print("  ❌ Failed to process downloaded data")
                return None, None
            
    except Exception as e:
        print(f"  ❌ An error occurred: {e}")
        return None, None


if __name__ == '__main__':
    leaderboard_df, file_date = fetch_latest_leaderboard_df()
    if leaderboard_df is not None:
        output_path = Path(__file__).parent.parent / "data" / "rank_data.json"
        
        records = leaderboard_df.to_dicts()
        
        output_data = {"last_updated": file_date, "models": records}
        
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        print(f"  ✅ Successfully updated LM Arena data, saved to data/rank_data.json")
    else:
        # If no update was needed, that's also success
        needs_update, _, _, _ = check_if_update_needed()
        if not needs_update:
            print("  ✅ No update needed - data is current")
        else:
            print("  ❌ Failed to extract data.")
            print("\n❌ DATA REFRESH FAILED")
            sys.exit(1)