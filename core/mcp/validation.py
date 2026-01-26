"""MCP Request validation and schema checking."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Result of schema validation."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SchemaValidator:
    """
    JSON Schema validator for MCP tool inputs.

    Validates tool arguments against their declared input schemas.
    """

    # JSON Schema type mappings to Python types
    TYPE_MAP = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    def validate(self, schema: Dict[str, Any], data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data against a JSON Schema.

        Args:
            schema: JSON Schema definition
            data: Data to validate

        Returns:
            ValidationResult with errors/warnings
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate required fields
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: '{field}'")

        # Validate properties
        properties = schema.get("properties", {})
        for field, value in data.items():
            if field not in properties:
                if schema.get("additionalProperties", True) is False:
                    errors.append(f"Unknown field: '{field}'")
                else:
                    warnings.append(f"Unknown field: '{field}'")
                continue

            field_schema = properties[field]
            field_errors = self._validate_field(field, value, field_schema)
            errors.extend(field_errors)

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _validate_field(
        self, name: str, value: Any, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate a single field against its schema."""
        errors = []

        # Handle null values
        if value is None:
            if "null" not in self._get_types(schema):
                errors.append(f"Field '{name}' cannot be null")
            return errors

        # Type validation
        expected_types = self._get_types(schema)
        if expected_types:
            valid_type = False
            for expected in expected_types:
                python_type = self.TYPE_MAP.get(expected)
                if python_type and isinstance(value, python_type):
                    valid_type = True
                    break
            if not valid_type:
                errors.append(
                    f"Field '{name}' has wrong type. Expected {expected_types}, got {type(value).__name__}"
                )
                return errors

        # String constraints
        if isinstance(value, str):
            errors.extend(self._validate_string(name, value, schema))

        # Number constraints
        if isinstance(value, (int, float)):
            errors.extend(self._validate_number(name, value, schema))

        # Array constraints
        if isinstance(value, list):
            errors.extend(self._validate_array(name, value, schema))

        # Enum validation
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"Field '{name}' must be one of: {schema['enum']}")

        return errors

    def _get_types(self, schema: Dict[str, Any]) -> List[str]:
        """Get type(s) from schema."""
        type_val = schema.get("type")
        if isinstance(type_val, list):
            return type_val
        elif type_val:
            return [type_val]
        return []

    def _validate_string(self, name: str, value: str, schema: Dict[str, Any]) -> List[str]:
        """Validate string constraints."""
        errors = []

        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"Field '{name}' must be at least {schema['minLength']} characters")

        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"Field '{name}' must be at most {schema['maxLength']} characters")

        if "pattern" in schema:
            import re
            if not re.match(schema["pattern"], value):
                errors.append(f"Field '{name}' does not match pattern: {schema['pattern']}")

        return errors

    def _validate_number(
        self, name: str, value: float, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate number constraints."""
        errors = []

        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"Field '{name}' must be >= {schema['minimum']}")

        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"Field '{name}' must be <= {schema['maximum']}")

        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"Field '{name}' must be > {schema['exclusiveMinimum']}")

        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(f"Field '{name}' must be < {schema['exclusiveMaximum']}")

        return errors

    def _validate_array(
        self, name: str, value: list, schema: Dict[str, Any]
    ) -> List[str]:
        """Validate array constraints."""
        errors = []

        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"Field '{name}' must have at least {schema['minItems']} items")

        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"Field '{name}' must have at most {schema['maxItems']} items")

        # Validate items if schema provided
        if "items" in schema:
            items_schema = schema["items"]
            for i, item in enumerate(value):
                item_errors = self._validate_field(f"{name}[{i}]", item, items_schema)
                errors.extend(item_errors)

        return errors


class RequestValidator:
    """
    Validates MCP requests for protocol compliance.
    """

    VALID_METHODS: Set[str] = {
        "initialize",
        "shutdown",
        "tools/list",
        "tools/call",
        "resources/list",
        "resources/read",
        "resources/subscribe",
        "resources/unsubscribe",
        "prompts/list",
        "prompts/get",
        "logging/setLevel",
        "notifications/initialized",
        "notifications/cancelled",
        "notifications/progress",
    }

    def __init__(self, strict: bool = False):
        """
        Initialize request validator.

        Args:
            strict: If True, reject unknown methods
        """
        self.strict = strict

    def validate_request(self, request: Dict[str, Any]) -> ValidationResult:
        """Validate a JSON-RPC request."""
        errors: List[str] = []
        warnings: List[str] = []

        # Check JSON-RPC version
        if request.get("jsonrpc") != "2.0":
            errors.append("Invalid or missing jsonrpc version (must be '2.0')")

        # Check method
        method = request.get("method")
        if not method:
            errors.append("Missing required field: 'method'")
        elif self.strict and method not in self.VALID_METHODS:
            # Check if it's a notification
            if not method.startswith("notifications/"):
                errors.append(f"Unknown method: '{method}'")

        # Check id for requests (not notifications)
        if method and not method.startswith("notifications/"):
            if "id" not in request:
                warnings.append("Request missing 'id' field (will be treated as notification)")

        # Validate params if present
        params = request.get("params")
        if params is not None and not isinstance(params, dict):
            errors.append("'params' must be an object")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_response(self, response: Dict[str, Any]) -> ValidationResult:
        """Validate a JSON-RPC response."""
        errors: List[str] = []

        # Check JSON-RPC version
        if response.get("jsonrpc") != "2.0":
            errors.append("Invalid or missing jsonrpc version")

        # Must have either result or error (or both for error case)
        has_result = "result" in response
        has_error = "error" in response

        if not has_result and not has_error:
            errors.append("Response must have either 'result' or 'error'")

        if has_error:
            error = response["error"]
            if not isinstance(error, dict):
                errors.append("'error' must be an object")
            else:
                if "code" not in error:
                    errors.append("Error missing 'code'")
                elif not isinstance(error["code"], int):
                    errors.append("Error 'code' must be an integer")
                if "message" not in error:
                    errors.append("Error missing 'message'")

        return ValidationResult(valid=len(errors) == 0, errors=errors)


# Global validator instances
schema_validator = SchemaValidator()
request_validator = RequestValidator()
