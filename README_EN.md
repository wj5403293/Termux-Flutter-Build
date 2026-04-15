<p align="center">
  <img src="assets/banner.png" alt="termux-flutter-wsl" width="800"/>
</p>

<h1 align="center">Flutter for Termux ARM64</h1>

<p align="center">
  <strong>🚀 World's first complete Flutter development environment on mobile devices</strong>
</p>

<p align="center">
  <code>flutter build apk</code> ✅ | <code>flutter run</code> + Hot Reload ✅ | Native Speed ✅ | One-Click Install ✅
</p>

<p align="center">
  <a href="README.md">中文</a> | <strong>English</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Flutter-3.41.5-02569B?logo=flutter" alt="Flutter Version"/>
  <img src="https://img.shields.io/badge/Platform-ARM64-green" alt="Platform"/>
  <img src="https://img.shields.io/badge/Build-WSL-0078D6?logo=windows" alt="WSL"/>
  <img src="https://img.shields.io/badge/build_apk-✓-success" alt="Build APK"/>
  <img src="https://img.shields.io/badge/hot_reload-✓-success" alt="Hot Reload"/>
  <img src="https://img.shields.io/badge/License-GPL--3.0-blue" alt="License"/>
</p>

<p align="center">
  <em>🍴 Forked from <a href="https://github.com/mumumusuc/termux-flutter">mumumusuc/termux-flutter</a></em>
</p>

<p align="center">
  <img src="assets/demo_hot_reload.jpg" alt="Flutter running on Termux with Hot Reload" width="600"/>
</p>

<p align="center">
  <em>📱 Flutter App running on Termux with Hot Reload support!</em>
</p>

---

## ❓ Why Does This Project Exist?

**Flutter "supports arm64" ≠ "you can develop on any arm64 device"**

| What Flutter means by arm64 support | Reality |
|-------------------------------------|---------|
| arm64 **Target** | ✅ Your app can run on arm64 devices |
| arm64 **Host** | ⚠️ Only macOS (Apple Silicon), Linux (glibc) |
| Android/Termux as Host | ❌ **Never supported** |

### Why isn't Termux supported?

Flutter assumes a Linux host environment with:
- glibc (standard C library)
- Full POSIX compliance
- Standard toolchain

