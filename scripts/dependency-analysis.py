#!/usr/bin/env python3
"""
VyaparAI Dependency Analysis Script
Analyzes Python dependencies and suggests optimizations
"""

import os
import subprocess
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

def parse_requirements() -> List[Dict]:
    """Parse requirements.txt and extract package information"""
    requirements_path = Path("backend/requirements.txt")
    if not requirements_path.exists():
        return []
    
    packages = []
    try:
        with open(requirements_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse package specification
                    if '==' in line:
                        package, version = line.split('==', 1)
                        constraint = '=='
                    elif '>=' in line:
                        package, version = line.split('>=', 1)
                        constraint = '>='
                    elif '<=' in line:
                        package, version = line.split('<=', 1)
                        constraint = '<='
                    elif '~=' in line:
                        package, version = line.split('~=', 1)
                        constraint = '~='
                    else:
                        package = line
                        version = 'latest'
                        constraint = 'none'
                    
                    packages.append({
                        'name': package.strip(),
                        'version': version.strip(),
                        'constraint': constraint,
                        'line': line_num,
                        'raw': line
                    })
    except Exception as e:
        print(f"Error parsing requirements.txt: {e}")
    
    return packages

def get_package_size(package_name: str) -> int:
    """Get installed package size (approximate)"""
    try:
        # Try to get package info from pip
        result = subprocess.run([
            'pip', 'show', package_name
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # Extract location from pip show output
            for line in result.stdout.split('\n'):
                if line.startswith('Location:'):
                    location = line.split(':', 1)[1].strip()
                    package_path = Path(location) / package_name.replace('-', '_')
                    if package_path.exists():
                        return sum(f.stat().st_size for f in package_path.rglob('*') if f.is_file())
    except Exception:
        pass
    
    return 0

def find_imports_in_file(file_path: Path) -> Set[str]:
    """Extract all imports from a Python file"""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse AST to find imports
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
    
    return imports

def find_all_imports() -> Dict[str, Set[str]]:
    """Find all imports in the backend codebase"""
    backend_path = Path("backend")
    if not backend_path.exists():
        return {}
    
    imports_by_file = {}
    all_imports = set()
    
    # Find all Python files
    python_files = list(backend_path.rglob("*.py"))
    
    for file_path in python_files:
        if 'node_modules' in str(file_path) or '__pycache__' in str(file_path):
            continue
        
        file_imports = find_imports_in_file(file_path)
        if file_imports:
            imports_by_file[str(file_path)] = file_imports
            all_imports.update(file_imports)
    
    return {
        'by_file': imports_by_file,
        'all_imports': all_imports
    }

def analyze_dependency_usage(packages: List[Dict], imports: Set[str]) -> Dict:
    """Analyze which dependencies are actually used"""
    usage_analysis = {
        'used': [],
        'unused': [],
        'potentially_unused': [],
        'missing': []
    }
    
    # Map package names to their requirements entries
    package_map = {pkg['name'].lower(): pkg for pkg in packages}
    
    # Check each package
    for package in packages:
        package_name = package['name'].lower()
        
        # Handle common package name variations
        variations = [
            package_name,
            package_name.replace('-', '_'),
            package_name.replace('_', '-'),
            package_name.split('[')[0]  # Remove extras like [dev]
        ]
        
        is_used = any(var in imports for var in variations)
        
        if is_used:
            usage_analysis['used'].append(package)
        else:
            # Check if it might be a transitive dependency
            if package_name in ['setuptools', 'wheel', 'pip']:
                usage_analysis['potentially_unused'].append(package)
            else:
                usage_analysis['unused'].append(package)
    
    # Find imports that don't have corresponding packages
    for imp in imports:
        if imp not in package_map and imp not in ['os', 'sys', 'json', 'pathlib', 'typing', 'collections']:
            usage_analysis['missing'].append(imp)
    
    return usage_analysis

def suggest_optimizations(usage_analysis: Dict, packages: List[Dict]) -> List[str]:
    """Generate optimization suggestions"""
    suggestions = []
    
    # Unused packages
    if usage_analysis['unused']:
        suggestions.append(f"Remove {len(usage_analysis['unused'])} unused packages:")
        for pkg in usage_analysis['unused'][:5]:  # Show first 5
            suggestions.append(f"  - {pkg['name']} (line {pkg['line']})")
        if len(usage_analysis['unused']) > 5:
            suggestions.append(f"  ... and {len(usage_analysis['unused']) - 5} more")
    
    # Large packages
    large_packages = []
    for pkg in packages:
        size = get_package_size(pkg['name'])
        if size > 10 * 1024 * 1024:  # 10MB
            large_packages.append((pkg, size))
    
    if large_packages:
        suggestions.append("Consider alternatives for large packages:")
        for pkg, size in sorted(large_packages, key=lambda x: x[1], reverse=True)[:3]:
            suggestions.append(f"  - {pkg['name']}: {size / (1024*1024):.1f}MB")
    
    # Development dependencies
    dev_deps = [pkg for pkg in packages if any(keyword in pkg['name'].lower() 
                                              for keyword in ['test', 'pytest', 'coverage', 'black', 'flake8'])]
    if dev_deps:
        suggestions.append("Move development dependencies to requirements-dev.txt:")
        for pkg in dev_deps[:3]:
            suggestions.append(f"  - {pkg['name']}")
    
    return suggestions

def main():
    print("🔍 VyaparAI Dependency Analysis")
    print("=" * 40)
    
    # Parse requirements
    print("\n📋 Parsing requirements.txt...")
    packages = parse_requirements()
    print(f"Found {len(packages)} packages in requirements.txt")
    
    # Find imports
    print("\n🔍 Analyzing codebase imports...")
    imports_data = find_all_imports()
    all_imports = imports_data.get('all_imports', set())
    print(f"Found {len(all_imports)} unique imports across {len(imports_data.get('by_file', {}))} files")
    
    # Analyze usage
    print("\n📊 Analyzing dependency usage...")
    usage_analysis = analyze_dependency_usage(packages, all_imports)
    
    # Print results
    print(f"\n📈 USAGE ANALYSIS")
    print("-" * 30)
    print(f"Used packages: {len(usage_analysis['used'])}")
    print(f"Unused packages: {len(usage_analysis['unused'])}")
    print(f"Potentially unused: {len(usage_analysis['potentially_unused'])}")
    print(f"Missing packages: {len(usage_analysis['missing'])}")
    
    # Show unused packages
    if usage_analysis['unused']:
        print(f"\n❌ UNUSED PACKAGES")
        print("-" * 30)
        for pkg in usage_analysis['unused'][:10]:  # Show first 10
            print(f"  {pkg['name']:<25} (line {pkg['line']})")
        if len(usage_analysis['unused']) > 10:
            print(f"  ... and {len(usage_analysis['unused']) - 10} more")
    
    # Show missing packages
    if usage_analysis['missing']:
        print(f"\n⚠️  MISSING PACKAGES")
        print("-" * 30)
        for pkg in usage_analysis['missing'][:10]:
            print(f"  {pkg}")
        if len(usage_analysis['missing']) > 10:
            print(f"  ... and {len(usage_analysis['missing']) - 10} more")
    
    # Package size analysis
    print(f"\n📦 PACKAGE SIZE ANALYSIS")
    print("-" * 30)
    
    total_size = 0
    large_packages = []
    
    for pkg in packages[:20]:  # Analyze first 20 packages
        size = get_package_size(pkg['name'])
        total_size += size
        if size > 0:
            large_packages.append((pkg['name'], size))
    
    print(f"Total analyzed size: {total_size / (1024*1024):.1f}MB")
    
    if large_packages:
        print("Largest packages:")
        for name, size in sorted(large_packages, key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {name:<25} {size / (1024*1024):.1f}MB")
    
    # Generate suggestions
    print(f"\n💡 OPTIMIZATION SUGGESTIONS")
    print("-" * 30)
    
    suggestions = suggest_optimizations(usage_analysis, packages)
    
    if suggestions:
        for suggestion in suggestions:
            print(suggestion)
    else:
        print("✅ No major optimizations needed")
    
    # Generate report
    report = {
        'packages_count': len(packages),
        'imports_count': len(all_imports),
        'usage_analysis': {
            'used_count': len(usage_analysis['used']),
            'unused_count': len(usage_analysis['unused']),
            'potentially_unused_count': len(usage_analysis['potentially_unused']),
            'missing_count': len(usage_analysis['missing'])
        },
        'unused_packages': [pkg['name'] for pkg in usage_analysis['unused']],
        'missing_packages': usage_analysis['missing'],
        'large_packages': large_packages,
        'total_size_mb': total_size / (1024*1024)
    }
    
    with open('dependency-analysis-report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Report saved to: dependency-analysis-report.json")

if __name__ == "__main__":
    main()
