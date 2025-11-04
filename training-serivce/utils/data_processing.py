# training-service/app/utils/data_processing.py
from datasets import load_dataset
import os

def validate_and_process(data_path: str):
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Dataset path {data_path} does not exist")
    ext = os.path.splitext(data_path)[1].lower()
    if ext == '.csv':
        ds = load_dataset('csv', data_files={'train': data_path})['train']
    elif ext in ['.json', '.jsonl']:
        ds = load_dataset('json', data_files={'train': data_path})['train']
    else:
        raise ValueError("Unsupported dataset format. Use CSV or JSON")
    return ds