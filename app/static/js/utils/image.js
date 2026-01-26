/**
 * Image handling utilities for file upload, compression, and base64 conversion.
 */

// Global state for attached image
let attachedImage = null; // { data: "base64...", type: "image/jpeg", fileName: "..." }

/**
 * Initialize image upload handlers.
 */
function initializeImageHandlers() {
    const imageInput = document.getElementById('imageInput');
    const inputContainer = document.querySelector('.input-container');
    const messagesArea = document.getElementById('messages');
    
    // File input change handler
    if (imageInput) {
        imageInput.addEventListener('change', handleImageSelect);
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
 * Handle file input selection.
 */
async function handleImageSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    await processImageFile(file);
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
 * Remove attached image.
 */
function removeAttachedImage() {
    attachedImage = null;
    const preview = document.getElementById('imagePreview');
    const imageInput = document.getElementById('imageInput');
    
    if (preview) {
        preview.style.display = 'none';
    }
    if (imageInput) {
        imageInput.value = '';
    }
}

/**
 * Get current attached image.
 */
function getAttachedImage() {
    return attachedImage;
}

/**
 * Check if image is attached.
 */
function hasAttachedImage() {
    return attachedImage !== null;
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
    if (file && file.type.startsWith('image/')) {
        await processImageFile(file);
    }
}
