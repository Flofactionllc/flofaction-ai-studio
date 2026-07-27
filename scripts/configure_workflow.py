#!/usr/bin/env python3
import os
import json
from pathlib import Path

DIRS = [
    "/Users/pauledwards/flofaction-ai-studio/output/commercial",
    "/Users/pauledwards/flofaction-ai-studio/output/social",
    "/Users/pauledwards/flofaction-ai-studio/logs",
    "/Users/pauledwards/flofaction-ai-studio/assets/brand",
    "/Users/pauledwards/flofaction-ai-studio/assets/intro",
    "/Users/pauledwards/flofaction-ai-studio/assets/products",
]

for d in DIRS:
    Path(d).mkdir(parents=True, exist_ok=True)
print("✅ Workflow configuration complete!")
