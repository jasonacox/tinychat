# TinyChat

A minimal, lightning-fast chatbot interface for OpenAI-compatible APIs with real-time streaming responses, markdown & math rendering, and image generation capabilities.

<img width="700" alt="image" src="https://github.com/user-attachments/assets/4ec87558-31b0-42c1-8502-3c2c2c285eaa" />

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

## Key Features

- **📝 Markdown Rendering**: Full markdown support with syntax-highlighted code blocks
- **🔢 Math Equations**: Beautiful LaTeX rendering with KaTeX (inline `$...$` and display `$$...$$`)
- **🎨 Syntax Highlighting**: Code blocks automatically highlighted in 180+ languages
- **💬 Real-time Streaming**: Server-Sent Events for token-by-token responses
- **🖼️ Image Generation**: Create images with SwarmUI or OpenAI DALL-E
- **💾 Client-side Storage**: Conversations persist in browser localStorage
- **⚙️ Smart Defaults**: Model selection and markdown preferences saved automatically
- **🔒 Security First**: Content Security Policy, input validation, sanitization
- **📊 Stateless**: Zero server-side memory, horizontally scalable
- **🚀 Fast**: Minimal overhead, sub-second startup, efficient streaming

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
| `IMAGE_PROVIDER` | `swarmui` | Image provider: `swarmui` or `openai` |
| `SWARMUI` | `http://localhost:7801` | SwarmUI API endpoint |
| `IMAGE_MODEL` | `Flux/flux1-schnell-fp8` | SwarmUI model name |
| `IMAGE_CFGSCALE` | `1.0` | SwarmUI CFG scale |
| `IMAGE_STEPS` | `6` | SwarmUI generation steps |
| `IMAGE_WIDTH` | `1024` | Image width in pixels |
| `IMAGE_HEIGHT` | `1024` | Image height in pixels |
| `IMAGE_SEED` | `-1` | Random seed (-1 for random) |
| `IMAGE_TIMEOUT` | `300` | Image generation timeout (seconds) |
| `OPENAI_IMAGE_API_KEY` | *(empty)* | OpenAI API key for image generation |
| `OPENAI_IMAGE_API_BASE` | `https://api.openai.com/v1` | OpenAI Images API endpoint |
| `OPENAI_IMAGE_MODEL` | `dall-e-3` | OpenAI image model |
| `OPENAI_IMAGE_SIZE` | `1024x1024` | OpenAI image size |
| `RLM_TIMEOUT` | `60` | RLM execution timeout (seconds) |
| `MAX_CONCURRENT_RLM` | `3` | Maximum parallel RLM executions |

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

### Image Generation

TinyChat supports image generation via SwarmUI (local) or OpenAI DALL-E.

<img width="700" alt="image" src="https://github.com/user-attachments/assets/b81b2a09-c251-4435-86c8-aba8369e2267" />

**Using SwarmUI (local)**:
```bash
docker run -d \
  --name tinychat \
  --network host \
  -e OPENAI_API_URL=http://localhost:11434/v1 \
  -e OPENAI_API_KEY=ollama \
  -e IMAGE_PROVIDER=swarmui \
  -e SWARMUI=http://localhost:7801 \
  -e IMAGE_MODEL=Flux/flux1-schnell-fp8 \
  jasonacox/tinychat:latest
```

**Using OpenAI DALL-E**:
```bash
docker run -d \
  --name tinychat \
  -p 8000:8000 \
  -e OPENAI_API_URL=https://api.openai.com/v1 \
  -e OPENAI_API_KEY=your-api-key \
  -e IMAGE_PROVIDER=openai \
  -e OPENAI_IMAGE_API_KEY=your-api-key \
  -e OPENAI_IMAGE_MODEL=dall-e-3 \
  jasonacox/tinychat:latest
```

**Usage**: In the chat interface, type `/image <your prompt>` to generate an image. For example:
- `/image A house with a green roof`
- `/image A futuristic city at sunset`

Generated images display at 25% size and can be clicked to view full size. Download button included.

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

# Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install Python dependencies
python -m pip install -U pip
pip install -r requirements.txt

# (Optional) Install RLM for Recursive Language Model Support
pip install git+https://github.com/alexzhang13/rlm.git

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

**Backend:**
- **FastAPI**: Async Python web framework
- **Pillow (PIL)**: Image optimization and format conversion
- **aiohttp**: Async HTTP client for image API requests

**Frontend:**
- **Vanilla JavaScript**: No framework dependencies
- **Server-Sent Events**: Real-time streaming
- **marked.js**: Markdown parsing with GFM support
- **highlight.js**: Syntax highlighting for 180+ languages
- **KaTeX**: Fast math typesetting

**Storage & Architecture:**
- **Browser localStorage**: Client-side conversation persistence
- **Stateless Backend**: Zero server-side storage
- **Multi-architecture Docker**: Support for amd64 and arm64

### Publishing to Docker Hub

Update version in `app/main.py`:

```python
__version__ = "0.2.2"
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

**Image Generation**: Use `/image` prefix in user message:

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "/image A house with a green roof"}
    ]
  }'
```

Response includes base64-encoded image data URI.
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

**⚠️ RLM Security Notice**: When RLM (Recursive Language Model) is enabled, the system executes code generated by the language model in a sandboxed Python environment. While the environment has restricted builtins and runs in isolated temp directories, **it should only be used with trusted users** or in controlled environments. RLM includes:
- Sandboxed Python REPL with limited builtins (no `eval`, `exec`, `input`)
- Configurable execution timeout (default: 60s)
- Concurrency limits to prevent resource exhaustion
- Automatic cleanup of temporary files
- Code execution is logged for audit purposes

For production deployments with untrusted users, consider:
- Running RLM in a separate containerized service with strict resource limits
- Implementing additional network isolation
- Disabling RLM feature entirely if code execution is not needed

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
- **RLM Integration**: [Recursive Language Models](https://github.com/alexzhang13/rlm) - Agentic reasoning framework by Alex L. Zhang, Tim Kraska, and Omar Khattab ([arXiv:2512.24601](https://arxiv.org/abs/2512.24601))
- **Built with**: [Claude](https://claude.ai) - AI pair programming assistant
- **Author**: Jason A. Cox ([@jasonacox](https://github.com/jasonacox))

<img width="500" alt="image" src="https://github.com/user-attachments/assets/cd39f8e8-caf5-4789-8333-653bb5fd2ad0" />

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**For educational and research purposes only.** AI models can make mistakes - always verify important information.
