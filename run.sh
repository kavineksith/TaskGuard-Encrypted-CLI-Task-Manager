#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# TaskGuard — bootstrap and run script
# Usage:
#   ./run.sh              Launch the interactive shell
#   ./run.sh test         Run the full test suite
#   ./run.sh <args>       Pass arguments directly to main.py
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQUIRED_PYTHON="3.12"
APP_NAME="TaskGuard"

# ── ANSI helpers ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERR]${RESET}   $*" >&2; exit 1; }

# ── Python version check ──────────────────────────────────────────────────────
check_python() {
    local py
    py=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
    if [[ -z "$py" ]]; then
        error "Python 3 not found. Install Python ${REQUIRED_PYTHON}+."
    fi
    local ver
    ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local major minor req_major req_minor
    IFS='.' read -r major minor <<< "$ver"
    IFS='.' read -r req_major req_minor <<< "$REQUIRED_PYTHON"
    if (( major < req_major )) || { (( major == req_major )) && (( minor < req_minor )); }; then
        error "Python ${REQUIRED_PYTHON}+ required. Found: ${ver}"
    fi
    echo "$py"
}

# ── virtual environment ───────────────────────────────────────────────────────
setup_venv() {
    local py="$1"
    if [[ ! -d "$VENV_DIR" ]]; then
        info "Creating virtual environment at ${VENV_DIR}..."
        "$py" -m venv "$VENV_DIR"
        success "Virtual environment created."
    fi
}

activate_venv() {
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
}

install_deps() {
    local req="${SCRIPT_DIR}/requirements.txt"
    if [[ ! -f "$req" ]]; then
        error "requirements.txt not found."
    fi
    info "Installing dependencies..."
    pip install --quiet --upgrade pip
    pip install --quiet -r "$req"
    success "Dependencies installed."
}

deps_installed() {
    python -c "import aiosqlite, cryptography, argon2" 2>/dev/null
}

# ── banner ────────────────────────────────────────────────────────────────────
print_header() {
    echo -e "${BOLD}${CYAN}"
    echo "  ╔══════════════════════════════════╗"
    echo "  ║   ${APP_NAME} v1.0.0               ║"
    echo "  ║   Encrypted CLI Task Manager     ║"
    echo "  ╚══════════════════════════════════╝"
    echo -e "${RESET}"
}

# ── main ──────────────────────────────────────────────────────────────────────
main() {
    print_header
    local py
    py=$(check_python)
    success "Python $(${py} --version 2>&1 | awk '{print $2}') detected."

    setup_venv "$py"
    activate_venv

    if ! deps_installed; then
        install_deps
    fi

    cd "$SCRIPT_DIR"

    if [[ "${1:-}" == "test" ]]; then
        info "Running test suite..."
        python -m pytest tests/ -v --tb=short
        success "All tests complete."
    else
        info "Starting ${APP_NAME}..."
        python main.py "$@"
    fi
}

main "$@"
