// Configuration management

// LocalStorage keys
const STORAGE_KEY = 'tinychat_conversations';
const MARKDOWN_PREF_KEY = 'tinychat_markdown_enabled';
const MODEL_PREF_KEY = 'tinychat_selected_model';
const RLM_ENABLED_KEY = 'tinychat_rlm_enabled';
const RLM_THINKING_KEY = 'tinychat_rlm_thinking_enabled';
const SESSION_ID_KEY = 'tinychat_session_id';

// Global state
let appConfig = null;
let sessionId = null;

// Initialize session ID (async)
async function initSessionId() {
    sessionId = await storageAdapter.getItem(SESSION_ID_KEY);
    if (!sessionId) {
        sessionId = generateUUID();
        await storageAdapter.setItem(SESSION_ID_KEY, sessionId);
    }
    return sessionId;
}

// Get markdown preference
async function getMarkdownEnabled() {
    const stored = await storageAdapter.getItem(MARKDOWN_PREF_KEY);
    return stored === null ? true : stored === true;  // Default to true
}

// Save markdown preference
async function setMarkdownEnabled(enabled) {
    await storageAdapter.setItem(MARKDOWN_PREF_KEY, enabled);
}

// Get saved model preference
async function getSavedModel() {
    return await storageAdapter.getItem(MODEL_PREF_KEY);
}

// Save model preference
async function saveModelPreference(model) {
    await storageAdapter.setItem(MODEL_PREF_KEY, model);
}

// Get RLM enabled preference
async function getRlmEnabled() {
    const stored = await storageAdapter.getItem(RLM_ENABLED_KEY);
    return stored === null ? false : stored === true;  // Default to false
}

// Save RLM enabled preference
async function setRlmEnabled(enabled) {
    await storageAdapter.setItem(RLM_ENABLED_KEY, enabled);
}

// Get RLM thinking enabled preference
async function getRlmThinkingEnabled() {
    const stored = await storageAdapter.getItem(RLM_THINKING_KEY);
    return stored === null ? true : stored === true;  // Default to true
}

// Save RLM thinking enabled preference
async function setRlmThinkingEnabled(enabled) {
    await storageAdapter.setItem(RLM_THINKING_KEY, enabled);
}

// Load configuration from server
async function loadConfiguration() {
    try {
        const response = await fetch('/api/config');
        appConfig = await response.json();
        
        // Populate model dropdown
        const modelSelect = document.getElementById('model');
        modelSelect.innerHTML = '';
        
        const savedModel = await getSavedModel();
        let modelToSelect = savedModel && appConfig.available_models.includes(savedModel) 
            ? savedModel 
            : appConfig.default_model;
        
        appConfig.available_models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            if (model === modelToSelect) {
                option.selected = true;
            }
            modelSelect.appendChild(option);
        });
        
        // Set default temperature
        const temperatureSlider = document.getElementById('temperature');
        const temperatureValue = document.getElementById('temperature-value');
        temperatureSlider.value = appConfig.default_temperature;
        temperatureValue.textContent = appConfig.default_temperature;
        
        // Set version in footer
        if (appConfig.version) {
            document.getElementById('version').textContent = appConfig.version;
        }
        
        // Load conversations after config is ready
        await loadConversations();
        
        // Set focus to message input for better UX
        document.getElementById('messageInput').focus();
        
        console.log('Configuration loaded:', appConfig);
    } catch (error) {
        console.error('Failed to load configuration:', error);
        showError('Failed to load application configuration');
    }
}
