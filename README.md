# TinyChat

A minimal, lightning-fast chatbot interface for OpenAI-compatible APIs with real-time streaming responses.

<img width="500" alt="image" src="https://github.com/user-attachments/assets/23317a73-40dd-4fc6-a512-5b430373c8c9" />

## Quick Start

### Using Docker Hub (Recommended)

Pull and run the latest image:

```bash
docker run -d \
  --name tinychat \
  -p 8000:8000 \
  -e OPENAI_API_URL=https://api.openai.com/v1 \
  -e OPENAI_API_KEY=your-api-key-here \
  -e DEFAULT_MODEL=gpt-3.5-turbo \
  -e AVAILABLE_MODELS=gpt-3.5-turbo,gpt-4 \
  jasonacox/tinychat:latest

# Access at http://localhost:8000
```

### For Localhost LLMs (Ollama, etc)

If your LLM runs on localhost, use host networking:

```bash
docker run -d \
  --name tinychat \
  --network host \
  -e OPENAI_API_URL=http://localhost:11434/v1 \
  -e OPENAI_API_KEY=ollama \
  -e DEFAULT_MODEL=llama2 \
  -e AVAILABLE_MODELS=llama2,codellama,mistral \
  -e PORT=8000 \
  jasonacox/tinychat:latest

# Access at http://localhost:8000
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_URL` | `https://api.openai.com/v1` | LLM API endpoint |
| `OPENAI_API_KEY` | *Required* | API authentication key |
| `DEFAULT_MODEL` | `gpt-3.5-turbo` | Default model selection |
| `AVAILABLE_MODELS` | `gpt-3.5-turbo,gpt-4,gpt-4-turbo` | Comma-separated model list |
| `DEFAULT_TEMPERATURE` | `0.7` | Default temperature (0.0-2.0) |
| `PORT` | `8000` | Server listen port |
| `MAX_MESSAGE_LENGTH` | `8000` | Max characters per message |
| `MAX_CONVERSATION_HISTORY` | `50` | Max messages per conversation |
| `CHAT_LOG` | *(empty)* | Path to JSONL conversation log file |
| `ENABLE_DEBUG_LOGS` | `false` | Enable detailed debug logging |

### Compatible APIs

TinyChat works with any OpenAI-compatible API:

```bash
# OpenAI
OPENAI_API_URL=https://api.openai.com/v1
AVAILABLE_MODELS=gpt-3.5-turbo,gpt-4,gpt-4-turbo

# Ollama (local)
OPENAI_API_URL=http://localhost:11434/v1
AVAILABLE_MODELS=llama2,codellama,mistral

# Groq
OPENAI_API_URL=https://api.groq.com/openai/v1
AVAILABLE_MODELS=llama-2-70b-chat,mixtral-8x7b-32768

# Any custom API endpoint
OPENAI_API_URL=http://your-api:4000/v1
AVAILABLE_MODELS=your-model-1,your-model-2
```

### Research Logging

Enable conversation logging for research purposes:

```bash
docker run -d \
  --name tinychat \
  -p 8000:8000 \
  -v /path/to/logs:/logs \
  -e CHAT_LOG=/logs/conversations.jsonl \
  -e OPENAI_API_URL=https://api.openai.com/v1 \
  -e OPENAI_API_KEY=your-api-key \
  jasonacox/tinychat:latest
```

Each conversation is logged as one JSON line containing timestamp, model, temperature, messages, and response.

## Developer Guide

### Local Development

Clone and run locally with hot-reload:

```bash
# Clone repository
git clone https://github.com/jasonacox/tinychat.git
cd tinychat

# Set your API configuration
export OPENAI_API_URL=https://api.openai.com/v1
export OPENAI_API_KEY=your-api-key-here
export DEFAULT_MODEL=gpt-3.5-turbo
export AVAILABLE_MODELS=gpt-3.5-turbo,gpt-4

# Run development server (with debug logging)
./local.sh dev

# Access at http://localhost:8008
```

The `local.sh` script includes several helpful commands:

```bash
./local.sh dev           # Development mode with hot reload
./local.sh mock          # Run with mock API (no real API calls)
./local.sh test-api      # Test API connectivity
./local.sh test-models   # Test different model configurations
./local.sh cleanup       # Clean up test artifacts
./local.sh help          # Show all commands
```

### Building from Source

Build and run using Docker:

```bash
# Build image
docker build -t tinychat:latest .

# Run with custom configuration
./docker-run.sh
```

Or edit `docker-run.sh` to set your defaults.

### Project Structure

```
tinychat/
├── app/
│   ├── main.py              # FastAPI application
│   └── static/
│       ├── index.html       # Frontend UI
│       └── favicon*.svg     # Icons
├── Dockerfile               # Multi-stage build
├── requirements.txt         # Python dependencies
├── docker-run.sh           # Docker deployment script
├── local.sh                # Local development script
├── upload.sh               # Docker Hub publishing script
└── README.md               # This file
```

### Technology Stack

- **Backend**: FastAPI (async Python web framework)
- **Frontend**: Vanilla JavaScript with Server-Sent Events
- **Storage**: Browser localStorage (client-side)
- **Streaming**: SSE for real-time token display
- **Container**: Docker with multi-architecture support (amd64, arm64)

### Publishing to Docker Hub

Update version in `app/main.py`:

```python
__version__ = "0.2.0"
```

Then build and push:

```bash
./upload.sh
```

This will build multi-architecture images and push both versioned and `latest` tags.

## API Reference

### Chat Endpoint

**POST** `/api/chat/stream`

Stream chat completions via Server-Sent Events.

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "model": "gpt-3.5-turbo"
  }'
```

### Configuration Endpoint

**GET** `/api/config`

Returns available models, defaults, and version.

```bash
curl http://localhost:8000/api/config
```

### Health Check

**GET** `/api/health`

Simple health check endpoint for monitoring.

```bash
curl http://localhost:8000/api/health
```

## Architecture

### Stateless Design

TinyChat is fully stateless:
- Conversations stored client-side in browser localStorage
- Server only handles API proxying and streaming
- Horizontally scalable - add as many instances as needed
- Zero memory footprint for conversations

### Security Features

- Input validation and sanitization
- Configurable message length limits
- CORS and security headers
- Client-side rate limiting
- Generic error messages in production
- Optional conversation history limits

### Performance

- **Async I/O**: Non-blocking request handling
- **Efficient Streaming**: Direct SSE, no buffering
- **Small Footprint**: ~50MB Docker image
- **Fast Startup**: Sub-second boot time
- **Low Latency**: Minimal overhead between API and client

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with clear commit messages
4. Test locally with `./local.sh dev`
5. Submit a pull request

## Credits

- **Inspired by**: [TinyLLM](https://github.com/jasonacox/TinyLLM) - Simple LLM proxy
- **Built with**: [Claude](https://claude.ai) - AI pair programming assistant
- **Author**: Jason A. Cox ([@jasonacox](https://github.com/jasonacox))

<img width="500" alt="image" src="https://github.com/user-attachments/assets/cd39f8e8-caf5-4789-8333-653bb5fd2ad0" />

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**For educational and research purposes only.** AI models can make mistakes - always verify important information.
