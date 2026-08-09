#!/bin/bash
# thinkstack: get users off a bad production release.
#
# ── The constraint this script is shaped by ──
#
# You cannot un-ship. The updater compares versions and only ever moves
# FORWARD, so an app that already updated to the bad version will never
# "update" back to the good one. Deleting the release does not reach it either.
#
# That splits rollback into two different problems, and they need different
# answers:
#
#   1. People who have not updated yet, and anyone downloading now.
#      Fixable instantly: /releases/latest resolves to the newest release NOT
#      marked prerelease, so marking the bad one as a prerelease makes GitHub
#      fall back to the previous good release within seconds. Downloads and
#      update checks both follow it. Nothing is deleted, so the assets survive
#      for diagnosis, and undoing it is one command.
#
#   2. People who already updated.
#      Only reachable by shipping AGAIN, with the old code under a HIGHER
#      number, because forward is the only direction that exists.
#
# usage:
#   scripts/rollback.sh                  # (1) hide the bad release, fall back
#   scripts/rollback.sh --reship         # (2) also re-ship the good tree
#   scripts/rollback.sh --undo           # unhide, if it was a false alarm
#   scripts/rollback.sh --dry-run
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'

MAIN_BRANCH="main"
REPO="$(jq -r '.repo // empty' release.config.json 2>/dev/null)"
[ -n "$REPO" ] || { echo "cannot read .repo from release.config.json" >&2; exit 1; }

MODE="hide"
DRY_RUN=false

while [ $# -gt 0 ]; do
    case "$1" in
        --reship)  MODE="reship"; shift ;;
        --undo)    MODE="undo"; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
        *)         echo -e "${RED}unknown argument: $1${NC}"; exit 1 ;;
    esac
done

run()  { echo -e "  ${CYAN}\$${NC} $*"; $DRY_RUN || "$@"; }
fail() { echo -e "${RED}✗ $*${NC}"; exit 1; }
ok()   { echo -e "  ${GREEN}✓${NC} $*"; }

# ── what is out there ───────────────────────────────────────
# Tolerated here, unlike in ship.sh. The default mode reads the release list
# from the API rather than from git, and hiding a bad release is the urgent
# path -- refusing to help during an incident because a fetch failed would be
# the wrong trade. --reship checks out a tag, so it insists separately below.
git fetch --quiet --tags origin 2>/dev/null \
    || echo -e "  ${YELLOW}!${NC} could not reach origin - release list still read from the API"

# Every stable release, newest first. Prereleases are excluded because betas
# and the rolling accel release are not candidates to fall back to.
mapfile -t STABLE < <(gh release list --repo "$REPO" --limit 30 \
    --json tagName,isPrerelease,isDraft \
    -q '.[] | select(.isPrerelease==false and .isDraft==false) | .tagName' 2>/dev/null)

[ "${#STABLE[@]}" -ge 1 ] || fail "no stable releases found"

CURRENT="${STABLE[0]}"
PREVIOUS="${STABLE[1]:-}"

echo -e "${CYAN}────────────────────────────────────────────${NC}"
echo -e "${CYAN}  rollback: production${NC}"
echo -e "${CYAN}────────────────────────────────────────────${NC}"
echo ""
echo -e "  currently latest: ${RED}${CURRENT}${NC}"
echo -e "  would fall back to: ${GREEN}${PREVIOUS:-(nothing - this is the only release)}${NC}"

# ── undo ────────────────────────────────────────────────────
if [ "$MODE" = "undo" ]; then
    HIDDEN="$(gh release list --repo "$REPO" --limit 30 --json tagName,isPrerelease \
        -q '.[] | select(.isPrerelease==true) | .tagName' 2>/dev/null | grep -E '^v[0-9]' | head -1)"
    [ -n "$HIDDEN" ] || fail "no hidden stable release to restore"
    echo ""
    echo -e "  restoring ${HIDDEN} to a normal release"
    run gh release edit "$HIDDEN" --repo "$REPO" --prerelease=false --latest
    ok "${HIDDEN} is visible again"
    exit 0
fi

[ -n "$PREVIOUS" ] || fail "there is no earlier release to fall back to"

