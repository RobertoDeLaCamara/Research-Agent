"""Saving files uploaded through the dashboard into the knowledge base."""

import os
from typing import Iterable, List, Tuple

from .config import settings


def save_uploads(files: Iterable, kb_path: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Write each uploaded file into ``kb_path`` if it passes the configured checks.

    ``files`` are objects with ``.name``, ``.size`` and ``.getbuffer()`` (Streamlit's UploadedFile).
    Only the base name of the client-supplied filename is used, so a name such as
    ``../../app/src/x.py`` cannot write outside ``kb_path``.

    Returns ``(saved_names, rejected)`` where ``rejected`` holds ``(name, reason)`` pairs with
    reason ``"extension"``, ``"size"`` or ``"name"``.
    """
    allowed = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in settings.allowed_file_extensions}
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    os.makedirs(kb_path, exist_ok=True)

    saved, rejected = [], []
    for f in files:
        name = os.path.basename((f.name or "").replace("\\", "/")).strip()
        if not name or name.startswith("."):
            rejected.append((f.name, "name"))
            continue
        if os.path.splitext(name)[1].lower() not in allowed:
            rejected.append((name, "extension"))
            continue
        if f.size > max_bytes:
            rejected.append((name, "size"))
            continue
        with open(os.path.join(kb_path, name), "wb") as out:
            out.write(f.getbuffer())
        saved.append(name)
    return saved, rejected


def uploader_types() -> List[str]:
    """Extensions for ``st.file_uploader(type=...)``, without the leading dot."""
    return [e.lstrip(".").lower() for e in settings.allowed_file_extensions]
