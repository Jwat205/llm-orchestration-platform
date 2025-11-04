import asyncio
from app.core.ml_engine import ModelManager
from app.models.chat import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, Usage
import structlog
import httpx

logger = structlog.get_logger()

async def generate_completion(req: ChatCompletionRequest) -> ChatCompletionResponse:
    """
    Synchronous-inference wrapper that runs in threadpool.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_generate, req)

async def log_to_billing(user_id: int, model: str, tokens: int):
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://django-service/api/billing/log/",
            json={"user": user_id, "model": model, "tokens": tokens},
        )

async def generate_completion_stream(req: ChatCompletionRequest):
    """
    Streamed inference, yields ChatCompletionChunk.
    """
    # For simplicity, call sync and split
    resp = await generate_completion(req)
    # In real streaming, chunk by chunk
    from ...models.chat import ChatCompletionChunk
    yield ChatCompletionChunk(**resp.dict())


def build_prompt(messages):
    # For DialoGPT, just join messages
    return "\n".join(msg.content if hasattr(msg, "content") else msg["content"] for msg in messages)

def _sync_generate(req: ChatCompletionRequest) -> ChatCompletionResponse:
    mgr = ModelManager()
    tokenizer = mgr.get_tokenizer()
    model = mgr.get_model()
    prompt = build_prompt(req.messages)
    inputs = tokenizer(prompt, return_tensors="pt").to(mgr.get_device())
    outputs = model.generate(
        **inputs,
        max_length=(req.max_tokens or 50) + inputs.input_ids.size(1),
        temperature=req.temperature or 1.0,
        pad_token_id=tokenizer.eos_token_id
    )
    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    reply = text[len(prompt):].strip() if text.startswith(prompt) else text.strip()
    print("Generated text:", reply)
    choice = ChatCompletionChoice(index=0, message={"role": "assistant", "content": reply}, finish_reason="stop")
    usage = Usage(
        prompt_tokens=inputs.input_ids.size(1),
        completion_tokens=len(outputs[0]),
        total_tokens=inputs.input_ids.size(1) + len(outputs[0])
    )
    return ChatCompletionResponse(
        id="chatcmpl-1",
        object="chat.completion",
        created=int(__import__('time').time()),
        model=mgr.get_model_name(),
        choices=[choice],
        usage=usage
    )