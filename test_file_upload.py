#!/usr/bin/env python3
import os
import sys
import shutil

def test_file_upload(source_file):
    """Test file upload by copying a file to the uploads directory."""
    
    print(f"Testing file upload with: {source_file}")
    
    if not os.path.exists(source_file):
        print(f"ERROR: Source file not found at {source_file}")
        return False
    
    # Create uploads directory if it doesn't exist
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        print(f"Creating uploads directory: {upload_dir}")
        os.makedirs(upload_dir, exist_ok=True)
    
    # Make sure directory has correct permissions
    try:
        os.chmod(upload_dir, 0o755)
        print(f"Set permissions on {upload_dir} to 755")
    except Exception as e:
        print(f"Warning: Could not set permissions: {e}")
    
    # Get filename from path
    filename = os.path.basename(source_file)
    dest_file = os.path.join(upload_dir, filename)
    
    # Copy the file
    try:
        print(f"Copying {source_file} to {dest_file}")
        shutil.copy2(source_file, dest_file)
        
        # Verify file was copied
        if os.path.exists(dest_file):
            file_size = os.path.getsize(dest_file)
            print(f"Success! File copied to {dest_file} ({file_size} bytes)")
            return True
        else:
            print(f"ERROR: File not found at destination {dest_file}")
            return False
    except Exception as e:
        print(f"ERROR: Could not copy file: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_file_upload.py <path_to_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    success = test_file_upload(file_path)
    
    if success:
        print("File upload test PASSED")
        sys.exit(0)
    else:
        print("File upload test FAILED")
        sys.exit(1)