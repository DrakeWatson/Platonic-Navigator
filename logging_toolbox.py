#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
	Description: 
		The logging toolbox contains a single class (LoggingToolBox) that contains functions used for producing logs within the repository.
	Usage:
	
"""

import os
import sys

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import logging
import datetime
import inspect

#_GLOBAL_LOG_LEVEL = logging.DEBUG
_GLOBAL_LOG_LEVEL = logging.INFO
_DEFAULT_CONSOLE_WIDTH = 100
_LOG_FORMAT = '%(asctime)s:%(name)s:%(levelname)s: %(message)s'
_CONSOLE_FORMAT = '%(msecs)d:%(levelname)s: %(message)s'

class LoggingToolbox:
	"""
	Class containing the basic logging infrastructure for the repository.
	"""
	def __init__(self):
		"""
		Initializes the LoggingToolbox.

		The logger name and the base for the log file name will be automatically 
		derived from the __name__ of the script/module that instantiates this class.
		
		Log files will be automatically placed in a 'logs' subdirectory relative 
		to the script that instantiates this class.
		The log filename will be formatted as: 
		<module_name>_<YYYY-MM-DD_HH-MM-SS>.log
		"""
		# --- Determine Caller's Information ---
		script_identifier_from_caller = "__main__" # Default if __name__ can't be found
		caller_script_full_path = None
		try:
			# inspect.stack()[0] is the current frame (LoggingToolbox.__init__).
			# inspect.stack()[1] is the frame of the direct caller.
			caller_frame_info = inspect.stack()[1]
			caller_frame = caller_frame_info.frame
			caller_script_full_path = os.path.abspath(caller_frame_info.filename)
			
			# Get __name__ from the caller's global scope
			if '__name__' in caller_frame.f_globals:
				script_identifier_from_caller = caller_frame.f_globals['__name__']
			else:
				# Fallback if __name__ is not in globals (should be rare for modules)
				# Use the filename without extension as a fallback identifier
				script_identifier_from_caller = os.path.splitext(os.path.basename(caller_script_full_path))[0]
				
		except Exception as e:
			print(f"[LoggingToolbox Init WARNING] Could not reliably determine caller's __name__ or path: {e}")
			# script_identifier_from_caller remains "__main__" or its last known good value
			# caller_script_full_path might be None

		# Get a logger instance.
		self.log = logging.getLogger(script_identifier_from_caller)
		self.log.setLevel(_GLOBAL_LOG_LEVEL)

		# Remove any existing handlers from this logger to avoid duplicate logs
		# if this logger_name was somehow configured before or if re-instantiating.
		if self.log.hasHandlers():
			self.log.handlers.clear()

		# --- Determine Log File Path and Name ---
		log_file_path_to_use = None
		try:
			# 1. Get the full path of the script that called this __init__ method.
			# inspect.stack()[0] is the current frame (LoggingToolbox.__init__).
			# inspect.stack()[1] is the frame of the caller.
			caller_frame_info = inspect.stack()[1]
			caller_frame = caller_frame_info.frame
			caller_script_full_path = os.path.abspath(caller_frame_info.filename)
			
			# 2. Determine the directory of the calling script.
			caller_script_dir = os.path.dirname(caller_script_full_path)
			
			# 3. Define the target 'logs' subdirectory.
			log_directory = os.path.join(caller_script_dir, "logs")

			# 4. Create the 'logs' directory if it doesn't exist.
			# os.makedirs will create parent directories if needed and 
			# exist_ok=True means it won't raise an error if the directory already exists.
			os.makedirs(log_directory, exist_ok=True)

			# 5. Generate the timestamp string including seconds.
			# Example: 2025-05-19_18-30-00
			timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
			
			# 6. Sanitize script_identifier for use in a filename (optional, but good practice)
			# Replace dots (common in __name__) with underscores for broader filesystem compatibility
			safe_script_identifier = script_identifier_from_caller.replace(".", "_")

			# 7. Construct the final log file name.
			log_file_name = f"{safe_script_identifier}_{timestamp_str}.log"
			
			# 8. Construct the full path to the log file.
			log_file_path_to_use = os.path.join(log_directory, log_file_name)
		except Exception as e:
			# If any error occurs during path determination or directory creation,
			# print an error and disable file logging for this instance.
			# Console logging will still be active.
			print(f"[LoggingToolbox Init ERROR] Could not configure log file path: {e}")
			self.log.error(f"Failed to configure log file path due to: {e}. File logging will be disabled for this instance.")
			log_file_path_to_use = None # Ensure it's None if setup failed
			
		# --- Setup Formatter (used by both handlers) ---
		file_formatter = logging.Formatter(_LOG_FORMAT)
		console_formatter = logging.Formatter(_CONSOLE_FORMAT)

		# --- Setup File Handler (if path was successfully determined) ---
		if log_file_path_to_use:
			try:
				file_handler = logging.FileHandler(log_file_path_to_use, mode='a') # Append mode
				file_handler.setLevel(_GLOBAL_LOG_LEVEL)
				file_handler.setFormatter(file_formatter)
				self.log.addHandler(file_handler)
			except Exception as e:
				# If FileHandler creation fails (e.g., permissions issue even if dir exists)
				print(f"[LoggingToolbox Init ERROR] Could not create FileHandler for {log_file_path_to_use}: {e}")
				self.log.error(f"Failed to create FileHandler for {log_file_path_to_use}: {e}. File logging might not work.")
		
		# --- Setup Console Handler (StreamHandler) ---
		# This ensures logs always go to the console, even if file logging fails.
		stream_handler = logging.StreamHandler()
		stream_handler.setLevel(_GLOBAL_LOG_LEVEL) # You could set a different level for console if desired
		stream_handler.setFormatter(console_formatter)
		self.log.addHandler(stream_handler)
		if log_file_path_to_use:
			self.log.debug(f"Logging initialized. Log file: {log_file_path_to_use}")
		else:
			self.log.warning("Logging initialized with console output only. File logging setup failed.")

	# Convenience methods to use the logger
	def debug(self, message: str, *args, **kwargs):
		self.log.debug(message, *args, **kwargs)

	def info(self, message: str, *args, **kwargs):
		self.log.info(message, *args, **kwargs)

	def warning(self, message: str, *args, **kwargs):
		self.log.warning(message, *args, **kwargs)

	def error(self, message: str, *args, **kwargs):
		# Pass exc_info=True to automatically include exception info if called from an except block
		self.log.error(message, exc_info=True, *args, **kwargs)

	def critical(self, message: str, *args, **kwargs):
		self.log.critical(message, exc_info=True, *args, **kwargs)
	
	def exception(self, message: str, *args, **kwargs):
		# Convenience method for logging ERROR with exception information
		self.log.exception(message, *args, **kwargs)
	
	def line_break(self, message_level: str = "info", width: int = _DEFAULT_CONSOLE_WIDTH, char: str = "="):
		"""
		Logs a universal seperator that can have its width adjusted as needed.
		
		Args:
			message_level (str): debug, info, warning, error, critical, exception
			width (int): Defaults to 30 character width, can be adjusted as needed.
		"""
		self._print_level(char * width, message_level)

	def line_wrap(self, message_string: str, message_level: str = "info", max_width: int = _DEFAULT_CONSOLE_WIDTH, offset_left: int = 0):
		"""
		Logs a wrapped output of a log message.
		
		Args:
			message_string (str): The message to be wrapped.
			message_level (str): debug, info, warning, error, critical, exception
			max_width (int): Defaults to 30 character width, can be adjusted as needed.
			offset_left (int): Defaults to 0, can be adjusted as needed.
		"""
		print_list = []
		actual_width = max_width - offset_left
		while len(message_string) > actual_width:
			print_list.append(f"{offset_left * ' '}{message_string[:actual_width]}")
			message_string = message_string[actual_width:]
		
		print_list.append(f"{offset_left * ' '}{message_string}")

		for print_line in print_list:
			self._print_level(print_line, message_level)

	def _print_level(self, message_string: str, message_level: str = "info"):
		"""
		Prints a message at the given level.

		Args:
			message_string (str): The message to be printed.
			message_level (str): debug, info, warning, error, critical, exception
		"""
		# The most complicated code in this entire repository
		if message_level.lower() == "debug":
			self.debug(message_string)
		if message_level.lower() == "info":
			self.info(message_string)
		if message_level.lower() == "warning":
			self.warning(message_string)
		if message_level.lower() == "error":
			self.error(message_string)
		if message_level.lower() == "critical":
			self.critical(message_string)
		if message_level.lower() == "exception":
			self.exception(message_string)

def test(test_plan_path: str) -> dict:
	"""
	Runs tests for this toolbox based on the provided test plan.

	Args:
		test_plan_path (str): The path to the JSON test plan file for this toolbox.
		test_case (str): The name of the test case to run. If not provided, all test cases will be run.
	Returns:
		dict: A dictionary containing the test results.
	"""

	log = LoggingToolbox()

	log.info(f"Running tests for toolbox_template using test plan: {test_plan_path}")
	if not os.path.exists(test_plan_path):
		log.error(f"Test plan not found: {test_plan_path}")
		return {"error": "Test plan not found", "passed": 0, "failed": 0, "coverage": 0}
		
	test_tb = test_toolbox.TestToolbox(test_plan_path)
	results = test_tb.execute_test_plan()

	log.info(f"Test results: {results}")
	return results

def main():
	"""
	Main execution function for logging toolbox. Primarily used for running test function.
	"""
	log = LoggingToolbox()
	parser = argparse.ArgumentParser(description="Logging toolbox.")
	parser.add_argument("--run-tests", action="store_true", help="Run tests for logging toolbox.")
	args = parser.parse_args()
	log.info("logging_toolbox.py main() started.")

	if args.run_tests:
		test_results = test("TOOLBOXES/tests/logging_toolbox/test_plan.json")
		log.info("Test Results:")
		for key, value in test_results.items():
			log.info(f"	 {key}: {value}")
		log.info(f"Test run completed with results: {test_results}")

	log.info("logging_toolbox.py main() finished.")

if __name__ == "__main__":
	main()