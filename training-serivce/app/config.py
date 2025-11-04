# training-service/app/config.py
import os

class Settings:
    DATA_DIR = os.getenv('DATA_DIR', './data')
    OUTPUT_DIR = os.getenv('OUTPUT_DIR', './outputs')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
