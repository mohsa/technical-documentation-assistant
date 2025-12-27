import re
#from typing import Dict, List, Tuple
from typing import Dict, List, Tuple, Optional

from datetime import datetime, timedelta

from observability.logger import logger

class ResponseValidator:
    """Validates LLM responses for quality and correctness"""
    
    def __init__(self):
        self.max_staleness_days = 180  # Flag docs older than 6 months
    
    def validate(
        self,
        response: str,
        retrieved_chunks: List[Dict]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate LLM response
        
        Args:
            response: LLM generated response
            retrieved_chunks: Context chunks used
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check 1: Response must have citations
        citations = self._extract_citations(response)
        if not citations:
            errors.append("Response has no citations")
        
        # Check 2: All citations must exist in retrieved context
        valid_paths = {chunk['file_path'] for chunk in retrieved_chunks}
        
        for citation in citations:
            if citation not in valid_paths:
                errors.append(f"Hallucinated citation: {citation}")
        
        # Check 3: Check for stale information
        for citation in citations:
            chunk = next((c for c in retrieved_chunks if c['file_path'] == citation), None)
            if chunk and chunk.get('commit_date'):
                try:
                    commit_date = datetime.fromisoformat(chunk['commit_date'].replace('Z', '+00:00'))
                    age_days = (datetime.now(commit_date.tzinfo) - commit_date).days
                    
                    if age_days > self.max_staleness_days:
                        warnings.append(
                            f"{citation} is {age_days} days old (last updated: {commit_date.date()})"
                        )
                except Exception as e:
                    logger.warning("Failed to parse commit date", error=str(e))
        
        # Check 4: Response should not be too short (likely error)
        if len(response.strip()) < 20:
            warnings.append("Response is very short, may be incomplete")
        
        # Check 5: Check for common error patterns
        error_patterns = [
            "I don't have",
            "I cannot find",
            "not available",
            "I apologize"
        ]
        
        for pattern in error_patterns:
            if pattern.lower() in response.lower():
                warnings.append(f"Response contains error pattern: '{pattern}'")
        
        is_valid = len(errors) == 0
        
        if errors:
            logger.warning("Response validation failed", errors=errors)
        
        if warnings:
            logger.info("Response validation warnings", warnings=warnings)
        
        return is_valid, errors, warnings
    
    def _extract_citations(self, response: str) -> List[str]:
        """
        Extract file path citations from response
        
        Looks for patterns like:
        - [path/to/file.md]
        - (path/to/file.py)
        - "path/to/file.js"
        """
        patterns = [
            r'\[([\w\-./]+\.\w+)\]',  # [file.md]
            r'\(([\w\-./]+\.\w+)\)',  # (file.py)
            r'"([\w\-./]+\.\w+)"',    # "file.js"
            r'`([\w\-./]+\.\w+)`',    # `file.ts`
        ]
        
        citations = set()
        for pattern in patterns:
            matches = re.findall(pattern, response)
            citations.update(matches)
        
        return list(citations)
    
    def add_warnings_to_response(
        self,
        response: str,
        warnings: List[str]
    ) -> str:
        """
        Append warnings to response
        
        Args:
            response: Original response
            warnings: List of warnings
        
        Returns:
            Response with warnings appended
        """
        if not warnings:
            return response
        
        warning_text = "\n\n⚠️ **Notes:**\n"
        for warning in warnings:
            warning_text += f"- {warning}\n"
        
        return response + warning_text


class InputValidator:
    """Validates user input for safety and quality"""
    
    def __init__(self):
        self.max_query_length = 500
        self.min_query_length = 3
    
    def validate_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate user query
        
        Args:
            query: User input query
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(query) < self.min_query_length:
            return False, f"Query too short (minimum {self.min_query_length} characters)"
        
        if len(query) > self.max_query_length:
            return False, f"Query too long (maximum {self.max_query_length} characters)"
        
        # Check for SQL injection patterns (basic)
        sql_patterns = [
            r";\s*DROP\s+TABLE",
            r";\s*DELETE\s+FROM",
            r"UNION\s+SELECT",
            r"--\s*$"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning("Potential SQL injection detected", query=query[:50])
                return False, "Invalid query format"
        
        # Check for script injection
        if "<script" in query.lower() or "javascript:" in query.lower():
            logger.warning("Potential script injection detected", query=query[:50])
            return False, "Invalid query format"
        
        return True, None