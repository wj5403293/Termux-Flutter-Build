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
from dataclasses import dataclass
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

def resolve_ndk_path(configured_ndk: str | None) -> str | None:
    return os.environ.get('ANDROID_NDK') or configured_ndk

TERMUX_PACKAGE_SECTIONS = [
    'flutter',
    'flutter_gpu',
    'sky_engine',
    'dart_sdk',
    'dart_bin',
    'dart_snapshots',
    'dartaotruntime',
    'dartdev_aot',
    'frontend_server_aot',
    'flutter_web_sdk',
    'engine_common_artifacts',
    'flutter_patched_sdk',
    'flutter_patched_sdk_product',
    'executable',
    'profile',
    'stamps',
    'android_gen_snapshot_arm64',
    'vm_snapshots',
    'post_install',
]

TERMUX_LINUX_EXTRA = [
    'linux_gen_snapshot',
    'flutter_linux_gtk',
    'flutter_linux_gtk_release',
]

FULL_PROFILE_EXTRA = [
    'flutter_linux_gtk_profile',
    'android_gen_snapshot_arm64_profile',
]


@dataclass(frozen=True)
class BuildPreset:
    name: str
    package_sections: list[str]
    package_deb: bool
    prepare_web_sdk: bool
    configure_linux_debug: bool
    build_flutter_core: bool
    build_dart: bool
    build_impellerc: bool
    build_const_finder: bool
    build_linux_desktop: bool
    build_linux_release: bool
    build_linux_profile: bool
    build_android_release: bool
    build_android_profile: bool


PRESETS = {
    'termux': BuildPreset(
        name='termux',
        package_sections=TERMUX_PACKAGE_SECTIONS,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=False,
        build_linux_release=False,
        build_linux_profile=False,
        build_android_release=True,
        build_android_profile=False,
    ),
    'termux-linux': BuildPreset(
        name='termux-linux',
        package_sections=TERMUX_PACKAGE_SECTIONS + TERMUX_LINUX_EXTRA,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=True,
        build_linux_release=True,
        build_linux_profile=False,
        build_android_release=True,
        build_android_profile=False,
    ),
    'full-no-profile': BuildPreset(
        name='full-no-profile',
        package_sections=TERMUX_PACKAGE_SECTIONS + TERMUX_LINUX_EXTRA,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=True,
        build_linux_release=True,
        build_linux_profile=False,
        build_android_release=True,
        build_android_profile=False,
    ),
    'full': BuildPreset(
        name='full',
        package_sections=TERMUX_PACKAGE_SECTIONS + TERMUX_LINUX_EXTRA + FULL_PROFILE_EXTRA,
        package_deb=True,
        prepare_web_sdk=True,
        configure_linux_debug=True,
        build_flutter_core=True,
        build_dart=True,
        build_impellerc=True,
        build_const_finder=True,
        build_linux_desktop=True,
        build_linux_release=True,
        build_linux_profile=True,
        build_android_release=True,
        build_android_profile=True,
    ),
}


def resolve_preset(name: str) -> BuildPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f'unknown preset: {name}') from exc


