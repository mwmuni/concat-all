# Generic file concatenation utility

import os
import argparse
import fnmatch
import pathlib
from datetime import datetime

def should_ignore_path(path, gitignore_patterns=None):
    """
    Check if a path should be ignored based on gitignore patterns.
    
    Args:
        path (str): Path to check
        gitignore_patterns (list): List of gitignore patterns
        
    Returns:
        bool: True if the path should be ignored, False otherwise
    """
    if not gitignore_patterns:
        return False

    path_str = str(pathlib.Path(path))  # Use a different variable name

    negated_patterns = []
    normal_patterns = []

    for p in gitignore_patterns:
        if p.startswith('!'):
            negated_patterns.append(p[1:])
        else:
            normal_patterns.append(p)

    # Check negated patterns first
    for pattern_loop_var in negated_patterns:
        temp_pattern = pattern_loop_var
        if temp_pattern.startswith('/'):
            temp_pattern = temp_pattern[1:]
        
        is_dir_pattern = temp_pattern.endswith('/')
        if is_dir_pattern:
            # Match "dir" itself if it's a directory
            if os.path.isdir(path_str) and fnmatch.fnmatch(path_str, temp_pattern[:-1]):
                return False # Don't ignore
            # Match "dir/anything"
            # Also matches "dir" itself if path_str is "dir" (fnmatch("dir", "dir/*") is false, fnmatch("dir", "dir") is true)
            if fnmatch.fnmatch(path_str, temp_pattern[:-1] + '/*') or \
               fnmatch.fnmatch(path_str, temp_pattern[:-1]):
                # If path_str is "dir" (a file) and pattern is "dir/", 
                # this file "dir" should not be unignored by the pattern "dir/".
                if path_str == temp_pattern[:-1] and not os.path.isdir(path_str):
                    pass 
                else:
                    return False # Don't ignore
        elif fnmatch.fnmatch(path_str, temp_pattern):
            return False # Don't ignore

    # Check normal patterns
    for pattern_loop_var in normal_patterns:
        temp_pattern = pattern_loop_var
        if temp_pattern.startswith('/'):
            temp_pattern = temp_pattern[1:]
            
        is_dir_pattern = temp_pattern.endswith('/')
        if is_dir_pattern:
            # Match "dir" itself if it's a directory
            if os.path.isdir(path_str) and fnmatch.fnmatch(path_str, temp_pattern[:-1]):
                return True # Ignore
            # Match "dir/anything"
            if fnmatch.fnmatch(path_str, temp_pattern[:-1] + '/*') or \
               fnmatch.fnmatch(path_str, temp_pattern[:-1]):
                if path_str == temp_pattern[:-1] and not os.path.isdir(path_str):
                    pass
                else:
                    return True # Ignore
        elif fnmatch.fnmatch(path_str, temp_pattern):
            return True # Ignore
            
    return False

def read_gitignore(dir_path):
    """
    Read .gitignore file and return list of patterns.
    
    Args:
        dir_path (str): Directory path where .gitignore is located
        
    Returns:
        list: List of gitignore patterns
    """
    gitignore_path = os.path.join(dir_path, '.gitignore')
    patterns = []
    
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)
                    
    return patterns

