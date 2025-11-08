#!/usr/bin/env python3
"""
VyaparAI Lambda Package Cleanup Script
Safely removes unnecessary files to reduce package size
"""

import os
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime

class LambdaPackageCleanup:
    def __init__(self, backend_path="backend"):
        self.backend_path = Path(backend_path)
        self.removed_files = []
        self.removed_sizes = {}
        self.size_before = 0
        self.size_after = 0
        self.backup_dir = None
        
    def get_directory_size(self, path):
        """Calculate directory size in bytes"""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        pass
        except Exception as e:
            print(f"Warning: Error calculating size for {path}: {e}")
        return total
    
    def format_size(self, size_bytes):
        """Format bytes to human readable size"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    def create_backup(self):
        """Create backup of important files before cleanup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = Path(f"backup_before_cleanup_{timestamp}")
        
        print(f"📦 Creating backup in: {self.backup_dir}")
        
        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)
        
        # Backup important files
        important_files = [
            "requirements.txt",
            "pyproject.toml",
            "lambda_handler.py",
            "main.py"
        ]
        
        for file_name in important_files:
            file_path = self.backend_path / file_name
            if file_path.exists():
                backup_path = self.backup_dir / file_name
                shutil.copy2(file_path, backup_path)
                print(f"  Backed up: {file_name}")
    
    def find_unnecessary_files(self):
        """Find files that can be safely removed"""
        unnecessary_files = []
        
        print("🔍 Scanning for unnecessary files...")
        
        for root, dirs, files in os.walk(self.backend_path):
            root_path = Path(root)
            
            # Remove __pycache__ directories
            if "__pycache__" in dirs:
                cache_path = root_path / "__pycache__"
                unnecessary_files.append(str(cache_path))
                dirs.remove("__pycache__")  # Don't traverse into it
            
            # Remove .pytest_cache directories
            if ".pytest_cache" in dirs:
                pytest_cache_path = root_path / ".pytest_cache"
                unnecessary_files.append(str(pytest_cache_path))
                dirs.remove(".pytest_cache")
            
            # Remove node_modules if any
            if "node_modules" in dirs:
                node_modules_path = root_path / "node_modules"
                unnecessary_files.append(str(node_modules_path))
                dirs.remove("node_modules")
            
            # Remove .git directories if accidentally included
            if ".git" in dirs:
                git_path = root_path / ".git"
                unnecessary_files.append(str(git_path))
                dirs.remove(".git")
            
            for file in files:
                filepath = root_path / file
                
                # Remove zip files (except deployment-related ones)
                if file.endswith('.zip'):
                    # Keep lambda-deploy-simple.zip as it's small and needed
                    if 'lambda-deploy-simple' not in str(filepath):
                        unnecessary_files.append(str(filepath))
                
                # Remove compiled binaries
                if file.endswith('.so'):
                    unnecessary_files.append(str(filepath))
                
                # Remove compiled Python files
                if file.endswith('.pyc') or file.endswith('.pyo'):
                    unnecessary_files.append(str(filepath))
                
                # Remove temporary files
                if (file.startswith('.') and file.endswith('.tmp')) or file.endswith('.temp'):
                    unnecessary_files.append(str(filepath))
                
                # Remove macOS system files
                if file == '.DS_Store':
                    unnecessary_files.append(str(filepath))
                
                # Remove IDE files
                if file.endswith('.swp') or file.endswith('.swo'):
                    unnecessary_files.append(str(filepath))
        
        return unnecessary_files
    
    def safe_remove(self, path):
        """Safely remove file or directory"""
        try:
            path_obj = Path(path)
            
            # Get size before removal
            if path_obj.is_file():
                size = path_obj.stat().st_size
            elif path_obj.is_dir():
                size = self.get_directory_size(path_obj)
            else:
                size = 0
            
            # Remove the file/directory
            if path_obj.is_dir():
                shutil.rmtree(path_obj)
                print(f"  Removed directory: {path} ({self.format_size(size)})")
            else:
                path_obj.unlink()
                print(f"  Removed file: {path} ({self.format_size(size)})")
            
            self.removed_files.append(path)
            self.removed_sizes[path] = size
            return True
            
        except Exception as e:
            print(f"  Error removing {path}: {e}")
            return False
    
    def cleanup(self):
        """Perform the cleanup process"""
        print("🧹 VyaparAI Lambda Package Cleanup")
        print("=" * 50)
        
        # Check if backend directory exists
        if not self.backend_path.exists():
            print(f"❌ Backend directory not found: {self.backup_path}")
            return False
        
        # Get initial size
        print("📊 Calculating initial package size...")
        self.size_before = self.get_directory_size(self.backend_path)
        print(f"Initial package size: {self.format_size(self.size_before)}")
        
        # Create backup
        self.create_backup()
        
        # Find unnecessary files
        unnecessary_files = self.find_unnecessary_files()
        print(f"Found {len(unnecessary_files)} unnecessary files/directories")
        
        if not unnecessary_files:
            print("✅ No unnecessary files found!")
            return True
        
        # Show what will be removed
        print(f"\n🗑️  Files/directories to be removed:")
        total_removal_size = 0
        for file_path in unnecessary_files[:10]:  # Show first 10
            path_obj = Path(file_path)
            if path_obj.exists():
                if path_obj.is_file():
                    size = path_obj.stat().st_size
                else:
                    size = self.get_directory_size(path_obj)
                total_removal_size += size
                print(f"  - {file_path} ({self.format_size(size)})")
        
        if len(unnecessary_files) > 10:
            print(f"  ... and {len(unnecessary_files) - 10} more files")
        
        print(f"Estimated removal size: {self.format_size(total_removal_size)}")
        
        # Confirm cleanup
        response = input(f"\n⚠️  Proceed with cleanup? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Cleanup cancelled")
            return False
        
        # Remove files
        print(f"\n🗑️  Removing unnecessary files...")
        removed_count = 0
        total_removed_size = 0
        
        for file_path in unnecessary_files:
            if self.safe_remove(file_path):
                removed_count += 1
                total_removed_size += self.removed_sizes.get(file_path, 0)
        
        # Get final size
        print(f"\n📊 Calculating final package size...")
        self.size_after = self.get_directory_size(self.backend_path)
        size_reduction = self.size_before - self.size_after
        
        # Generate report
        print(f"\n✅ CLEANUP COMPLETE")
        print("=" * 30)
        print(f"Files/directories removed: {removed_count}")
        print(f"Size before: {self.format_size(self.size_before)}")
        print(f"Size after: {self.format_size(self.size_after)}")
        print(f"Size reduction: {self.format_size(size_reduction)}")
        print(f"Reduction percentage: {(size_reduction/self.size_before)*100:.1f}%")
        
        # Check Lambda limits
        lambda_limit = 250 * 1024 * 1024  # 250 MB
        if self.size_after < lambda_limit:
            print(f"\n🎉 SUCCESS: Package now within Lambda limits!")
            print(f"   Current size: {self.format_size(self.size_after)}")
            print(f"   Lambda limit: {self.format_size(lambda_limit)}")
            print(f"   Available margin: {self.format_size(lambda_limit - self.size_after)}")
        else:
            print(f"\n⚠️  Still over Lambda limit")
            print(f"   Current size: {self.format_size(self.size_after)}")
            print(f"   Lambda limit: {self.format_size(lambda_limit)}")
            print(f"   Over by: {self.format_size(self.size_after - lambda_limit)}")
        
        # Save cleanup report
        self.save_cleanup_report()
        
        return True
    
    def save_cleanup_report(self):
        """Save cleanup report to JSON file"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'size_before': self.size_before,
            'size_after': self.size_after,
            'size_reduction': self.size_before - self.size_after,
            'reduction_percentage': ((self.size_before - self.size_after) / self.size_before) * 100,
            'files_removed': len(self.removed_files),
            'removed_files': self.removed_files,
            'removed_sizes': {k: v for k, v in self.removed_sizes.items()},
            'lambda_limit_bytes': 250 * 1024 * 1024,
            'within_limits': self.size_after < (250 * 1024 * 1024)
        }
        
        report_file = Path('cleanup-report.json')
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Cleanup report saved to: {report_file}")
    
    def validate_functionality(self):
        """Validate that critical functionality still works"""
        print(f"\n🔍 Validating functionality...")
        
        # Check if critical files exist
        critical_files = [
            "backend/requirements.txt",
            "backend/lambda-deploy-simple/lambda_handler.py",
            "backend/app/main.py"
        ]
        
        missing_files = []
        for file_path in critical_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ Missing critical files:")
            for file_path in missing_files:
                print(f"  - {file_path}")
            return False
        else:
            print(f"✅ All critical files present")
        
        # Check Python syntax
        print(f"🔍 Checking Python syntax...")
        try:
            result = subprocess.run([
                'python3', '-m', 'py_compile', 'backend/lambda-deploy-simple/lambda_handler.py'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Python syntax is valid")
            else:
                print(f"❌ Python syntax errors:")
                print(result.stderr)
                return False
        except Exception as e:
            print(f"⚠️  Could not validate Python syntax: {e}")
        
        return True

def main():
    cleanup = LambdaPackageCleanup()
    
    # Perform cleanup
    success = cleanup.cleanup()
    
    if success:
        # Validate functionality
        cleanup.validate_functionality()
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Run package size analysis: python3 scripts/analyze-package-size.py")
        print(f"2. Test local backend: cd backend && python3 -m uvicorn app.main:app --reload")
        print(f"3. Test endpoints: ./scripts/test-endpoints-simple.sh")
        print(f"4. Deploy optimized package to Lambda")
    else:
        print(f"\n❌ Cleanup failed or was cancelled")

if __name__ == "__main__":
    main()
