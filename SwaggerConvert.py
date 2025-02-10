import json
import requests
from typing import Dict, Any
from urllib.parse import urlparse

def fetch_api_details(base_url: str, path: str) -> Dict[str, Any]:
    """
    Fetch detailed information for each API endpoint.
    This assumes each endpoint returns the Swagger 1.2 definition.
    """
    full_url = f"{base_url}{path}"  # Build the full URL
    try:
        response = requests.get(full_url)
        response.raise_for_status()  # Check if the request is successful
        return response.json()  # Return the JSON data
    except requests.RequestException as e:
        print(f"Failed to fetch data from {full_url}: {e}")
        return {}

def convert_swagger_12_to_20(api_docs_url: str) -> Dict[str, Any]:
    # Ensure the provided URL ends with "api-docs"
    if not api_docs_url.endswith("api-docs"):
        print("Error: The provided URL does not end with 'api-docs'. Please provide the correct URL.")
        return {}

    # Parse the api-docs URL
    parsed_url = urlparse(api_docs_url)
    host = parsed_url.netloc  # Extract the host
    base_path = parsed_url.path.rstrip('/')  # Extract the base path and remove trailing slashes
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}/"  # Construct the complete URL

    # Fetch api-docs basic info
    try:
        print(f"Fetching API documentation from {api_docs_url}...")
        response = requests.get(api_docs_url)
        response.raise_for_status()
        input_data = response.json()  # Get the JSON data from api-docs URL
    except requests.RequestException as e:
        print(f"Failed to fetch api-docs data: {e}")
        return {}

    # Initialize the Swagger 2.0 structure
    swagger_20 = {
        "swagger": "2.0",
        "info": input_data["info"],
        "host": host,
        "basePath": base_path,
        "schemes": [parsed_url.scheme],  # Use the protocol from the URL (http or https)
        "paths": {},
        "definitions": {},
        "tags": []
    }

    # Convert global info
    swagger_20["info"]["version"] = input_data.get("apiVersion", "1.0")
    
    # Convert Tags and Paths
    seen_tags = set()
    for api_entry in input_data["apis"]:
        # Assume each controller corresponds to a tag
        tag_name = api_entry["path"].split("/")[-1].replace("-controller", "")
        if tag_name not in seen_tags:
            swagger_20["tags"].append({
                "name": tag_name,
                "description": api_entry["description"]
            })
            seen_tags.add(tag_name)

        # Fetch API details for each endpoint
        print(f"Fetching details for endpoint: {api_entry['path']}...")
        api_details = fetch_api_details(base_url, api_entry["path"])

        # Convert each API operation
        for endpoint in api_details.get("apis", []):
            path = endpoint["path"]
            for operation in endpoint["operations"]:
                method = operation["method"].lower()
                parameters = []
                
                # Convert parameters
                for param in operation.get("parameters", []):
                    param_spec = {
                        "name": param["name"],
                        "in": param["paramType"],
                        "description": param.get("description", ""),
                        "required": param["required"],
                        "type": param.get("type", "string").lower()  # Default to "string" if "type" is missing
                    }
                    if "format" in param:
                        param_spec["format"] = param["format"]
                    parameters.append(param_spec)

                # Convert responses
                responses = {}
                for resp in operation.get("responseMessages", []):
                    code = str(resp["code"])
                    responses[code] = {
                        "description": resp["message"] or "No description",
                        "schema": {"$ref": f"#/definitions/{resp['responseModel']}"} if resp["responseModel"] else None
                    }

                # Construct the operation object
                operation_obj = {
                    "tags": [tag_name],
                    "summary": operation["summary"],
                    "description": operation["notes"],
                    "parameters": parameters,
                    "responses": responses,
                    "consumes": operation["consumes"],
                    "produces": operation["produces"]
                }

                # Add operation to paths
                if path not in swagger_20["paths"]:
                    swagger_20["paths"][path] = {}
                swagger_20["paths"][path][method] = operation_obj

    # Convert model definitions
    for model_name, model_def in input_data.get("models", {}).items():
        properties = {}
        required = []
        for prop_name, prop_def in model_def["properties"].items():
            prop_spec = {
                "type": prop_def["type"].lower(),
                "description": prop_def.get("description", "")
            }
            if prop_def.get("format"):
                prop_spec["format"] = prop_def["format"]
            if prop_def.get("required", False):
                required.append(prop_name)
            properties[prop_name] = prop_spec

        swagger_20["definitions"][model_name] = {
            "type": "object",
            "properties": properties,
            "required": required if required else None,
            "description": model_def.get("description", "")
        }

    # Clean up empty fields
    for path in swagger_20["paths"].values():
        for method in path.values():
            if not method["responses"]:
                del method["responses"]
            if not method["parameters"]:
                del method["parameters"]
    
    return swagger_20

if __name__ == "__main__":
    # Prompt user to enter the api-docs URL
    api_docs_url = input("Please enter the API documentation URL: ").strip()
    
    print("\nConverting Swagger 1.2 to Swagger 2.0...\n")
    
    # Perform conversion
    output = convert_swagger_12_to_20(api_docs_url)
    
    if output:  # Only save if conversion is successful
        # Save the converted result
        with open("swagger.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print("\nConversion complete! The result has been saved to 'swagger.json'.")
