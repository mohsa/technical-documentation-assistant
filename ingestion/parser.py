from pathlib import Path
from typing import Optional

from observability.logger import logger

class ContentParser:
    """Extracts content from different file types"""
    
    def parse_file(self, file_path: Path) -> Optional[str]:
        """
        Parse file and extract content
        
        Args:
            file_path: Path to file
        
        Returns:
            Extracted text content or None if parsing fails
        """
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == '.md':
                return self._parse_markdown(file_path)
            elif suffix in ['.py', '.js', '.java', '.go', '.ts']:
                return self._parse_code(file_path)
            else:
                logger.warning("Unsupported file type", file=str(file_path), suffix=suffix)
                return None
                
        except Exception as e:
            logger.error("Failed to parse file", file=str(file_path), error=str(e))
            return None
    
    def _parse_markdown(self, file_path: Path) -> str:
        """Parse markdown file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return content
    
    def _parse_code(self, file_path: Path) -> str:
        """Parse code file - extract docstrings and comments"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        extracted_content = []
        in_docstring = False
        docstring_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            if '"""' in stripped or "'''" in stripped:
                if not in_docstring:
                    in_docstring = True
                    docstring_lines = [stripped]
                else:
                    docstring_lines.append(stripped)
                    extracted_content.append("\n".join(docstring_lines))
                    in_docstring = False
                    docstring_lines = []
            elif in_docstring:
                docstring_lines.append(stripped)
            elif stripped.startswith('#') or stripped.startswith('//'):
                extracted_content.append(stripped)
        
        result = "\n".join(extracted_content)
        if not result.strip():
            result = "".join(lines[:50])
        
        return result