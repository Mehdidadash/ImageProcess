"""Scan a folder and count occurrences of folder/file names that end with a type suffix like _S1, _S2, _SX, _F1, etc.

Writes a CSV to C:/Users/DTA-image/Documents/ImageProcess/type_counts.csv

Usage: python count_types.py
"""
import re
import os
import csv
from collections import Counter

SOURCE_DIR = r"C:\Users\DTA-image\Documents\old proccess"
OUT_CSV = r"C:\Users\DTA-image\Documents\ImageProcess\type_counts.csv"

# regex to match trailing _TYPE (e.g., _S1, _S2, _SX, _F1, _F2, _F3)
TYPE_RE = re.compile(r"_([A-Za-z0-9]+)$")
KNOWN_TYPES = {"SX", "S1", "S2", "F1", "F2", "F3"}


def scan_and_count(source_dir):
    counts = Counter()
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"Source folder not found: {source_dir}")

    # Walk only top-level entries (folders/files) in the source_dir
    for name in os.listdir(source_dir):
        full = os.path.join(source_dir, name)
        # We only need the name (folder or file)
        m = TYPE_RE.search(name)
        if m:
            t = m.group(1).upper()
            if t in KNOWN_TYPES:
                counts[t] += 1
            else:
                counts['FAILED'] += 1
        else:
            counts['FAILED'] += 1
    return counts


def write_csv(counts, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Type', 'Count'])
        for t, c in sorted(counts.items()):
            writer.writerow([t, c])


if __name__ == '__main__':
    try:
        counts = scan_and_count(SOURCE_DIR)
        write_csv(counts, OUT_CSV)
        print(f"Wrote counts to: {OUT_CSV}")
    except Exception as e:
        print(f"Error: {e}")
