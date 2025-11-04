"""
LLM Endpoints for API v1
Handles text completion and chat completion requests
"""

import uuid
import time
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator
import json
import asyncio
import structlog

from ..models import (
    CompletionRequest, CompletionResponse, ChatCompletionRequest,
    ChatCompletionResponse, ModelsResponse, StreamingResponse as StreamingResponseModel,
    Choice, ChatChoice, Usage, Message, MessageRole, ModelInfo, ErrorResponse
)

from ....core.model_manager import model_manager

logger = structlog.get_logger()

router = APIRouter()


async def get_llm_service():
    """Dependency to get LLM service"""
    return model_manager


@router.post("/completions", response_model=CompletionResponse)
async def create_completion(
    request: CompletionRequest,
    llm_service = Depends(get_llm_service)
) -> CompletionResponse:
    """
    Create a text completion using local models

    This endpoint generates text completions based on the provided prompt.
    """
    try:
        # Generate unique completion ID
        completion_id = f"cmpl-{uuid.uuid4().hex[:16]}"

        logger.info("Generating completion",
                   completion_id=completion_id,
                   model=request.model,
                   prompt_length=len(str(request.prompt)))

        # Use actual model for generation
        prompt_text = request.prompt if isinstance(request.prompt, str) else request.prompt[0]

        generated_text = await llm_service.generate_text(
            model_name=request.model,
            prompt=prompt_text,
            max_tokens=request.max_tokens or 50,
            temperature=request.temperature or 0.7,
            top_p=request.top_p or 0.9,
            top_k=50,
            stop_sequences=request.stop if request.stop else None
        )

        # Calculate token usage (approximate)
        prompt_tokens = len(prompt_text.split())
        completion_tokens = len(generated_text.split())

        response = CompletionResponse(
            id=completion_id,
            object="text_completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    text=generated_text,
                    index=0,
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )

        logger.info("Completion generated successfully",
                   completion_id=completion_id,
                   completion_tokens=completion_tokens)
        return response

    except Exception as e:
        logger.error("Error generating completion",
                    completion_id=completion_id if 'completion_id' in locals() else None,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate completion: {str(e)}")


@router.post("/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    llm_service: Dict[str, Any] = Depends(get_llm_service)
):
    """
    Create a chat completion
    
    This endpoint generates chat completions based on the conversation history.
    Supports both regular and streaming responses.
    """
    try:
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:16]}"
        
        if request.stream:
            return StreamingResponse(
                _generate_chat_stream(request, completion_id),
                media_type="text/plain",
                headers={"X-Completion-ID": completion_id}
            )
        else:
            return await _generate_chat_response(request, completion_id)
            
    except Exception as e:
        logger.error(f"Error generating chat completion: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _generate_chat_response(request: ChatCompletionRequest, completion_id: str) -> ChatCompletionResponse:
    """Generate non-streaming chat response using local models"""

    try:
        # Convert messages to dict format for model manager
        messages_dict = [
            {"role": msg.role.value, "content": msg.content}
            for msg in request.messages
        ]

        logger.info("Generating chat response",
                   completion_id=completion_id,
                   model=request.model,
                   message_count=len(messages_dict))

        # Generate response using model manager
        response_content = await model_manager.generate_chat_response(
            model_name=request.model,
            messages=messages_dict,
            max_tokens=request.max_tokens or 100,
            temperature=request.temperature or 0.7,
            top_p=request.top_p or 0.9,
            top_k=50
        )

        # Calculate token usage (approximate)
        prompt_tokens = sum(len(msg.content.split()) for msg in request.messages)
        completion_tokens = len(response_content.split())

        return ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatChoice(
                    message=Message(
                        role=MessageRole.assistant,
                        content=response_content
                    ),
                    index=0,
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )

    except Exception as e:
        logger.error("Error in chat response generation",
                    completion_id=completion_id,
                    error=str(e))
        raise


async def _generate_chat_stream(request: ChatCompletionRequest, completion_id: str) -> AsyncGenerator[str, None]:
    """Generate streaming chat response"""
    
    # Mock streaming response
    mock_response = "This is a mock streaming response that will be sent in chunks."
    words = mock_response.split()
    
    # Send initial chunk
    initial_chunk = StreamingResponseModel(
        id=completion_id,
        object="chat.completion.chunk",
        created=int(time.time()),
        model=request.model,
        choices=[{
            "index": 0,
            "delta": {"role": "assistant", "content": ""},
            "finish_reason": None
        }]
    )
    yield f"data: {initial_chunk.json()}\n\n"
    
    # Send word chunks
    for word in words:
        chunk = StreamingResponseModel(
            id=completion_id,
            object="chat.completion.chunk",
            created=int(time.time()),
            model=request.model,
            choices=[{
                "index": 0,
                "delta": {"content": f"{word} "},
                "finish_reason": None
            }]
        )
        yield f"data: {chunk.json()}\n\n"
        await asyncio.sleep(0.1)  # Simulate streaming delay
    
    # Send final chunk
    final_chunk = StreamingResponseModel(
        id=completion_id,
        object="chat.completion.chunk",
        created=int(time.time()),
        model=request.model,
        choices=[{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    )
    yield f"data: {final_chunk.json()}\n\n"
    yield "data: [DONE]\n\n"


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    llm_service = Depends(get_llm_service)
) -> ModelsResponse:
    """
    List available local models

    Returns a list of available language models for text and chat completions.
    """
    try:
        # Get actual available models from model manager
        available_models = llm_service.get_available_models()
        loaded_models = llm_service.get_loaded_models()

        models = []
        for model_name in available_models:
            models.append(ModelInfo(
                id=model_name,
                object="model",
                created=int(time.time()),
                owned_by="local",
                permission=[],
                root=model_name,
                parent=None
            ))

        logger.info("Listed models",
                   available_count=len(available_models),
                   loaded_count=len(loaded_models),
                   loaded_models=loaded_models)

        return ModelsResponse(
            object="list",
            data=models
        )

    except Exception as e:
        logger.error("Error listing models", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models/{model_id}", response_model=ModelInfo)
async def get_model(
    model_id: str,
    llm_service: Dict[str, Any] = Depends(get_llm_service)
) -> ModelInfo:
    """
    Get specific model information
    
    Returns detailed information about a specific model.
    """
    try:
        # Mock model lookup - replace with actual model service
        models_data = {
            "gpt-3.5-turbo": ModelInfo(
                id="gpt-3.5-turbo",
                object="model",
                created=int(time.time()),
                owned_by="openai",
                provider="openai",
                capabilities=["chat", "completion"],
                context_length=4096,
                description="GPT-3.5 Turbo model for chat and text completion"
            ),
            "claude-2": ModelInfo(
                id="claude-2",
                object="model",
                created=int(time.time()),
                owned_by="anthropic",
                provider="anthropic",
                capabilities=["chat", "completion"],
                context_length=100000,
                description="Claude 2 model for extended conversations"
            ),
            "llama-2-7b": ModelInfo(
                id="llama-2-7b",
                object="model",
                created=int(time.time()),
                owned_by="meta",
                provider="local",
                capabilities=["chat", "completion"],
                context_length=2048,
                description="Local Llama 2 7B model"
            )
        }
        
        if model_id not in models_data:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return models_data[model_id]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model {model_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")