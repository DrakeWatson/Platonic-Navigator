#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
	Description: 
		The test toolbox contains a single class (TestToolBox) that contains functions used for running .json formatted tests for python scripts.
	Usage:
	
"""

import os
import sys

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import inspect
import json # Added for parsing string-encoded json in params
from pathlib import Path
from typing import Any, Dict, List, Tuple, Callable # Added for type hinting

# Assuming logging_toolbox.py and test_toolbox.py are in TOOLBOXES folder
# and TOOLBOXES is in PYTHONPATH or accessible
try:
	from TOOLBOXES import logging_toolbox
	from TOOLBOXES import file_io_toolbox
except ImportError as e:
	print(f"Error importing a core toolbox: {e}")
	sys.exit(1)

# Test result dict format
_T_RESULT_DICT = {
	"name":"", # Test name
	"status":"", # 'PASS' | 'FAIL' | 'NOT_RAN'
	"reason":""} # Empty for 'PASS', some description for the other two status values

# Test case result dict format
_TC_RESULT_DICT = {
	"name":"", # Test case name
	"type":"", # unit | integration | full
	"subtype":"", # input_validation | expected_failure | functional_validation
	"tests":[]} # List of _T_RESULT_DICTs

# Test function dict format
_FUNC_DICT = {
	"file_path": "", # The path to the file containing the function
	"class_node": None, # If a toolbox file we need to access the class node from ast
	"function_node": None, # Function node from ast
	"callable_func": None # Stores the actual callable function/method
}
log = logging_toolbox.LoggingToolbox()
f_io = file_io_toolbox.FileIOToolbox()

class TestToolbox:
	"""
	Class containing the basic testing infrastructure functionality for the repository.
	"""
	def __init__(self, test_plan_path: str):
		"""
		Initializes the TestToolbox for a particular test plan.

		Args:
			test_plan_path (str): A valid path to a script's test plan .json file.
		"""
		
		self.test_plan_path = test_plan_path
		self.timeline_str_dict = {"__init__": f"Test Plan: {test_plan_path}"}
		self.test_case_dict: Dict[str, Any] = {}
		self.test_folder_path = os.path.dirname(test_plan_path)
		self.test_plan = f_io.parse_json_file(test_plan_path)
		if self.test_plan == None:
			log.error("%s either contains nothing or is not a valid .json file. Cannot setup TestToolBox.", test_plan_path)
			# Consider raising an exception here to halt execution if test plan is invalid

		# Test case vars for easier cross function data access
		self.current_test_case_result_list: List[Dict[str, Any]] = [] # Stores results for current test case
		self.tc_index = 0
		self.tc_name = ""
		self.tc_type = ""
		self.tc_subtype = ""
		
		self.t_index = 0
		self.t_name = ""
		
		self.loaded_test_files: Dict[str, Any] = {} # Stores content of loaded files like JSONs for param referencing
		self.test_files_path_list: List[str] = [] # Stores paths to files listed in "files"
		self.prepared_functions: Dict[str, _FUNC_DICT] = {} # Stores prepared callable functions

		self.return_value_store: Dict[str, Any] = {} # Stores return values from functions using "return_pointers"

	def prepare_for_self_test(self, test_case_dict: Dict[str, Any]):
		"""
		Prepares the TestToolbox for self-testing by setting up the test environment.
		"""
		log.debug("Preparing for self-test with test_case_dict: %s", test_case_dict)
		self.test_case_dict = test_case_dict
		self.tc_name = list(test_case_dict.keys())[0]
		self._capture_timeline_event(function_name="prepare_for_self_test", 
									tag_category_list=["tc_name"], 
									variables_dict={"test_case_dict": test_case_dict, "tc_name": self.tc_name}, 
									pre_var_words="test_case_dict", 
									entry_context="Initializing test environment by extracting test case data and setting up instance variables. This prepares the TestToolbox to run self-contained tests.", 
									depth_of_detail="3")

	def execute_test_plan(self, test_case_name: str = "") -> dict:
		"""
		Executes all test cases defined in the test plan.
		Requires the following class variables have valid values:
			self.test_folder_path
			self.test_plan
		Args:
			test_case_name (str): The name of the test case to execute. If None, all test cases will be executed.
		Returns:
			A dictionary containing details about the results of the test plan execution
		"""
		if self.test_plan is None:
			log.error("Cannot run test plan, it has a value of None.")
			return {"error": "Test plan is None", "summary": {}, "details": []}

		overall_results_summary = {"passed": 0, "failed": 0, "not_ran": 0, "total_tests": 0}
		detailed_results = []

		if test_case_name != "":
			self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=[], 
								variables_dict={"test_case_name": test_case_name}, pre_var_words="test_case_name_defined", 
								entry_context=f"Starting targeted execution of specific test case '{test_case_name}'. All other test cases in the plan will be skipped.", depth_of_detail="4")
		else:
			self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=[], 
								variables_dict={}, pre_var_words="no_test_case_name_specified", 
								entry_context=f"No specific test case name provided, so executing all test cases defined in the test plan sequentially.", 
								depth_of_detail="4")

		for index, test_case_header in enumerate(self.test_plan.get("test_cases", [])):
			self.tc_index = index
			self.tc_name = test_case_header.get("name", f"unnamed_test_case_{index}")
			self.tc_type = test_case_header.get("test_case_type", "unknown").lower()
			self.tc_subtype = test_case_header.get("test_case_subtype", "unknown").lower()
			timeline_vars_dict = {"tc_index": self.tc_index, "test_case_header": test_case_header, 
									"tc_name": self.tc_name, "tc_type": self.tc_type, "tc_subtype": self.tc_subtype,
									"test_case_name": test_case_name}
			self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=["tc_name"], 
								variables_dict=timeline_vars_dict, pre_var_words="tc_index_and_test_case_header", 
								entry_context=f"Processing test case {index + 1} of {len(self.test_plan.get('test_cases', []))} named '{self.tc_name}'. Extracting metadata including type '{self.tc_type}' and subtype '{self.tc_subtype}' for execution planning.", depth_of_detail="3")
			if test_case_name != "" and self.tc_name != test_case_name:
				log.debug("Skipping test case %s because it is not the one specified to run.", self.tc_name)
				timeline_vars_dict = {"test_case_name": test_case_name, "tc_name": self.tc_name}
				self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=["tc_name"], 
								 variables_dict=timeline_vars_dict, pre_var_words="not_running_test_case", 
								 entry_context=f"Skipping test case '{self.tc_name}' because it doesn't match the specified target test case '{test_case_name}'. Moving to next test case in the plan.", 
								 depth_of_detail="2")
				continue

			test_case_starting_str = "| | | | | | Starting Test Case: %s | | | | | |" % (self.tc_name)
			test_case_purpose_str = "Purpose: %s" % (test_case_header.get("purpose", ""))
			test_case_type_str = "Type: %s, Subtype: %s" % (self.tc_type, self.tc_subtype)
			script_func_tested_str = "Script Functions Tested: %s" % (test_case_header.get("script_functions_tested", ""))
			num_tests = len(test_case_header.get("tests", []))
			test_case_tests_str = "Number of tests: %s" % (num_tests)
			log.line_break(width=len(test_case_starting_str))
			log.info(test_case_starting_str)
			log.line_break(width=len(test_case_starting_str))
			log.line_wrap(test_case_purpose_str, max_width=len(test_case_starting_str), offset_left=3)
			log.line_wrap(test_case_type_str, max_width=len(test_case_starting_str), offset_left=3)
			log.line_wrap(script_func_tested_str, max_width=len(test_case_starting_str), offset_left=3)
			log.line_wrap(test_case_tests_str, max_width=len(test_case_starting_str), offset_left=3)
			log.line_break(width=len(test_case_starting_str))
			timeline_vars_dict = {"test_case_starting_str": test_case_starting_str, 
						"test_case_purpose_str": test_case_purpose_str, 
						"test_case_type_str": test_case_type_str, 
						"script_func_tested_str": script_func_tested_str, 
						"test_case_tests_str": test_case_tests_str}
			self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=["tc_name"], 
								variables_dict=timeline_vars_dict, pre_var_words="test_case_metadata", 
								entry_context=f"Displaying comprehensive test case metadata including purpose, type information, and functions being tested. This provides context for understanding what will be executed in this test case.", depth_of_detail="1")
			self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=["tc_name"], 
								variables_dict={}, pre_var_words="test_case_metadata", 
								entry_context=f"Beginning execution of test case '{self.tc_name}' with {num_tests} individual tests defined. All test environment setup and execution will follow.", 
								depth_of_detail="4")

			test_case_file_path = os.path.join(self.test_folder_path, f"{self.tc_name}.json")
			current_tc_full_data = f_io.parse_json_file(test_case_file_path)
			timeline_vars_dict = {"test_case_file_path": test_case_file_path, "current_tc_full_data": current_tc_full_data}
			self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=["tc_name"], 
								variables_dict=timeline_vars_dict, pre_var_words="test_case_file_path", 
								entry_context=f"Loading detailed test case configuration from JSON file at '{test_case_file_path}'. This file contains all test definitions, expected results, and test environment setup instructions.", depth_of_detail="1")

			if current_tc_full_data is None:
				log.error("Test case file %s either contains nothing or is not a valid .json file. Skipping test case.", test_case_file_path)
				# Create a dummy result for the whole test case if file is missing/invalid
				tc_result_entry = {**_TC_RESULT_DICT, 
								   "name": self.tc_name, 
								   "type": self.tc_type, 
								   "subtype": self.tc_subtype,
								   "tests": [{**_T_RESULT_DICT, "name": "test_case_file_load", "status": "NOT_RAN", "reason": f"Failed to load {test_case_file_path}"}]}
				detailed_results.append(tc_result_entry)
				overall_results_summary["not_ran"] += 1 # Assuming one main "test" for loading the TC file
				overall_results_summary["total_tests"] +=1
				timeline_vars_dict = {"test_case_file_path": test_case_file_path}
				self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=["tc_name"], 
								 variables_dict=timeline_vars_dict, pre_var_words="test_case_file_load_error", 
								 entry_context=f"Critical error: Test case file '{test_case_file_path}' is either empty, missing, or contains invalid JSON. Marking this test case as NOT_RAN and continuing with remaining test cases.", 
								 depth_of_detail="2")
				continue

			self.test_case_dict[self.tc_name] = current_tc_full_data # Store the loaded test case data
			
			tc_specific_results = self._execute_test_case()
			detailed_results.append(tc_specific_results)

			for test_result in tc_specific_results.get("tests", []):
				overall_results_summary["total_tests"] += 1
				if test_result["status"] == "PASS":
					overall_results_summary["passed"] += 1
				elif test_result["status"] == "FAIL":
					overall_results_summary["failed"] += 1
				else: # NOT_RAN or other
					overall_results_summary["not_ran"] += 1
			
			log.info("Completed Test Case: %s", self.tc_name)
			
		final_report = {
			"test_plan_name": self.test_plan.get("metadata", {}).get("name", "Unnamed Test Plan"),
			"module_under_test": self.test_plan.get("metadata", {}).get("module_under_test", "N/A"),
			"summary": overall_results_summary,
			"details": detailed_results
		}
		timeline_vars_dict = {"final_report": final_report}
		self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=[], 
							   variables_dict=timeline_vars_dict, pre_var_words="final_report", 
							   entry_context=f"Generating comprehensive final test report with summary statistics and detailed results for all executed test cases. This report will be logged and saved to disk for analysis.", depth_of_detail="1")
		self._log_final_report(final_report)

		# Write the final report into a .json file inside the directory where the test_plan.json is
		# Report file name should be "test_report_<file_name>_<date_time>.json"
		report_file_name = f"test_report_{self.tc_name}_{logging_toolbox.datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
		report_file_path = os.path.join(self.test_folder_path, report_file_name)
		f_io.write_json(report_file_path, final_report)
		timeline_vars_dict = {"report_file_path": report_file_path}
		self._capture_timeline_event(function_name="execute_test_plan", tag_category_list=[], variables_dict=timeline_vars_dict, 
							   pre_var_words="report_file_path", entry_context=f"Saving test execution report to permanent file '{report_file_path}' for future reference and analysis. Timeline data will also be saved separately for debugging purposes.", 
							   depth_of_detail="1")
		timeline_file_name = f"timeline_{logging_toolbox.datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
		timeline_file_path = os.path.join(self.test_folder_path, timeline_file_name)
		f_io.write_json(timeline_file_path, self.timeline_str_dict)

		return final_report
	
	def _capture_timeline_event(self, function_name : str, tag_category_list: list, variables_dict: dict, pre_var_words: str, entry_context:str, depth_of_detail: str):
		"""
		Captures a timeline event for a given function.

		Args:
			function_name (str): The name of the function that is capturing the timeline event.
			tag_category_list (list): A list of categories to tag the timeline event with.
			variables_dict (dict): A dictionary of variables to include in the timeline event.
			pre_var_words (str): A string of words to include before the variables in the timeline event.
			entry_context (str): A string of words to include in the timeline event.
			depth_of_detail (str): A string describing the depth of detail to include in the timeline event. No fixed set, but the programmer should use strings consistently for easier data analysis.
		"""
		tag_category_criterion = ["tc_name", "t_name"]
		for category in tag_category_list:
			if category not in tag_category_criterion:
				# The tag category list is limited intentionally to reduce the scope and complexity of this timeline.
				log.error("%s not in %s", category, tag_category_criterion)
				# Raise something, cannot capture a full test plan execution if the infrastructure is broke
				raise ValueError(f"{category} not in {tag_category_criterion}")

		# Capture a timecode
		timecode = logging_toolbox.datetime.datetime.now().timestamp() * 1000
		# Add an entry to the timeline_str_dict which is of the format:
		timeline_str = f"{timecode}.{function_name}."
		for category in tag_category_list:
			if category == "tc_name":
				timeline_str += f"{self.tc_name}."
			elif category == "t_name":
				timeline_str += f"{self.t_name}."
		timeline_str += f"{pre_var_words}"
		stored_variable_dict = {}
		for variable, value in variables_dict.items():
			timeline_str += f".{variable}"
			stored_variable_dict[variable] = str(value)
		timeline_entry_dict = {"entry_context": entry_context, "variables_dict": stored_variable_dict, "depth_of_detail": depth_of_detail}
		log.debug("Captured timeline event: %s", timeline_str + f".{depth_of_detail}")
		self.timeline_str_dict[timeline_str + f".{depth_of_detail}"] = timeline_entry_dict

	def _log_final_report(self, final_report: dict):
		"""
		Formats the final_report dictionary for human readability and logs it
		line by line.

		Args:
			final_report (dict): The report dictionary to format and log.
		"""
		report_lines = []
		report_lines.append("=" * 60)
		report_lines.append("FINAL TEST REPORT")
		report_lines.append("=" * 60)
		report_lines.append(f"Test Plan Name: {final_report.get('test_plan_name', 'N/A')}")
		report_lines.append(f"Module Under Test: {final_report.get('module_under_test', 'N/A')}")
		report_lines.append("-" * 60)

		# --- Summary ---
		report_lines.append("Summary:")
		summary = final_report.get("summary", {})
		if isinstance(summary, dict):
			if not summary:
				report_lines.append("  No summary data provided.")
			for key, value in summary.items():
				report_lines.append(f"  {str(key).replace('_', ' ').title()}: {value}")
		elif isinstance(summary, str):
			report_lines.append(f"  {summary}")
		else:
			# Fallback for other summary types, consider if more specific formatting is needed
			summary_str_lines = json.dumps(summary, indent=2).splitlines()
			for line in summary_str_lines:
				report_lines.append(f"  {line}")
		report_lines.append("-" * 60)

		# --- Details ---
		report_lines.append("Test Case Breakdown:")
		details = final_report.get("details", [])
		if isinstance(details, list):
			if not details:
				report_lines.append("  No detailed results available.")
			for i, detail_item in enumerate(details):
				report_lines.append(f"  --- --- --- --- --- --- ---  ")
				if isinstance(detail_item, dict):
					for key, value in detail_item.items():
						# Nicer formatting for nested structures if they are common
						if isinstance(value, dict):
							report_lines.append(f"    {str(key).replace('_', ' ').title()}:")
							for sub_key, sub_value in value.items():
								report_lines.append(f"      {str(sub_key).replace('_', ' ').title()}: {sub_value}")
						elif isinstance(value, list):
							report_lines.append(f"    {str(key).replace('_', ' ').title()}:")
							if not value:
								report_lines.append(f"      (empty list)")
							for item_in_list in value:
								sub_name = item_in_list["name"]
								sub_status = item_in_list["status"]
								sub_reason = item_in_list["reason"]
								if sub_reason != "":
									format_item = f"{sub_name} | Status: {sub_status} | Reason: {sub_reason}"
								else:
									format_item = f"{sub_name} | Status: {sub_status}"
								report_lines.append(f"      - {format_item}")
						else:
							report_lines.append(f"    {str(key).replace('_', ' ').title()}: {value}")
				else:
					report_lines.append(f"    {str(detail_item)}") # Ensure detail_item is string
		report_lines.append("=" * 60)
		report_lines.append("END OF REPORT")
		report_lines.append("=" * 60)

		# Log each line separately
		for line in report_lines:
			log.info(line)

	def _execute_test_case(self) -> dict:
		"""
		Given a test case name, runs all tests within that test case and returns the results.
		Assumes self.tc_name, self.tc_type, self.tc_subtype, and self.test_case_dict[self.tc_name] are set.
		Args:
		Returns:
			A dictionary conforming to _TC_RESULT_DICT with results of the test case execution.
		"""
		tc_result_dict = {**_TC_RESULT_DICT, 
						  "name": self.tc_name, 
						  "type": self.tc_type, 
						  "subtype": self.tc_subtype, 
						  "tests": []}

		current_tc_data = self.test_case_dict[self.tc_name]
		timeline_vars_dict = {"current_tc_data": current_tc_data}
		self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="current_tc_data", 
							   entry_context=f"Beginning execution of test case '{self.tc_name}' with loaded test configuration data. This data contains all individual test definitions that will be processed sequentially.", depth_of_detail="1")

		for index, test_definition in enumerate(current_tc_data.get("tests", [])):
			self.t_index = index
			self.t_name = test_definition.get("test_name", f"unnamed_test_{index}")
			self.return_value_store.clear() # Clear previous test's return values
			self.loaded_test_files.clear() # Clear previously loaded test files' content
			self.prepared_functions.clear() # Clear previously prepared functions
			timeline_vars_dict = {"t_index": self.t_index, "t_name": self.t_name}
			self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="t_index_and_t_name", 
							   entry_context=f"Starting individual test '{self.t_name}' (test {index + 1} in this test case). Clearing previous test state including return values, loaded files, and prepared functions to ensure clean test environment.", depth_of_detail="1")

			test_cases = self.test_plan.get("test_cases", {})
			test_case_data = next((test_case for test_case in test_cases if test_case["name"] == self.tc_name), None)
			timeline_vars_dict = {"test_case_data": test_case_data}
			self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_case_data", 
							   entry_context=f"Retrieving test case metadata from the test plan to access high-level information about the current test case. This metadata provides context about the overall test case structure.", depth_of_detail="1")
			if test_case_data is None:
				log.error("Test case '%s' not found in test plan.", self.tc_name)
				timeline_vars_dict = {"tc_name": self.tc_name}
				self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_case_data_not_found", 
							   entry_context=f"Critical error: Test case '{self.tc_name}' is not found in the test plan metadata. This indicates a mismatch between the test case file and the test plan definition, skipping to next test.", 
							   depth_of_detail="2")
				continue

			test_case_data = test_case_data.get("tests", [])
			test_details = next((test for test in test_case_data if test["test_name"] == self.t_name), None)
			timeline_vars_dict = {"test_details": test_details}
			self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_details", 
							   entry_context=f"Extracting specific test definition details from the test plan for test '{self.t_name}'. These details include function usage, expected outcomes, and validation methods required for test execution.", depth_of_detail="1")
			if test_details is None:
				log.error("Test '%s' not found in test case '%s'.", self.t_name, self.tc_name)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
				self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_details_not_found", 
							   entry_context=f"Critical error: Test '{self.t_name}' is defined in the test case file but not found in test plan metadata for test case '{self.tc_name}'. This indicates inconsistent test definitions, skipping to next test.", 
							   depth_of_detail="2")
				continue

			run_test_str = "! ! ! ! Running Test: %s.%s ! ! ! !" % (self.tc_name, self.t_name)
			test_func_used_str = "Script Functions Used: %s" % (test_details.get("functions_used", "ERROR: Test plan missing 'functions_used' key"))
			test_step_desc_str = "Test Steps Description: %s" % (test_details.get("description_of_steps", "ERROR: Test plan missing 'description_of_steps' key"))
			test_expected_outcome_str = "Expected Outcome: %s" % (test_details.get("expected_outcome", "ERROR: Test plan missing 'expected_outcome' key"))
			test_val_methods_str = "Validation Method(s): %s" % (test_details.get("validation_method", "ERROR: Test plan missing 'validation_method' key"))
			log.line_break(width=len(run_test_str), char="-")
			log.info(run_test_str)
			log.line_break(width=len(run_test_str), char="-")
			log.line_wrap(test_func_used_str, "info", max_width=len(run_test_str), offset_left=3)
			log.line_wrap(test_step_desc_str, "info", max_width=len(run_test_str), offset_left=3)
			log.line_wrap(test_val_methods_str, "info", max_width=len(run_test_str), offset_left=3)
			log.line_wrap(test_expected_outcome_str, "info", max_width=len(run_test_str), offset_left=3)
			log.line_break(width=len(run_test_str), char="-")
			log.info("")
			timeline_vars_dict = {"run_test_str": run_test_str, "test_func_used_str": test_func_used_str, "test_step_desc_str": test_step_desc_str, "test_expected_outcome_str": test_expected_outcome_str, "test_val_methods_str": test_val_methods_str}
			self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_metadata", 
							   entry_context=f"Displaying comprehensive test metadata including functions used, step descriptions, expected outcomes, and validation methods. This information provides complete context for understanding what the test will accomplish.", depth_of_detail="1")

			test_result_entry = self._execute_single_test_definition(test_definition)
			timeline_vars_dict = {"test_result_entry": test_result_entry}
			self._capture_timeline_event(function_name="_execute_test_case", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_result_entry", 
							   entry_context=f"Test execution completed for '{self.t_name}' with final result captured. This result contains the test status, execution details, and any validation outcomes that will be added to the overall test case results.", depth_of_detail="1")
			tc_result_dict["tests"].append(test_result_entry)
			log.info("Test %s.%s Result: %s", self.tc_name, self.t_name, test_result_entry["status"])

		return tc_result_dict
	
	def _execute_single_test_definition(self, test_def: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Executes all steps for a single test definition (e.g., one item from the "tests" list in a test case JSON).
		Args:
			test_def (Dict[str, Any]): The dictionary for a single test definition.
		Returns:
			A dictionary conforming to _T_RESULT_DICT.
		"""
		result_dict = {**_T_RESULT_DICT, "name": self.t_name}

		if not self._prepare_test_environment(test_def):
			result_dict["status"] = "NOT_RAN"
			result_dict["reason"] = "Failed to prepare test environment (load files or functions)."
			log.error("Test %s.%s marked as 'NOT_RAN' due to environment preparation failure.", self.tc_name, self.t_name)
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
			self._capture_timeline_event(function_name="_execute_single_test_definition", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_not_ran_due_to_environment_preparation_failure", 
							   entry_context=f"Test '{self.tc_name}.{self.t_name}' cannot proceed due to critical environment preparation failure. This typically means required test files couldn't be loaded or necessary functions couldn't be prepared for testing.", 
							   depth_of_detail="2")
			return result_dict
		
		timeline_vars_dict = {"test_def": test_def}
		self._capture_timeline_event(function_name="_execute_single_test_definition", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="test_def", 
							   entry_context=f"Beginning execution of test definition for '{self.t_name}' with test environment successfully prepared. The test definition contains all execution parameters, expected results, and validation criteria.", depth_of_detail="1")
		timeline_vars_dict = {"result_dict": result_dict}
		self._capture_timeline_event(function_name="_execute_single_test_definition", tag_category_list=["tc_name", "t_name"], 
							   variables_dict=timeline_vars_dict, pre_var_words="result_dict", 
							   entry_context=f"Initializing result dictionary to track test execution status, timing, and outcome details. This dictionary will be populated throughout the test execution process.", depth_of_detail="1")

		# Centralize test execution based on type, then subtype
		try:
			if self.tc_type == "unit":
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
				self._capture_timeline_event(function_name="_execute_single_test_definition", tag_category_list=["tc_name", "t_name"], 
								variables_dict=timeline_vars_dict, pre_var_words="running_unit_test_steps", 
							   entry_context=f"Executing unit test steps for '{self.t_name}' which will test individual functions in isolation. Unit tests focus on validating specific function behavior with controlled inputs.", depth_of_detail="3")
				self._run_unit_test_steps(test_def, result_dict)
			elif self.tc_type == "integration":
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
				self._capture_timeline_event(function_name="_execute_single_test_definition", tag_category_list=["tc_name", "t_name"], 
								 variables_dict=timeline_vars_dict, pre_var_words="running_integration_test_steps", 
							   entry_context=f"Executing integration test steps for '{self.t_name}' which will test interactions between multiple functions or components. Integration tests validate that components work correctly together.", depth_of_detail="3")
				self._run_integration_test_steps(test_def, result_dict)
			elif self.tc_type == "full":
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
				self._capture_timeline_event(function_name="_execute_single_test_definition", tag_category_list=["tc_name", "t_name"], 
								 variables_dict=timeline_vars_dict, pre_var_words="running_full_test_steps", 
							   entry_context=f"Running full test steps for comprehensive end-to-end validation. This combines unit, integration, and system-level testing to ensure complete functionality coverage.", depth_of_detail="3")
				self._run_full_test_steps(test_def, result_dict)
			else:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "tc_type": self.tc_type}
				self._capture_timeline_event(function_name="_execute_single_test_definition", tag_category_list=["tc_name", "t_name"], 
								 variables_dict=timeline_vars_dict, pre_var_words="unknown_test_type", 
							   entry_context=f"Error: Encountered unknown test type '{self.tc_type}' for test '{self.t_name}'. Valid test types are 'unit', 'integration', or 'full', marking test as NOT_RAN.", depth_of_detail="2")
				result_dict["status"] = "NOT_RAN"
				result_dict["reason"] = f"Unknown test case type: {self.tc_type}"
				log.error("Unknown test type '%s' for %s.%s", self.tc_type, self.tc_name, self.t_name)
		
		except Exception as e:
			log.exception("Unhandled exception during test step execution for %s.%s: %s", self.tc_name, self.t_name, e)
			result_dict["status"] = "FAIL"
			result_dict["reason"] = f"Unhandled execution error: {type(e).__name__}: {str(e)}"
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "e": e}
			self._capture_timeline_event(function_name="_execute_single_test_definition", 
								tag_category_list=["tc_name", "t_name"], 
								variables_dict=timeline_vars_dict, pre_var_words="unhandled_exception", 
								entry_context=f"Critical error: Unhandled exception occurred during test execution for '{self.tc_name}.{self.t_name}'. Exception details: {type(e).__name__}: {str(e)}, marking test as FAIL.", 
								depth_of_detail="3")

		# If status is still empty, it means steps ran but no explicit PASS/FAIL was set by subtype logic (should be handled within).
		# This can happen if validation logic is incomplete. Default to NOT_RAN if not explicitly set.
		if not result_dict["status"]:
			log.warning("Test %s.%s completed steps but status was not explicitly set. Defaulting to NOT_RAN.", self.tc_name, self.t_name)
			result_dict["status"] = "NOT_RAN"
			result_dict["reason"] = "Test steps executed but no PASS/FAIL condition was met or status not set."
			timeline_vars_dict = {}
			self._capture_timeline_event(function_name="_execute_single_test_definition", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="no_explicit_pass_fail", 
								entry_context=f"Warning: Test '{self.t_name}' completed all execution steps but no explicit PASS or FAIL status was set by the validation logic. This indicates incomplete test validation, defaulting to NOT_RAN.", 
								depth_of_detail="4")
		return result_dict

	def _prepare_test_environment(self, test_def: Dict[str, Any]) -> bool:
		"""Loads files and prepares functions needed for the test."""
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
		self._capture_timeline_event(function_name="_prepare_test_environment", 
							   tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							   pre_var_words="loading_test_files_content", 
							   entry_context=f"Setting up test environment for '{self.t_name}' by loading required test files into memory. These files contain test data, expected outputs, and configuration needed for test execution.", depth_of_detail="1")
		if not self._load_test_files_content(test_def.get("files", {})):
			timeline_vars_dict = {}
			self._capture_timeline_event(function_name="_prepare_test_environment", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="load_test_files_content_failed", 
								entry_context=f"Critical error: Failed to load required test files for test '{self.t_name}'. This means necessary test data or configuration files are missing or inaccessible, preventing test execution.", depth_of_detail="3")
			return False
		timeline_vars_dict = {}
		self._capture_timeline_event(function_name="_prepare_test_environment", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="preparing_functions_for_test", 
								entry_context=f"Preparing and importing functions required for test '{self.t_name}' execution. This includes loading function modules, setting up class instances, and making functions callable for the test.", depth_of_detail="1")
		if not self._prepare_functions_for_test(test_def.get("functions", []), test_def.get("class_instance_args", [])):
			timeline_vars_dict = {}
			self._capture_timeline_event(function_name="_prepare_test_environment", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="prepare_functions_for_test_failed", 
								entry_context=f"Critical error: Failed to prepare required functions for test '{self.t_name}'. This typically means function modules couldn't be imported or class instances couldn't be created, preventing test execution.", depth_of_detail="3")
			return False
		return True

	def _run_unit_test_steps(self, test_def: Dict[str, Any], result_dict: Dict[str, Any]):
		""" Executes steps for a unit test and updates result_dict. """
		log.info(" | Executing Unit Test Steps for %s (Subtype: %s)", self.t_name, self.tc_subtype)
		
		# Assuming unit tests usually have one primary function call defined in "test_steps_order"
		test_steps = test_def.get("test_steps_order", [])
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "test_steps": test_steps}
		self._capture_timeline_event(function_name="_run_unit_test_steps", 
							   tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							   pre_var_words="test_steps", entry_context=f"Beginning unit test execution for '{self.t_name}' with defined test steps. Unit tests validate individual functions in isolation to ensure they behave correctly with specific inputs.", depth_of_detail="1")
		if not test_steps: # Fallback if no explicit steps, try to use the first function in "functions"
			result_dict["status"] = "FAIL"
			result_dict["reason"] = "No test steps or functions defined for unit test."
			timeline_vars_dict = {}
			self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="no_test_steps_or_functions", 
								entry_context=f"Critical error: No test steps or functions are defined for unit test '{self.t_name}'. Unit tests require at least one function call to execute, marking test as FAIL.", 
								depth_of_detail="2")
			return

		# For unit tests, we usually focus on a single primary function call.
		# The template suggests "test_steps_order" even for unit, so we'll follow that.
		# This loop will typically run once for a simple unit test.
		for step_index, step in enumerate(test_steps):
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "step_index": step_index, "step": step}
			self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="step_index_and_step", 
								entry_context=f"Executing unit test step {step_index + 1} of {len(test_steps)} for test '{self.t_name}'. This step will call a specific function with predefined parameters and capture the result for validation.", depth_of_detail="0")
			log.debug(" || Executing step %s: %s", step_index + 1, step)
			func_key = step.get("function")
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "func_key": func_key}
			self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="func_key", entry_context=f"Identifying function '{func_key}' to be called in this test step. This function should have been prepared during the test environment setup phase.", depth_of_detail="0")
			if not func_key or func_key not in self.prepared_functions:
				result_dict["status"] = "FAIL"
				result_dict["reason"] = f"Function '{func_key}' in step {step_index} not prepared or found."
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "func_key": func_key, "step_index": step_index}
				self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="function_not_prepared_or_found", 
								entry_context=f"Critical error: Function '{func_key}' required for step {step_index + 1} was not prepared during environment setup or doesn't exist. This indicates a test configuration issue, marking test as FAIL.", 
								depth_of_detail="2")
				return

			callable_func_info = self.prepared_functions[func_key]
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "callable_func_info": callable_func_info}
			self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="callable_func_info", entry_context=f"Retrieved callable function information for '{func_key}' including the actual function reference and metadata. This information was prepared during the test environment setup phase.", depth_of_detail="0")
			log.debug("Callable func info: %s", callable_func_info)
			actual_callable = callable_func_info["callable_func"]
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "actual_callable": actual_callable}
			self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="actual_callable", entry_context=f"Extracted the actual callable function object that will be invoked for this test step. This is the prepared function ready to be called with test parameters.", depth_of_detail="0")
			params_config = step.get("params", {})
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "params_config": params_config}
			self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="params_config", entry_context=f"Processing parameter configuration that defines the input values for the function call. These parameters may include literal values, file references, or return value pointers from previous steps.", depth_of_detail="0")
			expected_exception_name = test_def.get("expected_exception", "")
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name}
			self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="expected_exception_name", entry_context=f"Checking if this test expects a specific exception to be thrown by the function under test. If an exception name is specified, the test will validate that the correct exception type is raised.", depth_of_detail="0")
			log.debug("Params config: %s", params_config)
			try: # Parameters need to be resolved before we pass them into the function we are testing.
				resolved_params = self._resolve_parameters(params_config)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "resolved_params": resolved_params}
				self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="resolved_params", entry_context=f"Successfully resolved all parameters from configuration including literal values, file references, and return value pointers. These resolved parameters are now ready to be passed to the target function.", depth_of_detail="0")
				try: # We need to catch exceptions from the function we are testing in case we expect them.
					log.info(" = = = EXECUTING TEST FUNCTION: %s", func_key)
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "func_key": func_key}
					self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="func_key_resolved", entry_context=f"Now executing the target test function '{func_key}' with resolved parameters. This is the core of the unit test where the actual function under test is called and its behavior is evaluated.", depth_of_detail="2")
					return_values = actual_callable(**resolved_params)
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "return_values": return_values}
					self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="return_values", entry_context=f"Function execution completed successfully and returned values. These return values will be used for validation against expected results and may be stored for use in subsequent test steps.", depth_of_detail="0")
					log.info(" = = = RETURN VALUES OF RAN FUNCTION: %s", return_values)

					# Store return values if pointers are defined
					return_pointers = step.get("return_pointers", [])
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "return_pointers": return_pointers}
					self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="return_pointers", entry_context=f"Processing return pointers to store specific return values for later use in the test. Return pointers allow subsequent test steps to reference outputs from this function call.", depth_of_detail="0")
					if not isinstance(return_values, tuple): # Ensure return_values is a tuple for consistent indexing
						return_values = (return_values,)
					for i, ptr_name in enumerate(return_pointers):
						if i < len(return_values):
							self.return_value_store[ptr_name] = return_values[i]
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ptr_name": ptr_name, "return_values": return_values}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="return_pointer_stored", 
								entry_context=f"Successfully stored return value at index {i} in pointer '{ptr_name}' for later reference. This value can now be used as a parameter in subsequent test steps.", 
								depth_of_detail="0")
						else: # Not enough return values for all pointers
							self.return_value_store[ptr_name] = None 
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ptr_name": ptr_name}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="return_pointer_none", 
								entry_context=f"Warning: Return pointer '{ptr_name}' is defined but the function returned fewer values than expected. Setting pointer to None which may cause issues in subsequent test steps.", 
								depth_of_detail="2")
							log.warning("Return pointer '%s' defined but function returned too few values.", ptr_name)
					
					if step_index < len(test_steps) - 1: # Don't perform validation if it's not the last step
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="not_last_step", 
							entry_context=f"This is not the final test step ({step_index + 1} of {len(test_steps)}), so skipping validation for now. Validation will occur after the last step completes.", 
							depth_of_detail="2")
						continue

					# Perform validations
					validation_passed = True
					validation_reasons = []

					# 1. Validate return values
					expected_returns = test_def.get("expected_return_value_and_order", {})
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_returns": expected_returns}
					self._capture_timeline_event(function_name="_run_unit_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="expected_returns", 
						entry_context=f"Beginning validation phase by checking expected return values against actual function outputs. This validation determines if the unit test passes or fails.", depth_of_detail="0")
					if expected_returns:
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="expected_returns_loop", 
							entry_context=f"Iterating through each expected return value specification to validate against actual function outputs. Each return value will be checked against its expected criteria.", depth_of_detail="0")
						for ret_var_name, spec in expected_returns.items():
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "spec": spec}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="ret_var_name_and_spec", 
								entry_context=f"Validating return variable '{ret_var_name}' against its specification. This involves comparing the actual return value with the expected value defined in the test configuration.", depth_of_detail="0")
							if ret_var_name not in self.return_value_store:
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="ret_var_name_not_in_return_value_store", 
									entry_context=f"Validation error: Expected return variable '{ret_var_name}' was not found in the return value store. This indicates the variable was not properly captured by return pointers during function execution.", 
									depth_of_detail="2")
								validation_passed = False
								reason = f"Expected return variable '{ret_var_name}' not found in return pointers."
								validation_reasons.append(reason)
								log.warning(reason)
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "reason": reason}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="validation_reason", 
									entry_context=f"Recording validation failure reason for return variable '{ret_var_name}'. This reason will be included in the final test result to help with debugging and analysis.", depth_of_detail="0")
								continue

							actual_val = self.return_value_store[ret_var_name]
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "actual_val": actual_val}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="actual_val", entry_context=f"Retrieved actual return value '{actual_val}' from return value store for comparison. This is the value that was captured when the function executed.", depth_of_detail="0")
							expected_val_source = list(spec.values())[0] # e.g., "hardcoded_var_value" or "json_1.key.path"
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_val_source": expected_val_source}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="expected_val_source", entry_context=f"Extracting expected value source configuration '{expected_val_source}' for validation comparison. This source will be resolved to get the actual expected value for comparison with function output.", depth_of_detail="0")
							log.debug("expected_val_source before being resolved: %s", expected_val_source)
							log.debug("actual_val: %s", actual_val)
							resolved_expected_val, error = self._resolve_single_param_value(expected_val_source)
							if error:
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "error": error}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="error", entry_context=f"Error occurred while resolving expected value for '{ret_var_name}' validation. This prevents proper comparison with the actual return value, causing validation failure.", depth_of_detail="3")
								validation_passed = False
								reason = f"Could not resolve expected value for '{ret_var_name}': {error}"
								validation_reasons.append(reason)
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "reason": reason}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="validation_reason", entry_context=f"Recording validation failure due to expected value resolution error. This issue prevents proper validation comparison and indicates a test configuration problem.", depth_of_detail="2")
								log.warning(reason)
								continue

							if actual_val != resolved_expected_val:
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="actual_val_not_equal_to_resolved_expected_val", 
									entry_context=f"Validation failure detected - actual return value '{actual_val}' does not match expected value '{resolved_expected_val}'. This indicates the function did not behave as expected for the given input.", 
									depth_of_detail="2")
								validation_passed = False
								reason = f"Return value mismatch for '{ret_var_name}': Expected '{resolved_expected_val}' (type {type(resolved_expected_val)}), Got '{actual_val}' (type {type(actual_val)})"
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "reason": reason}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="validation_reason", 
									entry_context=f"Recording detailed validation failure reason including expected vs actual values and their types. This information helps with debugging and understanding why the test failed.", depth_of_detail="2")
								validation_reasons.append(reason)
							
							if validation_passed:
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="validation_passed", 
									entry_context=f"Validation successful for return variable '{ret_var_name}' - actual value matches expected result perfectly. This portion of the test is functioning correctly.", depth_of_detail="2")
								log.info(f"Return value for '{ret_var_name}' matched: '{actual_val}'")
							else:
								timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
								self._capture_timeline_event(function_name="_run_unit_test_steps", 
									tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
									pre_var_words="validation_failed", 
									entry_context=f"Validation has failed for one or more return values. The collected validation reasons will be used to determine the final test result and provide debugging information.", depth_of_detail="2")
								log.warning(validation_reasons)
					
					# 2. Validate file content
					expected_file_content_checks = test_def.get("expected_file_content", [])
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_file_content_checks": expected_file_content_checks}
					self._capture_timeline_event(function_name="_run_unit_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="expected_file_content_checks", 
						entry_context=f"Processing expected file content validation checks to verify that function execution created, modified, or deleted files as expected. This validates side effects of the function call.", depth_of_detail="0")
					if expected_file_content_checks:
						file_content_ok, file_reasons = self._validate_file_contents(expected_file_content_checks)
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "file_content_ok": file_content_ok}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="file_content_ok", 
							entry_context=f"File content validation completed with result: {file_content_ok}. This indicates whether all expected file changes occurred correctly as a result of the function execution.", 
							depth_of_detail="0")
						if not file_content_ok:
							validation_passed = False
							validation_reasons.extend(file_reasons)
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "file_content_ok": file_content_ok}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="file_content_ok_false", 
								entry_context=f"File content validation failed - expected file changes did not occur correctly. This indicates the function did not produce the expected side effects on the file system.", 
								depth_of_detail="2")
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "file_reasons": file_reasons}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="file_reasons", 
								entry_context=f"Recording specific file validation failure reasons that detail which expected file changes were not met. These reasons help diagnose file system side effect issues.", depth_of_detail="2")
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="validation_failed", 
								entry_context=f"Overall validation marked as failed due to file content validation failure. File system side effects did not match expectations, contributing to test failure.", depth_of_detail="2")

					if validation_passed:
						result_dict["status"] = "PASS"
					else:
						result_dict["status"] = "FAIL"
						result_dict["reason"] = "; ".join(validation_reasons) if validation_reasons else "Functional validation failed."
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="result_status", 
							entry_context=f"Setting final test result status to FAIL based on validation failures. The test did not meet all expected criteria for return values or file system side effects.", depth_of_detail="0")
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="result_reason", 
							entry_context=f"Recording detailed failure reason that combines all validation failure messages. This provides comprehensive information about why the test failed for debugging purposes.", depth_of_detail="0")

				except Exception as e:
					if e.__class__.__name__ == expected_exception_name:
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="expected_exception_caught", 
							entry_context=f"Successfully caught expected exception '{expected_exception_name}' during function execution. This confirms the function correctly raises the expected error condition when given invalid input.", depth_of_detail="0")
						result_dict["status"] = "PASS"
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="result_dict_status", 
							entry_context=f"Setting test result status to PASS because the expected exception was correctly caught. The function behaved exactly as specified for invalid input conditions.", depth_of_detail="0")
						log.info("Correctly caught expected exception: %s", expected_exception_name)
					else:
						result_dict["status"] = "FAIL"
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="result_dict_status", 
							entry_context=f"Setting test result status to FAIL due to exception mismatch. An exception was thrown, but it was not the expected type or no exception was expected.", depth_of_detail="0")
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "e": e}
						self._capture_timeline_event(function_name="_run_unit_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="exception_was_hit_but_not_expected", 
							entry_context=f"An exception occurred during function execution but it does not match expectations. This indicates either unexpected behavior or incorrect test configuration.", depth_of_detail="0")
						if expected_exception_name:
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="expected_exception_name_is_set", 
								entry_context=f"Test was configured to expect exception '{expected_exception_name}' but received different exception '{e.__class__.__name__}'. This indicates a mismatch between expected and actual error behavior.", depth_of_detail="0")
							result_dict["reason"] = f"Expected exception '{expected_exception_name}', but got '{e.__class__.__name__}': {e}"
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name, "e": e}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="expected_exception_but_got_exception", 
								entry_context=f"Recording detailed exception mismatch: expected '{expected_exception_name}' but got '{e.__class__.__name__}: {e}'. This information helps diagnose why the function's error behavior differs from expectations.", 
								depth_of_detail="0")
						else:
							result_dict["reason"] = f"Unexpected exception '{e.__class__.__name__}': {e}"
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
							self._capture_timeline_event(function_name="_run_unit_test_steps", 
								tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
								pre_var_words="result_dict_reason", 
								entry_context=f"Recording unexpected exception as the failure reason. No exception was expected but one occurred, indicating the function has error conditions that were not anticipated in the test design.", depth_of_detail="0")
						log.error(result_dict["reason"])

			except Exception as e:
				log.exception("Exception during unit test step for %s.%s, function %s: %s", self.tc_name, self.t_name, func_key, e)
				result_dict["status"] = "FAIL"
				result_dict["reason"] = f"Execution error in function {func_key}: {type(e).__name__}: {str(e)}"
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
				self._capture_timeline_event(function_name="_run_unit_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="result_dict_status_exception", 
					entry_context=f"Critical execution error occurred in unit test step processing loop, causing test failure. Final status: {result_dict['status']}, reason: {result_dict['reason']}", 
					depth_of_detail="0")
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "e": e}
				self._capture_timeline_event(function_name="_run_unit_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="execution_error_in_large_loop", 
					entry_context=f"Unhandled exception in unit test step processing: {type(e).__name__}: {e}. This indicates a serious issue with test execution that prevented completion.", 
					depth_of_detail="3")
				return # Stop on first error in a step

	def _run_integration_test_steps(self, test_def: Dict[str, Any], result_dict: Dict[str, Any]):
		""" Executes steps for an integration test and updates result_dict. """
		log.info("Executing Integration Test Steps for %s", self.t_name)
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "test_def": test_def}
		self._capture_timeline_event(function_name="_run_integration_test_steps", 
			tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
			pre_var_words="test_def", entry_context=f"Beginning integration test execution for '{self.t_name}' with test definition containing step sequences. Integration tests validate that multiple functions or components work correctly together.", depth_of_detail="0")
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
		self._capture_timeline_event(function_name="_run_integration_test_steps", 
			tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
			pre_var_words="result_dict", entry_context=f"Initializing result dictionary to track integration test progress and outcomes. This will capture the cumulative results of all integration test steps.", depth_of_detail="0")
		test_steps = test_def.get("test_steps_order", [])
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "test_steps": test_steps}
		self._capture_timeline_event(function_name="_run_integration_test_steps", 
			tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
			pre_var_words="test_steps", entry_context=f"Processing ordered sequence of {len(test_steps)} integration test steps. Each step will be executed in sequence, with later steps potentially using outputs from earlier steps.", depth_of_detail="0")

		if not test_steps:
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="no_test_steps_order", 
				entry_context=f"Critical error: No test_steps_order defined for integration test '{self.t_name}'. Integration tests require a sequence of steps to execute, marking test as FAIL.", 
				depth_of_detail="2")
			result_dict["status"] = "FAIL"
			result_dict["reason"] = "No test_steps_order defined for integration test."
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="result_dict_status", 
				entry_context=f"Set integration test result status to FAIL due to missing test_steps_order configuration. This critical configuration error prevents test execution.", depth_of_detail="0")
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "result_dict": result_dict}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="result_dict_reason", 
				entry_context=f"Set failure reason explaining missing test_steps_order configuration. This helps identify the root cause of the integration test failure.", depth_of_detail="0")
			return

		all_steps_passed = True
		step_failure_reason = ""

		for step_index, step in enumerate(test_steps):
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "step_index": step_index, "step": step}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="step_index", entry_context=f"Executing integration test step {step_index + 1} of {len(test_steps)} for test '{self.t_name}'. Each step builds upon previous steps to validate component interactions.", depth_of_detail="0")
			func_key = step.get("function")
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "func_key": func_key}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="func_key", entry_context=f"Identifying function '{func_key}' for integration test step {step_index + 1}. This function should be prepared and available for execution as part of the integration workflow.", depth_of_detail="0")
			if not func_key or func_key not in self.prepared_functions:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "func_key": func_key, "step_index": step_index}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="func_key_not_prepared_or_found", 
					entry_context=f"Critical error: Function '{func_key}' required for integration step {step_index + 1} was not prepared during environment setup. This breaks the integration test workflow and causes failure.", 
					depth_of_detail="2")
				all_steps_passed = False
				step_failure_reason = f"Function '{func_key}' in step {step_index} not prepared or found."
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "step_failure_reason": step_failure_reason}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="step_failure_reason", 
					entry_context=f"Recording integration test failure reason for step {step_index + 1}. This failure will cause the entire integration test to fail since steps depend on each other.", depth_of_detail="0")
				break 

			callable_func_info = self.prepared_functions[func_key]
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "callable_func_info": callable_func_info}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="callable_func_info", 
				entry_context=f"Retrieved callable function information for '{func_key}' from prepared functions. This function was successfully prepared during environment setup and is ready for execution.", depth_of_detail="0")
			actual_callable = callable_func_info["callable_func"]
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "actual_callable": actual_callable}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="actual_callable", 
				entry_context=f"Extracted the actual callable function object that will be invoked for integration step {step_index + 1}. This function will be called with resolved parameters.", depth_of_detail="0")
			params_config = step.get("params", {})
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "params_config": params_config}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="params_config", 
				entry_context=f"Processing parameter configuration for integration step {step_index + 1}. Parameters may include outputs from previous steps, enabling step-to-step data flow.", depth_of_detail="0")
			
			try:
				resolved_params = self._resolve_parameters(params_config)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "step_index": step_index, "func_key": func_key, "resolved_params": resolved_params}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="calling_step", 
					entry_context=f"Executing integration step {step_index + 1}: calling function '{func_key}' with resolved parameters. This step builds upon previous integration test steps.", depth_of_detail="0")
				log.info("Calling step %s: %s with params %s", step_index, func_key, resolved_params)
				return_values = actual_callable(**resolved_params)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "step_index": step_index, "func_key": func_key, "return_values": return_values}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="return_values", 
					entry_context=f"Function execution completed for integration step {step_index + 1} and returned values. These values may be used by subsequent integration test steps.", depth_of_detail="0")

				# Store return values if pointers are defined
				return_pointers = step.get("return_pointers", [])
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "return_pointers": return_pointers}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="return_pointers", 
					entry_context=f"Processing return pointers for integration step {step_index + 1} to store outputs for later steps. These pointers enable data flow between integration test steps.", depth_of_detail="0")
				if not isinstance(return_values, tuple):
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "return_values": return_values}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="return_values_not_tuple", 
						entry_context=f"Function returned single value instead of tuple. Converting to tuple format to ensure consistent return value indexing for pointer storage.", depth_of_detail="0")
					return_values = (return_values,) # Ensure tuple for consistent indexing
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "return_values": return_values}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="return_values_converted_to_tuple", 
						entry_context=f"Successfully converted return values to tuple format for consistent processing. Return pointers can now be processed using standard indexing.", depth_of_detail="0")
				for i, ptr_name in enumerate(return_pointers):
					if i < len(return_values):
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ptr_name": ptr_name, "return_values": return_values, "i": i}
						self._capture_timeline_event(function_name="_run_integration_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="storing_return_pointer", 
							entry_context=f"Storing return value at index {i} in pointer '{ptr_name}' for use in subsequent integration test steps. This enables data flow between integration steps.", depth_of_detail="0")
						self.return_value_store[ptr_name] = return_values[i]
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ptr_name": ptr_name, "return_values": return_values, "i": i}
						self._capture_timeline_event(function_name="_run_integration_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="stored_return_pointer", 
							entry_context=f"Successfully stored return pointer '{ptr_name}' with value {return_values[i]}. This value is now available for subsequent integration test steps.", depth_of_detail="0")
						log.info("Stored return pointer '%s' = %s", ptr_name, return_values[i])
					else:
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ptr_name": ptr_name, "step_index": step_index}
						self._capture_timeline_event(function_name="_run_integration_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="return_pointer_defined_but_function_returned_too_few_values", 
							entry_context=f"Warning: Return pointer '{ptr_name}' is defined for step {step_index + 1} but function returned fewer values than expected. This may cause issues in subsequent integration steps.", 
							depth_of_detail="2")
						self.return_value_store[ptr_name] = None
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ptr_name": ptr_name, "step_index": step_index}
						self._capture_timeline_event(function_name="_run_integration_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="return_pointer_set_to_none", 
							entry_context=f"Setting return pointer '{ptr_name}' to None due to insufficient return values. This may cause subsequent integration steps to fail if they depend on this value.", 
							depth_of_detail="2")
						log.warning("Return pointer '%s' defined for step %s but function returned too few values.", ptr_name, step_index)

			except Exception as e:
				log.exception("Exception during integration test step %s for %s.%s, function %s: %s", step_index, self.tc_name, self.t_name, func_key, e)
				all_steps_passed = False
				step_failure_reason = f"Execution error in step {step_index} (function {func_key}): {type(e).__name__}: {str(e)}"
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "step_failure_reason": step_failure_reason}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="step_failure_reason", 
					entry_context=f"Critical error in integration step {step_index + 1}: {step_failure_reason}. This breaks the integration test workflow and causes the entire test to fail.", depth_of_detail="0")
				break # Stop integration test on first error

		if all_steps_passed:
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "all_steps_passed": all_steps_passed}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="all_steps_passed", 
				entry_context=f"All integration test steps completed successfully without errors. Proceeding to final validation phase to check expected return values and file content changes.", depth_of_detail="4")
			# Final validation for integration tests (after all steps)
			validation_passed = True
			validation_reasons = []
			# 1. Validate return values based on "expected_return_value_and_order"
			expected_returns = test_def.get("expected_return_value_and_order", {})
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_returns": expected_returns}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="expected_returns", 
				entry_context=f"Beginning final validation phase by checking expected return values from integration test steps. This validates that the combined workflow produced the correct end results.", depth_of_detail="0")
			if expected_returns:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_returns": expected_returns}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="expected_returns_defined", 
					entry_context=f"Expected return values are defined for integration test final validation. Each return variable will be checked against its expected criteria to determine overall test success.", depth_of_detail="1")
				for ret_var_name, spec in expected_returns.items():
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "spec": spec}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="ret_var_name", 
						entry_context=f"Validating expected return variable '{ret_var_name}' from integration test final results. This checks if the workflow produced the required output values.", depth_of_detail="0")
					if ret_var_name not in self.return_value_store:
						validation_passed = False
						reason = f"Expected final return variable '{ret_var_name}' not found in store."
						validation_reasons.append(reason); log.warning(reason)
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "spec": spec}
						self._capture_timeline_event(function_name="_run_integration_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="return_variable_not_found_in_store", 
							entry_context=f"Return variable not found in store.", depth_of_detail="2_more_detail")
						continue
					actual_val = self.return_value_store[ret_var_name]
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "actual_val": actual_val}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="actual_val", 
						entry_context=f"Retrieved actual value '{actual_val}' for return variable '{ret_var_name}' from the return value store. This will be compared against expected criteria.", depth_of_detail="0")
					expected_val_source = list(spec.values())[0]
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "expected_val_source": expected_val_source}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="expected_val_source", 
						entry_context=f"Processing expected value source '{expected_val_source}' for return variable '{ret_var_name}'. This defines what the actual value should be compared against.", depth_of_detail="0")
					log.debug("expected_val_source: %s", expected_val_source)
					resolved_expected_val, error = self._resolve_single_param_value(expected_val_source)
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "expected_val_source": expected_val_source, "resolved_expected_val": resolved_expected_val, "error": error}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="resolved_expected_val", 
						entry_context=f"Resolved expected value to '{resolved_expected_val}' for comparison with actual value '{actual_val}'. This enables final validation of integration test results.", depth_of_detail="0")
					if error:
						validation_passed = False
						reason = f"Could not resolve expected value for '{ret_var_name}': {error}"
						validation_reasons.append(reason)
						log.warning(reason)
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "expected_val_source": expected_val_source, "resolved_expected_val": resolved_expected_val, "error": error}
						self._capture_timeline_event(function_name="_run_integration_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="could_not_resolve_expected_val", 
							entry_context=f"Could not resolve expected value.", depth_of_detail="2_more_detail")
						continue
					if actual_val != resolved_expected_val:
						validation_passed = False
						reason = f"Final return value mismatch for '{ret_var_name}': Expected '{resolved_expected_val}', Got '{actual_val}'"
						validation_reasons.append(reason)
						log.warning(reason)
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "ret_var_name": ret_var_name, "expected_val_source": expected_val_source, "resolved_expected_val": resolved_expected_val, "error": error}
						self._capture_timeline_event(function_name="_run_integration_test_steps", 
							tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
							pre_var_words="final_return_value_mismatch", 
							entry_context=f"Final return value mismatch.", depth_of_detail="2_more_detail")
			
			# 2. Validate file content based on "expected_file_content"
			expected_file_content_checks = test_def.get("expected_file_content", [])
			if expected_file_content_checks:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_file_content_checks": expected_file_content_checks}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="expected_file_content_checks", 
					entry_context=f"Processing {len(expected_file_content_checks)} expected file content checks for integration test final validation. These verify that file modifications occurred correctly.", depth_of_detail="1")
				file_content_ok, file_reasons = self._validate_file_contents(expected_file_content_checks)
				if not file_content_ok:
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_file_content_checks": expected_file_content_checks, "file_content_ok": file_content_ok, "file_reasons": file_reasons}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="file_content_not_ok", 
						entry_context=f"File content not ok.", depth_of_detail="2_more_detail")
					validation_passed = False
					validation_reasons.extend(file_reasons)
			
			# 3. Check for expected exception IF defined at the top level for the whole integration test
			expected_exception_name = test_def.get("expected_exception")
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="expected_exception_name", 
				entry_context=f"Checking for expected exception configuration in integration test. Exception expectations validate that functions properly handle error conditions.", depth_of_detail="1")
			if expected_exception_name: # This means no exception should have occurred during steps if we reach here
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="expected_exception_name_defined", 
					entry_context=f"Expected exception '{expected_exception_name}' is defined for integration test validation. Will check if this exception was properly raised during execution.", depth_of_detail="1")
				result_dict["status"] = "FAIL"
				result_dict["reason"] = f"Expected exception '{expected_exception_name}' for the integration flow was not raised."
				return

			if validation_passed:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "validation_passed": validation_passed}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="validation_passed", 
					entry_context=f"Integration test validation PASSED for all criteria. All expected outcomes including return values, file changes, and exceptions occurred correctly.", depth_of_detail="2")
				result_dict["status"] = "PASS"
			else:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "validation_passed": validation_passed}
				self._capture_timeline_event(function_name="_run_integration_test_steps", 
					tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
					pre_var_words="validation_not_passed", 
					entry_context=f"Validation not passed:", depth_of_detail="2_more_detail")
				result_dict["status"] = "FAIL"
				result_dict["reason"] = "; ".join(validation_reasons) if validation_reasons else "Integration test final validation failed."
		else: # A step failed
			# If an exception was expected for the whole flow, and it occurred mid-step matching the type:
			expected_exception_name = test_def.get("expected_exception")
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="expected_exception_name", 
				entry_context=f"Checking for expected exception configuration in integration test failure. Will validate if the integration workflow properly raised the expected error condition.", depth_of_detail="1")
			if expected_exception_name and "Execution error" in step_failure_reason:
				# Basic check if the type name is in the failure reason (could be more precise)
				if expected_exception_name in step_failure_reason:
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "expected_exception_name": expected_exception_name}
					self._capture_timeline_event(function_name="_run_integration_test_steps", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
						pre_var_words="expected_exception_name_in_step_failure_reason", 
						entry_context=f"Expected exception '{expected_exception_name}' found in integration test failure reason. Exception validation PASSED - workflow correctly raised the expected error.", depth_of_detail="2")
					result_dict["status"] = "PASS"
					result_dict["reason"] = f"Correctly caught expected exception '{expected_exception_name}' during integration flow."
					log.info(result_dict["reason"])
					return 
			
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "step_failure_reason": step_failure_reason}
			self._capture_timeline_event(function_name="_run_integration_test_steps", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
				pre_var_words="step_failure_reason", 
				entry_context=f"Integration test step failure details: {step_failure_reason}. This provides context about what went wrong during the multi-step workflow execution.", depth_of_detail="2")
			result_dict["status"] = "FAIL"
			result_dict["reason"] = step_failure_reason
	
	def _run_full_test_steps(self, test_def: Dict[str, Any], result_dict: Dict[str, Any]):
		""" Executes steps for a full test. Similar to integration but may have more complex validation. """
		log.info("Executing Full Test Steps for %s (currently same logic as integration)", self.t_name)
		# For now, full tests will follow the same logic as integration tests.
		# This can be expanded later if "full" tests have unique requirements.
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "test_def": test_def, "result_dict": result_dict}
		self._capture_timeline_event(function_name="_run_full_test_steps", 
			tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
			pre_var_words="running_full_test_steps", 
			entry_context=f"Executing full test steps for comprehensive end-to-end validation. This combines unit, integration, and system-level testing for complete functionality coverage.", depth_of_detail="3")
		self._run_integration_test_steps(test_def, result_dict)

	def _resolve_parameters(self, params_config: Dict[str, str]) -> Dict[str, Any]:
		"""
		Resolves parameter values based on their definitions (hardcoded, from return_store, or from loaded files).
		Args:
			params_config (Dict[str, str]): The "params" dictionary from a test step.
		Returns:
			Dict[str, Any]: A dictionary of resolved parameter names and their actual values.
		"""
		resolved_params = {}
		log.debug("Resolving params config: %s", params_config)
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "params_config": params_config}
		self._capture_timeline_event(function_name="_resolve_parameters", 
			tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, 
			pre_var_words="params_config", 
			entry_context=f"Beginning parameter resolution process for function call. Converting parameter source configurations into actual values including literals, file references, and return value pointers.", depth_of_detail="0")
		for param_name, param_value_source in params_config.items():
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_name": param_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_parameters", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="param_value_source", 
				entry_context=f"Resolving parameter '{param_name}' with source '{param_value_source}'. Source will be interpreted as literal value, file reference, or return value pointer.", depth_of_detail="0")
			log.debug("Resolving param value source: %s", param_value_source)
			val, error_msg = self._resolve_single_param_value(param_value_source)
			if error_msg:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_name": param_name, "param_value_source": param_value_source, "val": val, "error_msg": error_msg}
				self._capture_timeline_event(function_name="_resolve_parameters", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="error_msg", 
					entry_context=f"Error occurred resolving parameter '{param_name}': {error_msg}. Falling back to using the source string as a literal value instead of resolved value.", depth_of_detail="0")
				log.warning("Error resolving param '%s': %s. Using string value '%s'.", param_name, error_msg, param_value_source)
				resolved_params[param_name] = param_value_source
			else:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_name": param_name, "val": val}
				self._capture_timeline_event(function_name="_resolve_parameters", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="got_val", 
					entry_context=f"Successfully resolved parameter '{param_name}' to value: {val}. This resolved value will be passed to the function call.", depth_of_detail="0")
				resolved_params[param_name] = val
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "resolved_params": resolved_params}
		self._capture_timeline_event(function_name="_resolve_parameters", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="successfully_resolved_params", 
			entry_context=f"Parameter resolution completed successfully. All parameters have been converted from their source configurations to actual values ready for function execution.", depth_of_detail="0")
		return resolved_params

	def _resolve_single_param_value(self, param_value_source: Any) -> Tuple[Any, str | None]:
		"""
		Resolves a single parameter's value.
		Sources can be:
		- "hardcoded_value" (literal string, taken as is unless it's a special type)
		- Special hardcoded: "true", "false", "null"/"none", integers, floats
		- "return_X" (from self.return_value_store)
		- "file_key.path.to.value" (from self.loaded_test_files, e.g., "json_0.some_dict.value")
		- "path/to/some_file_listed_in_files_key" (resolves to the absolute path of the file)
		Args:
			param_value_source (str): The string defining how to get the parameter's value.
		Returns:
			Tuple[Any, str | None]: The resolved value and an error message if resolution failed, else None.
		"""
		# 0. Check if the param has nested values. Recursively call this function to resolve each one.
		log.debug("Resolving param_value_source: %s (type: %s)", param_value_source, type(param_value_source))
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
		self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="param_value_source", 
			entry_context=f"Analyzing parameter value source type {type(param_value_source)} to determine appropriate resolution method. Will handle dictionaries, lists, and primitive types differently.", depth_of_detail="0")
		if isinstance(param_value_source, dict):
			log.debug("Found dictionary param_value_source with keys: %s", list(param_value_source.keys()))
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_dict_param_value_source", 
				entry_context=f"Found dictionary parameter value source with {len(param_value_source)} keys. Will recursively resolve each dictionary value to handle nested parameter structures.", depth_of_detail="0")
			for key, value in param_value_source.items():
				log.debug("Resolving dictionary value for key '%s': %s", key, value)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "key": key, "value": value}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="value", 
					entry_context=f"Recursively resolving dictionary value for key '{key}': {value}. This handles nested parameter structures within dictionary configurations.", depth_of_detail="0")
				resolved_value, error = self._resolve_single_param_value(value)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "key": key, "value": value, "resolved_value": resolved_value, "error": error}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolved_value", 
					entry_context=f"Recursive resolution completed for dictionary key '{key}' with result: {resolved_value}. Value will be stored back in the dictionary structure.", depth_of_detail="0")
				if error:
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "key": key, "value": value, "error": error}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="error", 
						entry_context=f"Error occurred during recursive resolution of dictionary value for key '{key}': {error}. This prevents successful parameter resolution.", depth_of_detail="0")
					log.debug("Error resolving dictionary value for key '%s': %s", key, error)
					return None, error
				log.debug("Successfully resolved dictionary value for key '%s' to: %s", key, resolved_value)
				param_value_source[key] = resolved_value
			log.debug("Completed resolving dictionary param_value_source. Final result: %s", param_value_source)
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="completed_resolving_dict_param_value_source", 
				entry_context=f"Successfully completed resolution of dictionary parameter value source. All nested values have been resolved and the dictionary is ready for function use.", depth_of_detail="0")
			return param_value_source, None
		elif isinstance(param_value_source, list):
			log.debug("Found list param_value_source with %d items", len(param_value_source))
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_list_param_value_source", 
				entry_context=f"Found list parameter value source with {len(param_value_source)} items. Will recursively resolve each list element to handle nested parameter structures.", depth_of_detail="0")
			for i, value in enumerate(param_value_source):
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "i": i, "value": value}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="value", 
					entry_context=f"Recursively resolving list value at index {i}: {value}. This handles nested parameter structures within list configurations.", depth_of_detail="0")
				log.debug("Resolving list value at index %d: %s", i, value)
				resolved_value, error = self._resolve_single_param_value(value)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "i": i, "value": value, "resolved_value": resolved_value, "error": error}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolved_value", 
					entry_context=f"Recursive resolution completed for list index {i} with result: {resolved_value}. Value will be stored back in the list structure.", depth_of_detail="0")
				if error:
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "i": i, "value": value, "error": error}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="error", 
						entry_context=f"Error occurred during recursive resolution of list value at index {i}: {error}. This prevents successful parameter resolution.", depth_of_detail="0")
					log.error("Error resolving list value at index %d: %s", i, error)
					return None, error
				log.debug("Successfully resolved list value at index %d to: %s", i, resolved_value)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "i": i, "value": value, "resolved_value": resolved_value}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="storing_resolved_value", 
					entry_context=f"Storing resolved value {resolved_value} back at list index {i}. This maintains the list structure while updating values with their resolved equivalents.", depth_of_detail="0")
				param_value_source[i] = resolved_value
			log.debug("Completed resolving list param_value_source. Final result: %s", param_value_source)
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="completed_resolving_list_param_value_source", 
				entry_context=f"Successfully completed resolution of list parameter value source. All nested values have been resolved and the list is ready for function use.", depth_of_detail="0")
			return param_value_source, None
		
		# 1. Check special hardcoded values
		if isinstance(param_value_source, str): # Ensure it's a string before lowercasing etc.
			log.debug("Processing string param_value_source: %s", param_value_source)
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="processing_string_param_value_source", 
				entry_context=f"Processing string parameter value source '{param_value_source}' to check for special type conversions. Will attempt to convert to boolean, None, integer, or float if recognized patterns are found.", depth_of_detail="0")
			val_lower = param_value_source.lower()
			if val_lower == "true": 
				log.debug("Resolved 'true' to boolean True")
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "val_lower": val_lower}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolved_true", 
					entry_context=f"Recognized string 'true' and converted to boolean True value. This allows boolean parameters to be specified as strings in test configurations.", depth_of_detail="0")
				return True, None
			if val_lower == "false": 
				log.debug("Resolved 'false' to boolean False")
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "val_lower": val_lower}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolved_false", 
					entry_context=f"Recognized string 'false' and converted to boolean False value. This allows boolean parameters to be specified as strings in test configurations.", depth_of_detail="0")
				return False, None
			if val_lower == "null" or val_lower == "none": 
				log.debug("Resolved 'null'/'none' to None")
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "val_lower": val_lower}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolved_null", 
					entry_context=f"Recognized string '{param_value_source}' and converted to None value. This allows null parameters to be specified as strings in test configurations.", depth_of_detail="0")
				return None, None
			try: # Integer?
				result = int(param_value_source)
				log.debug("Resolved string '%s' to integer: %d", param_value_source, result)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "val_lower": val_lower, "result": result}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolved_integer", 
					entry_context=f"Successfully converted string '{param_value_source}' to integer {result}. This enables integer parameters to be specified as strings in test configurations.", depth_of_detail="0")
				return result, None
			except ValueError:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "val_lower": val_lower}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="not_an_integer", 
					entry_context=f"String '{param_value_source}' is not a valid integer format. Continuing to check other possible data type conversions.", depth_of_detail="0")
				log.debug("String '%s' is not an integer", param_value_source)
				pass # Not an int
			try: # Float?
				result = float(param_value_source)
				log.debug("Resolved string '%s' to float: %f", param_value_source, result)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "val_lower": val_lower, "result": result}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolved_float", 
					entry_context=f"Successfully converted string '{param_value_source}' to float {result}. This enables decimal parameters to be specified as strings in test configurations.", depth_of_detail="0")
				return result, None
			except ValueError:
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "val_lower": val_lower}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="not_a_float", 
					entry_context=f"String '{param_value_source}' is not a valid float format. Will check if it's a return value pointer or file reference instead.", depth_of_detail="0")
				log.debug("String '%s' is not a float", param_value_source)
				pass # Not a float

		# 2. Check if it's a return pointer
		if param_value_source in self.return_value_store:
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "return_value_store": self.return_value_store}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_in_return_value_store", 
				entry_context=f"Found parameter value source '{param_value_source}' in return value store with value {self.return_value_store[param_value_source]}. This is a return value pointer from a previous test step.", depth_of_detail="0")
			log.debug("Found param_value_source '%s' in return_value_store: %s", param_value_source, self.return_value_store[param_value_source])
			return self.return_value_store[param_value_source], None

		# 3. Check if it's a path to a file listed in the test definition's "files"
		log.debug("Checking if param_value_source '%s' is a file reference", param_value_source)
		log.debug("tc_name: %s, t_index: %d", self.tc_name, self.t_index)
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index}
		self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="checking_if_file_reference", 
			entry_context=f"Checking if parameter value source '{param_value_source}' is a file reference from the test definition. This allows parameters to reference test files by logical name or filename.", depth_of_detail="0")
		current_test_files = self.test_case_dict[self.tc_name]["tests"][self.t_index].get("files", {})
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "current_test_files": current_test_files}
		self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="current_test_files", 
			entry_context=f"Retrieved current test files mapping with {len(current_test_files)} entries. Will check if parameter value matches any logical names or filenames.", depth_of_detail="0")
		log.debug("Current test files mapping: %s", current_test_files)
		for logical_name, filename_in_test_def_files in current_test_files.items():
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="logical_name", 
				entry_context=f"Checking logical file name '{logical_name}' mapped to filename '{filename_in_test_def_files}' to see if it matches parameter value source '{param_value_source}'.", depth_of_detail="0")
			log.debug("Checking against logical_name '%s' -> filename '%s'", logical_name, filename_in_test_def_files)
			if param_value_source == filename_in_test_def_files: # e.g., param_value_source is "input.json"
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="matched_filename", 
					entry_context=f"Parameter value '{param_value_source}' matches filename '{filename_in_test_def_files}' in test files mapping. Will construct full file path for resolution.", depth_of_detail="0")
				# Construct the full path relative to the test folder
				full_file_path = os.path.join(self.test_folder_path, filename_in_test_def_files)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files, "full_file_path": full_file_path}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="constructed_full_path", 
					entry_context=f"Constructed full file path '{full_file_path}' by joining test folder path with filename. Will check if this file exists before returning the path.", depth_of_detail="0")
				log.debug("Matched filename. Full path would be: %s", full_file_path)
				if os.path.exists(full_file_path):
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files, "full_file_path": full_file_path}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_exists", 
						entry_context=f"File exists at path '{full_file_path}'. Successfully resolved parameter value to existing file path for function use.", depth_of_detail="0")
					log.debug("File exists at path: %s", full_file_path)
					return full_file_path, None
				else:
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files, "full_file_path": full_file_path}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_does_not_exist", 
						entry_context=f"Error: File does not exist at path '{full_file_path}'. This is a configuration issue where the test references a non-existent file.", depth_of_detail="0")
					error_msg = f"File path '{param_value_source}' (resolved to {full_file_path}) does not exist."
					log.debug("File does not exist: %s", error_msg)
					return None, error_msg
			elif param_value_source == logical_name: # e.g. param_value_source is "json_0" -> path/to/input.json
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="matched_logical_name", 
					entry_context=f"Parameter value '{param_value_source}' matches logical name '{logical_name}' mapped to filename '{filename_in_test_def_files}'. Will construct full file path for resolution.", depth_of_detail="0")
				full_file_path = os.path.join(self.test_folder_path, filename_in_test_def_files)
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files, "full_file_path": full_file_path}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="constructed_logical_path", 
					entry_context=f"Constructed full file path '{full_file_path}' from logical name '{logical_name}'. Will check if this file exists before returning the path.", depth_of_detail="0")
				log.debug("Matched logical name. Full path would be: %s", full_file_path)

				if os.path.exists(full_file_path):
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files, "full_file_path": full_file_path}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_exists", 
						entry_context=f"File exists at path '{full_file_path}' for logical name '{logical_name}'. Successfully resolved parameter value to existing file path for function use.", depth_of_detail="0")
					log.debug("File exists at path: %s", full_file_path)
					return full_file_path, None # Return the path itself
				else:
					error_msg = f"File for logical name '{logical_name}' (path {full_file_path}) does not exist."
					log.debug("File does not exist: %s", error_msg)
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "t_index": self.t_index, "logical_name": logical_name, "filename_in_test_def_files": filename_in_test_def_files, "full_file_path": full_file_path, "error_msg": error_msg}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_does_not_exist", 
						entry_context=f"Error: File for logical name '{logical_name}' does not exist at path '{full_file_path}'. This is a configuration issue where the test references a non-existent file.", depth_of_detail="0")
					return None, error_msg

		# 4. Check if it has a special flag to escape dot-seperated path parsing and just take it as a literal string.
		# This is useful for cases where parameter is a dot string that would normally be parsed but is actually what we are passing
		# to test this file's ability to parse that dot string.
		if isinstance(param_value_source, str) and param_value_source.startswith("!STR_LITERAL!"):
			log.debug("Found special flag '!STR_LITERAL!' at start of param_value_source. Taking as literal string: %s", param_value_source[13:])
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_str_literal_flag", 
				entry_context=f"Found special flag '!STR_LITERAL!' at start of parameter value source. This flag forces treatment as literal string, bypassing dot-path parsing for testing purposes.", depth_of_detail="0")
			return param_value_source[13:], None

		# 5. Check if it's a dot-separated path into a loaded JSON/dict (e.g., "json_0.key.value")
		if isinstance(param_value_source, str):
			timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
			self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="checking_if_dot_separated_path", 
				entry_context=f"Checking if parameter value source '{param_value_source}' is a dot-separated path for nested data access. This enables accessing nested dictionary or list values using dot notation.", depth_of_detail="0")
			parts = param_value_source.split('.')
			log.debug("Split param_value_source into parts: %s", parts)
			if len(parts) > 1 and parts[0] in self.loaded_test_files:
				log.debug("Found root part '%s' in loaded_test_files", parts[0])
				timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts}
				self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_root_part", 
					entry_context=f"Found root part '{parts[0]}' in files data for dot-path resolution. This provides the starting point for navigating the nested data structure.", depth_of_detail="0")
				current_val = self.loaded_test_files[parts[0]]
				log.debug("Initial value from loaded_test_files: %s", current_val)
				try:
					for part in parts[1:]:
						log.debug("Processing path part '%s'", part)
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts, "current_val": current_val, "part": part}
						self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="processing_path_part", 
							entry_context=f"Processing path part '{part}' in dot-separated path navigation. This continues traversing the nested data structure to reach the target value.", depth_of_detail="0")
						if isinstance(current_val, dict):
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts, "current_val": current_val, "part": part}
							self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="current_value_is_dict", 
								entry_context=f"Current value is a dictionary, accessing key '{part}'. This allows navigation into nested dictionary structures using dot notation.", depth_of_detail="0")
							log.debug("Current value is a dict, accessing key '%s'", part)
							current_val = current_val[part]
						elif isinstance(current_val, list) and part.isdigit():
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts, "current_val": current_val, "part": part}
							self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="current_value_is_list", 
								entry_context=f"Current value is a list, accessing index {part}. This allows navigation into list elements using numeric indices in dot paths.", depth_of_detail="0")
							log.debug("Current value is a list, accessing index %d", int(part))
							current_val = current_val[int(part)]
						else:
							timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts, "current_val": current_val, "part": part}
							self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="cannot_access_part", 
								entry_context=f"Cannot access part '{part}' on current value type {type(current_val)}. Dot-path navigation failed because current value is not a dictionary or list.", depth_of_detail="0")
							error_msg = f"Cannot access part '{part}' in '{param_value_source}'."
							log.error("Failed to access path part: %s", error_msg)
							return None, error_msg
						log.debug("New current value after accessing part '%s': %s", part, current_val)
						timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts, "current_val": current_val, "part": part}
						self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="new_current_val", 
							entry_context=f"Updated current value to '{current_val}' after accessing path part '{part}'. Continuing navigation through the nested data structure.", depth_of_detail="0")
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts, "current_val": current_val}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="successfully_resolved_path", 
						entry_context=f"Successfully resolved dot-separated path '{param_value_source}' to final value '{current_val}'. This parameter is now ready for function use.", depth_of_detail="0")
					log.debug("Successfully resolved path '%s' to value: %s", param_value_source, current_val)
					return current_val, None
				except (KeyError, IndexError, TypeError) as e:
					timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source, "parts": parts, "current_val": current_val, "part": part, "e": e}
					self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="error_accessing_path", 
						entry_context=f"Error occurred accessing dot-separated path '{param_value_source}': {e}. Path navigation failed and parameter cannot be resolved.", depth_of_detail="0")
					error_msg = f"Error accessing path '{param_value_source}' in loaded file '{parts[0]}': {e}"
					log.error("Error during path resolution: %s", error_msg)
					return None, error_msg
		
		# 5. If none of the above, it's a hardcoded string value
		log.debug("No special resolution found for '%s', treating as hardcoded string value", param_value_source)
		timeline_vars_dict = {"tc_name": self.tc_name, "t_name": self.t_name, "param_value_source": param_value_source}
		self._capture_timeline_event(function_name="_resolve_single_param_value", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="no_special_resolution_found", 
			entry_context=f"No special resolution methods matched parameter value '{param_value_source}'. Treating as literal hardcoded string value for function use.", depth_of_detail="0")
		return param_value_source, None


	def _validate_file_contents(self, checks: List[str]) -> Tuple[bool, List[str]]:
		"""
		Validates file contents based on a list of check strings.
		Each check string is "file_key_or_path:OPERATOR:operand"
		e.g., "json_1:IS:json_2" -> content of file for json_1 is identical to content of file for json_2
			  "output.txt:HAS:Some string"
			  "output.txt:EXCLUDES:Error string"
		Args:
			checks (List[str]): List of validation strings.
		Returns:
			Tuple[bool, List[str]]: Overall validation status and list of failure reasons.
		"""
		all_ok = True
		reasons = []

		timeline_vars_dict = {"checks": checks}
		self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="checks", 
			entry_context=f"Beginning file content validation with {len(checks)} checks to perform. Each check validates that file changes occurred correctly as side effects of function execution.", depth_of_detail="0")
		for check_str in checks:
			timeline_vars_dict = {"checks": checks, "check_str": check_str}
			self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="check_str", 
				entry_context=f"Processing file content check '{check_str}' which specifies a file, operator, and expected operand. Will parse this into components for validation execution.", depth_of_detail="0")
			parts = check_str.split(':', 2)
			if len(parts) != 3:
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "parts": parts}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="invalid_format", 
					entry_context=f"Invalid file content check format in '{check_str}'. Expected format is file:OPERATOR:operand, but found {len(parts)} parts instead of 3.", depth_of_detail="0")
				reasons.append(f"Invalid file content check format: '{check_str}'. Expected file:OPERATOR:operand.")
				all_ok = False
				continue

			file_ref, operator, operand_ref = parts[0].strip(), parts[1].strip().upper(), parts[2].strip()
			timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref}
			self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_ref", 
				entry_context=f"Parsed file content check into components: file='{file_ref}', operator='{operator}', operand='{operand_ref}'. Will resolve file reference to actual file path for content reading.", depth_of_detail="0")
			# Resolve file_ref to an actual file path
			log.debug("Resolving file_ref: %s", file_ref)
			file_to_check_path, err = self._resolve_single_param_value(file_ref)
			timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "file_to_check_path": file_to_check_path, "err": err}
			self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_to_check_path", 
				entry_context=f"Resolved file reference '{file_ref}' to path '{file_to_check_path}' with error status: {err}. Will verify file exists before reading content for validation.", depth_of_detail="0")
			
			if err or not isinstance(file_to_check_path, str) or not f_io.file_exists(file_to_check_path):
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "file_to_check_path": file_to_check_path, "err": err}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_not_found_or_path_resolution_failed", 
					entry_context=f"File '{file_ref}' for content validation not found or path resolution failed with error: {err if err else 'Invalid path'}. Cannot proceed with content checking.", depth_of_detail="0")
				reasons.append(f"File '{file_ref}' for content check not found or path resolution failed: {err if err else 'Not a valid path'}.")
				all_ok = False
				continue
			
			# Read the file content
			file_content = f_io.read_file(file_to_check_path)
			timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "file_to_check_path": file_to_check_path, "file_content": file_content}
			self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_content", 
				entry_context=f"Successfully read file content from '{file_to_check_path}' for validation. This content will be compared against expected criteria using the specified operator.", depth_of_detail="0")
			if file_content is None: # Should not happen if file_exists passed, but defensive
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "file_to_check_path": file_to_check_path}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="could_not_read_content", 
					entry_context=f"Could not read content from file '{file_to_check_path}' for validation. This prevents checking if file changes occurred correctly as expected.", depth_of_detail="0")
				reasons.append(f"Could not read content of file '{file_to_check_path}' for validation.")
				all_ok = False; continue

			# Check if the file content is identical to the operand
			if operator == "IS": # Operand must also be a file reference
				log.debug("Resolving operand_ref: %s", operand_ref)
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "err": err}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolving_operand_ref", 
					entry_context=f"Processing IS operator to check if file content is identical to another file. Will resolve operand reference '{operand_ref}' to get comparison file path.", depth_of_detail="0")
				other_file_path, err = self._resolve_single_param_value(operand_ref)
				if err or not isinstance(other_file_path, str) or not f_io.file_exists(other_file_path):
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "other_file_path": other_file_path, "err": err}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="other_file_not_found_or_path_resolution_failed", 
						entry_context=f"Comparison file '{operand_ref}' for IS operator not found or path resolution failed: {err if err else 'Invalid path'}. Cannot perform file content comparison.", depth_of_detail="0")
					reasons.append(f"Comparison file '{operand_ref}' for 'IS' operator not found or path resolution failed: {err if err else 'Not a valid path'}.")
					all_ok = False; continue
				
				if not f_io.are_files_equal(file_to_check_path, other_file_path, shallow=False):
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "other_file_path": other_file_path}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="content_not_identical", 
						entry_context=f"File content validation FAILED: '{file_ref}' is NOT identical to '{operand_ref}'. Files have different content when exact match was expected.", depth_of_detail="2")
					reasons.append(f"Content of '{file_ref}' is NOT identical to '{operand_ref}'.")
					all_ok = False
				else:
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "other_file_path": other_file_path}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="content_identical", 
						entry_context=f"File content validation PASSED: '{file_ref}' IS identical to '{operand_ref}'. Files have exactly matching content as expected.", depth_of_detail="2")
					log.info(f"File content validation: '{file_ref}' IS '{operand_ref}' - PASS")
			
			elif operator == "HAS": # Operand is a literal string to search for
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "file_content": file_content}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolving_operand_ref", 
					entry_context=f"Processing HAS operator to check if file content contains specified string. Will resolve operand reference '{operand_ref}' to get the search string value.", depth_of_detail="0")
				# Resolve operand_ref in case it's a reference to a value (e.g. from another json file)
				log.debug("Resolving operand_ref: %s", operand_ref)
				operand_value, err = self._resolve_single_param_value(operand_ref)
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "err": err}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="operand_value", 
					entry_context=f"Resolved operand reference '{operand_ref}' to value '{operand_value}' for HAS content search. Will check if file content contains this string value.", depth_of_detail="0")
				if err:
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "err": err}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="could_not_resolve_operand", 
						entry_context=f"Could not resolve operand '{operand_ref}' for HAS operator: {err}. This prevents checking if file contains the expected string content.", depth_of_detail="0")
					reasons.append(f"Could not resolve operand '{operand_ref}' for HAS operator: {err}")
					all_ok = False; continue
				if not isinstance(operand_value, str): operand_value = str(operand_value) # Ensure string

				if operand_value not in file_content:
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "file_content": file_content}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="content_does_not_have_string", 
						entry_context=f"File content validation FAILED: '{file_ref}' does NOT contain expected string '{operand_value[:50]}...'. Required content is missing from file.", depth_of_detail="2")
					reasons.append(f"Content of '{file_ref}' does NOT HAVE the string '{operand_value[:50]}...'.") # Truncate long strings
					all_ok = False
				else:
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "file_content": file_content}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="content_has_string", 
						entry_context=f"File content validation PASSED: '{file_ref}' HAS required string '{operand_value[:50]}...'. Expected content found in file.", depth_of_detail="2")
					log.info(f"File content validation: '{file_ref}' HAS '{operand_value[:50]}...' - PASS")

			elif operator == "EXCLUDES":
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "file_content": file_content}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="resolving_operand_ref", 
					entry_context=f"Processing EXCLUDES operator to verify file content does not contain specified value. Will resolve operand reference and check for absence in file content.", depth_of_detail="0")
				log.debug("Resolving operand_ref: %s", operand_ref)
				operand_value, err = self._resolve_single_param_value(operand_ref)
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "err": err}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="operand_value", 
					entry_context=f"Resolved operand reference '{operand_ref}' to value '{operand_value}' for EXCLUDES content check. Will verify this string is NOT present in file content.", depth_of_detail="0")
				if err:
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "err": err}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="could_not_resolve_operand", 
						entry_context=f"Could not resolve operand '{operand_ref}' for EXCLUDES operator: {err}. This prevents checking if file properly excludes the specified content.", depth_of_detail="0")
					reasons.append(f"Could not resolve operand '{operand_ref}' for EXCLUDES operator: {err}")
					all_ok = False; continue
				if not isinstance(operand_value, str): operand_value = str(operand_value) # Ensure string

				if operand_value in file_content:
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "file_content": file_content}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="content_contains_string", 
						entry_context=f"File content validation FAILED: '{file_ref}' contains string '{operand_value[:50]}...' when it should be excluded. Unwanted content found in file.", depth_of_detail="2")
					reasons.append(f"Content of '{file_ref}' UNEXPECTEDLY CONTAINS the string '{operand_value[:50]}...'.")
					all_ok = False
				else:
					timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "operand_value": operand_value, "file_content": file_content}
					self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="content_does_not_contain_string", 
						entry_context=f"File content validation PASSED: '{file_ref}' correctly excludes string '{operand_value[:50]}...'. Unwanted content is properly absent from file.", depth_of_detail="2")
					log.info(f"File content validation: '{file_ref}' EXCLUDES '{operand_value[:50]}...' - PASS")
			else:
				timeline_vars_dict = {"checks": checks, "check_str": check_str, "file_ref": file_ref, "operator": operator, "operand_ref": operand_ref, "file_content": file_content}
				self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="unknown_operator", 
					entry_context=f"Unknown validation operator '{operator}' in file content check '{check_str}'. Supported operators are IS, HAS, and EXCLUDES.", depth_of_detail="0")
				reasons.append(f"Unknown validation operator '{operator}' in file content check '{check_str}'.")
				all_ok = False
		if reasons != []:
			timeline_vars_dict = {"checks": checks, "file_ref": file_ref, "reasons": reasons}
			self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="validation_failed", 
				entry_context=f"File content validation FAILED with {len(reasons)} errors. File changes did not meet expected criteria: {'; '.join(reasons[:2])}...", depth_of_detail="2")
			warning_str = "File content validation failed for '%s': %s" % (file_ref, reasons)
			log.warning(warning_str)
		else:
			timeline_vars_dict = {"checks": checks, "file_ref": file_ref}
			self._capture_timeline_event(function_name="_validate_file_contents", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="validation_passed", 
				entry_context=f"File content validation PASSED for all {len(checks)} checks. All expected file changes occurred correctly as side effects of function execution.", depth_of_detail="2")
			log.info(f"File content validation: '{file_ref}' - PASS")
		return all_ok, reasons

	def _load_test_files_content(self, files_map: Dict[str, str]) -> bool:
		"""
		Loads content of specified files (JSON, CSV) into self.loaded_test_files.
		Also populates self.test_files_path_list with their absolute paths.
		Args:
			files_map (Dict[str, str]): A dictionary like {"json_0": "file.json", "csv_0": "data.csv"}
										 from the test definition's "files" key.
		Returns:
			bool: True if all essential files were loaded successfully, False otherwise.
		"""
		timeline_vars_dict = {"files_map": files_map}
		self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="files_map", 
			entry_context=f"Loading test files content from {len(files_map)} file mappings. Each file will be parsed and stored for parameter resolution during test execution.", depth_of_detail="0")
		self.test_files_path_list = []
		self.loaded_test_files = {} # Clear previous

		for logical_name, file_name_in_test_def in files_map.items():
			timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def}
			self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="logical_name", 
				entry_context=f"Processing file mapping '{logical_name}' -> '{file_name_in_test_def}' for content loading. This enables parameter references to use logical names instead of full paths.", depth_of_detail="0")
			file_path = os.path.join(self.test_folder_path, file_name_in_test_def)
			timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
			self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_path", 
				entry_context=f"Resolved file path to '{file_path}' for content loading. Will check if file exists and determine appropriate parsing method based on file extension.", depth_of_detail="0")
			self.test_files_path_list.append(file_path) # Store path regardless of type for path resolution

			if not f_io.file_exists(file_path):
				timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
				self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_not_found", 
					entry_context=f"File not found at path '{file_path}' for logical name '{logical_name}'. This prevents loading test data and may cause parameter resolution failures.", depth_of_detail="0")
				log.warning("Test file '%s' (logical name '%s') not found at path '%s'. This might cause failures.", file_name_in_test_def, logical_name, file_path)
				# Don't necessarily return False, as not all files might be critical for all params.
				# _resolve_parameters will handle missing files.
				continue

			if logical_name.lower().startswith("json"): # By convention, json_0, json_1 etc.
				timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
				self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="is_valid_json", 
					entry_context=f"File '{file_path}' contains valid JSON format. Will parse JSON content and store in loaded test files for parameter resolution.", depth_of_detail="0")
				if f_io.is_valid_json(file_path):
					timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
					self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="loaded_json_content", 
						entry_context=f"Successfully loaded and parsed JSON content from '{file_path}'. This data is now available for parameter resolution using logical name '{logical_name}'.", depth_of_detail="0")
					parsed_content = f_io.parse_json_file(file_path)
					timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path, "parsed_content": parsed_content}
					self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="parsed_content", 
						entry_context=f"Parsing JSON content from file '{file_path}' for storage in test data. Parsed data structure will be available for parameter resolution.", depth_of_detail="0")
					if parsed_content is not None:
						self.loaded_test_files[logical_name] = parsed_content
						timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path, "parsed_content": parsed_content}
						self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="loaded_json_content", 
							entry_context=f"Successfully loaded and parsed JSON content from '{file_path}'. This data is now available for parameter resolution using logical name '{logical_name}'.", depth_of_detail="0")
						log.info("Loaded JSON content from '%s' into self.loaded_test_files['%s']", file_path, logical_name)
					else:
						timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
						self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="failed_to_parse_json", 
							entry_context=f"Failed to parse JSON content from file '{file_path}': {e}. This prevents loading structured data for parameter resolution.", depth_of_detail="0")
						log.warning("Failed to parse valid JSON file '%s' for logical name '%s': %s", file_path, logical_name, e)
						return False
				else:
					timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
					self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="not_valid_json", 
						entry_context=f"File '{file_path}' does not contain valid JSON format. Will store file path instead of parsed content for parameter resolution.", depth_of_detail="0")
					log.warning("File '%s' (logical_name '%s') is not valid JSON. Not loading its content.", file_path, logical_name)
						
			elif logical_name.lower().startswith("csv"): # By convention, csv_0, etc.
				# For CSVs, we might just store the path, or load if needed by a specific test logic.
				# For now, store the path and let tests decide if they need to parse it via FileIOToolbox.
				# If CSV content needs to be directly referenceable like JSON, this needs expansion.
				self.loaded_test_files[logical_name] = file_path # Store path for CSVs, could be parsed on demand
				timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
				self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="stored_csv_path", 
					entry_context=f"Stored CSV file path '{file_path}' with logical name '{logical_name}' for parameter resolution. CSV content can be accessed via file path references.", depth_of_detail="0")
				log.info("Stored path for CSV '%s' ('%s') into self.loaded_test_files['%s']", file_path, logical_name, logical_name)

			elif logical_name.lower().startswith("py"): # By convention, py_0, etc.
				timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
				self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="extracting_python_components", 
					entry_context=f"Extracting Python AST components from file '{file_path}' for code analysis. This enables dynamic function loading and execution.", depth_of_detail="0")
				# For Python files, we need to extract the functions/methods from the file
				# and store it in self.loaded_test_files[logical_name]
				py_components = f_io.extract_python_components(file_path)
				timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path, "py_components": py_components}
				self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="py_components", 
					entry_context=f"Successfully extracted Python components (functions, classes, imports) from '{file_path}'. Code structure is now available for analysis.", depth_of_detail="0")
				if py_components is not None:
					try:
						self.loaded_test_files[logical_name] = {}
						self.loaded_test_files[logical_name]["python_components"] = py_components
						timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path, "py_components": py_components}
						self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="stored_python_components", 
							entry_context=f"Stored Python components for logical name '{logical_name}' from file '{file_path}'. AST data is now available for parameter resolution.", depth_of_detail="0")
						log.info("Stored python components for Python file '%s' ('%s') into self.loaded_test_files['%s']", file_path, logical_name, logical_name)
					except Exception as e:
						timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path, "py_components": py_components, "e": e}
						self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="failed_to_store_python_components", 
							entry_context=f"Failed to extract Python components from '{file_path}'. File may have syntax errors or invalid Python code structure.", depth_of_detail="0")
						log.error("Failed to store python components for Python file '%s' ('%s'): %s", file_path, logical_name, e)
						return False
			# Other file types can be added here if their content needs to be pre-loaded/parsed.
			else: # For other keys, just store the path.
				self.loaded_test_files[logical_name] = file_path
				timeline_vars_dict = {"files_map": files_map, "logical_name": logical_name, "file_name_in_test_def": file_name_in_test_def, "file_path": file_path}
				self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="stored_path", 
					entry_context=f"Stored file path '{file_path}' with logical name '{logical_name}' for parameter resolution. File content is accessible via path references.", depth_of_detail="0")
				log.info("Stored path for file '%s' ('%s') into self.loaded_test_files['%s']", file_path, logical_name, logical_name)
		
		timeline_vars_dict = {"files_map": files_map}
		self._capture_timeline_event(function_name="_load_test_files_content", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="loaded_test_files", 
			entry_context=f"Successfully loaded {len(self.loaded_test_files)} test files for parameter resolution. All test data is now available for function execution.", depth_of_detail="1")
		log.info("Loaded test files: %s", self.loaded_test_files)
		return True


	def _prepare_functions_for_test(self, func_identifiers: List[str], class_instance_args_list: List[Dict[str, Any]]) -> bool:
		"""
		Prepares callable functions/methods based on identifiers (e.g., "script_file.func" or "toolbox.Class.method").
		Stores them in self.prepared_functions.
		Args:
			func_identifiers (List[str]): List of function identifiers.
			class_instance_args_list (List[Dict[str, Any]]): List of {"class": "toolbox.Class", "instance_args":{...}}
		Returns:
			bool: True if all functions were prepared successfully.
		"""
		timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list}
		self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="func_identifiers", 
			entry_context=f"Preparing {len(func_identifiers)} function identifiers for test execution. Each identifier will be parsed to locate and import the required function or method.", depth_of_detail="0")
		self.prepared_functions = {} # Clear previous
		self.prepared_class_instances = {} # Clear previous
		base_repo_dir = Path(self.test_folder_path).parent.parent.parent # Assuming tests are in REPO_ROOT/TYPE/tests/script_tests/
		log.debug("Base repo dir: %s", base_repo_dir)

		for func_id_str in func_identifiers:
			log.info("Preparing function: %s", func_id_str)
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="func_id_str", 
				entry_context=f"Processing function ID string '{func_id_str}' to parse module, class, and function components. This identifier specifies the exact callable to prepare for testing.", depth_of_detail="0")
			parts = func_id_str.split('.')
			func_data = {**_FUNC_DICT} # Create a new dict instance
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="parts", 
				entry_context=f"Split function identifier '{func_id_str}' into {len(parts)} parts: {parts}. These components define the module path and callable hierarchy.", depth_of_detail="0")
			file_name_part = parts[0]
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "file_name_part": file_name_part}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_name_part", 
				entry_context=f"Extracted file name part '{file_name_part}' from identifier. This will be used to determine the module path and script type (auditor, drafter, or toolbox).", depth_of_detail="0")
			relative_file_path = ""
			target_file_path_abs = None
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="relative_file_path", 
				entry_context=f"Initial relative file path setup for function preparation. Path will be resolved based on script type detection from filename patterns.", depth_of_detail="0")
			# Determine script type and path
			# This logic might need to be more robust if filenames aren't perfectly unique across types
			if "_auditor" in file_name_part:
				relative_file_path = os.path.join("AUDITORS", f"{file_name_part}.py")
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="relative_file_path", 
					entry_context=f"Identified auditor script type from filename '{file_name_part}'. Setting relative path to AUDITORS/{file_name_part}.py for module import.", depth_of_detail="0")
			elif "_drafter" in file_name_part:
				relative_file_path = os.path.join("DRAFTERS", f"{file_name_part}.py")
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="relative_file_path", 
					entry_context=f"Identified drafter script type from filename '{file_name_part}'. Setting relative path to DRAFTERS/{file_name_part}.py for module import.", depth_of_detail="0")
			elif "_toolbox" in file_name_part: # Covers general toolboxes like file_io_toolbox
				relative_file_path = os.path.join("TOOLBOXES", f"{file_name_part}.py")
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="relative_file_path", 
					entry_context=f"Identified toolbox script type from filename '{file_name_part}'. Setting relative path to TOOLBOXES/{file_name_part}.py for module import.", depth_of_detail="0")
			elif "_test" in file_name_part: # Covers all test scripts
				relative_file_path = "TESTS"
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="relative_file_path", 
					entry_context=f"Identified test script type from filename '{file_name_part}'. Setting relative path to TESTS directory for module import.", depth_of_detail="0")
			else: # Default for other scripts, might need refinement
				# Try to find it based on metadata of the test plan perhaps?
				log.warning("Cannot determine script type for '%s' from name alone. Trying AUDITORS, DRAFTERS, then TOOLBOXES.", func_id_str)
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="relative_file_path", 
					entry_context=f"Cannot determine script type from filename '{file_name_part}'. Will search in AUDITORS, DRAFTERS, then TOOLBOXES directories to locate the module file.", depth_of_detail="0")
				possible_paths = [
					base_repo_dir / "AUDITORS" / f"{file_name_part}.py",
					base_repo_dir / "DRAFTERS" / f"{file_name_part}.py",
					base_repo_dir / "TOOLBOXES" / f"{file_name_part}.py"
				]
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "possible_paths": possible_paths}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="possible_paths", 
					entry_context=f"Generated {len(possible_paths)} possible file paths to search for module '{file_name_part}'. Will check each location in order until the module file is found.", depth_of_detail="0")
				for p_path in possible_paths:
					if p_path.exists():
						target_file_path_abs = p_path
						break
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "possible_paths": possible_paths, "target_file_path_abs": target_file_path_abs}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="target_file_path_abs", 
					entry_context=f"Found target file at absolute path '{target_file_path_abs}' after searching multiple directories. This module file contains the required function for testing.", depth_of_detail="0")
				if not target_file_path_abs:
					log.error("Could not locate file for '%s' in standard directories.", func_id_str)
					return False
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="relative_file_path", 
				entry_context=f"Initial relative file path setup for function preparation. Path will be resolved based on script type detection from filename patterns.", depth_of_detail="0")
			log.debug("relative_file_path: %s", relative_file_path)

			if not target_file_path_abs: # If not found by fallback
				if relative_file_path == "TESTS":
					target_file_path_abs =  Path(self.test_folder_path) / f"{file_name_part}.py"
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="target_file_path_abs", 
						entry_context=f"Set relative file path for unidentified script type. Will search standard directories to locate the module file.", depth_of_detail="0")
				else:
					target_file_path_abs = base_repo_dir / relative_file_path
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "relative_file_path": relative_file_path, "target_file_path_abs": target_file_path_abs}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="target_file_path_abs", 
						entry_context=f"Set relative file path for unidentified script type. Will search standard directories to locate the module file.", depth_of_detail="0")
			log.debug("target_file_path_abs: %s", target_file_path_abs)

			if not target_file_path_abs.exists():
				log.error("Target file %s for function ID %s does not exist.", target_file_path_abs, func_id_str)
				return False
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "target_file_path_abs": target_file_path_abs}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="target_file_path_abs", 
				entry_context=f"Set absolute file path for TESTS script type to '{target_file_path_abs}'. This handles test script modules in the test folder.", depth_of_detail="0")
			func_data["file_path"] = str(target_file_path_abs)
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "target_file_path_abs": target_file_path_abs}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="file_path", 
				entry_context=f"Stored file path '{target_file_path_abs}' in function data for later import and execution. This enables the test system to locate and call the target function.", depth_of_detail="0")
			# Extract AST components
			py_components = f_io.extract_python_components(str(target_file_path_abs))
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "target_file_path_abs": target_file_path_abs, "py_components": py_components}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", 
				tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="py_components", 
				entry_context=f"Extracted Python AST components from module file to analyze structure. This provides access to classes, functions, and methods defined in the module.", depth_of_detail="0")
			if py_components is None:
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "target_file_path_abs": target_file_path_abs, "py_components": py_components}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="python_components", 
					entry_context=f"Python components extraction failed for module '{target_file_path_abs}'. Cannot analyze code structure or prepare functions from this file.", depth_of_detail="0")
				log.error("Could not extract Python components from %s", target_file_path_abs)
				return False

			if len(parts) == 2: # script_file.function_in_script
				script_func_name = parts[1]
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "script_func_name": script_func_name}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="script_func_name", 
					entry_context=f"Extracting script function name '{script_func_name}' from identifier '{func_id_str}'. This is a direct function call without class instantiation.", depth_of_detail="0")
				found_node = False
				for node in py_components["functions"]:
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "script_func_name": script_func_name, "node": node}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="node", 
						entry_context=f"Searching for function node '{script_func_name}' in Python AST components. This locates the specific function definition for preparation.", depth_of_detail="0")
					if node.name == script_func_name:
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "script_func_name": script_func_name, "node": node}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_node", 
							entry_context=f"Found function node for '{script_func_name}' in module. This confirms the function exists and can be prepared for test execution.", depth_of_detail="0")
						func_data["function_node"] = node
						found_node = True
						break
				if not found_node:
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "script_func_name": script_func_name}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="function_node_not_found", 
						entry_context=f"Function node '{script_func_name}' not found in module '{target_file_path_abs}'. This prevents function preparation and will cause test failures.", depth_of_detail="0")
					log.error("Function node '%s' not found in %s", script_func_name, target_file_path_abs)
					return False
				try:
					func_data["callable_func"] = f_io.prepare_ast_script_function(func_data["function_node"], func_data["file_path"])
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "script_func_name": script_func_name}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="callable_func", 
						entry_context=f"Successfully prepared callable function '{script_func_name}' for test execution. Function is now ready to be invoked with test parameters.", depth_of_detail="0")
				except Exception as e:
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "func_data": func_data, "script_func_name": script_func_name, "e": e}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="failed_to_prepare_script_function", 
						entry_context=f"Failed to prepare script function '{script_func_name}' from module '{target_file_path_abs}'. This will prevent test execution for this function.", depth_of_detail="0")
					log.error("Failed to prepare script function '%s': %s", func_id_str, e)
					return False

			elif len(parts) == 3: # toolbox_file.class_name.function_in_class
				# file_name_part is parts[0]
				class_name_part = parts[1]
				method_name_part = parts[2]
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="class_name_part", 
					entry_context=f"Extracting class name '{class_name_part}' and method '{method_name_part}' from identifier '{func_id_str}'. This indicates a class method call requiring instantiation.", depth_of_detail="0")
				if class_name_part in self.prepared_class_instances.keys():
					func_data["class_node"] = self.prepared_class_instances[class_name_part]["class_node"]
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="class_node", 
						entry_context=f"Reusing existing class node for '{class_name_part}' from prepared class instances. This optimizes preparation by avoiding duplicate class analysis.", depth_of_detail="0")
					func_data["instance"] = self.prepared_class_instances[class_name_part]["instance"]
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="instance", 
						entry_context=f"Reusing existing class instance for '{class_name_part}' from prepared instances. This avoids duplicate instantiation and maintains state consistency.", depth_of_detail="0")
				else:
					found_class_node = None
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "found_class_node": found_class_node}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_class_node", 
						entry_context=f"Searching for class node '{class_name_part}' in Python AST components to prepare new class instance. This locates the class definition for instantiation.", depth_of_detail="0")
					for c_node in py_components["classes"]:
						if c_node.name.lower() == class_name_part.lower():
							found_class_node = c_node
							self.prepared_class_instances[class_name_part] = {}
							self.prepared_class_instances[class_name_part]["class_node"] = found_class_node
							self.prepared_class_instances[class_name_part]["instance"] = None
							func_data["class_node"] = found_class_node
							timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data, "found_class_node": found_class_node}
							self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_class_node", 
								entry_context=f"Found class node for '{class_name_part}' in module. Class definition is available for instantiation and method access.", depth_of_detail="0")
							break
				if not found_class_node: 
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="class_node_not_found", 
						entry_context=f"Class node '{class_name_part}' not found in module '{target_file_path_abs}'. Cannot instantiate class or prepare methods for testing.", depth_of_detail="0")
					log.error("Class node '%s' not found in %s", class_name_part, target_file_path_abs); return False
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="class_node", 
					entry_context=f"Processing class node '{class_name_part}' for method preparation. Will search for the specified method within this class definition.", depth_of_detail="0")
				log.debug("Found class node: %s", func_data["class_node"])
				found_method_node = None
				
				# Methods can be defined directly in class or be part of ast.FunctionDef list if not properly nested by parser
				# The f_io.extract_python_components returns functions at all levels. Need to check parentage or assume flat list for now.
				# For simplicity, check FunctionDef nodes within the class AST node directly.
				for node in found_class_node.body: # Iterate through items in class body
					if isinstance(node, inspect.ast.FunctionDef) and node.name == method_name_part:
						found_method_node = node
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "found_method_node": found_method_node}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_method_node", 
							entry_context=f"Found method node '{found_method_node}' in class '{class_name_part}'. Method definition is available for preparation and testing.", depth_of_detail="0")
						break
				if not found_method_node: # Fallback: check all functions if not found in class body (less accurate)
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_method_node_not_found", 
						entry_context=f"Method '{method_name_part}' not found in class '{class_name_part}' body. Falling back to search in global functions (less accurate method).", depth_of_detail="0")
					for f_node in py_components["functions"]: # This might pick up non-class functions if names collide
						if f_node.name == method_name_part: # TODO: Check f_node is child of class_node
							log.warning("Method '%s' found globally, not nested in AST for class '%s'. Assuming it's the correct one.", method_name_part, class_name_part)
							found_method_node = f_node
							timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "found_method_node": found_method_node}
							self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_method_node", 
								entry_context=f"Found method node '{method_name_part}' in class '{class_name_part}' (multiple matches). Using first match for method preparation.", depth_of_detail="0")
							break
				
				if not found_method_node:
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="found_method_node_not_found", 
						entry_context=f"Method '{method_name_part}' not found in class '{class_name_part}'. Cannot prepare method for testing - verify method name exists in class definition.", depth_of_detail="0")
					log.error("Method node '%s' not found in class '%s' in %s", method_name_part, class_name_part, target_file_path_abs)
					return False
				func_data["function_node"] = found_method_node # This is ast.FunctionDef for the method
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="function_node", 
					entry_context=f"Stored method node '{method_name_part}' as function node for preparation. Method can now be prepared for test execution.", depth_of_detail="0")

				# Get instance arguments for this specific class
				instance_kwargs_dict = {}
				target_class_full_id = f"{file_name_part}.{class_name_part}" # e.g., "my_toolbox.MyClass"
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "target_class_full_id": target_class_full_id}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="target_class_full_id", 
					entry_context=f"Generated target class full ID '{target_class_full_id}' for instance management. This enables reusing class instances across multiple method calls.", depth_of_detail="0")
				for class_arg_spec in class_instance_args_list:
					if class_arg_spec.get("class") == target_class_full_id:
						raw_instance_args = class_arg_spec.get("instance_args", {})
						# Resolve these instance_args like other parameters
						resolved_init_kwargs = self._resolve_parameters(raw_instance_args)
						instance_kwargs_dict = resolved_init_kwargs # Assuming all are kwargs for now
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "instance_kwargs_dict": instance_kwargs_dict}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="instance_kwargs_dict", 
							entry_context=f"Processing instance kwargs dictionary for class instantiation. These arguments will be passed to the class constructor.", depth_of_detail="0")
						break
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "instance_kwargs_dict": instance_kwargs_dict}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="instance_kwargs_dict", 
					entry_context=f"No instance kwargs provided for class instantiation. Will create instance using default constructor without arguments.", depth_of_detail="0")
				try:
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="preparing_class_method", 
						entry_context=f"Preparing class method '{method_name_part}' in '{class_name_part}' for test execution. Will create instance and bind method for calling.", depth_of_detail="0")
					log.debug("Preparing class method: %s", func_id_str)
					if self.prepared_class_instances[class_name_part]["instance"] is not None:
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="reusing_prepared_class_instance", 
							entry_context=f"Reusing existing prepared class instance for '{target_class_full_id}'. This optimizes performance by avoiding duplicate instantiation.", depth_of_detail="0")
						log.debug("Reusing prepared class instance for %s", func_id_str)
						func_data["instance"] = self.prepared_class_instances[class_name_part]["instance"]
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="instance", 
							entry_context=f"Retrieved existing class instance for '{class_name_part}' from prepared instances. Instance is ready for method binding.", depth_of_detail="0")
						func_data["callable_func"] = f_io.prepare_ast_class_method_for_instance(
							func_data["instance"],
							func_data["function_node"].name
						)
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="callable_func", 
							entry_context=f"Successfully prepared callable method '{method_name_part}' from existing class instance. Method is now ready for test execution with parameters.", depth_of_detail="0")
					else:
						log.debug("Preparing new class instance for %s", func_id_str)
						func_data["callable_func"], func_data["instance"] = f_io.prepare_ast_class_method(
							func_data["class_node"], 
							func_data["function_node"], 
							func_data["file_path"],
							instance_kwargs=instance_kwargs_dict
						)
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="instance", 
							entry_context=f"Created new instance of class '{class_name_part}' with provided arguments. Instance is ready for method binding and execution.", depth_of_detail="0")
						self.prepared_class_instances[class_name_part]["instance"] = func_data["instance"]
						timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
						self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="instance", 
							entry_context=f"Stored class instance for '{target_class_full_id}' for potential reuse. Future method calls on this class can reuse the same instance.", depth_of_detail="0")
					log.debug("Completed preparation of class method: %s", func_data["callable_func"])
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="completed_preparation_of_class_method", 
						entry_context=f"Successfully completed preparation of class method '{method_name_part}' in '{class_name_part}'. Method is now ready for test execution.", depth_of_detail="1")
				except Exception as e:
					timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "e": e}
					self._capture_timeline_event(function_name="_prepare_functions_for_test", 
						tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="failed_to_prepare_class_method", 
						entry_context=f"Failed to prepare class method '{func_id_str}': {e}. This will prevent test execution for this method.", depth_of_detail="0")
					log.error("Failed to prepare class method '%s': %s", func_id_str, e)
					return False
			else:
				timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part}
				self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="invalid_function_identifier_format", 
					entry_context=f"Invalid function identifier format '{func_id_str}'. Expected format: 'module.function' or 'module.Class.method'.", depth_of_detail="0")
				log.error("Invalid function identifier format: %s", func_id_str)
				return False
			
			timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
			self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="prepared_functions", 
				entry_context=f"Successfully prepared function '{func_id_str}' and stored in prepared functions collection. Function is now ready for test execution with parameters.", depth_of_detail="1")
			self.prepared_functions[func_id_str] = func_data
			log.info("Successfully prepared function/method: %s", func_id_str)
		
		timeline_vars_dict = {"func_identifiers": func_identifiers, "class_instance_args_list": class_instance_args_list, "func_id_str": func_id_str, "parts": parts, "class_name_part": class_name_part, "method_name_part": method_name_part, "func_data": func_data}
		self._capture_timeline_event(function_name="_prepare_functions_for_test", tag_category_list=["tc_name", "t_name"], variables_dict=timeline_vars_dict, pre_var_words="success_prepared_function", 
			entry_context=f"Successfully prepared function", depth_of_detail="2_more_detail")

		return True

