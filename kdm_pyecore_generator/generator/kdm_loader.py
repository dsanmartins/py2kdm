from pathlib import Path
import sys

PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PY2KDM_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PY2KDM_PROJECT_ROOT))


from pyecore.resources import ResourceSet, URI

from py2kdm_common.paths import resolve_from_root


class KDMLoader:
    def __init__(self, ecore_path: str):
        self.ecore_path = ecore_path
        self.resource_set = ResourceSet()
        self.root_package = None

    def load(self):
        resource = self.resource_set.get_resource(URI(self.ecore_path))
        self.root_package = resource.contents[0]

        self.resource_set.metamodel_registry[self.root_package.nsURI] = self.root_package

        return self.resource_set, self.root_package
