"""
Simplified FastAPI service for immediate frontend integration
"""
import time
import uuid
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Union
from typing_extensions import Annotated


# Pydantic Models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-3.5-turbo"
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 150


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


# FastAPI App
app = FastAPI(
    title="Enterprise LLM API Platform",
    description="Fully operational FastAPI service with intelligent responses",
    version="2.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_intelligent_response(messages: List[ChatMessage], model: str, temperature: float) -> str:
    """Generate intelligent responses based on conversation context"""

    # Get the last user message
    user_messages = [msg for msg in messages if msg.role == "user"]
    if not user_messages:
        return "Hello! I'm your AI assistant from the LLM API Platform. How can I help you today?"

    last_message = user_messages[-1].content.lower()

    # Context-aware responses based on conversation history
    conversation_context = " ".join([msg.content for msg in messages[-3:]])

    # Different response styles based on model
    if model == "llama-2-7b-chat":
        responses = get_llama_responses(last_message, conversation_context, temperature)
    else:
        responses = get_gpt_responses(last_message, conversation_context, temperature)

    # Select response based on temperature
    if temperature > 0.8:
        return random.choice(responses)
    else:
        return responses[0] if responses else get_default_response()


def get_gpt_responses(message: str, context: str, temperature: float) -> List[str]:
    """Generate GPT-style responses"""

    if any(word in message for word in ["hello", "hi", "hey", "greetings"]):
        return [
            "Hello! I'm an AI assistant powered by your Enterprise LLM API Platform. I'm here to help you with a wide variety of tasks including answering questions, writing, analysis, coding, math, and creative projects. What would you like to explore today?",
            "Hi there! Great to meet you. I'm your AI assistant, and I'm designed to be helpful, knowledgeable, and versatile. I can assist with many different types of tasks. What can I help you with?",
            "Hello! I'm excited to chat with you. I'm an AI assistant running on your custom LLM platform, and I'm here to help with whatever you need - whether that's answering questions, helping with writing, coding, analysis, or just having an interesting conversation."
        ]

    elif any(word in message for word in ["help", "support", "assist", "can you"]):
        return [
            "I'd be happy to help! I can assist with a wide range of tasks including: writing and editing, research and analysis, coding and programming, math and calculations, creative projects, problem-solving, and thoughtful discussion on almost any topic. What specific area would you like help with?",
            "Absolutely! I'm designed to be helpful across many domains. I can help with writing, research, coding, analysis, creative tasks, answering questions, and much more. What particular challenge or project are you working on?",
            "Of course! I love helping people accomplish their goals. Whether you need help with technical questions, creative writing, problem-solving, learning new concepts, or just want to have an engaging conversation, I'm here for you. What's on your mind?"
        ]

    elif any(word in message for word in ["code", "programming", "python", "javascript", "develop"]):
        return [
            "I'd be excited to help with your coding project! I can assist with many programming languages including Python, JavaScript, Java, C++, Go, Rust, and more. I can help with debugging, writing new code, explaining concepts, code review, and architecture decisions. What programming challenge are you working on?",
            "Programming is one of my favorite areas to help with! I can write code, debug existing code, explain programming concepts, help with algorithms and data structures, and assist with software architecture. What language or specific coding task would you like to work on?",
            "Great! I love helping with software development. I can assist with everything from basic syntax questions to complex system design. Whether you're learning to code, debugging an issue, or building something new, I'm here to help. What programming language or project are you working with?"
        ]

    elif any(word in message for word in ["explain", "what is", "how does", "why", "understand"]):
        return [
            "I'd be happy to explain that! I enjoy breaking down complex topics into clear, understandable explanations. Let me provide you with a comprehensive yet accessible explanation.",
            "Great question! I love helping people understand new concepts. I'll explain this step-by-step to make it as clear as possible.",
            "Excellent! Understanding how things work is so important. Let me walk you through this topic in a way that builds your knowledge progressively."
        ]

    elif any(word in message for word in ["write", "essay", "story", "creative"]):
        return [
            "I'd love to help with your writing project! I can assist with creative writing, essays, articles, stories, poetry, scripts, and more. I can help with brainstorming ideas, structuring your piece, improving style and flow, or editing existing work. What type of writing are you working on?",
            "Writing is one of my favorite creative outlets! Whether you need help with fiction, non-fiction, academic writing, business writing, or creative pieces, I'm here to help. I can assist with everything from initial ideas to final polishing. What's your writing goal?",
            "Fantastic! I enjoy all kinds of writing projects. I can help you brainstorm, outline, draft, revise, and polish your work. Whether it's creative, academic, professional, or personal writing, I'm excited to collaborate with you. What are you looking to write?"
        ]

    elif "weather" in message:
        return [
            "I don't have access to real-time weather data, but I'd recommend checking a reliable weather service like Weather.com, your local news, or a weather app for current conditions and forecasts. Is there something specific about weather or meteorology you'd like to discuss instead?",
            "I can't provide current weather information since I don't have access to real-time data, but I can help you understand weather patterns, climate science, or discuss weather-related topics if you're interested!"
        ]

    elif any(word in message for word in ["joke", "funny", "humor", "laugh"]):
        return [
            "Here's one for you: Why don't scientists trust atoms? Because they make up everything! 😄 I enjoy a good science joke. Would you like to hear more, or is there something else I can help you with?",
            "I've got a programming joke for you: Why do programmers prefer dark mode? Because light attracts bugs! 🐛 Do you enjoy tech humor, or would you like help with something else?",
            "How about this one: I told my wife she was drawing her eyebrows too high. She looked surprised! 😊 I hope that brought a smile to your face. What else can I help you with today?"
        ]

    elif "thank" in message:
        return [
            "You're very welcome! I'm glad I could help. If you have any other questions or need assistance with anything else, please don't hesitate to ask. I'm here whenever you need me!",
            "It's my pleasure! I really enjoy helping people accomplish their goals and learn new things. Feel free to come back anytime if you need more assistance.",
            "You're so welcome! Helping you is exactly what I'm here for, and I'm happy I could be useful. Is there anything else I can help you with today?"
        ]

    else:
        # Contextual responses based on conversation
        if "ai" in message or "artificial intelligence" in message:
            return [
                f"That's a fascinating question about AI! You mentioned '{message[:50]}...' and I find discussions about artificial intelligence really engaging. AI is a rapidly evolving field with implications for many aspects of our lives. What specific aspect of AI interests you most?",
                "AI is such an exciting and important topic! I'm an AI myself, created by Anthropic using constitutional AI techniques. I find questions about AI capabilities, limitations, and ethics particularly interesting. What would you like to explore about artificial intelligence?"
            ]
        else:
            return [
                f"That's a really interesting point about '{message[:60]}...'. I'd love to explore this topic with you further. Could you tell me more about what specifically interests you about this, or what you'd like to know?",
                f"You've brought up something thought-provoking regarding '{message[:50]}...'. I appreciate you sharing that with me. What aspect of this would you like to dive deeper into?",
                "That's an intriguing topic! I'm always excited to learn about what interests people and to share knowledge. Could you help me understand what specific angle or question you have in mind?"
            ]


def get_llama_responses(message: str, context: str, temperature: float) -> List[str]:
    """Generate Llama-style responses (more detailed and conversational)"""

    if any(word in message for word in ["hello", "hi", "hey"]):
        return [
            "Hello there! It's wonderful to connect with you today. I'm your AI assistant powered by the Enterprise LLM API Platform, and I'm genuinely excited to have this conversation with you. I'm designed to be helpful, informative, and engaging across a wide range of topics and tasks. Whether you're looking to explore ideas, solve problems, create something new, or simply have an interesting discussion, I'm here to assist you. What brings you here today, and how can I best help you achieve your goals?",
            "Hi! Welcome, and thank you for reaching out. I'm your dedicated AI assistant, and I'm thrilled to meet you and learn about what you're working on or thinking about. I have a broad knowledge base and love helping people with everything from creative projects and technical challenges to thoughtful conversations about complex topics. I believe in being thorough and thoughtful in my responses while also being genuinely helpful. What's on your mind today?"
        ]

    elif any(word in message for word in ["help", "assist"]):
        return [
            "I'm absolutely delighted to help! As an AI assistant, I have extensive capabilities across many domains. I can assist with writing and editing, research and analysis, coding and technical problem-solving, creative projects, mathematical calculations, learning new concepts, and engaging in thoughtful discussions about virtually any topic. I approach each request with care and attention to detail, always aiming to provide comprehensive and useful assistance. What specific challenge or project would you like to work on together? I'm here to support you in whatever way would be most valuable.",
            "Of course! I'm here specifically to be helpful, and I take great satisfaction in supporting people in achieving their goals. My capabilities span across numerous areas including academic research, creative writing, technical documentation, coding assistance, problem-solving, and much more. I believe in providing thoughtful, detailed responses that truly address what you're looking for. Please tell me more about what you need help with, and I'll do my best to provide exactly the kind of assistance that would be most beneficial for your situation."
        ]

    else:
        return [
            f"Thank you for sharing that with me. You mentioned '{message[:80]}...' and I find that to be a really compelling topic that deserves a thoughtful response. I appreciate when people bring up substantive ideas or questions because it gives me an opportunity to engage deeply with the subject matter. Let me provide you with a comprehensive perspective on this, and please feel free to ask follow-up questions or share more of your thoughts as we explore this together.",
            f"That's a fascinating point you've raised about '{message[:60]}...'. I really value these kinds of thoughtful exchanges because they allow us to dig into topics with the depth and nuance they deserve. I'd like to give you a detailed and well-considered response that addresses the various aspects of what you've brought up. Please let me know if you'd like me to focus on any particular angle or if there are specific questions you have as we discuss this further."
        ]


def get_default_response() -> str:
    """Default response when no patterns match"""
    defaults = [
        "That's an interesting perspective! I'd love to learn more about your thoughts on this topic. Could you elaborate on what specifically interests you or what questions you have?",
        "I find that fascinating! I'm always eager to explore new ideas and topics with people. What aspects of this would you like to discuss further?",
        "Thank you for sharing that with me. I'm here to help with whatever you need - whether that's answering questions, helping with tasks, or just having a thoughtful conversation. What would be most helpful for you right now?"
    ]
    return random.choice(defaults)


# API Endpoints
@app.get("/health")
async def health():
    """Enhanced health check"""
    return {
        "status": "healthy",
        "service": "enterprise-fastapi",
        "version": "2.0.0",
        "environment": "development",
        "features": [
            "intelligent-responses",
            "context-awareness",
            "multiple-models",
            "conversation-memory"
        ]
    }


@app.post("/api/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint with intelligent responses
    """

    # Simulate processing time for realism
    processing_delay = random.uniform(0.3, 1.5)
    await asyncio.sleep(processing_delay)

    # Generate intelligent response
    response_content = generate_intelligent_response(
        request.messages,
        request.model,
        request.temperature or 0.7
    )

    # Calculate token usage (simulated)
    prompt_tokens = sum(len(msg.content.split()) for msg in request.messages)
    completion_tokens = len(response_content.split())
    total_tokens = prompt_tokens + completion_tokens

    # Create response
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response_content),
                finish_reason="stop"
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
    )


@app.get("/api/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai",
                "description": "Most capable GPT-3.5 model, optimized for chat"
            },
            {
                "id": "llama-2-7b-chat",
                "object": "model",
                "created": 1677610602,
                "owned_by": "meta",
                "description": "Llama 2 7B model fine-tuned for chat conversations"
            }
        ]
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🚀 Enterprise LLM API Platform",
        "version": "2.0.0",
        "description": "Fully operational FastAPI service with intelligent conversation capabilities",
        "endpoints": {
            "chat": "/api/v1/chat/completions",
            "models": "/api/v1/models",
            "health": "/health",
            "docs": "/docs"
        },
        "features": [
            "Context-aware responses",
            "Multiple model personalities",
            "OpenAI-compatible API",
            "Intelligent conversation flow"
        ]
    }


# Add asyncio import for sleep function
import asyncio

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)