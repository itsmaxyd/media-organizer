import logging
from pathlib import Path
from typing import List, Dict, Literal
from dataclasses import dataclass, field

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

logger = logging.getLogger(__name__)

class Organizer:
    def __init__(self, settings: Settings):
        """
        Initialize Organizer with settings.
        
        Args:
            settings: Settings instance containing output_dir and other configuration
        """
        self.settings = settings
        self.output_dir = Path(settings.output_dir)
        
    def build_plan(self, results: List[Dict]) -> List[Dict]:
        """
        Build execution plan from LLM results.
        
        Args:
            results: List of dicts with keys: source, category, subcategory, descriptive_name, tags, confidence, reasoning
            
        Returns:
            List of dicts with source, destination, action, and status
        """
        plan = []
        
        for result in results:
            source = Path(result["source"])
            category = result["category"]
            descriptive_name = result["descriptive_name"]
            ext = source.suffix.lower()
            
            # Build destination path
            dest_dir = self.output_dir / category
            if result.get("subcategory"):
                dest_dir = dest_dir / result["subcategory"]
            
            # Generate unique filename if needed
            base_name = f"{descriptive_name}{ext}"
            destination = dest_dir / base_name
            
            # Resolve conflicts by adding numeric suffix
            counter = 1
            while destination.exists():
                base_name = f"{descriptive_name}_{counter}{ext}"
                destination = dest_dir / base_name
                counter += 1
            
            plan.append({
                "source": str(source),
                "destination": str(destination),
                "action": "move",
                "status": "pending"
            })
            
        return plan
        
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
        executed_plan = []
        
        for item in plan:
            source = Path(item["source"])
            destination = Path(item["destination"])
            action = item["action"]
            
            # Ensure destination directory exists
            dest_dir = destination.parent
            if not dest_dir.exists():
                if dry_run:
                    status = "would_create_dir"
                else:
                    try:
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        status = "created_dir"
                    except Exception as e:
                        status = f"failed_create_dir: {e}"
            else:
                status = "ready"
            
            if status.startswith("failed"):
                executed_plan.append({
                    **item,
                    "status": status
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
                if action == "move":
                    source.rename(destination)
                    status = "moved"
                elif action == "copy":
                    import shutil
                    shutil.copy2(source, destination)
                    status = "copied"
                else:
                    status = "invalid_action"
            except Exception as e:
                status = f"failed: {e}"
            
            executed_plan.append({
                **item,
                "status": status
            })
            
        return executed_plan