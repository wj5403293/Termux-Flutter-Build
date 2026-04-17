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

        ndk = cfg['ndk'].get('path') or os.environ.get('ANDROID_NDK')
        api = cfg['ndk'].get('api')
        tag = cfg['flutter'].get('tag')
        repo = cfg['flutter'].get('repo')
        root = cfg['flutter'].get('path')
        arch = cfg['build'].get('arch')
        mode = cfg['build'].get('runtime')
        gclient = cfg['build'].get('gclient')
        jobs = cfg['build'].get('jobs')
        sync_cfg = cfg.get('sync', {})
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
        self.sync_cfg = sync_cfg

        if not self.release.parent.is_dir():
            raise ValueError(f'bad release path: "{release}"')

        with open(path/package, 'rb') as f:
            self.package = yaml.safe_load(f)

        if isinstance(patches, dict):
            self.patches = {}
            # Version-based patches: patches/{version}/*.patch
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
        root = Path(root or Path(__file__).parent)
        if ndk_root:
            ndk_root = Path(ndk_root).resolve()
        else:
            ndk_root = Path(self.toolchain).resolve().parents[3]
        sdk_root = root / 'engine' / 'src' / 'flutter' / 'third_party' / 'android_tools' / 'sdk'
        ndk_dir = sdk_root / 'ndk'
        ndk_version_dir = ndk_dir / '28.2.13676358'
        clang_dir = ndk_root / 'toolchains' / 'llvm' / 'prebuilt' / 'linux-x86_64' / 'lib' / 'clang'

        ndk_dir.mkdir(parents=True, exist_ok=True)
        if ndk_version_dir.exists() or ndk_version_dir.is_symlink():
            if ndk_version_dir.resolve() == ndk_root.resolve():
                self.ensure_android_ndk_clang_alias(clang_dir)
                return str(sdk_root)
            if ndk_version_dir.is_dir() and not ndk_version_dir.is_symlink():
                shutil.rmtree(ndk_version_dir)
            else:
                ndk_version_dir.unlink()

        ndk_version_dir.symlink_to(ndk_root)
        self.ensure_android_ndk_clang_alias(clang_dir)
        return str(sdk_root)

    def ensure_android_ndk_clang_alias(self, clang_dir: Path, expected_version: str = '19'):
        if not clang_dir.exists():
            return

        expected_dir = clang_dir / expected_version
        if expected_dir.exists():
            return

        actual_versions = sorted(
            p for p in clang_dir.iterdir()
            if p.is_dir() and p.name.replace('.', '').isdigit()
        )
        if not actual_versions:
            return

        expected_dir.symlink_to(actual_versions[-1].name)

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

    def sync_windows_to_wsl(self):
        """Sync files from Windows to WSL before debuild.

        This prevents the common issue of editing files on Windows
        but building in WSL with stale copies.
        """
        import platform

        if not self.sync_cfg:
            logger.debug('No sync config, skipping')
            return

        system = platform.system()
        is_windows = system == 'Windows'
        is_wsl = system == 'Linux' and (
            'microsoft' in platform.release().lower() or
            bool(os.environ.get('WSL_DISTRO_NAME'))
        )

        # GitHub-hosted Ubuntu runners are plain Linux, not WSL.
        if not is_windows and not is_wsl:
            logger.debug('Not running on Windows/WSL, skipping sync')
            return

        windows_root = self.sync_cfg.get('windows_root')
        wsl_root = self.sync_cfg.get('wsl_root')
        paths = self.sync_cfg.get('paths', [])

        if not windows_root or not wsl_root:
            logger.warning('sync config incomplete, skipping')
            return

        # Convert Windows path to WSL mount path
        wsl_mount = '/mnt/' + windows_root[0].lower() + windows_root[2:].replace('\\', '/')

        for p in paths:
            src = f"{wsl_mount}/{p}"
            dst = f"{wsl_root}/{p}"
            # Ensure dst exists
            if is_wsl:
                subprocess.run(['bash', '-c', f"mkdir -p {dst}"], check=False)
            else:
                subprocess.run(['wsl', '-e', 'bash', '-c', f"mkdir -p {dst}"], check=False)
                
            if '.' in p.split('/')[-1] and not src.endswith('/'):
                 # It's a file
                 cmd = f"cp -a {src} {dst}"
            else:
                 # It's a directory
                 cmd = f"cp -a {src}/. {dst}/"
            logger.info(f'Syncing: {p}')
            if is_wsl:
                # Running in WSL, execute directly
                subprocess.run(['bash', '-c', cmd], check=False)
            else:
                # Running in Windows, use wsl command
                subprocess.run(['wsl', '-e', 'bash', '-c', cmd], check=False)

        logger.success('Sync completed')

    def debuild(self, arch: str, output: str = None, root: str = None, **conf):
        # Sync files from Windows to WSL before building
        self.sync_windows_to_wsl()

        conf = conf or self.package
        # root is Flutter SDK root (flutter/), set from [flutter].path in build.toml
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
        """One-command build for complete Flutter Termux package.

        This builds everything needed for both:
        - flutter run -d linux (Linux target)
        - flutter build apk --release --target-platform android-arm64

        Note: Only android-arm64 gen_snapshot is built. Users must use
        --target-platform android-arm64 when building APKs.

        Technical limitation analysis (2025-12-28):
        ============================================
        We tested compiling gen_snapshot for android-arm and android-x64:

        1. android-arm64: ✅ Works
           - Host=ARM64, Target=ARM64, same architecture

        2. android-arm (32-bit): ❌ Fails
           - BoringSSL has shift overflow errors (e.g., `r0 << 63` on 32-bit type)
           - The GN build system compiles host tool dependencies for target arch
           - Would require extensive patches to BoringSSL and build system

        3. android-x64: ❌ Fails
           - ARM64 sysroot headers incompatible with x64 compilation
           - Cross-architecture compilation fundamentally not supported

        Root cause: Flutter Engine's GN build system assumes host and target
        are compatible architectures. It doesn't properly separate host toolchain
        (ARM64) from target compilation (ARM32/x64).

        Usage:
            python3 build.py build_all --arch=arm64
        """
        logger.info('=== Starting complete Flutter Termux build ===')

        # Step 1: Build Linux debug (for flutter run -d linux --debug)
        logger.info('[1/12] Configuring Linux debug...')
        self.configure(arch=arch, mode='debug')

        logger.info('[2/12] Building Flutter engine + dart...')
        self.build(arch=arch, mode='debug', jobs=jobs)
        self.build_dart(arch=arch, mode='debug', jobs=jobs)

        # Step 3: Build impellerc (for shader compilation)
        logger.info('[3/12] Building impellerc...')
        self.build_impellerc(arch=arch, mode='debug', jobs=jobs)

        # Step 4: Build const_finder (for icon tree shaking)
        logger.info('[4/12] Building const_finder...')
        self.build_const_finder(arch=arch, mode='debug', jobs=jobs)

        # Step 5: Build Linux release (for flutter build linux)
        logger.info('[5/12] Configuring Linux release...')
        self.configure(arch=arch, mode='release')

        logger.info('[6/12] Building Flutter engine (release)...')
        self.build(arch=arch, mode='release', jobs=jobs)

        # Step 7: Build Linux profile (for flutter run -d linux --profile)
        logger.info('[7/12] Configuring Linux profile...')
        self.configure(arch=arch, mode='profile')

        logger.info('[8/12] Building Flutter engine (profile)...')
        self.build(arch=arch, mode='profile', jobs=jobs)

        # Step 9: Build Android gen_snapshot (only arm64 supported)
        # Due to Dart VM cross-compilation limitations, we can only build
        # gen_snapshot for android-arm64. android-arm and android-x64 require
        # patching the Dart VM signal handler code.
        logger.info('[9/12] Building Android gen_snapshot release (arm64 only)...')
        self.configure_android(arch='arm64', mode='release')
        self.build_android_gen_snapshot(arch='arm64', mode='release', jobs=jobs)

        # Step 10: Build Android gen_snapshot profile mode
        logger.info('[10/12] Building Android gen_snapshot profile (arm64 only)...')
        self.configure_android(arch='arm64', mode='profile')
        self.build_android_gen_snapshot(arch='arm64', mode='profile', jobs=jobs)

        # Step 11: Package deb
        logger.info('[11/12] Packaging deb...')
        self.debuild(arch=arch, output=self.output(arch))

        logger.info('[12/12] Build complete!')
        logger.info(f'Output: {self.output(arch)}')
        logger.info('Note: Users must use --target-platform android-arm64 when building APKs')

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
