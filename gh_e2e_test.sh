#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Termux Flutter 3.41.5 — GitHub Clean Install E2E Test
# 模擬使用者從零開始安裝 + 完整功能測試
# ============================================================
set -e

export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH
export HOME=/data/data/com.termux/files/home
export TMPDIR=$PREFIX/tmp
export LD_LIBRARY_PATH=$PREFIX/lib
export FLUTTER_VERSION=3.41.5

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ PASS: $1${NC}"; }
fail() { echo -e "${RED}❌ FAIL: $1${NC}"; FAILED=1; }
FAILED=0

echo "╔═══════════════════════════════════════════╗"
echo "║  Termux Flutter E2E Clean Install Test    ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# =========================
# Step 0: Clean previous install
# =========================
echo "=== [0/8] Cleaning previous installation ==="
dpkg -r flutter 2>/dev/null || true
rm -rf $PREFIX/opt/flutter 2>/dev/null || true
rm -rf $HOME/gh_e2e_test 2>/dev/null || true
rm -f $HOME/flutter_${FLUTTER_VERSION}_aarch64.deb 2>/dev/null || true

# =========================
# Step 0.5: Install prerequisites
# =========================
echo "=== [0.5/8] Installing prerequisites ==="
pkg update -y > /dev/null 2>&1 || true
pkg install -y wget > /dev/null 2>&1 || true

# =========================
# Step 1: Download from GitHub Release
# =========================
echo ""
echo "=== [1/8] Downloading from GitHub Release ==="
DEB_URL="https://github.com/ImL1s/termux-flutter-wsl/releases/download/v${FLUTTER_VERSION}/flutter_${FLUTTER_VERSION}_aarch64.deb"
cd $HOME
wget -q --show-progress "$DEB_URL" -O "flutter_${FLUTTER_VERSION}_aarch64.deb"
ls -lh "flutter_${FLUTTER_VERSION}_aarch64.deb"
pass "Downloaded .deb from GitHub"

# =========================
# Step 2: Install .deb
# =========================
echo ""
echo "=== [2/8] Installing .deb ==="
dpkg -i "flutter_${FLUTTER_VERSION}_aarch64.deb" || true
apt --fix-broken install -y 2>/dev/null || true

if [ -f "$PREFIX/opt/flutter/bin/flutter" ]; then
    pass "Flutter binary installed"
else
    fail "Flutter binary not found"
    exit 1
fi

# =========================
# Step 3: Run post_install.sh
# =========================
echo ""
echo "=== [3/8] Running post_install.sh ==="
bash $PREFIX/share/flutter/post_install.sh 2>&1 | tail -20
pass "post_install.sh completed"

# =========================
# Step 4: Setup environment
# =========================
echo ""
echo "=== [4/8] Setting up environment ==="
source $PREFIX/etc/profile.d/flutter.sh 2>/dev/null || true
export PATH=$PREFIX/opt/flutter/bin:$PATH
export ANDROID_HOME=$PREFIX/opt/android-sdk
export JAVA_HOME=$(find $PREFIX/lib/jvm -maxdepth 1 -type d -name 'java-*-openjdk' | sort -V | tail -1)

flutter --version 2>&1 | head -3
if flutter --version 2>&1 | grep -q "3.41.5"; then
    pass "Flutter 3.41.5 active"
else
    fail "Wrong Flutter version"
fi

# =========================
# Step 5: flutter create
# =========================
echo ""
echo "=== [5/8] flutter create ==="
cd $HOME
flutter create gh_e2e_test 2>&1 | tail -5
if [ -f "$HOME/gh_e2e_test/lib/main.dart" ]; then
    pass "flutter create succeeded"
else
    fail "flutter create failed"
fi

# =========================
# Step 6: Configure project & build APK
# =========================
echo ""
echo "=== [6/8] flutter build apk --release ==="
cd $HOME/gh_e2e_test

# Per-project config
sed -i '1s|#!/usr/bin/env bash|#!/data/data/com.termux/files/usr/bin/bash|' android/gradlew
# compileSdk & targetSdk = 34
sed -i 's/compileSdk = flutter.compileSdkVersion.toInteger()/compileSdk = 34/' android/app/build.gradle.kts 2>/dev/null || true
sed -i 's/targetSdk = flutter.targetSdkVersion.toInteger()/targetSdk = 34/' android/app/build.gradle.kts 2>/dev/null || true
# AAPT2 override
echo "android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/bin/aapt2" >> android/gradle.properties
# ARM64 only
sed -i '/defaultConfig {/a\\        ndk { abiFilters += listOf("arm64-v8a") }' android/app/build.gradle.kts 2>/dev/null || true

flutter build apk --release --target-platform android-arm64 2>&1 | tail -5
APK=$(find build -name "*.apk" -type f 2>/dev/null | head -1)
if [ -n "$APK" ]; then
    ls -lh "$APK"
    pass "APK build succeeded"
else
    fail "APK build failed"
fi

# =========================
# Step 7: flutter build linux
# =========================
echo ""
echo "=== [7/8] flutter build linux --release ==="
# Add CMAKE_SYSTEM_NAME
if ! grep -q 'CMAKE_SYSTEM_NAME' linux/CMakeLists.txt 2>/dev/null; then
    sed -i '1i set(CMAKE_SYSTEM_NAME Linux)' linux/CMakeLists.txt
fi
flutter build linux --release 2>&1 | tail -5
LINUX_BIN="build/linux/arm64/release/bundle/gh_e2e_test"
if [ -f "$LINUX_BIN" ]; then
    file "$LINUX_BIN"
    pass "Linux build succeeded"
else
    fail "Linux build failed"
fi

# =========================
# Step 8: Install & launch APK
# =========================
echo ""
echo "=== [8/8] Install and launch APK ==="
if [ -n "$APK" ]; then
    cp "$APK" /data/local/tmp/app-release.apk
    chmod 644 /data/local/tmp/app-release.apk
    pm install /data/local/tmp/app-release.apk 2>&1 && pass "APK installed" || fail "APK install failed"
    am start -n com.example.gh_e2e_test/.MainActivity 2>&1 && pass "App launched" || fail "App launch failed"
else
    fail "No APK to install"
fi

# =========================
# Summary
# =========================
echo ""
echo "╔═══════════════════════════════════════════╗"
if [ "$FAILED" == "0" ]; then
    echo "║  🎉 ALL TESTS PASSED                     ║"
else
    echo "║  ⚠️  SOME TESTS FAILED                   ║"
fi
echo "╚═══════════════════════════════════════════╝"
echo ""

# Cleanup
rm -f $HOME/flutter_${FLUTTER_VERSION}_aarch64.deb 2>/dev/null
