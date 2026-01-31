// IndexedDB storage management via localforage adapter

// Local storage helper functions (now async)
async function getConversations() {
    const stored = await storageAdapter.getItem(STORAGE_KEY);
    return stored || {};
}

async function saveConversations(conversations) {
    await storageAdapter.setItem(STORAGE_KEY, conversations);
}

async function getConversation(conversationId) {
    const conversations = await getConversations();
    return conversations[conversationId] || null;
}

async function saveConversation(conversationId, conversation) {
    const conversations = await getConversations();
    conversations[conversationId] = conversation;
    
    // Try to save
    try {
        await saveConversations(conversations);
    } catch (e) {
        if (e.name === 'QuotaExceededError') {
            console.warn('Storage quota exceeded. Attempting cleanup...');
            
            // Cleanup old images
            if (cleanupOldImages(conversations)) {
                // Try again after cleanup
                try {
                    await saveConversations(conversations);
                } catch (e2) {
                    showError('Storage full. Please delete some old conversations.');
                    throw e2;
                }
            } else {
                showError('Storage full. Please delete some conversations.');
                throw e;
            }
        } else {
            throw e;
        }
    }
}

/**
 * Clean up old images from conversations to free storage space.
 * Keeps images only in the most recent 5 conversations.
 */
function cleanupOldImages(conversations) {
    let cleaned = false;
    
    // Get conversations sorted by last_updated (newest first)
    const sorted = Object.entries(conversations).sort((a, b) => {
        const dateA = new Date(a[1].last_updated || a[1].created || 0);
        const dateB = new Date(b[1].last_updated || b[1].created || 0);
        return dateB - dateA;
    });
    
    // Keep images in top 5 conversations, remove from others
    sorted.forEach(([id, conv], index) => {
        if (index >= 5 && conv.messages) {
            conv.messages.forEach(msg => {
                if (msg.image) {
                    delete msg.image;
                    delete msg.image_type;
                    cleaned = true;
                }
            });
        }
    });
    
    if (cleaned) {
        console.log('Cleaned up images from old conversations');
    }
    
    return cleaned;
}

/**
 * Get estimated storage usage using Storage API.
 */
async function getStorageUsage() {
    const stats = await storageAdapter.getStorageStats();
    return stats.usedMB;
}

/**
 * Get size of conversations in storage.
 */
async function getConversationsSize() {
    const conversations = await storageAdapter.getItem(STORAGE_KEY);
    if (!conversations) return '0.00';
    // Size in MB
    const sizeBytes = JSON.stringify(conversations).length;
    return (sizeBytes / 1024 / 1024).toFixed(2);
}

async function deleteConversation(conversationId) {
    const conversations = await getConversations();
    delete conversations[conversationId];
    await saveConversations(conversations);
}

async function deleteConversationById(conversationId) {
    if (confirm('Delete this conversation? This cannot be undone.')) {
        await deleteConversation(conversationId);
        
        // If deleted conversation was active, clear current
        if (currentConversationId === conversationId) {
            currentConversationId = null;
            document.getElementById('messages').innerHTML = '';
        }
        
        // Reload conversation list
        await loadConversations();
    }
}

async function clearAllConversations() {
    const conversations = await getConversations();
    const count = Object.keys(conversations).length;
    
    if (count === 0) {
        showError('No conversations to clear');
        return;
    }
    
    if (confirm(`Delete all ${count} conversation${count > 1 ? 's' : ''}? This cannot be undone.`)) {
        // Clear storage
        await storageAdapter.removeItem(STORAGE_KEY);
        
        // Clear current conversation
        currentConversationId = null;
        
        // Clear UI
        document.getElementById('messages').innerHTML = `
            <div style="text-align: center; color: #999; margin-top: 50px;">
                Welcome to TinyChat! Start a conversation by typing a message below.
            </div>
        `;
        
        // Reload conversation list (will be empty)
        await loadConversations();
        
        showError('All conversations cleared');
    }
}

// UUID generation
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}
