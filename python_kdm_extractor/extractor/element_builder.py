class ElementBuilder:
    """
    Builds a flat list of model elements from the hierarchical project model.

    The extractor keeps two complementary views of the analyzed project:

    1. Hierarchical view:
       Stored in project_model["files"]. This preserves the natural structure:

           project
             └── modules
                   ├── classes
                   │     ├── attributes
                   │     ├── instance attributes
                   │     └── methods
                   └── functions

    2. Flat element view:
       Stored in project_model["elements"]. This contains normalized elements
       with ids, names, qualified names, types, parent references and source
       location metadata.

    The flat element list is useful for later transformation, analysis,
    validation and debugging, because all relevant elements can be traversed
    without navigating the full nested JSON structure.
    """

    def __init__(self):
        """
        Initializes the element builder.

        elements:
            Flat list of generated element dictionaries.

        element_ids:
            Set used to avoid duplicate elements.
        """

        self.elements = []
        self.element_ids = set()

    def build_elements(self, project_model: dict):
        """
        Builds the flat element list for the full project model.

        Parameters
        ----------
        project_model:
            Intermediate project model produced by the extractor.

        Returns
        -------
        dict
            The same project model enriched with project_model["elements"].
        """

        self.elements = []
        self.element_ids = set()

        self._add_project_element(project_model)

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            self._add_module_element(file_model)

            for class_model in file_model.get("classes", []):
                self._add_class_element(class_model, file_model)

                for attribute_model in class_model.get("attributes", []):
                    self._add_class_attribute_element(
                        attribute_model,
                        class_model,
                        file_model,
                    )

                for instance_attribute_model in class_model.get(
                    "instance_attributes", []
                ):
                    self._add_instance_attribute_element(
                        instance_attribute_model,
                        class_model,
                        file_model,
                    )

                for method_model in class_model.get("methods", []):
                    self._add_callable_element(
                        method_model,
                        parent_id=class_model.get("id"),
                        parent_type="class",
                        file_model=file_model,
                    )

            for function_model in file_model.get("functions", []):
                self._add_callable_element(
                    function_model,
                    parent_id=file_model.get("id"),
                    parent_type="module",
                    file_model=file_model,
                )

        project_model["elements"] = self.elements

        return project_model

    def _add_project_element(self, project_model: dict):
        """
        Adds the project itself as the root flat element.
        """

        project_name = project_model.get("projectName")

        if not project_name:
            return

        element = {
            "id": f"project:{project_name}",
            "name": project_name,
            "qualified_name": project_name,
            "type": "project",
            "language": project_model.get("language"),
        }

        self._add_element(element)

    def _add_module_element(self, file_model: dict):
        """
        Adds a Python module element.
        """

        element = {
            "id": file_model.get("id"),
            "name": file_model.get("name"),
            "qualified_name": file_model.get("qualified_name"),
            "type": "module",
            "path": file_model.get("path"),
            "line_start": None,
            "line_end": None,
        }

        self._add_element(element)

    def _add_class_element(self, class_model: dict, file_model: dict):
        """
        Adds a class element.
        """

        element = {
            "id": class_model.get("id"),
            "name": class_model.get("name"),
            "qualified_name": class_model.get("qualified_name"),
            "type": "class",
            "module_id": file_model.get("id"),
            "module_qualified_name": file_model.get("qualified_name"),
            "bases": class_model.get("bases", []),
            "line_start": class_model.get("line_start"),
            "line_end": class_model.get("line_end"),
        }

        self._add_element(element)

    def _add_callable_element(
        self,
        callable_model: dict,
        parent_id: str,
        parent_type: str,
        file_model: dict,
    ):
        """
        Adds a function or method element.

        After adding the callable itself, this method also adds:

        - context variables introduced by with statements;
        - flat elements for all hierarchical body nodes.
        """

        element = {
            "id": callable_model.get("id"),
            "name": callable_model.get("name"),
            "qualified_name": callable_model.get("qualified_name"),
            "type": callable_model.get("type"),
            "parent_id": parent_id,
            "parent_type": parent_type,
            "module_id": file_model.get("id"),
            "module_qualified_name": file_model.get("qualified_name"),
            "parameters": callable_model.get("parameters", []),
            "line_start": callable_model.get("line_start"),
            "line_end": callable_model.get("line_end"),
        }

        self._add_element(element)

        self._add_context_variable_elements(
            callable_model,
            parent_id=callable_model.get("id"),
            parent_type=callable_model.get("type"),
            file_model=file_model,
        )

        self._add_body_elements(
            callable_model.get("body", []),
            parent_id=callable_model.get("id"),
            parent_type=callable_model.get("type"),
            file_model=file_model,
        )

    def _add_body_elements(
        self,
        body_nodes: list,
        parent_id: str,
        parent_type: str,
        file_model: dict,
    ):
        """
        Adds body nodes as flat elements and recursively processes nested bodies.

        This method preserves body nesting through parent_id and parent_type
        fields. It supports normal body branches, else branches, finally
        branches and exception handlers.
        """

        for body_node in body_nodes:
            element_id = body_node.get("id")

            if not element_id:
                continue

            element = {
                "id": element_id,
                "name": body_node.get("control_type")
                or body_node.get("statement_type")
                or body_node.get("type"),
                "qualified_name": element_id,
                "type": body_node.get("type"),
                "control_type": body_node.get("control_type"),
                "statement_type": body_node.get("statement_type"),
                "parent_id": parent_id,
                "parent_type": parent_type,
                "module_id": file_model.get("id"),
                "module_qualified_name": file_model.get("qualified_name"),
                "line_start": body_node.get("line_start"),
                "line_end": body_node.get("line_end"),
            }

            optional_fields = [
                "condition",
                "target",
                "iter",
                "value",
                "exception",
                "items",
                "targets",
                "annotation",
                "ast_node_type",
                "condition_calls",
                "iter_calls",
                "value_call",
                "value_calls",
                "exception_calls",
            ]

            for field in optional_fields:
                if field in body_node:
                    element[field] = body_node.get(field)

            if body_node.get("statement_type") == "call":
                element["call"] = body_node.get("call")

            self._add_element(element)

            # Normal body branch.
            self._add_body_elements(
                body_node.get("body", []),
                parent_id=element_id,
                parent_type=body_node.get("type"),
                file_model=file_model,
            )

            # Else branch.
            self._add_body_elements(
                body_node.get("orelse", []),
                parent_id=element_id,
                parent_type=body_node.get("type"),
                file_model=file_model,
            )

            # Finally branch.
            self._add_body_elements(
                body_node.get("finalbody", []),
                parent_id=element_id,
                parent_type=body_node.get("type"),
                file_model=file_model,
            )

            # Exception handlers.
            for handler in body_node.get("handlers", []):
                handler_element = {
                    "id": handler.get("id"),
                    "name": "except",
                    "qualified_name": handler.get("id"),
                    "type": "exception_handler",
                    "exception": handler.get("exception"),
                    "parent_id": element_id,
                    "parent_type": body_node.get("type"),
                    "module_id": file_model.get("id"),
                    "module_qualified_name": file_model.get("qualified_name"),
                    "line_start": handler.get("line_start"),
                    "line_end": handler.get("line_end"),
                }

                self._add_element(handler_element)

                self._add_body_elements(
                    handler.get("body", []),
                    parent_id=handler.get("id"),
                    parent_type="exception_handler",
                    file_model=file_model,
                )

    def _add_class_attribute_element(
        self,
        attribute_model: dict,
        class_model: dict,
        file_model: dict,
    ):
        """
        Adds a class attribute element.

        Example
        -------
        class UserService:
            service_name = "user-service"
        """

        attribute_name = attribute_model.get("name")

        if not attribute_name:
            return

        element_id = (
            f"attribute:{class_model.get('qualified_name')}.{attribute_name}"
        )

        element = {
            "id": element_id,
            "name": attribute_name,
            "qualified_name": f"{class_model.get('qualified_name')}.{attribute_name}",
            "type": "class_attribute",
            "parent_id": class_model.get("id"),
            "parent_type": "class",
            "module_id": file_model.get("id"),
            "module_qualified_name": file_model.get("qualified_name"),
            "assigned_value": attribute_model.get("assigned_value"),
            "assigned_type": attribute_model.get("assigned_type"),
            "annotation": attribute_model.get("annotation"),
            "line_start": attribute_model.get("line"),
            "line_end": attribute_model.get("line"),
        }

        self._add_element(element)

    def _add_instance_attribute_element(
        self,
        attribute_model: dict,
        class_model: dict,
        file_model: dict,
    ):
        """
        Adds an instance attribute element.

        Example
        -------
        self.repository = UserRepository()
        """

        attribute_name = attribute_model.get("name")

        if not attribute_name:
            return

        element_id = (
            f"instance_attribute:{class_model.get('qualified_name')}.{attribute_name}"
        )

        element = {
            "id": element_id,
            "name": attribute_name,
            "qualified_name": f"{class_model.get('qualified_name')}.{attribute_name}",
            "type": "instance_attribute",
            "full_name": attribute_model.get("full_name"),
            "parent_id": class_model.get("id"),
            "parent_type": "class",
            "module_id": file_model.get("id"),
            "module_qualified_name": file_model.get("qualified_name"),
            "defined_in": attribute_model.get("defined_in"),
            "assigned_value": attribute_model.get("assigned_value"),
            "assigned_type": attribute_model.get("assigned_type"),
            "resolved_type_id": attribute_model.get("resolved_type_id"),
            "resolved_type_qualified_name": attribute_model.get(
                "resolved_type_qualified_name"
            ),
            "type_resolution": attribute_model.get("type_resolution"),
            "line_start": attribute_model.get("line"),
            "line_end": attribute_model.get("line"),
        }

        self._add_element(element)

    def _add_element(self, element: dict):
        """
        Adds an element only if its id is valid and has not been added before.
        """

        element_id = element.get("id")

        if not element_id:
            return

        if element_id in self.element_ids:
            return

        self.element_ids.add(element_id)
        self.elements.append(element)

    def _add_context_variable_elements(
        self,
        callable_model: dict,
        parent_id: str,
        parent_type: str,
        file_model: dict,
    ):
        """
        Adds variables introduced by context managers as flat elements.

        Example
        -------
        with open(...) as file:
            file.write(...)

        Produces
        --------
        context_variable:<callable-qualified-name>.file
        """

        for variable in callable_model.get("context_variables", []):
            variable_name = variable.get("name")

            if not variable_name:
                continue

            element_id = (
                f"context_variable:"
                f"{callable_model.get('qualified_name')}.{variable_name}"
            )

            element = {
                "id": element_id,
                "name": variable_name,
                "qualified_name": (
                    f"{callable_model.get('qualified_name')}.{variable_name}"
                ),
                "type": "context_variable",
                "parent_id": parent_id,
                "parent_type": parent_type,
                "module_id": file_model.get("id"),
                "module_qualified_name": file_model.get("qualified_name"),
                "assigned_value": variable.get("assigned_value"),
                "assigned_type": variable.get("assigned_type"),
                "resolved_type_id": variable.get("resolved_type_id"),
                "resolved_type_qualified_name": variable.get(
                    "resolved_type_qualified_name"
                ),
                "type_resolution": variable.get("type_resolution"),
                "resolved_from_context_manager": variable.get(
                    "resolved_from_context_manager",
                    True,
                ),
                "external_factory": variable.get("external_factory"),
                "line_start": variable.get("line"),
                "line_end": variable.get("line"),
            }

            self._add_element(element)
