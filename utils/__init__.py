from pathlib import Path


def list_files(folder: str):
    folder_path = Path(folder)
    if not folder_path.exists():
        return []
    return sorted(p.name for p in folder_path.iterdir() if p.is_file())
