#!/usr/bin/env bash
# Superseded: xr/ is now served from this repo by .github/workflows/pages.yml at
# https://aryankalra404.github.io/SyntheticEyes/ . Kept for the old link only.
#
# Publish the WebXR bust in xr/ to the public repo aryankalra404/syntheticeyes-xr, served by
# GitHub Pages from main at / : https://aryankalra404.github.io/syntheticeyes-xr/
#
#     tools/publish_xr.sh                   # commit message "sync xr at <short sha>"
#     tools/publish_xr.sh "fix lash flicker"
#
# Copies the page and its assets only (no .certs, no tests, no local server), adds .nojekyll
# and a README, commits as the repo owner with the GitHub noreply address and pushes. Creates
# the repo and turns Pages on the first time. Uses the aryankalra404 gh account without
# switching the active one.
set -euo pipefail

ACCOUNT=aryankalra404
REPO=$ACCOUNT/syntheticeyes-xr
SITE=https://$ACCOUNT.github.io/syntheticeyes-xr/
ROOT=$(cd "$(dirname "$0")/.." && pwd)

GH_TOKEN=$(gh auth token -u "$ACCOUNT")
export GH_TOKEN
git_auth() {
  git -c credential.helper= \
      -c 'credential.helper=!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f' "$@"
}

sha=$(git -C "$ROOT" rev-parse --short HEAD)
msg=${1:-"sync xr at $sha"}
if [ -n "$(git -C "$ROOT" status --porcelain -- xr)" ]; then
  echo "note: xr/ has uncommitted changes; they are published as they are on disk" >&2
fi

if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public \
    --description "SyntheticEyes: a synthetic head that looks at you (WebXR, three.js)" \
    --homepage "$SITE" >/dev/null
  echo "created $REPO"
fi

user_id=$(gh api user -q .id)
name=$(git -C "$ROOT" config user.name)
email="$user_id+$ACCOUNT@users.noreply.github.com"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git_auth clone -q "https://github.com/$REPO.git" "$tmp/site" 2>/dev/null
cd "$tmp/site"
git rev-parse -q --verify HEAD >/dev/null || git symbolic-ref HEAD refs/heads/main

rsync -a --delete \
  --exclude .git --exclude .certs --exclude tests --exclude serve.py --exclude package.json \
  --exclude node_modules --exclude .DS_Store \
  "$ROOT/xr/" ./
touch .nojekyll
{
  echo "# SyntheticEyes in a headset"
  echo
  echo "This repository is the published copy of the \`xr/\` folder of the SyntheticEyes"
  echo "project (Samsung PRISM XR Hackathon 2026, Track 1). It holds the page and its assets"
  echo "only; the local server, the tests and the export from Blender stay in the main project."
  echo
  echo "---"
  echo
  tail -n +2 "$ROOT/xr/README.md"
} > README.md

git add -A
if git diff --cached --quiet; then
  echo "already up to date: $SITE"
else
  git -c user.name="$name" -c user.email="$email" commit -q -m "$msg"
  git_auth push -q origin HEAD:main
  echo "pushed $(git rev-parse --short HEAD) to $REPO"
fi

if ! gh api "repos/$REPO/pages" >/dev/null 2>&1; then
  gh api -X POST "repos/$REPO/pages" -f "source[branch]=main" -f "source[path]=/" >/dev/null
  echo "pages turned on (the first build takes a minute or two)"
fi
echo "$SITE"
