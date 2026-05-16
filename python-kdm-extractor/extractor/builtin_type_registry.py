class BuiltinTypeRegistry:
    """
    Registry of common Python built-in types, their known methods,
    and simple return-type rules.

    This registry is intentionally partial. Its goal is to classify common
    built-in method calls and support simple chained calls such as:

    name.strip().title()
    """

    BUILTIN_TYPE_METHODS = {
        "list": {
            "append",
            "extend",
            "insert",
            "remove",
            "pop",
            "clear",
            "index",
            "count",
            "sort",
            "reverse",
            "copy"
        },
        "dict": {
            "get",
            "keys",
            "values",
            "items",
            "update",
            "pop",
            "clear",
            "copy",
            "setdefault"
        },
        "str": {
            "strip",
            "lstrip",
            "rstrip",
            "title",
            "lower",
            "upper",
            "replace",
            "split",
            "join",
            "startswith",
            "endswith",
            "find",
            "format"
        },
        "set": {
            "add",
            "remove",
            "discard",
            "pop",
            "clear",
            "union",
            "intersection",
            "difference",
            "copy"
        },
        "tuple": {
            "count",
            "index"
        },
        "int": {
            "bit_length",
            "to_bytes"
        },
        "float": {
            "is_integer",
            "hex"
        },
        "bool": set(),
        "NoneType": set()
    }

    BUILTIN_METHOD_RETURN_TYPES = {
        "str": {
            "strip": "str",
            "lstrip": "str",
            "rstrip": "str",
            "title": "str",
            "lower": "str",
            "upper": "str",
            "replace": "str",
            "format": "str",
            "split": "list",
            "join": "str",
            "startswith": "bool",
            "endswith": "bool",
            "find": "int"
        },
        "list": {
            "copy": "list",
            "append": "NoneType",
            "extend": "NoneType",
            "insert": "NoneType",
            "remove": "NoneType",
            "clear": "NoneType",
            "sort": "NoneType",
            "reverse": "NoneType",
            "pop": "unknown",
            "index": "int",
            "count": "int"
        },
        "dict": {
            "get": "unknown",
            "keys": "dict_keys",
            "values": "dict_values",
            "items": "dict_items",
            "copy": "dict",
            "update": "NoneType",
            "pop": "unknown",
            "clear": "NoneType",
            "setdefault": "unknown"
        },
        "set": {
            "copy": "set",
            "union": "set",
            "intersection": "set",
            "difference": "set",
            "add": "NoneType",
            "remove": "NoneType",
            "discard": "NoneType",
            "clear": "NoneType",
            "pop": "unknown"
        },
        "tuple": {
            "count": "int",
            "index": "int"
        },
        "int": {
            "bit_length": "int",
            "to_bytes": "bytes"
        },
        "float": {
            "is_integer": "bool",
            "hex": "str"
        }
    }

    @classmethod
    def is_builtin_type(cls, type_name: str):
        """
        Checks whether a type name is a known built-in type.
        """

        return type_name in cls.BUILTIN_TYPE_METHODS

    @classmethod
    def has_method(cls, type_name: str, method_name: str):
        """
        Checks whether a built-in type has a known method.
        """

        if not type_name or not method_name:
            return False

        return method_name in cls.BUILTIN_TYPE_METHODS.get(type_name, set())

    @classmethod
    def get_method_return_type(cls, type_name: str, method_name: str):
        """
        Returns the known return type of a built-in method.

        Example:
        str.strip -> str
        str.title -> str
        list.append -> NoneType
        """

        if not type_name or not method_name:
            return None

        return cls.BUILTIN_METHOD_RETURN_TYPES.get(type_name, {}).get(
            method_name
        )
