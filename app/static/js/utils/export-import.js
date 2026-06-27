/**
 * Export/Import Conversations
 *
 * Provides manual backup/restore for TinyChat conversations.
 * Exports conversations as a structured JSON file with metadata.
 * Imports validate structure and offer merge or replace options.
 */

const EXPORT_VERSION = '1.0';
const MAX_IMPORT_SIZE_MB = 100;

/**
 * Export all conversations to a downloadable JSON file.
 * Includes metadata: export_date, version, conversation_count.
 */
async function exportConversations() {
    try {
        const conversations = await getConversations();
        const conversationCount = Object.keys(conversations).length;

        if (conversationCount === 0) {
            showError('No conversations to export.');
            return;
        }

        const exportData = {
            export_date: new Date().toISOString(),
            version: EXPORT_VERSION,
            conversation_count: conversationCount,
            conversations: conversations
        };

        const json = JSON.stringify(exportData, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const dateStr = new Date().toISOString().split('T')[0];
        const a = document.createElement('a');
        a.href = url;
        a.download = `tinychat-export-${dateStr}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showInfo(`Exported ${conversationCount} conversation${conversationCount !== 1 ? 's' : ''} successfully.`);
    } catch (error) {
        console.error('Export failed:', error);
        showError('Failed to export conversations: ' + error.message);
    }
}

/**
 * Import conversations from a JSON file selected via file picker.
 * Validates structure and asks user whether to merge or replace.
 */
async function importConversations(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Reset file input so the same file can be re-selected
    const fileInput = event.target;

    try {
        // Check file size
        const fileSizeMB = file.size / 1024 / 1024;
        if (fileSizeMB > MAX_IMPORT_SIZE_MB) {
            throw new Error(`File too large (${fileSizeMB.toFixed(1)} MB). Maximum is ${MAX_IMPORT_SIZE_MB} MB.`);
        }

        const text = await file.text();

        let data;
        try {
            data = JSON.parse(text);
        } catch (e) {
            throw new Error('File contains malformed JSON. Please select a valid TinyChat export file.');
        }

        // Validate the export structure
        const validationError = validateImportData(data);
        if (validationError) {
            throw new Error(validationError);
        }

        const importedConversations = data.conversations;
        const importCount = Object.keys(importedConversations).length;

        if (importCount === 0) {
            showError('The export file contains no conversations.');
            fileInput.value = '';
            return;
        }

        // Ask user whether to merge or replace
        const existingConversations = await getConversations();
        const existingCount = Object.keys(existingConversations).length;

        let mode = 'merge'; // default
        if (existingCount > 0) {
            mode = await showImportModeModal(importCount, existingCount);
            if (mode === null) {
                fileInput.value = '';
                return; // User cancelled
            }
        }

        // Sanitize imported conversations to prevent XSS via title or message content
        const sanitized = {};
        for (const [id, conv] of Object.entries(importedConversations)) {
            sanitized[id] = sanitizeConversation(conv);
        }

        // Perform the import
        if (mode === 'replace') {
            // Replace: clear existing and set imported
            await saveConversations(sanitized);
        } else {
            // Merge: add only conversations that don't already exist (no silent overwrite)
            const merged = { ...existingConversations };
            let skipped = 0;
            for (const [id, conv] of Object.entries(sanitized)) {
                if (merged[id]) {
                    skipped++;
                } else {
                    merged[id] = conv;
                }
            }
            await saveConversations(merged);
            if (skipped > 0) {
                showInfo(`Skipped ${skipped} conversation${skipped !== 1 ? 's' : ''} with existing IDs.`);
            }
        }

        // Clear current conversation if it was replaced
        if (mode === 'replace' && currentConversationId && !importedConversations[currentConversationId]) {
            currentConversationId = null;
            document.getElementById('messages').innerHTML = '';
        }

        // Reload UI
        await loadConversations();
        if (typeof updateStorageMeter === 'function') {
            await updateStorageMeter();
        }

        const actionText = mode === 'replace' ? 'Replaced with' : 'Merged';
        showInfo(`${actionText} ${importCount} conversation${importCount !== 1 ? 's' : ''} successfully.`);
    } catch (error) {
        console.error('Import failed:', error);
        showError('Import failed: ' + error.message);
    }

    fileInput.value = '';
}

/**
 * Sanitize a conversation object to prevent XSS when rendered in the DOM.
 * Strips HTML tags from title and message content fields as defense-in-depth.
 *
 * Note: all render paths are already safe —
 *   • markdown mode: content → renderMarkdownWithMath() → DOMPurify.sanitize() → innerHTML
 *   • plain mode:    content → document.createTextNode() (never parsed as HTML)
 * This sanitization is an extra layer applied once at import time so that any
 * future render path added without DOMPurify cannot accidentally execute
 * injected HTML from an imported file.
 */
function sanitizeConversation(conv) {
    const sanitized = { ...conv };
    if (sanitized.title) {
        sanitized.title = stripHtml(sanitized.title);
    }
    if (Array.isArray(sanitized.messages)) {
        sanitized.messages = sanitized.messages.map(msg => {
            if (msg && typeof msg === 'object' && msg.content) {
                return { ...msg, content: stripHtml(String(msg.content)) };
            }
            return msg;
        });
    }
    return sanitized;
}

/**
 * Strip HTML tags from a string, returning plain text.
 * Uses the browser's HTML parser to extract text content,
 * which removes all tags while preserving their visible text.
 *
 * Example: stripHtml('<b>Hello</b><script>evil()</script>') → 'Helloevil()'
 */
function stripHtml(str) {
    const div = document.createElement('div');
    div.innerHTML = str;
    return div.textContent || div.innerText || '';
}

/**
 * Validate imported data has the expected TinyChat export structure.
 * Returns an error message string if invalid, or null if valid.
 */
function validateImportData(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
        return 'Invalid file: not a JSON object.';
    }

    // Check for the expected export format
    if (!data.conversations || typeof data.conversations !== 'object' || Array.isArray(data.conversations)) {
        // Also accept legacy format from storageAdapter.exportData()
        if (data.data && data.data.tinychat_conversations &&
            typeof data.data.tinychat_conversations === 'object' &&
            !Array.isArray(data.data.tinychat_conversations)) {
            // Migrate legacy format in-place
            data.conversations = data.data.tinychat_conversations;
            data.conversation_count = Object.keys(data.conversations).length;
            data.version = data.version || '0.9';
            data.export_date = data.exportDate || data.export_date || 'unknown';
            return null;
        }
        return 'Invalid export file: missing or invalid "conversations" field. Expected an object map of conversations.';
    }

    // Validate conversation entries
    const entries = Object.entries(data.conversations);
    for (const [id, conv] of entries) {
        if (!conv || typeof conv !== 'object') {
            return `Invalid conversation entry "${id}": not an object.`;
        }
        if (!Array.isArray(conv.messages)) {
            return `Invalid conversation "${conv.title || id}": missing or invalid "messages" array.`;
        }
    }

    return null; // Valid
}

/**
 * Show a styled modal asking the user to choose merge or replace.
 * Returns 'merge', 'replace', or null (cancelled).
 */
function showImportModeModal(importCount, existingCount) {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.className = 'import-mode-modal';

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';

        const content = document.createElement('div');
        content.className = 'modal-content';

        const title = document.createElement('h3');
        title.textContent = 'Import Conversations';

        const body = document.createElement('p');
        body.textContent =
            `Importing ${importCount} conversation${importCount !== 1 ? 's' : ''}. ` +
            `You currently have ${existingCount} conversation${existingCount !== 1 ? 's' : ''}.`;

        const buttons = document.createElement('div');
        buttons.className = 'modal-buttons';

        const mergeBtn = document.createElement('button');
        mergeBtn.className = 'btn-merge';
        mergeBtn.textContent = 'Merge';
        mergeBtn.title = 'Add imported conversations alongside existing ones';

        const replaceBtn = document.createElement('button');
        replaceBtn.className = 'btn-replace';
        replaceBtn.textContent = 'Replace All';
        replaceBtn.title = 'Overwrite all existing conversations with the import';

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn-cancel';
        cancelBtn.textContent = 'Cancel';

        buttons.appendChild(mergeBtn);
        buttons.appendChild(replaceBtn);
        buttons.appendChild(cancelBtn);

        content.appendChild(title);
        content.appendChild(body);
        content.appendChild(buttons);
        modal.appendChild(overlay);
        modal.appendChild(content);
        document.body.appendChild(modal);

        function close(result) {
            document.body.removeChild(modal);
            resolve(result);
        }

        mergeBtn.onclick = () => close('merge');
        replaceBtn.onclick = () => close('replace');
        cancelBtn.onclick = () => close(null);
        overlay.onclick = () => close(null);

        // ESC to cancel
        function onKey(e) {
            if (e.key === 'Escape') {
                document.removeEventListener('keydown', onKey);
                close(null);
            }
        }
        document.addEventListener('keydown', onKey);

        // Focus merge button by default
        mergeBtn.focus();
    });
}
