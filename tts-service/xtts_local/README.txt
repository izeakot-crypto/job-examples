XTTS v2 Local Test
==================

This folder contains scripts to test Coqui XTTS v2 locally.

REQUIREMENTS:
- Python 3.9+
- 4GB+ RAM
- ~2GB disk space for model

INSTALLATION:
1. Open terminal in this folder
2. Run: python install.py
3. Wait for installation (may take 5-10 minutes)

TESTING:
1. Run: python test_xtts.py
2. First run will download the model (~1.8GB)
3. Audio samples will be saved to 'samples/' folder

SUPPORTED LANGUAGES:
- Ukrainian (uk)
- English (en)
- Russian (ru)
- Polish (pl)
- Spanish (es)
- Turkish (tr)

NOTES:
- First run is slow (model download + loading)
- Subsequent runs are faster
- CPU mode is slower than GPU
- For GPU: install PyTorch with CUDA support
