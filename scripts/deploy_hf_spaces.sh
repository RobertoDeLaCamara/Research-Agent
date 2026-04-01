#!/usr/bin/env bash
# Deploy Research-Agent to Hugging Face Spaces
# Usage: ./scripts/deploy_hf_spaces.sh <hf-username>
#
# Prerequisites:
#   pip install huggingface_hub
#   huggingface-cli login   (or set HF_TOKEN env var)

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

echo "▶ Deploying to Hugging Face Space: ${HF_REPO}"

# ── 1. Create the Space if it doesn't exist ───────────────────────────────────
python3 - <<PYEOF
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

# ── 2. Set up hf remote ───────────────────────────────────────────────────────
cd "$REPO_ROOT"
if git remote get-url hf &>/dev/null; then
  git remote set-url hf "$HF_REMOTE"
else
  git remote add hf "$HF_REMOTE"
fi
echo "  Remote 'hf' → ${HF_REMOTE}"

# ── 3. Prepare HF-specific files in a temp branch ────────────────────────────
TEMP_BRANCH="hf-spaces-deploy-$(date +%s)"
git checkout -b "$TEMP_BRANCH"

# Replace Dockerfile with the Spaces variant
cp Dockerfile.spaces Dockerfile

# Replace README.md with the HF frontmatter version
cp hf_spaces/README.md README.md

git add Dockerfile README.md
git commit --allow-empty -m "chore: prepare Dockerfile and README for HF Spaces deploy"

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
echo "Next: set OPENAI_API_KEY (Groq key) as a Secret in the Space settings"
echo "      so the demo works without users pasting their own key:"
echo "   https://huggingface.co/spaces/${HF_REPO}/settings"
