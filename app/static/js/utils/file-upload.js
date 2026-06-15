/**
 * File handling utilities for image and document upload.
 */

// Global state for attached files
let attachedImage = null; // { data: "base64...", type: "image/jpeg", fileName: "..." }
let attachedDocument = null; // { name, type, size, pages, markdown, uploadedAt }

/**
 * Initialize file upload handlers.
 */
function initializeFileHandlers() {
    const fileInput = document.getElementById('imageInput'); // Keep same ID for backward compatibility
    const inputContainer = document.querySelector('.input-container');
    const messagesArea = document.getElementById('messages');
    const messageInput = document.getElementById('messageInput');

    // File input change handler
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }

    // Paste handler for clipboard images (Ctrl+V / Cmd+V)
    if (messageInput) {
        messageInput.addEventListener('paste', handlePaste);
    }

    // Drag and drop handlers for input container
    if (inputContainer) {
        inputContainer.addEventListener('dragover', handleDragOver);
        inputContainer.addEventListener('dragleave', handleDragLeave);
        inputContainer.addEventListener('drop', handleDrop);
    }

    // Drag and drop handlers for messages area (conversation thread)
    if (messagesArea) {
        messagesArea.addEventListener('dragover', handleDragOver);
        messagesArea.addEventListener('dragleave', handleDragLeave);
        messagesArea.addEventListener('drop', handleDrop);
    }
}

/**
 * Handle paste event to detect clipboard images.
 * Supports Ctrl+V / Cmd+V with image data on clipboard.
 */
async function handlePaste(e) {
    const clipboardData = e.clipboardData || window.clipboardData;
    if (!clipboardData || !clipboardData.items) return;

    // Look for image items in clipboard
    for (const item of clipboardData.items) {
        if (item.type.startsWith('image/')) {
            e.preventDefault(); // Prevent pasting image as text
            const file = item.getAsFile();
            if (file) {
                await processImageFile(file);
            }
            return; // Only handle first image
        }
    }
}

// For backward compatibility
const initializeImageHandlers = initializeFileHandlers;

/**
 * Handle file input selection.
 */
async function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    await processFile(file);
}

/**
 * Process file - route to image or document handler.
 */
async function processFile(file) {
    const fileType = getFileType(file);
    
    if (fileType === 'image') {
        await processImageFile(file);
    } else if (fileType === 'document') {
        await processDocumentFile(file);
    } else {
        showError('Unsupported file type. Please upload an image or supported document format.');
    }
}

/**
 * Determine file type (image or document).
 */
function getFileType(file) {
    const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    const documentTypes = appConfig?.supported_document_types || [];
    
    if (imageTypes.includes(file.type)) {
        return 'image';
    } else if (documentTypes.includes(file.type)) {
        return 'document';
    }
    return 'unknown';
}

/**
 * Process and validate image file.
 */
async function processImageFile(file) {
    // Validate file type
    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!validTypes.includes(file.type)) {
        showError('Please select a valid image file (JPEG, PNG, GIF, or WebP)');
        return;
    }

    // Validate file size (max 10MB to avoid localStorage limits)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        showError('Image too large. Please select an image under 10MB.');
        return;
    }

    // Generate a display name (clipboard pastes often have generic names like "image.png")
    const fileName = (file.name && file.name !== 'image.png' && file.name !== 'blob')
        ? file.name
        : `Pasted image (${file.type.split('/')[1]})`;

    // Convert to base64
    try {
        const base64 = await fileToBase64(file);

        // Resize for vision (max 1024px on longest side)
        const compressed = await compressImageIfNeeded(base64, file.type);

        attachedImage = {
            data: compressed,
            type: file.type,
            fileName: fileName
        };

        showImagePreview(compressed, file.type, fileName);
    } catch (error) {
        console.error('Error processing image:', error);
        showError('Failed to process image. Please try again.');
    }
}

/**
 * Convert file to base64 string.
 */
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // Remove data URL prefix (e.g., "data:image/jpeg;base64,")
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

/**
 * Resize image for vision API (max 1024px on longest side).
 * Always resizes to keep payloads reasonable for LLM vision endpoints.
 */
async function resizeImageForVision(base64Data, mimeType) {
    const maxDimension = 1024;

    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
            let width = img.width;
            let height = img.height;

            // Only resize if larger than max dimension
            if (width <= maxDimension && height <= maxDimension) {
                const sizeInBytes = (base64Data.length * 3) / 4;
                console.log(`Image ${width}x${height} within limits (${(sizeInBytes / 1024).toFixed(0)}KB)`);
                resolve(base64Data);
                return;
            }

            // Scale down preserving aspect ratio
            if (width > height) {
                height = Math.round((height * maxDimension) / width);
                width = maxDimension;
            } else {
                width = Math.round((width * maxDimension) / height);
                height = maxDimension;
            }

            console.log(`Resizing from ${img.width}x${img.height} to ${width}x${height} for vision`);

            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;

            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            // Use JPEG for smaller size unless it's PNG with transparency
            const outputType = (mimeType === 'image/png') ? 'image/png' : 'image/jpeg';
            const quality = (outputType === 'image/jpeg') ? 0.85 : undefined;
            const compressedDataURL = canvas.toDataURL(outputType, quality);
            const compressedBase64 = compressedDataURL.split(',')[1];

            const newSize = (compressedBase64.length * 3) / 4;
            console.log(`Resized to ${width}x${height}: ${(newSize / 1024).toFixed(0)}KB`);

            resolve(compressedBase64);
        };
        img.src = `data:${mimeType};base64,${base64Data}`;
    });
}

