from pyecore.resources import ResourceSet, URI


KDM_ECORE_PATH = "metamodels/kdm_1_4.ecore"


def load_kdm_metamodel(ecore_path: str):
    rset = ResourceSet()

    resource = rset.get_resource(URI(ecore_path))
    kdm_root = resource.contents[0]

    rset.metamodel_registry[kdm_root.nsURI] = kdm_root

    return rset, kdm_root


def print_package_info(kdm_root):
    print("=== KDM ROOT PACKAGE ===")
    print("Name:", kdm_root.name)
    print("nsURI:", kdm_root.nsURI)
    print("nsPrefix:", kdm_root.nsPrefix)

    print("\n=== SUBPACKAGES ===")
    for subpkg in kdm_root.eSubpackages:
        print(f"- {subpkg.name}")
        print(f"  nsURI: {subpkg.nsURI}")
        print(f"  nsPrefix: {subpkg.nsPrefix}")
        print(f"  classifiers: {len(subpkg.eClassifiers)}")


def find_classifier(pkg, classifier_name: str):
    for classifier in pkg.eClassifiers:
        if classifier.name == classifier_name:
            return classifier

    for subpkg in pkg.eSubpackages:
        result = find_classifier(subpkg, classifier_name)
        if result is not None:
            return result

    return None


def check_required_classifiers(kdm_root):
    required = [
        "Segment",
        "CodeModel",
        "CompilationUnit",
        "ClassUnit",
        "MethodUnit",
        "CallableUnit",
        "ParameterUnit",
        "StorableUnit",
        "ActionElement",
        "Calls",
        "Extends",
        "Imports",
    ]

    print("\n=== REQUIRED CLASSIFIERS ===")

    for name in required:
        classifier = find_classifier(kdm_root, name)

        if classifier is None:
            print(f"[MISSING] {name}")
        else:
            print(f"[OK] {name}")


if __name__ == "__main__":
    rset, kdm_root = load_kdm_metamodel(KDM_ECORE_PATH)

    print_package_info(kdm_root)
    check_required_classifiers(kdm_root)
