# Generic file concatenation utility

import os
import argparse
import fnmatch
import pathlib
import re
import shutil
from datetime import datetime

import pathspec

def should_ignore_path(path, gitignore_patterns=None, base_dir=None):
    """Return True if ``path`` should be ignored according to ``gitignore_patterns``."""

    if not gitignore_patterns:
        return False

    path_str = str(pathlib.Path(path))
    abs_path = os.path.join(base_dir, path_str) if base_dir else path_str

    ignore = False
    for raw_pat in gitignore_patterns:
        negated = raw_pat.startswith('!')
        pat = raw_pat[1:] if negated else raw_pat
        if pat.startswith('/'):
            pat = pat[1:]

        if pat.endswith('/'):
            base_pat = pat[:-1]
            if (os.path.isdir(abs_path) and fnmatch.fnmatch(path_str, base_pat)) or \
               fnmatch.fnmatch(path_str, base_pat) or fnmatch.fnmatch(path_str, base_pat + '/*'):
                ignore = not negated
        else:
            if fnmatch.fnmatch(path_str, pat):
                ignore = not negated

    if ignore and os.path.isdir(abs_path):
        # If any negated pattern targets a path inside this directory, keep it
        for raw_pat in gitignore_patterns:
            if not raw_pat.startswith('!'):
                continue
            pat = raw_pat[1:]
            if pat.startswith('/'):
                pat = pat[1:]
            if pat.startswith(path_str.rstrip('/') + '/'):
                ignore = False
                break

    return ignore

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

def _normalize_rel_posix(path: str) -> str:
    rel = os.path.normpath(path)
    if rel == '.':
        rel = ''
    return rel.replace('\\', '/')

