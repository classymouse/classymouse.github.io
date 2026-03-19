#!/usr/bin/env python3
"""
The Crew Repository Generator
Automatically creates zip files for Kodi addons with proper structure and cleanup.
"""

import os
import shutil
import zipfile
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

# Configuration
KODI_ADDONS_PATH = r"C:\Users\fvanb\AppData\Roaming\Kodi\addons"
REPO_PATH = Path(__file__).parent  # classymouse.github.io directory

ADDONS = [
    "script.module.thecrew",
    "plugin.video.thecrew", 
    "script.thecrew.artwork"
]

# Files and directories to exclude (in addition to .gitignore)
EXCLUDE_PATTERNS = [
    # Python cache and compiled
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "__pycache__",
    ".pytest_cache",
    "*.egg-info",
    
    # Virtual environments
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenv",
    
    # Git and version control
    ".git",
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".github",
    
    # IDEs and editors
    ".idea",
    ".vscode",
    ".pylintrc",
    "*.swp",
    "*.swo",
    "*~",
    
    # Documentation and development
    "docs",
    "tools",
    "cleanup",
    "tests",
    "*.md",
    "README*",
    "TODO*",
    "CHANGELOG*",
    "LICENSE*",
    
    # Jupyter and notebooks
    "*.ipynb",
    ".ipynb_checkpoints",
    
    # Local development
    "local_overrides",
    "local_overrides*",
    "crew*.xml",
    "auto-commit.ps1",
    "backup_originals",
    "backup_originals*",
    "resize_images*.ps1",
    
    # Test files
    "test_*.py",
    "test_*",
    "*_test.py",
    
    # Build and temp
    "*.zip",
    "*.log",
    "*.tmp",
    "*.temp",
    "__MACOSX",
    
    # OS files
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.lnk"
]

def should_exclude(path, base_path):
    """Check if a file/directory should be excluded based on patterns."""
    relative = Path(path).relative_to(base_path)
    parts = relative.parts
    
    for pattern in EXCLUDE_PATTERNS:
        # Check directory names
        for part in parts:
            if pattern.startswith('*') and pattern.endswith('*'):
                if pattern[1:-1] in part:
                    return True
            elif pattern.startswith('*'):
                if part.endswith(pattern[1:]):
                    return True
            elif pattern.endswith('*'):
                if part.startswith(pattern[:-1]):
                    return True
            elif part == pattern:
                return True
        
        # Check full path
        path_str = str(relative)
        if pattern.startswith('*') and pattern.endswith('*'):
            if pattern[1:-1] in path_str:
                return True
        elif pattern.startswith('*'):
            if path_str.endswith(pattern[1:]):
                return True
        elif pattern.endswith('*'):
            if path_str.startswith(pattern[:-1]):
                return True
                
    return False

def get_addon_version(addon_path):
    """Extract version from addon.xml."""
    addon_xml = Path(addon_path) / "addon.xml"
    if not addon_xml.exists():
        raise FileNotFoundError(f"addon.xml not found in {addon_path}")
    
    tree = ET.parse(addon_xml)
    root = tree.getroot()
    return root.get('version')

def create_addon_zip(addon_id):
    """Create a properly structured zip file for an addon."""
    source_path = Path(KODI_ADDONS_PATH) / addon_id
    
    if not source_path.exists():
        print(f"❌ ERROR: {addon_id} not found in {KODI_ADDONS_PATH}")
        return False
    
    try:
        version = get_addon_version(source_path)
        print(f"\n📦 Creating {addon_id} version {version}...")
        
        # Destination directory in repo
        dest_dir = REPO_PATH / addon_id
        dest_dir.mkdir(exist_ok=True)
        
        zip_filename = f"{addon_id}-{version}.zip"
        zip_path = dest_dir / zip_filename
        
        # Remove old zip if exists
        if zip_path.exists():
            print(f"   🗑️  Removing old {zip_filename}")
            zip_path.unlink()
        
        # Create zip with proper structure (addon folder inside)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            file_count = 0
            for root, dirs, files in os.walk(source_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if not should_exclude(Path(root) / d, source_path)]
                
                for file in files:
                    file_path = Path(root) / file
                    
                    # Skip excluded files
                    if should_exclude(file_path, source_path):
                        continue
                    
                    # Calculate relative path from source
                    rel_path = file_path.relative_to(source_path)
                    
                    # Add to zip with addon_id as root folder
                    arcname = f"{addon_id}/{rel_path}"
                    zipf.write(file_path, arcname)
                    file_count += 1
            
            print(f"   ✅ Added {file_count} files")
        
        # Copy essential files to addon directory (for Kodi repo structure)
        for essential_file in ['addon.xml', 'fanart.jpg', 'icon.png']:
            src_file = source_path / essential_file
            if src_file.exists():
                dest_file = dest_dir / essential_file
                shutil.copy2(src_file, dest_file)
        
        # Copy changelog if exists
        changelog_src = source_path / "changelog.txt"
        if changelog_src.exists():
            changelog_dest = dest_dir / "changelog.txt"
            shutil.copy2(changelog_src, changelog_dest)
            print(f"   ✅ Copied changelog.txt")
        
        print(f"   ✅ Created {zip_filename} ({zip_path.stat().st_size // 1024} KB)")
        return True
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_addons_xml():
    """Update addons.xml and addons.xml.md5 in repo root."""
    print("\n📝 Updating addons.xml...")
    
    addons_root = ET.Element('addons')
    
    for addon_id in ADDONS:
        addon_xml_path = REPO_PATH / addon_id / "addon.xml"
        if addon_xml_path.exists():
            tree = ET.parse(addon_xml_path)
            addon_element = tree.getroot()
            addons_root.append(addon_element)
            print(f"   ✅ Added {addon_id}")
    
    # Write addons.xml
    tree = ET.ElementTree(addons_root)
    ET.indent(tree, space="    ")
    
    addons_xml_path = REPO_PATH / "addons.xml"
    tree.write(addons_xml_path, encoding='UTF-8', xml_declaration=True)
    print(f"   ✅ Updated addons.xml")
    
    # Create MD5 hash
    with open(addons_xml_path, 'rb') as f:
        md5_hash = hashlib.md5(f.read()).hexdigest()
    
    md5_path = REPO_PATH / "addons.xml.md5"
    with open(md5_path, 'w') as f:
        f.write(md5_hash)
    
    print(f"   ✅ Updated addons.xml.md5")

def main():
    """Main execution."""
    print("=" * 60)
    print("🚀 THE CREW REPOSITORY GENERATOR")
    print("=" * 60)
    
    success_count = 0
    
    for addon_id in ADDONS:
        if create_addon_zip(addon_id):
            success_count += 1
    
    print(f"\n📊 Result: {success_count}/{len(ADDONS)} addons processed successfully")
    
    if success_count == len(ADDONS):
        update_addons_xml()
        print("\n" + "=" * 60)
        print("✅ ALL DONE! Repository is ready to push.")
        print("=" * 60)
    else:
        print("\n⚠️  Some addons failed. Please check errors above.")

if __name__ == "__main__":
    main()
