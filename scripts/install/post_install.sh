#!/bin/bash
# Flutter Termux 安装后配置脚本
# 安装 deb 包后执行此脚本以完成 APK 构建环境配置

set -e

echo "=========================================="
echo "Flutter Termux 安装后配置"
echo "=========================================="

# 路径定义
FLUTTER_ROOT=/data/data/com.termux/files/usr/opt/flutter
ANDROID_SDK=/data/data/com.termux/files/usr/opt/android-sdk
DART_SDK=$FLUTTER_ROOT/bin/cache/dart-sdk

# 创建 NDK clang 包装器函数
setup_ndk_clang_wrappers() {
    local NDK_PATH="$1"
    local NDK_NAME=$(basename "$NDK_PATH")

    if [ ! -d "$NDK_PATH/toolchains/llvm" ]; then
        echo "    ⚠ 跳过 $NDK_NAME (没有 toolchains/llvm 目录)"
        return
    fi

    echo "    正在为 NDK $NDK_NAME 创建 clang 包装器..."

    # 创建包装器脚本
CLANG_WRAPPER="#!/data/data/com.termux/files/usr/bin/sh
NDK=$NDK_PATH
SYSROOT=\$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot
CLANG_VERSION=\$(ls -1 \$NDK/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/ | tail -n 1)
CLANG_LIB=\$NDK/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/\$CLANG_VERSION/lib/linux

ARCH=\"\"
for arg in \"\$@\"; do
    case \"\$arg\" in
        --target=aarch64*) ARCH=\"aarch64\" ;;
        --target=arm*) ARCH=\"arm\" ;;
    esac
done

if [ \"\$ARCH\" = \"aarch64\" ]; then
    LIB_PATH=\$SYSROOT/usr/lib/aarch64-linux-android
    CLANG_LIB_ARCH=\$CLANG_LIB/aarch64
elif [ \"\$ARCH\" = \"arm\" ]; then
    LIB_PATH=\$SYSROOT/usr/lib/arm-linux-androideabi
    CLANG_LIB_ARCH=\$CLANG_LIB/arm
else
    exec /data/data/com.termux/files/usr/bin/clang \"\$@\"
fi

exec /data/data/com.termux/files/usr/bin/clang -L\$LIB_PATH -L\$CLANG_LIB_ARCH \"\$@\""

CLANGPP_WRAPPER="#!/data/data/com.termux/files/usr/bin/sh
NDK=$NDK_PATH
SYSROOT=\$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot
CLANG_VERSION=\$(ls -1 \$NDK/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/ | tail -n 1)
CLANG_LIB=\$NDK/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/\$CLANG_VERSION/lib/linux

ARCH=\"\"
for arg in \"\$@\"; do
    case \"\$arg\" in
        --target=aarch64*) ARCH=\"aarch64\" ;;
        --target=arm*) ARCH=\"arm\" ;;
    esac
done

