# file_io_toolbox.py
# This toolbox provides a collection of utilities for file input/output operations.

"""
	Description: 
		The file io toolbox contains a single class (FileIOToolBox) that contains functions used for file manipulation and access within the repository.
	Usage:
	
"""

import os
import sys

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import shutil
import json
import csv
import ast # For parsing Python source code
import filecmp # For comparing files
import importlib.util
from types import ModuleType, FunctionType, MethodType
from typing import Callable, Tuple, Dict, Any

try:
	from TOOLBOXES import logging_toolbox
except ImportError as e:
	print(f"Error importing a core toolbox: {e}")
	sys.exit(1)
	
log = logging_toolbox.LoggingToolbox()

class FileIOToolbox:
	"""
	A toolbox class containing various methods for file and directory manipulation,
	parsing, and analysis.
	"""

	def __init__(self):
		"""
		Initializes the FileIOToolbox.
		Currently, no specific initialization parameters are required.
		"""
		pass

	# --- Basic File Operations ---

	def read_file(self, file_path: str) -> str | None:
		"""
		Reads the entire content of a file.

		Args:
			file_path (str): The path to the file.

		Returns:
			str | None: The content of the file as a string, or None if an error occurs.
		"""
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				return f.read()
		except FileNotFoundError:
			# self.logger.error(f"File not found: {file_path}")
			print(f"Error: File not found at '{file_path}'")
			return None
		except Exception as e:
			# self.logger.error(f"Error reading file '{file_path}': {e}")
			print(f"Error reading file '{file_path}': {e}")
			return None

	def write_file(self, file_path: str, content: str, overwrite: bool = True) -> bool:
		"""
		Writes content to a file. Can overwrite or append.

		Args:
			file_path (str): The path to the file.
			content (str): The content to write.
			overwrite (bool): If True, overwrites the file. If False, appends to the file.

		Returns:
			bool: True if writing was successful, False otherwise.
		"""
		mode = 'w' if overwrite else 'a'
		try:
			# Ensure directory exists
			dir_name = os.path.dirname(file_path)
			if dir_name and not self.dir_exists(dir_name):
				self.create_directory(dir_name)
				
			with open(file_path, mode, encoding='utf-8') as f:
				f.write(content)
			return True
		except Exception as e:
			# self.logger.error(f"Error writing to file '{file_path}': {e}")
			print(f"Error writing to file '{file_path}': {e}")
			return False

	def create_empty_file(self, file_path: str) -> bool:
		"""
		Creates a new empty file. If the file already exists, it will be truncated.

		Args:
			file_path (str): The path to the file to create.

		Returns:
			bool: True if creation was successful, False otherwise.
		"""
		return self.write_file(file_path, "", overwrite=True)

	def append_to_file(self, file_path: str, content: str) -> bool:
		"""
		Appends content to an existing file. If the file does not exist, it creates it.

		Args:
			file_path (str): The path to the file.
			content (str): The content to append.

		Returns:
			bool: True if appending was successful, False otherwise.
		"""
		return self.write_file(file_path, content, overwrite=False)

	# --- File Comparison and Content Checking ---

	def are_files_equal(self, file_path1: str, file_path2: str, shallow: bool = True) -> bool | None:
		"""
		Checks if the content of two files is equal.

		Args:
			file_path1 (str): Path to the first file.
			file_path2 (str): Path to the second file.
			shallow (bool): If True (default), performs a shallow comparison (metadata, size).
							If False, performs a byte-by-byte content comparison.

		Returns:
			bool | None: True if files are equal, False if not, None if one or both files don't exist.
		"""
		if not self.file_exists(file_path1) or not self.file_exists(file_path2):
			# self.logger.warning("One or both files do not exist for comparison.")
			print("Warning: One or both files do not exist for comparison.")
			return None
		try:
			return filecmp.cmp(file_path1, file_path2, shallow=shallow)
		except Exception as e:
			# self.logger.error(f"Error comparing files '{file_path1}' and '{file_path2}': {e}")
			print(f"Error comparing files '{file_path1}' and '{file_path2}': {e}")
			return None

	def find_string_in_file(self, file_path: str, search_string: str) -> bool:
		"""
		Checks if a specific string exists within a file.

		Args:
			file_path (str): The path to the file.
			search_string (str): The string to search for.

		Returns:
			bool: True if the string is found, False otherwise or if an error occurs.
		"""
		content = self.read_file(file_path)
		if content is not None:
			return search_string in content
		return False

	# --- Python Script Analysis ---

	def extract_python_components(self, file_path: str) -> dict | None:
		"""
		Extracts top-level functions and class names from a Python file.

		Args:
			file_path (str): The path to the Python file.

		Returns:
			dict | None: A dictionary with 'functions' and 'classes' lists, 
						 or None if parsing fails or file not found.
		"""
		if not file_path.endswith(".py"):
			# self.logger.warning(f"File '{file_path}' is not a Python file. Cannot extract components.")
			log.error("File '%s' is not a Python file.", file_path)
			return None
			
		content = self.read_file(file_path)
		if content is None:
			return None
		
		try:
			tree = ast.parse(content)
			functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
			classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
			
			return {"functions": functions, "classes": classes}
		except SyntaxError as e:
			# self.logger.error(f"Syntax error parsing Python file '{file_path}': {e}")
			print(f"Syntax error parsing Python file '{file_path}': {e}")
			return None
		except Exception as e:
			# self.logger.error(f"Error extracting components from '{file_path}': {e}")
			print(f"Error extracting components from '{file_path}': {e}")
			return None

	# --- File Validation and Parsing ---

	def is_valid_json(self, file_path: str) -> bool:
		"""
		Checks if a file contains valid JSON.

		Args:
			file_path (str): The path to the file.

		Returns:
			bool: True if the file is valid JSON, False otherwise.
		"""
		content = self.read_file(file_path)
		if content is None:
			return False
		if not content.strip(): # Empty file is not valid JSON
			return False
		try:
			json.loads(content)
			return True
		except json.JSONDecodeError:
			return False
		except Exception as e:
			# self.logger.error(f"Unexpected error validating JSON file '{file_path}': {e}")
			print(f"Unexpected error validating JSON file '{file_path}': {e}")
			return False


	def is_valid_csv(self, file_path: str, delimiter: str = ',', quotechar: str = '"') -> bool:
		"""
		Attempts to validate if a file is a well-formed CSV.
		This is a basic check; complex CSVs might require more sophisticated validation.

		Args:
			file_path (str): The path to the file.
			delimiter (str): The delimiter used in the CSV.
			quotechar (str): The quote character used.

		Returns:
			bool: True if the file seems to be a valid CSV, False otherwise.
		"""
		if not self.file_exists(file_path):
			return False
		try:
			with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
				# Try to read a few lines to see if it parses
				reader = csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
				for _ in range(5): # Check first 5 lines
					try:
						next(reader)
					except StopIteration: # File has less than 5 lines, but is valid up to this point
						break
					except csv.Error: # CSV parsing error
						return False 
				return True # If no errors in first few lines, assume valid for this basic check
		except Exception: # Includes file opening errors, encoding errors etc.
			return False

	def parse_json_file(self, file_path: str) -> dict | list | None:
		"""
		Parses a JSON file into a Python dictionary or list.

		Args:
			file_path (str): The path to the JSON file.

		Returns:
			dict | list | None: The parsed JSON data, or None if an error occurs.
		"""
		
		if not self.is_valid_json(file_path):
			log.error("%s is not a valid .json file.", file_path)
			return None
			
		content = self.read_file(file_path)
		if content is None:
			log.warning("%s is empty, no .json to parse. Returning None.", file_path)
			return None
		try:
			return json.loads(content)
		except json.JSONDecodeError as e:
			log.exception("JSON decoding error in file '%s': %s", file_path, e)
			return None
		except Exception as e:
			# self.logger.error(f"Unexpected error parsing JSON file '{file_path}': {e}")
			log.exception("Unexpected error parsing JSON file '%s': %s", file_path, e)
			return None

	def write_json(self, file_path: str, data: dict | list, overwrite: bool = True) -> bool:
		"""
		Writes a Python dictionary or list to a file as JSON.

		Args:
			file_path (str): The path to the file to write.
			data (dict | list): The data to serialize as JSON.
			overwrite (bool): If True, overwrites the file. If False, appends (not typical for JSON files).

		Returns:
			bool: True if writing was successful, False otherwise.
		"""
		try:
			json_str = json.dumps(data, indent=4)
			return self.write_file(file_path, json_str, overwrite=overwrite)
		except (TypeError, ValueError) as e:
			log.error(f"Error serializing data to JSON for file '{file_path}': {e}")
			return False
		except Exception as e:
			log.error(f"Unexpected error writing JSON to file '{file_path}': {e}")
			return False

	def parse_csv_file(self, file_path: str, delimiter: str = ',', as_dict: bool = False) -> list | None:
		"""
		Parses a CSV file into a list of lists or list of dictionaries.

		Args:
			file_path (str): The path to the CSV file.
			delimiter (str): The delimiter used in the CSV file.
			as_dict (bool): If True, parses CSV into a list of dictionaries using the first row as keys.
							If False (default), parses into a list of lists.

		Returns:
			list | None: A list of lists (or list of dicts) representing the CSV data, 
						 or None if an error occurs.
		"""
		
		if not self.is_valid_csv(file_path, delimiter):
			log.error("%s is not a valid .json file.", file_path)
			return None
			
		if not self.file_exists(file_path):
			log.error("Error: CSV file not found at '%s'", file_path)
			return None
		
		data = []
		try:
			with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
				if as_dict:
					reader = csv.DictReader(csvfile, delimiter=delimiter)
					for row in reader:
						data.append(dict(row))
				else:
					reader = csv.reader(csvfile, delimiter=delimiter)
					for row in reader:
						data.append(row)
			return data
		except Exception as e:
			log.error(f"Error parsing CSV file '%s': %s", file_path, e)
			return None

	# --- File Modification and Deletion ---

	def modify_line_in_file(self, file_path: str, line_number: int, new_content: str) -> bool:
		"""
		Modifies a specific line in a text file. Line numbers are 1-indexed.

		Args:
			file_path (str): The path to the file.
			line_number (int): The 1-indexed line number to modify.
			new_content (str): The new content for the line (without newline character).

		Returns:
			bool: True if modification was successful, False otherwise.
		"""
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				lines = f.readlines()
			
			if line_number <= 0 or line_number > len(lines):
				# self.logger.warning(f"Line number {line_number} is out of range for file '{file_path}'.")
				print(f"Warning: Line number {line_number} is out of range for file '{file_path}'.")
				return False
			
			lines[line_number - 1] = new_content + '\n' # Add newline
			
			with open(file_path, 'w', encoding='utf-8') as f:
				f.writelines(lines)
			return True
		except FileNotFoundError:
			# self.logger.error(f"File not found: {file_path}")
			print(f"Error: File not found at '{file_path}'")
			return False
		except Exception as e:
			# self.logger.error(f"Error modifying line in file '{file_path}': {e}")
			print(f"Error modifying line in file '{file_path}': {e}")
			return False

	def delete_file_contents(self, file_path: str) -> bool:
		"""
		Deletes all content from a file (truncates it).

		Args:
			file_path (str): The path to the file.

		Returns:
			bool: True if successful, False otherwise.
		"""
		return self.create_empty_file(file_path) # Reusing create_empty_file for truncation

	def delete_file(self, file_path: str) -> bool:
		"""
		Deletes a file.

		Args:
			file_path (str): The path to the file to delete.

		Returns:
			bool: True if deletion was successful, False otherwise.
		"""
		try:
			os.remove(file_path)
			return True
		except FileNotFoundError:
			# self.logger.warning(f"File not found for deletion: {file_path}")
			print(f"Warning: File not found for deletion: '{file_path}'")
			return False # Or True if "not found" means "already deleted" is acceptable
		except Exception as e:
			# self.logger.error(f"Error deleting file '{file_path}': {e}")
			print(f"Error deleting file '{file_path}': {e}")
			return False

	# --- Additional Utility Functions ---

	def get_file_size(self, file_path: str, human_readable: bool = False) -> int | str | None:
		"""
		Gets the size of a file.

		Args:
			file_path (str): The path to the file.
			human_readable (bool): If True, returns size in a human-readable format (KB, MB, GB).

		Returns:
			int | str | None: Size in bytes (int), or human-readable string, or None if file not found.
		"""
		if not self.file_exists(file_path):
			# self.logger.error(f"File not found: {file_path}")
			print(f"Error: File not found at '{file_path}'")
			return None
		try:
			size_bytes = os.path.getsize(file_path)
			if human_readable:
				if size_bytes < 1024:
					return f"{size_bytes} B"
				elif size_bytes < 1024**2:
					return f"{size_bytes/1024:.2f} KB"
				elif size_bytes < 1024**3:
					return f"{size_bytes/(1024**2):.2f} MB"
				else:
					return f"{size_bytes/(1024**3):.2f} GB"
			return size_bytes
		except Exception as e:
			# self.logger.error(f"Error getting size of file '{file_path}': {e}")
			print(f"Error getting size of file '{file_path}': {e}")
			return None

	def file_exists(self, file_path: str) -> bool:
		"""Checks if a file exists and is actually a file."""
		return os.path.isfile(file_path)

	def dir_exists(self, dir_path: str) -> bool:
		"""Checks if a directory exists and is actually a directory."""
		return os.path.isdir(dir_path)

	def create_directory(self, dir_path: str, exist_ok: bool = True) -> bool:
		"""
		Creates a directory.

		Args:
			dir_path (str): The path for the directory to be created.
			exist_ok (bool): If True, does not raise an error if the directory already exists.

		Returns:
			bool: True if directory was created or already existed (with exist_ok=True), False on error.
		"""
		try:
			os.makedirs(dir_path, exist_ok=exist_ok)
			return True
		except Exception as e:
			# self.logger.error(f"Error creating directory '{dir_path}': {e}")
			print(f"Error creating directory '{dir_path}': {e}")
			return False

	def list_directory_contents(self, dir_path: str, pattern: str | None = None) -> list | None:
		"""
		Lists contents (files and directories) of a given directory.
		Optionally filters by a simple wildcard pattern (e.g., "*.txt").

		Args:
			dir_path (str): The path to the directory.
			pattern (str | None): Optional wildcard pattern to filter results.

		Returns:
			list | None: A list of names of files and directories, or None if directory doesn't exist.
		"""
		if not self.dir_exists(dir_path):
			# self.logger.error(f"Directory not found: {dir_path}")
			print(f"Error: Directory not found at '{dir_path}'")
			return None
		try:
			contents = os.listdir(dir_path)
			if pattern:
				import fnmatch
				return [item for item in contents if fnmatch.fnmatch(item, pattern)]
			return contents
		except Exception as e:
			# self.logger.error(f"Error listing directory '{dir_path}': {e}")
			print(f"Error listing directory '{dir_path}': {e}")
			return None

	def copy_file(self, src_path: str, dest_path: str) -> bool:
		"""
		Copies a file from source to destination.
		Destination can be a directory (file will be copied into it with same name)
		or a full file path (file will be copied and possibly renamed).

		Args:
			src_path (str): Path to the source file.
			dest_path (str): Path to the destination file or directory.

		Returns:
			bool: True if copy was successful, False otherwise.
		"""
		if not self.file_exists(src_path):
			# self.logger.error(f"Source file for copy not found: {src_path}")
			print(f"Error: Source file for copy not found: '{src_path}'")
			return False
		try:
			# Ensure destination directory exists if dest_path is a full file path
			dest_dir = os.path.dirname(dest_path)
			if dest_dir and not self.dir_exists(dest_dir) and not os.path.isdir(dest_path): # check if dest_path itself is not a dir
				 self.create_directory(dest_dir)

			shutil.copy2(src_path, dest_path) # copy2 preserves metadata
			return True
		except Exception as e:
			# self.logger.error(f"Error copying file from '{src_path}' to '{dest_path}': {e}")
			print(f"Error copying file from '{src_path}' to '{dest_path}': {e}")
			return False

	def move_file(self, src_path: str, dest_path: str) -> bool:
		"""
		Moves (renames) a file from source to destination.

		Args:
			src_path (str): Path to the source file.
			dest_path (str): Path to the destination file or directory.

		Returns:
			bool: True if move was successful, False otherwise.
		"""
		if not self.file_exists(src_path) and not self.dir_exists(src_path): # Check if it's a file or dir
			# self.logger.error(f"Source for move not found: {src_path}")
			print(f"Error: Source for move not found: '{src_path}'")
			return False
		try:
			# Ensure destination directory exists if dest_path is a full file path
			dest_dir = os.path.dirname(dest_path)
			if dest_dir and not self.dir_exists(dest_dir) and not os.path.isdir(dest_path):
				 self.create_directory(dest_dir)
				 
			shutil.move(src_path, dest_path)
			return True
		except Exception as e:
			# self.logger.error(f"Error moving file from '{src_path}' to '{dest_path}': {e}")
			print(f"Error moving file from '{src_path}' to '{dest_path}': {e}")
			return False

	def prepare_ast_script_function(self,
		function_node: ast.FunctionDef,
		file_path: str
	) -> Callable:
		"""
		Prepares a specific top-level function from a Python file for later execution.

		This function loads the module and retrieves the function object.
		It does NOT execute the function itself. Module-level code in the file WILL execute.

		Args:
			function_node: The ast.FunctionDef node of the function to prepare.
			file_path: The path to the Python file containing the function.

		Returns:
			A callable function object ready to be executed.

		Raises:
			ValueError: If the provided node is not an ast.FunctionDef.
			FileNotFoundError: If the file_path does not exist or module spec cannot be created.
			AttributeError: If the function cannot be found or is not a function.
			Exception: Any other exception raised during module loading.

		Security Note:
			Executing code dynamically (including module-level code from files) can be risky
			if the source of the files is not trusted.

		Limitations:
			- The entire module containing the function is loaded, and its top-level code
			  (outside of any functions/classes) will execute during this preparation phase.
		"""
		if not isinstance(function_node, ast.FunctionDef):
			raise ValueError("Provided node is not an ast.FunctionDef.")

		function_name = function_node.name

		# Create a unique module name
		sanitized_file_path = "".join(c if c.isalnum() else "_" for c in file_path)
		module_name = f"temp_module_script_{function_name}_{sanitized_file_path}"

		# Create a module spec from the file path
		spec = importlib.util.spec_from_file_location(module_name, file_path)
		if spec is None or spec.loader is None:
			raise FileNotFoundError(
				f"Could not create module spec for '{file_path}'. Ensure the path is correct."
			)

		# Create a new module based on the spec
		module = importlib.util.module_from_spec(spec)

		# Execute the module (this runs all top-level code in the file)
		# and makes definitions available in the module object.
		spec.loader.exec_module(module)

		# Get the function from the executed module
		func_to_call = getattr(module, function_name, None)

		if func_to_call is None or not isinstance(func_to_call, FunctionType):
			raise AttributeError(
				f"Function '{function_name}' not found or is not a function in '{file_path}'."
			)

		return func_to_call

	def prepare_ast_class_method(self,
		class_node: ast.ClassDef,
		method_node: ast.FunctionDef,
		file_path: str,
		instance_args: Tuple = (),
		instance_kwargs: Dict[str, Any] = None
	) -> Callable:
		"""
		Prepares a specific method of a class from a Python file for later execution.

		This function loads the module, instantiates the class (executing its __init__),
		and retrieves the bound method. It does NOT execute the method itself.

		Args:
			class_node: The ast.ClassDef node of the class containing the method.
			method_node: The ast.FunctionDef node of the method to prepare.
			file_path: The path to the Python file containing the class and method.
			instance_args: A tuple of positional arguments for the class constructor (__init__).
			instance_kwargs: A dictionary of keyword arguments for the class constructor.

		Returns:
			A tuple containing:
			- A callable bound method ready to be executed.
			- An instance of the class.

		Raises:
			ValueError: If the provided nodes are not ast.ClassDef or ast.FunctionDef.
			FileNotFoundError: If the file_path does not exist or module spec cannot be created.
			AttributeError: If the class or method cannot be found.
			TypeError: If class instantiation (__init__) fails due to argument mismatch.
			Exception: Any other exception raised during module loading or class instantiation.

		"""

		class_name = class_node.name
		method_name = method_node.name

		# Create a unique module name to avoid conflicts
		# Sanitize file_path for use in module name
		sanitized_file_path = "".join(c if c.isalnum() else "_" for c in file_path)
		module_name = f"temp_module_{class_name}_{method_name}_{sanitized_file_path}"

		# Create a module spec from the file path
		spec = importlib.util.spec_from_file_location(module_name, file_path)
		if spec is None or spec.loader is None:
			raise FileNotFoundError(
				f"Could not create module spec for '{file_path}'. Ensure the path is correct."
			)

		# Create a new module based on the spec
		module = importlib.util.module_from_spec(spec)

		# Execute the module (this runs all top-level code in the file)
		# and makes definitions available in the module object.
		# Exceptions here (e.g., SyntaxError in the module) will propagate.
		spec.loader.exec_module(module)

		# 1. Get the class from the executed module
		ClassToInstantiate = getattr(module, class_name, None)
		if ClassToInstantiate is None or not isinstance(ClassToInstantiate, type):
			raise AttributeError(
				f"Class '{class_name}' not found or is not a class in '{file_path}'."
			)

		# 2. Instantiate the class
		#    This will call the class's __init__ method.
		#    Exceptions from __init__ (e.g., TypeError, ValueError) will propagate.
		instance = ClassToInstantiate(*instance_args, **instance_kwargs)

		# 3. Get the method from the instance (this binds it)
		bound_method = getattr(instance, method_name, None)

		if bound_method is None or not callable(bound_method):
			raise AttributeError(
				f"Method '{method_name}' not found or is not callable on an instance of '{class_name}'."
			)

		return bound_method, instance
	
	def prepare_ast_class_method_for_instance(self,
		class_instance: Any,
		method_name: str
	) -> Callable:
		"""
		Prepares a specific method of a class instance for later execution.

		This function retrieves the bound method from the instance.
		"""
		bound_method = getattr(class_instance, method_name, None)
		if bound_method is None or not callable(bound_method):
			raise AttributeError(
				f"Method '{method_name}' not found or is not callable on an instance of '{class_instance.__class__.__name__}'."
			)
		return bound_method

