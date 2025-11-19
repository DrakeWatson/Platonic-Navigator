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
import json
from datetime import datetime
from pathlib import Path
import inspect
import networkx as nx
import concurrent.futures

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
	sys.path.insert(0, _PROJECT_ROOT)
_PROJECT_ROOT = Path(_PROJECT_ROOT)

try:
	from TOOLBOXES import logging_toolbox
	from TOOLBOXES import file_io_toolbox
	from TOOLBOXES import llm_toolbox
except ImportError as e:
	print(f"Error importing a core toolbox: {e}")
	sys.exit(1)

log = logging_toolbox.LoggingToolbox()

DEBUG_MODE = False

FUNCTIONS_FOR_TESTING = [
	"file_io_toolbox.FileIOToolbox.read_file",
	"file_io_toolbox.FileIOToolbox.write_file",
	"file_io_toolbox.FileIOToolbox.create_empty_file",
	"file_io_toolbox.FileIOToolbox.append_to_file",
	"file_io_toolbox.FileIOToolbox.is_valid_json",
	"file_io_toolbox.FileIOToolbox.is_valid_csv",
	"file_io_toolbox.FileIOToolbox.parse_json_file",
	"file_io_toolbox.FileIOToolbox.write_json",
	"file_io_toolbox.FileIOToolbox.parse_csv_file",
	"file_io_toolbox.FileIOToolbox.get_file_size",
	"file_io_toolbox.FileIOToolbox.file_exists",
	"file_io_toolbox.FileIOToolbox.dir_exists",
	"file_io_toolbox.FileIOToolbox.list_directory_contents"
]

TEST_DRAFT_STEP_LIST = [
			"1_draft_test_plan_shell",
			"2_populate_test_plan",
			"3_populate_test_description",
			"4_populate_function_details",
			"5_populate_test_logic",
			"6_draft_test_case_shell",
			"7_populate_test_case",
			"8_populate_test_case_details",
			"9_populate_test_files",
			"10_populate_test_plan_tests"]

