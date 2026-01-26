// localStorage management

// Local storage helper functions
function getConversations() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
}

function saveConversations(conversations) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

function getConversation(conversationId) {
    const conversations = getConversations();
    return conversations[conversationId] || null;
}

function saveConversation(conversationId, conversation) {
    const conversations = getConversations();
    conversations[conversationId] = conversation;
    
    // Try to save
    try {
        saveConversations(conversations);
    } catch (e) {
        if (e.name === 'QuotaExceededError') {
            console.warn('localStorage quota exceeded. Attempting cleanup...');
            
            // Cleanup old images
            if (cleanupOldImages(conversations)) {
                // Try again after cleanup
                try {
                    saveConversations(conversations);
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
 * Get estimated localStorage usage.
 */
function getStorageUsage() {
    let total = 0;
    for (let key in localStorage) {
        if (localStorage.hasOwnProperty(key)) {
            total += localStorage[key].length + key.length;
        }
    }
    // Convert to MB
    return (total / 1024 / 1024).toFixed(2);
}

/**
 * Get size of conversations in localStorage.
 */
function getConversationsSize() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return 0;
    // Size in MB
    return (stored.length / 1024 / 1024).toFixed(2);
}

function deleteConversation(conversationId) {
    const conversations = getConversations();
    delete conversations[conversationId];
    saveConversations(conversations);
}

function deleteConversationById(conversationId) {
    if (confirm('Delete this conversation? This cannot be undone.')) {
        deleteConversation(conversationId);
        
        // If deleted conversation was active, clear current
        if (currentConversationId === conversationId) {
            currentConversationId = null;
            document.getElementById('messages').innerHTML = '';
        }
        
        // Reload conversation list
        loadConversations();
    }
}

function clearAllConversations() {
    const conversations = getConversations();
    const count = Object.keys(conversations).length;
    
    if (count === 0) {
        showError('No conversations to clear');
        return;
    }
    
    if (confirm(`Delete all ${count} conversation${count > 1 ? 's' : ''}? This cannot be undone.`)) {
        // Clear localStorage
        localStorage.removeItem(STORAGE_KEY);
        
        // Clear current conversation
        currentConversationId = null;
        
        // Clear UI
        document.getElementById('messages').innerHTML = `
            <div style="text-align: center; color: #999; margin-top: 50px;">
                Welcome to TinyChat! Start a conversation by typing a message below.
            </div>
        `;
        
        // Reload conversation list (will be empty)
        loadConversations();
        
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
