import logging
import shutil
from pathlib import Path
from typing import List, Dict, Literal, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class OrganizerError(Exception):
    """Custom exception for organizer errors."""
    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status

@dataclass
class Settings:
    """Settings configuration for the LLM client."""
    api_key: str = ""
    api_base_url: str = "https://frogapi.app/v1"
    model_name: str = "gpt-5-nano"
    source_dir: str = ""
    output_dir: str = ""
    testing_mode: bool = True
    testing_limit: int = 3
    keyframes_per_video: int = 8
    max_image_size_px: int = 512
    use_local_whisper: bool = True
    whisper_model: str = "base"
    dry_run: bool = True
    naming_template: str = "{category}/{descriptive_name}{ext}"

class Organizer:
    def __init__(self, settings: Settings):
        """
        Initialize Organizer with settings.
        
        Args:
            settings: Settings instance containing output_dir and other configuration
        """
        self.settings = settings
        self.output_dir = Path(settings.output_dir) if settings.output_dir else None
        self._created_dirs: set = set()  # Track directories we've created
        
    def build_plan(self, results: List[Dict]) -> List[Dict]:
        """
        Build execution plan from LLM results.
        
        Args:
            results: List of dicts with keys: source, category, subcategory, descriptive_name, tags, confidence, reasoning
            
        Returns:
            List of dicts with source, destination, action, and status
        """
        if not self.output_dir:
            raise OrganizerError("Output directory not set", status="config_error")
        
        plan = []
        used_paths: set = set()  # Track paths to avoid collisions within the plan itself
        
        for result in results:
            source = Path(result["source"])
            category = result.get("category", "misc")
            descriptive_name = result.get("descriptive_name", source.stem)
            ext = source.suffix.lower()
            
            # Build destination path
            dest_dir = self.output_dir / category
            if result.get("subcategory"):
                dest_dir = dest_dir / result["subcategory"]
            
            # Generate unique filename with collision resolution
            destination = self._generate_unique_path(
                dest_dir, descriptive_name, ext, used_paths
            )
            
            used_paths.add(str(destination))
            
            plan.append({
                "source": str(source),
                "destination": str(destination),
                "action": "move",
                "status": "pending"
            })
            
        return plan
    
    def _generate_unique_path(
        self, 
        dest_dir: Path, 
        base_name: str, 
        ext: str, 
        used_paths: set,
        max_attempts: int = 1000
    ) -> Path:
        """
        Generate a unique destination path, handling both existing files and planned destinations.
        Auto-suffixes with _2, _3, etc. on collision.
        
        Args:
            dest_dir: Destination directory
            base_name: Base filename (without extension)
            ext: File extension
            used_paths: Set of already planned destination paths
            max_attempts: Maximum number of suffix attempts
            
        Returns:
            Unique Path object
        """
        destination = dest_dir / f"{base_name}{ext}"
        
        # Check both filesystem and planned paths
        if str(destination) not in used_paths and not destination.exists():
            return destination
        
        # Try numeric suffixes starting from _2
        for counter in range(2, max_attempts + 1):
            destination = dest_dir / f"{base_name}_{counter}{ext}"
            if str(destination) not in used_paths and not destination.exists():
                return destination
        
        # Fallback to timestamp-based name if all suffixes exhausted
        import time
        timestamp = int(time.time() * 1000)
        return dest_dir / f"{base_name}_{timestamp}{ext}"
        
    def preview_plan(self, plan: List[Dict]) -> str:
        """
        Generate human-readable summary of the plan.
        
        Args:
            plan: List of dicts with source, destination, action, status
            
        Returns:
            Formatted string summary
        """
        if not plan:
            return "No files to process."
            
        summary = []
        summary.append("Plan Summary:")
        summary.append("-" * 50)
        
        for item in plan:
            summary.append(f"Move: {item['source']}")
            summary.append(f"  To:   {item['destination']}")
            summary.append(f"  Action: {item['action']}")
            summary.append("")
            
        summary.append("-" * 50)
        summary.append(f"Total files: {len(plan)}")
        
        return "\n".join(summary)
        
    def execute_plan(self, plan: List[Dict], dry_run: bool = True) -> List[Dict]:
        """
        Execute the file operations.
        
        Args:
            plan: List of dicts with source, destination, action, status
            dry_run: If True, only simulate operations
            
        Returns:
            Updated plan with execution status
        """
        if not self.output_dir:
            raise OrganizerError("Output directory not set", status="config_error")
        
        executed_plan = []
        
        # Ensure output directory exists
        if not dry_run:
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Ensured output directory exists: {self.output_dir}")
            except Exception as e:
                logger.error(f"Failed to create output directory: {e}")
                raise OrganizerError(f"Failed to create output directory: {e}", status="failed_create_dir")
        
        for item in plan:
            source = Path(item["source"])
            destination = Path(item["destination"])
            action = item["action"]
            
            # Ensure destination directory exists
            dest_dir = destination.parent
            dir_status = self._ensure_destination_dir(dest_dir, dry_run)
            
            if dir_status.startswith("failed"):
                executed_plan.append({
                    **item,
                    "status": dir_status
                })
                continue
            
            if dry_run:
                executed_plan.append({
                    **item,
                    "status": "would_move"
                })
                continue
            
            # Perform the actual operation
            try:
                if not source.exists():
                    status = f"failed: Source file not found: {source}"
                    logger.error(status)
                elif action == "move":
                    # Check if destination already exists (shouldn't happen due to _generate_unique_path)
                    if destination.exists():
                        logger.warning(f"Destination exists, generating new unique path: {destination}")
                        destination = self._generate_unique_path(
                            dest_dir, destination.stem, destination.suffix, set()
                        )
                    source.rename(destination)
                    status = "moved"
                    logger.info(f"Moved: {source} -> {destination}")
                elif action == "copy":
                    if destination.exists():
                        logger.warning(f"Destination exists, generating new unique path: {destination}")
                        destination = self._generate_unique_path(
                            dest_dir, destination.stem, destination.suffix, set()
                        )
                    shutil.copy2(source, destination)
                    status = "copied"
                    logger.info(f"Copied: {source} -> {destination}")
                else:
                    status = f"failed: Invalid action: {action}"
                    logger.error(status)
            except PermissionError as e:
                status = f"failed_permission: {e}"
                logger.error(f"Permission denied: {e}")
            except OSError as e:
                status = f"failed_io: {e}"
                logger.error(f"I/O error: {e}")
            except Exception as e:
                status = f"failed: {e}"
                logger.exception(f"Unexpected error during file operation: {e}")
            
            executed_plan.append({
                **item,
                "status": status
            })
            
        return executed_plan
    
    def _ensure_destination_dir(self, dest_dir: Path, dry_run: bool) -> str:
        """
        Ensure destination directory exists, creating it if necessary.
        
        Args:
            dest_dir: Destination directory path
            dry_run: If True, only simulate
            
        Returns:
            Status string
        """
        if str(dest_dir) in self._created_dirs:
            return "ready"
        
        if dest_dir.exists():
            self._created_dirs.add(str(dest_dir))
            return "ready"
        
        if dry_run:
            return "would_create_dir"
        
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            self._created_dirs.add(str(dest_dir))
            logger.info(f"Created directory: {dest_dir}")
            return "created_dir"
        except PermissionError as e:
            logger.error(f"Permission denied creating directory {dest_dir}: {e}")
            return f"failed_permission: {e}"
        except OSError as e:
            logger.error(f"I/O error creating directory {dest_dir}: {e}")
            return f"failed_io: {e}"
        except Exception as e:
            logger.exception(f"Failed to create directory {dest_dir}: {e}")
            return f"failed_create_dir: {e}"