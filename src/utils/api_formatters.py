"""
API Documentation Formatting Utilities
======================================

Functions for formatting extracted API endpoints and schemas into specific
documentation formats (e.g., Markdown, reStructuredText).
"""

from typing import Dict, Any, List, Optional

# Assuming logger is available or passed in
from .logging import core_logger 
logger = core_logger()

# --- Markdown Formatters ---

def format_markdown_endpoint(path: str, method: str, summary: str, description: str,
                           parameters: List[Dict[str, Any]], request_body: Optional[Dict[str, Any]],
                           responses: Dict[str, Dict[str, Any]]) -> str:
    """Format an endpoint as Markdown documentation (placeholder)."""
    logger.debug(f"Markdown endpoint formatter placeholder for {method} {path}")
    # Implementation needed: Generate Markdown sections for description, params, request body, responses.
    md = f"## `{method}` `{path}`\n\n"
    if summary:
        md += f"**{summary}**\n\n"
    if description:
        md += f"{description}\n\n"

    # Parameters
    if parameters:
        md += "### Parameters\n\n"
        md += "| Name | In | Type | Required | Description | Default |\n"
        md += "|------|----|------|----------|-------------|---------|\n"
        for param in parameters:
            p_schema = param.get("schema", {})
            p_default = p_schema.get("default", "*N/A*")
            md += f"| `{param.get('name')}` | {param.get('in')} | `{p_schema.get('type', 'any')}` | {param.get('required')} | {param.get('description', '')} | `{p_default}` |\n"
        md += "\n"

    # Request Body
    if request_body:
        md += "### Request Body\n\n"
        rb_required = request_body.get("required", True)
        rb_desc = request_body.get("description", "")
        md += f"* Required: {rb_required}\n"
        if rb_desc:
            md += f"* Description: {rb_desc}\n"
        
        # Look for schema reference or inline schema
        rb_content = request_body.get("content", {}).get("application/json", {}).get("schema", {})
        if "$ref" in rb_content:
            schema_name = rb_content["$ref"].split('/')[-1]
            md += f"* Schema: [`{schema_name}`](#schema-{schema_name.lower()})\n"
        elif rb_content:
             md += f"* Schema: (Inline object - details TBD)\n"
             # TODO: Potentially format inline schema if available
        md += "\n"

    # Responses
    if responses:
        md += "### Responses\n\n"
        md += "| Status Code | Description | Schema |\n"
        md += "|-------------|-------------|--------|\n"
        for status, resp_info in responses.items():
            resp_desc = resp_info.get("description", "")
            schema_info = "*N/A*"
            resp_content = resp_info.get("content", {}).get("application/json", {}).get("schema", {})
            if "$ref" in resp_content:
                schema_name = resp_content["$ref"].split('/')[-1]
                schema_info = f"[`{schema_name}`](#schema-{schema_name.lower()})"
            elif resp_content:
                schema_info = "(Inline object)"
            md += f"| `{status}` | {resp_desc} | {schema_info} |\n"
        md += "\n"

    return md

def format_markdown_schema(name: str, description: str, 
                         properties: Dict[str, Dict[str, Any]], 
                         required: List[str]) -> str:
    """Format a schema as Markdown documentation (placeholder)."""
    logger.debug(f"Markdown schema formatter placeholder for {name}")
    # Implementation needed: Generate schema name, description, and properties table.
    # Use an anchor for linking from endpoints
    md = f"### <a name=\"schema-{name.lower()}\"></a>Schema: `{name}`\n\n"
    if description:
        md += f"{description}\n\n"

    if properties:
        md += "#### Properties\n\n"
        md += "| Name | Type | Required | Description | Default |\n"
        md += "|------|------|----------|-------------|---------|\n"
        for prop_name, prop_details in properties.items():
            is_req = prop_name in required
            p_desc = prop_details.get('description', '')
            p_default = prop_details.get("default", "*N/A*")
            md += f"| `{prop_name}` | `{prop_details.get('type', 'any')}` | {is_req} | {p_desc} | `{p_default}` |\n"
        md += "\n"
    else:
        md += "*No properties defined.*\n\n"
        
    return md

def _format_markdown_schema(schema_data: dict) -> str:
    """
    Formats parsed Pydantic schema data into a Markdown section.

    Args:
        schema_data: A dictionary containing parsed schema info,
                     e.g., {'name': 'UserInput', 'fields': [...]}
                     (Structure based on _parse_pydantic_model output).

    Returns:
        A Markdown string representing the schema.
    """
    if not schema_data or 'name' not in schema_data or 'fields' not in schema_data:
        return ""

    schema_name = schema_data['name']
    fields = schema_data['fields']
    md = [f"### Schema: `{schema_name}`\n"]
    md.append("| Field | Type | Default | Required |")
    md.append("|-------|------|---------|----------|")
    for field in fields:
        name = field.get('name', 'N/A')
        type_ = field.get('type', 'N/A')
        default = field.get('default', '') # Represent None/missing as empty
        required = 'Yes' if field.get('required', False) else 'No'
        md.append(f"| `{name}` | `{type_}` | `{default}` | {required} |")

    return "\n".join(md) + "\n"

