# Release Notes

## v0.2.3 - Math & Currency Fixes

### Bug Fixes
- **Math & Currency Rendering**: Fixed conflict where currency amounts (e.g., "$3.50") were incorrectly interpreted as math equations.
  - Implemented strict isolation for currency symbols to prevent math parser collisions.
  - Added support for left-aligned display equations using `fleqn`.
  - Fixed issues with table rendering containing math equations.
  - Improved display math restoration for consistency (`$$...$$` handling).

## v0.2.2 - Markdown & Math Rendering

### New Features
- **Markdown Rendering**: Assistant responses now render markdown formatting
  - Toggle option in settings to enable/disable markdown rendering (enabled by default)
  - Support for headings, lists, tables, blockquotes, and inline formatting
  - Protected LaTeX extraction prevents markdown from corrupting math equations
  - Preference persists in localStorage
- **Syntax Highlighting**: Code blocks automatically highlighted with highlight.js
  - GitHub Dark theme for consistent code display
  - Support for multiple programming languages
- **Math Equation Rendering**: LaTeX equations rendered beautifully with KaTeX
  - Inline math: `$equation$`
  - Display math: `$$equation$$`
  - Support for complex formulas, fractions, square roots, and mathematical notation
- **Model Selection Persistence**: Selected model now saved to localStorage
  - Automatically restores last used model on page reload
  - Falls back to default model if saved model unavailable

### Improvements
- Enhanced Content Security Policy to allow CDN resources for libraries
  - Added support for cdn.jsdelivr.net and cdnjs.cloudflare.com
  - Properly configured script-src, style-src, and font-src directives
- Removed debug console logging for cleaner browser console output

### Dependencies
- Added **marked.js** (v11.1.1) for markdown parsing
- Added **highlight.js** (v11.9.0) for code syntax highlighting
- Added **KaTeX** (v0.16.9) for math equation rendering

## v0.2.1 - Image Persistence

- Images now persist in conversation history (stored in localStorage)
- Image data filtered from API requests to reduce bandwidth
- Fixed image display when revisiting conversations

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
