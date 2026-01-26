#!/bin/bash
echo "Build and Push jasonacox/tinychat to Docker Hub"
echo ""

# Check if we're in the tinychat directory
last_path=$(basename $PWD)
if [ "$last_path" != "tinychat" ]; then
  echo "ERROR: Current directory is not 'tinychat'. Please run from the tinychat directory."
  exit 1
fi

# Read version from app/__init__.py
if [ -f "app/__init__.py" ]; then
  VER=$(grep "^__version__ = " app/__init__.py | cut -d'"' -f2)
  echo "Version from __init__.py: ${VER}"
else
  echo "ERROR: app/__init__.py not found!"
  exit 1
fi

# Verify version was found
if [ -z "$VER" ]; then
  echo "ERROR: Could not extract version from app/__init__.py"
  exit 1
fi

# Check with user before proceeding
echo ""
echo "This will build and push the following images:"
echo "  - jasonacox/tinychat:${VER}"
echo "  - jasonacox/tinychat:latest"
echo ""

# Ask about --no-cache (default: no)
read -p "Use --no-cache for build? [y/N] " response
case "$response" in
    [yY][eE][sS]|[yY]) 
        CACHE_FLAG="--no-cache"
        ;;
    *)
        CACHE_FLAG=""
        ;;
esac

read -p "Press [Enter] to continue or Ctrl-C to cancel..."

# Build and push both tags in single command
echo ""
echo "* BUILD jasonacox/tinychat:${VER} and jasonacox/tinychat:latest"
docker buildx build ${CACHE_FLAG} --platform linux/amd64,linux/arm64 --push \
  -t jasonacox/tinychat:${VER} \
  -t jasonacox/tinychat:latest .
echo ""

# Verify
echo "* VERIFY jasonacox/tinychat:${VER}"
docker buildx imagetools inspect jasonacox/tinychat:${VER} | grep Platform
echo ""
echo "* VERIFY jasonacox/tinychat:latest"
docker buildx imagetools inspect jasonacox/tinychat:latest | grep Platform
echo ""

echo "✅ Build and push completed successfully!"
echo ""
echo "To pull and run:"
echo "  docker pull jasonacox/tinychat:${VER}"
echo "  docker pull jasonacox/tinychat:latest"
