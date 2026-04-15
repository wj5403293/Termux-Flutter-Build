# Termux Flutter 安裝指南

本文檔說明如何在 Termux 上安裝 Flutter 並構建 Android APK。

## 系統需求

| 項目 | 需求 |
|------|------|
| Android 版本 | Android 11 (API 30) 或更高 |
| 架構 | ARM64 (aarch64) |
| Termux | 從 [F-Droid](https://f-droid.org/packages/com.termux/) 安裝 |
| 可用空間 | 至少 5GB |

## 方法一：一鍵安裝（推薦）

完整安裝 Flutter + Android SDK + NDK，安裝後可直接 `flutter build apk`：

```bash
curl -sL https://raw.githubusercontent.com/ImL1s/termux-flutter-wsl/master/install_flutter_complete.sh -o ~/install.sh && bash ~/install.sh
```

> 總大小約 1.8GB，需要 10-30 分鐘。

安裝完成後，重新啟動 Termux 或執行：
```bash
source ~/.bashrc
flutter doctor
```

## 方法二：手動安裝

### 步驟 1：安裝依賴

```bash
pkg update -y
pkg install -y x11-repo
pkg install -y openjdk-21 git wget curl unzip aapt2
```

### 步驟 2：安裝 Flutter SDK

```bash
cd ~
wget https://github.com/ImL1s/termux-flutter-wsl/releases/download/v3.41.5/flutter_3.41.5_aarch64.deb
dpkg -i flutter_3.41.5_aarch64.deb
```

### 步驟 3：安裝 Android SDK

```bash
wget https://github.com/mumumusuc/termux-android-sdk/releases/download/35.0.0/android-sdk_35.0.0_aarch64.deb
dpkg -i --force-architecture android-sdk_35.0.0_aarch64.deb
```

### 步驟 4：安裝 ARM64 NDK

```bash
cd ~
wget https://github.com/lzhiyong/termux-ndk/releases/download/android-ndk/android-ndk-r27b-aarch64.zip
mkdir -p $PREFIX/opt/android-sdk/ndk
unzip android-ndk-r27b-aarch64.zip -d $PREFIX/opt/android-sdk/ndk/
mv $PREFIX/opt/android-sdk/ndk/android-ndk-r27b $PREFIX/opt/android-sdk/ndk/27.1.12297006
```

### 步驟 5：配置環境變數

```bash
cat >> ~/.bashrc << 'EOF'
# Flutter & Android SDK
export ANDROID_HOME=$PREFIX/opt/android-sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
EOF

source ~/.bashrc
```

### 步驟 6：配置 Flutter

```bash
flutter config --android-sdk $ANDROID_HOME
flutter doctor --android-licenses
flutter doctor
```

## 構建 APK（完整步驟）

### 步驟 7：修復 x86_64 CMake 問題

Android SDK 中的 CMake 是 x86_64 版本，無法在 ARM64 Termux 運行。需要用 Termux 的 ARM64 cmake 替換：

```bash
# 安裝 Termux cmake 和 ninja
pkg install cmake ninja

# 替換 SDK CMake（根據你的 CMake 版本調整）
CMAKE_VER=$(ls $ANDROID_HOME/cmake | head -1)
rm -rf $ANDROID_HOME/cmake/$CMAKE_VER/bin
mkdir -p $ANDROID_HOME/cmake/$CMAKE_VER/bin
ln -s $PREFIX/bin/cmake $ANDROID_HOME/cmake/$CMAKE_VER/bin/cmake
ln -s $PREFIX/bin/ninja $ANDROID_HOME/cmake/$CMAKE_VER/bin/ninja
```

### 步驟 8：修復 AAPT2 問題

Gradle 下載的 AAPT2 是 x86_64 版本。使用 SDK build-tools 中的 ARM64 版本：

```bash
# 找到 Gradle 緩存的 aapt2
AAPT2_CACHE=$(find ~/.gradle/caches -name "aapt2" -type f 2>/dev/null | head -1)

if [ -n "$AAPT2_CACHE" ]; then
    # 替換為 ARM64 版本
    rm -f "$AAPT2_CACHE"
    ln -s $ANDROID_HOME/build-tools/35.0.0/aapt2 "$AAPT2_CACHE"
    echo "已替換 AAPT2 為 ARM64 版本"
fi
```

> ⚠️ **注意**：第一次構建時 Gradle 會下載 AAPT2，構建失敗後再執行此步驟替換。

### 步驟 9：複製 flutter_patched_sdk_product

`flutter build apk --release` 需要 product 版本的 SDK：

```bash
FLUTTER_ROOT=$PREFIX/opt/flutter
mkdir -p $FLUTTER_ROOT/bin/cache/artifacts/engine/common/flutter_patched_sdk_product
cp -r $FLUTTER_ROOT/bin/cache/artifacts/engine/common/flutter_patched_sdk/* \
      $FLUTTER_ROOT/bin/cache/artifacts/engine/common/flutter_patched_sdk_product/
```

### 創建新專案

```bash
flutter create myapp
cd myapp
```

### 配置專案（必須）

在 `android/app/build.gradle.kts` 中指定 NDK 版本：
```kotlin
android {
    ndkVersion = "27.1.12297006"
    // ... 其他設定
}
```

### 構建

```bash
# Release APK（只構建 ARM64，跳過不支援的架構）
flutter build apk --release --target-platform android-arm64

# Debug APK
flutter build apk --debug --target-platform android-arm64
```

> ⚠️ **重要標記說明**：
> - `--target-platform android-arm64`：只構建 ARM64，跳過 arm 和 x64（避免需要額外的 gen_snapshot）

## 驗證安裝

```bash
# 檢查 Flutter
flutter doctor

# 檢查 gen_snapshot（應顯示 android_arm64）
$PREFIX/opt/flutter/bin/cache/artifacts/engine/android-arm64-release/linux-arm64/gen_snapshot --version
```

## 常見問題

### 問題：x11-repo 未安裝
```bash
pkg install x11-repo
```

### 問題：AAPT2 錯誤 (`EM_X86_64 instead of EM_AARCH64`)
這表示 Gradle 使用了 x86_64 版本的 AAPT2。參見步驟 8 替換為 ARM64 版本：
```bash
AAPT2_CACHE=$(find ~/.gradle/caches -name "aapt2" -type f 2>/dev/null | head -1)
rm -f "$AAPT2_CACHE"
ln -s $ANDROID_HOME/build-tools/35.0.0/aapt2 "$AAPT2_CACHE"
```

### 問題：CMake 錯誤 (`unexpected e_type: 2`)
Android SDK 的 CMake 是 x86_64 版本。參見步驟 7 替換為 Termux cmake。

### 問題：gen_snapshot 版本不匹配
錯誤訊息：`Wrong full snapshot version, expected 'X' found 'Y'`
這表示 dart binary 與 snapshot 版本不匹配。確保使用我們提供的 deb 包。

### 問題：flutter_patched_sdk_product 缺失
錯誤訊息：`FileSystemException: Cannot open file`
參見步驟 9 複製 flutter_patched_sdk 到 flutter_patched_sdk_product。

### 問題：NDK 找不到
確保 NDK 安裝在正確位置：
```bash
ls $ANDROID_HOME/ndk/27.1.12297006/toolchains/llvm/prebuilt/linux-aarch64/bin/clang
```

### 問題：空間不足
清理 Gradle 緩存：
```bash
rm -rf ~/.gradle/caches
rm -rf ~/.gradle/wrapper
```

### 問題：需要 arm/x64 的 gen_snapshot
使用 `--target-platform android-arm64` 只構建 ARM64：
```bash
flutter build apk --release --target-platform android-arm64
```
