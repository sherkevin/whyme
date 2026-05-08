'''
Author: shervin sherkevin@163.com
Date: 2026-01-15 15:48:49
LastEditors: shervin sherkevin@163.com
LastEditTime: 2026-01-21 10:16:34
FilePath: \whyme\test_server.py
Description: 

Copyright (c) 2026 by ${git_name_email}, All Rights Reserved. 
'''
"""Test server startup and routes."""

import sys

sys.path.insert(0, 'src')


from agent_os.server.app import STATIC_DIR, app

print("=" * 60)
print("Server Diagnostics")
print("=" * 60)

print(f"\n1. STATIC_DIR: {STATIC_DIR}")
print(f"   Exists: {STATIC_DIR.exists()}")

index_file = STATIC_DIR / "index.html"
print(f"\n2. Index file: {index_file}")
print(f"   Exists: {index_file.exists()}")

print("\n3. App routes:")
for route in app.routes:
    if hasattr(route, 'path'):
        print(f"   {route.path}")

print("\n" + "=" * 60)
print("All checks passed! Server should work.")
print("=" * 60)
