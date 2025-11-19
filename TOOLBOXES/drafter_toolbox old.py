#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Drafter Toolbox (VERY EARLY EXPERIMENTAL VERSION)
======================================================

This script serves as a template for toolbox modules within the self-iterating
code repository. Toolboxes contain a single class, `TYPEToolbox`, which groups
related utility functions and data structures for a specific category (e.g.,
FileIO, LLM interaction, Logging).

**File Header Format:**
	- Shebang: `#!/usr/bin/env python3`
	- Encoding: `-*- coding: utf-8 -*-`
	- Docstring: A comprehensive description of the toolbox's purpose and
	  functionality, adhering to standard Python docstring conventions. Should
	  include 'description' and 'usage' fields.

**Function Header Format:**
	Each method within the class should include a docstring explaining its
	purpose, arguments, and return values, following standard Python
	docstring conventions. Should include a brief description of the function
	and then 'args' and 'returns' fields.
"""


import os
import sys
from datetime import datetime
from pathlib import Path
import inspect

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
	sys.path.insert(0, project_root)

import argparse

# Assuming logging_toolbox.py and test_toolbox.py are in TOOLBOXES folder
# and TOOLBOXES is in PYTHONPATH or accessible
try:
	from TOOLBOXES import logging_toolbox
	from TOOLBOXES import test_toolbox
	from TOOLBOXES import file_io_toolbox
	from TOOLBOXES import llm_toolbox
except ImportError as e:
	print(f"Error importing a core toolbox: {e}")
	sys.exit(1)

log = logging_toolbox.LoggingToolbox()

# TODO Remove this variable later
_LIVE_LLM = True

class DrafterToolbox:
	"""
	Toolbox for drafting test cases.

	Function Naming Terms:
		'shell' - A file created programmatically without any LLM interaction.
		'populate' - Populate a shell file with LLM interaction.
	"""
	def __init__(self, file_category: str):
		"""
		Initializes the DrafterToolbox.

		Args:
			file_category: AUDITOR | DRAFTER | STRUCT | TEMPLATE | TOOLBOX | TEST
		"""
		self.f_io = file_io_toolbox.FileIOToolbox()
		self.log = logging_toolbox.LoggingToolbox()
		self.llm = llm_toolbox.LLMToolbox()
		self.log.info(f"DrafterToolbox initialized")

		self.file_category = file_category
		self.struct_file = Path(project_root) / "STRUCTS" / f"{self.file_category}_struct.json"
		self.struct_dict = self.f_io.parse_json_file(self.struct_file)
		self.struct_prompt_dict = self.struct_dict["prompts"]["draft_prompts"]
		self.prompt_dict = {}
		for prompt_key, prompt_value in self.struct_prompt_dict.items():
			self.prompt_dict[prompt_key] = {}
			self.prompt_dict[prompt_key]["context_files"] = prompt_value["context_files"]
			prompt_path = Path(project_root) / "STRUCTS" / "PROMPTS" / f"{self.file_category}_struct" / f"{prompt_key}.md"
			self.prompt_dict[prompt_key]["prompt_content"] = self.f_io.read_file(prompt_path)

		self.current_workspace = ""
		self.step_id = ""
		self.auto_mode = False
	
	def set_workspace(self, workspace_path: str) -> bool:
		"""
		Sets the current workspace path.

		Args:
			workspace_path (str): The path to the workspace directory.
		"""
		# Make sure its a directory that exists
		if not Path(workspace_path).exists():
			self.log.error(f"Workspace path does not exist: {workspace_path}")
			return False
		
		self.log.info(f"Setting workspace path to: {workspace_path}")
		self.current_workspace = workspace_path
		return True
	
	def set_step_id(self, step_id: str):
		"""
		Sets the current step id.

		Args:
			step_id (str): The id of the step to set. It will be dependent on the draft flow you run which step_id corresponds to what.
		"""
		self.log.info(f"Setting step_id to {step_id}")
		self.step_id = step_id

	def build_test_plan(self, target_script_path: str) -> bool:
		"""
		Builds a test plan based on the provided target script.

		Args:
			target_script_path (str): The path to the target script file.

		Returns:
			bool: True if the test plan was created successfully, False otherwise.
		"""
		target_script_name = Path(target_script_path).name.split(".")[0]
		test_plan_path = Path(target_script_path).parent / "tests" / f"{target_script_name}" / "test_plan.json"

		if self.current_workspace == "":
			self.log.info("No previous workspace found. Creating new workspace for this draft.")
			# Create a folder where test_plan.json is with the workspace name
			date_str = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')	
			workspace_name = f"{self.file_category}_workspace_{date_str}"
			workspace_path = test_plan_path.parent / workspace_name
			if not self.f_io.create_directory(workspace_path):
				self.log.error(f"Failed to create workspace directory: {workspace_path}")
				return False
			# Set the current workspace to that location
			self.set_workspace(workspace_path)

		self.log.debug("Completed set_workspace")
		if self.step_id == "" or self.step_id == "draft_test_plan_shell":
			# Clear step_id so that we start here and run the rest of the steps
			self.step_id = ""
			# Draft_test_plan_shell
			if not self.draft_test_plan_shell(test_plan_path,target_script_path):
				self.log.error(f"Failed to draft test plan shell for: {target_script_path}")
				return False
		self.log.debug("Completed draft_test_plan_shell")
		# Populate_test_plan
		if self.step_id == "" or self.step_id == "populate_test_plan":
			# Clear step_id so that we start here and run the rest of the steps
			self.step_id = ""
			# Use an LLM to populate the test plan
			if not self.populate_test_plan(test_plan_path, target_script_path):
				self.log.error(f"Failed to populate test plan: {test_plan_path}")
				return False

		test_plan_dict = self.f_io.parse_json_file(test_plan_path)
		test_cases_list = test_plan_dict["test_cases"]
		self.log.debug("Completed populate_test_plan")
		# draft_test_logic_shells
		if self.step_id == "" or self.step_id == "draft_test_logic_shells":	
			self.step_id = ""
			if not self.draft_test_logic_shells(test_plan_path):
				self.log.error(f"Failed to draft test logic shells: {target_script_path}")
				return False
		self.log.debug("Completed draft_test_logic_shells")
		self.log.debug("step_id: " + self.step_id)
		# populate_test_logic
		if self.step_id == "" or self.step_id == "populate_test_logic":
			self.step_id = ""
			
			self.log.info(f"The total number of test cases is: {len(test_cases_list)}")
			self.log.info(f"Enter the index of the test case you want to start at.")
			user_input = input()
			if user_input.isdigit():
				user_input = int(user_input)
				if user_input < len(test_cases_list):
					short_list = test_cases_list[user_input:]

			for test_case in short_list:
				# for each test in the TC
				tests_list = test_case["tests"]
				for test in tests_list:
					test_logic_path = Path(test_plan_path).parent / f"{test['test_name']}_logic.md"
					target_file_overview_path = Path(target_script_path).parent / f"{target_script_name}.json"

					# populate_test_logic
					if not self.populate_test_logic(test_case["purpose"], test_logic_path, target_file_overview_path):
						self.log.error(f"Failed to populate test logic: {target_script_path}")
						return False
		self.log.debug("Completed populate_test_logic")

		# draft_test_case_shell
		if self.step_id == "" or self.step_id == "draft_test_case_shell":
			self.step_id = ""
			for test_case in test_cases_list:
				# draft_test_case_shell
				if not self.draft_test_case_shell(test_plan_path, test_case["name"]):
					self.log.error(f"Failed to draft test case shell: {target_script_path}")
					return False
		self.log.debug("Completed draft_test_case_shell")

		# populate_test_case
		if self.step_id == "" or self.step_id == "populate_test_case":
			self.step_id = ""
			for test_case in test_cases_list:
				test_case_path = Path(test_plan_path).parent / f"{test_case['name']}.json"
				# populate_test_case
				if not self.populate_test_case(test_case_path):
					self.log.error(f"Failed to populate test case: {target_script_path}")
					return False
		self.log.debug("Completed populate_test_case")

		# Populate test case details
		if self.step_id == "" or self.step_id == "populate_test_case_details":
			self.step_id = ""
			for test_case in test_cases_list:
				test_case_path = Path(test_plan_path).parent / f"{test_case['name']}.json"
				if not self.populate_test_case_details(test_case_path):
					self.log.error(f"Failed to populate test case details: {target_script_path}")
					return False
		self.log.debug("Completed populate_test_case_details")

		# Populate test files
		if self.step_id == "" or self.step_id == "populate_test_files":
			self.step_id = ""
			for test_case in test_cases_list:
				test_case_path = Path(test_plan_path).parent / f"{test_case['name']}.json"
				if not self.populate_test_files(test_case_path):
					self.log.error(f"Failed to populate test files: {target_script_path}")
					return False
		self.log.debug("Completed populate_test_files")

		# populate_test_plan_tests
		if self.step_id == "" or self.step_id == "populate_test_plan_tests":
			self.step_id = ""
			if not self.populate_test_plan_tests(test_plan_path):
				self.log.error(f"Failed to populate test plan tests: {test_plan_path}")
				return False
		self.log.debug("Completed populate_test_plan_tests")
		"""
		for test_case in test_cases_list:
			# Test the TC
			test_failed = True
			test_tb = test_toolbox.TestToolbox(test_plan_path)
			while test_failed:
				if test_tb.execute_test_plan(test_case_path):
					# If fail, wait for user input to run the test again (after modifying files basically)
					# If pass, continue
					test_failed = False
					self.log.info(f"	Test case executed successfully for: {test_case['name']}")
				else:
					self.log.info(f"	Test failed: {test_case}. Waiting for user input to run the test again...")
					input()
		"""
		self.log.info(f"Test plan populated successfully: {test_plan_path}")
		return True

	def populate_test_case_details(self, test_case_path: str) -> bool:
		"""
		Populates the test case details.
		"""

		test_case_dict = self.f_io.parse_json_file(test_case_path)
		self.log.debug(f"Test case before details: {test_case_dict}")
		# Load the 'populate_test_case_details.md' prompt.
		total_prompt_str = self.prompt_dict["populate_test_case_details"]["prompt_content"]
		for context_file in self.prompt_dict["populate_test_case_details"]["context_files"]:
			file_content = self.f_io.read_file(context_file)
			total_prompt_str += f"\n\n{file_content}"
		total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_dict}\n[TEST CASE FILE END]"

		# Prompt LLM to fill in the test case file for that particular test.
		prompt_result_dict = self._fake_llm_call_user(total_prompt_str, "populate_test_case_details", force_json=True)
		self.log.debug(f"Test case after details: {prompt_result_dict}")
		# write the prompt_result_dict to the test_case_path
		if not self.f_io.write_json(test_case_path, prompt_result_dict):
			self.log.error(f"Failed to write prompt result to file: {test_case_path}")
			return False

		return True

	def populate_test_files(self, test_case_path: str) -> bool:
		"""
		Populates the test files.
		"""

		test_case_dict = self.f_io.parse_json_file(test_case_path)
		self.log.debug(f"Starting populate_test_files for: {test_case_dict}")
		# Load the 'populate_test_files.md' prompt.
		test_files_to_populate = test_case_dict["files_definitions"]
		
		# For each test in file_definitions
		for test, file_list in test_files_to_populate.items():
			for file_def_dict in file_list:
				self.log.debug(f"Populating for file: {file_def_dict}")
				# Load the 'populate_test_files.md' prompt.
				total_prompt_str = self.prompt_dict["populate_test_files"]["prompt_content"]
				for context_file in self.prompt_dict["populate_test_files"]["context_files"]:
					file_content = self.f_io.read_file(context_file)
					total_prompt_str += f"\n\n{file_content}"
				total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_dict}\n[TEST CASE FILE END]"
				total_prompt_str += f"\n\n[FILE DEFINITION START]\n{file_def_dict}\n[FILE DEFINITION END]"
				
				# If 'key' contains json request LLM to return a .json file content
				if "json" in file_def_dict["key"]:
					prompt_result_dict = self._fake_llm_call_user(total_prompt_str, "populate_test_files", force_json=True)
					self.log.debug(f"Test case after files: {prompt_result_dict}")
				# Else request LLM to return file content as a string
				else:
					prompt_result_dict = self._fake_llm_call_user(total_prompt_str, "populate_test_files", force_json=False)
					self.log.debug(f"Test case after files: {prompt_result_dict}")

				# Create the file at the target location.
				file_path = Path(test_case_path).parent / file_def_dict["name"]
				self.log.debug(f"Creating file: {file_path}")
				if not self.create_empty_workspace_file(file_path):
					self.log.error(f"Failed to create file: {file_path}")
					return False
				
				if "json" in file_def_dict["key"]:
					if not self.write_workspace_json(file_path, prompt_result_dict):
						self.log.error(f"Failed to write file: {file_path}")
						return False
				else:
					if not self.write_workspace_file(file_path, prompt_result_dict):
						self.log.error(f"Failed to write file: {file_path}")
						return False

		return True

	def create_empty_workspace_file(self, file_path: str) -> bool:
		"""
		Creates an empty file in the current workspace.

		Args:
			file_path (str): The path to the file to create.

		Returns:
			bool: True if the file was created successfully, False otherwise.
		"""

		if not self.f_io.create_empty_file(file_path):
			return False
		
		workspace_file_path = Path(self.current_workspace) / Path(file_path).name
		if not self.f_io.create_empty_file(workspace_file_path):
			self.log.error(f"Failed to create workspace file for {workspace_file_path}")
			return False
		
		return True

	def write_workspace_file(self, file_path: str, write_content: str) -> bool:
		"""
		Writes the content to the workspace file.

		Args:
			file_path (str): The path to the file to write to.
			write_content (str): The content to write to the file.

		Returns:
			bool: True if the file was written to successfully, False otherwise.
		"""

		if not self.f_io.write_file(file_path, write_content):
			return False
		
		workspace_file_path = Path(self.current_workspace) / Path(file_path).name
		if not self.f_io.write_file(workspace_file_path, write_content):
			self.log.error(f"Failed to create workspace file for {workspace_file_path}")
			return False
		
		return True
	
	def write_workspace_json(self, file_path: str, write_content: dict) -> bool:
		"""
		Writes the content to the workspace json file.

		Args:
			file_path (str): The path to the file to write to.
			write_content (dict): The content to write to the file.

		Returns:
			bool: True if the file was written to successfully, False otherwise.
		"""

		if not self.f_io.write_json(file_path, write_content):
			return False
		
		workspace_file_path = Path(self.current_workspace) / Path(file_path).name
		if not self.f_io.write_json(workspace_file_path, write_content):
			self.log.error(f"Failed to create workspace file for {workspace_file_path}")
			return False
		
		return True
	
	def draft_test_plan_shell(self, test_plan_path: str, test_plan_target_path: str) -> bool:
		"""
		Drafts a test plan shell based on the provided test plan.

		Currently based on the test_plan_template.json file as of 5/27/2025.

		Args:
			test_plan_path (str): The path to the 'tests/target_script/' directory.

		Returns:
			bool: True if the test plan shell was created successfully, False otherwise.
		"""

		test_plan_file = Path(test_plan_path)
		shell_content = {}

		# Create a new empty file at the provided path
		if not self.create_empty_workspace_file(test_plan_file):
			self.log.error(f"Failed to create test plan file: {test_plan_path}")
			return False
		
		shell_content["metadata"] = {}
		target_name = test_plan_target_path.split("\\")[-1] # Get the file name (with extension)
		target_name = target_name.split(".")[0] # Remove the extension
		shell_content["metadata"]["name"] = target_name + "_test_plan"
		module_under_test = test_plan_target_path.split("\\")[-2] + "\\" + target_name
		shell_content["metadata"]["module_under_test"] = module_under_test
		shell_content["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")

		shell_content["test_cases"] = []

		if not self.write_workspace_json(test_plan_file, shell_content):
			self.log.error(f"Failed to write test plan shell to file: {test_plan_path}")
			return False

		return True

	def _fake_llm_call_user(self, total_prompt_str: str, step_id: str, force_json: bool = True) -> dict:
		"""
		Fakes an LLM call to the user by writing the prompt to a temporary file and waiting for the user to respond.
		Note: The prompt must require a dictionary response from the LLM.

		Args:
			total_prompt_str (str): The complete prompt to be passed to the user.
			step_id (str): The current step ID to help manage the workspace.

		Returns:
			dict: A dictionary containing the response from the user.
		"""
		extension = ""
		if not force_json:
			extension = ".txt"
		else:
			extension = ".json"

		if _LIVE_LLM:
			self.log.info("    LIVE_LLM setting active.")
			self.log.info("    Collecting LLM response based on user response.")
			self.log.info(f"	CURRENT STEP_ID: {step_id}")

			# Get the number of prompts for this step_id in the current workspace
			menu_options = []
			for file in Path(self.current_workspace).glob(f"{step_id}_prompt_*"):
				menu_options.append(file.name)
			
			response_prompts_index = 0
			for file in Path(self.current_workspace).glob(f"{step_id}_{len(menu_options)}_*_response*"):
				response_prompts_index += 1

			# Write the prompt into the workspace (named {step_id}_prompt_{#})
			prompt_name = f"{step_id}_prompt_{len(menu_options)}"
			prompt_file_path = Path(self.current_workspace) / f"{prompt_name}"
			if not self.f_io.create_empty_file(prompt_file_path):
				self.log.error(f"Failed to create prompt file: {prompt_file_path}")
				return False
			self.f_io.write_file(prompt_file_path, total_prompt_str)
				
			# Ask if the user wants to continue with the current prompt (give them the name of the exact prompt file we just wrote into the workspace)
			if not self.auto_mode:
				self.log.info(f"	CURRENT PROMPT PATH: {prompt_file_path}")
				self.log.info("	Press enter to continue with the current prompt.")
				self.log.info("	Enter 'list' to list all available prompts for this step_id.")
				self.log.info("	Enter 'manual' to create an empty result file and continue.")
				self.log.info("	Enter 'auto' to run all following prompts automatically.")
				user_input = input()
			else:
				user_input = ""

			if user_input.lower() in ["list", "\'list\'"]:
				# Ask the user to select an index
				self.log.info("    Enter the index of the prompt you want to continue with or type 'refresh' to refresh the list:")
				while True:
					for i, option in enumerate(menu_options):
						self.log.info(f"		{i}: {option}")
					user_input = input()
					if user_input.isdigit():
						user_input = int(user_input)
						if user_input < len(menu_options):
							prompt_file_path = Path(self.current_workspace) / f"{step_id}_prompt_{user_input}.txt"
					elif user_input == "refresh":
						continue
					else:
						self.log.error("    Invalid entry. Please try again.")

					# If the user selects one, ask for confirmation (y/n) then continue forward with calling gemini
					self.log.info(f"    You have selected the prompt: {prompt_file_path}")
					self.log.info("    Press enter to continue with this prompt or enter anything else to select another prompt")
					user_input = input()
					if user_input == "":
						total_prompt_str = self.f_io.read_file(prompt_file_path)
						break
				response_dict = self.llm.call_gemini(total_prompt_str, force_json)
				# Write the response into the workspace (named {step_id}_{prompt#}_{response#}_response)
				prompt_result_name = f"{step_id}_{len(menu_options)}_{response_prompts_index}_response{extension}"
				prompt_result_file_path = Path(self.current_workspace) / f"{prompt_result_name}"
				if not self.f_io.write_file(prompt_result_file_path, response_dict):
					self.log.error(f"Failed to write prompt result to file: {prompt_result_file_path}")
					return False
				
				self.log.info(f"    Response saved to {prompt_result_file_path}. Press enter to continue...")
				input()

			elif user_input.lower() in ["manual", "\'manual\'"]:
				prompt_result_name = f"{step_id}_{len(menu_options)}_{response_prompts_index}_response{extension}"
				prompt_result_file_path = Path(self.current_workspace) / f"{prompt_result_name}"
				if not self.f_io.create_empty_file(prompt_result_file_path):
					self.log.error(f"Failed to create prompt result file: {prompt_result_file_path}")
					return False
				self.log.info(f"	Empty prompt result file created: {prompt_result_file_path}")
				self.log.info("		Press enter to continue once you have filled out the prompt result file.")
				input()
			
			else:
				if user_input.lower() in ["auto", "\'auto\'"]:
					self.auto_mode = True
				response_dict = self.llm.call_gemini(total_prompt_str, force_json)
				# Write the response into the workspace (named {step_id}_{prompt#}_{response#}_response)
				prompt_result_name = f"{step_id}_{len(menu_options)}_{response_prompts_index}_response{extension}"
				prompt_result_file_path = Path(self.current_workspace) / f"{prompt_result_name}"
				if not self.f_io.write_file(prompt_result_file_path, response_dict):
					self.log.error(f"Failed to write prompt result to file: {prompt_result_file_path}")
					return False
				
				self.log.info(f"    Response saved to {prompt_result_file_path}. Press enter to continue...")
				if not self.auto_mode:
					input()
				
			# if response_dict can be parsed into a dict, return the dict, otherwise return the string
			if self.f_io.is_valid_json(prompt_result_file_path):
				self.log.debug("    Response is a valid JSON. Parsing...")
				return self.f_io.parse_json_file(prompt_result_file_path)
			else:
				self.log.debug("    Response is not a valid JSON. Returning string...")
				return self.f_io.read_file(prompt_result_file_path)
		
		else: # Manual method for loading prompts
			self.log.info("Once the response is ready in ROOT/temp_prompt_result.json, press enter to continue...")
			# Wait for the response from the user (Should read from a target file after user states its ready)
			input()
		
			# Target file is ROOT/temp_prompt_result.json
			# Check if we can parse the .json, if not just read and return the contents
			if not self.f_io.is_valid_json(Path(project_root) / "temp_prompt_result.json"):
				prompt_result_dict = self.f_io.read_file(Path(project_root) / "temp_prompt_result.json")
			else:
				prompt_result_dict = self.f_io.parse_json_file(Path(project_root) / "temp_prompt_result.json")
			
			return prompt_result_dict

	def populate_test_plan(self, test_plan_path: str, target_script_path: str) -> bool:
		"""
		Populates the test plan with TCs using LLM interaction.

		Args:
			test_plan_path (str): The path to the test plan file.
			target_script_path (str): The path to the target script file.

		Returns:
			bool: True if the test plan was populated successfully, False otherwise.

		"""
		
		# Give the LLM the target script.
		# Ask for a test case outline returned in a parsable dictionary format.
		# The outline should be in terms of the test case type and the purpose of the test case.
		# Assumed return format:
		# "test_cases":[{
		# 	"name": "test_case_name",
		# 	"type": "unit | integration | full", 
		# 	"subtype": "functional_validation | expected_failure | input_validation",
		# 	"purpose": "Detailed description of this test case and its test's purpose.", 
		# 	"script_functions_tested": ["file_name.function_name1,file_name.class_name.function_name2,..."]
		# 	"tests": ["test_name_1", "test_name_2", "test_name_3", ...]
		# }]

		total_prompt_str = self.prompt_dict["populate_test_plan_prompt"]["prompt_content"]

		# Load the file content for the target script
		# Add the file content to the prompt_str
		file_content = self.f_io.read_file(target_script_path)
		total_prompt_str += f"\n\n[TARGET SCRIPT START]\n{file_content}\n[TARGET SCRIPT END]"

		for context_file in self.prompt_dict["populate_test_plan_prompt"]["context_files"]:
			file_content = self.f_io.read_file(context_file)
			total_prompt_str += f"\n\n{file_content}"
		prompt_result_dict = self._fake_llm_call_user(total_prompt_str, "populate_test_plan", force_json=True)
		test_cases_list = []

		for test_case in prompt_result_dict["test_cases"]:
			test_case_dict = {}
			test_case_dict["name"] = test_case["name"]
			test_case_dict["test_case_type"] = test_case["type"]
			test_case_dict["test_case_subtype"] = test_case["subtype"]
			test_case_dict["purpose"] = test_case["purpose"]
			test_case_dict["script_functions_tested"] = test_case["script_functions_tested"]
			test_case_dict["tests"] = []
			for test in test_case["tests"]:
				test_case_dict["tests"].append({"test_name": test, "functions_used": [], "description_of_steps": "", "expected_outcome": "", "validation_method": []})
			test_cases_list.append(test_case_dict)

		# Load the test plan .json dictionary
		test_plan_dict = self.f_io.parse_json_file(test_plan_path)

		# Add the test case dictionary to the test plan dictionary
		test_plan_dict["test_cases"] = test_cases_list

		# Write the test plan .json dictionary to the test plan file
		if not self.write_workspace_json(test_plan_path, test_plan_dict):
			self.log.error(f"Failed to write test plan to file: {test_plan_path}")
			return False

		return True

	def draft_test_logic_shells(self, test_plan_path: str) -> bool:
		"""
		Drafts all test logic shells for the provided test plan.

		Args:
			test_plan_path (str): The path to the test plan file.

		Returns:
			bool: True if the test logic shell was created successfully, False otherwise.
		"""

		# Load the test plan .json
		test_plan_dict = self.f_io.parse_json_file(test_plan_path)

		# Get the test case list
		test_cases_list = test_plan_dict["test_cases"]
		
		# Iterate over the test case list (for each test case entry dict)
		for test_case in test_cases_list:
			# Iterate over the tests list (for each test entry dict)
			for test in test_case["tests"]:
				# Create a test logic shell file in the ROOT/FILE_TYPE/'tests'/TARGET_MODULE directory
				test_logic_path = Path(test_plan_path).parent / f"{test['test_name']}_logic.md"
				if not self.create_empty_workspace_file(test_logic_path):
					self.log.error(f"Failed to create test logic file: {test_logic_path}")
					return False
				
				# Paste the test_logic_template.json into the test logic file
				test_logic_template_path = Path(project_root) / "TEMPLATES" / "test_logic_template.md"
				test_logic_template_content = self.f_io.read_file(test_logic_template_path)
				self.write_workspace_file(test_logic_path, test_logic_template_content)
		return True

	def populate_test_logic(self, test_case_description: str, test_logic_path: str, target_file_json_path: str) -> bool:
		"""
		Populates a test logic file with test logic.

		Args:
			test_logic_path (str): The path to the test logic file to be populated.

		Returns:
			bool: True if the test logic was populated successfully, False otherwise.
		"""
		test_logic_content = self.f_io.read_file(test_logic_path)
		target_file_overview = self.f_io.parse_json_file(target_file_json_path)
		# Get test logic population prompt
		total_prompt_str = self.prompt_dict["populate_test_logic_prompt"]["prompt_content"]
		for context_file in self.prompt_dict["populate_test_logic_prompt"]["context_files"]:
			file_content = self.f_io.read_file(context_file) # For now just file_io_toolbox.json is provided.
			total_prompt_str += f"\n\n[FILE IO OVERVIEW START]\n{file_content}\n[FILE IO OVERVIEW END]"

		if 'file_io_toolbox.json' not in target_file_json_path.name:
			total_prompt_str += f"\n\n[Target File Overview Start]\n{target_file_overview}\n[Target File Overview End]"

		total_prompt_str += f"\n\n[Test Case Description Start]\n{test_case_description}\n[Test Case Description End]"
		test_logic_name = test_logic_path.name.replace("_logic.md", "")
		total_prompt_str += f"\n\n[Test Name Start]\n{test_logic_name}\n[Test Name End]"
		total_prompt_str += f"\n\n[Test Logic File Template Start]\n{test_logic_content}\n[Test Logic File Template End]"
		total_prompt_str += f"\n\n[Target File Name Start]\n{target_file_json_path.name}\n[Target File Name End]"

		# Fake call with prompt
		prompt_result = self._fake_llm_call_user(total_prompt_str, "populate_test_logic", force_json=False)

		# Collect the functions used
		function_list = []
		self.log.debug("Prompt result: %s", prompt_result)
		for entry in prompt_result.split('#'):
			if 'Functions Execution Order' in entry:
				new_str = entry.replace(" Functions Execution Order", "").replace('`', '').replace('\n', '')
				self.log.debug("New str: %s", new_str)
				while (new_str.count('. ') > 1):
					chunk = new_str[new_str.find('. ') + 2:new_str.find('. ', 2) - 1]
					self.log.debug("Chunk: %s", chunk)
					if len(chunk) > 2:
						function_list.append(chunk)
					replace_start = new_str.find('. ', 2) - 1
					new_str = new_str[replace_start:]
				new_str = new_str[new_str.find(". ") + 2:]
				function_list.append(new_str)
				break
		self.log.debug("Function list: %s", function_list)
		func_data = {}
		# Extract AST components
		for function_dot_name in function_list:
			self.log.debug("Function dot name: %s", function_dot_name)
			parts = function_dot_name.split('.')
			relative_file_path = None
			# Determine script type and path
			# This logic might need to be more robust if filenames aren't perfectly unique across types
			if "_auditor" in parts[0]:
				relative_file_path = os.path.join("AUDITORS", f"{parts[0]}.py")
			elif "_drafter" in parts[0]:
				relative_file_path = os.path.join("DRAFTERS", f"{parts[0]}.py")
			elif "_toolbox" in parts[0]: # Covers general toolboxes like file_io_toolbox
				relative_file_path = os.path.join("TOOLBOXES", f"{parts[0]}.py")
			
			base_repo_dir = Path(project_root)
			function_file_path = base_repo_dir / relative_file_path
			if not function_file_path.exists():
				self.log.error("Function file not found: %s", function_file_path)
				return False

			func_data[function_dot_name] = {}
			py_components = self.f_io.extract_python_components(str(function_file_path))
			if py_components is None:
				self.log.error("Could not extract Python components from %s", function_dot_name)
				return False

			if len(parts) == 2: # script_file.function_in_script
				script_func_name = parts[1]
				found_node = False
				for node in py_components["functions"]:
					if node.name.lower() in script_func_name.lower():
						# Store the input and output parameters for the function
						func_data[function_dot_name]["input_parameters"] = node.args.args
						for function_dict in target_file_overview["functions"]:
							if function_dict["name"].lower() in function_dot_name.lower():
								func_data[function_dot_name]["output_parameters"] = function_dict["returns"]
								break
						found_node = True
						break
				if not found_node:
					self.log.error("Function node '%s' not found in %s", script_func_name)
					return False

			elif len(parts) == 3: # toolbox_file.class_name.function_in_class
				# file_name_part is parts[0]
				class_name_part = parts[1]
				method_name_part = parts[2]
				found_class_node = None
				for c_node in py_components["classes"]:
					if c_node.name.lower() in class_name_part.lower():
						found_class_node = c_node
						break
				if not found_class_node: 
					self.log.error("Class node '%s' not found", class_name_part)
					return False
				
				found_method_node = None
				# Methods can be defined directly in class or be part of ast.FunctionDef list if not properly nested by parser
				# The f_io.extract_python_components returns functions at all levels. Need to check parentage or assume flat list for now.
				# For simplicity, check FunctionDef nodes within the class AST node directly.
				for node in found_class_node.body: # Iterate through items in class body
					if isinstance(node, inspect.ast.FunctionDef) and node.name.lower() in method_name_part.lower():
						# Store the input and output parameters for the function
						func_data[function_dot_name]["input_parameters"] = node.args.args
						for function_dict in target_file_overview["functions"]:
							if function_dict["name"].lower() in function_dot_name.lower():
								func_data[function_dot_name]["output_parameters"] = function_dict["returns"]
								break
						
						break
				if not found_method_node: # Fallback: check all functions if not found in class body (less accurate)
					for f_node in py_components["functions"]: # This might pick up non-class functions if names collide
						if f_node.name.lower() in method_name_part.lower(): # TODO: Check f_node is child of class_node
							self.log.warning("Method '%s' found globally, not nested in AST for class '%s'. Assuming it's the correct one.", method_name_part, class_name_part)
							found_method_node = f_node
							func_data[function_dot_name]["input_parameters"] = f_node.args.args
							for function_dict in target_file_overview["functions"]:
								if function_dict["name"].lower() in function_dot_name.lower():
									func_data[function_dot_name]["output_parameters"] = function_dict["returns"]
									break
							break
				
				if not found_method_node:
					self.log.error("Method node '%s' not found in class '%s'", method_name_part, class_name_part)
					return False

		self.log.debug("Function data: %s", func_data)
		# Fill in the input parameters section per function
		input_param_str = ""

		for function_dot_name, func_dict in func_data.items():
			if func_dict["input_parameters"] is not None and len(func_dict["input_parameters"]) > 0:
				for input_param in func_dict["input_parameters"]:
					input_param_str += f"{function_dot_name}.{input_param.arg}\n"

		prompt_result = prompt_result.replace("# Input Parameters", "# Input Parameters\n" + input_param_str)
		# Fill in the return parameters section per function
		return_param_str = ""

		for function_dot_name, func_dict in func_data.items():
			if func_dict["output_parameters"] is not None:
				return_param_str += f"{function_dot_name}.{func_dict['output_parameters']}\n"


		prompt_result = prompt_result.replace("# Return Parameters", "# Return Parameters\n" + return_param_str)
		self.log.debug("Prompt result: %s", prompt_result)
		# Write the response to the test logic file
		if not self.write_workspace_file(test_logic_path, prompt_result):
			self.log.error(f"Failed to write test logic to file: {test_logic_path}")
			return False

		return True

	def populate_test_plan_tests(self, test_plan_path: str) -> bool:
		"""
		Populates the test plan. Assumes that each test case has already been iterated over and the tests directory has been populated with the test logic files for each TC.

		Args:
			test_plan_path (str): The path to the test plan file.

		Returns:
			bool: True if the test plan was populated successfully, False otherwise.
		"""
		test_plan_dict = self.f_io.parse_json_file(test_plan_path)
		test_cases_list = test_plan_dict["test_cases"]
		for test_case_index, test_case in enumerate(test_cases_list):
			# Load the test case file
			test_case_path = Path(test_plan_path).parent / f"{test_case['name']}.json"
			test_case_dict = self.f_io.parse_json_file(test_case_path)
			# Load the prompt needed for this function
			total_prompt_str = self.prompt_dict["populate_test_plan_tests_prompt"]["prompt_content"]
			for context_file in self.prompt_dict["populate_test_plan_tests_prompt"]["context_files"]:
				file_content = self.f_io.read_file(context_file)
				total_prompt_str += f"\n\n{file_content}"
			total_prompt_str += f"\n\n[TEST CASE DEFINITION START]\n{test_case}\n[TEST CASE DEFINITION END]"
			total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_dict}\n[TEST CASE FILE END]"

			# Give the test case file as context for the LLM
			prompt_result_dict = self._fake_llm_call_user(total_prompt_str, "populate_test_plan_tests", force_json=True)

			# Get a dictionary back which is the 'tests' list completely filled out for that test case with the appropriate dictionaries.
			test_plan_dict["test_cases"][test_case_index]["tests"] = prompt_result_dict["tests"]

		# Write the test plan to the file
		if not self.write_workspace_json(test_plan_path, test_plan_dict):
			self.log.error(f"Failed to write test plan to file: {test_plan_path}")
			return False
		
		return True


	def populate_test_case(self, test_case_path: str) -> bool:
		"""
		Populates the test case with its tests and their logic.
		Assumes that the test case has already been iterated over and the test case file has been created.

		Args:
			test_case_path (str): The path to the test case file to be populated.

		Returns:
			bool: True if the test case was populated successfully, False otherwise.
		"""
		test_case_dict = self.f_io.parse_json_file(test_case_path)
		
		if len(test_case_dict["tests"][0]["functions"]) != 0:
			self.log.debug("Test case already populated. Skipping.")
			return True

		new_tests = []
		# For each test within the test case file (test_name in tests will be defined)
		for test in test_case_dict["tests"]:
			# Load the corresponding test logic .md file
			test_name = test["test_name"]
			test_logic_path = Path(test_case_path).parent / f"{test_name}_logic.md"
			test_logic_content = self.f_io.read_file(test_logic_path)
			# Create the prompt
			total_prompt_str = self.prompt_dict["populate_test_case_prompt"]["prompt_content"]
			for context_file in self.prompt_dict["populate_test_case_prompt"]["context_files"]:
				file_content = self.f_io.read_file(context_file)
				total_prompt_str += f"\n\n{file_content}"
			total_prompt_str += f"\n\n[TEST LOGIC FILE START]\n{test_logic_content}\n[TEST LOGIC FILE END]"
			total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_dict}\n[TEST CASE FILE END]"
			# Prompt LLM to fill in the test case file for that particular test.
			prompt_result_dict = self._fake_llm_call_user(total_prompt_str, "populate_test_case", force_json=True)
			# Fill in the test case file for that particular test.
			prompt_result_dict["test_name"] = test_name
			new_tests.append(prompt_result_dict)

		test_case_dict["tests"] = new_tests
				
		# Write the response to the test case file
		if not self.f_io.write_json(test_case_path, test_case_dict):
			self.log.error(f"Failed to write test case to file: {test_case_path}")
			return False

		return True

	def draft_test_case_shell(self, test_plan_path: str, test_case: str) -> bool:
		"""
		Drafts a test case shell based on the provided test plan.
		"""

		# Check if the test plan file exists
		if not self.f_io.file_exists(test_plan_path):
			self.log.error(f"Test plan file not found: {test_plan_path}")
			return False

		# Read the test plan file
		test_plan_dict = self.f_io.parse_json_file(test_plan_path) 

		# Find the test case in the test plan
		test_case_dict = {}
		for test_case_tp in test_plan_dict["test_cases"]:
			if test_case_tp["name"] == test_case:
				test_case_dict = test_case_tp
				break
		else:
			self.log.error(f"Test case {test_case} not found in test plan: {test_plan_path}")
			return False

		test_case_name = test_case_dict["name"]
		test_case_path = Path(test_plan_path).parent / f"{test_case_name}.json"

		# Copy the test case template file at the correct location
		if not self.create_empty_workspace_file(test_case_path):
			self.log.error(f"Failed to create test case file: {test_case_path}")
			return False

		tp_organized_data = {}

		# Metadata
		tp_organized_data["metadata"] = {}
		tp_organized_data["metadata"]["name"] = test_case_dict["name"]
		tp_organized_data["metadata"]["test_case_type"] = test_case_dict["test_case_type"]
		tp_organized_data["metadata"]["description"] = test_case_dict["purpose"]
		tp_organized_data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")

		# Tests
		tp_organized_data["tests"] = []
		for test in test_case_dict["tests"]:
			test_content_dict = {}
			test_content_dict["test_name"] = test["test_name"]
			test_content_dict["files"] = {}
			test_content_dict["functions"] = test["functions_used"]
			test_content_dict["class_instance_args"] = []
			if "expected_exception" in test["validation_method"]:
				test_content_dict["expected_exception"] = []
			if "expected_return_value_and_order" in test["validation_method"]:
				test_content_dict["expected_return_value_and_order"] = {}
			if "expected_file_content" in test["validation_method"]:
				test_content_dict["expected_file_content"] = []
			test_content_dict["test_steps_order"] = []
			tp_organized_data["tests"].append(test_content_dict)

		if not self.write_workspace_json(test_case_path, tp_organized_data):
			self.log.error(f"Failed to write test case template to file: {test_case_path}")
			return False
		
		# Successfully created a new test case shell file
		return True
	
def test(test_plan_path: str) -> dict:
	"""
	Runs tests for this toolbox based on the provided test plan.

	Args:
		test_plan_path (str): The path to the JSON test plan file for this toolbox.

	Returns:
		dict: A dictionary containing the test results.
	"""
	logger.log_info(f"Running tests for toolbox_template using test plan: {test_plan_path}")
	if not os.path.exists(test_plan_path):
		logger.log_error(f"Test plan not found: {test_plan_path}")
		return {"error": "Test plan not found", "passed": 0, "failed": 0, "coverage": 0}
		
	test_tb = TestToolBox(test_plan_path)
	results = test_tb.execute_test_plan()
	logger.log_info(f"Test results: {results}")
	return results

def main():
	"""
	Main execution function for the toolbox template.
	Primarily for demonstration or direct testing of toolbox methods.
	"""

	box = DrafterToolbox('test')
	box.log.info("Do you want to use an already created workspace? Enter a path or press enter to use a new workspace.")
	workspace_path = input()
	if workspace_path:
		box.set_workspace(workspace_path)
	box.log.info("Do you want to start at a specific step? Enter a step or press enter to start at the beginning.")
	step = input()
	if step:
		box.set_step_id(step)
	box.build_test_plan(r'C:\Harbor\MVP\TOOLBOXES\file_io_toolbox.py')

if __name__ == "__main__":
	main()
