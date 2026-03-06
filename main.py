#!/usr/bin/env python3
"""Media Organizer - Main entry point with CLI and GUI modes."""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Configure logging
def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def run_cli_mode(args) -> int:
    """Run in headless CLI mode.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    logger = setup_logging(args.verbose)
    logger.info("Running in CLI mode")
    
    # Import core modules
    from media_organizer.core.llm_client import Settings, APIKeyError, APICallError
    from media_organizer.core.cache_manager import CacheManager
    from media_organizer.core.organizer import Organizer
    from media_organizer.gui.worker import MediaAnalyzer
    
    # Load settings
    settings = Settings()
    
    # Override with CLI args
    if args.source:
        settings.source_dir = args.source
    if args.output:
        settings.output_dir = args.output
    if args.limit:
        settings.testing_limit = args.limit
        settings.testing_mode = True
    if args.dry_run is not None:
        settings.dry_run = args.dry_run
    
    # Validate inputs
    if not settings.source_dir:
        logger.error("Source directory required. Use --source")
        return 1
    
    source_path = Path(settings.source_dir)
    if not source_path.exists():
        logger.error(f"Source directory does not exist: {source_path}")
        return 1
    
    if not settings.output_dir:
        logger.error("Output directory required. Use --output")
        return 1
    
    output_path = Path(settings.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Check API key
    if not settings.api_key:
        logger.error("API key not configured. Set it in Settings or config.json")
        return 1
    
    logger.info(f"Source: {source_path}")
    logger.info(f"Output: {output_path}")
    logger.info(f"Testing mode: {settings.testing_mode} (limit: {settings.testing_limit})")
    logger.info(f"Dry run: {settings.dry_run}")
    
    # Initialize components
    cache_manager = CacheManager()
    
    try:
        analyzer = MediaAnalyzer(settings, cache_manager)
    except APIKeyError as e:
        logger.error(f"API Key error: {e}")
        return 1
    
    # Track statistics
    total_tokens = {"prompt": 0, "completion": 0}
    start_time = datetime.now()
    
    def progress_callback(current: int, total: int, result: dict):
        """Report progress."""
        progress_pct = (current / total * 100) if total > 0 else 0
        logger.info(f"[{current}/{total}] {progress_pct:.0f}% - {result.get('source', 'unknown')}")
        if result.get('category'):
            logger.info(f"  -> Category: {result.get('category')}, Name: {result.get('descriptive_name')}")
    
    def file_done_callback(result: dict):
        """Called when a file is done."""
        status = result.get('status', 'unknown')
        if status == 'error':
            logger.error(f"  Error: {result.get('error_message', 'Unknown error')}")
    
    def token_callback(prompt_tokens: int, completion_tokens: int):
        """Track token usage."""
        total_tokens["prompt"] += prompt_tokens
        total_tokens["completion"] += completion_tokens
        logger.debug(f"Tokens: prompt={prompt_tokens}, completion={completion_tokens}")
    
    def should_cancel():
        """CLI mode doesn't support cancellation."""
        return False
    
    # Run analysis
    logger.info("Starting analysis...")
    try:
        results = analyzer.analyze_directory(
            directory=source_path,
            progress_callback=progress_callback,
            file_done_callback=file_done_callback,
            token_callback=token_callback,
            should_cancel=should_cancel
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return 1
    
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\nAnalysis complete: {len(results)} files processed in {elapsed:.1f}s")
    logger.info(f"Total tokens used: prompt={total_tokens['prompt']}, completion={total_tokens['completion']}")
    
    # Build and execute plan
    organizer = Organizer(settings)
    plan = organizer.build_plan(results)
    
    logger.info(f"\nExecution plan ({len(plan)} operations):")
    for op in plan[:10]:  # Show first 10
        logger.info(f"  {op['action']}: {Path(op['source']).name} -> {op['destination']}")
    if len(plan) > 10:
        logger.info(f"  ... and {len(plan) - 10} more")
    
    if settings.dry_run:
        logger.info("\nDry run - no files were moved. Use --no-dry-run to execute.")
    else:
        logger.info("\nExecuting plan...")
        try:
            organizer.execute_plan(plan)
            logger.info("Execution complete!")
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return 1
    
    return 0


def run_gui_mode() -> int:
    """Run in GUI mode.
    
    Returns:
        Exit code
    """
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont
    from PyQt5.QtCore import Qt
    from media_organizer.gui.main_window import MainWindow
    
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set application font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    return app.exec_()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Media Organizer - Organize media files with AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # GUI mode (default)
  python main.py

  # CLI mode with dry run
  python main.py --cli --source /path/to/media --output /path/out --limit 5 --dry-run

  # CLI mode - execute for real
  python main.py --cli --source /path/to/media --output /path/out --no-dry-run
        """
    )
    
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in headless CLI mode (no GUI)"
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Source directory containing media files"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output directory for organized files"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of files to process (testing mode)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Preview changes without moving files (default in testing mode)"
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Execute real file operations"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Handle --no-dry-run
    if args.no_dry_run:
        args.dry_run = False
    elif args.dry_run is None:
        args.dry_run = True  # Default to dry run
    
    if args.cli:
        return run_cli_mode(args)
    else:
        return run_gui_mode()


if __name__ == "__main__":
    sys.exit(main())