if [ \"\$ARCH\" = \"aarch64\" ]; then
    LIB_PATH=\$SYSROOT/usr/lib/aarch64-linux-android
    CLANG_LIB_ARCH=\$CLANG_LIB/aarch64
elif [ \"\$ARCH\" = \"arm\" ]; then
    LIB_PATH=\$SYSROOT/usr/lib/arm-linux-androideabi
    CLANG_LIB_ARCH=\$CLANG_LIB/arm
else
    exec /data/data/com.termux/files/usr/bin/clang++ \"\$@\"
fi

exec /data/data/com.termux/files/usr/bin/clang++ -L\$LIB_PATH -L\$CLANG_LIB_ARCH \"\$@\""

    # 在 prebuilt/bin/ 中创建包装器
    local PREBUILT="$NDK_PATH/toolchains/llvm/prebuilt"
    mkdir -p "$PREBUILT/bin"
    echo "$CLANG_WRAPPER" > "$PREBUILT/bin/clang"
    chmod +x "$PREBUILT/bin/clang"
    echo "$CLANGPP_WRAPPER" > "$PREBUILT/bin/clang++"
    chmod +x "$PREBUILT/bin/clang++"

    # 在 prebuilt/linux-x86_64/bin/ 中创建包装器
    mkdir -p "$PREBUILT/linux-x86_64/bin"
    for f in clang clang++; do
        if [ -L "$PREBUILT/linux-x86_64/bin/$f" ] || [ -f "$PREBUILT/linux-x86_64/bin/$f" ]; then
            unlink "$PREBUILT/linux-x86_64/bin/$f" 2>/dev/null || rm "$PREBUILT/linux-x86_64/bin/$f" 2>/dev/null || true
        fi
    done
    echo "$CLANG_WRAPPER" > "$PREBUILT/linux-x86_64/bin/clang"
    chmod +x "$PREBUILT/linux-x86_64/bin/clang"
    echo "$CLANGPP_WRAPPER" > "$PREBUILT/linux-x86_64/bin/clang++"
    chmod +x "$PREBUILT/linux-x86_64/bin/clang++"

    # 创建 linux-aarch64 目录
    rm -rf "$PREBUILT/linux-aarch64" 2>/dev/null || true
    mkdir -p "$PREBUILT/linux-aarch64/bin"
    cp "$PREBUILT/bin/clang" "$PREBUILT/linux-aarch64/bin/clang"
    cp "$PREBUILT/bin/clang++" "$PREBUILT/linux-aarch64/bin/clang++"

    # 创建所有 API 级别的 clang 包装器
    for api in 21 24 26 28 29 30 31 32 33 34 35; do
        ln -sf clang "$PREBUILT/linux-aarch64/bin/armv7a-linux-androideabi${api}-clang"
        ln -sf clang++ "$PREBUILT/linux-aarch64/bin/armv7a-linux-androideabi${api}-clang++"
        ln -sf clang "$PREBUILT/linux-aarch64/bin/aarch64-linux-android${api}-clang"
        ln -sf clang++ "$PREBUILT/linux-aarch64/bin/aarch64-linux-android${api}-clang++"
        ln -sf clang "$PREBUILT/linux-aarch64/bin/i686-linux-android${api}-clang"
        ln -sf clang++ "$PREBUILT/linux-aarch64/bin/i686-linux-android${api}-clang++"
        ln -sf clang "$PREBUILT/linux-aarch64/bin/x86_64-linux-android${api}-clang"
        ln -sf clang++ "$PREBUILT/linux-aarch64/bin/x86_64-linux-android${api}-clang++"
    done

    # 创建 sysroot 符号链接
    ln -sf linux-x86_64/sysroot "$PREBUILT/sysroot" 2>/dev/null || true

    # 修复 toolchain cmake
    local TOOLCHAIN="$NDK_PATH/build/cmake/android-legacy.toolchain.cmake"
    if [ -f "$TOOLCHAIN" ]; then
        if grep -q 'list(APPEND ANDROID_LINKER_FLAGS "-static-libstdc++")' "$TOOLCHAIN" 2>/dev/null; then
            sed -i 's/list(APPEND ANDROID_LINKER_FLAGS "-static-libstdc++")/# 为 Termux 禁用: list(APPEND ANDROID_LINKER_FLAGS "-static-libstdc++")/' "$TOOLCHAIN"
        fi
        if ! grep -q 'CMAKE_C_COMPILER_WORKS' "$TOOLCHAIN" 2>/dev/null; then
            sed -i '1a set(ANDROID_HOST_TAG "linux-x86_64")\nset(CMAKE_C_COMPILER_WORKS TRUE)\nset(CMAKE_CXX_COMPILER_WORKS TRUE)' "$TOOLCHAIN"
        fi
    fi
    
    local MAIN_TOOLCHAIN="$NDK_PATH/build/cmake/android.toolchain.cmake"
    if [ -f "$MAIN_TOOLCHAIN" ]; then
        if ! grep -q 'CMAKE_C_COMPILER_WORKS' "$MAIN_TOOLCHAIN" 2>/dev/null; then
            sed -i '1a set(ANDROID_HOST_TAG "linux-x86_64")\nset(CMAKE_C_COMPILER_WORKS TRUE)\nset(CMAKE_CXX_COMPILER_WORKS TRUE)' "$MAIN_TOOLCHAIN"
        fi
    fi

    echo "    ✓ NDK $NDK_NAME 配置完成"
}

# 1. 清理 ELF 二进制文件
echo "[1/12] 清理 ELF 二进制文件..."
pkg install -y termux-elf-cleaner 2>/dev/null || true

if command -v termux-elf-cleaner &> /dev/null; then
    echo "  正在清理 dart-sdk 二进制文件..."
    find $DART_SDK/bin -type f -executable 2>/dev/null | xargs -r termux-elf-cleaner 2>/dev/null || true

    echo "  正在清理引擎构件..."
    find $FLUTTER_ROOT/bin/cache/artifacts/engine -name "*.so" -o -name "gen_snapshot" -o -name "dart" 2>/dev/null | xargs -r termux-elf-cleaner 2>/dev/null || true

    echo "  ✓ ELF 二进制文件已清理"
else
    echo "  ⚠ 未找到 termux-elf-cleaner，跳过"
fi

# 2. 修复 Flutter SDK 脚本的 shebang
echo "[2/12] 修复 Flutter SDK 脚本的 shebang..."
TERMUX_BASH=/data/data/com.termux/files/usr/bin/bash
TERMUX_SH=/data/data/com.termux/files/usr/bin/sh
for f in $FLUTTER_ROOT/bin/flutter $FLUTTER_ROOT/bin/dart $FLUTTER_ROOT/bin/internal/shared.sh $FLUTTER_ROOT/bin/internal/update_dart_sdk.sh $FLUTTER_ROOT/bin/internal/content_aware_hash.sh $FLUTTER_ROOT/bin/internal/last_engine_commit.sh $FLUTTER_ROOT/bin/internal/update_engine_version.sh; do
    if [ -f "$f" ]; then
        sed -i "1s|#!/usr/bin/env bash|#!$TERMUX_BASH|" "$f"
        sed -i "1s|#!/usr/bin/env sh|#!$TERMUX_SH|" "$f"
    fi
done
echo "  ✓ Shebang 已修复"

# 3. 修复 engine.stamp 和 engine.realm
echo "[3/12] 修复 engine.stamp 和 engine.realm，注入框架版本标签..."
cp $FLUTTER_ROOT/bin/internal/engine.version $FLUTTER_ROOT/bin/cache/engine.stamp 2>/dev/null || true
echo -n > $FLUTTER_ROOT/bin/cache/engine.realm 2>/dev/null || true
echo "  ✓ engine.stamp=$(cat $FLUTTER_ROOT/bin/cache/engine.stamp)"
echo "  ✓ engine.realm 已清空"

if ! [ -d "$FLUTTER_ROOT/.git" ]; then
    echo "  ! 缺少 .git，正在创建虚拟仓库用于版本解析..."
    cd "$FLUTTER_ROOT" || true
    rm -f version
    /data/data/com.termux/files/usr/bin/git init -q >/dev/null 2>&1 || true
    /data/data/com.termux/files/usr/bin/git config user.email "termux@example.com" >/dev/null 2>&1 || true
    /data/data/com.termux/files/usr/bin/git config user.name "termux" >/dev/null 2>&1 || true
    /data/data/com.termux/files/usr/bin/git add bin/flutter >/dev/null 2>&1 || true
    /data/data/com.termux/files/usr/bin/git commit -q -m "Init framework" >/dev/null 2>&1 || true
    /data/data/com.termux/files/usr/bin/git tag "3.41.5" >/dev/null 2>&1 || true
    rm -f bin/cache/flutter.version.json 2>/dev/null || true
    echo "  ✓ 虚拟标签 3.41.5 已创建"
fi

# 4. 为 ARM64 兼容性修复 CMakeLists.txt
echo "[4/12] 为 ARM64 兼容性修复 CMakeLists.txt..."
CMAKE_FILE=$FLUTTER_ROOT/packages/flutter_tools/gradle/src/main/scripts/CMakeLists.txt
cat > "$CMAKE_FILE" << 'CMAKEOF'
cmake_minimum_required(VERSION 3.6)
set(CMAKE_C_COMPILER_WORKS TRUE)
set(CMAKE_CXX_COMPILER_WORKS TRUE)
project(FlutterNDKTrick C CXX)
CMAKEOF
echo "  ✓ CMakeLists.txt 已修复"

# 5. 生成 flutter_tools 的 package_config.json
echo "[5/12] 生成 flutter_tools 的 package_config.json..."
FLUTTER_TOOLS_DIR=$FLUTTER_ROOT/packages/flutter_tools
PKG_CONFIG=$FLUTTER_TOOLS_DIR/.dart_tool/package_config.json
if [ ! -f "$PKG_CONFIG" ]; then
    echo "  正在为 flutter_tools 运行 pub get..."
    cd "$FLUTTER_TOOLS_DIR"
    $DART_SDK/bin/dart pub get --suppress-analytics 2>/dev/null
    if [ -f "$PKG_CONFIG" ]; then
        echo "  ✓ package_config.json 已生成"
    else
        echo "  ✗ 生成 package_config.json 失败！"
    fi
else
    echo "  ✓ package_config.json 已存在"
fi

# 7. 禁用 forceNdkDownload
echo "[7/12] 禁用 forceNdkDownload..."
PLUGIN_UTILS="$FLUTTER_ROOT/packages/flutter_tools/gradle/src/main/kotlin/FlutterPluginUtils.kt"
if [ -f "$PLUGIN_UTILS" ]; then
    if ! grep -q "return // Termux: NDK already installed" "$PLUGIN_UTILS" 2>/dev/null; then
        sed -i '/fun forceNdkDownload/,/^    }/ {
            /val forcingNotRequired: Boolean/i\        return // Termux: NDK 已安装，跳过 CMake 技巧
        }' "$PLUGIN_UTILS"
        echo "  ✓ forceNdkDownload() 已修复为提前返回"
    else
        echo "  ✓ forceNdkDownload() 已修复"
    fi
