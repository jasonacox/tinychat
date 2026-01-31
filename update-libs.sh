#!/bin/bash
# Update frontend JavaScript libraries to their latest versions
# This script downloads the latest versions of all third-party libraries used by TinyChat

set -e  # Exit on error

LIBS_DIR="app/static/libs"
BACKUP_DIR="app/static/libs.backup.$(date +%Y%m%d_%H%M%S)"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== TinyChat Library Updater ===${NC}"
echo ""

# Check if we're in the right directory
if [ ! -d "app/static" ]; then
    echo -e "${RED}Error: Must be run from TinyChat root directory${NC}"
    exit 1
fi

# Create backup
echo -e "${YELLOW}Creating backup at ${BACKUP_DIR}...${NC}"
if [ -d "$LIBS_DIR" ]; then
    cp -r "$LIBS_DIR" "$BACKUP_DIR"
    echo -e "${GREEN}✓ Backup created${NC}"
else
    echo -e "${YELLOW}⚠ No existing libs directory to backup${NC}"
    mkdir -p "$LIBS_DIR"
fi

cd "$LIBS_DIR"

echo ""
echo -e "${BLUE}Downloading libraries...${NC}"
echo ""

# Marked.js - Markdown rendering
echo -e "${YELLOW}→ Marked.js (Markdown rendering)${NC}"
MARKED_VERSION=$(curl -s https://api.github.com/repos/markedjs/marked/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
echo "  Latest version: $MARKED_VERSION"
curl -sL "https://cdn.jsdelivr.net/npm/marked@${MARKED_VERSION}/marked.min.js" -o marked.min.js
echo -e "${GREEN}  ✓ Downloaded marked.min.js${NC}"
echo ""

# Highlight.js - Syntax highlighting
echo -e "${YELLOW}→ Highlight.js (Syntax highlighting)${NC}"
HLJS_VERSION=$(curl -s https://api.github.com/repos/highlightjs/highlight.js/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
echo "  Latest version: $HLJS_VERSION"
curl -sL "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/${HLJS_VERSION}/highlight.min.js" -o highlight.min.js
curl -sL "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/${HLJS_VERSION}/styles/github-dark.min.css" -o highlight-github-dark.min.css
echo -e "${GREEN}  ✓ Downloaded highlight.min.js${NC}"
echo -e "${GREEN}  ✓ Downloaded highlight-github-dark.min.css${NC}"
echo ""

# KaTeX - Math rendering
echo -e "${YELLOW}→ KaTeX (Math equation rendering)${NC}"
KATEX_VERSION=$(curl -s https://api.github.com/repos/KaTeX/KaTeX/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
echo "  Latest version: $KATEX_VERSION"
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.css" -o katex.min.css
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/katex.min.js" -o katex.min.js
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/contrib/auto-render.min.js" -o katex-auto-render.min.js
echo -e "${GREEN}  ✓ Downloaded katex.min.css${NC}"
echo -e "${GREEN}  ✓ Downloaded katex.min.js${NC}"
echo -e "${GREEN}  ✓ Downloaded katex-auto-render.min.js${NC}"

# KaTeX fonts
echo "  Downloading KaTeX fonts..."
mkdir -p fonts
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/fonts/KaTeX_Main-Regular.woff2" -o fonts/KaTeX_Main-Regular.woff2
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/fonts/KaTeX_Math-Italic.woff2" -o fonts/KaTeX_Math-Italic.woff2
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/fonts/KaTeX_Size1-Regular.woff2" -o fonts/KaTeX_Size1-Regular.woff2
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/fonts/KaTeX_Size2-Regular.woff2" -o fonts/KaTeX_Size2-Regular.woff2
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/fonts/KaTeX_AMS-Regular.woff2" -o fonts/KaTeX_AMS-Regular.woff2
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/fonts/KaTeX_Caligraphic-Bold.woff2" -o fonts/KaTeX_Caligraphic-Bold.woff2
curl -sL "https://cdn.jsdelivr.net/npm/katex@${KATEX_VERSION}/dist/fonts/KaTeX_Fraktur-Regular.woff2" -o fonts/KaTeX_Fraktur-Regular.woff2
echo -e "${GREEN}  ✓ Downloaded 7 KaTeX fonts${NC}"
echo ""

# LocalForage - IndexedDB wrapper
echo -e "${YELLOW}→ LocalForage (IndexedDB storage)${NC}"
LOCALFORAGE_VERSION=$(curl -s https://api.github.com/repos/localForage/localForage/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
echo "  Latest version: $LOCALFORAGE_VERSION"
curl -sL "https://cdn.jsdelivr.net/npm/localforage@${LOCALFORAGE_VERSION}/dist/localforage.min.js" -o localforage.min.js
echo -e "${GREEN}  ✓ Downloaded localforage.min.js${NC}"
echo ""

# Summary
echo -e "${GREEN}=== Update Complete ===${NC}"
echo ""
echo "Library versions:"
echo "  • Marked.js:    $MARKED_VERSION"
echo "  • Highlight.js: $HLJS_VERSION"
echo "  • KaTeX:        $KATEX_VERSION"
echo "  • LocalForage:  $LOCALFORAGE_VERSION"
echo ""
echo -e "${BLUE}Backup saved to: ${BACKUP_DIR}${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Test the application thoroughly"
echo "  2. Update THIRD-PARTY-LICENSES.md with new version numbers"
echo "  3. If everything works, remove backup: rm -rf ${BACKUP_DIR}"
echo "  4. Commit changes: git add ${LIBS_DIR} && git commit -m 'Update frontend libraries'"
echo ""
