#!/usr/bin/env python3
"""
VyaparAI Feature Documentation Scanner

This script scans the codebase to identify features and generate/update documentation.
It helps maintain up-to-date documentation by automatically detecting:
- React components
- API endpoints
- Database tables
- Configuration files
- New features

Usage:
    python3 docs/scan_features.py [--update] [--output FORMAT]

Options:
    --update    Update existing documentation files
    --output    Output format: markdown (default), json, html
"""

import os
import re
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set
import argparse

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend-pwa"
BACKEND_DIR = PROJECT_ROOT / "backend"
DOCS_DIR = PROJECT_ROOT / "docs"


class FeatureScanner:
    """Scans the codebase for features and components"""

    def __init__(self):
        self.features = {
            'components': [],
            'pages': [],
            'api_endpoints': [],
            'services': [],
            'database_tables': [],
            'lambda_functions': [],
            'recent_changes': []
        }

    def scan_react_components(self) -> List[Dict]:
        """Scan for React components in frontend"""
        components = []

        # Scan component directories
        component_dirs = [
            FRONTEND_DIR / "src" / "components",
            FRONTEND_DIR / "src" / "pages"
        ]

        for comp_dir in component_dirs:
            if not comp_dir.exists():
                continue

            for tsx_file in comp_dir.rglob("*.tsx"):
                with open(tsx_file, 'r', encoding='utf-8') as f:
                    try:
                        content = f.read()

                        # Extract component name from filename or export
                        comp_name = tsx_file.stem

                        # Look for component description in comments
                        description = self._extract_description(content)

                        # Check if it's a new file (modified in last 7 days)
                        mtime = os.path.getmtime(tsx_file)
                        is_recent = (datetime.now().timestamp() - mtime) < (7 * 24 * 3600)

                        # Extract props interface
                        props = self._extract_props(content)

                        # Extract features/functionality
                        features = self._extract_features(content)

                        components.append({
                            'name': comp_name,
                            'path': str(tsx_file.relative_to(PROJECT_ROOT)),
                            'type': 'page' if 'pages' in str(tsx_file) else 'component',
                            'description': description,
                            'props': props,
                            'features': features,
                            'recent': is_recent,
                            'last_modified': datetime.fromtimestamp(mtime).isoformat()
                        })
                    except Exception as e:
                        print(f"Error scanning {tsx_file}: {e}")

        return components

    def scan_api_endpoints(self) -> List[Dict]:
        """Scan for API endpoints in backend"""
        endpoints = []

        # Scan FastAPI routers
        api_dir = BACKEND_DIR / "app" / "api"
        if not api_dir.exists():
            return endpoints

        for py_file in api_dir.rglob("*.py"):
            if py_file.name.startswith('__'):
                continue

            with open(py_file, 'r', encoding='utf-8') as f:
                try:
                    content = f.read()

                    # Find route decorators
                    routes = re.findall(r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', content)

                    for method, path in routes:
                        # Extract function name and description
                        func_match = re.search(rf'@router\.{method}\(["\']' + re.escape(path) + r'["\'].*?\n\s*(?:async\s+)?def\s+(\w+)', content, re.DOTALL)
                        func_name = func_match.group(1) if func_match else 'unknown'

                        # Extract docstring
                        docstring = self._extract_docstring(content, func_name)

                        endpoints.append({
                            'method': method.upper(),
                            'path': path,
                            'function': func_name,
                            'file': str(py_file.relative_to(PROJECT_ROOT)),
                            'description': docstring
                        })
                except Exception as e:
                    print(f"Error scanning {py_file}: {e}")

        return endpoints

    def scan_database_tables(self) -> List[Dict]:
        """Scan for database table configurations"""
        tables = []

        # Check for DynamoDB table names in code
        files_to_scan = list((BACKEND_DIR / "app").rglob("*.py"))

        table_pattern = re.compile(r"(?:Table\(|TABLE\s*=\s*)['\"]([a-zA-Z0-9_-]+)['\"]")

        found_tables = set()
        for py_file in files_to_scan:
            with open(py_file, 'r', encoding='utf-8') as f:
                try:
                    content = f.read()
                    matches = table_pattern.findall(content)
                    for table_name in matches:
                        if table_name not in found_tables and 'vyaparai' in table_name.lower():
                            found_tables.add(table_name)
                            tables.append({
                                'name': table_name,
                                'found_in': str(py_file.relative_to(PROJECT_ROOT))
                            })
                except Exception as e:
                    print(f"Error scanning {py_file}: {e}")

        return tables

    def scan_lambda_functions(self) -> List[Dict]:
        """Scan for Lambda function configurations"""
        lambdas = []

        # Check backend directory for Lambda handlers
        if (BACKEND_DIR / "lambda_handler.py").exists():
            lambdas.append({
                'name': 'vyaparai-api-prod',
                'handler': 'lambda_handler.py',
                'description': 'Main API Lambda function'
            })

        # Check for other Lambda directories
        for dir_path in BACKEND_DIR.glob("lambda-*"):
            if dir_path.is_dir():
                lambdas.append({
                    'name': dir_path.name,
                    'path': str(dir_path.relative_to(PROJECT_ROOT)),
                    'description': f'Lambda function: {dir_path.name}'
                })

        return lambdas

    def _extract_description(self, content: str) -> str:
        """Extract description from comments or docstrings"""
        # Look for JSDoc-style comments
        match = re.search(r'/\*\*\s*\n\s*\*\s*(.+?)(?:\n\s*\*\s*@|\n\s*\*/)', content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Look for single-line comments at the top
        lines = content.split('\n')
        for line in lines[:20]:
            if line.strip().startswith('// ') or line.strip().startswith('* '):
                desc = line.strip().lstrip('/*').strip()
                if len(desc) > 20:
                    return desc

        return ""

    def _extract_props(self, content: str) -> List[str]:
        """Extract props interface from React component"""
        props = []

        # Look for interface or type definition
        match = re.search(r'interface\s+\w+Props\s*{([^}]+)}', content)
        if match:
            props_content = match.group(1)
            prop_lines = re.findall(r'(\w+)(?:\?)?\s*:', props_content)
            props = prop_lines

        return props

    def _extract_features(self, content: str) -> List[str]:
        """Extract feature descriptions from comments"""
        features = []

        # Look for feature lists in comments
        if 'Features:' in content or 'features:' in content:
            lines = content.split('\n')
            in_features = False
            for line in lines:
                if 'Features:' in line or 'features:' in line:
                    in_features = True
                    continue
                if in_features:
                    if line.strip().startswith('- ') or line.strip().startswith('* '):
                        feature = line.strip().lstrip('-*').strip()
                        features.append(feature)
                    elif line.strip() and not line.strip().startswith('//') and not line.strip().startswith('*'):
                        break

        return features

    def _extract_docstring(self, content: str, func_name: str) -> str:
        """Extract function docstring"""
        pattern = rf'def\s+{re.escape(func_name)}.*?:\s*"""(.+?)"""'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        pattern = rf'def\s+{re.escape(func_name)}.*?:\s*\'\'\'(.+?)\'\'\''
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        return ""

    def scan_all(self):
        """Scan all features in the codebase"""
        print("Scanning React components...")
        components = self.scan_react_components()
        self.features['components'] = [c for c in components if c['type'] == 'component']
        self.features['pages'] = [c for c in components if c['type'] == 'page']

        print("Scanning API endpoints...")
        self.features['api_endpoints'] = self.scan_api_endpoints()

        print("Scanning database tables...")
        self.features['database_tables'] = self.scan_database_tables()

        print("Scanning Lambda functions...")
        self.features['lambda_functions'] = self.scan_lambda_functions()

        # Find recent changes
        all_items = (self.features['components'] + self.features['pages'])
        self.features['recent_changes'] = [
            item for item in all_items if item.get('recent', False)
        ]

        return self.features

    def generate_markdown(self) -> str:
        """Generate markdown documentation"""
        md = []
        md.append("# VyaparAI Feature Documentation")
        md.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Recent changes
        if self.features['recent_changes']:
            md.append("## Recent Changes (Last 7 Days)\n")
            for item in self.features['recent_changes']:
                md.append(f"- **{item['name']}** ({item['path']})")
                if item.get('description'):
                    md.append(f"  - {item['description']}")
            md.append("")

        # Components
        md.append("## Components\n")
        for comp in self.features['components']:
            md.append(f"### {comp['name']}")
            md.append(f"**Location**: `{comp['path']}`\n")
            if comp.get('description'):
                md.append(f"{comp['description']}\n")
            if comp.get('features'):
                md.append("**Features**:")
                for feature in comp['features']:
                    md.append(f"- {feature}")
                md.append("")
            if comp.get('props'):
                md.append(f"**Props**: {', '.join(comp['props'])}\n")
            md.append("")

        # Pages
        md.append("## Pages\n")
        for page in self.features['pages']:
            md.append(f"### {page['name']}")
            md.append(f"**Location**: `{page['path']}`\n")
            if page.get('description'):
                md.append(f"{page['description']}\n")
            md.append("")

        # API Endpoints
        md.append("## API Endpoints\n")
        current_file = None
        for endpoint in sorted(self.features['api_endpoints'], key=lambda x: x['file']):
            if endpoint['file'] != current_file:
                current_file = endpoint['file']
                md.append(f"\n### {current_file}\n")
            md.append(f"- **{endpoint['method']}** `{endpoint['path']}`")
            if endpoint.get('description'):
                md.append(f"  - {endpoint['description']}")
        md.append("")

        # Database Tables
        md.append("## Database Tables\n")
        for table in self.features['database_tables']:
            md.append(f"- **{table['name']}** (found in `{table['found_in']}`)")
        md.append("")

        # Lambda Functions
        md.append("## Lambda Functions\n")
        for lambda_func in self.features['lambda_functions']:
            md.append(f"- **{lambda_func['name']}**: {lambda_func.get('description', 'No description')}")
        md.append("")

        return "\n".join(md)

    def save_documentation(self, output_format='markdown'):
        """Save documentation to files"""
        timestamp = datetime.now().strftime('%Y%m%d')

        if output_format == 'markdown':
            output_file = DOCS_DIR / f"FEATURES_{timestamp}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_markdown())
            print(f"\n✅ Documentation saved to: {output_file}")

        elif output_format == 'json':
            output_file = DOCS_DIR / f"features_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.features, f, indent=2)
            print(f"\n✅ JSON output saved to: {output_file}")

        return output_file


def main():
    parser = argparse.ArgumentParser(description='Scan VyaparAI codebase for features')
    parser.add_argument('--output', choices=['markdown', 'json'], default='markdown',
                       help='Output format (default: markdown)')
    parser.add_argument('--update', action='store_true',
                       help='Update existing documentation files')

    args = parser.parse_args()

    print("=" * 60)
    print("VyaparAI Feature Documentation Scanner")
    print("=" * 60)

    scanner = FeatureScanner()
    features = scanner.scan_all()

    # Print summary
    print(f"\n📊 Scan Summary:")
    print(f"   Components: {len(features['components'])}")
    print(f"   Pages: {len(features['pages'])}")
    print(f"   API Endpoints: {len(features['api_endpoints'])}")
    print(f"   Database Tables: {len(features['database_tables'])}")
    print(f"   Lambda Functions: {len(features['lambda_functions'])}")
    print(f"   Recent Changes: {len(features['recent_changes'])}")

    # Save documentation
    output_file = scanner.save_documentation(args.output)

    print(f"\n✅ Feature scan complete!")
    print(f"📄 Documentation: {output_file}")


if __name__ == '__main__':
    main()
