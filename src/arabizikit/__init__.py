"""arabizikit — Arabizi (Romanized Arabic) to Arabic-script transliteration toolkit.

Public API
----------
- ``transliterate`` : transliterate an Arabizi string to Arabic script.
- ``Transliterator`` : reusable object with candidate ranking and dialect hints.
- ``normalize``     : orthographic normalisation used by the benchmark and pipelines.
- ``benchmark``     : run the reproducible evaluation suite.
"""

from .dialect import guess_dialect
from .transliterate import Transliterator, transliterate

__version__ = "0.3.0"

__all__ = ["Transliterator", "__version__", "guess_dialect", "transliterate"]