class DrafterToolbox:
	"""
	Toolbox for drafting test cases.

	Function Naming Terms:
		'shell' - A file created programmatically without any LLM interaction.
		'populate' - Populate a shell file with LLM interaction.
	"""
	def __init__(self, target_file_path: str, working_dir: str, struct_file_path: str):
		"""
		Initializes the DrafterToolbox.

		Args:
			target_file_path (str): Path to the target file to be drafted
			working_dir (str): Path to where you want the workspaces to be populated
			struct_file_path (str): Path to the struct file to collect draft prompts from
		"""
		self.f_io = file_io_toolbox.FileIOToolbox()
		self.llm = llm_toolbox.LLMToolbox()
		self.path_dict = {
			"target_file": target_file_path,
			"working_dir": working_dir,
			"struct_file": struct_file_path,
			"workspace_dir": "",
			"template_path": Path(_PROJECT_ROOT) / "TEMPLATES"}
		self.struct_dict = self.f_io.parse_json_file(struct_file_path)
		self.struct_prompt_dict = self.struct_dict["prompts"]["draft_prompts"]
		self.prompt_dict = {}
		for prompt_key, prompt_value in self.struct_prompt_dict.items():
			self.prompt_dict[prompt_key] = {}
			self.prompt_dict[prompt_key]["context_files"] = prompt_value["context_files"]
			prompt_path = Path(struct_file_path).parent / "PROMPTS" / Path(struct_file_path).name.split(".")[0] / f"{prompt_key}.md"
			self.prompt_dict[prompt_key]["prompt_content"] = self.f_io.read_file(prompt_path)

		self.workspace_name = None
		self.current_graph = None
		self.cur_step_node = ""
		self.prev_io_node = ""
		self.cur_io_node = ""
		log.info(f"DrafterToolbox initialized. Target path: {target_file_path}")

		self.load_workspace()
		self.execute_steps()

	def load_workspace(self):
		"""
		
		Args:

		"""
		# Store all folder names within self.path_dict["working_dir"] in a list of strings
		workspace_list = self.f_io.list_directory_contents(self.path_dict["working_dir"])

		# List all folder names as a selectable menu
		for index, workspace in enumerate(workspace_list):
			log.info(f"{index}: {workspace}")
		choice = input("Select a workspace from the list or enter a name to create a new workspace: ")
		if choice.isdigit() and int(choice) < len(workspace_list):
			self.workspace_name = workspace_list[int(choice)]
			self.path_dict["workspace_dir"] = str(Path(self.path_dict["working_dir"]) / self.workspace_name)
			self.path_dict = self.f_io.parse_json_file(Path(self.path_dict["workspace_dir"]) / "workspace_paths.json")
			# Load the current graph from the workspace folder
			self.load_current_graph()
			self.load_step()

		else:
			self.create_workspace(choice)

	def create_workspace(self, workspace_name: str):
		"""

		Args:

		"""
		# Create a new directed graph for the workspace
		self.current_graph = nx.DiGraph()
		# Create a workspace folder
		workspace_path = str(Path(self.path_dict["working_dir"]) / Path(workspace_name))
		if not self.f_io.create_directory(workspace_path):
			log.error(f"Failed to create workspace directory at: {workspace_path}")
		self.workspace_name = workspace_name
		self.path_dict["workspace_dir"] = workspace_path
		self.init_test_draft_steps()
		self.save_workspace_paths()

	def init_test_draft_steps(self):
		"""

		Args:

		"""

		workspace_dir = self.path_dict["workspace_dir"]
		for step_name in TEST_DRAFT_STEP_LIST:
			self.current_graph.add_node(step_name, type="step")
			# Create a folder for this step in our current workspace
			folder_path = str(Path(workspace_dir) / f"{step_name}")
			if not self.f_io.create_directory(folder_path):
				log.error(f"Unable to create directory for step: {step_name}!")
			self.path_dict[step_name] = folder_path
			
		self.path_dict["test_plan_path"] = str(Path(self.path_dict["workspace_dir"]) / "test_plan.json")
		# Save the graph
		self.save_current_graph()
		self.save_workspace_paths()

	def load_step(self):
		"""
		
		Args:

		"""
		# Store the folder names within the self.path_dict["workspce_dir"] directory in a list of strings
		step_list = self.f_io.list_directory_contents(self.path_dict["workspace_dir"])
		# Provide the folder names to the user as a menu, asking the user to 'select a step to start from' or 'press enter to continue from the start'.
		step_list_str = []
		step_index = 0
		for step in step_list:
			if step[0].isdigit() and '.' not in step:
				log.info(f"{step_index}: {step}")
				step_list_str.append(step)
				step_index += 1
		choice = input(f"Select a step from the list or press enter to start from the beginning: {step_list_str[0]}\n")
		if (choice.isdigit() and int(choice) < len(step_list_str)) or choice in step_list_str:
			if choice.isdigit():
				log.debug(f"User used 'step index' as their choice: {choice}, step_list_str: {step_list_str}")
				self.cur_step_node = step_list_str[int(choice)]
			else:
				log.debug(f"User used 'literal step name' as their to select: {choice}")
				self.cur_step_node = choice
			# Custom path initializations we have to do, in real toolbox implementation this will be an initialization function which runs no matter what step we start at.
			self.path_dict[self.cur_step_node] = str(Path(self.path_dict["workspace_dir"]) / self.cur_step_node)
			self.path_dict["test_plan_path"] = str(Path(self.path_dict["workspace_dir"]) / "test_plan.json")
			log.debug(f"Setting cur_step_node to {self.cur_step_node}")
		else:
			self.cur_step_node = ""

	def save_workspace_paths(self):
		"""

		Args:

		"""
		save_dict = {}
		# log.debug(f"Saving workspace paths: {self.path_dict}")
		# This is a waste of time / processing but I cannot for the life of me find where we are saving the WindowsPath objects.
		for key, value in self.path_dict.items(): 
			save_dict[key] = str(value)
		self.f_io.write_json(Path(self.path_dict["workspace_dir"]) / "workspace_paths.json", save_dict)

	def load_current_graph(self):
		"""
		Loads the target graph for this workspace.

		Args:
			
		"""
		path_to_graph = Path(self.path_dict["workspace_dir"]) / f'{self.workspace_name}_graph.json'
		graph_data = self.f_io.parse_json_file(path_to_graph)
		log.debug(f"Graph data: {graph_data}")
		self.current_graph = nx.readwrite.json_graph.node_link_graph(graph_data, edges="edges")
		log.debug(f"Succesfully loaded graph: {self.current_graph}")

	def save_current_graph(self): 
		"""
		
		Args:

		"""
		path_to_save = Path(self.path_dict["workspace_dir"]) / f'{self.workspace_name}_graph.json'
		data = nx.readwrite.json_graph.node_link_data(self.current_graph, edges="edges")
		if not self.f_io.write_json(path_to_save, data):
			log.error(f"Failed to save graph at location: {path_to_save}")
			log.error(f"Graph: {data}")
		log.debug(f"Successfully saved graph {path_to_save}")

	def instantiate_io_node(self):
		"""
		
		Args:

		"""
		io_node_name = datetime.now().strftime("%Y_%m_%d_%M_%S")
		self.current_graph.add_node(io_node_name, type="io")
		self.cur_io_node = self.current_graph.nodes[io_node_name]
		self.cur_io_node["name"] = io_node_name
		
		step_path = self.path_dict[self.cur_step_node]
		self.path_dict[io_node_name] = str(Path(step_path) / io_node_name)
		# Create our node folder
		if not self.f_io.create_directory(self.path_dict[io_node_name]):
			log.error(f"Unable to create directory for node: {self.path_dict[io_node_name]}")

	def _llm_call(self, prompt, force_json: bool = True, json_schema: dict = None, prompt_tag: str = "") -> dict:
		"""
		
		Args:
		
		"""
		node_folder = self.path_dict[self.cur_io_node["name"]]
		
		# Ensure the node folder has the prompt
		node_path = Path(node_folder) / f"{prompt_tag}_prompt.txt"
		if not self.f_io.write_file(node_path, prompt):
			log.error(f"Unable to write to {node_path}")


		llm_response, llm_stats = self.llm.call_gemini(prompt, force_json, json_schema)

		# Ensure the node folder has the response
		node_path = Path(node_folder) / f"{prompt_tag}_response.txt"
		if not self.f_io.write_file(node_path, llm_response):
			log.error(f"Unable to write to {node_path}")

		# Ensure the node folder has the stats
		node_path = Path(node_folder) / f"{prompt_tag}_stats.json"
		if not self.f_io.write_json(node_path, llm_stats):
			log.error(f"Unable to write to {node_path}")
		
		return llm_response

	def _llm_call_worker(self, task: dict) -> dict:
		"""
		A private worker function that executes a single LLM call task.
		It's designed to be called by the ThreadPoolExecutor.

		Args:
			task (dict): A dictionary containing the task_id and all arguments for _llm_call.

		Returns:
			dict: A dictionary containing the original task_id and the 'result' from the LLM.
		"""
		task_id = task['task_id']
		log.debug(f"Thread worker starting task: {task_id}")
		try:
			result = self._llm_call(
				prompt=task['prompt'],
				force_json=task.get('force_json', True),
				json_schema=task.get('json_schema'),
				prompt_tag=task.get('prompt_tag', task_id))
			return {'task_id': task_id, 'result': result}
		except Exception as e:
			log.error(f"Error executing LLM task '{task_id}': {e}", exc_info=True)
			return {'task_id': task_id, 'result': None, 'error': e}

	def _run_llm_tasks_in_parallel(self, tasks: list, max_workers: int = 10) -> dict:
		"""
		A generic function to run multiple _llm_call tasks in parallel.

		Args:
			tasks (List[Dict[str, Any]]): A list of task dictionaries. Each dictionary
				must have a unique 'task_id' and the arguments for the _llm_call method
				(e.g., 'prompt', 'force_json', 'prompt_tag').
			max_workers (int): The maximum number of threads to use.

		Returns:
			Dict[str, Any]: A dictionary mapping each task_id to its LLM result.
						   Returns None for tasks that failed.
		"""
		results = {}
		with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='llm_worker') as executor:
			# Submit all tasks to the executor
			future_to_task_id = {executor.submit(self._llm_call_worker, task): task['task_id'] for task in tasks}

			log.debug(f"Submitted {len(tasks)} LLM tasks to the thread pool.")

			# Process results as they are completed
			for future in concurrent.futures.as_completed(future_to_task_id):
				task_id = future_to_task_id[future]
				try:
					# Get the result from the future
					task_result = future.result()
					if 'error' in task_result:
						log.error(f"Task '{task_id}' failed with error: {task_result['error']}")
						results[task_id] = None
					else:
						results[task_id] = task_result['result']
				except Exception as exc:
					log.error(f"Task '{task_id}' generated an exception: {exc}", exc_info=True)
					results[task_id] = None
		
		log.info("All LLM tasks have completed.")
		return results
		
	def select_node(self) -> list:
		"""

		Args:

		"""
		list_of_nodes = self.current_graph.nodes(data=True)
		valid_node_found = False
		while not valid_node_found:
			step_list = []
			for flow_node in list_of_nodes:
				log.debug(f"Flow node: {flow_node}")
				if flow_node[1]["type"] in ["step"]:
					log.debug(f"	Flow node is a step.")
					if self.cur_step_node == "": # If there isn't a step we are looking for, collect current and future steps
						step_list.append((flow_node[0], flow_node[1]))
						log.debug(f"	Step list: {step_list}")
						valid_node_found = True
					elif self.cur_step_node.lower() == flow_node[0].lower(): # If there is a step we are starting at, only add steps AFTER it has been found
						self.cur_step_node = ""
						io_node_keydickterator = self.current_graph.predecessors(flow_node[0])
						io_node_list = []
						for io_node in io_node_keydickterator:
							io_node_list.append(io_node)
						# Provide the io_node_list entries to the user in a selectable list
						for index, io_node in enumerate(io_node_list):
							log.info(f"{index}: {io_node}")
						if len(io_node_list) > 0:
							choice = input(f"Select a node from the list or press enter to use the last node. ")
							if choice.isdigit() and int(choice) < len(io_node_list):
								self.prev_io_node = self.current_graph.nodes[io_node_list[int(choice)]]
							else:
								self.prev_io_node = self.current_graph.nodes[io_node_list[-1]]

							valid_node_found = True
						else:
							log.info("No previous nodes found. Must try previous step to see if it has previous nodes populated.")
							# Get the flow_node[0] index inside the test_draft_step_list and then set our cur_step_node to the previous step
							step_index = TEST_DRAFT_STEP_LIST.index(flow_node[0])
							self.cur_step_node = TEST_DRAFT_STEP_LIST[step_index - 1]
							log.info(f"Changing starting step to {self.cur_step_node}")
							break

						step_list.append((flow_node[0], flow_node[1]))
			
		return step_list

	def execute_steps(self):
		"""
		
		Args:

		"""

		step_list = self.select_node()

		try:
			for flow_node in step_list:
				log.info(f"Executing step: {flow_node[0]}")
				self.cur_step_node = flow_node[0]
				self.instantiate_io_node()

				# Obviously the real drafter toolbox will execute functions via runtime dynamic evocation
				if flow_node[0][2:] == "draft_test_plan_shell":
					self.draft_test_plan_shell()
				
				if flow_node[0][2:] == "populate_test_plan":
					self.populate_test_plan()

				if flow_node[0][2:] == "populate_test_description":
					self.populate_test_description()

				if flow_node[0][2:] == "populate_function_details":
					self.populate_function_details()

				if flow_node[0][2:] == "populate_test_logic":
					self.populate_test_logic()

				if flow_node[0][2:] == "draft_test_case_shell":
					self.draft_test_case_shell()

				if flow_node[0][2:] == "populate_test_case":
					self.populate_test_case()

				if flow_node[0][2:] == "populate_test_case_details":
					self.populate_test_case_details()

				if flow_node[0][2:] == "populate_test_files":
					self.populate_test_files()

				if flow_node[0][2:] == "_populate_test_plan_tests":
					self.populate_test_plan_tests()

				self.current_graph.add_edge(flow_node[0], self.cur_io_node["name"]) # Cur_step -> Cur_node
				if flow_node[0][2:] != "draft_test_plan_shell":
					self.current_graph.add_edge(self.prev_io_node["name"], flow_node[0]) # Prev_node -> Cur_step
				
				self.save_current_graph() # Save the graph after each step
				self.save_workspace_paths()
				self.prev_io_node = self.cur_io_node
				log.info(f"Completed step: {flow_node[0]}")

		except Exception as e:
			log.error(f"Hit an exception during execute_steps. Saving workspace and graph. Traceback: {e}")

		finally:
			self.save_current_graph()
			self.save_workspace_paths()

	def write_node_file(self, target_path: str, content: str):
		"""
		Writes a file to the target path and the current node folder.

		Args:
			target_path (str): Path to the target file to be written
			content (str): Content to be written to the target file

		Returns:
			True if the file was written successfully, False otherwise
		"""

		if not self.f_io.write_file(target_path, content):
			log.error(f"Unable to create file at: {target_path}")
			return False
		file_name = Path(target_path).name
		node_path = Path(self.path_dict[self.cur_io_node["name"]]) / file_name
		if not self.f_io.write_file(node_path, content):
			log.error(f"Unable to create file at: {node_path}")
			return False

		return True

	def write_node_file_json(self, target_path: str, content: dict):
		"""
		Writes a JSON file to the target path and the current node folder.
		
		Args:
			target_path (str): Path to the target file to be written
			content (dict): Dictionary to be written to the target file

		Returns:
			True if the file was written successfully, False otherwise
		"""
		if not self.f_io.write_json(target_path, content):
			log.error(f"Unable to create file at: {target_path}")
			return False
		
		file_name = Path(target_path).name
		node_path = Path(self.path_dict[self.cur_io_node["name"]]) / file_name
		if not self.f_io.write_json(node_path, content):
			log.error(f"Unable to create file at: {node_path}")
			return False

		return True


	def draft_test_plan_shell(self):
		"""
		
		Args:

		"""
		
		target_path = self.path_dict["target_file"]

		shell_content = {}
		
		shell_content["metadata"] = {}
		target_name = Path(target_path).name
		target_name = target_name.split(".")[0] # Remove the extension
		shell_content["metadata"]["name"] = target_name + "_test_plan"
		module_under_test = Path(target_path).parent.name + "/" + Path(target_path).name
		shell_content["metadata"]["module_under_test"] = module_under_test
		shell_content["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")

		shell_content["test_cases"] = []
		test_plan_path = self.path_dict["test_plan_path"]
		if not self.write_node_file_json(test_plan_path, shell_content):
			self.log.error(f"Failed to write test plan shell to file: {test_plan_path}")
			return False

	def populate_test_plan(self):
		"""
		Populates the test plan with TCs using LLM interaction.

		Args:

		"""
		target_path = self.path_dict["target_file"]
		test_plan_path = self.path_dict["test_plan_path"]
		node_folder = self.path_dict[self.cur_io_node["name"]]

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

		# Add the file content to the prompt_str
		file_content = self.f_io.read_file(target_path)
		total_prompt_str += f"\n\n[TARGET SCRIPT START]\n{file_content}\n[TARGET SCRIPT END]"

		for context_file in self.prompt_dict["populate_test_plan_prompt"]["context_files"]:
			file_content = self.f_io.read_file(context_file)
			total_prompt_str += f"\n\n{file_content}"
		
		if DEBUG_MODE:
			total_prompt_str += f"\n\nDEBUG MODE INITIATED; PLEASE ONLY POPULATE 2 TEST CASES AND 2 TESTS FOR EACH OF THOSE TEST CASES! DO NOT POPULATE THE TEST PLAN FOR THE FULL VALIDATION"

		# Just for reference
		expected_dict = {
			"test_cases":[{"name":"", "type":"", "subtype":"", "purpose":"", "script_functions_tested":[], "tests": []}]
		}
		# This schema should restrict us to the above return format
		schema_for_dict = {
			"type": "OBJECT",
			"properties": {
				"test_cases": {
					"type": "ARRAY",
					"items": {
						"type": "OBJECT",
						"properties": {
							"name": {"type": "STRING"},
							"type": {"type": "STRING"},
							"subtype": {"type": "STRING"},
							"purpose": {"type": "STRING"},
							"script_functions_tested": {
								"type": "ARRAY",
								"items": {"type": "STRING"}
							},
							"tests": {
								"type": "ARRAY",
								"items": {"type": "STRING"}
							}
						},
						# Specifying required fields ensures the model includes them
						"required": ["name", "type", "subtype", "purpose", "script_functions_tested", "tests"]
					}
				}
			},
			"required": ["test_cases"]
		}
		prompt_result_dict = self._llm_call(total_prompt_str, force_json=True, json_schema=schema_for_dict, prompt_tag="populate_test_plan")
		test_cases_list = []

		prompt_result_dict = json.loads(prompt_result_dict)
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
		if not self.write_node_file_json(test_plan_path, test_plan_dict):
			self.log.error(f"Failed to write test plan to file: {test_plan_path}")

	def populate_test_description(self):
		"""
		Populates a test logic file with test logic.

		Args:

		"""
		test_plan_path = Path(self.path_dict[self.prev_io_node["name"]]) / "test_plan.json"
		test_plan_dict = self.f_io.parse_json_file(test_plan_path)
		test_case_list = test_plan_dict["test_cases"]
		llm_tasks = []
		for test_case_dict in test_case_list:
			tc_name = test_case_dict["name"]
			tc_type = test_case_dict["test_case_type"]
			tc_subtype = test_case_dict["test_case_subtype"]
			tc_purpose = test_case_dict["purpose"]
			tc_functions = test_case_dict["script_functions_tested"]
			tc_tests = ""
			for test_entry in test_case_dict["tests"]:
				t_name = test_entry["test_name"]
				tc_tests += f"{t_name}"
			tc_description = f"Name: {tc_name}, Type: {tc_type}, Subtype: {tc_subtype}, Purpose: {tc_purpose}, Tests: {tc_tests}"

			for test_dict in test_case_dict["tests"]:

				test_name = test_dict["test_name"]

				total_prompt_str = self.prompt_dict["populate_test_description_prompt"]["prompt_content"]

				for context_file in self.prompt_dict["populate_test_description_prompt"]["context_files"]:
					file_content = self.f_io.read_file(context_file)
					total_prompt_str += f"\n{file_content}"
				
				total_prompt_str += f"\n[TEST CASE DESCRIPTION START]\n{tc_description}\n[TEST CASE DESCRIPTION END]"
				total_prompt_str += f"\n[TEST NAME START]\n{test_name}\n[TEST CASE DESCRIPTION END]"
				total_prompt_str += f"\n[TEST CASE FUNCTION(S) START]\n{tc_functions}\n[TEST CASE FUNCTION(S) END]"
				
				functions_to_use_list = []
				for function_to_use in FUNCTIONS_FOR_TESTING:
					if function_to_use in tc_functions:
						continue
					else:
						functions_to_use_list.append(function_to_use)

				total_prompt_str += f"\n[FUNCTIONS TO USE START]\n{functions_to_use_list}\n[FUNCTIONS TO USE END]"

				# Just for reference
				expected_dict = {
					"test_description": "",
					"functions_used": []
				}
				# This should restrict the LLM output to the dictionary above
				json_schema_dict = {
				"type": "OBJECT",
				"properties": {
					"test_description": {"type": "STRING"},
					"functions_used": {
						"type": "ARRAY",
						"items": {"type": "STRING"}
					}
				},
				"required": ["test_description", "functions_used"]
				}
				task_id = f"{tc_name}_{test_name}"
				llm_tasks.append({
					"task_id": task_id,
					"prompt": total_prompt_str,
					"force_json": True,
					"json_schema": json_schema_dict,
					"prompt_tag": task_id
				})

		llm_results = self._run_llm_tasks_in_parallel(llm_tasks, max_workers=100)
		for task_id, result in llm_results.items():
			prompt_result_dict = json.loads(result)
			# Write as a node file
			node_path = Path(self.path_dict["workspace_dir"]) / f"{task_id}_logic.json"
			self.write_node_file_json(node_path, prompt_result_dict)
	
	def populate_function_details(self):
		"""
		
		Args:

		"""

		test_plan_path = self.path_dict["test_plan_path"]
		test_plan_dict = self.f_io.parse_json_file(test_plan_path)
		test_case_list = test_plan_dict["test_cases"]
		llm_tasks = []
		functions_dict = {
			"FULL": {},
			"LIMITED": {}
		}
		test_functions_dict = {}
		for test_case_dict in test_case_list:
			tc_functions_tested = test_case_dict["script_functions_tested"]
			for test_dict in test_case_dict["tests"]:
				# Get the logic description created in the previous step's node
				test_name = test_dict["test_name"]
				test_case_name = test_case_dict["name"]
				logic_path = Path(self.path_dict[self.prev_io_node["name"]]) / f"{test_case_name}_{test_name}_logic.json"
				logic_dict = self.f_io.parse_json_file(logic_path)
				self.path_dict[f"{test_case_name}_{test_name}_logic"] = str(logic_path)
				log.debug(f"	Logic path: {logic_path}")
				functions_used = logic_dict["functions_used"]
				test_functions_dict[f"{test_case_name}_{test_name}"] = functions_used
				for function_name in functions_used:

					total_prompt_str = self.prompt_dict["populate_function_details_prompt"]["prompt_content"]
					# Need to access the script file for any function referenced
					script_folder = ""
					function_file = function_name.split('.')[0]
					if '_auditor' in function_file.lower():
						script_folder = 'AUDITORS'
					elif '_drafter' in function_file.lower():
						script_folder = 'DRAFTERS'
					elif '_toolbox' in function_file.lower():
						script_folder = 'TOOLBOXES'
					else:
						log.error(f"Could not determine script type for: {function_name}.")

					script_path = Path(_PROJECT_ROOT) / Path(script_folder) / Path(f"{function_file}.py")

					function_type = ""

					# If the function is part of the test case 'tested functions'
					if function_name in tc_functions_tested:
						# Check if we have a cached version before we use an LLM
						if function_name in functions_dict["FULL"].keys():
							continue
						else:
							script_content = self.f_io.read_file(script_path)
							total_prompt_str += f"\n[TARGET SCRIPT START]\n{script_content}\n[TARGET SCRIPT END]"
							total_prompt_str += f"\n[EXTRACTION TYPE START]\nFULL\n[EXTRACTION TYPE END]"
							function_type = "FULL"
							functions_dict[function_type][function_name] = ""


					# If the function is just helping us execute the test
					else:
						# Check if we have a cached version before we use an LLM
						if function_name in functions_dict["LIMITED"].keys():
							continue							
						else:
							script_content = self.f_io.read_file(script_path)
							total_prompt_str += f"\n[TARGET SCRIPT START]\n{script_content}\n[TARGET SCRIPT END]"
							total_prompt_str += f"\n[EXTRACTION TYPE START]\nLIMITED\n[EXTRACTION TYPE END]"
							function_type = "LIMITED"
							functions_dict[function_type][function_name] = ""
				
					llm_tasks.append({
						"task_id": f"{function_name}!{function_type}",
						"prompt": total_prompt_str,
						"force_json": False,
						"prompt_tag": f"{function_name}"
					})

		llm_results = self._run_llm_tasks_in_parallel(llm_tasks, max_workers=100)
		for function_tag, result in llm_results.items():
			function_type = function_tag.split("!")[1]
			function_name = function_tag.split("!")[0]
			functions_dict[function_type][function_name] = result

		for tc_test_name, functions_used in test_functions_dict.items():
			functions_needed = []
			functions_tested = []
			for function_name in functions_used:
				if function_name in functions_dict["FULL"].keys():
					functions_tested.append(functions_dict["FULL"][function_name])
				else:
					functions_needed.append(functions_dict["LIMITED"][function_name])

			tested_path = Path(self.path_dict["workspace_dir"]) / f"{tc_test_name}_functions_to_test.txt"
			needed_path = Path(self.path_dict["workspace_dir"]) / f"{tc_test_name}_functions_needed.txt"

			self.write_node_file(tested_path, str(functions_tested))
			self.write_node_file(needed_path, str(functions_needed))


	def populate_test_logic(self):
		"""
		
		Args:

		"""

		test_plan_path = self.path_dict["test_plan_path"]
		test_case_list = self.f_io.parse_json_file(test_plan_path)["test_cases"]

		llm_tasks = []
		for test_case_dict in test_case_list:
			for test_dict in test_case_dict["tests"]:
				tc_name = test_case_dict["name"]
				test_name = test_dict["test_name"]
				test_logic_path = self.path_dict[f"{tc_name}_{test_name}_logic"]
				test_description = self.f_io.parse_json_file(test_logic_path)
				

				tested_functions = self.f_io.read_file(Path(self.path_dict[self.prev_io_node["name"]]) / f"{tc_name}_{test_name}_functions_to_test.txt")
				needed_functions = self.f_io.read_file(Path(self.path_dict[self.prev_io_node["name"]]) / f"{tc_name}_{test_name}_functions_needed.txt")
				tc_type = test_case_dict["test_case_type"]
				tc_subtype = test_case_dict["test_case_subtype"]
				test_case_details = f"Test Case Name: {tc_name} | Test Case Type/Subtype: {tc_type}.{tc_subtype}"

				total_prompt_str = self.prompt_dict["populate_test_logic_prompt"]["prompt_content"]

				for context_file in self.prompt_dict["populate_test_logic_prompt"]["context_files"]:
					file_content = self.f_io.read_file(context_file)
					total_prompt_str += f"\n{file_content}"
				total_prompt_str += f"\n[TEST CASE DETAILS START]\n{test_case_details}[TEST CASE DETAILS END]"
				total_prompt_str += f"\n[TEST NAME START]\n{test_name}\n[TEST NAME END]"
				total_prompt_str += f"\n[TEST DESCRIPTION START]\n{test_description}\n[TEST DESCRIPTION END]"
				total_prompt_str += f"\n[FUNCTION(S) TESTED DETAILS START]\n{tested_functions}\n[FUNCTION(S) TESTED DETAILS END]"
				total_prompt_str += f"\n[FUNCTION(S) NEEDED DETAILS START]\n{needed_functions}\n[FUNCTION(S) NEEDED DETAILS END]"

				# Just for reference of what the LLM should return
				expected_dict = {
					"ordered_function_calls": [],
					"expected_exceptions": [],
					"file_comparison": [],
					"return_value": []
				}
				# This schema should restrict the LLM to the above return
				json_schema_dict = {
				"type": "OBJECT",
				"properties": {
					"ordered_function_calls": {
						"type": "ARRAY",
						"items": {"type": "STRING"}
					},
					"expected_exceptions": {
						"type": "ARRAY",
						"items": {"type": "STRING"}
					},
					"file_comparison": {
						"type": "ARRAY",
						"items": {"type": "STRING"}
					},
					"return_value": {
						"type": "ARRAY",
						"items": {"type": "STRING"}
					}
				},
				"required": ["ordered_function_calls", "expected_exceptions", "file_comparison", "return_value"]
				}
				task_id = f"{tc_name}_{test_name}"
				llm_tasks.append({
					"task_id": task_id,
					"prompt": total_prompt_str,
					"force_json": True,
					"json_schema": json_schema_dict,
					"prompt_tag": task_id
				})

		llm_results = self._run_llm_tasks_in_parallel(llm_tasks, max_workers=100)
		for task_id, result in llm_results.items():
			prompt_result_dict = json.loads(result)
			# Write as a node file
			logic_path = Path(self.path_dict["workspace_dir"]) / f"{task_id}_logic.json"
			self.write_node_file_json(logic_path, prompt_result_dict)

	def draft_test_case_shell(self):
		"""
		
		Args:

		"""

		test_plan_path = self.path_dict["test_plan_path"]
		test_case_list = self.f_io.parse_json_file(test_plan_path)["test_cases"]
		for test_case_dict in test_case_list:
			test_case_name = test_case_dict["name"]
			test_case_path = Path(self.path_dict["workspace_dir"]) / f"{test_case_name}.json"

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
				t_name = test["test_name"]
				test_content_dict = {}
				test_content_dict["test_name"] = t_name
				test_content_dict["files"] = {}
				test_content_dict["functions"] = {}
				test_content_dict["class_instance_args"] = []
				if "expected_exception" in test["validation_method"]:
					test_content_dict["expected_exception"] = []
				if "expected_return_value_and_order" in test["validation_method"]:
					test_content_dict["expected_return_value_and_order"] = {}
				if "expected_file_content" in test["validation_method"]:
					test_content_dict["expected_file_content"] = []
				test_content_dict["test_steps_order"] = []
				tp_organized_data["tests"].append(test_content_dict)

			if not self.write_node_file_json(test_case_path, tp_organized_data):
				self.log.error(f"Failed to write test case template to file: {test_case_path}")
	
	def populate_test_case(self):
		"""

		Args:

		"""

		test_plan_path = self.path_dict["test_plan_path"]
		test_case_list = self.f_io.parse_json_file(test_plan_path)["test_cases"]

		llm_tasks = []
		for test_case_dict in test_case_list:
			test_case_name = test_case_dict["name"]
			test_case_path = Path(self.path_dict["workspace_dir"]) / f"{test_case_name}.json"
			test_case_file_dict = self.f_io.parse_json_file(test_case_path)

			# For each test within the test case file (test_name in tests will be defined)
			for test in test_case_file_dict["tests"]:
				# Load the corresponding test logic json file
				test_name = test["test_name"]
				test_logic_path = self.path_dict[f"{test_case_name}_{test_name}_logic"]
				test_logic_content = self.f_io.parse_json_file(test_logic_path)
				# Create the prompt
				total_prompt_str = self.prompt_dict["populate_test_case_prompt"]["prompt_content"]
				for context_file in self.prompt_dict["populate_test_case_prompt"]["context_files"]:
					file_content = self.f_io.read_file(context_file)
					total_prompt_str += f"\n\n{file_content}"
				total_prompt_str += f"\n\n[TEST LOGIC FILE START]\n{test_logic_content}\n[TEST LOGIC FILE END]"
				total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_dict}\n[TEST CASE FILE END]"

				task_id = f"{test_case_name}&{test_name}"
				# Prompt LLM to fill in the test case file for that particular test.
				llm_tasks.append({
					"task_id": task_id,
					"prompt": total_prompt_str,
					"force_json": True,
					"prompt_tag": task_id
				})

		llm_results = self._run_llm_tasks_in_parallel(llm_tasks, max_workers=100)
		test_case_dict = {}
		for task_id, result in llm_results.items():
			test_case_name = task_id.split('&')[0]
			test_name = task_id.split('&')[1]
			prompt_result_dict = json.loads(result)
			# Fill in the test case file for that particular test.
			prompt_result_dict["test_name"] = test_name
			if test_case_name not in test_case_dict.keys():
				test_case_dict[test_case_name] = []	
			test_case_dict[test_case_name].append(prompt_result_dict)

		for test_case_name, tests in test_case_dict.items():
			test_case_path = Path(self.path_dict["workspace_dir"]) / f"{test_case_name}.json"

			# Parse the test case file as .json to dictionary
			# Add the tests to the test case file
			test_case_file_dict = self.f_io.parse_json_file(test_case_path)
			test_case_file_dict["tests"] = tests
			# Write the response to the test case file
			if not self.write_node_file_json(test_case_path, test_case_file_dict):
				log.error(f"Failed to write test case to file: {test_case_path}")

	def populate_test_case_details(self):
		"""
		
		Args:

		"""

		test_plan_path = self.path_dict["test_plan_path"]
		test_case_list = self.f_io.parse_json_file(test_plan_path)["test_cases"]
		
		llm_tasks = []

		for test_case_dict in test_case_list:
			test_case_name = test_case_dict["name"]
			test_case_path = Path(self.path_dict["workspace_dir"]) / f"{test_case_name}.json"
			test_case_file_dict = self.f_io.parse_json_file(test_case_path)

			# Load the 'populate_test_case_details.md' prompt.
			total_prompt_str = self.prompt_dict["populate_test_case_details_prompt"]["prompt_content"]
			for context_file in self.prompt_dict["populate_test_case_details_prompt"]["context_files"]:
				file_content = self.f_io.read_file(context_file)
				total_prompt_str += f"\n\n{file_content}"
			total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_file_dict}\n[TEST CASE FILE END]"

			task_id = test_case_name
			llm_tasks.append({
				"task_id": task_id,
				"prompt": total_prompt_str,
				"force_json": True,
				"prompt_tag": task_id
			})

		llm_results = self._run_llm_tasks_in_parallel(llm_tasks, max_workers=100)
		for task_id, result in llm_results.items():
			prompt_result_dict = json.loads(result)

			test_case_path = Path(self.path_dict["workspace_dir"]) / f"{task_id}.json"

			# write the prompt_result_dict to the test_case_path
			if not self.write_node_file_json(test_case_path, prompt_result_dict):
				log.error(f"Failed to write prompt result to file: {test_case_path}")

	def populate_test_files(self):
		"""
		
		Args:

		"""

		test_plan_path = self.path_dict["test_plan_path"]
		test_case_list = self.f_io.parse_json_file(test_plan_path)["test_cases"]

		llm_tasks = []
		file_metadata = {}

		for test_case_dict in test_case_list:
			test_case_name = test_case_dict["name"]
			test_case_path = Path(self.path_dict["workspace_dir"]) / f"{test_case_name}.json"
			test_case_file_dict = self.f_io.parse_json_file(test_case_path)
			test_files_to_populate = test_case_file_dict["files_definitions"]
			
			# For each test in file_definitions
			for test, file_list in test_files_to_populate.items():
				for file_def_dict in file_list:
					# Load the 'populate_test_files_prompt.md' prompt.
					total_prompt_str = self.prompt_dict["populate_test_files_prompt"]["prompt_content"]
					for context_file in self.prompt_dict["populate_test_files_prompt"]["context_files"]:
						file_content = self.f_io.read_file(context_file)
						total_prompt_str += f"\n\n{file_content}"
					total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_file_dict}\n[TEST CASE FILE END]"
					total_prompt_str += f"\n\n[FILE DEFINITION START]\n{file_def_dict}\n[FILE DEFINITION END]"
					
					task_id = f"{test_case_name}_{test}_{file_def_dict['name']}"
					is_json = "json" in file_def_dict["key"]
					llm_tasks.append({
						"task_id": task_id,
						"prompt": total_prompt_str,
						"force_json": is_json,
						"prompt_tag": task_id
					})
					file_metadata[task_id] = {
						"file_path": Path(self.path_dict["workspace_dir"]) / file_def_dict["name"],
						"is_json": is_json
					}

		llm_results = self._run_llm_tasks_in_parallel(llm_tasks, max_workers=100)
		for task_id, result in llm_results.items():
			metadata = file_metadata[task_id]
			file_path = metadata['file_path']

			if metadata['is_json'] and len(result) > 1:
				try:
					content_to_write = json.loads(result)
				except:
					if not self.write_node_file(file_path, result):
						log.error(f"Failed to write file: {file_path}")
				if not self.write_node_file_json(file_path, content_to_write):
					log.error(f"Failed to write file: {file_path}")
			else:
				if not self.write_node_file(file_path, result):
					log.error(f"Failed to write file: {file_path}")


	def populate_test_plan_tests(self):
		"""

		Args:

		"""
		# Just for reference for what the LLM should return as its dictionary
		expected_return_dict = {
			"tests":[{
				"test_name": "",
				"functions_used": [],
				"description_of_steps": "",
				"expected_outcome": "",
				"validation_method": []
			}]
		}
		# This schema should restrict the response from the LLM to the above dictionary
		json_schema_dict = {
			"type": "OBJECT",
			"properties": {
				"tests": {
					"type": "ARRAY",
					"items": {
						"type": "OBJECT",
						"properties": {
							"test_name": {"type": "STRING"},
							"functions_used": {
								"type": "ARRAY",
								"items": {"type": "STRING"}
							},
							"description_of_steps": {"type": "STRING"},
							"expected_outcome": {"type": "STRING"},
							"validation_method": {
								"type": "ARRAY",
								"items": {"type": "STRING"}
							}
						},
						"required": ["test_name", "functions_used", "description_of_steps", "expected_outcome", "validation_method"]
					}
				}
			},
			"required": ["tests"]
		}

		test_plan_path = self.path_dict["test_plan_path"]
		test_plan_dict = self.f_io.parse_json_file(test_plan_path)
		test_cases_list = test_plan_dict["test_cases"]
		llm_tasks = []

		for test_case in test_cases_list:
			# Load the test case file
			test_case_name = test_case["name"]
			test_case_path = Path(self.path_dict["workspace_dir"]) / f"{test_case_name}.json"
			test_case_file_dict = self.f_io.parse_json_file(test_case_path)

			# Load the prompt needed for this function
			total_prompt_str = self.prompt_dict["populate_test_plan_tests_prompt"]["prompt_content"]
			for context_file in self.prompt_dict["populate_test_plan_tests_prompt"]["context_files"]:
				file_content = self.f_io.read_file(context_file)
				total_prompt_str += f"\n\n{file_content}"
			total_prompt_str += f"\n\n[TEST CASE DEFINITION START]\n{test_case}\n[TEST CASE DEFINITION END]"
			total_prompt_str += f"\n\n[TEST CASE FILE START]\n{test_case_file_dict}\n[TEST CASE FILE END]"
			task_id = f"{test_case_name}"
			# Give the test case file as context for the LLM
			llm_tasks.append({
				"task_id": task_id,
				"prompt": total_prompt_str,
				"force_json": True,
				"json_schema": json_schema_dict,
				"prompt_tag": task_id
			})
			

		llm_results = self._run_llm_tasks_in_parallel(llm_tasks, max_workers=100)
		for task_id, result in llm_results.items():
			prompt_result_dict = json.loads(result)
			# Get a dictionary back which is the 'tests' list completely filled out for that test case with the appropriate dictionaries.
			test_case_list = test_plan_dict["test_cases"]
			for test_case in test_case_list:
				if test_case["name"] == task_id:
					test_case["tests"] = prompt_result_dict["tests"]
					break
			
		# Write the test plan to the file
		if not self.write_node_file_json(test_plan_path, test_plan_dict):
			log.error(f"Failed to write test plan to file: {test_plan_path}")

def test(test_plan_path: str) -> dict:


	"""
	Runs tests for this toolbox based on the provided test plan.

	Args:
		test_plan_path (str): The path to the JSON test plan file for this toolbox.

	Returns:
		dict: A dictionary containing the test results.
	"""
	return True

def main():
	"""
	Main execution function for the toolbox template.
	Primarily for demonstration or direct testing of toolbox methods.
	"""
	try:
		box = DrafterToolbox('C:\Harbor\MVP\TOOLBOXES\\file_io_toolbox.py', 'C:\Harbor\MVP\TOOLBOXES\\tests\\file_io_toolbox', 'C:\Harbor\MVP\STRUCTS\\test_struct.json')
	except KeyboardInterrupt:
		log.info("Keyboard interrupt detected. Exiting...")
		sys.exit(0)

if __name__ == "__main__":
	main()
