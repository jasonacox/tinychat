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
    saveConversations(conversations);
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
