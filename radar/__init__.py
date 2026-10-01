"""Topic-adaptive briefing engine.

RADAR_* is the public configuration namespace. GENUI_* remains a compatibility
alias for installed voices/accounts and historical experiments during migration.
"""
import os

for key, value in list(os.environ.items()):
    if key.startswith('RADAR_'):
        os.environ['GENUI_'+key[6:]] = value
