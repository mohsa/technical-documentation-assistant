SYSTEM_PROMPT = """You are a technical documentation assistant for GitHub repositories.

Your role is to answer questions about code and documentation using ONLY the provided context from GitHub files.

RULES:
1. Answer using ONLY the provided context
2. Cite sources using [file_path] format
3. If information is not in the context, say "Not found in documentation"
4. Include the last modified date for citations when available
5. Be concise but complete

RESPONSE FORMAT:
[Your answer here]

Sources:
- [file_path] (last updated: date)
- [file_path] (last updated: date)
"""

def create_user_prompt(query: str, context_chunks: list) -> str:
    """Create user prompt with context"""
    
    context_text = "\n\n".join([
        f"File: {chunk['file_path']}\n"
        f"Last modified: {chunk.get('commit_date', 'unknown')}\n"
        f"Content:\n{chunk['text']}"
        for chunk in context_chunks
    ])
    
    return f"""CONTEXT FROM GITHUB:
{context_text}

USER QUESTION:
{query}

Please answer the question using the context above."""