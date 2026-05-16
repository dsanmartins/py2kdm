from pathlib import Path
from pyecore.resources import ResourceSet, URI


KDM_ECORE_PATH = "metamodels/kdm_1_4.ecore"
OUTPUT_PATH = "output/example_project_compilation_unit.kdm.xmi"


def find_classifier(pkg, classifier_name: str):
    for classifier in pkg.eClassifiers:
        if classifier.name == classifier_name:
            return classifier

    for subpkg in pkg.eSubpackages:
        result = find_classifier(subpkg, classifier_name)
        if result is not None:
            return result

    return None


def load_kdm_metamodel(ecore_path: str):
    rset = ResourceSet()
    resource = rset.get_resource(URI(ecore_path))
    kdm_root = resource.contents[0]
    rset.metamodel_registry[kdm_root.nsURI] = kdm_root
    return rset, kdm_root


def main():
    Path("output").mkdir(exist_ok=True)

    rset, kdm_root = load_kdm_metamodel(KDM_ECORE_PATH)

    Segment = find_classifier(kdm_root, "Segment")
    CodeModel = find_classifier(kdm_root, "CodeModel")
    CompilationUnit = find_classifier(kdm_root, "CompilationUnit")

    segment = Segment()
    segment.name = "example_project"

    code_model = CodeModel()
    code_model.name = "example_project_CodeModel"
    segment.model.append(code_model)

    compilation_unit = CompilationUnit()
    compilation_unit.name = "app.py"

    # CodeModel contiene elementos de código mediante 'codeElement'
    code_model.codeElement.append(compilation_unit)

    output_resource = rset.create_resource(URI(OUTPUT_PATH))
    output_resource.append(segment)
    output_resource.save()

    print(f"Modelo KDM con CompilationUnit generado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
