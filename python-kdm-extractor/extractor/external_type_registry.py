class ExternalTypeRegistry:
    """
    Registry of known external factory functions, external types, and methods.

    This registry is intentionally partial. Its purpose is to classify common
    calls from standard libraries or external libraries without requiring
    full static analysis of those libraries.
    """

    FACTORY_RETURN_TYPES = {
        "logging.getLogger": "logging.Logger",
        "logging.Logger": "logging.Logger",
        "Path": "pathlib.Path",
        "open": "io.TextIOWrapper",
        "requests.get": "requests.Response",
        "pandas.DataFrame": "pandas.DataFrame",
        "open": "io.TextIOWrapper"
    }

    EXTERNAL_TYPE_METHODS = {
        "logging.Logger": {
            "debug",
            "info",
            "warning",
            "error",
            "exception",
            "critical",
            "log",
            "setLevel",
            "addHandler",
            "removeHandler"
        },

        "pathlib.Path": {
            "exists",
            "is_file",
            "is_dir",
            "read_text",
            "write_text",
            "mkdir",
            "glob",
            "resolve",
            "joinpath"
        },

        "io.TextIOWrapper": {
            "write",
            "read",
            "readline",
            "readlines",
            "close",
            "flush"
        },

        "requests.Response": {
            "json",
            "text",
            "raise_for_status"
        },

        "pandas.DataFrame": {
            "head",
            "tail",
            "to_csv",
            "drop",
            "merge",
            "groupby"
        }
    }

    @classmethod
    def get_factory_return_type(cls, factory_name: str):
        """
        Returns the known return type of an external factory function.

        Example:
        logging.getLogger(...) -> logging.Logger
        """

        if not factory_name:
            return None

        return cls.FACTORY_RETURN_TYPES.get(factory_name)

    @classmethod
    def is_external_type(cls, type_name: str):
        """
        Checks whether a type is a known external type.
        """

        return type_name in cls.EXTERNAL_TYPE_METHODS

    @classmethod
    def has_method(cls, type_name: str, method_name: str):
        """
        Checks whether an external type has a known method.
        """

        if not type_name or not method_name:
            return False

        return method_name in cls.EXTERNAL_TYPE_METHODS.get(type_name, set())
