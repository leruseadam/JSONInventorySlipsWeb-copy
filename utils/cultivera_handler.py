from pathlib import Path
from typing import Dict, List, Optional
import json
import shutil
from datetime import datetime
import logging

class CultiveraHandler:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.incoming_dir = self.root_dir / "incoming"
        self.processed_dir = self.root_dir / "processed"
        self.failed_dir = self.root_dir / "failed"
        self._setup_directories()
        self._setup_logging()

    def _setup_directories(self) -> None:
        """Create required directories if they don't exist"""
        for dir_path in [self.incoming_dir, self.processed_dir, self.failed_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _setup_logging(self) -> None:
        """Configure logging"""
        logging.basicConfig(
            filename=self.root_dir / "cultivera.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def process_file(self, file_path: Path) -> Optional[Dict]:
        """Process a single Cultivera file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Move to processed directory with timestamp
            new_path = self._move_file(file_path, self.processed_dir)
            logging.info(f"Successfully processed file: {file_path.name}")
            return data

        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error in {file_path.name}: {str(e)}")
            self._move_file(file_path, self.failed_dir)
            return None
        except Exception as e:
            logging.error(f"Error processing {file_path.name}: {str(e)}")
            self._move_file(file_path, self.failed_dir)
            return None

    def _move_file(self, file_path: Path, destination: Path) -> Path:
        """Move file to destination with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        new_path = destination / new_name
        shutil.move(str(file_path), str(new_path))
        return new_path

    def get_pending_files(self) -> List[Path]:
        """Get list of files waiting to be processed"""
        return list(self.incoming_dir.glob("*.json"))