def test(test_plan_path: str) -> dict:
	"""
	Runs tests for this toolbox based on the provided test plan.

	Args:
		test_plan_path (str): The path to the JSON test plan file for this toolbox.

	Returns:
		dict: A dictionary containing the test results.
	"""
	log.info(f"Running tests for toolbox_template using test plan: {test_plan_path}")
	if not os.path.exists(test_plan_path):
		logger.log_error(f"Test plan not found: {test_plan_path}")
		return {"error": "Test plan not found", "passed": 0, "failed": 0, "coverage": 0}
		
	test_tb = TestToolBox(test_plan_path)
	results = test_tb.execute_test_plan()
	log.info(f"Test results: {results}")
	return results


def main():
	"""
	Main execution function for file io toolbox. Primarily used for running test function.
	"""
	parser = argparse.ArgumentParser(description="File IO toolbox.")
	parser.add_argument("--run-tests", nargs='?', 
						const="TOOLBOXES/tests/file_io_toolbox/test_plan.json",
						help="Run self-tests. Optionally provide a path to a specific test plan.")

	args = parser.parse_args()
	log.info("file_io_toolbox.py main() started.")

	if args.run_tests:
		test_results = test(args.run_tests)
		log.info("Test Results:")
		for key, value in test_results.items():
			log.info(f"	 {key}: {value}")
		log.info(f"Test run completed with results: {test_results}")
	else:
		log.warning("Missing --run-tests param. Main() function is only used for running the test() function for file_io_toolbox.py- Doing nothing!")
	log.info("file_io_toolbox.py main() finished.")

if __name__ == "__main__":
	main()
