# shared/functions/file_operations.py
import os

def list_files(path: str) -> list:
    return os.listdir(path)

def read_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()