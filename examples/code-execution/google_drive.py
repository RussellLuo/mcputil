from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP(name="Google Drive", port=8000)


@mcp.tool()
def get_document(
    document_id: str = Field(description="The ID of the Google Drive document"),
    fields: str = Field(description="Specific fields to return", default="*"),
) -> str:
    """Retrieves a document from Google Drive"""
    return "The document content"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
