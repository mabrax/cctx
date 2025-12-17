#!/usr/bin/env bash
# pre-write-ctx-check.sh
# Pre-write hook for Living Context plugin
# Warns (never blocks) when writing to directories with .ctx/
#
# Usage: pre-write-ctx-check.sh <file_path>
# Output: JSON feedback format for Claude Code hooks
# Exit: Always 0 (warning only, never blocking)

set -euo pipefail

# Always exit 0 - this hook warns but never blocks
trap 'exit 0' EXIT

# Check if file path argument is provided
if [[ -z "${1:-}" ]]; then
    exit 0
fi

FILE_PATH="$1"

# Check if UV is available, exit silently if not
if ! command -v uv &>/dev/null; then
    exit 0
fi

# Function to get the directory of a file
get_dir() {
    local path="$1"
    if [[ -d "$path" ]]; then
        echo "$path"
    else
        dirname "$path"
    fi
}

# Function to check if .ctx exists in a directory
has_ctx() {
    local dir="$1"
    [[ -d "${dir}/.ctx" ]]
}

# Walk up parent directories looking for .ctx/
check_for_ctx() {
    local current_dir
    current_dir="$(get_dir "$FILE_PATH")"

    # Resolve to absolute path if relative
    if [[ "$current_dir" != /* ]]; then
        current_dir="$(cd "$current_dir" 2>/dev/null && pwd)" || exit 0
    fi

    # Walk up the directory tree
    while [[ "$current_dir" != "/" ]]; do
        if has_ctx "$current_dir"; then
            return 0  # Found .ctx
        fi
        current_dir="$(dirname "$current_dir")"
    done

    # Check root as well
    if has_ctx "/"; then
        return 0
    fi

    return 1  # No .ctx found
}

# Main logic
if check_for_ctx; then
    # Output JSON warning for Claude Code hooks
    echo '{"type": "warning", "message": "File is in a Living Context system. Run '\''uv run lctx health'\'' after changes."}'
fi

exit 0
