from typing import List, Dict

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "Search for specific code patterns, function names, or technical terms in the codebase",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g., 'Redis configuration', 'authentication function')"
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["markdown", "python", "javascript", "any"],
                        "description": "Type of files to search"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def execute_search_codebase(query: str, file_type: str = "any") -> List[Dict]:
    """
    Execute codebase search (stub for now - will integrate with retrieval on Day 3)
    
    Args:
        query: Search query
        file_type: File type filter
    
    Returns:
        List of search results
    """
    return [
        {
            "file_path": "docs/example.md",
            "text": "Example search result",
            "commit_date": "2024-12-20"
        }
    ]