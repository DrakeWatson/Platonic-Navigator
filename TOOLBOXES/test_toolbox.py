#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
	Description: 
		The test toolbox contains a single class (TestToolBox) that contains functions used for running .json formatted tests for python scripts.
	Usage:
	
"""

import os
import sys
import time

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import inspect
import json 
from pathlib import Path
from typing import Any, Dict, List, Tuple, Callable

try:
	from TOOLBOXES import logging_toolbox
	from TOOLBOXES import file_io_toolbox
	from TOOLBOXES import system_trace_toolbox 
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
		"""
		
		self.test_plan_path = test_plan_path
		self.test_case_dict: Dict[str, Any] = {}
		self.timeline_str_dict = {"__init__": f"Test Plan: {test_plan_path}"}
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

		# Initialize the SystemTraceToolbox
		# It will automatically generate/load the context map for this script.
		self.tracer = system_trace_toolbox.SystemTraceToolbox(
			target_script_path=__file__, # The path to this current script
			capture_event_callback=self._capture_timeline_event
		)
		self.target_tracer_dict = {}
		self.prev_trace_time = 0
		self.same_time_counter = 0

	def _capture_timeline_event(self, file_name: str, function_name : str, variables_dict: dict, line_num: str, entry_context:str, depth_of_detail: int, code_str:str):
		"""
		Captures a timeline event. This is now the callback for the Tracer.
		"""
		time_nanoseconds = time.time_ns()
		# Modern CPUs can execute faster than nanosecond timescales. Keep track of ordering.
		if time_nanoseconds == self.prev_trace_time:
			self.same_time_counter += 1
		else:
			self.same_time_counter = 0
			self.prev_trace_time = time_nanoseconds

		timeline_str = f"{time_nanoseconds}.{self.same_time_counter}.{file_name}.{function_name}.{line_num}"
		
		test_details = ""
		if self.tc_name != "":
			test_details += f"{self.tc_name}"
		if self.t_name != "":
			test_details += f".{self.t_name}"
		stored_variable_dict = {}
		# Sanitize variables to avoid circular references and large objects
		for variable, value in variables_dict.items():
			if variable.startswith('self') or variable == 'log' or variable == 'f_io' or variable == 'tracer':
				continue
			try:
				# Attempt to get a reasonable string representation
				str_val = str(value)
				if len(str_val) > 500: # Truncate very long values
					str_val = str_val[:500] + "..."
				stored_variable_dict[variable] = str_val
			except Exception:
				stored_variable_dict[variable] = f"<unserializable: {type(value).__name__}>"

		timeline_entry_dict = {
			"entry_context": entry_context, 
			"variables_dict": stored_variable_dict,
			"depth_of_detail": depth_of_detail,
			"code_str": code_str,
			"test_details": test_details
		}
		
		final_key = f"{timeline_str}"
		self.timeline_str_dict[final_key] = timeline_entry_dict
		
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

		for index, test_case_header in enumerate(self.test_plan.get("test_cases", [])):
			self.tc_index = index
			self.tc_name = test_case_header.get("name", f"unnamed_test_case_{index}")
			self.tc_type = test_case_header.get("test_case_type", "unknown").lower()
			self.tc_subtype = test_case_header.get("test_case_subtype", "unknown").lower()
			
			if test_case_name != "" and self.tc_name != test_case_name:
				log.debug("Skipping test case %s because it is not the one specified to run.", self.tc_name)
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
			
			test_case_file_path = os.path.join(self.test_folder_path, f"{self.tc_name}.json")
			current_tc_full_data = f_io.parse_json_file(test_case_file_path)

			if current_tc_full_data is None:
				log.error("Test case file %s is invalid or empty. Skipping.", test_case_file_path)
				# Create a dummy result for the whole test case if file is missing/invalid
				tc_result_entry = {**_TC_RESULT_DICT, "name": self.tc_name, "tests": [{**_T_RESULT_DICT, "name": "file_load", "status": "NOT_RAN", "reason": f"Failed to load {test_case_file_path}"}]}
				detailed_results.append(tc_result_entry)
				overall_results_summary["not_ran"] += 1 # Assuming one main "test" for loading the TC file
				overall_results_summary["total_tests"] +=1
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
		self._log_final_report(final_report)

		report_file_name = f"test_report_{self.tc_name}_{logging_toolbox.datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
		report_file_path = os.path.join(self.test_folder_path, report_file_name)
		f_io.write_json(report_file_path, final_report)

		timeline_file_name = f"timeline_{logging_toolbox.datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
		timeline_file_path = os.path.join(self.test_folder_path, timeline_file_name)
		f_io.write_json(timeline_file_path, self.timeline_str_dict)

		return final_report

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
			log.line_wrap(line, "info", 150)

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

		for index, test_definition in enumerate(current_tc_data.get("tests", [])):
			self.t_index = index
			self.t_name = test_definition.get("test_name", f"unnamed_test_{index}")
			self.return_value_store.clear() # Clear previous test's return values
			self.loaded_test_files.clear() # Clear previously loaded test files' content
			self.prepared_functions.clear() # Clear previously prepared functions
			
			test_cases = self.test_plan.get("test_cases", {})
			test_case_data = next((test_case for test_case in test_cases if test_case["name"] == self.tc_name), None)

			if test_case_data is None:
				log.error("Test case '%s' not found in test plan.", self.tc_name)
				continue

			test_case_data = test_case_data.get("tests", [])
			test_details = next((test for test in test_case_data if test["test_name"] == self.t_name), None)
			if test_details is None:
				log.error("Test '%s' not found in test case '%s'.", self.t_name, self.tc_name)
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
			test_result_entry = self._execute_single_test_definition(test_definition)
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

		# The tracer will not be active during environment prep to reduce noise.
		if not self._prepare_test_environment(test_def):
			result_dict["status"] = "NOT_RAN"
			result_dict["reason"] = "Failed to prepare test environment."
			return result_dict
		
		# Get the paths of all target scripts for this specific test
		target_script_paths = [info['file_path'] for info in self.prepared_functions.values()]
		
		# Add the target script paths to the main tracer for this run
		self.tracer.add_trace_targets(target_script_paths)

		# Activate the tracer only around the core execution logic
		try:
			with self.tracer.start_trace():
				# All code executed within this block will be traced line-by-line
				if self.tc_type == "unit":
					self._run_unit_test_steps(test_def, result_dict)
				elif self.tc_type == "integration":
					self._run_integration_test_steps(test_def, result_dict)
				elif self.tc_type == "full":
					self._run_full_test_steps(test_def, result_dict)
				else:
					result_dict["status"] = "NOT_RAN"
					result_dict["reason"] = f"Unknown test case type: {self.tc_type}"
					log.error("Unknown test type '%s' for %s.%s", self.tc_type, self.tc_name, self.t_name)
		
		except Exception as e:
			# The tracer will have already logged the exception details.
			log.exception("Unhandled exception during traced execution for %s.%s: %s", self.tc_name, self.t_name, e)
			result_dict["status"] = "FAIL"
			result_dict["reason"] = f"Unhandled execution error: {type(e).__name__}: {str(e)}"
			
		# If status is still empty, it means steps ran but no explicit PASS/FAIL was set by subtype logic (should be handled within).
		# This can happen if validation logic is incomplete. Default to NOT_RAN if not explicitly set.
		if not result_dict["status"]:
			log.warning("Test %s.%s completed steps but status was not explicitly set. Defaulting to NOT_RAN.", self.tc_name, self.t_name)
			result_dict["status"] = "NOT_RAN"
			result_dict["reason"] = "Test steps executed but no PASS/FAIL condition was met."
			
		return result_dict

	def _prepare_test_environment(self, test_def: Dict[str, Any]) -> bool:
		"""Loads files and prepares functions needed for the test."""
		if not self._load_test_files_content(test_def.get("files", {})):
			return False
		if not self._prepare_functions_for_test(test_def.get("functions", []), test_def.get("class_instance_args", [])):
			return False
		return True

	def _run_unit_test_steps(self, test_def: Dict[str, Any], result_dict: Dict[str, Any]):
		""" Executes steps for a unit test and updates result_dict. """
		log.info(" | Executing Unit Test Steps for %s (Subtype: %s)", self.t_name, self.tc_subtype)
		
		# Assuming unit tests usually have one primary function call defined in "test_steps_order"
		test_steps = test_def.get("test_steps_order", [])
		if not test_steps:
			result_dict["status"] = "FAIL"
			result_dict["reason"] = "No test steps defined for unit test."
			return

		# For unit tests, we usually focus on a single primary function call.
		# The template suggests "test_steps_order" even for unit, so we'll follow that.
		# This loop will typically run once for a simple unit test.
		for step_index, step in enumerate(test_steps):
			func_key = step.get("function")
			if not func_key or func_key not in self.prepared_functions:
				result_dict["status"] = "FAIL"
				result_dict["reason"] = f"Function '{func_key}' in step {step_index} not prepared."
				return

			callable_func_info = self.prepared_functions[func_key]
			actual_callable = callable_func_info["callable_func"]
			params_config = step.get("params", {})
			expected_exception_name = test_def.get("expected_exception", "")
			func_script_name = func_key.split('.')[0]
			
			try: # Parameters need to be resolved before we pass them into the function we are testing.
				resolved_params = self._resolve_parameters(params_config)
				
				try: # We need to catch exceptions from the function we are testing in case we expect them.
					return_values = actual_callable(**resolved_params)
				except Exception as e:
					if e.__class__.__name__ == expected_exception_name:
						result_dict["status"] = "PASS"
					else:
						result_dict["status"] = "FAIL"
						if expected_exception_name:
							result_dict["reason"] = f"Expected '{expected_exception_name}', but got '{e.__class__.__name__}': {e}"
						else:
							result_dict["reason"] = f"Unexpected exception '{e.__class__.__name__}': {e}"
					
					continue

				# Store return values if pointers are defined
				return_pointers = step.get("return_pointers", [])
				if not isinstance(return_values, tuple): # Ensure return_values is a tuple for consistent indexing
					return_values = (return_values,)
				for i, ptr_name in enumerate(return_pointers):
					if i < len(return_values):
						self.return_value_store[ptr_name] = return_values[i]
					else:
						self.return_value_store[ptr_name] = None
						log.warning("Return pointer '%s' defined but function returned too few values.", ptr_name)

				if step_index < len(test_steps) - 1: # Don't perform validation if it's not the last step
					continue

				# Perform Validations
				validation_passed = True
				validation_reasons = []
				
				# 1. Validate return values
				expected_returns = test_def.get("expected_return_value_and_order", {})
				if expected_returns:
					for ret_var_name, spec in expected_returns.items():
						if ret_var_name not in self.return_value_store:
							validation_passed = False
							reason = f"Expected return variable '{ret_var_name}' not found in return pointers."
							validation_reasons.append(reason)
							log.warning(reason)
							continue

						actual_val = self.return_value_store[ret_var_name]
						expected_val_source = list(spec.values())[0] # e.g., "hardcoded_var_value" or "json_1.key.path"
						log.debug("expected_val_source before being resolved: %s", expected_val_source)
						log.debug("actual_val: %s", actual_val)
						resolved_expected_val, error = self._resolve_single_param_value(expected_val_source)
						if error:
							validation_passed = False
							reason = f"Could not resolve expected value for '{ret_var_name}': {error}"
							validation_reasons.append(reason)
							log.warning(reason)
							continue

						if actual_val != resolved_expected_val:
							validation_passed = False
							reason = f"Return value mismatch for '{ret_var_name}': Expected '{resolved_expected_val}' (type {type(resolved_expected_val)}), Got '{actual_val}' (type {type(actual_val)})"
							validation_reasons.append(reason)
						
						if validation_passed:
							log.info(f"Return value for '{ret_var_name}' matched: '{actual_val}'")
						else:
							log.warning(validation_reasons)

				# 2. Validate file content
				expected_file_content_checks = test_def.get("expected_file_content", [])
				if expected_file_content_checks:
					file_content_ok, file_reasons = self._validate_file_contents(expected_file_content_checks)
					if not file_content_ok:
						validation_passed = False
						validation_reasons.extend(file_reasons)

				if validation_passed:
					result_dict["status"] = "PASS"
				else:
					result_dict["status"] = "FAIL"
					result_dict["reason"] = "; ".join(validation_reasons)

			except Exception as e:
				result_dict["status"] = "FAIL"
				result_dict["reason"] = f"Execution error in function {func_key}: {e}"
				return # Stop on first error in a step

	def _run_integration_test_steps(self, test_def: Dict[str, Any], result_dict: Dict[str, Any]):
		""" Executes steps for an integration test and updates result_dict. """
		log.info("Executing Integration Test Steps for %s", self.t_name)
		test_steps = test_def.get("test_steps_order", [])

		if not test_steps:
			result_dict["status"] = "FAIL"
			result_dict["reason"] = "No test_steps_order defined for integration test."
			return

		all_steps_passed = True
		step_failure_reason = ""

		for step_index, step in enumerate(test_steps):
			func_key = step.get("function")
			if not func_key or func_key not in self.prepared_functions:
				all_steps_passed = False
				step_failure_reason = f"Function '{func_key}' in step {step_index} not prepared or found."
				break 

			callable_func_info = self.prepared_functions[func_key]
			actual_callable = callable_func_info["callable_func"]
			params_config = step.get("params", {})
			func_script_name = func_key.split('.')[0]
			
			try:
				resolved_params = self._resolve_parameters(params_config)
				log.info("Calling step %s: %s with params %s", step_index, func_key, resolved_params)

				return_values = actual_callable(**resolved_params)

				# Store return values if pointers are defined
				return_pointers = step.get("return_pointers", [])
				if not isinstance(return_values, tuple):
					return_values = (return_values,) # Ensure tuple for consistent indexing
				for i, ptr_name in enumerate(return_pointers):
					if i < len(return_values):
						self.return_value_store[ptr_name] = return_values[i]
						log.info("Stored return pointer '%s' = %s", ptr_name, return_values[i])
					else:
						self.return_value_store[ptr_name] = None
						log.warning("Return pointer '%s' defined for step %s but function returned too few values.", ptr_name, step_index)

			except Exception as e:
				log.exception("Exception during integration test step %s for %s.%s, function %s: %s", step_index, self.tc_name, self.t_name, func_key, e)
				all_steps_passed = False
				step_failure_reason = f"Execution error in step {step_index} (function {func_key}): {type(e).__name__}: {str(e)}"
				break # Stop integration test on first error

		if all_steps_passed:
			# Final validation for integration tests (after all steps)
			validation_passed = True
			validation_reasons = []
			# 1. Validate return values based on "expected_return_value_and_order"
			expected_returns = test_def.get("expected_return_value_and_order", {})

			if expected_returns:
				for ret_var_name, spec in expected_returns.items():
					if ret_var_name not in self.return_value_store:
						validation_passed = False
						reason = f"Expected final return variable '{ret_var_name}' not found in store."
						validation_reasons.append(reason); log.warning(reason)
						continue
					actual_val = self.return_value_store[ret_var_name]
					expected_val_source = list(spec.values())[0]
					log.debug("expected_val_source: %s", expected_val_source)
					resolved_expected_val, error = self._resolve_single_param_value(expected_val_source)
					if error:
						validation_passed = False
						reason = f"Could not resolve expected value for '{ret_var_name}': {error}"
						validation_reasons.append(reason)
						log.warning(reason)
						continue
					if actual_val != resolved_expected_val:
						validation_passed = False
						reason = f"Final return value mismatch for '{ret_var_name}': Expected '{resolved_expected_val}', Got '{actual_val}'"
						validation_reasons.append(reason)
						log.warning(reason)
			
			# 2. Validate file content based on "expected_file_content"
			expected_file_content_checks = test_def.get("expected_file_content", [])
			if expected_file_content_checks:
				file_content_ok, file_reasons = self._validate_file_contents(expected_file_content_checks)
				if not file_content_ok:
					validation_passed = False
					validation_reasons.extend(file_reasons)
			
			# 3. Check for expected exception IF defined at the top level for the whole integration test
			expected_exception_name = test_def.get("expected_exception")
			if expected_exception_name: # This means no exception should have occurred during steps if we reach here
				result_dict["status"] = "FAIL"
				result_dict["reason"] = f"Expected exception '{expected_exception_name}' for the integration flow was not raised."
				return

			if validation_passed:
				result_dict["status"] = "PASS"
			else:
				result_dict["status"] = "FAIL"
				result_dict["reason"] = "; ".join(validation_reasons) if validation_reasons else "Integration test final validation failed."
		else: # A step failed
			# If an exception was expected for the whole flow, and it occurred mid-step matching the type:
			expected_exception_name = test_def.get("expected_exception")
			if expected_exception_name and "Execution error" in step_failure_reason:
				# Basic check if the type name is in the failure reason (could be more precise)
				if expected_exception_name in step_failure_reason:
					result_dict["status"] = "PASS"
					result_dict["reason"] = f"Correctly caught expected exception '{expected_exception_name}' during integration flow."
					log.info(result_dict["reason"])
					return 
			
			result_dict["status"] = "FAIL"
			result_dict["reason"] = step_failure_reason
	
	def _run_full_test_steps(self, test_def: Dict[str, Any], result_dict: Dict[str, Any]):
		""" Executes steps for a full test. Similar to integration but may have more complex validation. """
		log.info("Executing Full Test Steps for %s (currently same logic as integration)", self.t_name)
		# For now, full tests will follow the same logic as integration tests.
		# This can be expanded later if "full" tests have unique requirements.
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
		for param_name, param_value_source in params_config.items():
			log.debug("Resolving param value source: %s", param_value_source)
			val, error_msg = self._resolve_single_param_value(param_value_source)
			if error_msg:
				log.warning("Error resolving param '%s': %s. Using string value '%s'.", param_name, error_msg, param_value_source)
				resolved_params[param_name] = param_value_source
			else:
				resolved_params[param_name] = val
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
		if isinstance(param_value_source, dict):
			log.debug("Found dictionary param_value_source with keys: %s", list(param_value_source.keys()))
			for key, value in param_value_source.items():
				log.debug("Resolving dictionary value for key '%s': %s", key, value)
				resolved_value, error = self._resolve_single_param_value(value)
				if error:
					log.debug("Error resolving dictionary value for key '%s': %s", key, error)
					return None, error
				log.debug("Successfully resolved dictionary value for key '%s' to: %s", key, resolved_value)
				param_value_source[key] = resolved_value
			log.debug("Completed resolving dictionary param_value_source. Final result: %s", param_value_source)
			return param_value_source, None
		elif isinstance(param_value_source, list):
			log.debug("Found list param_value_source with %d items", len(param_value_source))
			for i, value in enumerate(param_value_source):
				log.debug("Resolving list value at index %d: %s", i, value)
				resolved_value, error = self._resolve_single_param_value(value)
				if error:
					log.error("Error resolving list value at index %d: %s", i, error)
					return None, error
				log.debug("Successfully resolved list value at index %d to: %s", i, resolved_value)
				param_value_source[i] = resolved_value
			log.debug("Completed resolving list param_value_source. Final result: %s", param_value_source)
			return param_value_source, None
		
		# 1. Check special hardcoded values
		if isinstance(param_value_source, str): # Ensure it's a string before lowercasing etc.
			log.debug("Processing string param_value_source: %s", param_value_source)
			val_lower = param_value_source.lower()
			if val_lower == "true": 
				log.debug("Resolved 'true' to boolean True")
				return True, None
			if val_lower == "false": 
				log.debug("Resolved 'false' to boolean False")
				return False, None
			if val_lower == "null" or val_lower == "none": 
				log.debug("Resolved 'null'/'none' to None")
				return None, None
			try: # Integer?
				result = int(param_value_source)
				log.debug("Resolved string '%s' to integer: %d", param_value_source, result)
				return result, None
			except ValueError:
				log.debug("String '%s' is not an integer", param_value_source)
				pass # Not an int
			try: # Float?
				result = float(param_value_source)
				log.debug("Resolved string '%s' to float: %f", param_value_source, result)
				return result, None
			except ValueError:
				log.debug("String '%s' is not a float", param_value_source)
				pass # Not a float

		# 2. Check if it's a return pointer
		if param_value_source in self.return_value_store:
			log.debug("Found param_value_source '%s' in return_value_store: %s", param_value_source, self.return_value_store[param_value_source])
			return self.return_value_store[param_value_source], None

		# 3. Check if it's a path to a file listed in the test definition's "files"
		log.debug("Checking if param_value_source '%s' is a file reference", param_value_source)
		log.debug("tc_name: %s, t_index: %d", self.tc_name, self.t_index)
		current_test_files = self.test_case_dict[self.tc_name]["tests"][self.t_index].get("files", {})
		log.debug("Current test files mapping: %s", current_test_files)
		for logical_name, filename_in_test_def_files in current_test_files.items():
			log.debug("Checking against logical_name '%s' -> filename '%s'", logical_name, filename_in_test_def_files)
			if param_value_source == filename_in_test_def_files: # e.g., param_value_source is "input.json"
				# Construct the full path relative to the test folder
				full_file_path = os.path.join(self.test_folder_path, filename_in_test_def_files)
				log.debug("Matched filename. Full path would be: %s", full_file_path)
				if os.path.exists(full_file_path):
					log.debug("File exists at path: %s", full_file_path)
					return full_file_path, None
				else:
					error_msg = f"File path '{param_value_source}' (resolved to {full_file_path}) does not exist."
					log.debug("File does not exist: %s", error_msg)
					return None, error_msg
			elif param_value_source == logical_name: # e.g. param_value_source is "json_0" -> path/to/input.json
				full_file_path = os.path.join(self.test_folder_path, filename_in_test_def_files)
				log.debug("Matched logical name. Full path would be: %s", full_file_path)

				if os.path.exists(full_file_path):
					log.debug("File exists at path: %s", full_file_path)
					return full_file_path, None # Return the path itself
				else:
					error_msg = f"File for logical name '{logical_name}' (path {full_file_path}) does not exist."
					log.debug("File does not exist: %s", error_msg)
					return None, error_msg

		# 4. Check if it has a special flag to escape dot-seperated path parsing and just take it as a literal string.
		# This is useful for cases where parameter is a dot string that would normally be parsed but is actually what we are passing
		# to test this file's ability to parse that dot string.
		if isinstance(param_value_source, str) and param_value_source.startswith("!STR_LITERAL!"):
			log.debug("Found special flag '!STR_LITERAL!' at start of param_value_source. Taking as literal string: %s", param_value_source[13:])
			return param_value_source[13:], None

		# 5. Check if it's a dot-separated path into a loaded JSON/dict (e.g., "json_0.key.value")
		if isinstance(param_value_source, str):
			parts = param_value_source.split('.')
			log.debug("Split param_value_source into parts: %s", parts)
			if len(parts) > 1 and parts[0] in self.loaded_test_files:
				log.debug("Found root part '%s' in loaded_test_files", parts[0])
				current_val = self.loaded_test_files[parts[0]]
				log.debug("Initial value from loaded_test_files: %s", current_val)
				try:
					for part in parts[1:]:
						log.debug("Processing path part '%s'", part)
						if isinstance(current_val, dict):
							log.debug("Current value is a dict, accessing key '%s'", part)
							current_val = current_val[part]
						elif isinstance(current_val, list) and part.isdigit():
							log.debug("Current value is a list, accessing index %d", int(part))
							current_val = current_val[int(part)]
						else:
							error_msg = f"Cannot access part '{part}' in '{param_value_source}'."
							log.error("Failed to access path part: %s", error_msg)
							return None, error_msg
						log.debug("New current value after accessing part '%s': %s", part, current_val)
					log.debug("Successfully resolved path '%s' to value: %s", param_value_source, current_val)
					return current_val, None
				except (KeyError, IndexError, TypeError) as e:
					error_msg = f"Error accessing path '{param_value_source}' in loaded file '{parts[0]}': {e}"
					log.error("Error during path resolution: %s", error_msg)
					return None, error_msg
		
		# 5. If none of the above, it's a hardcoded string value
		log.debug("No special resolution found for '%s', treating as hardcoded string value", param_value_source)
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

		for check_str in checks:
			parts = check_str.split(':', 2)
			if len(parts) != 3:
				reasons.append(f"Invalid file content check format: '{check_str}'. Expected file:OPERATOR:operand.")
				all_ok = False
				continue

			file_ref, operator, operand_ref = parts[0].strip(), parts[1].strip().upper(), parts[2].strip()
			# Resolve file_ref to an actual file path
			log.debug("Resolving file_ref: %s", file_ref)
			file_to_check_path, err = self._resolve_single_param_value(file_ref)
			
			if err or not isinstance(file_to_check_path, str) or not f_io.file_exists(file_to_check_path):
				reasons.append(f"File '{file_ref}' for content check not found or path resolution failed: {err if err else 'Not a valid path'}.")
				all_ok = False
				continue
			
			# Read the file content
			file_content = f_io.read_file(file_to_check_path)
			if file_content is None: # Should not happen if file_exists passed, but defensive
				reasons.append(f"Could not read content of file '{file_to_check_path}' for validation.")
				all_ok = False; continue

			# Check if the file content is identical to the operand
			if operator == "IS": # Operand must also be a file reference
				log.debug("Resolving operand_ref: %s", operand_ref)
				other_file_path, err = self._resolve_single_param_value(operand_ref)
				if err or not isinstance(other_file_path, str) or not f_io.file_exists(other_file_path):
					reasons.append(f"Comparison file '{operand_ref}' for 'IS' operator not found or path resolution failed: {err if err else 'Not a valid path'}.")
					all_ok = False; continue
				
				if not f_io.are_files_equal(file_to_check_path, other_file_path, shallow=False):
					reasons.append(f"Content of '{file_ref}' is NOT identical to '{operand_ref}'.")
					all_ok = False
				else:
					log.info(f"File content validation: '{file_ref}' IS '{operand_ref}' - PASS")
			
			elif operator == "HAS": # Operand is a literal string to search for
				# Resolve operand_ref in case it's a reference to a value (e.g. from another json file)
				log.debug("Resolving operand_ref: %s", operand_ref)
				operand_value, err = self._resolve_single_param_value(operand_ref)
				if err:
					reasons.append(f"Could not resolve operand '{operand_ref}' for HAS operator: {err}")
					all_ok = False; continue
				if not isinstance(operand_value, str): operand_value = str(operand_value) # Ensure string

				if operand_value not in file_content:
					reasons.append(f"Content of '{file_ref}' does NOT HAVE the string '{operand_value[:50]}...'.") # Truncate long strings
					all_ok = False
				else:
					log.info(f"File content validation: '{file_ref}' HAS '{operand_value[:50]}...' - PASS")

			elif operator == "EXCLUDES":
				log.debug("Resolving operand_ref: %s", operand_ref)
				operand_value, err = self._resolve_single_param_value(operand_ref)
				if err:
					reasons.append(f"Could not resolve operand '{operand_ref}' for EXCLUDES operator: {err}")
					all_ok = False; continue
				if not isinstance(operand_value, str): operand_value = str(operand_value) # Ensure string

				if operand_value in file_content:
					reasons.append(f"Content of '{file_ref}' UNEXPECTEDLY CONTAINS the string '{operand_value[:50]}...'.")
					all_ok = False
				else:
					log.info(f"File content validation: '{file_ref}' EXCLUDES '{operand_value[:50]}...' - PASS")
			else:
				reasons.append(f"Unknown validation operator '{operator}' in file content check '{check_str}'.")
				all_ok = False
		if reasons != []:
			warning_str = "File content validation failed for '%s': %s" % (file_ref, reasons)
			log.warning(warning_str)
		else:
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
		self.test_files_path_list = []
		self.loaded_test_files = {} # Clear previous

		for logical_name, file_name_in_test_def in files_map.items():
			file_path = os.path.join(self.test_folder_path, file_name_in_test_def)
			self.test_files_path_list.append(file_path) # Store path regardless of type for path resolution

			if not f_io.file_exists(file_path):
				log.warning("Test file '%s' (logical name '%s') not found at path '%s'. This might cause failures.", file_name_in_test_def, logical_name, file_path)
				# Don't necessarily return False, as not all files might be critical for all params.
				# _resolve_parameters will handle missing files.
				continue

			if logical_name.lower().startswith("json"): # By convention, json_0, json_1 etc.
				if f_io.is_valid_json(file_path):
					parsed_content = f_io.parse_json_file(file_path)
					if parsed_content is not None:
						self.loaded_test_files[logical_name] = parsed_content
						log.info("Loaded JSON content from '%s' into self.loaded_test_files['%s']", file_path, logical_name)
					else:
						log.warning("Failed to parse valid JSON file '%s' for logical name '%s': %s", file_path, logical_name, e)
						return False
				else:
					log.warning("File '%s' (logical_name '%s') is not valid JSON. Not loading its content.", file_path, logical_name)
						
			elif logical_name.lower().startswith("csv"): # By convention, csv_0, etc.
				# For CSVs, we might just store the path, or load if needed by a specific test logic.
				# For now, store the path and let tests decide if they need to parse it via FileIOToolbox.
				# If CSV content needs to be directly referenceable like JSON, this needs expansion.
				self.loaded_test_files[logical_name] = file_path # Store path for CSVs, could be parsed on demand
				log.info("Stored path for CSV '%s' ('%s') into self.loaded_test_files['%s']", file_path, logical_name, logical_name)

			elif logical_name.lower().startswith("py"): # By convention, py_0, etc.
				# For Python files, we need to extract the functions/methods from the file
				# and store it in self.loaded_test_files[logical_name]
				py_components = f_io.extract_python_components(file_path)
				if py_components is not None:
					try:
						self.loaded_test_files[logical_name] = {}
						self.loaded_test_files[logical_name]["python_components"] = py_components
						log.info("Stored python components for Python file '%s' ('%s') into self.loaded_test_files['%s']", file_path, logical_name, logical_name)
					except Exception as e:
						log.error("Failed to store python components for Python file '%s' ('%s'): %s", file_path, logical_name, e)
						return False
			# Other file types can be added here if their content needs to be pre-loaded/parsed.
			else: # For other keys, just store the path.
				self.loaded_test_files[logical_name] = file_path
				log.info("Stored path for file '%s' ('%s') into self.loaded_test_files['%s']", file_path, logical_name, logical_name)
		
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
		self.prepared_functions = {} # Clear previous
		self.prepared_class_instances = {} # Clear previous
		base_repo_dir = Path(self.test_folder_path).parent.parent.parent # Assuming tests are in REPO_ROOT/TYPE/tests/script_tests/
		log.debug("Base repo dir: %s", base_repo_dir)

		for func_id_str in func_identifiers:
			log.info("Preparing function: %s", func_id_str)
			parts = func_id_str.split('.')
			func_data = {**_FUNC_DICT} # Create a new dict instance
			file_name_part = parts[0]
			relative_file_path = ""
			target_file_path_abs = None
			# Determine script type and path
			# This logic might need to be more robust if filenames aren't perfectly unique across types
			if "_auditor" in file_name_part:
				relative_file_path = os.path.join("AUDITORS", f"{file_name_part}.py")
			elif "_drafter" in file_name_part:
				relative_file_path = os.path.join("DRAFTERS", f"{file_name_part}.py")
			elif "_toolbox" in file_name_part: # Covers general toolboxes like file_io_toolbox
				relative_file_path = os.path.join("TOOLBOXES", f"{file_name_part}.py")
			elif "_test" in file_name_part: # Covers all test scripts
				relative_file_path = "TESTS"
			else: # Default for other scripts, might need refinement
				# Try to find it based on metadata of the test plan perhaps?
				log.warning("Cannot determine script type for '%s' from name alone. Trying AUDITORS, DRAFTERS, then TOOLBOXES.", func_id_str)
				possible_paths = [
					base_repo_dir / "AUDITORS" / f"{file_name_part}.py",
					base_repo_dir / "DRAFTERS" / f"{file_name_part}.py",
					base_repo_dir / "TOOLBOXES" / f"{file_name_part}.py"
				]
				for p_path in possible_paths:
					if p_path.exists():
						target_file_path_abs = p_path
						break
				if not target_file_path_abs:
					log.error("Could not locate file for '%s' in standard directories.", func_id_str)
					return False
			log.debug("relative_file_path: %s", relative_file_path)

			if not target_file_path_abs: # If not found by fallback
				if relative_file_path == "TESTS":
					target_file_path_abs =  Path(self.test_folder_path) / f"{file_name_part}.py"
				else:
					target_file_path_abs = base_repo_dir / relative_file_path
			log.debug("target_file_path_abs: %s", target_file_path_abs)

			if not target_file_path_abs.exists():
				log.error("Target file %s for function ID %s does not exist.", target_file_path_abs, func_id_str)
				return False
			func_data["file_path"] = str(target_file_path_abs)
			# Extract AST components
			py_components = f_io.extract_python_components(str(target_file_path_abs))
			if py_components is None:
				log.error("Could not extract Python components from %s", target_file_path_abs)
				return False

			if len(parts) == 2: # script_file.function_in_script
				script_func_name = parts[1]
				found_node = False
				for node in py_components["functions"]:
					if node.name == script_func_name:
						func_data["function_node"] = node
						found_node = True
						break
				if not found_node:
					log.error("Function node '%s' not found in %s", script_func_name, target_file_path_abs)
					return False
				try:
					func_data["callable_func"] = f_io.prepare_ast_script_function(func_data["function_node"], func_data["file_path"])
				except Exception as e:
					log.error("Failed to prepare script function '%s': %s", func_id_str, e)
					return False

			elif len(parts) == 3: # toolbox_file.class_name.function_in_class
				# file_name_part is parts[0]
				class_name_part = parts[1]
				method_name_part = parts[2]
				if class_name_part in self.prepared_class_instances.keys():
					func_data["class_node"] = self.prepared_class_instances[class_name_part]["class_node"]
					func_data["instance"] = self.prepared_class_instances[class_name_part]["instance"]
				else:
					found_class_node = None
					for c_node in py_components["classes"]:
						if c_node.name.lower() == class_name_part.lower():
							found_class_node = c_node
							self.prepared_class_instances[class_name_part] = {}
							self.prepared_class_instances[class_name_part]["class_node"] = found_class_node
							self.prepared_class_instances[class_name_part]["instance"] = None
							func_data["class_node"] = found_class_node
							break
				if not found_class_node: 
					log.error("Class node '%s' not found in %s", class_name_part, target_file_path_abs); return False
				log.debug("Found class node: %s", func_data["class_node"])
				found_method_node = None
				
				# Methods can be defined directly in class or be part of ast.FunctionDef list if not properly nested by parser
				# The f_io.extract_python_components returns functions at all levels. Need to check parentage or assume flat list for now.
				# For simplicity, check FunctionDef nodes within the class AST node directly.
				for node in found_class_node.body: # Iterate through items in class body
					if isinstance(node, inspect.ast.FunctionDef) and node.name == method_name_part:
						found_method_node = node
						break
				if not found_method_node: # Fallback: check all functions if not found in class body (less accurate)
					for f_node in py_components["functions"]: # This might pick up non-class functions if names collide
						if f_node.name == method_name_part: # TODO: Check f_node is child of class_node
							log.warning("Method '%s' found globally, not nested in AST for class '%s'. Assuming it's the correct one.", method_name_part, class_name_part)
							found_method_node = f_node
							break
				
				if not found_method_node:
					log.error("Method node '%s' not found in class '%s' in %s", method_name_part, class_name_part, target_file_path_abs)
					return False
				func_data["function_node"] = found_method_node # This is ast.FunctionDef for the method

				# Get instance arguments for this specific class
				instance_kwargs_dict = {}
				target_class_full_id = f"{file_name_part}.{class_name_part}" # e.g., "my_toolbox.MyClass"
				for class_arg_spec in class_instance_args_list:
					if class_arg_spec.get("class") == target_class_full_id:
						raw_instance_args = class_arg_spec.get("instance_args", {})
						# Resolve these instance_args like other parameters
						resolved_init_kwargs = self._resolve_parameters(raw_instance_args)
						instance_kwargs_dict = resolved_init_kwargs # Assuming all are kwargs for now
						break
				try:
					log.debug("Preparing class method: %s", func_id_str)
					if self.prepared_class_instances[class_name_part]["instance"] is not None:
						log.debug("Reusing prepared class instance for %s", func_id_str)
						func_data["instance"] = self.prepared_class_instances[class_name_part]["instance"]
						func_data["callable_func"] = f_io.prepare_ast_class_method_for_instance(
							func_data["instance"],
							func_data["function_node"].name
						)
					else:
						log.debug("Preparing new class instance for %s", func_id_str)
						func_data["callable_func"], func_data["instance"] = f_io.prepare_ast_class_method(
							func_data["class_node"], 
							func_data["function_node"], 
							func_data["file_path"],
							instance_kwargs=instance_kwargs_dict
						)
						self.prepared_class_instances[class_name_part]["instance"] = func_data["instance"]
					log.debug("Completed preparation of class method: %s", func_data["callable_func"])
				except Exception as e:
					log.error("Failed to prepare class method '%s': %s", func_id_str, e)
					return False
			else:
				log.error("Invalid function identifier format: %s", func_id_str)
				return False
			
			self.prepared_functions[func_id_str] = func_data
			log.info("Successfully prepared function/method: %s", func_id_str)
			
			# Create a tracer for all scripts with functions evoked during the testing
			if file_name_part not in self.target_tracer_dict.keys():
				self.target_tracer_dict[file_name_part] = system_trace_toolbox.SystemTraceToolbox(
				target_script_path= Path(__file__).parent / Path(f"{file_name_part}.py"),
				capture_event_callback=self._capture_timeline_event
				)
		
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
