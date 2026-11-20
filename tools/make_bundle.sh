#!/usr/bin/env bash
# Build the submission zip from the repo root: the PDF-spec bundle (scene.blend, wrapper/,
# renders/, metadata.json, README.md) plus what the rubric scores and what the wrapper needs to
# render (textures/, outputs/videos/, outputs/stills/), the Dockerfile, the AI disclosure, the
# unit tests and the validator. Files sit at the top of the zip, as in the track slide.
#
#     tools/make_bundle.sh CollegeName_TeamName        # writes CollegeName_TeamName.zip
#     tools/make_bundle.sh NAME OUT_DIR                # writes OUT_DIR/NAME.zip
#
# Then test it from a clean unzip:
#     python3 tools/validate.py --zip NAME.zip --blender "$BLENDER"
set -euo pipefail

name=${1:?usage: tools/make_bundle.sh NAME [OUT_DIR]}
root=$(cd "$(dirname "$0")/.." && pwd)
out_dir=$(cd "${2:-$root}" && pwd)
out="$out_dir/$name.zip"

cd "$root"
files=(
  scene.blend wrapper renders metadata.json README.md
  textures outputs/videos outputs/stills outputs/direction_check.json
  Dockerfile .dockerignore AI_DISCLOSURE.md tests tools/validate.py
)
for f in "${files[@]}"; do
  [ -e "$f" ] || { echo "missing: $f" >&2; exit 1; }
done
[ -e LICENSE ] && files+=(LICENSE)

rm -f "$out"
zip -q -r -X "$out" "${files[@]}" \
  -x '*/__pycache__/*' '*.pyc' '*.DS_Store' '*.blend1'
echo "$out ($(du -h "$out" | cut -f1))"
