from datasets import load_dataset
from transformers import Trainer, TrainingArguments, AutoModelForCausalLM, AutoTokenizer
from .models import HyperparameterConfig


def prepare_data(file_path: str):
    """Validate file and load as HuggingFace dataset."""
    if file_path.endswith('.csv'):
        ds = load_dataset('csv', data_files={'train': file_path})['train']
    elif file_path.endswith(('.json', '.jsonl')):
        ds = load_dataset('json', data_files={'train': file_path})['train']
    else:
        raise ValueError("Unsupported dataset format")
    return ds


def start_training(dataset, hyperparams: dict, resume: bool = False) -> dict:
    model_name = hyperparams.get('base_model', 'gpt2')
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(model_name)

    def tokenize_fn(examples):
        return tokenizer(examples['text'], truncation=True, padding='max_length', max_length=hyperparams.get('max_length', 512))

    dataset = dataset.map(tokenize_fn, batched=True)
    training_args = TrainingArguments(
        output_dir=hyperparams.get('output_dir', f"./outputs/{model_name}"),
        evaluation_strategy=hyperparams.get('evaluation_strategy', 'steps'),
        per_device_train_batch_size=hyperparams.get('batch_size', 8),
        learning_rate=hyperparams.get('learning_rate', 5e-5),
        num_train_epochs=hyperparams.get('epochs', 3),
        weight_decay=hyperparams.get('weight_decay', 0.0),
        logging_steps=hyperparams.get('logging_steps', 50),
        save_steps=hyperparams.get('save_steps', 200),
        load_best_model_at_end=True
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        eval_dataset=dataset
    )
    trainer.train(resume_from_checkpoint=resume)
    return trainer.evaluate()