def concat_files(dir_path: str, file_extensions: str, output_file: str = './dump_{file_extension}.txt', 
                comment_prefix: str = '//', use_gitignore: bool = False, filename_suffix: str = '',
                dry_run: bool = False, exclude_patterns: list = None, max_depth: int = -1):
    """
    Concatenate all files with the specified extension(s) under dir_path recursively
    and output to the specified output file.
    
    Args:
        dir_path (str): Directory path to search for files
        file_extensions (str or list): File extension(s) to filter (e.g., '.dart', '.tex')
                                      Can be a single string or a list of extensions
                                      Use '*' for all files
        output_file (str): Path to the output file
        comment_prefix (str): Prefix for comments in the output file
        use_gitignore (bool): Whether to filter files using .gitignore
        filename_suffix (str): Suffix to append to the output file name
    """
    # Handle comma-separated extensions and remove leading dots and spaces
    extensions = [ext.strip('. ') for ext in file_extensions.split(',')]
    use_wildcard = '*' in extensions
    
    # Set output filename
    if use_wildcard:
        output_file = output_file.format(file_extension='all')
    else:
        output_file = output_file.format(file_extension='_'.join(extensions))

    if filename_suffix:
        if '{timestamp}' in filename_suffix:
            filename_suffix = filename_suffix.replace('{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S'))
        if '{unixtime}' in filename_suffix:
            filename_suffix = filename_suffix.replace('{unixtime}', str(int(datetime.now().timestamp())))
        base, ext = os.path.splitext(output_file)
        output_file = f"{base}{filename_suffix}{ext}"

    if dry_run:
        print("Dry run mode enabled.")
        print(f"Output file would be: {os.path.abspath(output_file)}")
    else:
        if os.path.isfile(output_file):
            os.remove(output_file)
    
    # Read gitignore if needed
    gitignore_patterns = []
    if use_gitignore:
        gitignore_patterns = read_gitignore(dir_path)
        # Add .git directory to the patterns when using gitignore
        if '.git' not in gitignore_patterns:
            gitignore_patterns.append('.git/')
        if '.gitignore' not in gitignore_patterns:
            gitignore_patterns.append('.gitignore')

    if exclude_patterns is None:
        exclude_patterns = []
    
    dir_path = os.path.abspath(dir_path)
    # Calculate initial depth based on the absolute path
    # Normalize dir_path to remove any trailing slash for consistent depth calculation
    initial_depth = os.path.normpath(dir_path).count(os.sep)

    for root, dirs, files in os.walk(dir_path):
        current_abs_path = os.path.abspath(root)
        # Calculate current depth
        current_path_depth = os.path.normpath(current_abs_path).count(os.sep)
        relative_depth = current_path_depth - initial_depth

        # Apply max_depth logic
        if max_depth != -1 and relative_depth >= max_depth:
            if dry_run:
                print(f"Max depth ({max_depth}) reached. Not traversing further from: {os.path.relpath(root, dir_path) or '.'}")
            dirs[:] = [] # Prune subdirectories from further traversal

        current_rel_dir_path = os.path.relpath(root, dir_path)
        if current_rel_dir_path == ".": # Avoid "./" for root dir matching
            current_rel_dir_path = ""

        # Check if current directory should be ignored by gitignore (this should happen after depth check if depth is 0)
        # If max_depth is 0, we process files in root, then clear dirs. Gitignore on root itself still applies.
        if use_gitignore and should_ignore_path(current_rel_dir_path, gitignore_patterns):
            if dry_run:
                print(f"Ignoring directory (gitignore): {current_rel_dir_path if current_rel_dir_path else os.path.basename(root)}")
            dirs[:] = [] # Also prune if gitignored
            continue
        
        # Filter subdirectories based on --exclude patterns. This should also respect max_depth.
        # If dirs are already cleared by max_depth, this loop won't run or won't matter.
        original_dirs = list(dirs) 
        dirs[:] = [] 
        for d in original_dirs:
            dir_rel_path = os.path.join(current_rel_dir_path, d)
            excluded_by_custom_pattern = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(dir_rel_path, pattern) or fnmatch.fnmatch(dir_rel_path + '/', pattern):
                    if dry_run:
                        print(f"Excluding directory (--exclude pattern '{pattern}'): {dir_rel_path}")
                    excluded_by_custom_pattern = True
                    break
            if not excluded_by_custom_pattern:
                dirs.append(d)
        
        for file in files:
            file_path = os.path.join(root, file)
            # Use current_rel_dir_path for file's relative path to ensure consistency
            rel_path = os.path.join(current_rel_dir_path, file) 
            
            # Skip the output file itself
            if os.path.abspath(file_path) == os.path.abspath(output_file):
                continue
                
            # Skip files matched by gitignore
            if use_gitignore and should_ignore_path(rel_path, gitignore_patterns):
                if dry_run: # Optional: log gitignore skips for files too
                    print(f"Ignoring file (gitignore): {rel_path}")
                continue

            # Skip files matched by --exclude patterns
            excluded_by_user_pattern = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(rel_path, pattern):
                    if dry_run:
                        print(f"Excluding file (--exclude pattern '{pattern}'): {rel_path}")
                    else:
                        # Optional: print even if not dry_run, as per instructions
                        print(f"Excluding file (--exclude pattern '{pattern}'): {rel_path}")
                    excluded_by_user_pattern = True
                    break
            if excluded_by_user_pattern:
                continue
                
            file_ext = os.path.splitext(file)[1]
            # Remove leading dot from file extension for comparison
            if file_ext.startswith('.'):
                file_ext = file_ext[1:]
            
            if use_wildcard or file_ext in extensions:
                if dry_run:
                    print(f"Would concatenate: {file_path}")
                else:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        with open(output_file, 'a', encoding='utf-8') as dump_file:
                            dump_file.write(f"{comment_prefix} File: {file_path}\n{content}\n\n")
                    except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                        # Skip binary files and files we can't read
                        pass