def main():

	"""
	Main execution function for testing toolbox.
	"""
	log.info("test_toolbox.py main() started for self-testing.")
	parser = argparse.ArgumentParser(description="Test toolbox.")
	parser.add_argument("--test_plan", help="Optionally provide a path to a specific test plan.", default="TOOLBOXES/tests/test_toolbox/test_plan.json")
	parser.add_argument("--test_case", help="Optionally provide the name of a test case inside the provided test plan.", default=None)

	args = parser.parse_args()

	# Initialize TestToolbox with the fixed test plan path
	test_runner = TestToolbox(args.test_plan)

	# Execute the test plan
	log.info(f"Executing self-test plan: {args.test_plan}")
	if args.test_case is None:
		test_results = test_runner.execute_test_plan()
	else:
		test_results = test_runner.execute_test_plan(args.test_case)

	if test_results and test_results.get("summary", {}).get("failed", 0) == 0 and test_results.get("summary", {}).get("not_ran", 0) == 0:
		log.info("All self-tests passed or were skipped appropriately.")
	else:
		log.warning("Some self-tests failed or were not executed. Please review the report.")

	log.info("test_toolbox.py main() finished.")

if __name__ == "__main__":
	# The sys.path modification at the top of the file should handle imports
	# for when this script is run directly.
	main()
