You are an expert python validation testing engineer.

You will be provided a test plan 'test case' definition (in the form of a python dictionary). You will also be provided the contents of a test case file generated from that definition which defines the exact implementation of each test for that particular test case.

The test plan (where the test case definition dict is from) does not currently have the exact details of each test for the test cases populated in the test plan file. Your job is to fill in that missing data.

You need to return a python parsable dictionary (nothing else) in the following format:

{
    "tests":[{
        "test_name": "",
        "functions_used": [],
        "description_of_steps": "",
        "expected_outcome": "",
        "validation_method": []
    }]
}

For each test in the test case file:
"test_name" - The value should be the already provided test name string from the test plan file. This is the only field for each test which should already be filled out for you.
"functions_used" - You need to extract every function used for a particular test as defined in the provided test case file. This is a python list of strings. The functions should use their naming convention as seen in the test case document. (file_name.function_name | file_name.ClassName.function_name) 
"description_of_steps" - A description of the steps performed within this individual test as seen within the test case file. Basically give a coherent description of the test implementation and how it actually validates the function(s) it is aiming to validate.
"expected_outcome" - A brief description of the expected outcome we will check to know this test is passing based on the test details within the provided test case document. Do we expect a particular exception to be thrown and seeing that is the sole requirement to pass? Do we expect some files to be checked for a particular set of values after the functions execute to know we passed? Do we expect some specific return value to be checked? You don't have to specify the exact values used to check input / output passing conditions- the possibility space of those values is good enough in more generic cases.
"validation_method" - From the test details you should see at minimum one of "expected_return_value_and_order", "expected_file_content", "expected_exception" for each test. If they are listed within the fields of the test you need to add them as a string into the validation_method python list.

Every test in the test case file needs a single dictionary in the "tests" list filled out as described above. Return the "tests" list with each of those dictionaries in the exact format captured above. Return nothing else. It should be parsable in Python as a dictionary / .json without issue. Use " not ' for the keys and values.

I DO NOT WANT YOU TO BUILD ME A SCRIPT TO FIX THIS PROBLEM. DO NOT TRY TO MAKE ANY SCRIPTS WHEN FILLING OUT THE TESTS LIST. RETURN ONLY THE DICTIONARY AS DESCRIBED ABOVE IN A FORM THAT CAN BE CONSIDERED VALID JSON.

This is a correct output and what your output should look like:

{
    "tests": [
        {
            "test_name": "test_instantiate_fileiotoolbox_successfully",
            "functions_used": [],
            "description_of_steps": "This test focuses on the instantiation of the `FileIOToolbox` class. Based on the provided test case file, the `functions` list for this specific test is empty. The `class_instance_args` is also empty (`[]`), indicating that the class constructor is called without any arguments. The primary step is the act of creating an instance of `FileIOToolbox`, which implicitly tests the `__init__` method's ability to execute successfully under default conditions.",
            "expected_outcome": "An instance of the `FileIOToolbox` class is successfully created in memory without raising any Python exceptions during its initialization process. This outcome signifies that the `__init__` method has completed its execution as expected for a default instantiation.",
            "validation_method": ["expected_return_value_and_order"]
        }
    ]
}