#!/usr/bin/env python3
"""
VyaparAI Package Size Analysis Script
Analyzes backend package sizes and compares against AWS Lambda limits
"""

import os
import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Constants
LAMBDA_LIMIT_MB = 250
LAMBDA_LIMIT_BYTES = LAMBDA_LIMIT_MB * 1024 * 1024

def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

def get_dir_size(path: Path) -> int:
    """Calculate total size of directory"""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total += os.path.getsize(filepath)
    except Exception as e:
        print(f"Warning: Error calculating size for {path}: {e}")
    return total

def analyze_requirements_dependencies() -> List[Dict]:
    """Analyze requirements.txt dependencies"""
    requirements_path = Path("backend/requirements.txt")
    if not requirements_path.exists():
        return []
    
    dependencies = []
    try:
        with open(requirements_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '==' in line:
                    package, version = line.split('==', 1)
                    dependencies.append({
                        'package': package.strip(),
                        'version': version.strip(),
                        'size': 'Unknown'  # Would need pip to get actual size
                    })
    except Exception as e:
        print(f"Error reading requirements.txt: {e}")
    
    return dependencies

def check_lambda_packages() -> List[Dict]:
    """Check existing Lambda deployment packages"""
    packages = []
    
    lambda_package_paths = [
        "backend/lambda-deploy",
        "backend/lambda-deploy-simple",
        ".serverless",
        "backend/vyaparai-backend.zip",
        "backend/vyaparai-backend-docker.zip",
        "backend/vyaparai-backend-minimal.zip"
    ]
    
    for package_path in lambda_package_paths:
        path = Path(package_path)
        if path.exists():
            size = get_dir_size(path) if path.is_dir() else path.stat().st_size
            packages.append({
                'path': str(path),
                'size': size,
                'type': 'directory' if path.is_dir() else 'file'
            })
    
    return packages

def analyze_backend_structure() -> Dict:
    """Analyze backend directory structure and sizes"""
    backend_path = Path("backend")
    if not backend_path.exists():
        return {}
    
    structure = {}
    
    # Analyze main directories
    main_dirs = ['app', 'tests', 'alembic', 'scripts', 'lambda-deploy', 'lambda-deploy-simple']
    
    for dir_name in main_dirs:
        dir_path = backend_path / dir_name
        if dir_path.exists():
            size = get_dir_size(dir_path)
            structure[dir_name] = {
                'size': size,
                'files': len(list(dir_path.rglob('*')))
            }
    
    # Analyze specific file types
    file_types = {}
    for file_path in backend_path.rglob('*'):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext not in file_types:
                file_types[ext] = {'count': 0, 'size': 0}
            file_types[ext]['count'] += 1
            file_types[ext]['size'] += file_path.stat().st_size
    
    structure['file_types'] = file_types
    
    return structure

def main():
    print("🔍 VyaparAI Package Size Analysis")
    print("=" * 50)
    
    # Get current working directory
    cwd = Path.cwd()
    print(f"Working Directory: {cwd}")
    
    # Analyze backend directory
    backend_path = Path("backend")
    if not backend_path.exists():
        print("❌ Backend directory not found!")
        return
    
    total_backend_size = get_dir_size(backend_path)
    
    print(f"\n📊 SIZE ANALYSIS")
    print("-" * 30)
    print(f"Total Backend Size: {format_size(total_backend_size)}")
    print(f"AWS Lambda Limit:  {format_size(LAMBDA_LIMIT_BYTES)}")
    
    if total_backend_size > LAMBDA_LIMIT_BYTES:
        print(f"❌ EXCEEDS LIMIT by {format_size(total_backend_size - LAMBDA_LIMIT_BYTES)}")
    else:
        print(f"✅ WITHIN LIMIT ({(total_backend_size / LAMBDA_LIMIT_BYTES) * 100:.1f}% used)")
    
    # Analyze backend structure
    print(f"\n🏗️ BACKEND STRUCTURE")
    print("-" * 30)
    structure = analyze_backend_structure()
    
    for dir_name, info in structure.items():
        if dir_name != 'file_types':
            print(f"{dir_name:20} {format_size(info['size']):>10} ({info['files']} files)")
    
    # Check Lambda packages
    print(f"\n📦 LAMBDA PACKAGES")
    print("-" * 30)
    packages = check_lambda_packages()
    
    if packages:
        for package in packages:
            status = "❌ EXCEEDS" if package['size'] > LAMBDA_LIMIT_BYTES else "✅ WITHIN"
            print(f"{package['path']:40} {format_size(package['size']):>10} {status}")
    else:
        print("No Lambda packages found")
    
    # Analyze dependencies
    print(f"\n📋 DEPENDENCIES")
    print("-" * 30)
    dependencies = analyze_requirements_dependencies()
    
    if dependencies:
        print(f"Found {len(dependencies)} dependencies in requirements.txt")
        print("Top 10 largest packages (estimated):")
        # Note: This would need pip to get actual sizes
        for i, dep in enumerate(dependencies[:10]):
            print(f"  {i+1:2}. {dep['package']:<20} {dep['version']}")
    else:
        print("No requirements.txt found or no dependencies parsed")
    
    # File type analysis
    if 'file_types' in structure:
        print(f"\n📁 FILE TYPE BREAKDOWN")
        print("-" * 30)
        file_types = structure['file_types']
        sorted_types = sorted(file_types.items(), key=lambda x: x[1]['size'], reverse=True)
        
        for ext, info in sorted_types[:10]:
            print(f"{ext:10} {format_size(info['size']):>10} ({info['count']} files)")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print("-" * 30)
    
    if total_backend_size > LAMBDA_LIMIT_BYTES:
        print("❌ Package size exceeds Lambda limit. Consider:")
        print("  1. Use Lambda Layers for heavy dependencies")
        print("  2. Optimize requirements.txt (remove unused packages)")
        print("  3. Use container deployment instead of Lambda")
        print("  4. Split into multiple Lambda functions")
        print("  5. Use .gitignore to exclude unnecessary files")
    else:
        print("✅ Package size is within Lambda limits")
        print("  - Consider monitoring for size increases")
        print("  - Optimize dependencies if needed")
    
    # Generate JSON report
    report = {
        'timestamp': str(Path.cwd()),
        'total_size': total_backend_size,
        'lambda_limit': LAMBDA_LIMIT_BYTES,
        'exceeds_limit': total_backend_size > LAMBDA_LIMIT_BYTES,
        'structure': structure,
        'packages': packages,
        'dependencies_count': len(dependencies)
    }
    
    with open('package-size-report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Report saved to: package-size-report.json")

if __name__ == "__main__":
    main()
