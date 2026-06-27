// System Prompt Presets - CRUD operations and UI management

// Built-in presets (cannot be deleted or permanently modified)
const BUILT_IN_PRESETS = [
    {
        id: 'default',
        name: 'Default',
        content: 'You are a helpful assistant.',
        builtIn: true
    },
    {
        id: 'concise',
        name: 'Concise',
        content: 'You are a helpful assistant. Be concise and direct in your responses. Avoid unnecessary filler words or lengthy explanations unless asked for more detail.',
        builtIn: true
    },
    {
        id: 'creative',
        name: 'Creative',
        content: 'You are a creative and imaginative assistant. Think outside the box, offer unique perspectives, and use vivid language. Be expressive and engaging in your responses.',
        builtIn: true
    }
];

// System prompts manager
const systemPrompts = {
    presets: [],
    selectedId: null,

    /**
     * Initialize presets from storage, merging with built-ins
     */
    async initialize() {
        const stored = await storageAdapter.getItem(SYSTEM_PROMPTS_KEY);

        if (stored && Array.isArray(stored)) {
            // Merge: keep built-ins as base, layer user customizations on top
            const userPresets = stored.filter(p => !p.builtIn);
            this.presets = [...BUILT_IN_PRESETS, ...userPresets];
        } else {
            this.presets = [...BUILT_IN_PRESETS];
        }

        // Load selected preset, normalized to a valid id
        this.selectedId = await storageAdapter.getItem(SELECTED_PROMPT_KEY);
        if (!this.selectedId || (this.selectedId !== 'none' && !this.getById(this.selectedId))) {
            this.selectedId = 'none';
        }

        this.populateDropdown();
        return this.presets;
    },

    /**
     * Get all presets
     */
    getAll() {
        return this.presets;
    },

    /**
     * Get a preset by ID
     */
    getById(id) {
        return this.presets.find(p => p.id === id) || null;
    },

    /**
     * Get the currently selected preset, or null if 'none' is selected.
     */
    getSelected() {
        if (this.selectedId === 'none') return null;
        return this.getById(this.selectedId) || null;
    },

    /**
     * Get the system prompt content for the selected preset.
     * Returns empty string when 'none' is selected (no system prompt).
     */
    getSelectedContent() {
        const preset = this.getSelected();
        return preset ? preset.content : '';
    },

    /**
     * Select a preset by ID
     */
    async select(id) {
        this.selectedId = id;
        await storageAdapter.setItem(SELECTED_PROMPT_KEY, id);
    },

    /**
     * Add a new custom preset
     */
    async add(name, content) {
        const preset = {
            id: generateUUID(),
            name: name.trim(),
            content: content.trim(),
            builtIn: false
        };
        this.presets.push(preset);
        await this.save();
        this.populateDropdown();
        return preset;
    },

    /**
     * Update an existing preset
     */
    async update(id, name, content) {
        const preset = this.getById(id);
        if (!preset) return null;

        preset.name = name.trim();
        preset.content = content.trim();
        await this.save();
        this.populateDropdown();
        return preset;
    },

    /**
     * Delete a custom preset (built-ins cannot be deleted)
     */
    async delete(id) {
        const preset = this.getById(id);
        if (!preset || preset.builtIn) return false;

        this.presets = this.presets.filter(p => p.id !== id);

        // If deleted preset was selected, revert to none
        if (this.selectedId === id) {
            this.selectedId = 'none';
            await storageAdapter.setItem(SELECTED_PROMPT_KEY, 'none');
        }

        await this.save();
        this.populateDropdown();
        return true;
    },

    /**
     * Persist user presets to storage
     */
    async save() {
        // Only save user-created presets (built-ins are always loaded from code)
        const userPresets = this.presets.filter(p => !p.builtIn);
        await storageAdapter.setItem(SYSTEM_PROMPTS_KEY, userPresets);
    },

    /**
     * Populate the dropdown in the UI
     */
    populateDropdown() {
        const select = document.getElementById('systemPromptSelect');
        if (!select) return;

        select.innerHTML = '';

        // Add "None" option
        const noneOption = document.createElement('option');
        noneOption.value = 'none';
        noneOption.textContent = '(None)';
        if (this.selectedId === 'none') noneOption.selected = true;
        select.appendChild(noneOption);

        // Add built-in group
        const builtInGroup = document.createElement('optgroup');
        builtInGroup.label = 'Built-in';
        this.presets.filter(p => p.builtIn).forEach(preset => {
            const option = document.createElement('option');
            option.value = preset.id;
            option.textContent = preset.name;
            if (preset.id === this.selectedId) option.selected = true;
            builtInGroup.appendChild(option);
        });
        select.appendChild(builtInGroup);

        // Add custom group if any exist
        const customPresets = this.presets.filter(p => !p.builtIn);
        if (customPresets.length > 0) {
            const customGroup = document.createElement('optgroup');
            customGroup.label = 'Custom';
            customPresets.forEach(preset => {
                const option = document.createElement('option');
                option.value = preset.id;
                option.textContent = preset.name;
                if (preset.id === this.selectedId) option.selected = true;
                customGroup.appendChild(option);
            });
            select.appendChild(customGroup);
        }
    },

    /**
     * Show the edit modal for managing presets
     */
    showEditModal() {
        // Remove existing modal if any
        const existing = document.getElementById('systemPromptModal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'systemPromptModal';
        modal.className = 'system-prompt-modal';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Manage System Prompts</h3>
                    <button class="modal-close" title="Close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="preset-list" id="presetList"></div>
                    <div class="preset-editor" id="presetEditor" style="display: none;">
                        <div class="editor-field">
                            <label for="presetName">Name:</label>
                            <input type="text" id="presetName" placeholder="Preset name" maxlength="50">
                        </div>
                        <div class="editor-field">
                            <label for="presetContent">System Prompt:</label>
                            <textarea id="presetContent" placeholder="Enter the system prompt content..." rows="6"></textarea>
                        </div>
                        <div class="editor-actions">
                            <button class="btn-save" id="presetSaveBtn">Save</button>
                            <button class="btn-cancel" id="presetCancelBtn">Cancel</button>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-add" id="addPresetBtn">+ New Preset</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Bind events
        modal.querySelector('.modal-overlay').onclick = () => this.closeEditModal();
        modal.querySelector('.modal-close').onclick = () => this.closeEditModal();
        modal.querySelector('#addPresetBtn').onclick = () => this.showEditor(null);

        // ESC to close — store handler so closeEditModal() can clean it up
        this._escapeHandler = (e) => {
            if (e.key === 'Escape') {
                this.closeEditModal();
            }
        };
        document.addEventListener('keydown', this._escapeHandler);

        this.renderPresetList();
    },

    /**
     * Render the list of presets in the modal
     */
    renderPresetList() {
        const list = document.getElementById('presetList');
        if (!list) return;

        list.innerHTML = '';
        this.presets.forEach(preset => {
            const item = document.createElement('div');
            item.className = 'preset-item';

            const info = document.createElement('div');
            info.className = 'preset-item-info';

            const name = document.createElement('span');
            name.className = 'preset-item-name';
            name.textContent = preset.name;
            if (preset.builtIn) {
                const badge = document.createElement('span');
                badge.className = 'preset-badge';
                badge.textContent = 'built-in';
                name.appendChild(badge);
            }

            const preview = document.createElement('span');
            preview.className = 'preset-item-preview';
            preview.textContent = preset.content.substring(0, 80) + (preset.content.length > 80 ? '...' : '');

            info.appendChild(name);
            info.appendChild(preview);

            const actions = document.createElement('div');
            actions.className = 'preset-item-actions';

            const editBtn = document.createElement('button');
            editBtn.className = 'btn-edit';
            editBtn.textContent = 'Edit';
            editBtn.onclick = () => this.showEditor(preset.id);
            actions.appendChild(editBtn);

            if (!preset.builtIn) {
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn-delete';
                deleteBtn.textContent = 'Delete';
                deleteBtn.onclick = () => this.confirmDelete(preset.id, preset.name);
                actions.appendChild(deleteBtn);
            }

            item.appendChild(info);
            item.appendChild(actions);
            list.appendChild(item);
        });
    },

    /**
     * Show the editor panel for creating/editing a preset
     */
    showEditor(presetId) {
        const editor = document.getElementById('presetEditor');
        const list = document.getElementById('presetList');
        const addBtn = document.getElementById('addPresetBtn');
        const nameInput = document.getElementById('presetName');
        const contentInput = document.getElementById('presetContent');

        if (!editor) return;

        editor.style.display = 'block';
        list.style.display = 'none';
        addBtn.style.display = 'none';

        if (presetId) {
            const preset = this.getById(presetId);
            if (preset) {
                nameInput.value = preset.name;
                contentInput.value = preset.content;
            }
        } else {
            nameInput.value = '';
            contentInput.value = '';
        }

        // Focus name input
        nameInput.focus();

        // Save handler
        const saveBtn = document.getElementById('presetSaveBtn');
        saveBtn.onclick = async () => {
            const name = nameInput.value.trim();
            const content = contentInput.value.trim();

            if (!name) {
                nameInput.focus();
                return;
            }
            if (!content) {
                contentInput.focus();
                return;
            }

            if (presetId) {
                await this.update(presetId, name, content);
            } else {
                await this.add(name, content);
            }

            this.hideEditor();
        };

        // Cancel handler
        const cancelBtn = document.getElementById('presetCancelBtn');
        cancelBtn.onclick = () => this.hideEditor();
    },

    /**
     * Hide the editor and show the list again
     */
    hideEditor() {
        const editor = document.getElementById('presetEditor');
        const list = document.getElementById('presetList');
        const addBtn = document.getElementById('addPresetBtn');

        if (editor) editor.style.display = 'none';
        if (list) list.style.display = 'block';
        if (addBtn) addBtn.style.display = 'inline-block';

        this.renderPresetList();
    },

    /**
     * Confirm and delete a preset
     */
    async confirmDelete(id, name) {
        if (confirm(`Delete preset "${name}"? This cannot be undone.`)) {
            await this.delete(id);
            this.renderPresetList();
        }
    },

    /**
     * Close the edit modal and clean up listeners
     */
    closeEditModal() {
        const modal = document.getElementById('systemPromptModal');
        if (modal) modal.remove();
        if (this._escapeHandler) {
            document.removeEventListener('keydown', this._escapeHandler);
            this._escapeHandler = null;
        }
    }
};
