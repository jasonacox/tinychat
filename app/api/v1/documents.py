"""Document upload and parsing endpoints."""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.services.document_parser import DocumentParser
from app.config import Settings

logger = logging.getLogger("tinychat")
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/parse")
async def parse_document(file: UploadFile = File(...)):
    """
    Parse uploaded document to markdown.
    
    Accepts various document formats, parses to markdown, and returns
    the structured content to the client for storage in IndexedDB.
    
    The backend does NOT store the file - it's processed in memory and discarded.
    
    Args:
        file: Uploaded file
        
    Returns:
        {
            "markdown": str,     # Parsed content
            "filename": str,     # Original filename
            "size": int,         # File size in bytes
            "type": str,         # Content type
            "pages": int         # Number of pages (if applicable)
        }
    """
    try:
        # Read file content
        content = await file.read()
        
        # Validate size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > Settings.MAX_DOCUMENT_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {size_mb:.1f}MB exceeds limit of {Settings.MAX_DOCUMENT_SIZE_MB}MB"
            )
        
        # Validate content type
        content_type = file.content_type
        if content_type not in Settings.SUPPORTED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {content_type}. Supported types: {', '.join(Settings.SUPPORTED_DOCUMENT_TYPES)}"
            )
        
        # Parse document
        result = await DocumentParser.parse_document(
            file_content=content,
            filename=file.filename,
            content_type=content_type
        )
        
        logger.info(f"Successfully parsed document: {file.filename} ({size_mb:.2f}MB)")
        return JSONResponse(content=result)
        
    except ValueError as e:
        logger.error(f"Document parsing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error parsing document: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse document")
