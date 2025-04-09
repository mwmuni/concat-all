# concat-all

**A simple CLI tool to recursively concatenate all files of a certain extension in a directory into a single file.**

---

## Features

- Concatenate all files with specified extension(s) in a directory tree
- Supports multiple extensions at once (e.g., `.py,.txt`)
- Optionally respects `.gitignore` rules to skip ignored files and folders
- Adds a comment header before each file's content in the output
- Flexible output file naming and location
- Cross-platform and Python 3.9+ compatible

---

## Installation

Clone the repository and install locally:

```bash
git clone https://github.com/mwmuni/concat-all.git
cd concat-all
python -m pip install .
```

Or use your preferred Python packaging tool.

```bash
uvx concat-all
```

---

## Requirements

- Python >= 3.9

---

## Usage

### Command Line Interface

```bash
concat-all <file_extensions> [options]
```

### Arguments

| Argument                     | Description                                                                                      | Example                                         |
|------------------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------|
| `<file_extensions>`          | Comma-separated list of file extensions (without or with dot). Use `*` for all files.            | `py,txt` or `*.md` or `*`                       |

### Options

| Option                      | Description                                                                                      | Default                        |
|-----------------------------|--------------------------------------------------------------------------------------------------|--------------------------------|
| `--dir_path`, `-d`          | Directory to search recursively                                                                  | Current working directory      |
| `--output_file`, `-o`       | Output file name (can include `{file_extension}` placeholder)                                   | `dump_{file_extension}.txt`    |
| `--output_file_dir`, `-D`   | Directory to save the output file                                                               | Current working directory      |
| `--comment_prefix`, `-c`    | Prefix for comment headers before each file's content                                           | `//`                           |
| `--gitignore`, `-i`         | Respect `.gitignore` rules when selecting files                                                 | Disabled                       |

---

### Examples

Concatenate all `.py` files in the current directory and subdirectories:

```bash
concat-all py
```

Concatenate `.py` and `.txt` files, saving output to a specific directory:

```bash
concat-all py,txt -D ./output_dir
```

Concatenate all files regardless of extension:

```bash
concat-all * -o all_files.txt
```

Concatenate `.md` files, respecting `.gitignore`:

```bash
concat-all md --gitignore
```

Change the comment prefix to `#`:

```bash
concat-all py -c "#"
```

---

## How it works

- Recursively walks the specified directory
- Filters files by extension(s) or includes all files with `*`
- Optionally skips files/directories matching `.gitignore` patterns
- Concatenates file contents into a single output file
- Adds a comment header before each file's content indicating its path

---

## Programmatic Usage

You can also use `concat-all` as a Python module:

```python
from concat_all import concat_files

concat_files(
    dir_path="path/to/dir",
    file_extensions="py,txt",
    output_file="./output/dump_{file_extension}.txt",
    comment_prefix="//",
    use_gitignore=True
)
```

---

## Notes

- The output file name supports the placeholder `{file_extension}` which will be replaced with the concatenated extensions or `'all'` if using `*`.
- The tool skips binary files or files it cannot read.
- Negated `.gitignore` patterns (starting with `!`) are currently ignored for simplicity.
- The output file itself is automatically excluded from concatenation.

---

## License

MIT License

---

## Author

Matthew Muller

---

## Version

0.1.0

---

Enjoy! 😊
