# training-service/app/main.py
from fastapi import FastAPI, HTTPException
from trainers.lora_trainer import LoRATrainer
from trainers.full_trainer import FullTrainer
from trainers.qlora_trainer import QLoRATrainer
from shared.schemas.training import TrainingRequest

app = FastAPI()

@app.post("/train/lora")
def train_lora(request: TrainingRequest):
    trainer = LoRATrainer()
    try:
        return trainer.train(request.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/train/full")
def train_full(request: TrainingRequest):
    trainer = FullTrainer()
    try:
        return trainer.train(request.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/train/qlora")
def train_qlora(request: TrainingRequest):
    trainer = QLoRATrainer()
    try:
        return trainer.train(request.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))