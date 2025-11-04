# training-service/app/utils/validation.py

def validate_config(config: dict) -> bool:
    required = ['data_path', 'batch_size', 'learning_rate', 'epochs']
    for key in required:
        if key not in config:
            return False
    if config['batch_size'] <= 0 or config['learning_rate'] <= 0 or config['epochs'] <= 0:
        return False
    return True
