"""
Fuzzy Matching Script for Provider Deduplication
JS Construcciones Data Architecture Project

This script identifies potential duplicate providers using fuzzy string matching.
It compares provider names and outputs a list of similar entries for manual review.
"""

import pandas as pd
from rapidfuzz import fuzz

def normalize(text: str) -> str:
    """Normalize text for comparison: uppercase and trim whitespace."""
    return str(text).upper().strip()

def find_duplicates(df: pd.DataFrame, column: str, threshold: int = 80) -> pd.DataFrame:
    """
    Find potential duplicates in a DataFrame column using fuzzy matching.
    
    Args:
        df: DataFrame containing the data
        column: Name of the column to check for duplicates
        threshold: Minimum similarity percentage (0-100) to consider as duplicate
    
    Returns:
        DataFrame with potential duplicate pairs and their similarity scores
    """
    # Get unique values
    values = df[column].dropna().unique().tolist()
    
    duplicates = []
    
    for i, val1 in enumerate(values):
        for val2 in values[i+1:]:
            score = fuzz.ratio(normalize(val1), normalize(val2))
            if score >= threshold:
                duplicates.append({
                    'Value1': val1,
                    'Value2': val2,
                    'Similarity': score
                })
    
    df_duplicates = pd.DataFrame(duplicates)
    
    if not df_duplicates.empty:
        df_duplicates = df_duplicates.sort_values('Similarity', ascending=False)
    
    return df_duplicates

def main():
    # Configuration
    INPUT_FILE = 'DimProveedores.csv'
    COLUMN_NAME = 'NombreProveedor'
    OUTPUT_FILE = 'potential_duplicates.csv'
    THRESHOLD = 80  # Minimum similarity percentage
    
    # Load data
    print(f"Loading data from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    print(f"Total records: {len(df)}")
    
    # Find duplicates
    print(f"\nSearching for duplicates (threshold: {THRESHOLD}%)...")
    df_duplicates = find_duplicates(df, COLUMN_NAME, THRESHOLD)
    
    # Display results
    print(f"\nPotential duplicates found: {len(df_duplicates)}")
    
    if not df_duplicates.empty:
        print("\nTop matches:")
        print(df_duplicates.head(20).to_string(index=False))
        
        # Save to CSV for manual review
        df_duplicates.to_csv(OUTPUT_FILE, index=False)
        print(f"\nFull results saved to: {OUTPUT_FILE}")
    else:
        print("No duplicates found above threshold.")

if __name__ == "__main__":
    main()
