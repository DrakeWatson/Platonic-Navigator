You are tasked with generating test logic markdown files for a Python testing infrastructure. Adhere strictly to the capabilities and limitations of this framework when defining test_steps_order, parameter sources, return value capturing, and validation methods.
Core Principles for Test Step Generation:

    Sequential Execution: Steps within "test_steps_order" are executed in the order they appear.
    Explicit Data Flow: Data (parameters, return values) must be explicitly passed or captured. The framework cannot access internal variables of a function unless they are returned.
    Valid Sources: Parameters for functions and values for validation must originate from:
        Hardcoded literals (strings, numbers, booleans, null).
        Values from files listed in the test's "files" map (e.g., "json_0.data.key").
        Return values captured from previous steps using "return_pointers" (e.g., "return_X").
        Absolute file paths resolved from the test's "files" map (e.g., parameter value is "input.json").
    No Intermediate State Access: You cannot validate or use the internal state of a function (e.g., local variables) that is not explicitly returned.
    Atomic Operations: Each function call in "test_steps_order" is distinct. Side effects on internal class states are possible if the same instance is used across steps, but direct inspection of that state (other than through method calls that return values) is not built into the validation keywords.

Defining Test Steps: test_steps_order

Each item in the "test_steps_order" list is a dictionary representing a function call with the following keys:

    "function" (String): Required. The identifier of the function/method to call.
        Format: "module_name.function_name" for script functions (e.g., "my_script.calculate_value").
        Format: "module_name.ClassName.method_name" for class methods (e.g., "my_toolbox.MyClass.process_data").
        Ensure the module_name (and ClassName if applicable) matches how it's defined in the test case's top-level "functions" list and, for classes, in "class_instance_args".

    "params" (Object): Optional. A dictionary where keys are parameter names and values are their sources.
        Hardcoded Values:
            Strings: "a string value"
            Integers: "42" (will be resolved to int 42)
            Floats: "3.14" (will be resolved to float 3.14)
            Booleans: "true", "false" (will be resolved to True/False)
            None/Null: null or "null" or "none" (will be resolved to None)
            Literal Dot-Paths: If a string parameter is a dot-separated path but should not be parsed (e.g., you are testing a function that parses such paths), prefix it with "!STR_LITERAL!" (e.g., "!STR_LITERAL!some.literal.path").
        Values from Loaded Files:
            Reference content from files defined in the test's "files" map (e.g., {"json_0": "data.json"}).
            Syntax: "json_0.path.to.value", "json_0.array_key.0.name".
            Only files specified with logical names like "json_X" are guaranteed to have their content parsed and accessible this way. Other files might only provide paths.
        Values from Previous Step's Return:
            Syntax: "return_my_value", where "my_value" was defined in a previous step's "return_pointers".
        File Paths:
            To pass the path to a test file (from the "files" map), use its logical name (e.g., "json_0") or its filename (e.g., "actual_data.json"). This will be resolved to the absolute path of the file in the test directory.
        Nested Structures: Parameters can be complex objects or lists, with their inner values also resolved using these rules:
        JSON

        "params": {
            "config_object": {
                "setting1": "json_0.settings.value1",
                "mode": "return_previous_mode",
                "threshold": 42
            }
        }

    "return_pointers" (Array of Strings): Optional. A list of strings used as keys to store the return value(s) of the current function call.
        Example: ["result_id", "status_code"]
        If the function returns a single value, it's stored under the first pointer.
        If the function returns a tuple, values are assigned to pointers in order.
        These stored values can be used by subsequent steps or by the final "expected_return_value_and_order" validation.
        Crucial: If a function's output is needed later, it must be captured here.

Defining Validation (Outside test_steps_order, at the test definition level)

Validation occurs after all steps in "test_steps_order" have completed (for unit tests, this is typically after one primary call; for integration/full tests, after all sequential calls).

    "expected_return_value_and_order" (Object): Optional. Validates values captured by "return_pointers".
        Keys are the return_pointer names. Values are objects specifying the expected value source.
        The value source (e.g., hardcoded_var_value, a JSON path like "json_1.expected.output") is resolved similarly to function parameters.
        Examples:
		"expected_return_value_and_order": {
			"result_id": {"string": "expected_id_123"},
			"status_code": {"string": "json_1.expected_status"} 
		}
		"expected_return_value_and_order": {
			"resolved_params": { // This is the return_pointer name
				"dict": {        // This 'dict' indicates the expected type
					"string_val": "test_string",
					"int_val": 42,
					"nested_value": "json_1.data.nested.value" // This will be resolved
				}
			}
		}

    "expected_exception" (String): Optional. The class name of an exception that is expected to be raised during the execution of any step in "test_steps_order".
        Example: "ValueError"
        If an exception is listed here, the test passes if and only if an exception of this exact type is raised and not caught by the test steps themselves. If no exception or a different exception is raised, the test fails.

    "expected_file_content" (Array of Strings): Optional. Validates the content of files after all steps have run. Each string is a check: "file_reference:OPERATOR:operand_reference".
        file_reference: A file key (e.g., "json_0", "py_0", "csv_0", "txt_0") from the test's "files" map. This file's content is the subject of the check.
        OPERATOR:
            "IS": Content of file_reference must be identical to the content of operand_reference (which must also be a file reference).
            "HAS": Content of file_reference must contain the string resolved from operand_reference.
            "EXCLUDES": Content of file_reference must not contain the string resolved from operand_reference.
        operand_reference: Can be a file reference (for "IS") or a string literal, a JSON path (e.g., "json_1.expected_substring"), or a return pointer (e.g., "return_expected_text") for "HAS"/"EXCLUDES". These are resolved like function parameters.
        Example: ["txt_0:HAS:csv_0.expected_val", "json_0:IS:json_1"]

