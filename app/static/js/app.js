// Main app initialization and event listeners

async function setupEventListeners() {
    const messageInput = document.getElementById('messageInput');
    const temperatureSlider = document.getElementById('temperature');
    const temperatureValue = document.getElementById('temperature-value');

    // Auto-resize textarea
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });

    // Send on Enter (Shift+Enter for new line)
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Update temperature display
    temperatureSlider.addEventListener('input', function() {
        temperatureValue.textContent = this.value;
    });

    // Markdown toggle listener
    const markdownToggle = document.getElementById('markdownToggle');
    markdownToggle.checked = await getMarkdownEnabled();
    markdownToggle.addEventListener('change', async function() {
        await setMarkdownEnabled(this.checked);
        // Reload current conversation to re-render messages
        if (currentConversationId) {
            await loadConversation(currentConversationId);
        }
    });

    // Model selection listener
    const modelSelect = document.getElementById('model');
    modelSelect.addEventListener('change', async function() {
        await saveModelPreference(this.value);
    });

    // RLM toggle listener - with passcode protection
    const rlmToggle = document.getElementById('rlmToggle');
    const rlmThinkingToggle = document.getElementById('rlmThinkingToggle');
    const rlmThinkingGroup = document.getElementById('rlmThinkingGroup');
    
    // Load saved preferences (but don't auto-enable RLM)
    const savedRlmEnabled = await getRlmEnabled();
    rlmThinkingToggle.checked = await getRlmThinkingEnabled();
    
    // If RLM was previously enabled and we have valid access, restore it
    if (savedRlmEnabled && rlmSecurity.rlmAvailable) {
        // Check access asynchronously without blocking page load
        rlmSecurity.checkRLMAccess().then(hasAccess => {
            if (hasAccess) {
                rlmToggle.checked = true;
            }
        });
    }
    
    function updateRlmThinkingVisibility() {
        rlmThinkingGroup.style.display = rlmToggle.checked ? 'flex' : 'none';
    }
    
    rlmToggle.addEventListener('change', async function() {
        if (this.checked) {
            // User wants to enable RLM - check access
            const hasAccess = await rlmSecurity.checkRLMAccess();
            
            if (!hasAccess) {
                // Prompt for passcode
                const granted = await rlmSecurity.promptForPasscode();
                
                if (!granted) {
                    // User cancelled or invalid passcode - uncheck toggle
                    this.checked = false;
                    await setRlmEnabled(false);
                    updateRlmThinkingVisibility();
                    return;
                }
            }
            
            // Access granted - enable RLM
            await setRlmEnabled(true);
            updateRlmThinkingVisibility();
        } else {
            // User is disabling RLM
            await setRlmEnabled(false);
            updateRlmThinkingVisibility();
        }
    });
    
    rlmThinkingToggle.addEventListener('change', async function() {
        await setRlmThinkingEnabled(this.checked);
    });
    
    updateRlmThinkingVisibility(); // Set initial state
}

// Update storage meter display
async function updateStorageMeter() {
    const stats = await storageAdapter.getStorageStats();
    const meterFill = document.getElementById('storageMeterFill');
    const meterText = document.getElementById('storageMeterText');
    
    if (meterFill && meterText) {
        const percentage = stats.percentUsed;
        meterFill.style.width = `${percentage}%`;
        
        // Color based on usage
        if (percentage > 90) {
            meterFill.style.backgroundColor = '#ef4444'; // Red
        } else if (percentage > 70) {
            meterFill.style.backgroundColor = '#f59e0b'; // Orange
        } else {
            meterFill.style.backgroundColor = '#10b981'; // Green
        }
        
        meterText.textContent = `${stats.usedMB.toFixed(1)} MB / ${stats.totalMB.toFixed(0)} MB (${percentage.toFixed(1)}%)`;
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', async function() {
    // STEP 1: Run migration from localStorage to IndexedDB
    await storageAdapter.migrateFromLocalStorage();
    
    // STEP 2: Initialize session ID (now async)
    await initSessionId();
    
    // Configure markdown library
    configureMarked();
    
    // Initialize image handlers
    initializeImageHandlers();
    
    // Initialize RLM security
    await rlmSecurity.initialize();
    
    // Track session for analytics
    try {
        const sessionResponse = await fetch('/api/session' + (sessionId ? `?session_id=${sessionId}` : ''));
        const sessionData = await sessionResponse.json();
        sessionId = sessionData.session_id;
        await storageAdapter.setItem(SESSION_ID_KEY, sessionId);
    } catch (err) {
        console.log('Session tracking failed:', err);
    }
    
    // Initialize storage meter
    updateStorageMeter();
    
    await loadConfiguration();
    await setupEventListeners();
});