@utils.record
class Build:
    @utils.recordm
    def __init__(self, conf='build.toml'):
        path = Path(__file__).parent
        conf = path/conf
        
        # Explicitly add depot_tools to PATH
        depot_tools_path = path / 'depot_tools'
        if depot_tools_path.is_dir():
             os.environ['PATH'] = str(depot_tools_path) + os.pathsep + os.environ['PATH']
             logger.info(f"Added {depot_tools_path} to PATH")

        with open(conf, 'rb') as f:
            cfg = tomllib.load(f)

        ndk = resolve_ndk_path(cfg['ndk'].get('path'))
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

        # TODO: check parameters
        self.tag = tag
        self.api = api or 26
        self.conf = conf
        # TODO: detect host
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
            patch_base = path / patches.get('dir', './patches')

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

        # Fix #5: package_config.json language version too old
        # 1. Replace prebuilt dart-sdk with matching version (3.11.3)
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

        # 2. Run dart pub get in third_party/dart/
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
        """Assemble Termux sysroot and apply fixes."""
        self._sysroot(arch=arch)
        
        sysroot_path = Path(self._sysroot.path)
        
        # Fix #3: Remove c++/v1 headers from sysroot (avoid libcxx conflict)
        cxx_dir = sysroot_path / 'usr' / 'include' / 'c++'
        if cxx_dir.is_dir():
            cxx_bak = sysroot_path / 'usr' / 'include' / 'c++.bak'
            if cxx_bak.exists():
                shutil.rmtree(cxx_bak)
            os.rename(cxx_dir, cxx_bak)
            logger.success("Fixed #3: Renamed sysroot c++ headers to c++.bak")

        # Fix #4: Patch glib-typeof.h to wrap <type_traits> with extern "C++"
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
            # Build libflutter_linux_gtk.so for flutter build linux
            'flutter/shell/platform/linux:flutter_gtk',
            # disable zip_archives
            # 'flutter/build/archives:artifacts',
            # 'flutter/build/archives:dart_sdk_archive',
            # 'flutter/build/archives:flutter_patched_sdk',
            # 'flutter/tools/font_subset',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')
        subprocess.run(cmd, check=True)

    def build_flutter_core(self, arch: str, mode: str, root: str = None, jobs: int = None):
        root = root or self.root
        jobs = jobs or self.jobs
        cmd = [
            'ninja',
            '-C',
            utils.target_output(root, arch, mode),
            'flutter',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')
        subprocess.run(cmd, check=True)

    def build_linux_desktop(self, arch: str, mode: str, root: str = None, jobs: int = None):
        root = root or self.root
        jobs = jobs or self.jobs
        cmd = [
            'ninja',
            '-C',
            utils.target_output(root, arch, mode),
            'flutter/shell/platform/linux:flutter_gtk',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')
        subprocess.run(cmd, check=True)

    def prepare_web_sdk(self, root: str = None):
        root = Path(root or self.root)
        flutter_bin = root / 'bin' / 'flutter'
        subprocess.run(
            [str(flutter_bin), '--suppress-analytics', 'precache', '--web'],
            cwd=root,
            check=True,
        )

    def build_dart(self, arch: str, mode: str, root: str = None, jobs: int = None):
        """Build dart binary for Termux.

        IMPORTANT: `ninja flutter` does NOT compile the dart binary!
        This method compiles the dart binary separately and copies it to dart-sdk/bin/.

        The dart binary is required for flutter build apk to work on Termux.
        """
        root = root or self.root
        jobs = jobs or self.jobs
        out_dir = utils.target_output(root, arch, mode)

        # Build dart binary and dartaotruntime_product
        cmd = [
            'ninja', '-C', out_dir,
            'exe.unstripped/dart',
            'dartaotruntime_product',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')

        logger.info(f'Building dart binary for {arch}...')
        subprocess.run(cmd, check=True)

        # Copy dart to dart-sdk/bin/
        dart_src = os.path.join(out_dir, 'exe.unstripped', 'dart')
        dart_dst = os.path.join(out_dir, 'dart-sdk', 'bin', 'dart')

        if copy_if_needed(dart_src, dart_dst):
            logger.info(f'dart binary copied to {dart_dst}')
        elif os.path.exists(dart_src):
            logger.info(f'dart binary already available at {dart_dst}')
        else:
            logger.warning(f'dart binary not found at {dart_src}')

        # Copy dartaotruntime_product to dart-sdk/bin/dartaotruntime
        aotruntime_src = os.path.join(out_dir, 'dartaotruntime_product')
        aotruntime_dst = os.path.join(out_dir, 'dart-sdk', 'bin', 'dartaotruntime')

        if copy_if_needed(aotruntime_src, aotruntime_dst):
            logger.info(f'dartaotruntime copied to {aotruntime_dst}')
        elif os.path.exists(aotruntime_src):
            logger.info(f'dartaotruntime already available at {aotruntime_dst}')
        else:
            logger.warning(f'dartaotruntime_product not found at {aotruntime_src}')

    def build_impellerc(self, arch: str, mode: str, root: str = None, jobs: int = None):
        """Build impellerc shader compiler for Termux.

        Required for flutter build apk --release to compile shaders.
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

        # Verify impellerc was built
        impellerc_path = os.path.join(out_dir, 'impellerc')
        if os.path.exists(impellerc_path):
            logger.info(f'impellerc built at {impellerc_path}')
        else:
            logger.warning(f'impellerc not found at {impellerc_path}')

    def build_const_finder(self, arch: str, mode: str, root: str = None, jobs: int = None):
        """Build const_finder.dart.snapshot for icon tree shaking.

        Without this, users need --no-tree-shake-icons flag.
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

        # Verify and copy to artifacts
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
        """Configure GN for Android target with Termux cross-host.

        This builds gen_snapshot that:
        - Runs on ARM64 Termux (cross-compiled from x86-64)
        - Produces Android ARM64 AOT code
        """
        root = root or self.root
        sysroot = os.path.abspath(sysroot or self._sysroot.path)
        toolchain = os.path.abspath(toolchain or self.toolchain)
        android_sdk_root = self.android_sdk_root(root=root)

        # Output directory for Android build
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
            # Note: no --target-toolchain for Android (uses default)
            # Termux cross-host settings
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
        """Build gen_snapshot for Android target.

        This produces gen_snapshot that can be run on Termux
        and generates Android ARM64 AOT code.
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
        # package.yaml expects: android_release_arm64/clang_arm64/gen_snapshot
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
            # Copy to the location expected by package.yaml
            target_dir = os.path.join(out_path, 'clang_arm64')
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, 'gen_snapshot')
            shutil.copy(gen_snapshot_src, target_path)
            logger.info(f'✓ gen_snapshot copied to {target_path}')
            return target_path

        logger.warning('gen_snapshot not found at expected paths')
        return None

    def debuild(self, arch: str, output: str = None, root: str = None, section=None, **conf):
        conf = conf or self.package
        # root is Flutter SDK root (flutter/), set from [flutter].path in build.toml
        root = root or self.root
        output = output or self.output(arch)

        pkg = Package(root=root, arch=arch, **conf)
        pkg.debuild(output=output, section=section)

    def output(self, arch: str):
        if self.release.is_dir():
            name = f'flutter_{self.tag}_{utils.termux_arch(arch)}.deb'
            return self.release/name
        else:
            return self.release

    def build_selected(self, arch: str = 'arm64', preset: str = 'termux', jobs: int = None):
        plan = resolve_preset(preset)
        jobs = jobs or self.jobs

        if plan.configure_linux_debug:
            self.configure(arch=arch, mode='debug')
        if plan.build_flutter_core:
            self.build_flutter_core(arch=arch, mode='debug', jobs=jobs)
        if plan.build_dart:
            self.build_dart(arch=arch, mode='debug', jobs=jobs)
        if plan.build_impellerc:
            self.build_impellerc(arch=arch, mode='debug', jobs=jobs)
        if plan.build_const_finder:
            self.build_const_finder(arch=arch, mode='debug', jobs=jobs)
        if plan.prepare_web_sdk:
            self.prepare_web_sdk()

        if plan.build_linux_desktop:
            self.build_linux_desktop(arch=arch, mode='debug', jobs=jobs)
        if plan.build_linux_release:
            self.configure(arch=arch, mode='release')
            self.build_linux_desktop(arch=arch, mode='release', jobs=jobs)
        if plan.build_linux_profile:
            self.configure(arch=arch, mode='profile')
            self.build_linux_desktop(arch=arch, mode='profile', jobs=jobs)

        if plan.build_android_release:
            self.configure_android(arch='arm64', mode='release')
            self.build_android_gen_snapshot(arch='arm64', mode='release', jobs=jobs)
        if plan.build_android_profile:
            self.configure_android(arch='arm64', mode='profile')
            self.build_android_gen_snapshot(arch='arm64', mode='profile', jobs=jobs)

        if plan.package_deb:
            self.debuild(arch=arch, output=self.output(arch), section=plan.package_sections)

    def build_all(self, arch: str = 'arm64', jobs: int = None):
        self.build_selected(arch=arch, preset='full', jobs=jobs)

    # TODO: check gclient and ninja existence
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
