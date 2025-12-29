#!/bin/bash

# Local testing script for TinyChat
# This file is for local development and testing only - not checked into git

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Local environment variables for testing
export OPENAI_API_URL="${OPENAI_API_URL:-https://api.openai.com/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-your-api-key-here}"
export DEFAULT_MODEL="${DEFAULT_MODEL:-gpt-3.5-turbo}"
export DEFAULT_TEMPERATURE="${DEFAULT_TEMPERATURE:-0.7}"
export AVAILABLE_MODELS="${AVAILABLE_MODELS:-gpt-3.5-turbo,gpt-4}"
export ENABLE_DEBUG_LOGS="true"  # Always true for local development
export CHAT_LOG="${CHAT_LOG:-}"
export PORT="${PORT:-8008}"

# Function to test API connectivity
test_api() {
    echo_info "Testing API connectivity..."
    
    if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-test-key-for-local-testing" ]; then
        echo_warn "Using test API key. Set OPENAI_API_KEY for real testing."
    fi
    
    echo_debug "API URL: $OPENAI_API_URL"
    echo_debug "Model: $DEFAULT_MODEL"
    echo_debug "Temperature: $DEFAULT_TEMPERATURE"
    
    # Simple curl test
    curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $OPENAI_API_KEY" \
        -H "Content-Type: application/json" \
        "$OPENAI_API_URL/models" || echo_warn "API test failed"
}

# Function to run with mock API for testing
mock_api() {
    local port=${1:-$PORT}  # Use parameter or PORT env var
    echo_info "Starting with mock API responses on port $port..."
    export OPENAI_API_URL="http://localhost:8001/v1"
    
    # Start a simple mock server in background
    python3 -c "
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if 'chat/completions' in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.end_headers()
            
            # Mock streaming response
            chunks = [
                'data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}',
                'data: {\"choices\":[{\"delta\":{\"content\":\" from\"}}]}', 
                'data: {\"choices\":[{\"delta\":{\"content\":\" mock\"}}]}',
                'data: {\"choices\":[{\"delta\":{\"content\":\" API!\"}}]}',
                'data: [DONE]'
            ]
            
            import time
            for chunk in chunks:
                self.wfile.write((chunk + '\n\n').encode())
                self.wfile.flush()
                time.sleep(0.1)
    
    def log_message(self, format, *args):
        pass

httpd = HTTPServer(('localhost', 8001), MockHandler)
httpd.serve_forever()
" &
    
    MOCK_PID=$!
    echo_info "Mock API started on port 8001 (PID: $MOCK_PID)"
    
    # Wait a moment for mock server to start
    sleep 2
    
    # Now run the app
    run_dev_local $port
    
    # Cleanup
    kill $MOCK_PID 2>/dev/null || true
}

# Function to run locally with hot reload
run_dev_local() {
    local port=${1:-$PORT}  # Use parameter or PORT env var or default
    echo_info "Starting TinyChat in local development mode on port $port..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo_info "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    echo_info "Installing/updating dependencies..."
    pip install -r requirements.txt
    
    # Run with custom settings for local testing
    echo_info "Starting FastAPI server with local config on http://127.0.0.1:$port..."
    uvicorn app.main:app \
        --host 127.0.0.1 \
        --port $port \
        --reload \
        --reload-dir app \
        --log-level debug
}

# Function to test with different models
test_models() {
    echo_info "Testing different model configurations..."
    
    local models=("gpt-3.5-turbo" "gpt-4" "gpt-4-turbo")
    
    for model in "${models[@]}"; do
        echo_debug "Testing with model: $model"
        export DEFAULT_MODEL="$model"
        
        # Quick API test
        curl -s -X POST http://localhost:8000/api/chat/stream \
            -H "Content-Type: application/json" \
            -d "{\"message\": \"Test with $model\", \"model\": \"$model\"}" \
            2>/dev/null | head -n 5 || echo_warn "Failed to test $model"
        
        echo ""
    done
}

# Function to load test the application
load_test() {
    echo_info "Running basic load test..."
    
    if ! command -v curl &> /dev/null; then
        echo_error "curl is required for load testing"
        return 1
    fi
    
    echo_info "Sending 10 concurrent requests..."
    
    for i in {1..10}; do
        curl -s -X POST http://localhost:8000/api/chat/stream \
            -H "Content-Type: application/json" \
            -d "{\"message\": \"Load test message $i\"}" &
    done
    
    wait
    echo_info "Load test completed"
}

# Function to clean up local testing artifacts
cleanup() {
    echo_info "Cleaning up local testing files..."
    
    # Remove test logs
    rm -f *.log
    
    # Remove test conversations
    rm -f conversations.json
    
    # Stop any running containers
    docker stop tinychat 2>/dev/null || true
    docker rm tinychat 2>/dev/null || true
    
    # Kill any background processes
    pkill -f "uvicorn" || true
    pkill -f "python.*mock" || true
    
    echo_info "Cleanup completed"
}

# Function to show current environment
show_env() {
    echo_info "Current environment settings:"
    echo "OPENAI_API_URL: $OPENAI_API_URL"
    echo "DEFAULT_MODEL: $DEFAULT_MODEL" 
    echo "DEFAULT_TEMPERATURE: $DEFAULT_TEMPERATURE"
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}..."
    else
        echo "OPENAI_API_KEY: (not set)"
    fi
}

# Function to show help
show_help() {
    cat << EOF
Local TinyChat Testing Script

Usage: $0 [COMMAND] [PORT]

Commands:
    dev [PORT]      Run in development mode with hot reload (default: 8008)
    mock [PORT]     Run with mock API for testing without real API calls (default: 8008)
    test-api        Test API connectivity
    test-models     Test different model configurations  
    load-test       Run basic load test
    env             Show current environment variables
    cleanup         Clean up testing artifacts
    help            Show this help message

Examples:
    $0 dev                    # Start development server on port 8008
    $0 dev 3000              # Start development server on port 3000
    $0 mock                   # Use mock API responses on port 8008
    $0 mock 9000             # Use mock API responses on port 9000
    $0 test-api              # Test your API configuration
    OPENAI_API_KEY=sk-... $0 dev  # Run with specific API key

Environment Variables:
    OPENAI_API_URL     API endpoint (default: https://api.openai.com/v1)
    OPENAI_API_KEY     Your API key
    DEFAULT_MODEL      Model to use (default: gpt-3.5-turbo)
    DEFAULT_TEMPERATURE Temperature setting (default: 0.7)

Note: This script is for local testing only and should not be committed to git.

EOF
}

# Main script logic
case "${1:-help}" in
    dev)
        show_env
        run_dev_local "${2:-$PORT}"
        ;;
    mock)
        echo_warn "Using mock API - no real API calls will be made"
        mock_api "${2:-$PORT}"
        ;;
    test-api)
        show_env
        test_api
        ;;
    test-models)
        test_models
        ;;
    load-test)
        load_test
        ;;
    env)
        show_env
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac