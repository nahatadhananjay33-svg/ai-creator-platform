"""Media acquisition providers.

The dataset builder operates on local media. Acquisition is abstracted behind
``MediaProvider`` so a different source (e.g. an importer for a platform's
official data export) can be added later without touching the pipeline. No
provider here scrapes or bypasses any platform's terms.
"""
from .base import MediaProvider
from .local_folder import LocalFolderProvider

__all__ = ["MediaProvider", "LocalFolderProvider"]