def _load_gitignore_lines(gitignore_file_path: str):
    if not os.path.isfile(gitignore_file_path):
        return []
    lines = []
    with open(gitignore_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                lines.append(line)
    return lines

def _prefix_gitignore_pattern(pattern: str, rel_dir_posix: str) -> str:
    if not rel_dir_posix:
        return pattern

    neg = pattern.startswith('!')
    raw = pattern[1:] if neg else pattern
    if not raw:
        return pattern

    if raw.startswith('/'):
        raw = raw[1:]

    if '/' not in raw:
        prefixed = f"{rel_dir_posix}/**/{raw}"
    else:
        prefixed = f"{rel_dir_posix}/{raw}"

    return f"!{prefixed}" if neg else prefixed

def _build_gitignore_spec(root_dir: str, max_depth: int):
    root_dir = os.path.abspath(root_dir)
    spec = pathspec.GitIgnoreSpec.from_lines([
        '.git/',
        '.gitignore',
    ])

    initial_depth = os.path.normpath(root_dir).count(os.sep)
    for current_dir, dirs, files in os.walk(root_dir):
        current_abs_path = os.path.abspath(current_dir)
        current_path_depth = os.path.normpath(current_abs_path).count(os.sep)
        rel_depth = current_path_depth - initial_depth

        if max_depth != -1 and rel_depth > max_depth:
            dirs[:] = []
            continue

        rel_dir = os.path.relpath(current_dir, root_dir)
        rel_dir_posix = _normalize_rel_posix(rel_dir)

        gitignore_file = os.path.join(current_dir, '.gitignore')
        lines = _load_gitignore_lines(gitignore_file)
        if lines:
            adjusted = [_prefix_gitignore_pattern(pat, rel_dir_posix) for pat in lines]
            spec += pathspec.GitIgnoreSpec.from_lines(adjusted)

    return spec

def concat_files(dir_path: str, file_extensions: str, output_file: str = './dump_{file_extension}.txt', 
                comment_prefix: str = '//', use_gitignore: bool = False, filename_suffix: str = '',
                dry_run: bool = False, exclude_patterns: list = None, exclude_regex_patterns: list = None,
                max_depth: int = -1, force: bool = False, append: bool = False, verbose: bool = False,
                strict: bool = False, encoding: str = 'utf-8-sig', errors: str = 'strict',
                max_bytes: int = -1, max_files: int = -1, include_tree: bool = False,
                follow_symlinks: bool = True):
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
        exclude_patterns (list): Glob patterns to exclude
        exclude_regex_patterns (list): Regex patterns to exclude
    """
    # Handle comma-separated extensions and remove leading dots and spaces
    raw_extensions = [ext.strip() for ext in file_extensions.split(',') if ext.strip()]
    extensions = []
    use_wildcard = False
    for ext in raw_extensions:
        if ext in {'*', '*.*'}:
            use_wildcard = True
            continue
        if ext.startswith('*.'):
            ext = ext[2:]
        ext = ext.strip('. ')
        if ext == '*':
            use_wildcard = True
        elif ext:
            extensions.append(ext)
    extensions_set = set(extensions)
    
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

    output_file_abs = os.path.abspath(output_file)
    if dry_run:
        print("Dry run mode enabled.")
        print(f"Output file would be: {output_file_abs}")
        output_handle = None
    else:
        if os.path.exists(output_file_abs) and not append and not force:
            print(f"Refusing to overwrite existing output file (use --force or --append): {output_file_abs}")
            return 2
        if not append and os.path.isfile(output_file_abs) and force:
            os.remove(output_file_abs)
        output_handle = open(output_file_abs, 'a' if append else 'w', encoding='utf-8')
    
    gitignore_spec = None
    if use_gitignore:
        gitignore_spec = _build_gitignore_spec(dir_path, max_depth=max_depth)

    if exclude_patterns is None:
        exclude_patterns = []

    if exclude_regex_patterns is None:
        exclude_regex_patterns = []

    compiled_exclude_regex = [re.compile(pat) for pat in exclude_regex_patterns]
    
    dir_path = os.path.abspath(dir_path)
    # Calculate initial depth based on the absolute path
    # Normalize dir_path to remove any trailing slash for consistent depth calculation
    initial_depth = os.path.normpath(dir_path).count(os.sep)

    included_files = []
    written_bytes = 0
    concatenated_files = 0

    for root, dirs, files in os.walk(dir_path, followlinks=follow_symlinks):
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

        current_rel_dir_path_posix = _normalize_rel_posix(current_rel_dir_path)

        dirs.sort()
        files.sort()

        if use_gitignore and gitignore_spec is not None:
            check_dir = current_rel_dir_path_posix + ('/' if current_rel_dir_path_posix else '')
            if current_rel_dir_path_posix and gitignore_spec.match_file(check_dir):
                if dry_run or verbose:
                    print(f"Ignoring directory (gitignore): {current_rel_dir_path if current_rel_dir_path else os.path.basename(root)}")
        
        # Filter subdirectories based on --exclude patterns. This should also respect max_depth.
        # If dirs are already cleared by max_depth, this loop won't run or won't matter.
        original_dirs = list(dirs) 
        dirs[:] = [] 
        for d in original_dirs:
            dir_rel_path = os.path.join(current_rel_dir_path, d)
            dir_rel_path_posix = _normalize_rel_posix(dir_rel_path)
            excluded_by_custom_pattern = False

            for pattern in exclude_patterns:
                if fnmatch.fnmatch(dir_rel_path_posix, pattern) or fnmatch.fnmatch(dir_rel_path_posix + '/', pattern):
                    if dry_run or verbose:
                        print(f"Excluding directory (--exclude pattern '{pattern}'): {dir_rel_path}")
                    excluded_by_custom_pattern = True
                    break

            if not excluded_by_custom_pattern:
                for cregex in compiled_exclude_regex:
                    if cregex.search(dir_rel_path_posix):
                        if dry_run or verbose:
                            print(f"Excluding directory (--exclude-regex '{cregex.pattern}'): {dir_rel_path}")
                        excluded_by_custom_pattern = True
                        break

            if not excluded_by_custom_pattern:
                dirs.append(d)
        
        for file in files:
            file_path = os.path.join(root, file)
            file_abs = file_path
            # Use current_rel_dir_path for file's relative path to ensure consistency
            rel_path = os.path.join(current_rel_dir_path, file)
            rel_path_posix = _normalize_rel_posix(rel_path)

            # Skip the output file itself
            if file_abs == output_file_abs:
                continue
                
            if use_gitignore and gitignore_spec is not None:
                if gitignore_spec.match_file(rel_path_posix):
                    if dry_run or verbose:
                        print(f"Ignoring file (gitignore): {rel_path}")
                    continue

            # Skip files matched by --exclude patterns
            excluded_by_user_pattern = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(rel_path_posix, pattern):
                    if dry_run or verbose:
                        print(f"Excluding file (--exclude pattern '{pattern}'): {rel_path}")
                    excluded_by_user_pattern = True
                    break
            if excluded_by_user_pattern:
                continue

            for cregex in compiled_exclude_regex:
                if cregex.search(rel_path_posix):
                    if dry_run or verbose:
                        print(f"Excluding file (--exclude-regex '{cregex.pattern}'): {rel_path}")
                    excluded_by_user_pattern = True
                    break
            if excluded_by_user_pattern:
                continue
                
            file_ext = os.path.splitext(file)[1]
            # Remove leading dot from file extension for comparison
            if file_ext.startswith('.'):
                file_ext = file_ext[1:]

            if use_wildcard or file_ext in extensions_set:
                if dry_run:
                    print(f"Would concatenate: {file_path}")
                else:
                    try:
                        if max_files != -1 and concatenated_files >= max_files:
                            if verbose:
                                print(f"Max files limit reached ({max_files}). Stopping.")
                            break

                        header_path = file_path.replace('\\', '/')
                        header = f"{comment_prefix} File: {header_path}\n"
                        output_handle.write(header)
                        written_bytes += len(header.encode('utf-8', errors='ignore'))

                        with open(file_path, 'r', encoding=encoding, errors=errors) as f:
                            shutil.copyfileobj(f, output_handle)

                        output_handle.write("\n\n")
                        written_bytes += 2
                        concatenated_files += 1
                        included_files.append(rel_path_posix)

                        if max_bytes != -1 and written_bytes >= max_bytes:
                            if verbose:
                                print(f"Max bytes limit reached ({max_bytes}). Stopping.")
                            break
                    except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                        if strict:
                            if output_handle is not None:
                                output_handle.close()
                            raise
                        if verbose:
                            print(f"Skipping unreadable/binary file: {file_path}")
                        continue

        if (max_files != -1 and concatenated_files >= max_files) or (max_bytes != -1 and written_bytes >= max_bytes):
            break

    if output_handle is not None:
        if include_tree and included_files:
            output_handle.write(f"{comment_prefix} Included files ({len(included_files)}):\n")
            for p in included_files:
                output_handle.write(f"{comment_prefix} - {p}\n")
            output_handle.write("\n")
        output_handle.close()

    return 0

def main():
    # Example usage
    parser = argparse.ArgumentParser(description='Concatenate files with the specified extension(s) under the given directory.')
    parser.add_argument('file_extension', type=str, help='File extension(s) to filter (e.g., "txt", "dart" or "txt,dart,py"). Use "*" for all files. Leading dots are optional.')
    parser.add_argument('--dir-path', '--dir_path', '-d', type=str, help='Path to the directory containing the files to concatenate')
    parser.add_argument('--output-file', '--output_file', '-o', type=str, help='Path to the output file')
    parser.add_argument('--output-file-dir', '--output_file_dir', '-D', type=str, help='Path to the directory for the output file')
    parser.add_argument('--comment-prefix', '--comment_prefix', '-c', type=str, help='Prefix for comments in the output file')
    parser.add_argument('--gitignore', '-i', action='store_true', help='Filter files using .gitignore')
    parser.add_argument('--filename-suffix', '--filename_suffix', type=str, help='Suffix to append to the output filename (supports {timestamp}, {unixtime})')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Enable dry run mode. Shows files that would be concatenated without actually writing them.')
    parser.add_argument('--exclude', type=str, help='Comma-separated list of glob patterns to exclude files/directories (e.g., "*.log,temp/*,specific_file.py")')
    parser.add_argument('--exclude-regex', type=str, help='Comma-separated list of regex patterns to exclude files/directories (matched against relative path)')
    parser.add_argument('--max-depth', type=int, default=-1, help='Maximum recursion depth. 0 for current directory, 1 for current + direct children, etc. Default: -1 (unlimited).')
    parser.add_argument('--force', action='store_true', help='Allow overwriting an existing output file.')
    parser.add_argument('--append', action='store_true', help='Append to the output file if it exists (implies no overwrite delete).')
    parser.add_argument('--verbose', action='store_true', help='Print files that are ignored/excluded/skipped.')
    parser.add_argument('--strict', action='store_true', help='Fail on unreadable/binary files instead of skipping them.')
    parser.add_argument('--encoding', type=str, default='utf-8-sig', help='Text encoding used to read input files. Default: utf-8-sig')
    parser.add_argument('--errors', type=str, default='strict', help='Encoding error handler (e.g., strict, ignore, replace). Default: strict')
    parser.add_argument('--max-bytes', type=int, default=-1, help='Stop once at least this many bytes have been written to output. Default: -1 (unlimited).')
    parser.add_argument('--max-files', type=int, default=-1, help='Stop after concatenating this many files. Default: -1 (unlimited).')
    parser.add_argument('--include-tree', action='store_true', help='Append a list of included files to the output.')
    parser.add_argument('--no-follow-symlinks', action='store_true', help='Do not follow symlinks while walking directories.')
    args = parser.parse_args()

    kwargs = {}
    kwargs['dir_path'] = args.dir_path if args.dir_path else os.getcwd()

    output_file = args.output_file
    if args.output_file_dir:
        os.makedirs(args.output_file_dir, exist_ok=True)
        if not output_file:
            output_file = 'dump_{file_extension}.txt'
        output_file = os.path.join(args.output_file_dir, output_file)

    if output_file:
        kwargs['output_file'] = output_file
    if args.comment_prefix:
        kwargs['comment_prefix'] = args.comment_prefix
    if args.gitignore:
        kwargs['use_gitignore'] = True
    if args.filename_suffix:
        kwargs['filename_suffix'] = args.filename_suffix
    if args.dry_run:
        kwargs['dry_run'] = True
    if args.exclude:
        kwargs['exclude_patterns'] = [p.strip() for p in args.exclude.split(',') if p.strip()]
    if args.exclude_regex:
        kwargs['exclude_regex_patterns'] = [p.strip() for p in args.exclude_regex.split(',') if p.strip()]
    if args.max_depth is not None: # Will always be true due to default, but good practice
        kwargs['max_depth'] = args.max_depth
    if args.force:
        kwargs['force'] = True
    if args.append:
        kwargs['append'] = True
    if args.verbose:
        kwargs['verbose'] = True
    if args.strict:
        kwargs['strict'] = True
    if args.encoding:
        kwargs['encoding'] = args.encoding
    if args.errors:
        kwargs['errors'] = args.errors
    if args.max_bytes is not None:
        kwargs['max_bytes'] = args.max_bytes
    if args.max_files is not None:
        kwargs['max_files'] = args.max_files
    if args.include_tree:
        kwargs['include_tree'] = True
    kwargs['follow_symlinks'] = not bool(args.no_follow_symlinks)

    exit_code = concat_files(dir_path=kwargs.pop('dir_path'), file_extensions=args.file_extension, **kwargs)
    raise SystemExit(exit_code)
    
if __name__ == "__main__":
    main()

