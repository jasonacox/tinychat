// Markdown and math rendering utilities

// Configure marked.js with syntax highlighting
function configureMarked() {
    if (typeof marked !== 'undefined') {
        console.log('Configuring marked.js version:', marked.VERSION || 'unknown');
        marked.setOptions({
            highlight: function(code, lang) {
                if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {
                        console.error('Highlight error:', e);
                    }
                }
                return code;
            },
            breaks: true,
            gfm: true
        });
    } else {
        console.warn('marked.js library not loaded');
    }
}

// Render math equations in an element using KaTeX
function renderMath(element) {
    if (typeof renderMathInElement !== 'undefined') {
        try {
            renderMathInElement(element, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '\\[', right: '\\]', display: true},
                    {left: '\\(', right: '\\)', display: false}
                ],
                fleqn: true,
                throwOnError: false,
                strict: false
            });
        } catch (e) {
            console.error('KaTeX rendering error:', e);
        }
    }
}

// Process content with markdown and math rendering
function renderMarkdownWithMath(content) {
    if (typeof marked === 'undefined') {
        return content;
    }

    // Step 1: Extract LaTeX blocks to protect them from markdown processing
    const mathBlocks = [];
    let processedContent = content;

    // Escape currency: $ followed by digit
    // Use a unique placeholder that doesn't contain $
    processedContent = processedContent.replace(/\$(?=[0-9])/g, '___CURRENCY_SYMBOL_PLACEHOLDER___');
    
    // Extract display math blocks ($$...$$)
    processedContent = processedContent.replace(/\$\$([\s\S]+?)\$\$/g, (match, math) => {
        const placeholder = `MATHBLOCK${mathBlocks.length}PLACEHOLDER`;
        mathBlocks.push({ type: 'display', content: math.trim() });
        return placeholder;
    });
    
    // Extract display math blocks (\[...\])
    processedContent = processedContent.replace(/\\\[([\s\S]+?)\\\]/g, (match, math) => {
        const placeholder = `MATHBLOCK${mathBlocks.length}PLACEHOLDER`;
        mathBlocks.push({ type: 'display', content: math.trim() });
        return placeholder;
    });

    // Extract inline math (\(...\))
    processedContent = processedContent.replace(/\\\(([\s\S]+?)\\\)/g, (match, math) => {
        const placeholder = `MATHINLINE${mathBlocks.length}PLACEHOLDER`;
        mathBlocks.push({ type: 'inline', content: math.trim() });
        return placeholder;
    });
    
    // Extract inline math ($...$) - but not $$ which we already handled
    processedContent = processedContent.replace(/\$([^\$\n]+?)\$/g, (match, math) => {
        const placeholder = `MATHINLINE${mathBlocks.length}PLACEHOLDER`;
        mathBlocks.push({ type: 'inline', content: math.trim() });
        return placeholder;
    });

    // Step 2: Process markdown
    const html = typeof marked.parse === 'function' ? marked.parse(processedContent) : marked(processedContent);
    
    // Step 3: Restore LaTeX blocks
    let finalHtml = html;
    mathBlocks.forEach((block, index) => {
        if (block.type === 'display') {
            const placeholder = `MATHBLOCK${index}PLACEHOLDER`;
            const mathHtml = `\\[${block.content}\\]`;
            finalHtml = finalHtml.replace(new RegExp(placeholder, 'g'), mathHtml);
        } else {
            const placeholder = `MATHINLINE${index}PLACEHOLDER`;
            const mathHtml = `<span class="math-inline">\\(${block.content}\\)</span>`;
            finalHtml = finalHtml.replace(new RegExp(placeholder, 'g'), mathHtml);
        }
    });
    
    // Convert currency placeholder back to $
    finalHtml = finalHtml.replace(/___CURRENCY_SYMBOL_PLACEHOLDER___/g, '$');
    
    return finalHtml;
}