But **Termux is**:
- **bionic libc** (Android's C library, not glibc)
- Android sandbox + SELinux restrictions
- Different dynamic linker (`/system/bin/linker64`)

For Flutter officially: **This is not an OS they support.**

### What did we do?

```
Flutter SDK engine binaries:
bin/cache/artifacts/engine/
    ├── darwin-arm64/     ← for macOS
    ├── linux-arm64/      ← for Linux (glibc)
    └── android-arm64/    ← This is TARGET, not HOST!

❌ No Termux/bionic host version exists
```

**We cross-compiled the entire Flutter Engine from source**, specifically for Termux (Android/bionic):

- Fixed TLS alignment issues (bionic linker requirement)
- Fixed dynamic linker path
- Compiled host-side tools (dart, gen_snapshot, impellerc)
- Enabled Hot Reload and APK builds to run natively on Termux

> **In one sentence: Flutter officially supports arm64 as a target platform, but never supported Android as a development host. We filled that gap.**

---

## 📖 Introduction

This project is based on [mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter) and provides a complete solution for cross-compiling the Flutter Engine for Termux on a **WSL (Windows Subsystem for Linux)** environment.

### 🆚 Differences from Upstream

| Feature | Upstream | This Project |
|---|---|---|
| Build Env | Linux / Termux Native | **WSL (Windows)** |
| Flutter Ver | 3.29.2 | **3.41.5** |
| Android Compat | ❌ No Android 14+ | ✅ **Android 16 Tested** |
| Fixes | - | **`-llog`, `-lm` deps** |
| Docs | Basic | **Full Guide (EN/ZH)** |

> ✅ **Verified**: Successfully ran Flutter app on Android 16 device!

### 🏆 World's First Complete Flutter Dev Environment

This project is **the world's first** to achieve a **complete Flutter development workflow** on ARM64 Termux!

#### 🎯 What Can We Do?

| Feature | This Project | Other Solutions |
|---------|--------------|-----------------|
| `flutter build apk` | ✅ **Native support** | ❌ Cannot achieve |
| `flutter run` + Hot Reload | ✅ **Full support** | ❌ Cannot achieve |
| Performance | ✅ **Native speed** | ⚠️ x86 emulation, 3-5x slower |
| Installation | ✅ **One-click** | ⚠️ Complex setup |
| APK Size | ✅ **Normal (~17MB)** | ⚠️ proot adds overhead |

#### 📊 Full Feature Comparison

| Project | build apk | flutter run | hot reload | Native | Status |
|---------|-----------|-------------|------------|--------|--------|
| **This Project** | ✅ | ✅ | ✅ | ✅ | ✅ Active |
| Flutter Official | ❌ | ❌ | ❌ | ❌ | [Issue #177936](https://github.com/flutter/flutter/issues/177936): Not supported |
| [mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter) | ❌ | ⚠️ linux only | ❌ | ✅ | ⚠️ Stale |
| [Hax4us/flutter_in_termux](https://github.com/Hax4us/flutter_in_termux) | ⚠️ proot | ⚠️ proot | ❌ | ❌ x86 emu | ⚠️ Stale |
| [bdloser404/Fluttermux](https://github.com/bdloser404/Fluttermux) | ❌ | ❌ | ❌ | ❌ | ❌ Broken |

> 💡 If you find another project that natively supports this, please [open an Issue](https://github.com/ImL1s/termux-flutter-wsl/issues) to let us know!

#### 🚀 What Does This Mean?

**Complete Flutter development on your phone/tablet:**

```
📱 Your Android Device
    ↓
🖥️ Termux Terminal
    ↓
✍️ Write code (vim/nano/code-server)
    ↓
🔥 flutter run → See changes instantly (Hot Reload!)
    ↓
📦 flutter build apk → Get installable APK
    ↓
📲 Install directly on device
```

**No computer, no emulator, no cloud service needed!**

### 📊 Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| `flutter doctor` | ✅ Verified | Dart SDK runs correctly |
| `flutter create` | ✅ Verified | Can create new projects |
| `flutter run -d linux` | ✅ Verified | Requires Termux:X11 |
| `flutter build linux` | ✅ Verified | Produces ARM64 ELF executable |
| `flutter build apk` | ✅ Verified | Requires post_install.sh |
| `flutter run` (Android) | ✅ Verified | Hot reload works! Requires post_install.sh |

> ✅ **v3.41.5 Release**: All features verified! Including hot reload support!

### ✨ Features

- 🪟 Cross-compile entirely within Windows WSL
- 🔧 Fixed missing Android log symbols (`-llog`)
- 📦 Produced `flutter_3.41.5_aarch64.deb` (662MB)
- 🤖 Fully automated build scripts

### ⚠️ System Requirements

| Item | Minimum |
|------|---------|
| Android Version | **Android 11 (API 30)** or higher |
| Architecture | ARM64 (aarch64) |
| Termux | Install from [F-Droid](https://f-droid.org/packages/com.termux/) |

> ⚠️ **Important**: The `adb` in Android SDK requires Android 11+ system functions (`pthread_cond_clockwait`). On Android 10 or older devices, extra steps are required (see below).

<details>
<summary><b>🔧 ADB Fix for Android 10 or Older Devices</b></summary>

If your device is Android 10 or older, `termux-android-sdk`'s adb will show this error:
```
CANNOT LINK EXECUTABLE "adb": cannot locate symbol "pthread_cond_clockwait"
```

**Solution:** Install [MasterDevX/Termux-ADB](https://github.com/MasterDevX/Termux-ADB) and replace adb:

```bash
# 1. Install compatible adb
wget https://github.com/MasterDevX/Termux-ADB/raw/master/InstallTools.sh -q && bash InstallTools.sh

# 2. Replace Android SDK's adb with compatible version
cp $PREFIX/bin/adb.bin $PREFIX/opt/android-sdk/platform-tools/adb

# 3. Verify
flutter doctor
```

This installs adb 1.0.39 (android-8.0.0), which works on Android 9 and older devices.

</details>

---

## 🚀 Quick Start

### Complete One-Click Install (Recommended - Includes APK Build)

One command installs Flutter + Android SDK + NDK, ready to `flutter build apk`:

```bash
curl -sL https://raw.githubusercontent.com/ImL1s/termux-flutter-wsl/master/install_flutter_complete.sh -o ~/install.sh && bash ~/install.sh
```

> This script auto-installs Flutter, Android SDK, ARM64 NDK, and tests APK build.
> Total size ~1.8GB, takes 10-30 minutes.

### Flutter Only (No APK Build)

If you only need `flutter run -d linux`, no APK building:

```bash
curl -sL https://raw.githubusercontent.com/ImL1s/termux-flutter-wsl/master/install_termux_flutter.sh -o ~/install.sh && bash ~/install.sh
```

After install, **restart Termux** then run:
```bash
flutter doctor
```

> This script only installs Flutter SDK (~550MB), no Android SDK.

### Manual Install

```bash
# 1. Install dependencies
pkg update && pkg install x11-repo wget openjdk-21

# 2. Download package
wget https://github.com/ImL1s/termux-flutter-wsl/releases/download/3.41.5/flutter_3.41.5_aarch64.deb

# 3. Install
dpkg -i flutter_3.41.5_aarch64.deb
apt --fix-broken install -y

# 4. Run post-install script (configures APK build and hot reload)
bash $PREFIX/share/flutter/post_install.sh

# 5. Load environment and verify
source $PREFIX/etc/profile.d/flutter.sh
flutter doctor
```

> ⚠️ **Important**: `post_install.sh` downloads and configures:
> - Android API 34 platform
> - Official Dart SDK snapshots (required for hot reload)
> - Android cmdline-tools
> - ELF binary cleaning (fixes linker warnings)

### Build from Source (on WSL)

```bash
# Build everything
./build_termux_flutter.sh

# Or step-by-step
python3 build.py sysroot --arch=arm64    # Assemble Termux sysroot
python3 build.py configure --arch=arm64 --mode=debug
python3 build.py build --arch=arm64 --mode=debug
python3 build.py debuild --arch=arm64    # Package .deb
```

### Run Flutter App (with Termux:X11)

After installation, you need [Termux:X11](https://github.com/termux/termux-x11/releases) to display GUI apps.

**Install Termux:X11**: Download APK from [GitHub Releases](https://github.com/termux/termux-x11/releases) or [F-Droid](https://f-droid.org/packages/com.termux.x11/).

```bash
# 1. Start X11 server in Termux
export DISPLAY=:0
termux-x11 :0 >/dev/null 2>&1 &

# 2. Open Termux:X11 App (black screen is normal initially)

# 3. Create and run Flutter project
flutter create hello_termux
cd hello_termux
flutter run -d linux
```

> 💡 **Alternative**: If X11 is difficult to set up, use Web mode:
> ```bash
> flutter run -d web-server --web-port=8080
> ```
> Then open `http://localhost:8080` in browser.

### Build Android APK

To run `flutter build apk` in Termux, you need the full Android development environment.

#### Step 1: Install Dependencies

```bash
# Update packages and install JDK
pkg update
pkg install openjdk-21 git wget
```

#### Step 2: Install Android SDK

Download and install from [termux-android-sdk](https://github.com/mumumusuc/termux-android-sdk/releases):

```bash
wget https://github.com/mumumusuc/termux-android-sdk/releases/download/35.0.0/android-sdk_35.0.0_aarch64.deb
dpkg -i --force-architecture android-sdk_35.0.0_aarch64.deb
```

> ⚠️ **Note**: The `--force-architecture` flag is required because dpkg treats `aarch64` and `arm64` as different architectures.

> This package includes native ARM64 `aapt2`, `build-tools 35.0.0`, `platforms android-34/35`, and other essential tools.

#### Step 3: Configure Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export ANDROID_HOME=$PREFIX/opt/android-sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin

# Important: Do NOT set JAVA_HOME, let Gradle find Java from PATH
# If already set, unset it:
unset JAVA_HOME
```

Reload configuration:
```bash
source ~/.bashrc
```

#### Step 4: Configure Flutter

```bash
# Set Android SDK path
flutter config --android-sdk $ANDROID_HOME

# Accept Android licenses
flutter doctor --android-licenses

# Check environment
flutter doctor
```

#### Step 5: Install ARM64 NDK (Critical Step)

The official Android NDK only provides x86_64 Linux host binaries, which cannot run on ARM64 Termux. You need to install a third-party prebuilt ARM64 NDK:

```bash
# Download ARM64 NDK (~538MB)
cd ~
wget https://github.com/lzhiyong/termux-ndk/releases/download/android-ndk/android-ndk-r27b-aarch64.zip

# Extract to Android SDK's NDK directory
mkdir -p $ANDROID_HOME/ndk
unzip android-ndk-r27b-aarch64.zip -d $ANDROID_HOME/ndk/

# Rename to standard version number (required by Flutter)
mv $ANDROID_HOME/ndk/android-ndk-r27b $ANDROID_HOME/ndk/27.1.12297006

# Verify installation
ls $ANDROID_HOME/ndk/27.1.12297006/toolchains/llvm/prebuilt/linux-aarch64/bin/clang
```

> ✅ **Verified**: The ARM64 NDK contains a complete `linux-aarch64` toolchain with clang 18.0.2.

> 💡 **Source**: [lzhiyong/termux-ndk](https://github.com/lzhiyong/termux-ndk) - Provides prebuilt ARM64 Android NDK.

#### Step 6: Fix x86_64 CMake

Android SDK's CMake is x86_64, cannot run on ARM64 Termux. Replace with Termux cmake:

```bash
# Install Termux cmake and ninja
pkg install cmake ninja

# Replace SDK CMake (adjust version as needed)
CMAKE_VER=$(ls $ANDROID_HOME/cmake | head -1)
rm -rf $ANDROID_HOME/cmake/$CMAKE_VER/bin
mkdir -p $ANDROID_HOME/cmake/$CMAKE_VER/bin
ln -s $PREFIX/bin/cmake $ANDROID_HOME/cmake/$CMAKE_VER/bin/cmake
ln -s $PREFIX/bin/ninja $ANDROID_HOME/cmake/$CMAKE_VER/bin/ninja
```

#### Step 7: Fix AAPT2

Gradle downloads x86_64 AAPT2. Use the ARM64 version from SDK build-tools:

```bash
# Find Gradle's cached aapt2
AAPT2_CACHE=$(find ~/.gradle/caches -name "aapt2" -type f 2>/dev/null | head -1)

if [ -n "$AAPT2_CACHE" ]; then
    # Replace with ARM64 version
    rm -f "$AAPT2_CACHE"
    ln -s $ANDROID_HOME/build-tools/35.0.0/aapt2 "$AAPT2_CACHE"
    echo "AAPT2 replaced with ARM64 version"
fi
```

> **Note**: Gradle downloads AAPT2 on first build. Run this step after the first build fails.

#### Step 8: Copy flutter_patched_sdk_product

`flutter build apk --release` requires the product SDK:

```bash
FLUTTER_ROOT=$PREFIX/opt/flutter
mkdir -p $FLUTTER_ROOT/bin/cache/artifacts/engine/common/flutter_patched_sdk_product
cp -r $FLUTTER_ROOT/bin/cache/artifacts/engine/common/flutter_patched_sdk/* \
      $FLUTTER_ROOT/bin/cache/artifacts/engine/common/flutter_patched_sdk_product/
```

#### Step 9: Configure Gradle (Important)

**Option A: Use One-Click Configuration Script (Recommended)**

```bash
# Run in your project directory
curl -sL https://raw.githubusercontent.com/ImL1s/termux-flutter-wsl/master/setup_flutter_project.sh | bash
```

**Option B: Manual Configuration**

Add required settings to your project's `android/gradle.properties`:

```bash
cat >> android/gradle.properties << 'EOF'
android.useAndroidX=true
android.enableJetifier=true
android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/bin/aapt2
org.gradle.jvmargs=-Xmx768m -XX:MaxMetaspaceSize=384m
EOF
```

Also specify the NDK version in `android/app/build.gradle.kts`:

```kotlin
android {
    ndkVersion = "27.1.12297006"
    // ... other settings
}
```

#### Step 10: Build APK

```bash
# Create project
flutter create myapp
cd myapp

# Configure NDK version in android/app/build.gradle.kts
# Add: ndkVersion = "27.1.12297006"

# Build Release APK (no extra flags needed!)
flutter build apk --release

# Build Debug APK
flutter build apk --debug
```

> ✨ **No `--target-platform` flag needed!**
>
> We have patched the Flutter SDK defaults to only build `android-arm64` architecture.
> This is because gen_snapshot for android-arm and android-x64 cannot be cross-compiled on ARM64 hosts.
>
> 💡 **Impact**: The output APK will only run on ARM64 devices. Most modern Android devices (2019+) are ARM64.

<details>
<summary><b>📝 Technical Limitation Analysis (Tested 2025-12-28)</b></summary>

We attempted to compile gen_snapshot for android-arm and android-x64:

| Target | Result | Error Reason |
|--------|--------|--------------|
| android-arm64 | ✅ Success | Host=ARM64, Target=ARM64, same architecture |
| android-arm | ❌ Failed | BoringSSL has 32-bit shift overflow errors (`r0 << 63` on 32-bit type) |
| android-x64 | ❌ Failed | ARM64 sysroot headers incompatible with x64 compilation |

**Root cause**: Flutter Engine's GN build system assumes host and target are compatible architectures. When we need:
- Host = ARM64 (where gen_snapshot runs)
- Target = ARM32 or x64 (what code gen_snapshot produces)

The build system cannot properly separate host toolchain from target compilation, causing dependency libraries to be compiled with wrong architecture settings.

This is one of the reasons why Flutter officially doesn't support ARM64 hosts.

</details>

> ✅ **Verified**: With the above configuration, `flutter build apk --release` runs successfully on Termux!
>
> Example output:
> ```
> Running Gradle task 'assembleRelease'...                          312.5s
> ✓ Built build/app/outputs/flutter-apk/app-release.apk (17.2MB)
> ```

### Run Flutter App Locally (Hot Reload)

Run Flutter app directly in Termux with hot reload support:

```bash
# 1. Enable Wireless Debugging
#    Settings → Developer Options → Wireless Debugging → ON

# 2. Pair device (first time only)
#    Tap "Pair device with pairing code", note the code and port
adb pair 127.0.0.1:<pairing_port>
# Enter pairing code

# 3. Connect device
adb connect 127.0.0.1:<connect_port>

# 4. Run Flutter app
cd your_flutter_project
flutter run
```

> 💡 When connected, you'll see:
> ```
> Flutter run key commands.
> r Hot reload. 🔥🔥🔥
> R Hot restart.
> ```

### Deploy to Android Device

#### Connect ADB Device

**Method A: Wireless ADB (Same Phone)**

1. Enable "Developer Options" → "Wireless Debugging" on your phone
2. Tap "Pair device with pairing code", note the pairing code and port

```bash
# Pair (only once)
adb pair 127.0.0.1:<pairing_port>
# Enter pairing code

# Connect
adb connect 127.0.0.1:<connect_port>
```

**Method B: Connect to Other Devices**

```bash
# Ensure target device has USB debugging or wireless debugging enabled
adb connect <device_ip>:5555
```

#### Run App

```bash
# List connected devices
flutter devices

# Deploy to Android device
flutter run -d <device_id>

# Or install APK directly
adb install build/app/outputs/flutter-apk/app-release.apk
```

> ⚠️ **Note**: `flutter devices` only shows `linux` by default. Install `termux-android-sdk` to see Android device options.

---

## 📁 Directory Structure

```
termux-flutter-wsl/
├── build.py                  # Main build script
├── build.toml                # Configuration
├── patches/                  # Engine patches
├── build_termux_flutter.sh   # One-click build (WSL)
├── install_termux_flutter.sh # Termux one-click installer
├── setup_flutter_project.sh  # Project configuration script
├── README.md                 # Chinese docs
├── README_EN.md              # English docs
├── assets/                   # Assets
└── .agent/workflows/         # Automation
```

---

## 🔧 Technical Details

### Build Requirements

| Item | Version/Config |
|---|---|
| Host OS | Windows 11 + WSL (Ubuntu 22.04+) |
| Target | ARM64 Android (Termux) |
| NDK | r27d (API 35) |
| Python | 3.10+ |

### Key Fixes

We applied the following fixes to ensure WSL compatibility:

```gn
# build/config/termux/BUILD.gn - runtime_library
ldflags = [
  "-stdlib=libstdc++",
  "-Wl,--warn-shared-textrel",
  "-llog",   # Added: Android logging lib
  "-lm",     # Added: Math lib
]
```

### Android gen_snapshot Cross-Compilation

To support `flutter build apk --release` (AOT compilation) on Termux, we cross-compiled a specialized gen_snapshot:

```bash
# Build in WSL (for developers)
python3 build.py configure_android --arch=arm64 --mode=release
python3 build.py build_android_gen_snapshot --arch=arm64 --mode=release
```

This gen_snapshot:
- **Runs on** ARM64 Termux
- **Produces** Android ARM64 AOT machine code
- **Included** in the `flutter_3.41.5_aarch64.deb` package

> ✅ **Verified**: gen_snapshot runs successfully on Termux:
> ```
> $ gen_snapshot --version
> Dart SDK version: 3.9.0 on "android_arm64"
> ```

**Technical Note**: The official Flutter SDK's gen_snapshot only runs on x86_64 Linux. We used NDK to cross-compile a version that runs natively on ARM64 Android (Termux), which is essential for `flutter build apk`.

---

## 📋 Upgrading

1. Update `tag` in `build.toml`.
2. Sync and patch:
   ```bash
   python3 build.py clone
   python3 build.py sync
   python3 build.py patch_engine  # Update patches if needed
   ```
3. Run the full build process.

---

## 🔄 Sync with Upstream

This project is a fork of [mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter). To sync updates:

```bash
git remote add upstream https://github.com/mumumusuc/termux-flutter.git
git fetch upstream
git merge upstream/main
```

**Note**: Merge conflicts may occur because we customized build scripts for WSL support. Please resolve conflicts manually.

---

## 🙏 Acknowledgements

- [mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter) - Original build tools
- [lzhiyong/termux-ndk](https://github.com/lzhiyong/termux-ndk) - Prebuilt ARM64 Android NDK
- [Flutter](https://flutter.dev/) - Google's UI Toolkit
- [Termux](https://termux.com/) - Android Terminal Emulator

---

## 📄 License

Based on [mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter), licensed under **GPL-3.0**.

See [LICENSE](LICENSE) for details.
