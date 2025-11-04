from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class TrainingRequest(BaseModel):
    data_path: str
    hyperparams: Dict[str, Any] = Field(..., description="Training hyperparameters and scheduler settings")
    resume: Optional[bool] = Field(False, description="Whether to resume from checkpoint")

class TrainingStatus(BaseModel):
    job_id: int
    status: str

class TrainingMetrics(BaseModel):
    metrics: Dict[str, float]

class DatasetInfo(BaseModel):
    id: int
    name: str
    uploaded_at: str

class HyperparameterConfigSchema(BaseModel):
    name: str
    parameters: Dict[str, Any]
