import unittest
import os
import sys
import tempfile
import io
import contextlib
import shutil

# Add project root to sys.path to allow importing concat_all
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from concat_all import concat_all

class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = self.test_dir.name

    def tearDown(self):
        self.test_dir.cleanup()

    def _create_files(self, file_dict):
        """
        Creates files and directories within the temporary test directory.
        file_dict: A dictionary where keys are relative file paths
                   and values are their content. Directories are created
                   implicitly. If content is None, an empty directory is created.
        """
        for rel_path, content in file_dict.items():
            full_path = os.path.join(self.test_dir_path, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            if content is not None:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            else: # content is None, ensure directory exists
                if not os.path.exists(full_path): # only if it's not implicitly created by another file
                    os.makedirs(full_path, exist_ok=True)


    def _run_concat_files(self, extensions="txt", output_file_name="concat_out.txt", **kwargs):
        """
        Runs concat_files and captures its stdout, then returns output file content and stdout.
        """
        output_file_path = os.path.join(self.test_dir_path, output_file_name)
        
        # Default kwargs for concat_files, can be overridden
        run_kwargs = {
            'dir_path': self.test_dir_path,
            'file_extensions': extensions,
            'output_file': output_file_path,
            'comment_prefix': '//',
        }
        run_kwargs.update(kwargs)

        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            concat_all.concat_files(**run_kwargs)
        
        stdout_output = stdout_capture.getvalue()
        
        output_content = None
        if os.path.exists(output_file_path):
            with open(output_file_path, 'r', encoding='utf-8') as f:
                output_content = f.read()
                
        return output_content, stdout_output

class TestGitignoreHandling(BaseTestCase):
    def test_general_ignore(self):
        self._create_files({
            ".gitignore": "*.log\ntemp/",
            "file1.txt": "content1",
            "file2.log": "log_content",
            "temp/file3.txt": "temp_content",
            "another.txt": "content_another"
        })
        content, _ = self._run_concat_files(use_gitignore=True)
        self.assertIn("file1.txt", content)
        self.assertIn("content1", content)
        self.assertIn("another.txt", content)
        self.assertIn("content_another", content)
        self.assertNotIn("file2.log", content)
        self.assertNotIn("log_content", content)
        self.assertNotIn("temp/file3.txt", content)
        self.assertNotIn("temp_content", content)

    def test_negated_file_pattern(self):
        self._create_files({
            ".gitignore": "*.log\n!important.log",
            "file1.txt": "content1",
            "file2.log": "log_content_ignored",
            "important.log": "log_content_important" # Should be included despite *.log
        })
        # Test with log extension to try and pick up important.log
        content, _ = self._run_concat_files(extensions="txt,log", use_gitignore=True)
        self.assertIn("file1.txt", content)
        self.assertNotIn("file2.log", content)
        self.assertIn("important.log", content)
        self.assertIn("log_content_important", content)

    def test_negated_directory_pattern(self):
        self._create_files({
            ".gitignore": "temp/\n!temp/keep_this/",
            "file1.txt": "content1",
            "temp/ignored_dir/ignore.txt": "ignored_in_temp",
            "temp/keep_this/valuable.txt": "valuable_content",
            "temp/another_ignored.txt": "also_ignored"
        })
        content, _ = self._run_concat_files(use_gitignore=True)
        self.assertIn("file1.txt", content)
        self.assertNotIn("ignored_dir/ignore.txt", content)
        self.assertIn("temp/keep_this/valuable.txt", content) # Key assertion
        self.assertIn("valuable_content", content)
        self.assertNotIn("temp/another_ignored.txt", content)

    def test_negation_overrides_general_within_path(self):
        # Scenario: ignore all in 'build/', but not 'build/public/'
        self._create_files({
            ".gitignore": "build/\n!build/public/",
            "main.txt": "main content",
            "build/secret.txt": "secret",
            "build/public/index.txt": "public index"
        })
        content, _ = self._run_concat_files(use_gitignore=True)
        self.assertIn("main.txt", content)
        self.assertNotIn("build/secret.txt", content)
        self.assertIn("build/public/index.txt", content)
        self.assertIn("public index", content)


class TestDryRunMode(BaseTestCase):
    def test_dry_run_output_and_no_file_creation(self):
        self._create_files({
            "file1.py": "print('hello')",
            "subdir/file2.py": "print('world')"
        })
        output_content, stdout_output = self._run_concat_files(extensions="py", dry_run=True, output_file_name="dry_run_test.py")
        
        self.assertIsNone(output_content, "Output file should not be created in dry-run mode")
        
        self.assertIn("Dry run mode enabled.", stdout_output)
        expected_output_path = os.path.join(self.test_dir_path, "dry_run_test.py")
        self.assertIn(f"Output file would be: {expected_output_path}", stdout_output)
        
        # Normalize paths for comparison as os.walk order might vary slightly by OS
        # and our concat might pick them up in different order.
        # We care that both are mentioned.
        path1 = os.path.join(self.test_dir_path, "file1.py")
        path2 = os.path.join(self.test_dir_path, "subdir", "file2.py")
        self.assertIn(f"Would concatenate: {path1}", stdout_output)
        self.assertIn(f"Would concatenate: {path2}", stdout_output)

class TestExcludeOption(BaseTestCase):
    def test_exclude_specific_file(self):
        self._create_files({
            "file1.txt": "content1",
            "file_to_exclude.txt": "exclude_me",
            "file3.txt": "content3"
        })
        exclude_patterns = ["file_to_exclude.txt"]
        content, _ = self._run_concat_files(exclude_patterns=exclude_patterns)
        self.assertIn("file1.txt", content)
        self.assertNotIn("file_to_exclude.txt", content)
        self.assertIn("file3.txt", content)

    def test_exclude_by_glob_pattern(self):
        self._create_files({
            "file1.txt": "content1",
            "file.log": "log_data",
            "another.txt": "content_A",
            "another.log": "log_data_2"
        })
        exclude_patterns = ["*.log"]
        # Concatenate all files initially to check exclusion
        content, _ = self._run_concat_files(extensions="*", exclude_patterns=exclude_patterns)
        self.assertIn("file1.txt", content)
        self.assertNotIn("file.log", content)
        self.assertIn("another.txt", content)
        self.assertNotIn("another.log", content)

    def test_exclude_directory(self):
        self._create_files({
            "file1.txt": "content1",
            "build/file_in_build.txt": "build_content",
            "src/file_in_src.txt": "src_content",
            "build/another.txt": "build_content2"
        })
        exclude_patterns = ["build/"] # or "build/*" or "build"
        content, _ = self._run_concat_files(extensions="txt", exclude_patterns=exclude_patterns)
        self.assertIn("file1.txt", content)
        self.assertNotIn("build/file_in_build.txt", content)
        self.assertNotIn("build_content", content)
        self.assertIn("src/file_in_src.txt", content)

    def test_exclude_pattern_relative_to_root(self):
        self._create_files({
            "src/app1/main.py": "app1",
            "src/app2/main.py": "app2",
            "src/app1/utils.py": "app1_utils"
        })
        # Exclude all main.py files inside any subdirectory of src
        exclude_patterns = ["src/*/main.py"]
        content, _ = self._run_concat_files(extensions="py", exclude_patterns=exclude_patterns)
        self.assertNotIn("src/app1/main.py", content)
        self.assertNotIn("src/app2/main.py", content)
        self.assertIn("src/app1/utils.py", content)

class TestMaxDepthOption(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._create_files({
            "root.txt": "root_content",
            "level1_dir/level1.txt": "level1_content",
            "level1_dir/level2_dir/level2.txt": "level2_content",
            "level1_dir/level2_dir/level3_dir/level3.txt": "level3_content",
            "another_level1_dir/another_level1.txt": "another_l1_content"
        })

    def test_max_depth_0(self):
        content, _ = self._run_concat_files(max_depth=0)
        self.assertIn("root.txt", content)
        self.assertNotIn("level1.txt", content)
        self.assertNotIn("level2.txt", content)
        self.assertNotIn("level3.txt", content)
        self.assertNotIn("another_level1.txt", content)

    def test_max_depth_1(self):
        content, _ = self._run_concat_files(max_depth=1)
        self.assertIn("root.txt", content)
        self.assertIn("level1.txt", content)
        self.assertIn("another_level1.txt", content)
        self.assertNotIn("level2.txt", content)
        self.assertNotIn("level3.txt", content)

    def test_max_depth_2(self):
        content, _ = self._run_concat_files(max_depth=2)
        self.assertIn("root.txt", content)
        self.assertIn("level1.txt", content)
        self.assertIn("another_level1.txt", content)
        self.assertIn("level2.txt", content)
        self.assertNotIn("level3.txt", content)
        
    def test_max_depth_unlimited(self): # default is -1
        content, _ = self._run_concat_files() # max_depth=-1 by default in concat_files
        self.assertIn("root.txt", content)
        self.assertIn("level1.txt", content)
        self.assertIn("another_level1.txt", content)
        self.assertIn("level2.txt", content)
        self.assertIn("level3.txt", content)

    def test_max_depth_stdout_message_dry_run(self):
        _, stdout = self._run_concat_files(max_depth=0, dry_run=True)
        # Path is relative to test_dir_path, which is "." for root in this context
        self.assertIn("Max depth (0) reached. Not traversing further from: .", stdout)

        _, stdout_l1 = self._run_concat_files(max_depth=1, dry_run=True)
        # Check for one of the level1 dirs
        path_l1d = os.path.join("level1_dir") 
        # The message should appear for each directory at max_depth
        self.assertIn(f"Max depth (1) reached. Not traversing further from: {path_l1d}", stdout_l1)
        path_al1d = os.path.join("another_level1_dir")
        self.assertIn(f"Max depth (1) reached. Not traversing further from: {path_al1d}", stdout_l1)


class TestMainOutputDir(BaseTestCase):
    def test_output_file_dir_with_default_name(self):
        self._create_files({"file1.txt": "content1"})
        output_dir = os.path.join(self.test_dir_path, "out")

        stdout_capture = io.StringIO()
        prev_argv = sys.argv
        sys.argv = ["concat-all", "txt", "-d", self.test_dir_path, "-D", output_dir]
        try:
            with contextlib.redirect_stdout(stdout_capture):
                concat_all.main()
        finally:
            sys.argv = prev_argv

        output_file_path = os.path.join(output_dir, "dump_txt.txt")
        self.assertTrue(os.path.exists(output_file_path))
        with open(output_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("file1.txt", content)


if __name__ == '__main__':
    unittest.main()