# ── 1. hide the bad release ─────────────────────────────────
echo ""
echo -e "${CYAN}[step 1]${NC} take ${CURRENT} out of circulation"
echo -e "  Marking it a prerelease rather than deleting it: /releases/latest"
echo -e "  skips prereleases, so downloads and update checks fall back to"
echo -e "  ${PREVIOUS} within seconds. The assets stay put for diagnosis, and"
echo -e "  ${CYAN}scripts/rollback.sh --undo${NC} puts it back."
echo ""
echo -e "  ${YELLOW}This does NOT reach anyone who already updated to ${CURRENT}.${NC}"
echo -e "  ${YELLOW}The updater only moves forward. For them, use --reship.${NC}"

if ! $DRY_RUN; then
    echo ""
    printf "  hide %s and fall back to %s? [y/N] " "$CURRENT" "$PREVIOUS"
    read -r ans
    case "$ans" in y|Y|yes) ;; *) echo "  aborted."; exit 0 ;; esac
fi

run gh release edit "$CURRENT" --repo "$REPO" --prerelease=true || fail "could not hide ${CURRENT}"
run gh release edit "$PREVIOUS" --repo "$REPO" --latest || fail "could not mark ${PREVIOUS} latest"

if ! $DRY_RUN; then
    RESOLVED="$(gh api "repos/${REPO}/releases/latest" -q .tag_name 2>/dev/null)"
    [ "$RESOLVED" = "$PREVIOUS" ] || fail "/releases/latest still resolves to ${RESOLVED}"
    ok "/releases/latest -> ${PREVIOUS}"
fi

if [ "$MODE" != "reship" ]; then
    echo ""
    echo -e "${CYAN}────────────────────────────────────────────${NC}"
    echo -e "${GREEN}  new downloads and update checks now get ${PREVIOUS}.${NC}"
    echo -e "  ${YELLOW}Anyone already on ${CURRENT} is still on it.${NC}"
    echo -e "  To reach them: ${CYAN}scripts/rollback.sh --reship${NC}"
    echo -e "${CYAN}────────────────────────────────────────────${NC}"
    exit 0
fi

# ── 2. re-ship the good tree under a higher number ──────────
echo ""
echo -e "${CYAN}[step 2]${NC} re-ship ${PREVIOUS}'s code under a NEW higher version"
echo -e "  This is the only way to reach an app that already updated: forward."

[ -z "$(git status --porcelain)" ] || fail "working tree is dirty - commit or stash first"

# This half rewrites main from a tag, so the tag has to be the real one.
git fetch --quiet --tags origin \
    || fail "could not reach origin - refusing to rewrite ${MAIN_BRANCH} from possibly stale tags"
git rev-parse "refs/tags/${PREVIOUS}" >/dev/null 2>&1 \
    || fail "tag ${PREVIOUS} not found locally after fetch"

BAD_V="${CURRENT#v}"
NEW_V="$(python3 - "$BAD_V" <<'PY'
import sys
major, minor, patch = (int(x) for x in sys.argv[1].split("."))
# One past the BAD version, not past the good one: the number has to exceed
# what people already have, and what they have is the bad one.
print(f"{major}.{minor}.{patch + 1}")
PY
)"

echo -e "  ${CURRENT} is bad; ${PREVIOUS}'s tree will ship as ${GREEN}v${NEW_V}${NC}"
echo -e "  ${YELLOW}main will be reset to ${PREVIOUS} and force-pushed.${NC}"
echo ""
echo -e "  ${RED}This rewrites the production branch.${NC}"

if ! $DRY_RUN; then
    printf "  type the version to confirm (%s): " "$NEW_V"
    read -r typed
    [ "$typed" = "$NEW_V" ] || { echo "  aborted."; exit 0; }
fi

START_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
trap 'git checkout --quiet "$START_BRANCH" 2>/dev/null || true' EXIT

run git checkout --quiet -B "$MAIN_BRANCH" "refs/tags/${PREVIOUS}" || fail "could not check out ${PREVIOUS}"
run git push --force-with-lease origin "refs/heads/${MAIN_BRANCH}:refs/heads/${MAIN_BRANCH}" \
    || fail "could not push ${MAIN_BRANCH}"
run gh workflow run release.yml --repo "$REPO" -f channel=stable -f version="$NEW_V" \
    || fail "could not dispatch release.yml"

echo ""
echo -e "${CYAN}────────────────────────────────────────────${NC}"
echo -e "${GREEN}  re-shipping ${PREVIOUS}'s code as v${NEW_V}.${NC}"
echo -e "  Everyone, including those on ${CURRENT}, updates forward to it."
echo -e "  watch: ${CYAN}gh run list -w release.yml -L 1${NC}"
echo -e "${CYAN}────────────────────────────────────────────${NC}"
