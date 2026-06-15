// Configuration management

// LocalStorage keys
const STORAGE_KEY = 'tinychat_conversations';
const MARKDOWN_PREF_KEY = 'tinychat_markdown_enabled';
const MODEL_PREF_KEY = 'tinychat_selected_model';
const BACKEND_PREF_KEY = 'tinychat_selected_backend';
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

// Get saved backend preference
async function getSavedBackend() {
    return await storageAdapter.getItem(BACKEND_PREF_KEY);
}

// Save backend preference
async function saveBackendPreference(backend) {
    await storageAdapter.setItem(BACKEND_PREF_KEY, backend);
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

// Get current backend name (returns null if single-backend / default)
function getCurrentBackend() {
    const backendSelect = document.getElementById('backend');
    if (!backendSelect) return null;
    return backendSelect.value || null;
}

// Populate model dropdown for a given backend
async function populateModelsForBackend(backendName) {
    const modelSelect = document.getElementById('model');
    modelSelect.innerHTML = '';

    // Find the backend's model list
    let models = appConfig.available_models;  // fallback
    if (appConfig.backends && appConfig.backends.length > 1 && backendName) {
        const backend = appConfig.backends.find(b => b.name === backendName);
        if (backend && backend.models && backend.models.length > 0) {
            models = backend.models;
        }
    }

    const savedModel = await getSavedModel();
    let modelToSelect;

    // Check URL param
    const urlParams = new URLSearchParams(window.location.search);
    const urlModel = urlParams.get('model');

    // Priority: URL parameter > saved preference > first in list
    if (urlModel && models.includes(urlModel)) {
        modelToSelect = urlModel;
        await saveModelPreference(urlModel);
    } else if (savedModel && models.includes(savedModel)) {
        modelToSelect = savedModel;
    } else {
        modelToSelect = models[0] || appConfig.default_model;
    }

    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        if (model === modelToSelect) {
            option.selected = true;
        }
        modelSelect.appendChild(option);
    });
}

// Load configuration from server
async function loadConfiguration() {
    try {
        const response = await fetch('/api/config');
        appConfig = await response.json();

        // Setup backend selector if multiple backends are configured
        const backendGroup = document.getElementById('backendGroup');
        const backendSelect = document.getElementById('backend');

        if (appConfig.backends && appConfig.backends.length > 1) {
            backendGroup.style.display = '';
            backendSelect.innerHTML = '';

            const savedBackend = await getSavedBackend();
            let backendToSelect = null;

            // Check URL param for backend
            const urlParams = new URLSearchParams(window.location.search);
            const urlBackend = urlParams.get('backend');

            const backendNames = appConfig.backends.map(b => b.name);

            if (urlBackend && backendNames.includes(urlBackend)) {
                backendToSelect = urlBackend;
                await saveBackendPreference(urlBackend);
            } else if (savedBackend && backendNames.includes(savedBackend)) {
                backendToSelect = savedBackend;
            } else {
                backendToSelect = appConfig.backends[0].name;
            }

            appConfig.backends.forEach(backend => {
                const option = document.createElement('option');
                option.value = backend.name;
                option.textContent = backend.name;
                if (backend.name === backendToSelect) {
                    option.selected = true;
                }
                backendSelect.appendChild(option);
            });

            // Populate models for the selected backend
            await populateModelsForBackend(backendToSelect);
        } else {
            // Single backend -- hide selector, populate models normally
            backendGroup.style.display = 'none';
            await populateModelsForBackend(null);
        }

        // Set default temperature
        const temperatureSlider = document.getElementById('temperature');
        const temperatureValue = document.getElementById('temperature-value');
        temperatureSlider.value = appConfig.default_temperature;
        temperatureValue.textContent = appConfig.default_temperature;

        // Set version in footer
        if (appConfig.version) {
            document.getElementById('version').textContent = appConfig.version;
        }

        // Enable send button now that models are loaded
        document.getElementById('sendBtn').disabled = false;

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
