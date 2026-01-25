# Release Notes

## v0.3.0 - RLM Integration & Enhanced UI

### Major Features
- **RLM (Recursive Language Model) Integration**: Added support for agentic reasoning workflows
  - Toggle "Use RLM" in settings to enable recursive reasoning with code execution
  - RLM uses a REPL environment to solve complex problems through iterative reasoning
  - Supports multi-iteration workflows with code execution and result evaluation
  - Smart variable resolution automatically extracts final answers from REPL variables
  - Fallback mechanisms for models that don't use proper FINAL() macros
  - Toggle "Show RLM Thinking" to view detailed reasoning steps or hide them
  - Real-time streaming of reasoning steps, code execution, and intermediate results
  - Status indicator shows RLM progress when thinking details are hidden
  - Both RLM toggle states persist in localStorage across sessions

### RLM Features
- **Thinking Mode Display**:
  - Detailed view shows reasoning, REPL code, and execution results for each iteration
  - Automatic resolution of `FINAL()` and `FINAL_VAR()` macros in thinking display
  - Smart output capture shows variable values even when code doesn't print explicitly
  - Markdown-formatted iteration headers for clear organization
- **Status Indicator**:
  - Floating status badge in bottom-right when "Show RLM Thinking" is disabled
  - Shows current iteration progress ("Iteration 1...", "Iteration 2...", etc.)
  - Pulse animation for visual feedback
  - Automatically hides when final answer is delivered
- **Smart Answer Extraction**:
  - Detects if model returns variable name instead of value
  - Automatically retrieves actual values from REPL environment
  - Works with both local and remote execution environments
  - Fallback to execution output if FINAL() macro is malformed

### UI Improvements
- **Fixed Footer Scrolling**: Footer now stays locked at bottom of viewport
  - Added overflow constraints to body and main-content containers
  - Chat messages scroll independently within their container
  - Header, footer, and input area remain fixed in position
- **Conditional Toggle Visibility**: "Show RLM Thinking" toggle only appears when "Use RLM" is enabled
  - Cleaner UI when RLM features aren't being used
  - Automatic show/hide based on RLM toggle state
- **Preference Persistence**: RLM settings saved to browser localStorage
  - "Use RLM" state persists across page refreshes
  - "Show RLM Thinking" preference remembered per user
  - Consistent with other UI preferences (markdown, model selection)

### Technical Improvements
- **Backend Architecture**:
  - Graceful RLM import handling with HAS_RLM flag
  - Background threading for RLM execution to prevent blocking
  - Queue-based message passing for real-time status updates
  - Separate streaming paths for thinking vs. non-thinking modes
  - Enhanced error handling and logging for RLM operations
- **Code Quality**:
  - Fixed Pydantic validator warnings (added @classmethod decorators)
  - Improved code organization with helper functions
  - Regular expression support for text parsing
  - Type hints and documentation throughout

### Configuration
New RLM integration works with existing OpenAI-compatible API settings:
- `OPENAI_API_URL` - Used for both standard chat and RLM backend
- `OPENAI_API_KEY` - Authentication for LLM access
- RLM automatically uses the selected model from the UI dropdown
- `RLM_TIMEOUT` - Execution timeout for RLM operations (default: 300s / 5 minutes)
- `MAX_CONCURRENT_RLM` - Maximum parallel RLM executions (default: 3)

### Dependencies
- Added **rlm** package for recursive language model functionality
  - Includes local REPL environment for safe code execution
  - Supports multiple backend providers (OpenAI, Anthropic, etc.)
  - Built-in parsing utilities for code blocks and FINAL() macros

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
