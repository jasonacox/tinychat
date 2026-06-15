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
            const choice = prompt(
                `Import ${importCount} conversation${importCount !== 1 ? 's' : ''}.\n\n` +
                `You currently have ${existingCount} conversation${existingCount !== 1 ? 's' : ''}.\n\n` +
                `Type "merge" to add imported conversations to existing ones,\n` +
                `or "replace" to overwrite all existing conversations.\n\n` +
                `(Cancel to abort)`,
                'merge'
            );

            if (choice === null) {
                fileInput.value = '';
                return; // User cancelled
            }

            mode = choice.trim().toLowerCase();
            if (mode !== 'merge' && mode !== 'replace') {
                showError('Import cancelled. Please type "merge" or "replace".');
                fileInput.value = '';
                return;
            }
        }

        // Perform the import
        if (mode === 'replace') {
            // Replace: clear existing and set imported
            await saveConversations(importedConversations);
        } else {
            // Merge: combine existing with imported (imported wins on ID conflict)
            const merged = { ...existingConversations, ...importedConversations };
            await saveConversations(merged);
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
 * Validate imported data has the expected TinyChat export structure.
 * Returns an error message string if invalid, or null if valid.
 */
function validateImportData(data) {
    if (!data || typeof data !== 'object') {
        return 'Invalid file: not a JSON object.';
    }

    // Check for the expected export format
    if (!data.conversations || typeof data.conversations !== 'object') {
        // Also accept legacy format from storageAdapter.exportData()
        if (data.data && data.data.tinychat_conversations) {
            // Migrate legacy format in-place
            data.conversations = data.data.tinychat_conversations;
            data.conversation_count = Object.keys(data.conversations).length;
            data.version = data.version || '0.9';
            data.export_date = data.exportDate || data.export_date || 'unknown';
            return null;
        }
        return 'Invalid export file: missing "conversations" field. This does not appear to be a TinyChat export.';
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
