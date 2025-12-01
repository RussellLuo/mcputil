from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP(name="Salesforce", port=8001)


@mcp.tool()
def udpate_record(
    object_type: str = Field(
        description="Type of Salesforce object (Lead, Contact, Account, etc.)"
    ),
    record_id: str = Field(description="The ID of the record to update"),
    data: dict = Field(description="Fields to update with their new values"),
) -> str:
    """Updates a record in Salesforce"""
    return "Record updated successfully"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
