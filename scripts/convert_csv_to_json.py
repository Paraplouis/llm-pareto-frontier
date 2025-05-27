#!/usr/bin/env python3
import csv
import json

def convert_csv_to_json():
    """Convert LLM Arena CSV data to JSON format"""
    # Read the CSV file
    with open('lmsys_latest.csv', 'r') as f:
        reader = csv.DictReader(f)
        data = []
        for row in reader:
            # Convert to the format expected by the project
            data.append({
                'Rank (UB)': int(row['rank']),
                'Rank (Style Control)': int(row['rank_stylectrl']),
                'Model': row['model'],
                'Score': int(row['arena_score']),
                '95% CI (±)': row['95_pct_ci'],
                'Votes': row['votes'],
                'Organization': row['organization'],
                'License': row['license']
            })

    # Write to JSON file with proper UTF-8 encoding and ensure_ascii=False to preserve Unicode
    with open('data/rank_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f'✅ Converted {len(data)} models to JSON format')

if __name__ == "__main__":
    convert_csv_to_json() 