/**
 * Compress image if it exceeds size threshold.
 * Also applies vision resize (max 1024px) to keep payloads manageable.
 */
async function compressImageIfNeeded(base64Data, mimeType) {
    // Always resize for vision (max 1024px on longest side)
    return resizeImageForVision(base64Data, mimeType);
}

/**
 * Show image preview in the UI.
 */
function showImagePreview(base64Data, mimeType, fileName) {
    const preview = document.getElementById('imagePreview');
    const img = document.getElementById('previewImg');
    const fileNameSpan = document.getElementById('imageFileName');
    
    if (!preview || !img) return;
    
    img.src = `data:${mimeType};base64,${base64Data}`;
    if (fileNameSpan) {
        fileNameSpan.textContent = fileName;
    }
    preview.style.display = 'flex';
}

/**
 * Drag over handler.
 */
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.add('drag-over');
}

/**
 * Drag leave handler.
 */
function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('drag-over');
}

/**
 * Drop handler.
 */
async function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('drag-over');
    
    const file = e.dataTransfer.files[0];
    if (file) {
        await processFile(file);
    }
}

/**
 * Process document file (upload to backend for parsing).
 */
async function processDocumentFile(file) {
    const maxSize = (appConfig?.max_document_size_mb || 10) * 1024 * 1024;
    
    if (file.size > maxSize) {
        showError(`Document too large. Maximum size: ${(maxSize / 1024 / 1024).toFixed(0)}MB`);
        return;
    }
    
    // Show upload indicator
    showInfo('📄 Uploading and parsing document...');
    
    try {
        // Upload to backend for parsing
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/documents/parse', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to parse document');
        }
        
        const parsed = await response.json();
        
        // Store parsed document
        attachedDocument = {
            name: parsed.filename,
            type: parsed.type,
            size: parsed.size,
            pages: parsed.pages,
            markdown: parsed.markdown,
            uploadedAt: new Date().toISOString()
        };
        
        // Show preview
        showDocumentPreview(attachedDocument);
        showInfo(`✅ Document parsed: ${parsed.pages} page(s), ${(parsed.size / 1024).toFixed(0)}KB`);
        
    } catch (error) {
        console.error('Document upload error:', error);
        showError('Failed to upload document: ' + error.message);
        attachedDocument = null;
    }
}

/**
 * Show document preview in the UI.
 */
function showDocumentPreview(docData) {
    // Remove any existing preview
    const existingPreview = document.getElementById('filePreviewContainer');
    if (existingPreview) {
        existingPreview.remove();
    }
    
    // Create preview container
    const container = document.createElement('div');
    container.id = 'filePreviewContainer';
    container.className = 'file-preview-container';
    container.innerHTML = `
        <div class="document-preview">
            <div class="document-icon">📄</div>
            <div class="document-info">
                <div class="document-name">${docData.name}</div>
                <div class="document-meta">${docData.pages} page(s) • ${(docData.size / 1024).toFixed(0)}KB</div>
            </div>
            <button class="remove-file" onclick="removeAttachedFile()" title="Remove document">×</button>
        </div>
    `;
    
    // Insert before input area
    const inputContainer = document.querySelector('.input-container');
    if (inputContainer) {
        inputContainer.parentElement.insertBefore(container, inputContainer);
    }
}

/**
 * Remove attached file (image or document).
 */
function removeAttachedFile() {
    attachedImage = null;
    attachedDocument = null;
    
    // Remove image preview
    const imagePreview = document.getElementById('imagePreview');
    if (imagePreview) {
        imagePreview.style.display = 'none';
    }
    
    // Remove document preview
    const filePreview = document.getElementById('filePreviewContainer');
    if (filePreview) {
        filePreview.remove();
    }
    
    // Clear file input
    const fileInput = document.getElementById('imageInput');
    if (fileInput) {
        fileInput.value = '';
    }
}

/**
 * Check if any file is attached.
 */
function hasAttachedFile() {
    return attachedImage !== null || attachedDocument !== null;
}

/**
 * Get attached file data.
 */
function getAttachedFile() {
    if (attachedImage) {
        return {
            type: 'image',
            data: attachedImage
        };
    } else if (attachedDocument) {
        return {
            type: 'document',
            data: attachedDocument
        };
    }
    return null;
}

// Backward compatibility functions
const removeAttachedImage = removeAttachedFile;
const hasAttachedImage = hasAttachedFile;

/**
 * Get attached image (backward compatibility).
 */
function getAttachedImage() {
    return attachedImage;
}