Key Limitations to Respect:

    No Direct Internal Inspection: You cannot check the value of a variable local to a function being tested unless that function returns it and it's captured via "return_pointers".
    No Mocking/Patching via Keywords: The framework does not have built-in keywords in the JSON test definition for mocking objects or patching methods. If mocking is needed, it must be a feature of the Python function being called (e.g., the function itself accepts a mock object as a parameter).
    Sequential Function Calls Only: For integration or full tests, ensure that "test_steps_order" lists at least two consecutive function calls as per test_struct.json rules.
    Return Value Scope: Values captured by "return_pointers" are available for the remainder of the current test definition's execution (i.e., subsequent steps in test_steps_order or the final validation phase). They do not persist across different test definitions in the "tests" array.

Suggested Thought Process for Generating a Test:

    Goal: What specific behavior or outcome of the target function(s) are you trying to verify?
    Function(s) Under Test: Identify the primary function(s) and any helper/sequential functions involved.
    Inputs:
        What parameters do these functions need?
        Where will these parameter values come from (hardcoded, a test file, output of a previous function call)?
    Execution Flow (test_steps_order):
        List the function calls in sequence.
        For each call, define its "function" identifier.
        Define its "params", resolving each parameter to a valid source.
        If a function's output is needed for a later step or final validation, add its name to "return_pointers".
    Outputs & Validation:
        What are the key outputs to validate? (Return values, side effects like file modifications, expected exceptions).
        How will they be validated?
            "expected_return_value_and_order" for function returns.
            "expected_exception" if an error is the correct outcome.
            "expected_file_content" for validating files created/modified by the test.
    File Dependencies: List all necessary input/comparison files in the test's top-level "files" map, giving them logical names (e.g., "json_0", "csv_0").

By following these guidelines, the generated test steps will align with the capabilities of the test_toolbox.py infrastructure.

CONTEXT FILES PROVIDED:

    [TARGET SCRIPT]: The Python script the test plan is validating.

    [TEST PLAN]: The test plan defining each test case and its tests for the [TARGET SCRIPT] script.

    [TEST CASE]: The specific test case entry in test_plan.json.

Your job is to create a file for each individual test defined in the test plan for the selected test case. 

For each test of the test case you will create a "[TEST CASE]_[TEST NAME]_logic.md" markdown file inside the SCRIPT_TYPE/tests/[TARGET SCRIPT]/ folder of this repository. (DO NOT CREATE ANY NEW FOLDERS, ALL FOLDERS ARE ALREADY CREATED FOR YOU.)

Inside each file you create you will define clearly and explicitly step by step the logic required to complete that particular test. You must ensure all details and information that is necessary to correctly fill out the test_steps_order field of each test within a test case file that will be created after this.

Your purpose is to ensure that each test's logic correctly takes into account the testing infrastructure's capabilities and limitations. Ensure that the logic defined for each test is actually executable and implementable within the current testing infrastructure as it is described to you.

If there is a validation test that cannot be performed correctly within the current testing infrastructure, DO NOT TRY TO MAKE IT WORK. Simply mark in that test's .md file you create that the current infrastructure doesn't support validating that kind of test.

YOU WILL NOT BE CREATING ANY SCRIPTS OR JSON FILES. YOU ARE ONLY FOCUSED ON GENERATING VALID STEP BY STEP OPERATIONS FOR THE SINGLE TEST OF EACH NEW FILE YOU CREATE.

The markdown file should conform exactly to the template provided below. NO ADDITIONAL FIELDS OR SECTIONS SHOULD BE INCLUDED. The file should be simple, straight forward, and focused entirely on the working execution of the series of functions.

STARTTEMPLATE
# function call order
    function_0
        Input parameter values
        Return pointers
    function_1
    .
    .
    .
    function_n

# validation method
brief description of how the validation will be performed (if any).

ENDTEMPLATE

USER TO DEFINE BELOW:
[TARGET SCRIPT]
[TEST PLAN]
[TEST CASE]