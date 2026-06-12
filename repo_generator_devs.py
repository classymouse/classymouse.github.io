#!/usr/bin/env python3
"""Generate the The Crew dev repository.

This script is intentionally simpler than the shared repo generator:
- one output target only: repository.devs
- one repository addon only: repository.thecrew.devs
- no production deploy switches
- defaults to packaging from the live Kodi addons source tree
- can also package from a separate working copy containing the addon folders

Usage examples:
    python repo_generator_devs.py
    python repo_generator_devs.py --source-root D:\\path\\to\\working\\copy
    python repo_generator_devs.py --output-dir D:\\Development\\github\\classymouse.github.io\\repository.devs
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


KODI_ADDONS_PATH = r'C:\\Users\\fvanb\\AppData\\Roaming\\Kodi\\addons'

SOURCE_ADDONS = [
    'script.module.thecrew',
    'plugin.video.thecrew',
    'script.thecrew.artwork',
]

REPO_ADDON_ID = 'repository.thecrew.devs'
REPO_ADDON_VERSION = '1.0.5'
CLEAN_INSTALL_NOTE = (
    'Clean Kodi? Update repositories, then install bs4, SimpleJSON, and InputStream Helper from the '
    'built-in Kodi Add-on repository before module/plugin. ResolveURL comes from Gujal (bundled in this repo).'
)
REPO_ADDON_NAME = 'The Crew Dev Repository'
# One URL for File Manager browse, repo index, checksum, and zip datadir (same pattern as alpha repo).
REPO_BASE_URL = 'https://classymouse.github.io/repository.devs/'
REPO_ADDON_URL = REPO_BASE_URL
DEFAULT_OUTPUT_DIR = Path(__file__).parent / 'repository.devs'
DEFAULT_SOURCE_ROOT = Path(KODI_ADDONS_PATH)
REPO_DIR_NAME = REPO_ADDON_ID

REQUIRED_MODULE_FILES = [
    'lib/resources/lib/modules/scraper_test.py',
    'lib/resources/lib/modules/sources_test.py',
]

# Artwork zips must ship the full modern theme — partial installs break icons and dialogs.
ARTWORK_MIN_MODERN_PNG = 170
ARTWORK_MIN_MODERN_1080I_XML = 18
ARTWORK_REQUIRED_PATHS = [
    'resources/media/modern/main_movies.png',
    'resources/skins/modern/1080i/ScraperStatus.xml',
    'resources/skins/modern/1080i/EpisodeInfo.xml',
]

EXCLUDE_DIRS = {
    '.git', '.github', '__pycache__', '.pytest_cache', '.mypy_cache',
    '.venv', 'venv', 'env', '.env', '.idea', '.vscode', '.vs',
    'docs', 'tools', 'tests', 'repository.devs', 'cleanup', 'test_videos',
    'local_overrides', 'backup_originals', 'backup_originals*', 'white',
}

EXCLUDE_FILES = {
    '.gitignore', '.gitattributes', 'README.md', 'README.txt', 'TODO.md',
    'CHANGELOG.md', 'LICENSE', 'LICENSE.txt', 'addons.xml', 'addons.xml.md5',
}


def get_addon_version(addon_path: Path) -> str:
    addon_xml = addon_path / 'addon.xml'
    if not addon_xml.exists():
        raise FileNotFoundError(f'addon.xml not found in {addon_path}')
    tree = ET.parse(addon_xml)
    root = tree.getroot()
    version = root.get('version')
    if not version:
        raise ValueError(f'Missing version in {addon_xml}')
    return version


def should_skip_path(path: Path, base_path: Path) -> bool:
    rel = path.relative_to(base_path)
    parts = rel.parts

    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
        if part.startswith('.'):
            return True

    name = path.name
    if name in EXCLUDE_FILES:
        return True
    if name.startswith('.'):
        return True
    if name.endswith(('.pyc', '.pyo', '.db', '.bak', '.old', '.tmp', '.temp')):
        return True
    if name.endswith('.zip'):
        return True
    if name.lower().startswith('readme'):
        return True
    if name.lower().startswith('todo'):
        return True
    if name.lower().startswith('changelog'):
        return True
    return False


def copy_metadata_files(source_dir: Path, dest_dir: Path) -> None:
    for meta in ['addon.xml', 'icon.png', 'fanart.jpg', 'changelog.txt']:
        src = source_dir / meta
        if src.exists():
            shutil.copy2(src, dest_dir / meta)


def write_dir_index_html(target_dir: Path, title: str) -> None:
    """HTML index Kodi File Manager can parse — lists zips and subfolders."""
    links = []
    for entry in sorted(target_dir.iterdir()):
        if entry.is_dir():
            links.append(f'<a href="{entry.name}/">{entry.name}/</a>')
        elif entry.suffix == '.zip':
            links.append(f'<a href="{entry.name}">{entry.name}</a>')
    body = '<br>\n'.join(links)
    html = f'''<html>
<head><title>Index of {title}</title></head>
<body>
<h1>Index of {title}</h1>
{body}
</body>
</html>
'''
    (target_dir / 'index.html').write_text(html, encoding='utf-8')


def verify_artwork_zip(zip_path: Path, addon_id: str = 'script.thecrew.artwork') -> None:
    """Fail the build if the artwork zip would produce hollow Shield installs."""
    prefix = f'{addon_id}/'
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
    modern_png = [n for n in names if f'{prefix}resources/media/modern/' in n and n.endswith('.png')]
    dialog_xml = [
        n for n in names
        if f'{prefix}resources/skins/modern/1080i/' in n and n.endswith('.xml')
    ]
    missing = [f'{prefix}{rel}' for rel in ARTWORK_REQUIRED_PATHS if f'{prefix}{rel}' not in names]
    errors = []
    if len(modern_png) < ARTWORK_MIN_MODERN_PNG:
        errors.append(f'modern PNG count {len(modern_png)} < {ARTWORK_MIN_MODERN_PNG}')
    if len(dialog_xml) < ARTWORK_MIN_MODERN_1080I_XML:
        errors.append(f'modern 1080i XML count {len(dialog_xml)} < {ARTWORK_MIN_MODERN_1080I_XML}')
    if missing:
        errors.append('missing required paths: ' + ', '.join(missing))
    if errors:
        raise RuntimeError(f'Artwork zip failed integrity check ({zip_path.name}): ' + '; '.join(errors))


def create_addon_zip(addon_id: str, source_root: Path, output_root: Path) -> tuple[str, str, Path]:
    source_dir = source_root / addon_id
    if not source_dir.exists():
        raise FileNotFoundError(f'Source addon directory not found: {source_dir}')

    version = get_addon_version(source_dir)
    addon_out_dir = output_root / addon_id
    addon_out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = addon_out_dir / f'{addon_id}-{version}.zip'
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not should_skip_path(root_path / d, source_dir)]
            for file in files:
                file_path = root_path / file
                if should_skip_path(file_path, source_dir):
                    continue
                arcname = f'{addon_id}/{file_path.relative_to(source_dir)}'
                zf.write(file_path, arcname)

    copy_metadata_files(source_dir, addon_out_dir)
    write_dir_index_html(addon_out_dir, addon_id)

    if addon_id == 'script.module.thecrew':
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = set(zf.namelist())
        for req in REQUIRED_MODULE_FILES:
            arcname = f'{addon_id}/{req}'
            if arcname not in names:
                raise RuntimeError(f'Missing required module file in zip: {req}')

    if addon_id == 'script.thecrew.artwork':
        verify_artwork_zip(zip_path, addon_id)

    return addon_id, version, zip_path


def build_addons_xml(source_root: Path, output_root: Path) -> Path:
    addons_root = ET.Element('addons')

    for addon_id in SOURCE_ADDONS:
        addon_xml = source_root / addon_id / 'addon.xml'
        if not addon_xml.exists():
            raise FileNotFoundError(f'Missing addon.xml for {addon_id}: {addon_xml}')
        addons_root.append(ET.parse(addon_xml).getroot())

    tree = ET.ElementTree(addons_root)
    ET.indent(tree, space='    ')
    addons_xml_path = output_root / 'addons.xml'
    tree.write(addons_xml_path, encoding='UTF-8', xml_declaration=True)

    # GitHub Pages serves LF; Windows checkout may CRLF the working tree.
    # Normalize so addons.xml.md5 always matches the deployed bytes Kodi fetches.
    xml_bytes = addons_xml_path.read_bytes().replace(b'\r\n', b'\n')
    addons_xml_path.write_bytes(xml_bytes)

    md5 = hashlib.md5(xml_bytes).hexdigest()
    (output_root / 'addons.xml.md5').write_text(md5, encoding='ascii')

    if hashlib.md5(addons_xml_path.read_bytes()).hexdigest() != md5:
        raise RuntimeError('addons.xml.md5 mismatch after build — line-ending normalization failed')
    return addons_xml_path


def build_repo_addon(output_root: Path, source_root: Path) -> Path:
    repo_dir = output_root / REPO_DIR_NAME
    repo_dir.mkdir(parents=True, exist_ok=True)

    addon_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{REPO_ADDON_ID}" name="{REPO_ADDON_NAME}" version="{REPO_ADDON_VERSION}" provider-name="The Crew">
    <extension point="xbmc.addon.repository" name="{REPO_ADDON_NAME}">
        <dir>
            <info compressed="false">{REPO_BASE_URL}addons.xml</info>
            <checksum>{REPO_BASE_URL}addons.xml.md5</checksum>
            <datadir zip="true">{REPO_BASE_URL}</datadir>
        </dir>
        <dir>
            <info compressed="false">https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml</info>
            <checksum>https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml.md5</checksum>
            <datadir zip="true">https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/</datadir>
        </dir>
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary lang="en">The Crew development repository</summary>
        <description lang="en">Development repository for The Crew side-project and refactor work. Contains dev/test builds that may change rapidly and are not intended for regular users.[CR][CR]{CLEAN_INSTALL_NOTE}</description>
        <disclaimer lang="en">This repository contains development software. Use at your own risk. Backup your Kodi data before installing.</disclaimer>
        <platform>all</platform>
        <license>GNU GENERAL PUBLIC LICENSE Version 3</license>
        <website>{REPO_ADDON_URL}</website>
        <source>https://github.com/classymouse/script.module.thecrew</source>
        <assets>
            <icon>icon.png</icon>
            <fanart>fanart.jpg</fanart>
        </assets>
        <news>v1.0.5 - Single GitHub Pages URL for browse + repo index (drop raw.githubusercontent datadir)[CR]v1.0.4 - Clean-install dependency note[CR]v1.0.3 - addons.xml.md5 LF fix on Windows</news>
    </extension>
</addon>
'''
    (repo_dir / 'addon.xml').write_text(addon_xml, encoding='utf-8')

    # Keep artwork source local and explicit; never fall back to another repository.
    repo_icon = source_root / 'script.module.thecrew' / 'icon.png'
    repo_fanart = source_root / 'script.module.thecrew' / 'fanart.jpg'
    if not repo_icon.exists() or not repo_fanart.exists():
        raise FileNotFoundError(
            f'Missing repository artwork source files: {repo_icon} / {repo_fanart}'
        )
    shutil.copy2(repo_icon, repo_dir / 'icon.png')
    shutil.copy2(repo_fanart, repo_dir / 'fanart.jpg')

    zip_path = repo_dir / f'{REPO_DIR_NAME}-{REPO_ADDON_VERSION}.zip'
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(repo_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for file in files:
                file_path = root_path / file
                if file_path == zip_path:
                    continue
                if file_path.suffix == '.zip':
                    continue
                arcname = f'{REPO_DIR_NAME}/{file_path.relative_to(repo_dir)}'
                zf.write(file_path, arcname)

    return zip_path


def build_root_index(output_root: Path) -> None:
    # Flat zip link in the source root — same pattern as repository.thecrew.alpha.
    # Kodi File Manager parses simple same-directory hrefs reliably; nested paths often fail on Android.
    links = [
        f'<a href="{REPO_DIR_NAME}-{REPO_ADDON_VERSION}.zip">{REPO_DIR_NAME}-{REPO_ADDON_VERSION}.zip</a>',
    ]
    body = '<br>\n'.join(links)
    index_html = f'''<html>
<head><title>The Crew Dev Repository</title></head>
<body>
<h1>The Crew Dev Repository</h1>
<p>Development repository for The Crew side project.</p>
<p><strong>Kodi source (File Manager + repository index):</strong> <code>{REPO_BASE_URL}</code></p>
<p><strong>Clean install:</strong> {CLEAN_INSTALL_NOTE}</p>
<p><em>One URL only — do not use raw.githubusercontent.com (directories return HTTP 400).</em></p>
<hr>
{body}
</body>
</html>
'''
    (output_root / 'index.html').write_text(index_html, encoding='utf-8')
    write_dir_index_html(output_root / REPO_DIR_NAME, REPO_DIR_NAME)


def main() -> int:
    parser = argparse.ArgumentParser(description='Build The Crew dev repository')
    parser.add_argument('--source-root', default=str(DEFAULT_SOURCE_ROOT), help='Directory containing addon source folders')
    parser.add_argument('--output-dir', default=str(DEFAULT_OUTPUT_DIR), help='Output repository directory')
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    output_root = Path(args.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    missing = [addon_id for addon_id in SOURCE_ADDONS if not (source_root / addon_id).exists()]
    if missing:
        print('ERROR: source root does not contain all required addon folders:')
        for addon_id in missing:
            print(f'  - {source_root / addon_id}')
        print('\\nHint: use the live Kodi addons tree or pass --source-root to a separate working copy.')
        return 1

    print('=' * 60)
    print('The Crew Dev Repository Generator')
    print('=' * 60)
    print(f'Source root: {source_root}')
    print(f'Output root : {output_root}')

    addons_info = []
    for addon_id in SOURCE_ADDONS:
        print(f'Packaging {addon_id}...')
        addons_info.append(create_addon_zip(addon_id, source_root, output_root))

    addons_xml_path = build_addons_xml(source_root, output_root)
    repo_zip_path = build_repo_addon(output_root, source_root)
    shutil.copy2(repo_zip_path, output_root / repo_zip_path.name)
    build_root_index(output_root)

    print('\nPackaged addons:')
    for addon_id, version, zip_path in addons_info:
        print(f'  • {addon_id} v{version} -> {zip_path}')
    print(f'  • {REPO_ADDON_ID} v{REPO_ADDON_VERSION} -> {repo_zip_path}')
    print(f'  • addons.xml -> {addons_xml_path}')
    print(f'  • addons.xml.md5 -> {output_root / "addons.xml.md5"}')
    print('\nDone.')
    return 0


if __name__ == '__main__':
    sys.exit(main())




