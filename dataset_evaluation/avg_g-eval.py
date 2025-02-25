import pandas as pd
from pathlib import Path

g_eval_dir = Path(__file__).parent / 'g_eval_scores'
all_scores = []

for csv_file in g_eval_dir.glob('*.csv'):
    df = pd.read_csv(csv_file)
    # Exclude the "Question ID" column.
    df_scores = df.drop(columns=['Question ID'])
    print(csv_file.name)
    print(df_scores.mean())
    all_scores.append(df_scores)

# Concatenate all DataFrames, aligning columns by name.
combined_df = pd.concat(all_scores, axis=0, ignore_index=True)

# Calculate the average and standard deviation, handling missing columns.
avg_scores = combined_df.mean(skipna=True)
variation = combined_df.std(skipna=True)

print("Overall Average Scores Across All CSVs:")
print(avg_scores)
print("Overall Variations (std) Across All CSVs:")
print(variation)