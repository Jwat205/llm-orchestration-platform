# Getting Started with LLM API Platform

Welcome to the LLM API Platform! This guide will help you get up and running quickly with our enterprise-grade Local LLM API service.

## Quick Start

### 1. Authentication

All API requests require authentication using either an API key or JWT token.

```bash
# Using API Key
curl -H "X-API-Key: YOUR_API_KEY" \
     https://api.llm-platform.com/v1/models
```

```bash
# Using Bearer Token
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     https://api.llm-platform.com/v1/models
```

### 2. Your First API Call

Check available models:

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
     https://api.llm-platform.com/v1/models
```

### 3. Chat Completion

Create your first chat completion:

```bash
curl -X POST \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "llama-2-7b-chat",
       "messages": [
         {
           "role": "user",
           "content": "Hello, how are you?"
         }
       ],
       "max_tokens": 150
     }' \
     https://api.llm-platform.com/v1/chat/completions
```

### 4. Streaming Response

For real-time streaming:

```bash
curl -X POST \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "llama-2-7b-chat",
       "messages": [
         {
           "role": "user",
           "content": "Write a short story"
         }
       ],
       "stream": true
     }' \
     https://api.llm-platform.com/v1/chat/completions
```

## API Overview

### Base URL
- **Production**: `https://api.llm-platform.com`
- **Staging**: `https://staging-api.llm-platform.com`

### Authentication Methods

1. **API Key** (Recommended for server-to-server)
   - Header: `X-API-Key: your_api_key_here`

2. **JWT Token** (Recommended for user applications)
   - Header: `Authorization: Bearer your_jwt_token_here`

### Rate Limits

| Plan | Requests/minute | Tokens/minute |
|------|-----------------|---------------|
| Free | 60 | 10,000 |
| Pro | 3,000 | 500,000 |
| Enterprise | Custom | Custom |

### Available Models

| Model ID | Description | Context Length | Use Case |
|----------|-------------|---------------|----------|
| `llama-2-7b-chat` | Llama 2 7B Chat | 4,096 | General chat |
| `llama-2-13b-chat` | Llama 2 13B Chat | 4,096 | Advanced chat |
| `codellama-7b` | Code Llama 7B | 4,096 | Code generation |
| `mistral-7b` | Mistral 7B | 8,192 | Multilingual chat |

## Core Endpoints

### 1. Chat Completions

**Endpoint**: `POST /v1/chat/completions`

Generate conversational responses using various LLM models.

**Key Parameters**:
- `model` (required): Model identifier
- `messages` (required): Conversation history
- `max_tokens`: Response length limit
- `temperature`: Creativity control (0.0 - 2.0)
- `stream`: Enable streaming responses

### 2. Embeddings

**Endpoint**: `POST /v1/embeddings`

Convert text into vector embeddings for semantic search and similarity.

**Key Parameters**:
- `input` (required): Text to embed
- `model` (required): Embedding model
- `user`: User identifier for tracking

### 3. Fine-tuning

**Endpoint**: `POST /v1/fine-tuning/jobs`

Create custom models fine-tuned on your data.

**Key Parameters**:
- `model` (required): Base model to fine-tune
- `training_file` (required): Training data file ID
- `validation_file`: Validation data file ID
- `hyperparameters`: Training configuration

## Python SDK Example

```python
from llm_api_client import LLMClient

# Initialize client
client = LLMClient(api_key="your_api_key_here")

# Chat completion
response = client.chat.completions.create(
    model="llama-2-7b-chat",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    max_tokens=150
)

print(response.choices[0].message.content)
```

## JavaScript SDK Example

```javascript
import { LLMClient } from 'llm-api-client';

const client = new LLMClient({
  apiKey: 'your_api_key_here'
});

const completion = await client.chat.completions.create({
  model: 'llama-2-7b-chat',
  messages: [
    { role: 'user', content: 'Hello!' }
  ],
  max_tokens: 150
});

console.log(completion.choices[0].message.content);
```

## Error Handling

The API uses standard HTTP status codes and returns detailed error messages:

```json
{
  "error": {
    "message": "Invalid model specified",
    "type": "invalid_request_error",
    "param": "model",
    "code": "model_not_found"
  }
}
```

### Common Error Codes

- `400` - Bad Request: Invalid parameters
- `401` - Unauthorized: Invalid or missing API key
- `429` - Rate Limit Exceeded: Too many requests
- `500` - Internal Server Error: Server issue

## Best Practices

### 1. Efficient Token Usage

- Set appropriate `max_tokens` limits
- Use `stop` sequences to control output
- Consider model selection based on use case

### 2. Rate Limit Management

- Implement exponential backoff for retries
- Monitor your usage through the dashboard
- Use streaming for long responses

### 3. Error Handling

- Always implement proper error handling
- Log errors for debugging
- Have fallback mechanisms

### 4. Security

- Never expose API keys in client-side code
- Use environment variables for keys
- Implement proper authentication for user-facing apps

## Advanced Features

### Function Calling

Enable your models to call functions:

```json
{
  "model": "llama-2-7b-chat",
  "messages": [{"role": "user", "content": "What's the weather?"}],
  "functions": [
    {
      "name": "get_weather",
      "description": "Get current weather",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string"}
        }
      }
    }
  ]
}
```

### Custom Models

Upload your own fine-tuned models:

1. Prepare training data in JSONL format
2. Upload files via the API
3. Create fine-tuning job
4. Deploy custom model

## Support & Resources

- **Documentation**: [docs.llm-platform.com](https://docs.llm-platform.com)
- **API Reference**: [docs.llm-platform.com/api](https://docs.llm-platform.com/api)
- **Status Page**: [status.llm-platform.com](https://status.llm-platform.com)
- **Support**: [support@llm-platform.com](mailto:support@llm-platform.com)
- **Community**: [community.llm-platform.com](https://community.llm-platform.com)

## Next Steps

1. [Explore API endpoints in detail](api-usage-examples.md)
2. [Set up billing and monitor usage](billing-guide.md)
3. [Learn about integration patterns](integration-examples.md)
4. [Review security best practices](../architecture/security-model.md)

Need help? Check our [troubleshooting guide](../operations/troubleshooting.md) or contact support!