#!/bin/bash
set -euo pipefail

# lineage-to-graph スキルインストーラー
# 使用方法: bash scripts/install-skills.sh [--global | --local <project-dir>]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_SRC="$REPO_DIR/.claude/skills"

SKILL_NAMES=(lineage-core lineage-create lineage-to-code code-to-lineage)

usage() {
    echo "Usage: $0 [--global | --local <project-dir>]"
    echo ""
    echo "Options:"
    echo "  --global              Install to ~/.claude/skills/ (available in all projects)"
    echo "  --local <project-dir> Install to <project-dir>/.claude/skills/ (project only)"
    echo ""
    echo "Examples:"
    echo "  $0 --global"
    echo "  $0 --local /path/to/my-project"
    echo ""
    echo "If no option is specified, you will be prompted to choose."
}

check_dependencies() {
    echo "Checking dependencies..."
    echo ""

    local has_error=false

    # Python
    if command -v python3 &>/dev/null; then
        echo "  [OK] python3 $(python3 --version 2>&1 | awk '{print $2}')"
    else
        echo "  [NG] python3 not found. Please install Python 3.8+"
        has_error=true
    fi

    # PyYAML
    if python3 -c "import yaml" 2>/dev/null; then
        echo "  [OK] PyYAML"
    else
        echo "  [..] PyYAML not found. Installing..."
        if pip3 install PyYAML; then
            echo "  [OK] PyYAML installed"
        else
            echo "  [NG] Failed to install PyYAML. Run: pip3 install PyYAML"
            has_error=true
        fi
    fi

    # md-mermaid-lint (optional)
    if command -v npx &>/dev/null && npx md-mermaid-lint --help &>/dev/null; then
        echo "  [OK] md-mermaid-lint"
    else
        echo "  [--] md-mermaid-lint not available (optional, requires Node.js + npm)"
    fi

    echo ""

    if [ "$has_error" = true ]; then
        echo "Some dependencies are missing. Please fix them before using the skills."
        echo ""
    fi
}

install_skills() {
    local dest="$1"
    local label="$2"

    mkdir -p "$dest"

    for skill in "${SKILL_NAMES[@]}"; do
        if [ -d "$dest/$skill" ]; then
            echo "  Updating: $skill"
            rm -rf "${dest:?}/${skill:?}"
        else
            echo "  Installing: $skill"
        fi
        cp -r "$SKILLS_SRC/$skill" "$dest/$skill"
    done

    echo ""
    echo "Installed ${#SKILL_NAMES[@]} skills to $label ($dest)"
}

main() {
    echo "lineage-to-graph Skills Installer"
    echo "================================="
    echo ""

    # Check source exists
    if [ ! -d "$SKILLS_SRC" ]; then
        echo "Error: Skills source directory not found: $SKILLS_SRC"
        exit 1
    fi

    local mode="${1:-}"

    if [ "$mode" = "--help" ] || [ "$mode" = "-h" ]; then
        usage
        exit 0
    fi

    # Check dependencies
    check_dependencies

    if [ -z "$mode" ]; then
        echo "Where would you like to install the skills?"
        echo ""
        echo "  1) Global  (~/.claude/skills/) - Available in all projects"
        echo "  2) Local   (<project-dir>/.claude/skills/) - Specific project only"
        echo ""
        read -rp "Choose [1/2]: " choice
        case "$choice" in
            1) mode="--global" ;;
            2)
                read -rp "Project directory: " project_dir
                if [ -z "$project_dir" ]; then
                    echo "Error: Project directory is required."
                    exit 1
                fi
                mode="--local"
                ;;
            *)
                echo "Invalid choice."
                exit 1
                ;;
        esac
    fi

    case "$mode" in
        --global)
            install_skills "$HOME/.claude/skills" "global"
            ;;
        --local)
            local target_dir="${project_dir:-${2:-}}"
            if [ -z "$target_dir" ]; then
                echo "Error: --local requires a project directory."
                echo ""
                usage
                exit 1
            fi
            if [ ! -d "$target_dir" ]; then
                echo "Error: Directory not found: $target_dir"
                exit 1
            fi
            # Prevent installing into the source repo itself
            local target_real
            target_real="$(cd "$target_dir" && pwd)"
            if [ "$target_real" = "$REPO_DIR" ]; then
                echo "Error: Cannot install into the lineage-to-graph repository itself."
                echo "Please specify a different project directory."
                exit 1
            fi
            install_skills "$target_real/.claude/skills" "local ($target_real)"
            ;;
        *)
            usage
            exit 1
            ;;
    esac

    echo ""
    echo "Available skills:"
    for skill in "${SKILL_NAMES[@]}"; do
        case "$skill" in
            lineage-core) echo "  - $skill (shared resources)" ;;
            *) echo "  - $skill" ;;
        esac
    done
}

main "$@"
