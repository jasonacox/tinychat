// Main app initialization and event listeners

function setupEventListeners() {
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
    markdownToggle.checked = getMarkdownEnabled();
    markdownToggle.addEventListener('change', function() {
        setMarkdownEnabled(this.checked);
        // Reload current conversation to re-render messages
        if (currentConversationId) {
            loadConversation(currentConversationId);
        }
    });

    // Model selection listener
    const modelSelect = document.getElementById('model');
    modelSelect.addEventListener('change', function() {
        saveModelPreference(this.value);
    });

    // RLM toggle listener - with passcode protection
    const rlmToggle = document.getElementById('rlmToggle');
    const rlmThinkingToggle = document.getElementById('rlmThinkingToggle');
    const rlmThinkingGroup = document.getElementById('rlmThinkingGroup');
    
    // Load saved preferences (but don't auto-enable RLM)
    const savedRlmEnabled = getRlmEnabled();
    rlmThinkingToggle.checked = getRlmThinkingEnabled();
    
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
                    setRlmEnabled(false);
                    updateRlmThinkingVisibility();
                    return;
                }
            }
            
            // Access granted - enable RLM
            setRlmEnabled(true);
            updateRlmThinkingVisibility();
        } else {
            // User is disabling RLM
            setRlmEnabled(false);
            updateRlmThinkingVisibility();
        }
    });
    
    rlmThinkingToggle.addEventListener('change', function() {
        setRlmThinkingEnabled(this.checked);
    });
    
    updateRlmThinkingVisibility(); // Set initial state
}

// Initialize app
document.addEventListener('DOMContentLoaded', async function() {
    // Configure markdown library
    configureMarked();
    
    // Initialize RLM security
    await rlmSecurity.initialize();
    
    // Track session for analytics
    try {
        const sessionResponse = await fetch('/api/session' + (sessionId ? `?session_id=${sessionId}` : ''));
        const sessionData = await sessionResponse.json();
        sessionId = sessionData.session_id;
        localStorage.setItem(SESSION_ID_KEY, sessionId);
    } catch (err) {
        console.log('Session tracking failed:', err);
    }
    
    loadConfiguration();
    setupEventListeners();
});
