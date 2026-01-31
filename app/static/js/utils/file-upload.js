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
    
    // File input change handler
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
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
    
    // Convert to base64
    try {
        const base64 = await fileToBase64(file);
        
        // Compress/resize if needed
        const compressed = await compressImageIfNeeded(base64, file.type);
        
        attachedImage = {
            data: compressed,
            type: file.type,
            fileName: file.name
        };
        
        showImagePreview(compressed, file.type, file.name);
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
 * Compress image if it exceeds size threshold.
 */
async function compressImageIfNeeded(base64Data, mimeType) {
    // If image is small enough, return as-is
    const sizeInBytes = (base64Data.length * 3) / 4; // Approximate size
    const maxSize = 5 * 1024 * 1024; // 5MB threshold for compression
    
    if (sizeInBytes < maxSize) {
        console.log(`Image size OK: ${(sizeInBytes / 1024 / 1024).toFixed(2)}MB`);
        return base64Data;
    }
    
    console.log(`Compressing image: ${(sizeInBytes / 1024 / 1024).toFixed(2)}MB`);
    
    // Compress using canvas
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            
            // Calculate new dimensions (max 2048px on longest side)
            let width = img.width;
            let height = img.height;
            const maxDimension = 2048;
            
            if (width > maxDimension || height > maxDimension) {
                if (width > height) {
                    height = (height * maxDimension) / width;
                    width = maxDimension;
                } else {
                    width = (width * maxDimension) / height;
                    height = maxDimension;
                }
                console.log(`Resizing from ${img.width}x${img.height} to ${Math.round(width)}x${Math.round(height)}`);
            }
            
            canvas.width = width;
            canvas.height = height;
            
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);
            
            // Convert back to base64 with compression
            const compressedDataURL = canvas.toDataURL(mimeType, 0.85);
            const compressedBase64 = compressedDataURL.split(',')[1];
            
            const newSize = (compressedBase64.length * 3) / 4;
            console.log(`Compressed to: ${(newSize / 1024 / 1024).toFixed(2)}MB`);
            
            resolve(compressedBase64);
        };
        img.src = `data:${mimeType};base64,${base64Data}`;
    });
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
