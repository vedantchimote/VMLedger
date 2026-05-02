#!/usr/bin/env python
"""
Verify that the VMLedger setup is correct.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_imports():
    """Check that all core modules can be imported."""
    print("Checking imports...")
    
    try:
        from vmledger import config
        print("✓ vmledger.config")
    except ImportError as e:
        print(f"✗ vmledger.config: {e}")
        return False
    
    try:
        from vmledger import logging_config
        print("✓ vmledger.logging_config")
    except ImportError as e:
        print(f"✗ vmledger.logging_config: {e}")
        return False
    
    try:
        from vmledger import database
        print("✓ vmledger.database")
    except ImportError as e:
        print(f"✗ vmledger.database: {e}")
        return False
    
    try:
        from vmledger import celery_app
        print("✓ vmledger.celery_app")
    except ImportError as e:
        print(f"✗ vmledger.celery_app: {e}")
        return False
    
    try:
        from vmledger import main
        print("✓ vmledger.main")
    except ImportError as e:
        print(f"✗ vmledger.main: {e}")
        return False
    
    return True


def check_structure():
    """Check that all required directories exist."""
    print("\nChecking directory structure...")
    
    required_dirs = [
        "vmledger",
        "vmledger/api",
        "vmledger/models",
        "vmledger/schemas",
        "vmledger/services",
        "vmledger/tasks",
        "tests",
        "tests/unit",
        "tests/properties",
        "tests/integration",
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print(f"✓ {dir_path}/")
        else:
            print(f"✗ {dir_path}/ (missing)")
            all_exist = False
    
    return all_exist


def check_files():
    """Check that all required files exist."""
    print("\nChecking required files...")
    
    required_files = [
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "README.md",
        "vmledger/__init__.py",
        "vmledger/config.py",
        "vmledger/database.py",
        "vmledger/logging_config.py",
        "vmledger/celery_app.py",
        "vmledger/main.py",
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.isfile(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} (missing)")
            all_exist = False
    
    return all_exist


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("VMLedger Setup Verification")
    print("=" * 60)
    
    checks = [
        ("Directory Structure", check_structure),
        ("Required Files", check_files),
        ("Module Imports", check_imports),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} check failed with error: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All checks passed! Setup is complete.")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and configure your settings")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Set up PostgreSQL and Redis")
        print("4. Run the application: uvicorn vmledger.main:app --reload")
        return 0
    else:
        print("\n✗ Some checks failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
