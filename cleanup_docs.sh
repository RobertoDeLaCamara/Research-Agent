#!/bin/bash
# cleanup_docs.sh - Restructure repository documentation
# Run this script to clean up outdated and redundant documentation

set -e

echo "📚 Research-Agent Documentation Cleanup"
echo "========================================"
echo ""

# Create directories
echo "📁 Creating directory structure..."
mkdir -p docs/archive
mkdir -p scripts/archive
mkdir -p .github

# Archive outdated code reviews
echo "🗄️  Archiving outdated documentation..."
[ -f CODE_REVIEW.md ] && mv CODE_REVIEW.md docs/archive/CODE_REVIEW_2024.md && echo "  ✓ Archived CODE_REVIEW.md"
[ -f ACTION_ITEMS.md ] && mv ACTION_ITEMS.md docs/archive/ACTION_ITEMS_2024.md && echo "  ✓ Archived ACTION_ITEMS.md"
[ -f FIX_SUMMARY.md ] && mv FIX_SUMMARY.md docs/archive/FIX_SUMMARY_2024.md && echo "  ✓ Archived FIX_SUMMARY.md"
[ -f IMPROVEMENTS.md ] && mv IMPROVEMENTS.md docs/archive/IMPROVEMENTS_2024.md && echo "  ✓ Archived IMPROVEMENTS.md"

# Rename current review
echo "📝 Updating current documentation..."
[ -f CODE_REVIEW_2026.md ] && mv CODE_REVIEW_2026.md CODE_REVIEW.md && echo "  ✓ Renamed CODE_REVIEW_2026.md → CODE_REVIEW.md"

# Archive one-time scripts
echo "🔧 Archiving one-time fix scripts..."
[ -f fix_critical_issues.sh ] && mv fix_critical_issues.sh scripts/archive/ && echo "  ✓ Archived fix_critical_issues.sh"
[ -f fix_imports.sh ] && mv fix_imports.sh scripts/archive/ && echo "  ✓ Archived fix_imports.sh"

# Delete temporary files
echo "🗑️  Removing temporary files..."
[ -f CODE_REVIEW_INDEX.md ] && rm CODE_REVIEW_INDEX.md && echo "  ✓ Deleted CODE_REVIEW_INDEX.md"
[ -f REVIEW_SUMMARY.md ] && rm REVIEW_SUMMARY.md && echo "  ✓ Deleted REVIEW_SUMMARY.md"
[ -f MERGE_CHECKLIST.md ] && rm MERGE_CHECKLIST.md && echo "  ✓ Deleted MERGE_CHECKLIST.md"
[ -f QUICK_REFERENCE.md ] && rm QUICK_REFERENCE.md && echo "  ✓ Deleted QUICK_REFERENCE.md"
[ -f COMMIT_MESSAGE.txt ] && rm COMMIT_MESSAGE.txt && echo "  ✓ Deleted COMMIT_MESSAGE.txt"
[ -f reporte_Test_Topic.md ] && rm reporte_Test_Topic.md && echo "  ✓ Deleted reporte_Test_Topic.md"
[ -f research-agent.txt ] && rm research-agent.txt && echo "  ✓ Deleted research-agent.txt (3.6MB)"

echo ""
echo "✅ Documentation cleanup complete!"
echo ""
echo "📊 Summary:"
echo "  • Archived: 4 outdated documents → docs/archive/"
echo "  • Archived: 2 one-time scripts → scripts/archive/"
echo "  • Deleted: 7 temporary files"
echo "  • Renamed: CODE_REVIEW_2026.md → CODE_REVIEW.md"
echo ""
echo "📋 Next steps:"
echo "  1. Review changes: git status"
echo "  2. Create new docs: docs/ARCHITECTURE.md, docs/SECURITY.md, etc."
echo "  3. Update README.md with new documentation structure"
echo "  4. Commit: git commit -m 'docs: restructure and clean up documentation'"
