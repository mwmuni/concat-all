# Generic file concatenation utility

import os
import argparse
import fnmatch
import pathlib

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
        
    # Convert path to relative path for matching
    path = str(pathlib.Path(path))
    
    for pattern in gitignore_patterns:
        if pattern.startswith('!'):  # Negated pattern
            continue  # Skip negated patterns for simplicity
        
        # Remove leading slash from pattern for matching
        if pattern.startswith('/'):
            pattern = pattern[1:]
            
        # Trailing slash means directory
        if pattern.endswith('/'):
            if os.path.isdir(path) and fnmatch.fnmatch(path, pattern[:-1] + '*'):
                return True
        elif fnmatch.fnmatch(path, pattern):
            return True
            
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
                comment_prefix: str = '//', use_gitignore: bool = False):
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
    """
    # Handle comma-separated extensions and remove leading dots and spaces
    extensions = [ext.strip('. ') for ext in file_extensions.split(',')]
    use_wildcard = '*' in extensions
    
    # Set output filename
    if use_wildcard:
        output_file = output_file.format(file_extension='all')
    else:
        output_file = output_file.format(file_extension='_'.join(extensions))
    
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
    
    dir_path = os.path.abspath(dir_path)
    for root, dirs, files in os.walk(dir_path):
            
        # Check if current directory should be ignored
        if use_gitignore and should_ignore_path(os.path.relpath(root, dir_path), gitignore_patterns):
            dirs[:] = []  # Don't traverse into ignored directories
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, dir_path)
            
            # Skip the output file itself
            if os.path.abspath(file_path) == os.path.abspath(output_file):
                continue
                
            # Skip files matched by gitignore
            if use_gitignore and should_ignore_path(rel_path, gitignore_patterns):
                continue
                
            file_ext = os.path.splitext(file)[1]
            # Remove leading dot from file extension for comparison
            if file_ext.startswith('.'):
                file_ext = file_ext[1:]
            
            if use_wildcard or file_ext in extensions:
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
    args = parser.parse_args()

    kwargs = {}

    kwargs['dir_path'] = args.dir_path if args.dir_path else os.getcwd()
    if args.output_file_dir:
        os.makedirs(args.output_file_dir, exist_ok=True)
        if not args.output_file:
            args.output_file = 'dump_{file_extension}.txt'
        kwargs['output_file'] = os.path.join(args.output_file_dir, args.output_file)
    if args.comment_prefix:
        kwargs['comment_prefix'] = args.comment_prefix
    if args.gitignore:
        kwargs['use_gitignore'] = True

    concat_files(dir_path=kwargs.pop('dir_path'), file_extensions=args.file_extension, **kwargs)
    
if __name__ == "__main__":
    main()
    