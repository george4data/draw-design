#!/usr/bin/env bash
# Re-create the read-only reference checkouts used by docs/prd.md.
# They are git-ignored; never edit them and never import code from them at runtime.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p reference
clone() {
  local url="$1" dir="$2"
  if [ -d "reference/$dir/.git" ]; then
    git -C "reference/$dir" pull --ff-only
  else
    git clone --depth 1 "$url" "reference/$dir"
  fi
}
clone https://github.com/cathrynlavery/diagram-design.git diagram-design
clone https://github.com/jgraph/drawio-desktop.git drawio-desktop
