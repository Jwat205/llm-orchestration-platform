# django-service/apps/training/tasks.py
from celery import shared_task
from .models import TrainingJob
from .training_utils import prepare_data, start_training

@shared_task
def run_training_job(job_id):
    job = TrainingJob.objects.get(id=job_id)
    job.status = 'running'
    job.save()
    data = prepare_data(job.dataset.file.path)
    metrics = start_training(data, job.hyperparams.parameters, resume=True)
    job.metrics = metrics
    job.status = 'completed'
    job.save()