// Chat component - messaging and streaming

let currentConversationId = null;
let isStreaming = false;

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    // Allow sending if we have a message OR an attached image
    if ((!message && !hasAttachedImage()) || isStreaming) return;
    
    const temperature = parseFloat(document.getElementById('temperature').value);
    const model = document.getElementById('model').value;
    const rlm = document.getElementById('rlmToggle').checked;
    const show_rlm_thinking = document.getElementById('rlmThinkingToggle').checked;
    
    // Create conversation if needed
    if (!currentConversationId) {
        currentConversationId = generateUUID();
        const conversation = {
            title: 'New Conversation',
            messages: [],
            created: new Date().toISOString(),
            last_updated: new Date().toISOString()
        };
        await saveConversation(currentConversationId, conversation);
    }
    
    // Get current conversation
    const conversation = await getConversation(currentConversationId);
    
    // Update title with first message if still using default
    const displayMessage = message || '(image)';
    if (conversation.title === 'New Conversation' && conversation.messages.length === 0) {
        conversation.title = displayMessage.substring(0, 50) + (displayMessage.length > 50 ? '...' : '');
    }
    
    // Build user message
    const userMessage = {
        role: 'user',
        content: message || '(image)',
        timestamp: new Date().toISOString()
    };
    
    // Add image data if attached
    const imageData = getAttachedImage();
    if (imageData) {
        userMessage.image = imageData.data;
        userMessage.image_type = imageData.type;
    }
    
    // Add user message to local storage
    conversation.messages.push(userMessage);
    conversation.last_updated = new Date().toISOString();
    await saveConversation(currentConversationId, conversation);
    
    // Clear input and add user message to UI
    input.value = '';
    input.style.height = 'auto';
    addMessageToUI('user', message || '(image)', new Date().toISOString(), false, imageData);
    
    // Clear attached image
    removeAttachedImage();
    
    isStreaming = true;
    document.getElementById('sendBtn').disabled = true;
    document.getElementById('typing').style.display = 'block';
    
    // Get markdown preference once at start (it's async now)
    const markdownEnabled = await getMarkdownEnabled();
    
    try {
        // Send conversation history to API (includes image data)
        // Find the most recent N messages with images (N = max_images_in_context from config)
        const maxImagesInContext = appConfig?.max_images_in_context || 1;
        const imageIndices = [];
        for (let i = conversation.messages.length - 1; i >= 0 && imageIndices.length < maxImagesInContext; i--) {
            if (conversation.messages[i].image || conversation.messages[i].has_image) {
                imageIndices.push(i);
            }
        }
        
        const apiMessages = conversation.messages.map((m, index) => {
            const msg = {
                role: m.role,
                content: m.content
            };
            
            // Only include image data for the most recent N images
            if (imageIndices.includes(index)) {
                // Include user-uploaded image data if present
                if (m.image) {
                    msg.image = m.image;
                    msg.image_type = m.image_type;
                }
                // Include generated image data if present (for vision models to see their own output)
                else if (m.has_image && m.image_data) {
                    // Extract base64 data from data URL if needed
                    const dataUrlMatch = m.image_data.match(/^data:image\/(\w+);base64,(.+)$/);
                    if (dataUrlMatch) {
                        msg.image = dataUrlMatch[2];  // Base64 data
                        msg.image_type = `image/${dataUrlMatch[1]}`;  // e.g., image/png
                    } else {
                        // If it's already in the right format, use as-is
                        msg.image = m.image_data;
                        msg.image_type = 'image/png';
                    }
                }
            }
            
            return msg;
        });
        
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: apiMessages,  // Send full conversation history with images
                temperature,
                model,
                session_id: sessionId,
                rlm: rlm,
                rlm_passcode: rlm ? rlmSecurity.getCookie(rlmSecurity.cookieName) : null,  // SECURITY: Send passcode for backend validation
                show_rlm_thinking: show_rlm_thinking
            })
        });
        
        if (!response.ok) {
            // Try to parse JSON error body for a friendlier message
            let errText;
            try {
                const errBody = await response.json();
                if (errBody && errBody.error) {
                    errText = errBody.detail ? `${errBody.error}: ${errBody.detail}` : errBody.error;
                } else {
                    errText = JSON.stringify(errBody);
                }
            } catch (e) {
                errText = `HTTP ${response.status}`;
            }
            throw new Error(errText);
        }
        
        await handleStreamResponse(response, conversation, markdownEnabled);
        
    } catch (error) {
        showError('Failed to send message: ' + error.message);
    } finally {
        isStreaming = false;
        document.getElementById('sendBtn').disabled = false;
        document.getElementById('typing').style.display = 'none';
        await loadConversations();  // Refresh sidebar
        await updateStorageMeter();  // Update storage meter after saving
    }
}

