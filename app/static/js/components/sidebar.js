// Sidebar component - conversation management

async function loadConversations() {
    const conversations = await getConversations();
    const container = document.getElementById('conversations');
    container.innerHTML = '';
    
    // Convert to array and sort by last updated
    const convArray = Object.entries(conversations).map(([id, conv]) => ({
        id,
        title: conv.title || 'New Conversation',
        message_count: conv.messages?.length || 0,
        last_updated: conv.last_updated || new Date().toISOString()
    }));
    
    convArray.sort((a, b) => new Date(b.last_updated) - new Date(a.last_updated));
    
    convArray.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'conversation-item';
        if (conv.id === currentConversationId) {
            item.classList.add('active');
        }
        
        item.innerHTML = `
            <div class="conversation-info">
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-meta">${conv.message_count} messages</div>
            </div>
            <button class="delete-btn" onclick="event.stopPropagation(); deleteConversationById('${conv.id}')">Delete</button>
        `;
        
        // Add click handler to conversation info only
        item.querySelector('.conversation-info').onclick = () => loadConversation(conv.id);
        
        container.appendChild(item);
    });
}

async function createNewConversation() {
    const conversationId = generateUUID();
    const conversation = {
        title: 'New Conversation',
        messages: [],
        created: new Date().toISOString(),
        last_updated: new Date().toISOString()
    };

    await saveConversation(conversationId, conversation);
    currentConversationId = conversationId;

    // Reset token counter for new conversation
    resetTokenTotal();

    document.getElementById('messages').innerHTML = `
        <div style="text-align: center; color: #999; margin-top: 50px;">
            New conversation started! Type a message to begin.
        </div>
    `;

    await loadConversations();

    // Set focus to message input for immediate typing
    document.getElementById('messageInput').focus();
}

async function loadConversation(conversationId) {
    currentConversationId = conversationId;
    
    // Update active conversation in sidebar
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Find and mark the conversation item as active
    const activeItem = document.querySelector(`.conversation-item [onclick*="'${conversationId}'"]`)?.closest('.conversation-item');
    if (activeItem) {
        activeItem.classList.add('active');
    }
    
    const conversation = await getConversation(conversationId);
    if (!conversation) {
        showError('Conversation not found');
        return;
    }
    
    const container = document.getElementById('messages');
    container.innerHTML = '';

    // Recalculate token totals from stored usage data
    recalcTokenTotal(conversation.messages);

    // Use for...of instead of forEach to support async/await
    for (const message of conversation.messages) {
        // For assistant messages with generated images, we need special handling
        if (message.role === 'assistant' && message.has_image && message.image_data) {
            // Add the text message first
            const messageElement = await addMessageToUI(
                message.role,
                message.content,
                message.timestamp,
                true,  // useMarkdown
                null,  // no fileData yet, we'll add it separately
                message.model,  // pass stored model name
                message.usage || null  // pass stored usage data
            );

            // Now add the image container with download button (same as during generation)
            const messageContent = messageElement.querySelector('.message-content');
            const imageContainer = createImageContainer(message.image_data);
            messageContent.appendChild(imageContainer);
        } else {
            // Regular message handling (user messages or assistant text without images/documents)
            let fileData = null;

            // Check for image attachment
            if (message.image && message.image_type) {
                fileData = {
                    type: 'image',
                    data: {
                        data: message.image,
                        type: message.image_type,
                        isComplete: false  // User uploaded images need data: prefix
                    }
                };
            }
            // Check for document attachment
            else if (message.document) {
                fileData = {
                    type: 'document',
                    data: message.document
                };
            }

            await addMessageToUI(
                message.role,
                message.content,
                message.timestamp,
                message.role === 'assistant',
                fileData,
                message.model,  // pass stored model name
                message.usage || null  // pass stored usage data
            );
        }
    }

    scrollToBottom();
}

// Helper function to create image container with viewer
function createImageContainer(imageData) {
    const imageContainer = document.createElement('div');
    imageContainer.className = 'image-container';
    imageContainer.style.marginTop = '10px';
    
    const img = document.createElement('img');
    img.src = imageData;
    img.style.width = '25%';
    img.style.borderRadius = '8px';
    img.style.display = 'block';
    img.style.cursor = 'pointer';
    img.title = 'Click to view full size';
    
    // Click to view full size
    img.onclick = () => {
        const modal = document.createElement('div');
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
        modal.style.display = 'flex';
        modal.style.justifyContent = 'center';
        modal.style.alignItems = 'center';
        modal.style.zIndex = '10000';
        modal.style.cursor = 'pointer';
        
        const fullImg = document.createElement('img');
        fullImg.src = imageData;
        fullImg.style.maxWidth = '90%';
        fullImg.style.maxHeight = '90%';
        fullImg.style.borderRadius = '8px';
        
        modal.appendChild(fullImg);
        modal.onclick = () => document.body.removeChild(modal);
        
        document.body.appendChild(modal);
    };
    
    const downloadBtn = document.createElement('button');
    downloadBtn.textContent = '⬇ Download Image';
    downloadBtn.className = 'download-btn';
    downloadBtn.style.marginTop = '8px';
    downloadBtn.style.padding = '8px 16px';
    downloadBtn.style.backgroundColor = '#2196f3';
    downloadBtn.style.color = 'white';
    downloadBtn.style.border = 'none';
    downloadBtn.style.borderRadius = '4px';
    downloadBtn.style.cursor = 'pointer';
    downloadBtn.onclick = () => {
        const a = document.createElement('a');
        a.href = imageData;
        a.download = `tinychat-image-${Date.now()}.jpg`;
        a.click();
    };
    
    imageContainer.appendChild(img);
    imageContainer.appendChild(downloadBtn);
    
    return imageContainer;
}

// Export/Import functions are in /static/js/utils/export-import.js
