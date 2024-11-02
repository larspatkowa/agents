import subprocess
import sys
import inspect

def run_python_code(code):
    '''Run Python code in a sandboxed environment. Use this function for calculations or data processing. You must use print() to receive any output, and you cannot import other modules.'''
    try:
        # Run the provided Python code in a separate process
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            timeout=10,
            text=True
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Execution timed out"
    except Exception as e:
        return f"Error: {e}"

def generate_openapi_schema(func):
    '''Generate an OpenAPI schema for a given function.'''
    sig = inspect.signature(func)
    parameters = {
        "type": "object",
        "required": [],
        "properties": {}
    }
    # Iterate over function parameters to build the schema
    for param in sig.parameters.values():
        param_info = {
            "type": "string",
            "description": param.annotation if param.annotation != inspect.Parameter.empty else ""
        }
        parameters["properties"][param.name] = param_info
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(param.name)
    
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "parameters": parameters,
            "description": func.__doc__
        }
    }

# Dictionary of available functions
available_functions = {
    "run_python_code": run_python_code
}

# Generate a list of OpenAPI schemas for all available functions
openapi_schemas = [
    generate_openapi_schema(func)
    for func in available_functions.values()
]
# Print the generated OpenAPI schemas
# print(openapi_schemas)