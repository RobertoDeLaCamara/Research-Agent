#!/bin/bash
# fix_critical_issues.sh - Apply critical fixes to Research-Agent

set -e

echo "🔧 Research-Agent Critical Fixes"
echo "================================"
echo ""

# Backup original files
echo "📦 Creating backups..."
mkdir -p .backups
cp -r src .backups/src_backup_$(date +%Y%m%d_%H%M%S)

# Fix 1: Update imports in src/agent.py
echo "🔨 Fixing imports in src/agent.py..."
sed -i 's/^from tools\./from .tools./g' src/agent.py
sed -i 's/^from db_manager/from .db_manager/g' src/agent.py

# Fix 2: Update imports in all tool files
echo "🔨 Fixing imports in src/tools/*.py..."
find src/tools -name "*.py" -type f -exec sed -i 's/^from state import/from ..state import/g' {} \;
find src/tools -name "*.py" -type f -exec sed -i 's/^from utils import/from ..utils import/g' {} \;
find src/tools -name "*.py" -type f -exec sed -i 's/^from config import/from ..config import/g' {} \;
find src/tools -name "*.py" -type f -exec sed -i 's/^from db_manager import/from ..db_manager import/g' {} \;
find src/tools -name "*.py" -type f -exec sed -i 's/^from progress import/from ..progress import/g' {} \;
find src/tools -name "*.py" -type f -exec sed -i 's/^from tools\./from ./g' {} \;

# Fix 3: Update imports in src/*.py files
echo "🔨 Fixing imports in src/*.py files..."
find src -maxdepth 1 -name "*.py" -type f -exec sed -i 's/^from config import/from .config import/g' {} \;
find src -maxdepth 1 -name "*.py" -type f -exec sed -i 's/^from state import/from .state import/g' {} \;
find src -maxdepth 1 -name "*.py" -type f -exec sed -i 's/^from utils import/from .utils import/g' {} \;

# Fix 4: Add missing dependencies
echo "📦 Checking requirements.txt..."
if ! grep -q "python-docx" requirements.txt; then
    echo "python-docx>=0.8.11" >> requirements.txt
    echo "✅ Added python-docx"
fi

# Fix 5: Remove duplicate PyPDF2 entry (keep PyPDF2, remove pypdf2)
if grep -q "^pypdf2$" requirements.txt; then
    sed -i '/^pypdf2$/d' requirements.txt
    echo "✅ Removed duplicate pypdf2 entry"
fi

# Fix 6: Ensure PyPDF2 is correctly listed
if ! grep -q "PyPDF2" requirements.txt; then
    echo "PyPDF2>=3.0.0" >> requirements.txt
    echo "✅ Added PyPDF2"
fi

echo ""
echo "✅ Critical fixes applied!"
echo ""
echo "⚠️  IMPORTANT SECURITY NOTICE:"
echo "   Your .env file contains exposed credentials!"
echo "   Please IMMEDIATELY:"
echo "   1. Revoke all API keys and tokens"
echo "   2. Generate new credentials"
echo "   3. Update .env with new values"
echo "   4. Verify .env is in .gitignore"
echo ""
echo "📋 Next steps:"
echo "   1. Review the changes: git diff"
echo "   2. Run tests: python3 -m pytest tests/ -v"
echo "   3. If tests pass, commit: git add . && git commit -m 'fix: resolve import issues'"
echo ""
echo "💾 Backups saved in .backups/"