def _format_markdown_endpoint(endpoint_data: dict) -> str:
    """
    Formats parsed endpoint data into a Markdown section.

    Args:
        endpoint_data: A dictionary containing parsed endpoint info,
                       e.g., {'path': '/users/', 'method': 'POST',
                              'name': 'create_user', 'summary': '...',
                              'params': [...], 'request_model': 'UserInput',
                              'response_model': 'UserOutput'}
                       (Structure based on parser output - TBD refinement).

    Returns:
        A Markdown string representing the endpoint.
    """
    if not endpoint_data or 'path' not in endpoint_data or 'method' not in endpoint_data:
        return ""

    path = endpoint_data['path']
    method = endpoint_data['method'].upper()
    name = endpoint_data.get('name', '')
    summary = endpoint_data.get('summary', '') # Will come from docstring parsing later
    params = endpoint_data.get('params', [])
    request_model = endpoint_data.get('request_model', None)
    response_model = endpoint_data.get('response_model', None)

    md = [f"## `{method}` `{path}`"]
    if name:
        md.append(f"**Operation ID:** `{name}`")
    if summary:
        md.append(f"\n{summary}\n") # Add newline before/after summary

    # Parameters (Path/Query)
    if params:
        md.append("### Parameters")
        md.append("| Name | In | Type | Default | Required | Description |")
        md.append("|------|----|------|---------|----------|-------------|")
        for param in params:
            p_name = param.get('name', 'N/A')
            p_in = param.get('in', 'N/A') # e.g., 'path', 'query'
            p_type = param.get('type', 'N/A')
            p_default = param.get('default', '')
            p_required = 'Yes' if param.get('required', False) else 'No'
            p_desc = param.get('description', '') # Will come from docstring parsing later
            md.append(f"| `{p_name}` | {p_in} | `{p_type}` | `{p_default}` | {p_required} | {p_desc} |")
        md.append("\n") # Add spacing

    # Request Body
    if request_model:
        md.append("### Request Body")
        md.append(f"- **Schema:** `{request_model}`") # Link later if possible
        md.append("\n") # Add spacing

    # Response Body
    if response_model:
        md.append("### Response Body (Success)") # Assuming 200/201 for now
        md.append(f"- **Schema:** `{response_model}`") # Link later if possible

    return "\n".join(md) + "\n"

# --- reStructuredText Formatters ---

def format_rst_endpoint(path: str, method: str, summary: str, description: str,
                      parameters: List[Dict[str, Any]], request_body: Optional[Dict[str, Any]],
                      responses: Dict[str, Dict[str, Any]]) -> str:
    """Format an endpoint as reStructuredText documentation (placeholder)."""
    logger.debug(f"RST endpoint formatter placeholder for {method} {path}")
    # Implementation needed: Use http:method directive, field lists for params/body, table for responses.
    rst = f".. http:{method.lower()}:: {path}\n"
    rst += f"   :synopsis: {summary}\n\n"
    if description:
         rst += f"   {description}\n\n"

    # Parameters
    for param in parameters:
        p_schema = param.get("schema", {})
        p_type = p_schema.get('type', 'string')
        p_req = ':required:' if param.get('required') else ''
        p_desc = param.get('description', '')
        rst += f"   :{param.get('in')}parameter {p_type} {param.get('name')}: {p_desc} {p_req}\n"

    # Request Body
    if request_body:
        # TODO: Add more detail for request body in RST
        rb_desc = request_body.get("description", "Request Body")
        rst += f"   :request: {rb_desc}\n"
        rb_content = request_body.get("content", {}).get("application/json", {}).get("schema", {})
        if "$ref" in rb_content:
             schema_name = rb_content["$ref"].split('/')[-1]
             rst += f"      :schema: See :schema:`{schema_name}`\n"
        
    # Responses
    for status, resp_info in responses.items():
        resp_desc = resp_info.get("description", "")
        rst += f"   :statuscode {status}: {resp_desc}\n"
        resp_content = resp_info.get("content", {}).get("application/json", {}).get("schema", {})
        if "$ref" in resp_content:
             schema_name = resp_content["$ref"].split('/')[-1]
             rst += f"      :schema: See :schema:`{schema_name}`\n"

    rst += "\n"
    return rst

def format_rst_schema(name: str, description: str, 
                    properties: Dict[str, Dict[str, Any]], 
                    required: List[str]) -> str:
    """Format a schema as reStructuredText documentation (placeholder)."""
    logger.debug(f"RST schema formatter placeholder for {name}")
    # Implementation needed: Use .. schema:: directive, field lists or tables for properties.
    rst = f".. schema:: {name}\n\n"
    if description:
        rst += f"   {description}\n\n"

    if properties:
        for prop_name, prop_details in properties.items():
            p_type = prop_details.get('type', 'any')
            p_req = " (required)" if prop_name in required else ""
            p_desc = prop_details.get('description', '')
            p_default = prop_details.get("default")
            default_str = f", default: ``{p_default}``" if p_default is not None else ""
            rst += f"   :property {prop_name}: {p_desc}\n"
            rst += f"      :type: {p_type}{p_req}{default_str}\n"
        rst += "\n"
    else:
         rst += "   *No properties defined.*\n\n"
         
    return rst

# --- Add other formatters as needed (e.g., OpenAPI) --- 