import subprocess
from pathlib import Path
from typing import List
from datetime import datetime
import fnmatch

from config.settings import settings
from observability.logger import logger
from observability.metrics import SyncMetrics, metrics_collector

class GitHubSyncer:
    """Handles GitHub repository syncing"""
    
    def __init__(self):
        self.github_token = settings.github.token
        self.clone_dir = settings.github.clone_dir
        self.clone_dir.mkdir(parents=True, exist_ok=True)
    
    def sync_repo(self, repo: str) -> SyncMetrics:
        """
        Sync a GitHub repository
        
        Args:
            repo: Repository in format "owner/repo"
        
        Returns:
            SyncMetrics with sync results
        """
        start_time = datetime.utcnow()
        metrics = SyncMetrics(repo=repo, start_time=start_time, end_time=start_time)
        
        with logger.operation("github_sync", repo=repo):
            try:
                repo_path = self._get_repo_path(repo)
                
                if repo_path.exists():
                    self._pull_repo(repo_path, metrics)
                else:
                    self._clone_repo(repo, repo_path, metrics)
                
                files = self._get_files_to_process(repo_path)
                metrics.files_processed = len(files)
                
                logger.info(
                    "Sync completed",
                    repo=repo,
                    files_processed=metrics.files_processed
                )
                
            except Exception as e:
                metrics.errors.append(str(e))
                logger.error("Sync failed", repo=repo, error=str(e))
                raise
            finally:
                metrics.end_time = datetime.utcnow()
                metrics_collector.record_sync(metrics)
        
        return metrics
    
    def _get_repo_path(self, repo: str) -> Path:
        """Get local path for repo"""
        repo_name = repo.replace("/", "_")
        return self.clone_dir / repo_name
    
    def _clone_repo(self, repo: str, repo_path: Path, metrics: SyncMetrics):
        """Clone repository"""
        logger.info("Cloning repository", repo=repo)
        
        repo_url = f"https://{self.github_token}@github.com/{repo}.git"
        
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Repository cloned", repo=repo, path=str(repo_path))
        except subprocess.CalledProcessError as e:
            error_msg = f"Clone failed: {e.stderr}"
            metrics.errors.append(error_msg)
            raise RuntimeError(error_msg)
    
    def _pull_repo(self, repo_path: Path, metrics: SyncMetrics):
        """Pull latest changes"""
        logger.info("Pulling repository", path=str(repo_path))
        
        try:
            before_hash = self._get_commit_hash(repo_path)
            
            subprocess.run(
                ["git", "-C", str(repo_path), "pull"],
                check=True,
                capture_output=True,
                text=True
            )
            
            after_hash = self._get_commit_hash(repo_path)
            
            if before_hash != after_hash:
                logger.info(
                    "Repository updated",
                    path=str(repo_path),
                    before=before_hash[:7],
                    after=after_hash[:7]
                )
            else:
                logger.info("Repository already up to date", path=str(repo_path))
                
        except subprocess.CalledProcessError as e:
            error_msg = f"Pull failed: {e.stderr}"
            metrics.errors.append(error_msg)
            raise RuntimeError(error_msg)
    
    def _get_commit_hash(self, repo_path: Path) -> str:
        """Get current commit hash"""
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    
    def _get_files_to_process(self, repo_path: Path) -> List[Path]:
        """Get list of files to process based on config"""
        files = []
        
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            relative_path = file_path.relative_to(repo_path)
            if self._should_exclude(str(relative_path)):
                continue
            
            if file_path.stat().st_size > settings.github.max_file_size_mb * 1024 * 1024:
                logger.warning(
                    "File too large, skipping",
                    file=str(relative_path),
                    size_mb=round(file_path.stat().st_size / (1024 * 1024), 2)
                )
                continue
            
            if file_path.suffix in ['.md', '.py', '.js', '.java', '.go', '.ts']:
                files.append(file_path)
        
        return files
    
    def _should_exclude(self, path: str) -> bool:
        """Check if path matches exclusion patterns"""
        for pattern in settings.github.excluded_patterns:
            if fnmatch.fnmatch(path, pattern) or pattern in path:
                return True
        return False
    
    def get_file_metadata(self, repo_path: Path, file_path: Path) -> dict:
        """Get git metadata for a file"""
        try:
            result = subprocess.run(
                [
                    "git", "-C", str(repo_path),
                    "log", "-1", "--format=%H|%ad|%an|%ae",
                    "--date=iso-strict",
                    "--", str(file_path.relative_to(repo_path))
                ],
                check=True,
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                commit_hash, date, author_name, author_email = result.stdout.strip().split("|")
                return {
                    "commit_hash": commit_hash,
                    "commit_date": date,
                    "author": f"{author_name} <{author_email}>"
                }
        except Exception as e:
            logger.warning("Failed to get file metadata", file=str(file_path), error=str(e))
        
        return {
            "commit_hash": "unknown",
            "commit_date": datetime.utcnow().isoformat(),
            "author": "unknown"
        }