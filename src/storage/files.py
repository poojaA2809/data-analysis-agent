"""Local file storage for uploaded datasets."""
from pathlib import Path

# Repo-root/data/uploads — files.py is at src/storage/files.py → 3 parents up.
_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def uploads_dir() -> Path:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return _UPLOAD_DIR


def store_upload(dataset_id: str, content: bytes, suffix: str = ".csv") -> str:
    """Write raw upload bytes to data/uploads/<dataset_id><suffix>; return the path."""
    dest = uploads_dir() / f"{dataset_id}{suffix}"
    dest.write_bytes(content)
    return str(dest)
