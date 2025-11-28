import csv
import os
import sys
import urllib.request
from pathlib import Path

# Configuration
DATASET_URL = "https://huggingface.co/datasets/tensonaut/EPSTEIN_FILES_20K/resolve/main/EPS_FILES_20K_NOV2025.csv"
OUTPUT_DIR = Path("./data/documents/epstein")

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}...")
    try:
        urllib.request.urlretrieve(url, dest_path)
        print("Download complete.")
    except Exception as e:
        print(f"Download failed: {e}")
        raise

def ingest_csv(csv_path, output_dir):
    print(f"Ingesting from {csv_path}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    count = 0
    # Increase field size limit for large text fields
    csv.field_size_limit(sys.maxsize)
    
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        
        # Print field names to debug
        print(f"CSV Field names: {reader.fieldnames}")
        
        # Try to identify the content column
        content_col = None
        candidates = ['text', 'content', 'body', 'document', 'file_content']
        
        for col in reader.fieldnames:
            if col.lower() in candidates:
                content_col = col
                break
        
        if not content_col:
            # Fallback: use the last column or the longest one? 
            # Let's just use the first one that looks like text if we can't find a name
            # But for now, let's assume one of the candidates works or we'll inspect the first row
            print(f"Could not identify content column from {reader.fieldnames}. Using 'text' as default.")
            content_col = 'text'

        for row in reader:
            try:
                content = row.get(content_col, "")
                if not content and 'text' in row: # Fallback
                     content = row['text']
                
                if not content:
                    continue
                    
                # Create a filename
                # If there's a filename column, use it, otherwise generate one
                filename = row.get('filename', f"doc_{count:05d}.txt")
                # Clean filename
                filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
                if not filename.endswith('.txt'):
                    filename += '.txt'
                
                file_path = output_dir / filename
                
                # Write content
                with open(file_path, 'w', encoding='utf-8') as out_f:
                    out_f.write(content)
                
                count += 1
                if count % 100 == 0:
                    print(f"Processed {count} documents...", end='\r')
                    
            except Exception as e:
                print(f"Error processing row {count}: {e}")
                
    print(f"\nIngestion complete. {count} documents saved to {output_dir}")

def main():
    # Create temporary dir for download
    temp_dir = Path("./data/temp_ingest")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = temp_dir / "dataset.csv"
    
    try:
        if not csv_path.exists():
            download_file(DATASET_URL, csv_path)
        
        ingest_csv(csv_path, OUTPUT_DIR)
        
        # Cleanup
        # csv_path.unlink()
        # temp_dir.rmdir()
        print("Cleanup skipped for debugging. You can remove ./data/temp_ingest manually.")
        
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
