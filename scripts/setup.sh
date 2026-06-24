#!/bin/bash
# thinkstack: full environment bootstrap
# installs all system dependencies, language toolchains, and project packages.
# a new developer clones the repo, runs this once, and is ready to build.
# usage: ./scripts/setup.sh
set -e

echo "----------------------------------------"
echo "thinkstack: setup"
echo "----------------------------------------"

# -- detect package manager --
if command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
elif command -v apt-get &>/dev/null; then
    PKG_MGR="apt-get"
elif command -v pacman &>/dev/null; then
    PKG_MGR="pacman"
else
    echo "error: unsupported package manager. install dependencies manually."
    exit 1
fi
echo "detected package manager: ${PKG_MGR}"

# -- system dependencies for tauri --
echo "[1/5] system dependencies (tauri prerequisites)"
case "$PKG_MGR" in
    dnf)
        sudo dnf install -y \
            webkit2gtk4.1-devel \
            openssl-devel \
            curl \
            wget \
            file \
            libappindicator-gtk3-devel \
            librsvg2-devel \
            pango-devel \
            gcc \
            gcc-c++ \
            make \
            2>/dev/null || echo "  some packages may already be installed"
        ;;
    apt-get)
        sudo apt-get update -qq
        sudo apt-get install -y \
            libwebkit2gtk-4.1-dev \
            libssl-dev \
            curl \
            wget \
            file \
            libayatana-appindicator3-dev \
            librsvg2-dev \
            libpango1.0-dev \
            build-essential \
            2>/dev/null || echo "  some packages may already be installed"
        ;;
    pacman)
        sudo pacman -S --needed --noconfirm \
            webkit2gtk-4.1 \
            openssl \
            curl \
            wget \
            file \
            libappindicator-gtk3 \
            librsvg \
            pango \
            base-devel \
            2>/dev/null || echo "  some packages may already be installed"
        ;;
esac
echo "  system dependencies installed"

# -- rust toolchain --
echo "[2/5] rust toolchain"
if command -v rustc &>/dev/null; then
    echo "  rust already installed: $(rustc --version)"
else
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    echo "  rust installed: $(rustc --version)"
fi

# -- python virtual environment --
echo "[3/5] python virtual environment"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  created .venv"
else
    echo "  .venv already exists"
fi
source .venv/bin/activate
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller
echo "  python dependencies installed"

# -- node / frontend dependencies --
echo "[4/5] frontend dependencies"
if [ -f "package.json" ]; then
    npm install --silent
    echo "  node modules installed"
else
    echo "  no package.json found, skipping"
fi

# -- tectonic (latex compiler) --
echo "[5/5] tectonic latex compiler"
if command -v tectonic &>/dev/null; then
    echo "  tectonic already installed: $(tectonic --version)"
else
    case "$PKG_MGR" in
        dnf)    sudo dnf install -y tectonic 2>/dev/null || echo "  tectonic not in repos, install manually: https://tectonic-typesetting.github.io" ;;
        apt-get) sudo apt-get install -y tectonic 2>/dev/null || echo "  tectonic not in repos, install manually: https://tectonic-typesetting.github.io" ;;
        pacman) sudo pacman -S --needed --noconfirm tectonic 2>/dev/null || echo "  tectonic not in repos, install manually: https://tectonic-typesetting.github.io" ;;
    esac
fi

echo "----------------------------------------"
echo "setup complete."
echo "  development:  ./scripts/dev.sh"
echo "  validation:   ./scripts/validate.sh"
echo "  production:   ./scripts/build.sh"
echo "----------------------------------------"
