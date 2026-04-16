
#!/usr/bin/env python3

import os
import sys
import git
import fire
import yaml
import utils
import shutil
import tomllib
import subprocess
from loguru import logger
from pathlib import Path
from sysroot import Sysroot
from package import Package


class GitProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        logger.trace(f"cloning {cur_count}/{max_count} {message}")


def patch_glib_typeof_content(content: str) -> str:
    wrapped_include = 'extern "C++" {\n#include <type_traits>\n}'
    return content.replace('#include <type_traits>', wrapped_include)


def copy_if_needed(src: str, dst: str) -> bool:
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        return False

    if dst_path.exists() and src_path.samefile(dst_path):
        return False

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_path, dst_path)
    return True


def ensure_symlink(path: Path, target: Path):
    if path.exists() or path.is_symlink():
        if path.is_symlink() and path.resolve() == target.resolve():
            return
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)


@utils.record
class Build:
    @utils.recordm
    def __init__(self, conf='build.toml'):
        path = Path(__file__).parent
        conf = path/conf

        # 若仓库内存在 depot_tools，则优先加入 PATH，便于本地直接运行
        depot_tools_path = path / 'depot_tools'
        if depot_tools_path.is_dir():
             os.environ['PATH'] = str(depot_tools_path) + os.pathsep + os.environ['PATH']
             logger.info(f"Added {depot_tools_path} to PATH")

        with open(conf, 'rb') as f:
            cfg = tomllib.load(f)

        ndk = cfg['ndk'].get('path') or os.environ.get('ANDROID_NDK')
        api = cfg['ndk'].get('api')
        tag = cfg['flutter'].get('tag')
        repo = cfg['flutter'].get('repo')
        root = cfg['flutter'].get('path')
        arch = cfg['build'].get('arch')
        mode = cfg['build'].get('runtime')
        gclient = cfg['build'].get('gclient')
        jobs = cfg['build'].get('jobs')
        sysroot = cfg['sysroot']
        syspath = sysroot.pop('path')
        package = cfg['package'].get('conf')
        release = cfg['package'].get('path')
        patches = cfg.get('patch')

        if not ndk:
            raise ValueError('neither ndk path nor ANDROID_NDK is set')
        if not tag:
            raise ValueError('require flutter tag')

        self.tag = tag
        self.api = api or 26
        self.conf = conf
        self.host = 'linux-x86_64'
        self.repo = repo or 'https://github.com/flutter/flutter'
        self.arch = arch or 'arm64'
        self.mode = mode or 'debug'
        self._sysroot = Sysroot(path=path/syspath, **sysroot)
        self.root = path/root
        self.gclient = path/gclient
        self.release = path/release
        self.toolchain = Path(ndk, f'toolchains/llvm/prebuilt/{self.host}')
        self.jobs = jobs
        if not self.release.parent.is_dir():
            raise ValueError(f'bad release path: "{release}"')

        with open(path/package, 'rb') as f:
            self.package = yaml.safe_load(f)

        if isinstance(patches, dict):
            self.patches = {}
            # 版本化补丁目录：patches/<flutter-tag>/*.patch
            patch_base = path / patches.get('dir', './patches') / self.tag

            def patch(key):
                return lambda: self.patch(**self.patches[key])

            for k, v in patches.items():
                if k == 'dir':  # Skip base directory config
                    continue
                if not isinstance(v, dict):  # Skip non-dict entries
                    continue
                self.patches[k] = {
                    'file': patch_base / v['file'],
                    'path': self.root / v['path']}
                self.__dict__[f'patch_{k}'] = patch(k)

    def config(self):
        info = (f'{k}\t: {v}' for k, v in self.__dict__.items() if k != 'package')
        logger.info('\n'+'\n'.join(info))

    def android_sdk_root(self, root: str = None, ndk_root: str = None):
        """创建 Flutter Android 构建默认会查找的 SDK 目录。

        Flutter 3.41.5 的 Android 构建默认会在
        flutter/engine/src/flutter/third_party/android_tools/sdk/ndk/28.2.13676358
        下查找 NDK。本方法在仓库工作区内创建这个目录，并把它符号链接到
        实际安装好的 NDK 路径，避免改动 Flutter 上游 GN 逻辑。
        """
        root = Path(root or Path(__file__).parent)
        if ndk_root:
            ndk_root = Path(ndk_root).resolve()
        else:
            ndk_root = Path(self.toolchain).resolve().parents[3]
        sdk_root = root / 'engine' / 'src' / 'flutter' / 'third_party' / 'android_tools' / 'sdk'
        ndk_dir = sdk_root / 'ndk'
        ndk_version_dir = ndk_dir / '28.2.13676358'

        ndk_dir.mkdir(parents=True, exist_ok=True)
        ensure_symlink(ndk_version_dir, ndk_root)
        return str(sdk_root)

    def clone(self, *, url: str = None, tag: str = None, out: str = None):
        url = url or self.repo
        out = out or self.root
        tag = tag or self.tag
        progress = GitProgress()

        if utils.flutter_tag(out) == tag:
            logger.info('flutter exists, skip.')
            return
        elif os.path.isdir(out):
            logger.info(f'moving {out} to {out}.old ...')
            os.rename(out, f'{out}.old')
            return

        try:
            git.Repo.clone_from(
                url=url,
                to_path=out,
                progress=progress,
                branch=tag)
        except git.exc.GitCommandError:
            raise RuntimeError('\n'.join(progress.error_lines))

    def sync(self, *, cfg: str = None, root: str = None):
        cfg = cfg or self.gclient
        src = root or self.root

        shutil.copy(cfg, os.path.join(src, '.gclient'))
        cmd = ['gclient', 'sync', '-DR', '--no-history']
        subprocess.run(cmd, cwd=src, check=True)

        # 修复 package_config.json 语言版本过旧的问题：
        # 1. 将预编译 dart-sdk 替换为与当前流程兼容的 3.11.3
        dart_sdk_dir = Path(src) / 'engine' / 'src' / 'third_party' / 'dart' / 'tools' / 'sdks' / 'dart-sdk'
        if dart_sdk_dir.exists():
            import urllib.request
            import zipfile
            import tempfile
            
            version_file = dart_sdk_dir / 'version'
            if version_file.exists() and version_file.read_text().strip() == '3.11.3':
                logger.info('Dart SDK already replaced with 3.11.3')
            else:
                logger.info('Replacing prebuilt dart-sdk with 3.11.3...')
                url = 'https://storage.googleapis.com/dart-archive/channels/stable/release/3.11.3/sdk/dartsdk-linux-x64-release.zip'
                with tempfile.TemporaryDirectory() as tmp_dir:
                    zip_path = Path(tmp_dir) / 'dartsdk.zip'
                    urllib.request.urlretrieve(url, zip_path)
                    
                    shutil.rmtree(dart_sdk_dir)
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(dart_sdk_dir.parent)

                logger.success('Fixed #5: Replaced prebuilt dart-sdk with version 3.11.3')

        # 2. 在 third_party/dart 中执行 dart pub get
        dart_dir = Path(src) / 'engine' / 'src' / 'third_party' / 'dart'
        if dart_dir.exists():
            logger.info('Running dart pub get in third_party/dart/ ...')
            dart_bin = dart_sdk_dir / 'bin' / 'dart'
            cmd_pub = [str(dart_bin), 'pub', 'get']
            subprocess.run(cmd_pub, cwd=dart_dir, check=True)
            logger.success('Fixed #5: Finished dart pub get')

    def patch(self, *, file, path):
        repo = git.Repo(path)
        repo.git.apply([file])

    def sysroot(self, arch: str = 'arm64'):
        """组装 Termux sysroot，并修复头文件兼容问题。"""
        self._sysroot(arch=arch)

        sysroot_path = Path(self._sysroot.path)

        # 修复 #3：移走 sysroot 自带的 libc++ 头文件，避免与 Flutter 自带 libcxx 冲突
        cxx_dir = sysroot_path / 'usr' / 'include' / 'c++'
        if cxx_dir.is_dir():
            cxx_bak = sysroot_path / 'usr' / 'include' / 'c++.bak'
            if cxx_bak.exists():
                shutil.rmtree(cxx_bak)
            os.rename(cxx_dir, cxx_bak)
            logger.success("Fixed #3: Renamed sysroot c++ headers to c++.bak")

        # 修复 #4：给 glib-typeof.h 中的 <type_traits> 增加 extern "C++" 包裹
        glib_typeof = sysroot_path / 'usr' / 'include' / 'glib-2.0' / 'glib' / 'glib-typeof.h'
        if glib_typeof.exists():
            content = glib_typeof.read_text(encoding='utf-8')
            if '<type_traits>' in content and 'extern "C++"' not in content:
                content = patch_glib_typeof_content(content)
                glib_typeof.write_text(content, encoding='utf-8')
                logger.success("Fixed #4: Patched glib-typeof.h with extern C++ wrapper")

    def configure(
        self,
        arch: str,
        mode: str,
        api: int = 26,
        root: str = None,
        sysroot: str = None,
        toolchain: str = None,
    ):
        root = root or self.root
        sysroot = os.path.abspath(sysroot or self._sysroot.path)
        toolchain = os.path.abspath(toolchain or self.toolchain)
        cmd = [
            'python3',
            'engine/src/flutter/tools/gn',
            '--linux',
            '--linux-cpu', arch,
            '--enable-fontconfig',
            '--no-goma',
            '--no-backtrace',
            '--clang',
            '--lto',
            '--no-enable-unittests',
            '--no-build-embedder-examples',
            '--no-prebuilt-dart-sdk',
            '--target-toolchain', toolchain,
            '--runtime-mode', mode,
            '--no-build-glfw-shell',
            '--gn-args', 'symbol_level=0',
            '--gn-args', 'use_default_linux_sysroot=false',
            '--gn-args', 'arm_use_neon=false',
            '--gn-args', 'arm_optionally_use_neon=true',
            '--gn-args', 'dart_include_wasm_opt=false',
            '--gn-args', 'dart_platform_sdk=false',
            '--gn-args', 'is_desktop_linux=false',
            '--gn-args', 'use_default_linux_sysroot=false',
            '--gn-args', 'dart_support_perfetto=false',
            '--gn-args', 'skia_use_perfetto=false',
            '--gn-args', f'custom_sysroot="{sysroot}"',
            '--gn-args', 'is_termux=true',
            '--gn-args', f'is_termux_host={utils.__TERMUX__}',
            '--gn-args', f'termux_ndk_path="{toolchain}"',
            # '--gn-args', f'termux_api_level={api}',
        ]
        subprocess.run(cmd, cwd=root, check=True)

    def build(self, arch: str, mode: str, root: str = None, jobs: int = None):
        root = root or self.root
        jobs = jobs or self.jobs
        cmd = [
            'ninja', '-C', utils.target_output(root, arch, mode),
            'flutter',
            # 额外构建 libflutter_linux_gtk.so，供 flutter build linux 使用
            'flutter/shell/platform/linux:flutter_gtk',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')
        subprocess.run(cmd, check=True)

    def build_dart(self, arch: str, mode: str, root: str = None, jobs: int = None):
        """单独构建 dart 可执行文件并放入 dart-sdk/bin。

        注意：`ninja flutter` 不会产出 dart 二进制，因此这里必须单独构建，
        否则后续 `flutter build apk` 无法正常工作。
        """
        root = root or self.root
        jobs = jobs or self.jobs
        out_dir = utils.target_output(root, arch, mode)

        # 单独构建 dart 与 dartaotruntime_product
        cmd = [
            'ninja', '-C', out_dir,
            'exe.unstripped/dart',
            'dartaotruntime_product',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')

        logger.info(f'Building dart binary for {arch}...')
        subprocess.run(cmd, check=True)

        # 将 dart 复制到 dart-sdk/bin/
        dart_src = os.path.join(out_dir, 'exe.unstripped', 'dart')
        dart_dst = os.path.join(out_dir, 'dart-sdk', 'bin', 'dart')

        if copy_if_needed(dart_src, dart_dst):
            logger.info(f'dart binary copied to {dart_dst}')
        elif os.path.exists(dart_src):
            logger.info(f'dart binary already available at {dart_dst}')
        else:
            logger.warning(f'dart binary not found at {dart_src}')

        # 将 dartaotruntime_product 复制到 dart-sdk/bin/dartaotruntime
        aotruntime_src = os.path.join(out_dir, 'dartaotruntime_product')
        aotruntime_dst = os.path.join(out_dir, 'dart-sdk', 'bin', 'dartaotruntime')

        if copy_if_needed(aotruntime_src, aotruntime_dst):
            logger.info(f'dartaotruntime copied to {aotruntime_dst}')
        elif os.path.exists(aotruntime_src):
            logger.info(f'dartaotruntime already available at {aotruntime_dst}')
        else:
            logger.warning(f'dartaotruntime_product not found at {aotruntime_src}')

    def build_impellerc(self, arch: str, mode: str, root: str = None, jobs: int = None):
        """构建 impellerc 着色器编译器。

        `flutter build apk --release` 在编译 shader 时需要它。
        """
        root = root or self.root
        jobs = jobs or self.jobs
        out_dir = utils.target_output(root, arch, mode)

        cmd = [
            'ninja', '-C', out_dir,
            'flutter/impeller/compiler:impellerc',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')

        logger.info(f'Building impellerc for {arch}...')
        subprocess.run(cmd, check=True)

        # 校验 impellerc 是否已经生成
        impellerc_path = os.path.join(out_dir, 'impellerc')
        if os.path.exists(impellerc_path):
            logger.info(f'impellerc built at {impellerc_path}')
        else:
            logger.warning(f'impellerc not found at {impellerc_path}')

    def build_const_finder(self, arch: str, mode: str, root: str = None, jobs: int = None):
        """构建 const_finder.dart.snapshot，用于图标 tree shaking。

        若缺少该文件，用户需要额外传 `--no-tree-shake-icons`。
        """
        root = root or self.root
        jobs = jobs or self.jobs
        out_dir = utils.target_output(root, arch, mode)

        cmd = [
            'ninja', '-C', out_dir,
            'flutter/tools/const_finder:const_finder',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')

        logger.info(f'Building const_finder for {arch}...')
        subprocess.run(cmd, check=True)

        # 校验并复制到产物目录
        snapshot_src = os.path.join(out_dir, 'gen', 'const_finder.dart.snapshot')
        snapshot_dst = os.path.join(out_dir, 'const_finder.dart.snapshot')

        if os.path.exists(snapshot_src):
            shutil.copy(snapshot_src, snapshot_dst)
            logger.info(f'const_finder.dart.snapshot built at {snapshot_dst}')
        else:
            logger.warning(f'const_finder.dart.snapshot not found at {snapshot_src}')

    def configure_android(
        self,
        arch: str = 'arm64',
        mode: str = 'release',
        root: str = None,
        sysroot: str = None,
        toolchain: str = None,
    ):
        """配置 Android 版 gen_snapshot 的 GN 参数。

        目标是生成一个能在 ARM64 Termux 上运行、并输出 Android ARM64 AOT 代码的
        host-side `gen_snapshot`。
        """
        root = root or self.root
        sysroot = os.path.abspath(sysroot or self._sysroot.path)
        toolchain = os.path.abspath(toolchain or self.toolchain)
        android_sdk_root = self.android_sdk_root(root=root)

        # Android 构建输出目录
        out_dir = f'android_{mode}_{arch}'

        cmd = [
            'python3',
            'engine/src/flutter/tools/gn',
            '--android',
            '--android-cpu', arch,
            '--runtime-mode', mode,
            '--no-goma',
            '--no-backtrace',
            '--clang',
            '--lto',
            '--no-enable-unittests',
            '--no-build-embedder-examples',
            '--no-prebuilt-dart-sdk',
            # Android 目标构建不传 --target-toolchain，保留 Flutter 默认 Android toolchain
            # 这里仅补充 Termux cross-host 所需 GN 参数
            '--gn-args', 'termux_cross_host=true',
            '--gn-args', f'android_sdk_root="{android_sdk_root}"',
            '--gn-args', f'termux_ndk_path="{toolchain}"',
            '--gn-args', f'custom_sysroot="{sysroot}"',
            '--gn-args', 'symbol_level=0',
            '--gn-args', 'use_default_linux_sysroot=false',
        ]
        logger.info(f'Configuring Android gen_snapshot build: {out_dir}')
        subprocess.run(cmd, cwd=root, check=True)
        return out_dir

    def build_android_gen_snapshot(
        self,
        arch: str = 'arm64',
        mode: str = 'release',
        root: str = None,
        jobs: int = None,
    ):
        """构建 Android 目标的 gen_snapshot。

        该二进制运行在 Termux 主机侧，但输出的是 Android ARM64 的 AOT 代码。
        """
        root = root or self.root
        jobs = jobs or self.jobs
        out_dir = f'android_{mode}_{arch}'
        out_path = os.path.join(root, 'engine', 'src', 'out', out_dir)

        cmd = [
            'ninja', '-C', out_path,
            'flutter/third_party/dart/runtime/bin:gen_snapshot',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')

        logger.info(f'Building Android gen_snapshot: {out_dir}')
        subprocess.run(cmd, check=True)

        # Find and copy gen_snapshot to the location expected by package.yaml
        # package.yaml 期望的产物路径：android_release_arm64/clang_arm64/gen_snapshot
        possible_paths = [
            os.path.join(out_path, 'exe.stripped', 'gen_snapshot'),
            os.path.join(out_path, 'gen_snapshot'),
            os.path.join(out_path, 'clang_x64', 'exe.stripped', 'gen_snapshot'),
            os.path.join(out_path, 'clang_x64', 'gen_snapshot'),
        ]

        gen_snapshot_src = None
        for path in possible_paths:
            if os.path.exists(path):
                gen_snapshot_src = path
                break

        if gen_snapshot_src:
            # 复制到 package.yaml 期望的位置
            target_dir = os.path.join(out_path, 'clang_arm64')
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, 'gen_snapshot')
            shutil.copy(gen_snapshot_src, target_path)
            logger.info(f'✓ gen_snapshot copied to {target_path}')
            return target_path

        logger.warning('gen_snapshot not found at expected paths')
        return None

    def debuild(self, arch: str, output: str = None, root: str = None, **conf):
        conf = conf or self.package
        # root 指向 Flutter SDK 根目录（即 build.toml 中的 [flutter].path）
        root = root or self.root
        output = output or self.output(arch)

        pkg = Package(root=root, arch=arch, **conf)
        pkg.debuild(output=output)

    def output(self, arch: str):
        if self.release.is_dir():
            name = f'flutter_{self.tag}_{utils.termux_arch(arch)}.deb'
            return self.release/name
        else:
            return self.release

    def build_all(self, arch: str = 'arm64', jobs: int = None):
        """一条命令完成完整的 Flutter Termux 构建。

        该流程会同时构建：
        - `flutter run -d linux` 需要的 Linux 侧产物
        - `flutter build apk --release --target-platform android-arm64`
          需要的 Android `gen_snapshot`

        当前仅支持 `android-arm64` 的 APK 构建产物。
        """
        logger.info('=== Starting complete Flutter Termux build ===')

        # 第 1 步：构建 Linux debug，用于 flutter run -d linux --debug
        logger.info('[1/12] Configuring Linux debug...')
        self.configure(arch=arch, mode='debug')

        logger.info('[2/12] Building Flutter engine + dart...')
        self.build(arch=arch, mode='debug', jobs=jobs)
        self.build_dart(arch=arch, mode='debug', jobs=jobs)

        # 第 3 步：构建 impellerc，用于 shader 编译
        logger.info('[3/12] Building impellerc...')
        self.build_impellerc(arch=arch, mode='debug', jobs=jobs)

        # 第 4 步：构建 const_finder，用于图标 tree shaking
        logger.info('[4/12] Building const_finder...')
        self.build_const_finder(arch=arch, mode='debug', jobs=jobs)

        # 第 5 步：构建 Linux release，用于 flutter build linux
        logger.info('[5/12] Configuring Linux release...')
        self.configure(arch=arch, mode='release')

        logger.info('[6/12] Building Flutter engine (release)...')
        self.build(arch=arch, mode='release', jobs=jobs)

        # 第 7 步：构建 Linux profile，用于 flutter run -d linux --profile
        logger.info('[7/12] Configuring Linux profile...')
        self.configure(arch=arch, mode='profile')

        logger.info('[8/12] Building Flutter engine (profile)...')
        self.build(arch=arch, mode='profile', jobs=jobs)

        # 第 9 步：构建 Android release 版 gen_snapshot（仅支持 arm64）
        logger.info('[9/12] Building Android gen_snapshot release (arm64 only)...')
        self.configure_android(arch='arm64', mode='release')
        self.build_android_gen_snapshot(arch='arm64', mode='release', jobs=jobs)

        # 第 10 步：构建 Android profile 版 gen_snapshot
        logger.info('[10/12] Building Android gen_snapshot profile (arm64 only)...')
        self.configure_android(arch='arm64', mode='profile')
        self.build_android_gen_snapshot(arch='arm64', mode='profile', jobs=jobs)

        # 第 11 步：打包 deb
        logger.info('[11/12] Packaging deb...')
        self.debuild(arch=arch, output=self.output(arch))

        logger.info('[12/12] Build complete!')
        logger.info(f'Output: {self.output(arch)}')
        logger.info('Note: Users must use --target-platform android-arm64 when building APKs')

    def __call__(self):
        self.config()
        self.clone()
        self.sync()

        for arch in self.arch:
            self.sysroot(arch=arch)
            for mode in self.mode:
                self.configure(arch=arch, mode=mode)
                self.build(arch=arch, mode=mode)
            self.debuild(arch=arch, output=self.output(arch))


if __name__ == '__main__':
    logger.remove()
    logger.add(
        sys.stdout,
        diagnose=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <9}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>")
        )
    fire.Fire(Build())
