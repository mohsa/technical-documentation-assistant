import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class GitHubConfig(BaseModel):
    """GitHub integration settings"""
    token: str = Field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    repos: List[str] = Field(default_factory=lambda: os.getenv("GITHUB_REPOS", "").split(",") if os.getenv("GITHUB_REPOS") else [])
    clone_dir: Path = Field(default=Path("./data/repos"))
    excluded_patterns: List[str] = Field(default=[
        "node_modules/", "vendor/", ".git/", "*.min.js", 
        "package-lock.json", "*.lock"
    ])
    max_file_size_mb: int = 1
    
class LLMConfig(BaseModel):
    """LLM settings"""
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 1500
    embedding_model: str = "text-embedding-3-small"
    
class ChunkingConfig(BaseModel):
    """Chunking parameters"""
    chunk_size: int = 512
    chunk_overlap: int = 50
    
class ObservabilityConfig(BaseModel):
    """Logging and metrics"""
    log_level: str = "INFO"
    log_file: Path = Field(default=Path("./logs/app.log"))
    enable_metrics: bool = True

class DatabaseConfig(BaseModel):
    """Database settings"""
    url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

class Settings(BaseModel):
    """Application settings"""
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    
    def validate_required(self):
        """Validate required settings are present"""
        errors = []
        if not self.github.token:
            errors.append("GITHUB_TOKEN not set")
        if not self.llm.api_key:
            errors.append("OPENAI_API_KEY not set")
        if not self.github.repos:
            errors.append("No repositories configured")
        if not self.database.url:
            errors.append("DATABASE_URL not set")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

settings = Settings()