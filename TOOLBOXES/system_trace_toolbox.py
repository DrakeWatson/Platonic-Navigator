#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
System Trace Toolbox
====================
Provides a modular system for tracing Python script execution line-by-line,
leveraging an LLM-generated context map for rich, descriptive timeline logging.
"""

import os
import sys
import inspect
import json
import hashlib
import ast
import concurrent.futures
from datetime import datetime
from pathlib import Path

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from TOOLBOXES import logging_toolbox
    from TOOLBOXES import file_io_toolbox
    from TOOLBOXES import llm_toolbox
except ImportError as e:
    print(f"Error importing a core toolbox: {e}")
    sys.exit(1)

log = logging_toolbox.LoggingToolbox()

class Tracer:
    """A context manager to trace execution within a 'with' block."""
    def __init__(self, context_maps: dict, capture_event_callback: callable, trace_targets: set):
        self.context_maps = context_maps
        self.capture_event_callback = capture_event_callback
        self.trace_targets = trace_targets
        self.previous_trace_function = None

    def __enter__(self):
        self.previous_trace_function = sys.gettrace()
        sys.settrace(self._trace_dispatcher)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.settrace(self.previous_trace_function)

    def _trace_dispatcher(self, frame, event, arg):
        current_file = os.path.abspath(frame.f_code.co_filename)

        # 1. Check if the file being executed is one of our targets. If not, ignore.
        if current_file not in self.trace_targets:
            # If there was another tracer running before us, we should call it.
            if self.previous_trace_function:
                 return self.previous_trace_function(frame, event, arg)
            return self._trace_dispatcher

        # 2. Get the correct context map for the current file
        context_map = self.context_maps.get(current_file)
        if not context_map:
            # We are supposed to trace this file, but have no map. Continue tracing it but without context.
            return self._trace_dispatcher

        func_name = frame.f_code.co_name
        line_no = frame.f_lineno
        file_name = Path(current_file).stem # Use stem to get name without extension

        if event == 'line':
            line_key = str(line_no)
            if context_map.get(func_name) and context_map[func_name].get(line_key):
                context_info = context_map[func_name][line_key]
                try:
                    local_vars = frame.f_locals.copy()
                    formatted_context = context_info["context"].format(**local_vars)
                except (KeyError, IndexError):
                    formatted_context = context_info["context"]

                self.capture_event_callback(
                    file_name=file_name,
                    function_name=func_name,
                    variables_dict=frame.f_locals,
                    line_num=f"line_{line_no}",
                    entry_context=formatted_context,
                    depth_of_detail=context_info["detail"],
                    code_str=context_info["code_str"]
                )
        elif event == 'exception':
            exc_type, exc_value, _ = arg
            self.capture_event_callback(
                file_name=file_name,
                function_name=func_name,
                variables_dict={"exception": str(exc_value), "type": exc_type.__name__, "line": line_no},
                line_num=f"exception_at_line_{line_no}",
                entry_context=f"An exception occurred in {func_name}",
                depth_of_detail=1,
                code_str=""
            )
        return self._trace_dispatcher

class SystemTraceToolbox:
    """Toolbox for generating and managing system traces."""
    def __init__(self, target_script_path: str, capture_event_callback: callable):
        self.initial_target_script = os.path.abspath(target_script_path)
        self.capture_event_callback = capture_event_callback
        self.f_io = file_io_toolbox.FileIOToolbox()
        self.llm = llm_toolbox.LLMToolbox()

        self.trace_targets = {self.initial_target_script}
        self.context_maps = {} # Keyed by absolute script path

        # Load the context map for the initial script
        self.context_maps[self.initial_target_script] = self._manage_context_map(self.initial_target_script)

    def add_trace_targets(self, script_paths: list):
        """Adds new script paths to the trace list and ensures their context maps are loaded."""
        for path in script_paths:
            abs_path = os.path.abspath(path)
            self.trace_targets.add(abs_path)
            # If we don't have a map for this new target, load or generate it
            if abs_path not in self.context_maps:
                log.info(f"Loading/generating context map for new target: {os.path.basename(abs_path)}")
                self.context_maps[abs_path] = self._manage_context_map(abs_path)

    def clear_trace_targets(self):
        """Resets trace targets to only the initial script."""
        self.trace_targets = {self.initial_target_script}

    def _get_script_hash(self, script_path: str) -> str:
        """Calculates the SHA256 hash of the target script's content."""
        hasher = hashlib.sha256()
        try:
            with open(script_path, 'rb') as f:
                buf = f.read()
                hasher.update(buf)
            return hasher.hexdigest()
        except FileNotFoundError:
            log.error(f"Target script for hashing not found: {script_path}")
            return ""

    def _chunk_script_by_function(self, script_path: str) -> dict:
        """Parses the script and returns a dict of functions with their source code."""
        script_content = self.f_io.read_file(script_path)
        if not script_content:
            return {}
        
        log.debug(f"Chunking {script_path}")
        tree = ast.parse(script_content)
        functions = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                source_segment = ast.get_source_segment(script_content, node)
                if source_segment:
                    source_lines_list = source_segment.splitlines()
                    code_dict = {node.lineno + i: line for i, line in enumerate(source_lines_list)}
                    functions[node.name] = {"code": code_dict, "start_line": node.lineno}
        return functions

    def _generate_context_map_worker(self, task: dict) -> dict:
        """Worker function for parallel LLM calls."""
        func_name = task['func_name']
        log.debug(f"Thread worker starting context generation for function: {func_name}")
        try:
            response_text, _ = self.llm.call_gemini(
                gemini_prompt=task['prompt'],
                force_json=True,
                json_schema=task['json_schema']
            )
            if response_text:
                return {'func_name': func_name, 'result': json.loads(response_text)}
            return {'func_name': func_name, 'result': None}
        except Exception as e:
            log.error(f"Error generating context for '{func_name}': {e}")
            return {'func_name': func_name, 'result': None}

    def _generate_context_map(self, script_path: str) -> dict:
        """Uses an LLM to generate the timeline context map in parallel chunks."""
        log.info(f"Generating new timeline context map for {os.path.basename(script_path)}...")
        
        script_chunks = self._chunk_script_by_function(script_path)
        # ... (The rest of this function's logic remains the same, no changes needed here) ...
        if not script_chunks:
            log.error("Could not find any functions to analyze in the script.")
            return {}

        tasks = []
        for func_name, chunk_data in script_chunks.items():
            # ** UPDATED Prompt to ask for an array of objects **
            prompt = f"""
            Objective: Analyze the following Python function chunk (ordered and numbered lines of code in a python dictionary) to generate a JSON object containing a list of 'code line context entries'.

            For each line of code in the chunk provided you will create a single entry which will contain the line number, a context string, a verbosity integer (0-4), and a code string which is just the line of code itself. The intention is to make each programmatic step easily reviewable by an LLM or human after executing a test plan built for the script the chunk provided to you came from.

            The context string you generate for each entry is the most important piece here. It will be the descriptive sentence(s) which are shown in a debug timeline of code that has just executed. The context string should be a brief explanation of what that line of code is doing. The context string content should correspond to the verbosity of the timeline entry.
            
            Each entry you create will be assigned a verbosity level between '0' (high detail) and '4' (low detail). The verbosity is used to help the user zoom 'in/out' of the context for any code flow. Below is an explanation of each verbosity level with brief examples of the type of context you would add for that line of code.

            [4] 'EXECUTION OVERVIEW' - Starting a test plan / case / test. Ending a test plan / case / test. Examples: 'Test plan started execution', 'Test case completed execution', 'Entire test plan completed'

            [3] 'EXECUTION STEPS' - Entry/exit point of an individual function. Examples: 'Executing function X', 'Returning from function X', 'Exited function X due to exception'

            [2] 'EXECUTION STEP DETAILS' - Functional block inside a function. Examples: 'Loading variables from file', 'Organizing output data into correct format', 'Checking for valid range.'

            [1] 'EXECUTION SUB-STEP DETAILS' - Details inside a functional block. Examples: 'Looping over entries in container', 'Updating list based on previous return value', 'Checking if merging file contents is valid'

            [0] 'EXECUTION CODE PIECE' - Exact step taken within a functional block. If any line of code does not meet the criteria for 1-4, it should be given '0'. Examples: "Opening `{{file_path}}` with read and modify permission", "Logging variables `{{a}}` and `{{b}}`", "Adding 1 to `{{counter_var}}`"

            Your actual context strings should be longer than the examples above. You can be as verbose as is needed to properly express the line of code you are creating the context for. Imagine that you are going to debug this specific line of code; what explanation of that line of code would you need to know to start debugging effectively? That is the perspective you should have in order to 'properly express' the context.

            Do not create entries for comments or blank lines.

            **VARIABLE FORMAT IN CONTEXT STRING:**
            - When referencing any variable from the code within your context string use this exact format: `{{variable_name}}`.

            For each entry you will need to capture the 'code_str' which is the line of code referenced for any context entry you create. You don't need to include the exact implementation since some code is going to be formatted weird or have comments or just be too long; but ensure that the code_str reasonably indicates the actual line of code being executed and referenced within the context string.

            **OUTPUT STRUCTURE:**
            Your response must be a JSON object with a single key "timeline_entries", which is an array of objects.
            Example:
            {{
              "timeline_entries": [
                {{
                  "line_number": 152,
                  "context": "Initializing result dictionary for test case '{{{{tc_name}}}}'.",
                  "code_str": "_T_RESULT_DICT = {{\"name\":\"\", \"status\":\"\", \"reason\":\"\"}}",
                  "detail": 2
                }},
                {{
                  "line_number": 155,
                  "context": "Processing test definition at index {{{{index}}}}.",
                  "code_str": "for index, test_definition in enumerate(current_tc_data.get(\"tests\", [])):",
                  "detail": 1
                }}
              ]
            }}

            **Function Chunk from '{func_name}':**
            ---
            {chunk_data['code']}
            ---
            """
            
            # ** CORRECTED JSON Schema to match the new array-based structure **
            json_schema = {
                "type": "OBJECT",
                "properties": {
                    "timeline_entries": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "line_number": {"type": "INTEGER"},
                                "context": {"type": "STRING"},
                                "code_str": {"type": "STRING"},
                                "detail": {"type": "INTEGER"}
                            },
                            "required": ["line_number", "context", "detail", "code_str"]
                        }
                    }
                },
                "required": ["timeline_entries"]
            }
            
            tasks.append({
                'func_name': func_name,
                'prompt': prompt,
                'json_schema': json_schema
            })

        final_context_map = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_func = {executor.submit(self._generate_context_map_worker, task): task['func_name'] for task in tasks}
            for future in concurrent.futures.as_completed(future_to_func):
                result_data = future.result()
                if result_data and result_data['result'] and 'timeline_entries' in result_data['result']:
                    func_name = result_data['func_name']
                    line_map = { str(entry['line_number']): { "context": entry['context'], "detail": entry['detail'], "code_str": entry['code_str'], } for entry in result_data['result']['timeline_entries'] }
                    final_context_map[func_name] = line_map
        
        log.info(f"Finished generating context map with entries for {len(final_context_map)} functions.")
        return final_context_map

    def _manage_context_map(self, script_path: str) -> dict:
        """Loads the context map from cache or generates a new one if the script has changed."""
        script_dir = os.path.dirname(script_path)
        cache_dir = os.path.join(script_dir, ".trace_cache")
        map_filename = f"{os.path.basename(script_path)}.map.json"
        map_path = os.path.join(cache_dir, map_filename)

        current_hash = self._get_script_hash(script_path)
        if not current_hash:
            return {}

        if self.f_io.file_exists(map_path):
            map_data = self.f_io.parse_json_file(map_path)
            if map_data and map_data.get("metadata", {}).get("source_hash") == current_hash:
                log.info(f"Loading timeline context map for {os.path.basename(script_path)} from cache.")
                return map_data.get("context_map", {})

        new_map = self._generate_context_map(script_path)
        if new_map:
            map_data_to_save = {
                "metadata": {
                    "source_script": os.path.basename(script_path),
                    "source_hash": current_hash,
                    "last_updated": datetime.now().isoformat()
                },
                "context_map": new_map
            }
            self.f_io.create_directory(cache_dir)
            self.f_io.write_json(map_path, map_data_to_save)
            return new_map
        
        return {}

    def start_trace(self) -> Tracer:
        """Returns a Tracer context manager instance to begin tracing."""
        log.info(f"Starting system trace for {', '.join([os.path.basename(p) for p in self.trace_targets])}")

        return Tracer(
            context_maps=self.context_maps,
            capture_event_callback=self.capture_event_callback,
            trace_targets=self.trace_targets
        )

def main():
    """Demonstration of the SystemTraceToolbox."""
    log.info("system_trace_toolbox.py main() started.")
    
    def demo_capture_callback(**kwargs):
        print(f"[TRACE EVENT CAPTURED]: Level {kwargs.get('depth_of_detail')} | {kwargs.get('function_name')}:{kwargs.get('line_num')} -> {kwargs.get('entry_context')}")

    target_script = os.path.join(project_root, "TOOLBOXES", "test_toolbox.py")
    
    try:
        tracer_toolbox = SystemTraceToolbox(
            target_script_path=target_script,
            capture_event_callback=demo_capture_callback
        )
        log.info("Tracer toolbox initialized. Context map has been loaded or generated.")
        
    except Exception as e:
        log.error(f"Failed to initialize or run SystemTraceToolbox: {e}")

    log.info("system_trace_toolbox.py main() finished.")

if __name__ == "__main__":
    main()