async function handleStreamResponse(response, conversation, markdownEnabled) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    let assistantMessageElement = null;
    let assistantContent = '';
    let errorOccurred = false;
    let buffer = '';  // Buffer for incomplete lines
    
    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;  // Add to buffer
            
            // Split on newlines but keep the last incomplete line in buffer
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';  // Keep last incomplete line
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    
                    if (data === '[DONE]') {
                        continue; // Message will be saved in finally block
                    }
                    
                    try {
                        const parsed = JSON.parse(data);
                        
                        if (parsed.error) {
                            errorOccurred = true;
                            
                            // Check for vision-not-supported error
                            if (parsed.error === 'vision_not_supported' && parsed.message) {
                                // Show friendly vision error message
                                showError('⚠️ ' + parsed.message);
                                
                                // If remove_images flag is set, remove all images from conversation
                                if (parsed.remove_images) {
                                    const conversation = await getConversation(currentConversationId);
                                    if (conversation && conversation.messages) {
                                        conversation.messages.forEach(msg => {
                                            if (msg.image) {
                                                delete msg.image;
                                                delete msg.image_type;
                                            }
                                        });
                                        await saveConversation(currentConversationId, conversation);
                                        console.log('Removed images from conversation after vision error');
                                    }
                                }
                                
                                return; // Exit early - don't save error message
                            }
                            
                            // Clean up the error message for display
                            let errorMsg = parsed.error;
                            
                            // Extract the useful part if it's a nested JSON error
                            try {
                                const errorMatch = errorMsg.match(/'error': '([^']+)'/);
                                if (errorMatch) {
                                    errorMsg = errorMatch[1];
                                }
                            } catch (e) {
                                // Use original message if extraction fails
                            }
                            
                            throw new Error(errorMsg);
                        }
                        
                        // Handle RLM status updates (when thinking is hidden)
                        if (parsed.rlm_status) {
                            const rlmStatusIndicator = document.getElementById('rlmStatus');
                            rlmStatusIndicator.textContent = '🧠 ' + parsed.rlm_status;
                            rlmStatusIndicator.style.display = 'block';
                        }
                        
                        if (parsed.content) {
                            if (!assistantMessageElement) {
                                assistantMessageElement = await addMessageToUI('assistant', '', null, true);
                            }
                            
                            assistantContent += parsed.content;
                            const messageContent = assistantMessageElement.querySelector('.message-content');
                            
                            if (markdownEnabled && typeof marked !== 'undefined') {
                                try {
                                    // Render markdown with math protection
                                    const html = renderMarkdownWithMath(assistantContent);
                                    messageContent.innerHTML = html;
                                    messageContent.classList.add('markdown');
                                    // Apply syntax highlighting to code blocks
                                    if (typeof hljs !== 'undefined') {
                                        messageContent.querySelectorAll('pre code').forEach(block => {
                                            hljs.highlightElement(block);
                                        });
                                    }
                                    // Render math equations
                                    renderMath(messageContent);
                                } catch (e) {
                                    console.error('Markdown parsing error:', e);
                                    messageContent.textContent = assistantContent;
                                    messageContent.classList.remove('markdown');
                                }
                            } else {
                                messageContent.textContent = assistantContent;
                                messageContent.classList.remove('markdown');
                            }
                            scrollToBottom();
                        }
                        
                        // Handle image response
                        if (parsed.image) {
                            if (!assistantMessageElement) {
                                assistantMessageElement = await addMessageToUI('assistant', parsed.content || 'Here is your image.');
                                assistantContent = parsed.content || 'Here is your image.';
                            }
                            
                            // Store image data temporarily for saving to conversation
                            window._lastGeneratedImage = parsed.image;
                            
                            // Add image to the message
                            const messageContent = assistantMessageElement.querySelector('.message-content');
                            const imageContainer = createImageContainer(parsed.image);
                            messageContent.appendChild(imageContainer);
                            scrollToBottom();
                        }
                    } catch (e) {
                        // If it's our error from above, re-throw it
                        if (errorOccurred || e.message.includes('model') || e.message.includes('Invalid')) {
                            throw e;
                        }
                        // Otherwise, only log unexpected JSON parse errors
                        if (!e.message.includes('Unexpected token')) {
                            console.error('Parse error:', e);
                        }
                    }
                }
            }
        }
    } catch (error) {
        showError('Error: ' + error.message);
        // Don't save partial content if there was an error
        errorOccurred = true;
    } finally {
        // Hide RLM status indicator
        document.getElementById('rlmStatus').style.display = 'none';
        
        // Only save assistant message if we got content and no error occurred
        if (assistantContent && !errorOccurred) {
            const assistantMessage = {
                role: 'assistant',
                content: assistantContent,
                timestamp: new Date().toISOString()
            };
            
            // If this response included an image, store it for display purposes
            // Mark it so we can filter it out when sending back to API
            if (window._lastGeneratedImage) {
                assistantMessage.image_data = window._lastGeneratedImage;
                assistantMessage.has_image = true;
                window._lastGeneratedImage = null;  // Clear after storing
            }
            
            conversation.messages.push(assistantMessage);
            conversation.last_updated = new Date().toISOString();
            await saveConversation(currentConversationId, conversation);
        }
    }
}

