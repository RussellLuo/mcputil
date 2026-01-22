from typing import Any
from ..group import group


async def get_document(document_id: str, fields: str = '*') -> str:
    """Retrieves a document from Google Drive

    Args:
        document_id: The ID of the Google Drive document (required)
        fields: Specific fields to return (optional)
    """
    arguments = {
        "document_id": document_id,
        "fields": fields
    }
    result = await group.call_tool("google_drive", "get_document", **arguments)
    return await result.output()