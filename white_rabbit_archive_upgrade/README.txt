WHITE RABBIT PREVIOUS ARTICLES ARCHIVE UPGRADE - V4

IMPORTANT: Use the Python installer. Do not run the old PowerShell installer.

From the project root with the virtual environment active:

    python .\white_rabbit_archive_upgrade\install_upgrade.py

The installer:
- backs up existing files it replaces
- copies the archive/retrieval modules into the project
- preserves .env and adds only missing archive settings
- prompts for WR_SUBSTACK_URL if not already configured
- creates research_library and knowledge directories
- installs requirements
- runs the test suite

Afterward:

    python -m white_rabbit archive sync
    python -m white_rabbit archive status
