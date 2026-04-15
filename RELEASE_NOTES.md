# Flutter 3.41.5 for Termux (ARM64)

**世界首個在 Termux ARM64 上運行的完整 Flutter 開發環境**

## 安裝

### 方法 1: 一鍵安裝（推薦）
```bash
curl -sL https://raw.githubusercontent.com/ImL1s/termux-flutter-wsl/master/install_flutter_complete.sh -o ~/install.sh && bash ~/install.sh
```

### 方法 2: 只安裝 Flutter（不含 Android SDK）
```bash
curl -sL https://raw.githubusercontent.com/ImL1s/termux-flutter-wsl/master/scripts/install/install_termux_flutter.sh -o ~/install.sh && bash ~/install.sh
```

### 方法 3: 手動安裝
```bash
# 1. 下載並安裝 deb
wget https://github.com/ImL1s/termux-flutter-wsl/releases/download/v3.41.5/flutter_3.41.5_aarch64.deb
dpkg -i flutter_3.41.5_aarch64.deb
apt --fix-broken install -y

# 2. 執行 post-install 腳本
bash $PREFIX/share/flutter/post_install.sh

# 3. 設置環境變數
source $PREFIX/etc/profile.d/flutter.sh

# 4. 驗證安裝
flutter doctor
```

## 功能狀態

| 功能 | 狀態 | 備註 |
|------|------|------|
| `flutter doctor` | ✅ 已驗證 | |
| `flutter create` | ✅ 已驗證 | |
| `flutter build apk --release` | ✅ 已驗證 | 151.6MB |
| `flutter build apk --debug` | ✅ 已驗證 | |
| `flutter build linux --release` | ✅ 已驗證 | ARM64 ELF |
| `flutter run` (Android) | ✅ 已驗證 | Hot Reload 支援 |

## 系統需求

- Android 11+ (API 30+)
- ARM64 (aarch64) 架構
- Termux 從 [F-Droid](https://f-droid.org/packages/com.termux/) 安裝
- 約 2GB 儲存空間

## APK 構建配置

每個 Flutter 專案需要修改以下配置：

**android/app/build.gradle.kts:**
```kotlin
android {
    compileSdk = 34
    defaultConfig {
        targetSdk = 34
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }
}
```

**android/gradle.properties:**
```properties
android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/bin/aapt2
```

## Linux Desktop 構建

在 `linux/CMakeLists.txt` 第一行加入：
```cmake
set(CMAKE_SYSTEM_NAME Linux)
```

然後執行：
```bash
flutter build linux --release
```

## flutter run（Hot Reload）

```bash
# 1. 啟用無線調試（設定 → 開發者選項 → 無線調試）
# 2. 配對（首次）
adb pair 127.0.0.1:<配對端口> <配對碼>
# 3. 連接
adb connect 127.0.0.1:<連接端口>
# 4. 運行
flutter run
```

## 已知限制

- 僅支援 `android-arm64` 目標（不支援 android-arm、android-x64）
- 需要手動執行 post_install.sh 配置環境

## 更新內容

### v3.41.5 (2026-04-13)
- Flutter SDK 升級至 3.41.5 (Dart 3.11.3)
- **新增 `flutter build linux` 支援**（post_install.sh 自動 patch）
- 修復 `post_install.sh` sed 分隔符衝突
- 修復 `build.py` sync 目錄複製問題
- 強制刪除 flutter_tools.stamp/snapshot 確保 patch 生效
- E2E 測試腳本 `gh_e2e_test.sh`

### v3.35.0 (2026-01-07)
- 首次公開發布
- 完整支援 APK 構建（debug/profile/release）
- `flutter run` + Hot Reload 支援

## 致謝

- [mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter) - 原始構建工具
- [lzhiyong/termux-ndk](https://github.com/lzhiyong/termux-ndk) - ARM64 預編譯 Android NDK
