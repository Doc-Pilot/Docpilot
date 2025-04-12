"""
FastAPI and Pydantic Parsing Logic
====================================

Functions specific to parsing FastAPI endpoints and Pydantic models using AST.
"""

import ast
import re
import os
import textwrap
from typing import Dict, Any, List, Optional

# Assuming logger is available from utils
# We might need to adjust this import based on final structure
# from ..utils.logging import core_logger
# For now, let's assume a logger is passed or handled differently
import logging
logger = logging.getLogger(__name__) # Use standard logging for now


# Helper to safely evaluate literal expressions
def _safe_literal_eval(node: ast.AST) -> Any:
    try:
        # Limit complexity to prevent potential DoS
        # This is a basic check; more robust libraries might exist
        # For demonstration, we keep it simple
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as e:
        logger.debug(f"_safe_literal_eval failed for node {ast.dump(node)}: {e}")
        try:
            # Fallback to unparsing if literal_eval fails
            return ast.unparse(node)
        except Exception as unparse_err:
            logger.error(f"ast.unparse failed after literal_eval failure: {unparse_err}")
            return "<Parse Error>"

def parse_fastapi_function(node: ast.FunctionDef, file_path: str, source_code: str, repo_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Parse a single function definition for FastAPI route info."""
    logger.debug(f"Parsing function '{node.name}' in {file_path}")
    route_decorator = None
    http_method = None
    route_path = None
    response_model_name = None
    request_model_name = None # ADDED: To store request body model name
    status_code = 200 # Default
    tags = []

    # Find FastAPI route decorators (e.g., @app.get, @router.post)
    for decorator in node.decorator_list:
        logger.debug(f"  Checking decorator: {ast.dump(decorator)}") # DEBUG LOG
        if isinstance(decorator, ast.Call):
            decorator_func_unparsed = ast.unparse(decorator.func)
            decorator_name = decorator_func_unparsed.lower()
            logger.debug(f"    Decorator is ast.Call. Unparsed func: '{decorator_func_unparsed}', Lowercase: '{decorator_name}'") # DEBUG LOG
            patterns = [".get", ".post", ".put", ".delete", ".patch", ".options", ".head", ".trace"]
            match_found = any(pattern in decorator_name for pattern in patterns)
            logger.debug(f"    Checking patterns {patterns} in '{decorator_name}'. Match found: {match_found}") # DEBUG LOG
            if match_found:
                method_match = re.search(r'\.(\w+)$', decorator_name)
                if method_match:
                    http_method = method_match.group(1).upper()
                    route_decorator = decorator
                    logger.debug(f"    Found route decorator '{decorator_name}' for function '{node.name}', Method: {http_method}") # DEBUG LOG
                    break
                else:
                    logger.debug(f"    Pattern matched but regex failed for '{decorator_name}'") # DEBUG LOG
        elif isinstance(decorator, ast.Attribute):
             decorator_unparsed = ast.unparse(decorator)
             decorator_name = decorator_unparsed.lower()
             logger.debug(f"    Decorator is ast.Attribute. Unparsed: '{decorator_unparsed}', Lowercase: '{decorator_name}'") # DEBUG LOG
             patterns = [".get", ".post", ".put", ".delete", ".patch", ".options", ".head", ".trace"]
             match_found = any(pattern in decorator_name for pattern in patterns)
             logger.debug(f"    Checking patterns {patterns} in '{decorator_name}'. Match found: {match_found}") # DEBUG LOG
             if match_found:
                method_match = re.search(r'\.(\w+)$', decorator_name)
                if method_match:
                    http_method = method_match.group(1).upper()
                    route_decorator = decorator
                    logger.debug(f"    Found route decorator '{decorator_name}' for function '{node.name}', Method: {http_method}") # DEBUG LOG
                    break
                else:
                    logger.debug(f"    Pattern matched but regex failed for '{decorator_name}'") # DEBUG LOG
        else:
             logger.debug(f"    Decorator is neither Call nor Attribute: {type(decorator)}") # DEBUG LOG

    if not route_decorator or not http_method:
        logger.debug(f"No valid FastAPI route decorator found for function '{node.name}'")
        return None # Not a FastAPI route function

    # Extract info from the decorator
    if isinstance(route_decorator, ast.Call):
        if route_decorator.args:
            route_path = _safe_literal_eval(route_decorator.args[0])
            logger.debug(f"Extracted route path: {route_path}")

        for keyword in route_decorator.keywords:
            if keyword.arg == 'response_model':
                response_model_name = ast.unparse(keyword.value)
                logger.debug(f"Extracted response_model: {response_model_name}")
            elif keyword.arg == 'status_code':
                status_code_val = _safe_literal_eval(keyword.value)
                if isinstance(status_code_val, int):
                    status_code = status_code_val
                elif isinstance(status_code_val, str) and "status." in status_code_val:
                     code_part = status_code_val.split('_')[-1]
                     if code_part.isdigit(): status_code = int(code_part)
                logger.debug(f"Extracted status_code: {status_code}")
            elif keyword.arg == 'tags' and isinstance(keyword.value, (ast.List, ast.Tuple)):
                tags = _safe_literal_eval(keyword.value)
                if not isinstance(tags, list):
                   tags = [ast.unparse(el) for el in keyword.value.elts]
                logger.debug(f"Extracted tags: {tags}")
    elif route_path is None:
         logger.debug(f"Could not determine route path for {node.name} in {file_path} from decorator {ast.unparse(route_decorator)}")
         if node.name.startswith(('get_', 'create_', 'update_', 'delete_')):
             route_path = f"/{node.name.split('_', 1)[-1]}" # Basic guess
             logger.debug(f"Guessed route path: {route_path}")
         else:
             logger.warning(f"Failed to determine route path for '{node.name}'")
             return None

    # Extract info from the function definition
    func_name = node.name
    docstring = ast.get_docstring(node) or ""
    summary = ""
    description = ""
    if docstring:
        lines = docstring.strip().split('\n', 1) # Split into first line and the rest
        summary = lines[0].strip()
        if len(lines) > 1:
            # Dedent the remaining description block
            description = textwrap.dedent(lines[1].strip()).strip()
        else:
            # If only one line, use it as summary only
            description = "" 
    
    if not summary:
        summary = func_name # Fallback to function name if no docstring/summary line
    logger.debug(f"Function '{node.name}': summary='{summary}'")

    start_line = node.lineno

    parameters = []
    request_body_param_info = None
    param_docs = _parse_docstring_params(docstring) # NEW helper call

    num_args = len(node.args.args)
    num_defaults = len(node.args.defaults)
    for i, arg in enumerate(node.args.args):
        param_name = arg.arg
        if param_name in ('self', 'cls'): continue
        logger.debug(f"Processing parameter '{param_name}'")

        param_type = "Any" # Default
        param_default = None
        param_source = "query" # Default
        is_request_body = False
        param_description = "" # TODO: Parse from docstring
        is_optional = False
        effective_param_type = "Any"

        if arg.annotation:
            param_type_str = ast.unparse(arg.annotation)
            param_type = param_type_str # Store the raw annotation string
            annotation_node = arg.annotation
            logger.debug(f"  Annotation found: {param_type_str}")

            # Handle Optional[Type] or Union[Type, None]
            if isinstance(annotation_node, ast.Subscript) and isinstance(annotation_node.value, ast.Name):
                 if annotation_node.value.id == 'Optional':
                     is_optional = True
                     inner_type_node = annotation_node.slice
                     effective_param_type = ast.unparse(inner_type_node)
                     logger.debug(f"  Detected Optional, effective type: {effective_param_type}")
                 elif annotation_node.value.id == 'Union':
                     if isinstance(annotation_node.slice, ast.Tuple):
                         types_in_union = [ast.unparse(t) for t in annotation_node.slice.elts]
                         if 'None' in types_in_union or 'NoneType' in types_in_union:
                             is_optional = True
                             non_none_types = [t for t in types_in_union if t not in ('None', 'NoneType')]
                             if len(non_none_types) == 1:
                                 effective_param_type = non_none_types[0]
                             else:
                                 effective_param_type = f"Union[{', '.join(non_none_types)}]"
                             logger.debug(f"  Detected Union with None, effective type: {effective_param_type}")
                     else: # Single type in Union?
                         effective_param_type = ast.unparse(annotation_node.slice)
                 else:
                    effective_param_type = param_type # No optional/union detected
            else:
                effective_param_type = param_type # No subscript

            # Check for Query, Path, Body, Header calls
            assign_node = None
            for parent_node in ast.walk(node):
                 if isinstance(parent_node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == param_name for t in parent_node.targets):
                     assign_node = parent_node
                     break
                 if isinstance(parent_node, ast.AnnAssign) and isinstance(parent_node.target, ast.Name) and parent_node.target.id == param_name:
                     assign_node = parent_node
                     break

            check_nodes = [annotation_node]
            default_value_node = None
            if isinstance(assign_node, ast.AnnAssign) and assign_node.value:
                default_value_node = assign_node.value
                check_nodes.append(assign_node.value)
            elif isinstance(assign_node, ast.Assign):
                default_value_node = assign_node.value
                check_nodes.append(assign_node.value)

            found_param_marker = False
            marker_description = ""
            for check_node in check_nodes:
                if isinstance(check_node, ast.Call) and isinstance(check_node.func, ast.Name):
                    param_func_name = check_node.func.id
                    marker_source_map = {'Path': 'path', 'Query': 'query', 'Body': 'body', 'Header': 'header'}
                    if param_func_name in marker_source_map:
                        param_source = marker_source_map[param_func_name]
                        is_request_body = (param_source == 'body')
                        found_param_marker = True
                        logger.debug(f"  Found marker: {param_func_name}, source: {param_source}")
                        # Extract details from the call
                        for kw in check_node.keywords:
                            if kw.arg == 'description': 
                                marker_desc_val = _safe_literal_eval(kw.value)
                                if isinstance(marker_desc_val, str): marker_description = marker_desc_val
                            if kw.arg == 'default': 
                                param_default = _safe_literal_eval(kw.value)
                        # Default can also be the first positional arg
                        if not param_default and check_node.args:
                            param_default = _safe_literal_eval(check_node.args[0])
                        logger.debug(f"  Marker details: default={param_default}, description='{marker_description}'")
                        break # Found marker

            # Extract default from function signature if not found elsewhere
            if param_default is None:
                arg_index_in_sig = next((idx for idx, sig_arg in enumerate(node.args.args) if sig_arg.arg == param_name), -1)
                if arg_index_in_sig != -1 and arg_index_in_sig >= num_args - num_defaults:
                    default_index = arg_index_in_sig - (num_args - num_defaults)
                    param_default = _safe_literal_eval(node.args.defaults[default_index])
                    logger.debug(f"  Default value from signature: {param_default}")

            is_required = param_default is None and not is_optional
            logger.debug(f"  Parameter '{param_name}': type={effective_param_type}, required={is_required}, optional={is_optional}, source={param_source}")

            # Use the effective type (inner type of Optional/Union)
            # Ensure param_type holds the actual model name if it's a body
            model_name_for_body = effective_param_type if is_request_body else None
            if model_name_for_body:
                request_model_name = model_name_for_body # CAPTURE request model name
                logger.debug(f"  Identified request body model: {request_model_name}")

            param_description = param_docs.get(param_name, "") # Get description from parsed docstring

            # Prioritize marker description if available
            final_param_description = marker_description or param_description
            logger.debug(f"  Final description: '{final_param_description}'")

            param_info = {
                "name": param_name,
                "in": param_source,
                "required": is_required,
                "type": effective_param_type,
                "description": final_param_description
            }
            if param_default is not None:
                 param_info["default"] = param_default

            if is_request_body:
                 request_body_param_info = param_info # Store details, including type/model name
                 logger.debug(f"  Stored request body info for '{param_name}'")
            else:
                 parameters.append(param_info)
                 logger.debug(f"  Added parameter '{param_name}' to list")

    # Assemble Endpoint Data
    endpoint_dict = {
        "path": route_path,
        "method": http_method,
        "name": func_name, # Added function name as operationId candidate
        "summary": summary, # Use extracted summary
        "description": description, # Use extracted description
        "parameters": parameters,
        "request_model": request_model_name, # ADDED
        "response_model": response_model_name, # From decorator
        "status_code": status_code,
        "responses": {str(status_code): {"description": "Successful Response"}}, # Basic success response
        "source_file": file_path,
        "source_line": start_line,
        "tags": tags if isinstance(tags, list) else []
    }

    # Refine response structure using response_model_name
    if response_model_name:
        endpoint_dict["responses"][str(status_code)]["content"] = {
            "application/json": {
                "schema_name": response_model_name # Store just the name
            }
        }

    # Refine request body structure using request_model_name
    if request_model_name and request_body_param_info:
        endpoint_dict["request_body_details"] = { # Use a different key
            "description": request_body_param_info.get("description", ""),
            "required": request_body_param_info.get("required", True),
            "schema_name": request_model_name # Store just the name
        }

    logger.info(f"Successfully parsed endpoint '{func_name}' in {file_path}")
    return endpoint_dict


def parse_fastapi_endpoint(file_path: str, file_structure: Dict[str, Any], repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse FastAPI-specific endpoint definitions using AST."""
    endpoints = []
    full_path = os.path.join(repo_path, file_path) if repo_path and not os.path.isabs(file_path) else file_path
    logger.info(f"Attempting to parse FastAPI endpoints in: {full_path}")

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        tree = ast.parse(source_code)
    except FileNotFoundError:
         logger.error(f"File not found for FastAPI parsing: {full_path}")
         return []
    except Exception as e:
        logger.warning(f"Failed to read or parse AST for {full_path}: {e}", exc_info=True)
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            endpoint_data = parse_fastapi_function(node, file_path, source_code, repo_path=repo_path)
            if endpoint_data:
                endpoints.append(endpoint_data)

    logger.info(f"Finished parsing FastAPI endpoints in {file_path}. Found {len(endpoints)} endpoints.")
    return endpoints

def parse_pydantic_model(class_info: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a Pydantic model using AST to extract fields, types, and defaults."""
    fields = [] # Changed from properties dict to list of field dicts
    required = [] # Keep track of required field names
    body_source = class_info.get("body_source", "")
    class_name = class_info.get("name", "UnknownClass")
    file_path = class_info.get("source_file", "unknown_file")
    logger.debug(f"Parsing Pydantic model '{class_name}' in {file_path}")

    if not body_source:
        logger.warning(f"No body source found for Pydantic model {class_name} in {file_path}")
        return {"fields": fields, "required": required}

    try:
        if not body_source.strip():
             logger.warning(f"Empty body source for Pydantic model {class_name} in {file_path}")
             return {"fields": fields, "required": required}

        # Wrap in a dummy class for parsing
        dummy_class_source = f"class DummyModel:\n{textwrap.indent(body_source or 'pass', '    ')}"
        tree = ast.parse(dummy_class_source)
        class_body_nodes = tree.body[0].body
        logger.debug(f"Parsed AST for {class_name}")

        for node in class_body_nodes:
            field_name = None
            field_type_str = "Any"
            is_required = True
            default_value_repr = None
            description = None

            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    field_name = node.target.id
                if node.annotation:
                    field_type_str = ast.unparse(node.annotation).strip()
                    if field_type_str.startswith("Optional[") or (field_type_str.startswith("Union[") and "None" in field_type_str):
                         is_required = False
                if node.value:
                    is_required = False
                    default_value_repr = ast.unparse(node.value).strip()
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'Field':
                        field_args = node.value
                        has_explicit_default = False
                        for kw in field_args.keywords:
                             if kw.arg in ('default', 'default_factory'):
                                 has_explicit_default = True
                                 is_required = False
                                 break
                        if not has_explicit_default and field_args.args:
                             is_required = False

                        for kw in field_args.keywords:
                            if kw.arg == 'required':
                                req_val = _safe_literal_eval(kw.value)
                                if req_val is True: is_required = True
                                if req_val is False: is_required = False
                                logger.debug(f"  Field '{field_name}': Found explicit required={req_val} in Field()")
                                break

                        for kw in field_args.keywords:
                            if kw.arg == 'description':
                                desc_val = _safe_literal_eval(kw.value)
                                if isinstance(desc_val, str): description = desc_val
                                logger.debug(f"  Field '{field_name}': Found description='{description}' in Field()")
                                break

            elif isinstance(node, ast.Assign):
                if node.targets and isinstance(node.targets[0], ast.Name):
                    field_name = node.targets[0].id
                    is_required = False
                    default_value_repr = ast.unparse(node.value).strip()

            if field_name:
                logger.debug(f"  Processing field: {field_name}, Type: {field_type_str}, Required: {is_required}, Default: {default_value_repr}")
                field_details = {
                    "name": field_name,
                    "type": field_type_str,
                    "required": is_required # Store required status per field
                 }
                if default_value_repr is not None:
                    field_details["default"] = default_value_repr
                if description is not None:
                    field_details["description"] = description

                fields.append(field_details)
                if is_required:
                    required.append(field_name) # Keep the separate list for OpenAPI compatibility if needed
            else:
                 logger.debug(f"  Skipping node in {class_name} body: {ast.dump(node)}")

    except SyntaxError as e:
        logger.error(f"AST Syntax Error parsing Pydantic model {class_name} in {file_path}: {e}\nSource:\n{dummy_class_source}")
        return {"fields": [], "required": []}
    except Exception as e:
        logger.exception(f"Unexpected error parsing Pydantic model {class_name} in {file_path}: {e}", exc_info=True)
        return {"fields": [], "required": []}

    logger.info(f"Finished parsing Pydantic model '{class_name}'. Found {len(fields)} fields.")
    # Return list of fields instead of properties dict
    return {"fields": fields, "required": required} 

# --- Helper function for Docstring Parsing ---
def _parse_docstring_params(docstring: str) -> Dict[str, str]:
    """Rudimentary parsing of Args/Parameters section in Google/reST style docstrings."""
    params = {}
    if not docstring: return params

    lines = docstring.strip().split('\n')
    in_args_section = False
    current_param = None

    # Simple regex for common patterns like "param_name (type): description"
    # or ":param param_name: description"
    google_style_match = re.compile(r"^\s*(\w+)\s*(\(.*?\))?:\s*(.*)")
    rest_param_match = re.compile(r"^\s*:param\s+(\w+):\s*(.*)")
    rest_type_match = re.compile(r"^\s*:type\s+(\w+):\s*(.*)") # Can capture type too, but not used here
    indent_match = re.compile(r"^(\s+)(.*)")

    current_description_lines = []

    for line in lines:
        stripped_line = line.strip()

        # Detect start of standard sections
        if stripped_line in ("Args:", "Arguments:", "Parameters:"):
            in_args_section = True
            current_param = None # Reset current param when section starts
            continue
        
        # Detect end of section (e.g., Returns:, Raises:, blank line)
        if in_args_section and (stripped_line.endswith(":") or not stripped_line):
             if current_param and current_description_lines: # Store last param's description
                 params[current_param] = " ".join(current_description_lines).strip()
             # Reset state if section ends
             # Heuristic: If line ends with ':', assume new section starts
             if stripped_line.endswith(":") and stripped_line not in ("Args:", "Arguments:", "Parameters:"):
                 in_args_section = False
             current_param = None
             current_description_lines = []
             if not stripped_line: # Stop parsing params on blank line within section
                 # Could make this more robust, but fine for now
                 # in_args_section = False # Optionally stop section on blank line
                 pass
             continue # Skip processing the section header/blank line itself

        if not in_args_section:
            continue

        # Try matching param definitions
        match_google = google_style_match.match(line) # Match against original line for indentation
        match_rest = rest_param_match.match(line)

        new_param_found = False
        param_name = None
        description_start = None
        indent_level = 0
        line_indent_match = indent_match.match(line)
        if line_indent_match:
            indent_level = len(line_indent_match.group(1))
        else: # Handle lines starting with no indent within the block
            indent_level = 0
            
        if match_google:
            param_name = match_google.group(1)
            description_start = match_google.group(3).strip()
            new_param_found = True
        elif match_rest:
            param_name = match_rest.group(1)
            description_start = match_rest.group(2).strip()
            new_param_found = True

        if new_param_found:
            # Store previous parameter's description
            if current_param and current_description_lines:
                params[current_param] = " ".join(current_description_lines).strip()
            
            # Start new parameter
            current_param = param_name
            current_description_lines = [description_start] if description_start else []
        elif current_param and line_indent_match and len(line_indent_match.group(1)) > 0: # Check for indentation > 0
             # This is a continuation line for the current parameter's description
             current_description_lines.append(stripped_line)
        elif current_param: # Line doesn't match format and isn't indented? Treat as part of previous description or ignore.
             # This heuristic might be too simple. Let's append if it looks like continuation
             current_description_lines.append(stripped_line)
             pass # Or potentially reset current_param here if strict formatting is expected

    # Store the last parameter's description
    if current_param and current_description_lines:
        params[current_param] = " ".join(current_description_lines).strip()

    return params 