You are an expert python validation testing engineer.

The test plan and test cases for a particular script have been finalized. We are in the third step of developing the implemented testing logic for a single test in one of the defined test cases.

Your objective is two fold:
1. Solidify the exact logical flow the testing infrastructure needs to execute some (or all) of the provided functions in order to perform the validation task defined in the test description.
2. Identify the pass/fail checking method(s) to be used once the test flow has completed. Some important clarifications about the three distinct checking methods:
	2a. Return value - Checks for an expected return value after full test flow has been performed. The return value checked can be from any of the functions executed during the test flow. If the description indicates a return value check will be needed, you only need to identify which function(s) return value(s) will be checked once the test flow has completed.
	2b. Expected Exception - Generally only used in 'expected_failure' and 'input_validation' subtype tests. If the expected exception is hit during the test flow it would be a 'pass' assuming all other checking requirements are also a pass. You just need to specify the exact exception(s) expected for a pass if the description indicates an expected exception will be used to validate the test.
	2c. File comparison - After a test flow has completed the test methodology can check files to determine pass/fail. Any number of files can be checked, but there is a limit on the kinds of operations that can be performed. "IS", "HAS", "EXCLUDES". "IS" will be used when you need to check that one file has the exact same contents as another file. "HAS" is used to check if a file has a string. "EXCLUDES" is used to check if a file does not have a string in it. If the description indicates file comparison is needed to validate the test you need to identify for each file required the type needed for that particular check. You need to ensure any file mentioned has it's type listed explicitly in the expression(s) you build for the file comparison check. Ensure that each sentence you create contains 'HAS', 'EXCLUDES', or 'IS' as required by the description. File types are restricted to: json, csv, txt, py (discouraged, but sometimes necessary), and md. Examples of the sentences you can populate if the description requires file comparison checking are listed in the .json format specified further down this prompt. You are not concerned with the exact values or data that will be populated in these files; only whether they will be needed or not to execute & validate the test correctly.

The following sections are appended to this prompt which you need to use to complete the requirements above:
Test Case Details - The name, type, and subtype of the test case the single test you are working on is a part of. Useful for determining validation requirements and expectations for the test.
Test Name - The name of the single test described by the test description.
Test Description - The logical description of the test you will use to generate the exact function flow and expected validation requirements.
Function(s) Tested Details - The full python implementation of one or more functions that will are required to be executed during this test so you have full clarity on their implementation details.
Functions Needed Details - A list of functions you may need to utilize to correctly generate the test function flow. In addition to the name of the functions it contains input parameters, function descriptions, and any return parameters.

You will be responding in a .json / python dictionary format. The exact .json structure to populate is as follows:
{
	"ordered_function_calls": ["script_name.function_name", "script_name.ClassName.function_name", "script_name.function_name", ...],
	"expected_exceptions": ["first_expected_exception", "second_expected_exception", ...],
	"file_comparison": ["Check if an input .json file HAS some string.", "A .md file is created that EXCLUDES some string.", "A test .csv file IS some reference .csv file with the data expected.", ...],
	"return_value": ["script_name.function_name.return_param_name", "script_name.ClassName.function_name.return_param_name", ...]
}

expected_exceptions, file_comparison, and return_value can be empty lists so long as at least one other validation method is not an empty list. ordered_function_calls cannot be empty.

Nothing else should be in your response besides the .json format above with those exact four keys and any values you populate in their lists.