def main():
    # Example usage
    parser = argparse.ArgumentParser(description='Concatenate files with the specified extension(s) under the given directory.')
    parser.add_argument('file_extension', type=str, help='File extension(s) to filter (e.g., "txt", "dart" or "txt,dart,py"). Use "*" for all files. Leading dots are optional.')
    parser.add_argument('--dir_path', '-d', type=str, help='Path to the directory containing the files to concatenate')
    parser.add_argument('--output_file', '-o', type=str, help='Path to the output file')
    parser.add_argument('--output_file_dir', '-D', type=str, help='Path to the directory for the output file')
    parser.add_argument('--comment_prefix', '-c', type=str, help='Prefix for comments in the output file')
    parser.add_argument('--gitignore', '-i', action='store_true', help='Filter files using .gitignore')
    parser.add_argument('--filename_suffix', type=str, help='Suffix to append to the output filename (supports {timestamp}, {unixtime})')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Enable dry run mode. Shows files that would be concatenated without actually writing them.')
    parser.add_argument('--exclude', type=str, help='Comma-separated list of glob patterns to exclude files/directories (e.g., "*.log,temp/*,specific_file.py")')
    parser.add_argument('--max-depth', type=int, default=-1, help='Maximum recursion depth. 0 for current directory, 1 for current + direct children, etc. Default: -1 (unlimited).')
    args = parser.parse_args()

    kwargs = {}
    kwargs['dir_path'] = args.dir_path if args.dir_path else os.getcwd()
    if args.output_file_dir:
        os.makedirs(args.output_file_dir, exist_ok=True)
        if not args.output_file:
            args.output_file = 'dump_{file_extension}.txt'
        kwargs['output_file'] = os.path.join(args.output_file_dir, args.output_file)
    if args.output_file:
        kwargs['output_file'] = args.output_file
    if args.comment_prefix:
        kwargs['comment_prefix'] = args.comment_prefix
    if args.gitignore:
        kwargs['use_gitignore'] = True
    if args.filename_suffix:
        kwargs['filename_suffix'] = args.filename_suffix
    if args.dry_run:
        kwargs['dry_run'] = True
    if args.exclude:
        kwargs['exclude_patterns'] = [p.strip() for p in args.exclude.split(',')]
    if args.max_depth is not None: # Will always be true due to default, but good practice
        kwargs['max_depth'] = args.max_depth

    concat_files(dir_path=kwargs.pop('dir_path'), file_extensions=args.file_extension, **kwargs)
    
if __name__ == "__main__":
    main()

