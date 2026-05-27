class KDMFactory:
    """
    Factory for creating KDM 1.4 model elements and relations.

    This class centralizes the instantiation of PyEcore objects from the loaded
    KDM metamodel. It hides low-level PyEcore construction details from the
    rest of the generator and provides a stable API for creating:

    - framework elements such as Segment;
    - inventory elements such as InventoryModel and SourceFile;
    - code elements such as CodeModel, CompilationUnit, ClassUnit,
      MethodUnit, CallableUnit, ParameterUnit and StorableUnit;
    - action elements such as ActionElement, BlockUnit, TryUnit, CatchUnit
      and FinallyUnit;
    - KDM relations such as Calls, Creates, Reads, Writes, Throws, HasType,
      HasValue, Imports, Extends, ExceptionFlow and ExitFlow;
    - source traceability elements such as SourceRef and SourceRegion.

    All resolvers and mappers should use this factory instead of directly
    instantiating PyEcore classes.
    """

    def __init__(self, resolver):
        """
        Initializes the factory by resolving all KDM metaclasses used by the
        generator.

        Parameters
        ----------
        resolver:
            ClassifierResolver instance used to locate EClasses inside the
            loaded KDM 1.4 Ecore metamodel.
        """

        self.resolver = resolver

        # KDM framework
        self.Segment = resolver.find("Segment")

        # Extension package
        self.ExtensionFamily = resolver.find("ExtensionFamily")
        self.Stereotype = resolver.find("Stereotype")

        # Code package
        self.CodeModel = resolver.find("CodeModel")
        self.CompilationUnit = resolver.find("CompilationUnit")
        self.ClassUnit = resolver.find("ClassUnit")
        self.MethodUnit = resolver.find("MethodUnit")
        self.CallableUnit = resolver.find("CallableUnit")
        self.Signature = resolver.find("Signature")
        self.ParameterUnit = resolver.find("ParameterUnit")
        self.StorableUnit = resolver.find("StorableUnit")

        # Action package
        self.ActionElement = resolver.find("ActionElement")
        self.BlockUnit = resolver.find("BlockUnit")
        self.ActionRelationship = resolver.find("ActionRelationship")
        self.Calls = resolver.find("Calls")
        self.Creates = resolver.find("Creates")
        self.Reads = resolver.find("Reads")
        self.Writes = resolver.find("Writes")
        self.Throws = resolver.find("Throws")

        # Exception-related action elements and flows
        self.TryUnit = resolver.find("TryUnit")
        self.CatchUnit = resolver.find("CatchUnit")
        self.FinallyUnit = resolver.find("FinallyUnit")
        self.ExceptionFlow = resolver.find("ExceptionFlow")
        self.ExitFlow = resolver.find("ExitFlow")

        # Code relationships
        self.Extends = resolver.find("Extends")
        self.Imports = resolver.find("Imports")
        self.HasType = resolver.find("HasType")
        self.HasValue = resolver.find("HasValue")

        # Code values and datatypes
        self.Value = resolver.find("Value")
        self.BooleanType = resolver.find("BooleanType")
        self.IntegerType = resolver.find("IntegerType")
        self.StringType = resolver.find("StringType")
        self.FloatType = resolver.find("FloatType")
        self.VoidType = resolver.find("VoidType")
        self.Datatype = resolver.find("Datatype")

        # KDM annotations
        self.Attribute = resolver.find("Attribute")
        self.Annotation = resolver.find("Annotation")

        # Source package
        self.InventoryModel = resolver.find("InventoryModel")
        self.SourceFile = resolver.find("SourceFile")
        self.SourceRef = resolver.find("SourceRef")
        self.SourceRegion = resolver.find("SourceRegion")

        # Structure package
        self.StructureModel = resolver.find("StructureModel")
        self.SoftwareSystem = resolver.find("SoftwareSystem")
        self.ArchitectureView = resolver.find("ArchitectureView")
        self.Subsystem = resolver.find("Subsystem")
        self.Component = resolver.find("Component")
        self.StructureElement = resolver.find("StructureElement")
        self.StructureRelationship = resolver.find("StructureRelationship")
        self.AggregatedRelationship = resolver.find("AggregatedRelationship")


    # ------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------

    def has_feature(self, obj, feature_name: str):
        """
        Checks whether a PyEcore object has a structural feature.

        Parameters
        ----------
        obj:
            PyEcore model element.

        feature_name:
            Name of the structural feature to check.

        Returns
        -------
        bool
            True if the element supports the requested feature.
        """

        return feature_name in [
            feature.name for feature in obj.eClass.eAllStructuralFeatures()
        ]

    # ------------------------------------------------------------
    # KDM framework elements
    # ------------------------------------------------------------

    def create_segment(self, name: str):
        """
        Creates the root KDM Segment.

        The Segment is the root container of the generated KDM model.
        """

        segment = self.Segment()
        segment.name = name
        return segment

    def create_extension_family(self, name: str):
        """
        Creates a KDM ExtensionFamily.
        """

        family = self.ExtensionFamily()
        family.name = name
        return family

    def create_stereotype(self, name: str, stereotype_type: str):
        """
        Creates a KDM Stereotype.

        The KDM extension package defines a stereotype name and a type string
        indicating the kind of KDM element to which it applies, for example
        ``structure:Component`` or ``structure:Subsystem``.
        """

        stereotype = self.Stereotype()
        stereotype.name = name

        if self.has_feature(stereotype, "type"):
            stereotype.type = stereotype_type
        else:
            self.add_attribute(stereotype, "type", stereotype_type)

        return stereotype

    # ------------------------------------------------------------
    # Code model elements
    # ------------------------------------------------------------

    def create_code_model(self, name: str):
        """
        Creates a KDM CodeModel.
        """

        model = self.CodeModel()
        model.name = name
        return model

    def create_compilation_unit(self, name: str):
        """
        Creates a KDM CompilationUnit.

        In py2kdm, a Python source file is represented as a CompilationUnit
        in the generated CodeModel.
        """

        unit = self.CompilationUnit()
        unit.name = name
        return unit

    def create_class_unit(self, name: str):
        """
        Creates a KDM ClassUnit.
        """

        unit = self.ClassUnit()
        unit.name = name
        return unit

    def create_method_unit(self, name: str):
        """
        Creates a KDM MethodUnit.
        """

        unit = self.MethodUnit()
        unit.name = name
        return unit

    def create_callable_unit(self, name: str):
        """
        Creates a KDM CallableUnit.

        In py2kdm, module-level Python functions are represented as
        CallableUnit elements.
        """

        unit = self.CallableUnit()
        unit.name = name
        return unit

    def create_signature(self, name: str):
        """
        Creates a KDM Signature.

        A Signature is the native KDM representation of a callable or method
        signature. ControlElement.type should reference this Signature.
        """

        signature = self.Signature()
        signature.name = name
        return signature

    def create_parameter_unit(self, name: str):
        """
        Creates a KDM ParameterUnit.
        """

        unit = self.ParameterUnit()
        unit.name = name
        return unit

    def create_storable_unit(self, name: str):
        """
        Creates a KDM StorableUnit.

        StorableUnit is used for variables, fields, temporary return values
        and exception data objects.
        """

        unit = self.StorableUnit()
        unit.name = name
        return unit

    # ------------------------------------------------------------
    # Action elements
    # ------------------------------------------------------------

    def create_action_element(self, name: str, kind: str = None):
        """
        Creates a generic KDM ActionElement.

        Parameters
        ----------
        name:
            Name of the action.

        kind:
            Optional KDM action kind, for example ``return``, ``raise``,
            ``assignment`` or ``function_call``.
        """

        action = self.ActionElement()
        action.name = name

        if kind is not None and self.has_feature(action, "kind"):
            action.kind = kind

        return action

    def create_block_unit(self, name: str = "body", kind: str = "body"):
        """
        Creates a KDM BlockUnit.

        In py2kdm, each MethodUnit or CallableUnit with executable statements
        receives a BlockUnit named ``body``. Executable actions are attached to
        this BlockUnit instead of being attached directly to the callable
        declaration.
        """

        unit = self.BlockUnit()
        unit.name = name

        if kind is not None and self.has_feature(unit, "kind"):
            unit.kind = kind

        return unit

    def create_try_unit(self, name: str = "try"):
        """
        Creates a KDM TryUnit.
        """

        unit = self.TryUnit()
        unit.name = name
        return unit

    def create_catch_unit(self, name: str = "except"):
        """
        Creates a KDM CatchUnit.
        """

        unit = self.CatchUnit()
        unit.name = name
        return unit

    def create_finally_unit(self, name: str = "finally"):
        """
        Creates a KDM FinallyUnit.
        """

        unit = self.FinallyUnit()
        unit.name = name
        return unit

    # ------------------------------------------------------------
    # Action relations
    # ------------------------------------------------------------

    def create_action_relationship(self, target, kind: str):
        """
        Creates a generic ActionRelationship.

        This method is retained as an extension mechanism. Prefer using
        specific KDM relations such as Calls, Creates, Reads, Writes, Throws,
        ExceptionFlow and ExitFlow whenever possible.
        """

        relation = self.ActionRelationship()

        if not self.has_feature(relation, "to"):
            raise ValueError("ActionRelationship does not have feature 'to'.")

        relation.to = target

        if self.has_feature(relation, "kind"):
            relation.kind = kind
        else:
            self.add_attribute(relation, "kind", kind)

        return relation

    def create_calls_relation(self, target):
        """
        Creates an action::Calls relation to the given callable target.
        """

        relation = self.Calls()

        if not self.has_feature(relation, "to"):
            raise ValueError("Calls relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_creates_relation(self, target):
        """
        Creates an action::Creates relation to the given constructed target.
        """

        relation = self.Creates()

        if not self.has_feature(relation, "to"):
            raise ValueError("Creates relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_reads_relation(self, target):
        """
        Creates an action::Reads relation.

        In this generator, Reads targets are expected to be StorableUnit
        elements.
        """

        relation = self.Reads()

        if not self.has_feature(relation, "to"):
            raise ValueError("Reads relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_writes_relation(self, target):
        """
        Creates an action::Writes relation.

        In this generator, Writes targets are expected to be StorableUnit
        elements.
        """

        relation = self.Writes()

        if not self.has_feature(relation, "to"):
            raise ValueError("Writes relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_throws_relation(self, target):
        """
        Creates an action::Throws relation.

        In this generator, the target is a StorableUnit representing the
        thrown exception object, not the exception class itself.
        """

        relation = self.Throws()

        if not self.has_feature(relation, "to"):
            raise ValueError("Throws relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_exception_flow_relation(self, target):
        """
        Creates an action::ExceptionFlow relation from a TryUnit to a CatchUnit.
        """

        relation = self.ExceptionFlow()

        if not self.has_feature(relation, "to"):
            raise ValueError("ExceptionFlow relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_exit_flow_relation(self, target):
        """
        Creates an action::ExitFlow relation from a TryUnit to a FinallyUnit.
        """

        relation = self.ExitFlow()

        if not self.has_feature(relation, "to"):
            raise ValueError("ExitFlow relation does not have feature 'to'.")

        relation.to = target
        return relation

    # ------------------------------------------------------------
    # Code relations
    # ------------------------------------------------------------

    def create_extends_relation(self, target):
        """
        Creates a code::Extends relation.
        """

        relation = self.Extends()

        if not self.has_feature(relation, "to"):
            raise ValueError("Extends relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_imports_relation(self, target):
        """
        Creates a code::Imports relation.
        """

        relation = self.Imports()

        if not self.has_feature(relation, "to"):
            raise ValueError("Imports relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_has_type_relation(self, target):
        """
        Creates a code::HasType relation.
        """

        relation = self.HasType()

        if not self.has_feature(relation, "to"):
            raise ValueError("HasType relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_has_value_relation(self, target):
        """
        Creates a code::HasValue relation.
        """

        relation = self.HasValue()

        if not self.has_feature(relation, "to"):
            raise ValueError("HasValue relation does not have feature 'to'.")

        relation.to = target
        return relation

    # ------------------------------------------------------------
    # KDM attributes
    # ------------------------------------------------------------

    def create_attribute(self, tag: str, value):
        """
        Creates a KDM Attribute.

        Attributes are used only for lightweight traceability or generator
        metadata. Semantic information should be represented through KDM
        metaclasses and relations whenever possible.
        """

        attribute = self.Attribute()
        attribute.tag = str(tag)

        if value is None:
            attribute.value = ""
        else:
            attribute.value = str(value)

        return attribute

    def create_annotation(self, text: str):
        """
        Creates a KDM Annotation element.
        """

        annotation = self.Annotation()

        if self.has_feature(annotation, "text"):
            annotation.text = str(text)

        return annotation

    def add_annotation(self, element, text: str):
        """
        Adds a native KDM Annotation to an annotatable element.
        """

        if text is None:
            return None

        if not self.has_feature(element, "annotation"):
            return None

        annotation = self.create_annotation(text)
        element.annotation.append(annotation)
        return annotation

    def add_attribute(self, element, tag: str, value):
        """
        Adds a KDM Attribute to an element if the element supports attributes.

        None values are ignored. This method does not check duplicates; callers
        that may visit the same element multiple times should implement their
        own ``add_once`` helper.
        """

        if value is None:
            return

        if not self.has_feature(element, "attribute"):
            return

        attribute = self.create_attribute(tag, value)
        element.attribute.append(attribute)

    def add_attributes_from_dict(self, element, metadata: dict):
        """
        Adds several KDM Attribute elements from a dictionary.
        Values equal to None are ignored.
        """

        for tag, value in metadata.items():
            self.add_attribute(element, tag, value)

    # ------------------------------------------------------------
    # Source traceability
    # ------------------------------------------------------------

    def create_source_ref(self, language: str = None, snippet: str = None):
        """
        Creates a KDM SourceRef.
        """

        source_ref = self.SourceRef()

        if language is not None and self.has_feature(source_ref, "language"):
            source_ref.language = language

        if snippet is not None and self.has_feature(source_ref, "snippet"):
            source_ref.snippet = snippet

        return source_ref

    def create_source_region(
        self,
        path: str = None,
        language: str = None,
        start_line=None,
        end_line=None,
        start_position=None,
        end_position=None,
        file_item=None,
    ):
        """
        Creates a KDM SourceRegion.

        SourceRegion preserves traceability from generated KDM elements back
        to source-file locations.
        """

        region = self.SourceRegion()

        if path is not None and self.has_feature(region, "path"):
            region.path = path

        if file_item is not None and self.has_feature(region, "file"):
            region.file = file_item

        if language is not None and self.has_feature(region, "language"):
            region.language = language

        if start_line is not None and self.has_feature(region, "startLine"):
            region.startLine = int(start_line)

        if end_line is not None and self.has_feature(region, "endLine"):
            region.endLine = int(end_line)

        if start_position is not None and self.has_feature(region, "startPosition"):
            region.startPosition = int(start_position)

        if end_position is not None and self.has_feature(region, "endPosition"):
            region.endPosition = int(end_position)

        return region

    def add_source_region(
        self,
        element,
        path: str = None,
        language: str = None,
        start_line=None,
        end_line=None,
        start_position=None,
        end_position=None,
        snippet: str = None,
        file_item=None,
    ):
        """
        Adds a SourceRef with a SourceRegion to a KDM element.

        If only one of start_line or end_line is provided, the other one is
        inferred so that the region covers a single source line.
        """

        # KDM SourceRegion must identify its physical artifact either through
        # a SourceFile reference or through an explicit path. Line numbers alone
        # are not sufficient and produce invalid orphan SourceRegion elements.
        if path is None and file_item is None:
            return

        if start_line is not None and end_line is None:
            end_line = start_line

        if end_line is not None and start_line is None:
            start_line = end_line

        if not self.has_feature(element, "source"):
            return

        source_ref = self.create_source_ref(
            language=language,
            snippet=snippet,
        )

        region = self.create_source_region(
            path=path,
            language=language,
            start_line=start_line,
            end_line=end_line,
            start_position=start_position,
            end_position=end_position,
            file_item=file_item,
        )

        source_ref.region.append(region)
        element.source.append(source_ref)

    # ------------------------------------------------------------
    # Datatypes and values
    # ------------------------------------------------------------

    def create_boolean_type(self, name: str = "bool"):
        """
        Creates a BooleanType.
        """

        datatype = self.BooleanType()
        datatype.name = name
        return datatype

    def create_integer_type(self, name: str = "int"):
        """
        Creates an IntegerType.
        """

        datatype = self.IntegerType()
        datatype.name = name
        return datatype

    def create_string_type(self, name: str = "str"):
        """
        Creates a StringType.
        """

        datatype = self.StringType()
        datatype.name = name
        return datatype

    def create_float_type(self, name: str = "float"):
        """
        Creates a FloatType.
        """

        datatype = self.FloatType()
        datatype.name = name
        return datatype

    def create_void_type(self, name: str = "None"):
        """
        Creates a VoidType.
        """

        datatype = self.VoidType()
        datatype.name = name
        return datatype

    def create_generic_datatype(self, name: str):
        """
        Creates a generic Datatype.
        """

        datatype = self.Datatype()
        datatype.name = name
        return datatype

    def create_value(self, name: str = None, value=None):
        """
        Creates a KDM Value element.
        """

        value_element = self.Value()

        if name is not None and self.has_feature(value_element, "name"):
            value_element.name = str(name)

        if value is not None and self.has_feature(value_element, "value"):
            value_element.value = str(value)

        return value_element

    # ------------------------------------------------------------
    # Inventory model
    # ------------------------------------------------------------

    def create_inventory_model(self, name: str):
        """
        Creates a KDM InventoryModel.
        """

        model = self.InventoryModel()
        model.name = name
        return model

    def create_source_file(
        self,
        name: str,
        path: str,
        language: str = None,
        encoding: str = "UTF-8",
        format_: str = "text",
    ):
        """
        Creates a KDM SourceFile.
        """

        source_file = self.SourceFile()
        source_file.name = name
        source_file.path = path

        if format_ is not None and self.has_feature(source_file, "format"):
            source_file.format = format_

        if language is not None and self.has_feature(source_file, "language"):
            source_file.language = language

        if encoding is not None and self.has_feature(source_file, "encoding"):
            source_file.encoding = encoding

        return source_file

    # ------------------------------------------------------------
    # Structure model elements
    # ------------------------------------------------------------

    def create_structure_model(self, name: str):
        """
        Creates a KDM StructureModel.

        StructureModel contains high-level architectural elements through its
        structureElement containment reference.
        """

        model = self.StructureModel()
        model.name = name
        return model

    def create_software_system(self, name: str):
        """
        Creates a KDM SoftwareSystem.
        """

        element = self.SoftwareSystem()
        element.name = name
        return element

    def create_architecture_view(self, name: str):
        """
        Creates a KDM ArchitectureView.
        """

        element = self.ArchitectureView()
        element.name = name
        return element

    def create_subsystem(self, name: str):
        """
        Creates a KDM Subsystem.
        """

        element = self.Subsystem()
        element.name = name
        return element

    def create_component(self, name: str):
        """
        Creates a KDM Component.
        """

        element = self.Component()
        element.name = name
        return element

    def create_structure_element(self, name: str):
        """
        Creates a generic KDM StructureElement.
        """

        element = self.StructureElement()
        element.name = name
        return element

    def create_structure_relationship(self, source, target):
        """
        Creates a KDM StructureRelationship.

        The KDM 1.4 metamodel defines:
        - from : AbstractStructureElement
        - to   : KDMEntity

        Because 'from' is a Python keyword, this method sets it defensively
        through setattr.
        """

        relation = self.StructureRelationship()

        if not self.has_feature(relation, "from"):
            raise ValueError("StructureRelationship does not have feature 'from'.")

        if not self.has_feature(relation, "to"):
            raise ValueError("StructureRelationship does not have feature 'to'.")

        setattr(relation, "from", source)
        relation.to = target

        return relation

    def create_aggregated_relationship(self, source, target, relations=None):
        """
        Creates a KDM core::AggregatedRelationship.

        The KDM 1.4 Ecore metamodel defines:
        - from    : KDMEntity[1]
        - to      : KDMEntity[1]
        - relation: KDMRelationship[0..*]
        - density : Integer

        The AggregatedRelationship must be contained in the
        aggregatedRelation reference of the KDMEntity that acts as the
        aggregation from-endpoint.
        """

        aggregation = self.AggregatedRelationship()

        if not self.has_feature(aggregation, "from"):
            raise ValueError("AggregatedRelationship does not have feature 'from'.")

        if not self.has_feature(aggregation, "to"):
            raise ValueError("AggregatedRelationship does not have feature 'to'.")

        setattr(aggregation, "from", source)
        aggregation.to = target

        relations = relations or []

        if self.has_feature(aggregation, "relation"):
            for relation in relations:
                if relation is not None:
                    aggregation.relation.append(relation)

        if self.has_feature(aggregation, "density"):
            aggregation.density = len(relations) if relations else 1

        return aggregation