async function addMessageToUI(role, content, timestamp, useMarkdown = false, imageData = null) {
    const container = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    
    // Create message structure safely
    const messageHeader = document.createElement('div');
    messageHeader.className = 'message-header';
    
    const roleSpan = document.createElement('span');
    roleSpan.className = `message-role ${role}`;
    roleSpan.textContent = role === 'user' ? 'You' : 'Assistant';
    
    const timestampSpan = document.createElement('span');
    timestampSpan.className = 'message-timestamp';
    timestampSpan.textContent = time;
    
    messageHeader.appendChild(roleSpan);
    messageHeader.appendChild(timestampSpan);
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    // Add image if present
    if (imageData) {
        const img = document.createElement('img');
        // Check if this is already a complete data URL (generated images)
        if (imageData.isComplete) {
            img.src = imageData.data;
        } else {
            // User uploaded image - needs data: prefix
            img.src = `data:${imageData.type};base64,${imageData.data}`;
        }
        img.className = 'message-image';
        img.alt = 'Uploaded image';
        img.title = 'Click to view full size';
        
        // Click to view full size
        img.onclick = () => {
            showImageModal(img.src);
        };
        
        messageContent.appendChild(img);
    }
    
    // Add text content if present
    if (content) {
        // Apply markdown rendering if enabled and requested
        const markdownEnabled = await getMarkdownEnabled();
        
        if (useMarkdown && markdownEnabled && role === 'assistant' && typeof marked !== 'undefined') {
            try {
                // Render markdown with math protection
                const html = renderMarkdownWithMath(content);
                const textDiv = document.createElement('div');
                textDiv.innerHTML = html;
                textDiv.classList.add('markdown');
                messageContent.appendChild(textDiv);
                
                // Apply syntax highlighting to code blocks
                if (typeof hljs !== 'undefined') {
                    textDiv.querySelectorAll('pre code').forEach(block => {
                        hljs.highlightElement(block);
                    });
                }
                // Render math equations
                renderMath(textDiv);
            } catch (e) {
                console.error('Markdown parsing error:', e);
                const textNode = document.createTextNode(content);
                messageContent.appendChild(textNode);
            }
        } else {
            const textNode = document.createTextNode(content);
            messageContent.appendChild(textNode);
        }
        
        // Add markdown class if applicable
        if (useMarkdown && markdownEnabled && role === 'assistant') {
            messageContent.classList.add('markdown');
        }
    }
    
    messageDiv.appendChild(messageHeader);
    messageDiv.appendChild(messageContent);
    
    // Clear welcome message if it exists
    if (container.children.length === 1 && container.firstElementChild.style.textAlign === 'center') {
        container.innerHTML = '';
    }
    
    container.appendChild(messageDiv);
    scrollToBottom();
    
    return messageDiv;
}

function showError(message) {
    const container = document.getElementById('messages');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    container.appendChild(errorDiv);
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('messages');
    container.scrollTop = container.scrollHeight;
}

/**
 * Show full-size image in a modal overlay.
 */
function showImageModal(imageSrc) {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.className = 'image-modal';
    modal.innerHTML = `
        <div class="image-modal-overlay"></div>
        <div class="image-modal-content">
            <button class="image-modal-close" title="Close (Esc)">×</button>
            <img src="${imageSrc}" alt="Full size image">
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close handlers
    const closeModal = () => {
        document.body.removeChild(modal);
        document.removeEventListener('keydown', handleEscape);
    };
    
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    };
    
    // Click overlay or close button to close
    modal.querySelector('.image-modal-overlay').onclick = closeModal;
    modal.querySelector('.image-modal-close').onclick = closeModal;
    
    // ESC key to close
    document.addEventListener('keydown', handleEscape);
}
