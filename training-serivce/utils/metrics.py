# training-service/app/utils/metrics.py
import math
import torch

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    shift_logits = logits[..., :-1, :].reshape(-1, logits.shape[-1])
    shift_labels = labels[..., 1:].reshape(-1)
    loss_fct = torch.nn.CrossEntropyLoss()
    loss = loss_fct(shift_logits, shift_labels)
    ppl = math.exp(loss.item())
    return {'loss': loss.item(), 'perplexity': ppl}