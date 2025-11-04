# training-service/app/trainers/full_trainer.py
from transformers import Trainer, TrainingArguments, AutoModelForCausalLM, AutoTokenizer
from ..utils.validation import validate_config
from ..utils.data_processing import validate_and_process
from ..utils.metrics import compute_metrics
from ..config import Settings

class FullTrainer:
    def train(self, config: dict) -> dict:
        if not validate_config(config):
            raise ValueError("Invalid hyperparameter configuration")
        dataset = validate_and_process(config['data_path'])
        model_name = config.get('base_model', 'gpt2')
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)
        def tokenize_fn(examples):
            return tokenizer(examples['text'], padding='max_length', truncation=True, max_length=config.get('max_length',512))
        dataset = dataset.map(tokenize_fn, batched=True)
        args = TrainingArguments(
            output_dir=Settings.OUTPUT_DIR+'/full',
            per_device_train_batch_size=config['batch_size'],
            learning_rate=config['learning_rate'],
            num_train_epochs=config['epochs'],
            logging_steps=config.get('logging_steps',50),
            evaluation_strategy='steps',
            eval_steps=config.get('eval_steps',100),
            save_total_limit=2,
            load_best_model_at_end=True
        )
        trainer = Trainer(model=model, args=args, train_dataset=dataset, eval_dataset=dataset, compute_metrics=compute_metrics)
        trainer.train()
        return {'status':'completed','metrics':trainer.evaluate()}