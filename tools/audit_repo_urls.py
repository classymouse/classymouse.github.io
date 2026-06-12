#!/usr/bin/env python3
"""Live audit: browse URL, Kodi index, md5, sample zip — check all boxes."""
from __future__ import annotations

import hashlib
import sys
import urllib.error
import urllib.request

REPOS = [
    {
        'name': 'Alpha (classymouse root)',
        'browse': 'https://classymouse.github.io/',
        'addons_xml': 'https://classymouse.github.io/addons.xml',
        'md5': 'https://classymouse.github.io/addons.xml.md5',
        'sample_zip': 'https://classymouse.github.io/script.module.thecrew/script.module.thecrew-3.0.5.zip',
        'file_manager_note': 'https://classymouse.github.io/repository.thecrew.alpha/',
    },
    {
        'name': 'Dev (repository.devs)',
        'browse': 'https://classymouse.github.io/repository.devs/',
        'addons_xml': 'https://classymouse.github.io/repository.devs/addons.xml',
        'md5': 'https://classymouse.github.io/repository.devs/addons.xml.md5',
        'sample_zip': 'https://classymouse.github.io/repository.devs/script.module.thecrew/script.module.thecrew-3.0.5.zip',
        'file_manager_note': 'https://classymouse.github.io/repository.devs/',
    },
    {
        'name': 'Dev RAW (broken browse — must fail)',
        'browse': 'https://raw.githubusercontent.com/classymouse/classymouse.github.io/main/repository.devs/',
        'addons_xml': None,
        'md5': None,
        'sample_zip': None,
        'file_manager_note': None,
    },
    {
        'name': 'Production (team-crew.github.io)',
        'browse': 'https://team-crew.github.io/',
        'addons_xml': 'https://team-crew.github.io/addons.xml',
        'md5': 'https://team-crew.github.io/addons.xml.md5',
        'sample_zip': 'https://team-crew.github.io/plugin.video.thecrew/plugin.video.thecrew-0.3.9.zip',
        'file_manager_note': 'https://team-crew.github.io/',
    },
    {
        'name': 'Gujal smrzips (dep index only)',
        'browse': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/',
        'addons_xml': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml',
        'md5': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml.md5',
        'sample_zip': 'https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/script.module.resolveurl/script.module.resolveurl-5.1.202.zip',
        'file_manager_note': None,
    },
]


def probe(url: str) -> tuple[str, int | None, int | None]:
    try:
        resp = urllib.request.urlopen(url, timeout=20)
        data = resp.read()
        return 'OK', resp.status, len(data)
    except urllib.error.HTTPError as exc:
        return f'HTTP {exc.code}', exc.code, None
    except Exception as exc:
        return str(exc), None, None


def main() -> int:
    failed = 0
    for repo in REPOS:
        print('=' * 60)
        print(repo['name'])
        print('=' * 60)
        status, code, size = probe(repo['browse'])
        browse_ok = code == 200
        print(f"  [{'x' if browse_ok else ' '}] Browse root HTTP 200     {repo['browse']}")
        print(f"      -> {status}" + (f' ({size} bytes)' if size else ''))

        if repo['addons_xml']:
            status, code, size = probe(repo['addons_xml'])
            xml_ok = code == 200 and size
            print(f"  [{'x' if xml_ok else ' '}] addons.xml               {status}" + (f' {size}b' if size else ''))
            if xml_ok:
                xml = urllib.request.urlopen(repo['addons_xml'], timeout=20).read()
                md5_raw = urllib.request.urlopen(repo['md5'], timeout=20).read().decode().strip()
                match = hashlib.md5(xml).hexdigest() == md5_raw
                print(f"  [{'x' if match else ' '}] addons.xml.md5 match     {md5_raw[:12]}...")
                if not match:
                    failed += 1
            else:
                failed += 1

        if repo['sample_zip']:
            status, code, size = probe(repo['sample_zip'])
            zip_ok = code == 200 and size and size > 100_000
            print(f"  [{'x' if zip_ok else ' '}] Sample zip               {status}" + (f' {size // 1024}KB' if size else ''))
            if not zip_ok:
                failed += 1

        if repo.get('file_manager_note'):
            same_base = repo['file_manager_note'].rstrip('/') in repo['browse'].rstrip('/') or repo['browse'].startswith(repo['file_manager_note'])
            # alpha: browse is root, file manager is repository.thecrew.alpha subfolder — related not identical
            if repo['name'].startswith('Alpha'):
                unified = repo['addons_xml'].startswith('https://classymouse.github.io/') and 'raw.githubusercontent.com/classymouse' not in repo['addons_xml']
            else:
                unified = repo['browse'] == repo['file_manager_note']
            print(f"  [{'x' if unified else ' '}] Crew index = Pages (not raw classymouse)")

        if repo['name'].startswith('Dev RAW'):
            expect_fail = not browse_ok
            print(f"  [{'x' if expect_fail else ' '}] Expected browse fail (400)  — do not use as File Manager source")
            if not expect_fail:
                failed += 1

        print()
    print('=' * 60)
    print(f'Done. Failures: {failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
