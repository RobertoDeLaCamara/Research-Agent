#!/usr/bin/env bash
# Deploy Research-Agent to Hugging Face Spaces
# Usage: ./scripts/deploy_hf_spaces.sh <hf-username>
#
# Prerequisites:
#   venv/bin/python -c "from huggingface_hub import login; login()"

set -euo pipefail

HF_USER="${1:-}"
if [[ -z "$HF_USER" ]]; then
  echo "Usage: $0 <huggingface-username>"
  exit 1
fi

SPACE_NAME="research-agent"
HF_REPO="${HF_USER}/${SPACE_NAME}"
HF_REMOTE="https://huggingface.co/spaces/${HF_REPO}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${REPO_ROOT}/venv/bin/python"
if [[ ! -f "$PYTHON" ]]; then PYTHON="python3"; fi

echo "▶ Deploying to Hugging Face Space: ${HF_REPO}"

# ── 1. Create the Space if it doesn't exist ───────────────────────────────────
"$PYTHON" - <<PYEOF
from huggingface_hub import HfApi
api = HfApi()
try:
    api.repo_info(repo_id="${HF_REPO}", repo_type="space")
    print("  Space already exists — skipping creation.")
except Exception:
    api.create_repo(
        repo_id="${HF_REPO}",
        repo_type="space",
        space_sdk="docker",
        private=False,
        exist_ok=True,
    )
    print("  Space created: https://huggingface.co/spaces/${HF_REPO}")
PYEOF

# ── 2. Set up hf remote (token embedded for non-interactive push) ─────────────
cd "$REPO_ROOT"
HF_TOKEN="${HF_TOKEN:-$(cat ~/.cache/huggingface/token 2>/dev/null || echo "")}"
if [[ -z "$HF_TOKEN" ]]; then
  echo "ERROR: No HF token found. Run: venv/bin/python -c \"from huggingface_hub import login; login()\""
  exit 1
fi
HF_REMOTE_AUTH="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_REPO}"
if git remote get-url hf &>/dev/null; then
  git remote set-url hf "$HF_REMOTE_AUTH"
else
  git remote add hf "$HF_REMOTE_AUTH"
fi
echo "  Remote 'hf' → ${HF_REMOTE}"

# ── 3. Build an orphan branch (no history) to avoid binary file rejection ─────
TEMP_BRANCH="hf-spaces-deploy-$(date +%s)"

TMPDIR_DEPLOY="$(mktemp -d)"
# Copy all tracked files except binaries HF rejects
git ls-files | grep -vE '\.(gif|db|sqlite|sqlite3|png|jpg|jpeg|mp4|pt|bin|pkl)$' \
  | xargs -I{} bash -c 'mkdir -p "$1/$(dirname "$2")" && cp "$2" "$1/$2"' _ "$TMPDIR_DEPLOY" {}

# Swap in HF-specific files
cp Dockerfile.spaces "${TMPDIR_DEPLOY}/Dockerfile"
cp hf_spaces/README.md "${TMPDIR_DEPLOY}/README.md"

# Create orphan branch from that clean tree
git checkout --orphan "$TEMP_BRANCH"
git rm -rf . --quiet
cp -r "${TMPDIR_DEPLOY}/." .
rm -rf "$TMPDIR_DEPLOY"

git add -A
git commit -m "chore: HF Spaces deploy (orphan — no binary history)"

# ── 4. Push to HF ─────────────────────────────────────────────────────────────
echo "▶ Pushing to Hugging Face…"
git push hf "${TEMP_BRANCH}:main" --force

# ── 5. Clean up temp branch ───────────────────────────────────────────────────
git checkout main
git branch -D "$TEMP_BRANCH"

echo ""
echo "✅ Deployed! Your Space will be live in ~2 minutes at:"
echo "   https://huggingface.co/spaces/${HF_REPO}"
echo ""
echo "Next: set OPENAI_API_KEY (Groq key) as a Secret in the Space settings:"
echo "   https://huggingface.co/spaces/${HF_REPO}/settings"
