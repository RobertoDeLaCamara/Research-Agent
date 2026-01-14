#!/bin/bash
# Fix import paths in all Python files

cd /home/ecerocg/research-agent

# Fix relative imports in src/ directory
find src/ -name "*.py" -exec sed -i 's/^from state import/from .state import/g' {} \;
find src/ -name "*.py" -exec sed -i 's/^from config import/from .config import/g' {} \;
find src/ -name "*.py" -exec sed -i 's/^from utils import/from .utils import/g' {} \;
find src/ -name "*.py" -exec sed -i 's/^from tools\./from .tools./g' {} \;

echo "Import paths fixed"