fi

# 8. 创建 NDK clang 包装器
echo "[8/12] 创建 NDK clang 包装器..."

NDK_DIR="$ANDROID_SDK/ndk"
if [ -d "$NDK_DIR" ]; then
    NDK_COUNT=0
    for ndk_path in "$NDK_DIR"/*; do
        if [ -d "$ndk_path" ]; then
            setup_ndk_clang_wrappers "$ndk_path"
            NDK_COUNT=$((NDK_COUNT + 1))
        fi
    done
    if [ $NDK_COUNT -eq 0 ]; then
        echo "  ⚠ 未找到 NDK。安装 NDK 后将创建 clang 包装器。"
        echo "    安装 NDK 后重新运行此脚本: bash $PREFIX/share/flutter/post_install.sh"
    else
        echo "  ✓ $NDK_COUNT 个 NDK 已配置"
    fi
else
    echo "  ⚠ 未找到 NDK 目录。安装 NDK 后将创建 clang 包装器。"
    echo "    安装 NDK 后重新运行此脚本: bash $PREFIX/share/flutter/post_install.sh"
fi


# 11. 接受 Android 许可证
echo "[11/12] 接受 Android 许可证..."
mkdir -p $ANDROID_SDK/licenses
echo -e "\n24333f8a63b6825ea9c5514f83c2829b004d1fee" > $ANDROID_SDK/licenses/android-sdk-license
echo -e "\n84831b9409646a918e30573bab4c9c91346d8abd" > $ANDROID_SDK/licenses/android-sdk-preview-license
echo "  ✓ Android 许可证已接受"

# 配置 Flutter 的 Android SDK 路径
echo "[11.5/12] 在 Flutter 配置中设置 Android SDK 路径..."
$FLUTTER_ROOT/bin/flutter config --android-sdk $ANDROID_SDK --suppress-analytics 2>/dev/null || true
echo "  ✓ ANDROID_HOME=$ANDROID_SDK"

# 12. 创建主机平台符号链接
echo "[12/12] 创建主机平台符号链接..."
ENG_ART=$FLUTTER_ROOT/bin/cache/artifacts/engine
for dir in android-arm64-release android-arm64-profile; do
    if [ -d "$ENG_ART/$dir/linux-arm64" ] && [ ! -e "$ENG_ART/$dir/linux-x64" ]; then
        ln -sf linux-arm64 "$ENG_ART/$dir/linux-x64"
        echo "  ✓ $dir/linux-x64 -> linux-arm64"
    fi
done

if [ -d "$ENG_ART/linux-arm64" ] && [ ! -e "$ENG_ART/linux-x64" ]; then
    ln -sf linux-arm64 "$ENG_ART/linux-x64"
    echo "  ✓ linux-x64 -> linux-arm64"
fi

echo ""
echo "=========================================="
echo "安装后配置完成！"
echo "=========================================="
echo ""
echo "=== 快速开始 ==="
echo "  source /data/data/com.termux/files/usr/etc/profile.d/flutter.sh"
echo "  flutter create myapp && cd myapp"
echo ""
echo "=== 重要：项目设置（每个 Flutter 项目都需要） ==="
echo "  1. 修复 gradlew shebang:"
echo "     sed -i '1s|#!/usr/bin/env bash|#!/data/data/com.termux/files/usr/bin/bash|' android/gradlew"
echo ""
echo "  2. 编辑 android/app/build.gradle.kts:"
echo "     compileSdk = 36"
echo "     targetSdk = 36"
echo "     ndk { abiFilters += listOf(\"arm64-v8a\") }"
echo ""
echo "  3. 添加到 android/gradle.properties:"
echo "     android.aapt2FromMavenOverride=/data/data/com.termux/files/usr/opt/android-sdk/build-tools/36.1.0/aapt2"
echo ""
echo "  5. 构建 APK:"
echo "     flutter build apk --release --target-platform android-arm64"
echo ""
echo "=== Linux 桌面构建（可选） ==="
echo "  1. 添加到 linux/CMakeLists.txt（第一行，在 cmake_minimum_required 之前）:"
echo "     set(CMAKE_SYSTEM_NAME Linux)"
echo ""
echo "  2. 构建:"
echo "     flutter build linux --release"
echo ""
echo "=== Flutter Run（在设备上热重载） ==="
echo "  1. 安装 android-tools:  pkg install android-tools"
echo "  2. 启用 ADB TCP（从 PC）:  adb tcpip 5555"
echo "  3. 在 Termux 中连接:  adb connect localhost:5555"
echo "     （在屏幕上接受 '允许 USB 调试？' 对话框）"
echo "  4. 运行:  flutter run -d emulator-5554"
echo ""
