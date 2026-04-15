---
description: 為 Termux 交叉編譯 Flutter Engine 並打包成 .deb 安裝包
---

# Termux Flutter 構建流程

## 前置條件
- WSL (Ubuntu) 或 Linux 環境
- Android NDK r27d 安裝於 `/opt/android-ndk-r27d`
- Python 3.10+
- depot_tools 已配置

## 快速構建 (一鍵)
// turbo-all
```bash
cd /home/iml1s/projects/termux-flutter
python3 build.py build_all --arch=arm64
```

## 分步驟構建

### 1. 組裝 Sysroot
```bash
python3 build.py sysroot --arch=arm64
```

### 2. Linux Debug Engine (主要)
```bash
python3 build.py configure --arch=arm64 --mode=debug
python3 build.py build --arch=arm64 --mode=debug
python3 build.py build_dart --arch=arm64 --mode=debug
python3 build.py build_impellerc --arch=arm64 --mode=debug
python3 build.py build_const_finder --arch=arm64 --mode=debug
```

### 3. Linux Release Engine
```bash
python3 build.py configure --arch=arm64 --mode=release
python3 build.py build --arch=arm64 --mode=release
```

### 4. Linux Profile Engine
```bash
python3 build.py configure --arch=arm64 --mode=profile
python3 build.py build --arch=arm64 --mode=profile
```

### 5. Android gen_snapshot
```bash
python3 build.py configure_android --arch=arm64 --mode=release
python3 build.py build_android_gen_snapshot --arch=arm64 --mode=release
```

### 6. 打包 .deb
```bash
python3 build.py debuild --arch=arm64
```

## 在 Termux 上安裝與驗證

```powershell
# 推送到手機 (PowerShell, 不要用 Git Bash)
adb push flutter_3.41.5_aarch64.deb /data/local/tmp/
```

```bash
# 在 Termux 中執行
dpkg -i /data/local/tmp/flutter_3.41.5_aarch64.deb
apt-get install -f
bash $PREFIX/share/flutter/post_install.sh
source $PREFIX/etc/profile.d/flutter.sh

# 驗證
flutter --version
flutter create test_app && cd test_app

# Build Matrix 驗證 (6/6)
flutter build linux --debug
flutter build linux --release
flutter build linux --profile
flutter build apk --debug --target-platform android-arm64
flutter build apk --release --target-platform android-arm64
flutter build apk --profile --target-platform android-arm64
```

## ⚠️ 關鍵注意事項

1. `utils.py __MODE__` 必須是 `('debug', 'release', 'profile')` — debug 在前！
   - `Output.any` 取第一個存在的目錄
   - 如果 release 在前，dart-sdk snapshots 會用 product mode → 整個 flutter CLI 壞掉

2. `ninja flutter` **不會** build dart binary — 必須另外跑 `build_dart()`

3. 只支援 ARM64 APK — android-arm/android-x64 gen_snapshot 無法交叉編譯

## 升級到新版本

1. 修改 `build.toml` 中的 `tag = '新版本號'`
2. 執行 `python3 build.py clone`
3. 執行 `python3 build.py sync`
4. 如果補丁失敗，需手動更新 `patches/*.patch`
5. 執行完整構建流程
