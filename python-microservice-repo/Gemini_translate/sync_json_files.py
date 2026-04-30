#!/usr/bin/env python3
"""
Sync JSON files - remove entries from old file that don't exist in current file
Usage: python3 sync_json_files.py <current_file.json> <old_file.json>
"""

import json
import sys
import os
from datetime import datetime

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 sync_json_files.py <current_file.json> <old_file.json>")
        print()
        print("  current_file.json - актуальный файл (источник правды)")
        print("  old_file.json     - старый файл для очистки")
        print()
        print("Скрипт найдет записи в old_file, которых нет в current_file (по полю 'original')")
        print("и предложит удалить их.")
        sys.exit(1)

    current_file = sys.argv[1]
    old_file = sys.argv[2]

    # Check if files exist
    if not os.path.exists(current_file):
        print(f"❌ Error: File not found: {current_file}")
        sys.exit(1)

    if not os.path.exists(old_file):
        print(f"❌ Error: File not found: {old_file}")
        sys.exit(1)

    print("🔍 Comparing files...")
    print(f"📄 Current (актуальный): {current_file}")
    print(f"📄 Old (старый):         {old_file}")
    print()

    # Load JSON files
    try:
        with open(current_file, 'r', encoding='utf-8') as f:
            current_data = json.load(f)

        with open(old_file, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        sys.exit(1)

    # Extract all "original" values from current file
    current_originals = set()
    for item in current_data:
        if 'original' in item:
            current_originals.add(item['original'])

    current_count = len(current_data)
    old_count = len(old_data)

    print(f"📊 Current file has {current_count} entries")
    print(f"📊 Old file has {old_count} entries")
    print()

    # Find entries in old file that don't exist in current file
    to_delete = []
    to_keep = []

    for item in old_data:
        original = item.get('original', '')
        if original not in current_originals:
            to_delete.append(item)
        else:
            to_keep.append(item)

    # Check if there's anything to delete
    if not to_delete:
        print("✅ Файлы синхронизированы! Нет записей для удаления.")
        sys.exit(0)

    delete_count = len(to_delete)

    print(f"⚠️  Found {delete_count} entries to DELETE from old file:")
    print("━" * 60)

    # Show first 10 entries to delete
    for i, item in enumerate(to_delete[:10]):
        original = item.get('original', '')
        translation = item.get('translation', '')
        print(f"  [{i+1}] Original: {original[:80]}{'...' if len(original) > 80 else ''}")
        if translation:
            print(f"      Translation: {translation[:80]}{'...' if len(translation) > 80 else ''}")
        print()

    if len(to_delete) > 10:
        print(f"  ... and {len(to_delete) - 10} more entries")

    print("━" * 60)
    print()
    print("📊 Summary:")
    print(f"  - Current file: {current_count} entries")
    print(f"  - Old file:     {old_count} entries")
    print(f"  - To delete:    {delete_count} entries")
    print(f"  - After sync:   {len(to_keep)} entries")
    print()

    # Ask for confirmation
    response = input(f"❓ Delete these {delete_count} entries from {old_file}? (y/n): ").strip().lower()

    if response not in ['y', 'yes']:
        print("❌ Cancelled. No changes made.")
        sys.exit(0)

    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{old_file}.backup.{timestamp}"

    try:
        with open(old_file, 'r', encoding='utf-8') as f:
            with open(backup_file, 'w', encoding='utf-8') as bf:
                bf.write(f.read())
        print(f"💾 Backup created: {backup_file}")
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        sys.exit(1)

    # Save filtered data
    try:
        with open(old_file, 'w', encoding='utf-8') as f:
            json.dump(to_keep, f, ensure_ascii=False, indent=2)

        new_count = len(to_keep)

        print("✅ Done!")
        print(f"  - Deleted: {delete_count} entries")
        print(f"  - Remaining: {new_count} entries")
        print(f"  - Backup: {backup_file}")

    except Exception as e:
        print(f"❌ Error saving file: {e}")
        print(f"⚠️  Original file backed up at: {backup_file}")
        sys.exit(1)

if __name__ == '__main__':
    main()
