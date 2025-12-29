# Release Notes

## v0.2.0 - Image Generation

### New Features
- **Image Generation**: Added `/image <prompt>` command to generate images
  - Support for SwarmUI (local) and OpenAI DALL-E image providers
  - Configurable via `IMAGE_PROVIDER` environment variable
  - Images display at 25% size with click-to-enlarge modal view
  - Download button for saving generated images
  - Automatic JPEG conversion and optimization for web display

### Configuration
New environment variables:
- `IMAGE_PROVIDER` - Set to "swarmui" or "openai" (default: swarmui)
- `SWARMUI` - SwarmUI API endpoint (default: http://localhost:7801)
- `IMAGE_MODEL` - SwarmUI model name (default: Flux/flux1-schnell-fp8)
- `IMAGE_CFGSCALE`, `IMAGE_STEPS`, `IMAGE_WIDTH`, `IMAGE_HEIGHT`, `IMAGE_SEED` - Generation parameters
- `OPENAI_IMAGE_API_KEY`, `OPENAI_IMAGE_API_BASE`, `OPENAI_IMAGE_MODEL` - OpenAI image settings

### Dependencies
- Added `aiohttp` for async HTTP requests to image APIs
- Added `Pillow` for image processing and optimization


## v0.1.0 - First Release
