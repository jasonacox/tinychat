// RLM Security Management

class RLMSecurity {
    constructor() {
        this.cookieName = 'tinychat_rlm_passcode';
        this.rlmAvailable = false;
        this.requiresPasscode = false;
    }
    
    async initialize() {
        // Check RLM status from server
        try {
            const response = await fetch('/api/rlm/status');
            const status = await response.json();
            this.rlmAvailable = status.available;
            this.requiresPasscode = status.requires_passcode;
            
            // Hide RLM toggle if not available
            if (!this.rlmAvailable) {
                const rlmToggleGroup = document.getElementById('rlmToggle').closest('.setting-group');
                if (rlmToggleGroup) {
                    rlmToggleGroup.style.display = 'none';
                }
            }
            
            return true;
        } catch (error) {
            console.error('Error checking RLM status:', error);
            return false;
        }
    }
    
    async checkRLMAccess() {
        // If no passcode required, allow access
        if (!this.requiresPasscode) {
            return true;
        }
        
        // Check if we have a stored passcode
        const storedPasscode = this.getCookie(this.cookieName);
        
        if (storedPasscode) {
            // Validate with server
            const valid = await this.validatePasscode(storedPasscode);
            return valid;
        }
        
        return false;
    }
    
    async promptForPasscode() {
        return new Promise((resolve) => {
            // Create modal
            const modal = document.createElement('div');
            modal.className = 'rlm-passcode-modal';
            modal.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <h3>Authentication Required</h3>
                    <p>Please enter your passcode:</p>
                    <input type="password" id="rlmPasscodeInput" placeholder="Enter passcode" autocomplete="off">
                    <div class="modal-buttons">
                        <button id="rlmPasscodeSubmit">Submit</button>
                        <button id="rlmPasscodeCancel">Cancel</button>
                    </div>
                    <p class="modal-error" id="rlmPasscodeError"></p>
                </div>
            `;
            document.body.appendChild(modal);
            
            const input = document.getElementById('rlmPasscodeInput');
            const submitBtn = document.getElementById('rlmPasscodeSubmit');
            const cancelBtn = document.getElementById('rlmPasscodeCancel');
            const errorDiv = document.getElementById('rlmPasscodeError');
            
            input.focus();
            
            const cleanup = () => {
                document.body.removeChild(modal);
            };
            
            submitBtn.onclick = async () => {
                const passcode = input.value.trim();
                if (!passcode) {
                    errorDiv.textContent = 'Please enter a passcode';
                    return;
                }
                
                submitBtn.disabled = true;
                submitBtn.textContent = 'Validating...';
                
                const valid = await this.validatePasscode(passcode);
                
                if (valid) {
                    // Store in cookie (365 days expiration)
                    this.setCookie(this.cookieName, passcode, 365);
                    cleanup();
                    resolve(true);
                } else {
                    errorDiv.textContent = 'Invalid passcode. Please try again.';
                    input.value = '';
                    input.focus();
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit';
                }
            };
            
            cancelBtn.onclick = () => {
                cleanup();
                resolve(false);
            };
            
            // Allow Enter key to submit
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    submitBtn.click();
                }
            });
            
            // Allow Escape key to cancel
            modal.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    cancelBtn.click();
                }
            });
        });
    }
    
    async validatePasscode(passcode) {
        try {
            const response = await fetch('/api/rlm/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ passcode })
            });
            
            const result = await response.json();
            
            if (result.error) {
                console.error('RLM validation error:', result.error);
                return false;
            }
            
            return result.valid === true;
        } catch (error) {
            console.error('Error validating RLM passcode:', error);
            return false;
        }
    }
    
    setCookie(name, value, days) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/;SameSite=Strict`;
    }
    
    getCookie(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }
    
    clearAccess() {
        this.setCookie(this.cookieName, '', -1);
    }
}

// Initialize RLM security manager
const rlmSecurity = new RLMSecurity();
