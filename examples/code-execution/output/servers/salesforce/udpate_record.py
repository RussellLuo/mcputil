from typing import Any
from ..group import group


async def udpate_record(object_type: str, record_id: str, data: dict[str, Any]) -> str:
    """Updates a record in Salesforce

    Args:
        object_type: Type of Salesforce object (Lead, Contact, Account, etc.) (required)
        record_id: The ID of the record to update (required)
        data: Fields to update with their new values (required)
    """
    arguments = {
        "object_type": object_type,
        "record_id": record_id,
        "data": data
    }
    result = await group.call_tool("salesforce", "udpate_record", **arguments)
    return await result.output()