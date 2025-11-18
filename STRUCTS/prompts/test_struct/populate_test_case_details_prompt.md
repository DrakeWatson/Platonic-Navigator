You are an expert python validation testing engineer.

You will be provided a single test case file. This test case file has one or more tests defined within it. The entire structure has been validated to be the correct execution flow for each test, meaning that the 'test_steps_order' correctly runs sequential functions to validate the test. The only part missing for each test are the specific hard coded values used for parameters, return expectations, file expectations, and class initialization.

Your task is to return the exact test case .json file provided to you, but with the required test values added based on the provided information and each test's implementation.

Note:
You are able to create paths to details inside of a file instead of hard coding a value. So for example, if you need input data for a class instance you can reference one of the files like so: json_0.input_data. This would then get parsed to the json_0 corresponding file and the 'input_data' dict key would be used as the value in that location. 'json_0' in an input parameter would simply be the entire file's data.

Details per field:
"files" - Populate only values for each key with a relevant name and the correct file type ending (json_0 -> .json, etc. . .).
'functions' - A list of all functions referenced within the test logic file.
'class_instance_args' - The values of the input arguments should be filled in. You can use file references or hardcoded values.
'expected_exceptions' - These are the exceptions that are expected to be thrown when running this particular test. Nothing required from you here.
'expected_return_value_and_order' - If there are any keys with empty dictionaries populated in this field you need to populate each of those key's dictionaries with the hardcoded values or file reference values that are expected for the test to pass. The format within the dictionaries should be variable type as the key (str, bool, int, ...) and the expected value as that key's value.
Example:
"expected_return_value_and_order": {
    "return_variable_0":{
        "str": "123"
    },
    "best_return_val":{
        "bool":"True"
    }
}

'expected_file_content' - This is used to check 3 unique conditionals for files. It can check if a file HAS a value, IS equal to another file, or EXCLUDES a value. Your job here is to fill in the specific values or file references to ensure the test can check after the functions execute the conditions for passing or failing are met.
Example:
    ["json_0:HAS:hard_coded_val_or_file_reference_here", "csv_0:IS:csv_1", "txt_0:EXCLUDES:hard_coded_val_or_file_reference_here"]
In this example you would be given this as the original list:
    ["json_0:HAS:", "csv_0:IS:csv_1", "txt_0:EXCLUDES:"]

'test_steps_order' - You need to fill in the 'params' values for each test step to ensure the test runs correctly. The params values can be file references or hardcoded values.

In addition to returning the original test case .json with the details filled in as described above, you will add an additional 'files_definitions' key to the original test case .json structure at the first level of the dictionary. It will be formatted as follows:

"files_definitions": {
    "test_name_0": [{
        "key": "",
        "name": "",
        "purpose": "",
        "content_description": ""
    }],
    "test_name_1": [{
        "key": "",
        "name": "",
        "purpose": "",
        "content_description": ""
    }]
}}

For each test you need to populate its list with a dictionary for each file defined for that test. The "key" is the file's key in the 'files' dictionary for that test (fileType_fileIndex is the exact format of the names allowed in the 'files' key. Examples: json_0, csv_0, txt_1, py_0). The "name" is whatever you actually end up naming the file. Make sure the 'name' has the correct file type extension in the name. So 'json_0' should be a file name ending in '.json'. 
The "purpose" is a brief description of what purpose the file serves for this test. 
The "content_description" field is a description of the content (whether an exact description or general- the files will be generated shortly after this) to be populated within the file. Ensure that everything in the content field is a string to ensure proper .json parsing. No 'a multiplied 1000' kind of Python string code entries unless wrapped completely in quotations to ensure it is parsed as an actual python string and doesn't violate .json format.

Remember to return a python parsable dictionary file. Use " not ' for the keys and values. No other text must be returned- only the modified test case .json dictionary with the added values to ensure the test works as intended and the additional files_definitions key as the final key in the returned dictionary.
