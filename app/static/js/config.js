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
let sessionId = localStorage.getItem(SESSION_ID_KEY);

// Get markdown preference
function getMarkdownEnabled() {
    const stored = localStorage.getItem(MARKDOWN_PREF_KEY);
    return stored === null ? true : stored === 'true';  // Default to true
}

// Save markdown preference
function setMarkdownEnabled(enabled) {
    localStorage.setItem(MARKDOWN_PREF_KEY, enabled.toString());
}

// Get saved model preference
function getSavedModel() {
    return localStorage.getItem(MODEL_PREF_KEY);
}

// Save model preference
function saveModelPreference(model) {
    localStorage.setItem(MODEL_PREF_KEY, model);
}

// Get RLM enabled preference
function getRlmEnabled() {
    const stored = localStorage.getItem(RLM_ENABLED_KEY);
    return stored === null ? false : stored === 'true';  // Default to false
}

// Save RLM enabled preference
function setRlmEnabled(enabled) {
    localStorage.setItem(RLM_ENABLED_KEY, enabled.toString());
}

// Get RLM thinking enabled preference
function getRlmThinkingEnabled() {
    const stored = localStorage.getItem(RLM_THINKING_KEY);
    return stored === null ? true : stored === 'true';  // Default to true
}

// Save RLM thinking enabled preference
function setRlmThinkingEnabled(enabled) {
    localStorage.setItem(RLM_THINKING_KEY, enabled.toString());
}

// Load configuration from server
async function loadConfiguration() {
    try {
        const response = await fetch('/api/config');
        appConfig = await response.json();
        
        // Populate model dropdown
        const modelSelect = document.getElementById('model');
        modelSelect.innerHTML = '';
        
        const savedModel = getSavedModel();
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
        loadConversations();
        
        // Set focus to message input for better UX
        document.getElementById('messageInput').focus();
        
        console.log('Configuration loaded:', appConfig);
    } catch (error) {
        console.error('Failed to load configuration:', error);
        showError('Failed to load application configuration');
    }
}
