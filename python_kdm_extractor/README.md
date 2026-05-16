# Python KDM Extractor

Este proyecto implementa un primer prototipo de extractor de modelos intermedios para proyectos escritos en Python. El objetivo principal es analizar código fuente Python mediante el módulo nativo `ast` y generar una representación intermedia en formato JSON, que posteriormente pueda ser transformada hacia un modelo compatible con KDM/EMF.

El flujo general de la herramienta es:

```text
Proyecto Python
   ↓
Recorrido de archivos .py
   ↓
Construcción del AST con ast.parse()
   ↓
Extracción mediante visitors
   ↓
Generación de modelo intermedio JSON
   ↓
Futura transformación a KDM/EMF
```

---

## Estructura del proyecto

```text
python-kdm-extractor/
│
├── main.py
├── python_ast_extractor.py
├── example_project/
│   └── user_service.py
└── output/
    └── python_model.json
```

---

# 1. Archivo `main.py`

El archivo `main.py` es el punto de entrada principal de la herramienta. Se encarga de recibir la ruta de un proyecto Python, buscar todos los archivos `.py`, invocar el extractor AST para cada archivo y escribir el resultado final en un archivo JSON.

---

## Constante `IGNORED_DIRS`

```python
IGNORED_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".git",
    ".mypy_cache",
    ".pytest_cache"
}
```

Esta constante define un conjunto de carpetas que deben ser ignoradas durante el recorrido del proyecto.

Se excluyen directorios que no forman parte del código fuente principal, tales como entornos virtuales, cachés de Python, archivos de Git y carpetas temporales de herramientas de análisis.

---

## Método `find_python_files(project_root: Path)`

```python
def find_python_files(project_root: Path):
```

Este método busca recursivamente todos los archivos con extensión `.py` dentro del proyecto indicado.

### Parámetro

| Parámetro | Tipo | Descripción |
|---|---|---|
| `project_root` | `Path` | Ruta raíz del proyecto Python que será analizado. |

### Funcionamiento

El método utiliza:

```python
project_root.rglob("*.py")
```

para recorrer todos los subdirectorios del proyecto y encontrar archivos Python.

Durante el recorrido, ignora los archivos que se encuentren dentro de carpetas incluidas en `IGNORED_DIRS`.

### Retorno

Retorna una lista de objetos `Path`, donde cada elemento corresponde a un archivo Python encontrado.

### Ejemplo de retorno

```python
[
    Path("example_project/user_service.py"),
    Path("example_project/repository/user_repository.py")
]
```

---

## Método `extract_project(project_path: str)`

```python
def extract_project(project_path: str):
```

Este método construye el modelo intermedio completo de un proyecto Python.

### Parámetro

| Parámetro | Tipo | Descripción |
|---|---|---|
| `project_path` | `str` | Ruta del proyecto Python que se desea analizar. |

### Funcionamiento

Primero convierte la ruta recibida en un objeto `Path` absoluto:

```python
project_root = Path(project_path).resolve()
```

Luego inicializa el modelo general del proyecto:

```python
project_model = {
    "projectName": project_root.name,
    "language": "python",
    "files": []
}
```

Después busca todos los archivos `.py` mediante:

```python
python_files = find_python_files(project_root)
```

Para cada archivo encontrado, invoca:

```python
extract_file_model(file_path, project_root)
```

El resultado se agrega a la lista `files` del modelo general.

### Manejo de errores

Si un archivo Python tiene errores de sintaxis, el método captura la excepción `SyntaxError` y agrega una entrada con el error correspondiente.

Ejemplo:

```json
{
    "path": "broken_file.py",
    "error": "SyntaxError: invalid syntax"
}
```

### Retorno

Retorna un diccionario con el modelo completo del proyecto.

### Ejemplo de retorno

```json
{
    "projectName": "example_project",
    "language": "python",
    "files": [
        {
            "path": "user_service.py",
            "imports": [],
            "classes": [],
            "functions": []
        }
    ]
}
```

---

## Método `write_json_model(model: dict, output_path: str)`

```python
def write_json_model(model: dict, output_path: str):
```

Este método escribe el modelo intermedio en un archivo JSON.

### Parámetros

| Parámetro | Tipo | Descripción |
|---|---|---|
| `model` | `dict` | Modelo intermedio generado a partir del proyecto Python. |
| `output_path` | `str` | Ruta donde se guardará el archivo JSON. |

### Funcionamiento

Primero crea la carpeta de salida si no existe:

```python
output_file.parent.mkdir(parents=True, exist_ok=True)
```

Luego escribe el diccionario `model` en formato JSON usando:

```python
json.dump(model, file, indent=4, ensure_ascii=False)
```

La opción `indent=4` permite que el JSON sea legible. La opción `ensure_ascii=False` permite conservar caracteres especiales, como tildes o símbolos propios del español.

### Salida

Genera un archivo como:

```text
output/python_model.json
```

---

## Bloque principal

```python
if __name__ == "__main__":
```

Este bloque permite ejecutar el script desde la terminal.

### Funcionamiento

Primero verifica que el usuario haya entregado una ruta de proyecto:

```python
if len(sys.argv) < 2:
    print("Usage: python main.py <python_project_path>")
    sys.exit(1)
```

Luego toma la ruta entregada:

```python
project_path = sys.argv[1]
```

Extrae el modelo del proyecto:

```python
model = extract_project(project_path)
```

Finalmente, escribe el archivo JSON:

```python
write_json_model(model, "output/python_model.json")
```

---

# 2. Archivo `python_ast_extractor.py`

El archivo `python_ast_extractor.py` contiene la clase encargada de recorrer el AST de cada archivo Python y extraer información estructural y conductual simple.

Utiliza el módulo estándar:

```python
import ast
```

y define un visitor personalizado basado en:

```python
ast.NodeVisitor
```

---

## Clase `PythonASTExtractor`

```python
class PythonASTExtractor(ast.NodeVisitor):
```

Esta clase recorre el árbol de sintaxis abstracta de un archivo Python y construye un modelo intermedio.

Extrae información como:

```text
- Imports
- Clases
- Funciones
- Métodos
- Parámetros
- Atributos
- Variables locales
- Llamadas a funciones o métodos
```

---

## Constructor `__init__(self, file_path: Path, project_root: Path)`

```python
def __init__(self, file_path: Path, project_root: Path):
```

Inicializa el extractor para un archivo Python específico.

### Parámetros

| Parámetro | Tipo | Descripción |
|---|---|---|
| `file_path` | `Path` | Ruta del archivo Python que será analizado. |
| `project_root` | `Path` | Ruta raíz del proyecto. |

### Atributos inicializados

```python
self.file_path = file_path
self.project_root = project_root
```

Guardan la ruta del archivo y la raíz del proyecto.

```python
self.model = {
    "path": str(file_path.relative_to(project_root)),
    "imports": [],
    "classes": [],
    "functions": []
}
```

Inicializa el modelo correspondiente al archivo analizado.

```python
self.current_class = None
self.current_function = None
```

Estas variables permiten mantener contexto durante el recorrido del AST.

Por ejemplo, permiten saber si una asignación corresponde a:

```text
- un atributo de clase
- una variable local dentro de una función
- una variable dentro de un método
```

---

## Método `visit_Import(self, node)`

```python
def visit_Import(self, node):
```

Este método se ejecuta cuando el visitor encuentra una instrucción `import`.

### Ejemplo de código Python

```python
import os
import numpy as np
```

### Información extraída

Para cada importación, agrega una entrada al campo `imports`.

Ejemplo:

```json
{
    "type": "import",
    "module": "numpy",
    "alias": "np"
}
```

### Uso de `generic_visit`

Al final se llama:

```python
self.generic_visit(node)
```

Esto permite que el visitor continúe recorriendo los nodos internos del AST.

---

## Método `visit_ImportFrom(self, node)`

```python
def visit_ImportFrom(self, node):
```

Este método se ejecuta cuando el visitor encuentra una instrucción `from ... import ...`.

### Ejemplo de código Python

```python
from repository.user_repository import UserRepository
```

### Información extraída

Agrega una entrada como:

```json
{
    "type": "from_import",
    "module": "repository.user_repository",
    "name": "UserRepository",
    "alias": null
}
```

Si existe alias, también se registra.

Por ejemplo:

```python
from pandas import DataFrame as DF
```

genera:

```json
{
    "type": "from_import",
    "module": "pandas",
    "name": "DataFrame",
    "alias": "DF"
}
```

---

## Método `visit_ClassDef(self, node)`

```python
def visit_ClassDef(self, node):
```

Este método se ejecuta cuando el visitor encuentra una definición de clase.

### Ejemplo de código Python

```python
class UserService(BaseService):
    pass
```

### Información extraída

Construye un diccionario con:

```python
class_model = {
    "name": node.name,
    "bases": [self._get_name(base) for base in node.bases],
    "methods": [],
    "attributes": [],
    "line": node.lineno
}
```

### Campos extraídos

| Campo | Descripción |
|---|---|
| `name` | Nombre de la clase. |
| `bases` | Lista de clases base o superclases. |
| `methods` | Lista de métodos definidos dentro de la clase. |
| `attributes` | Lista de atributos de clase. |
| `line` | Línea donde se define la clase. |

### Manejo del contexto

El método guarda la clase actual en:

```python
self.current_class = class_model
```

Luego visita el contenido interno de la clase:

```python
self.generic_visit(node)
```

Esto permite que los métodos y atributos encontrados dentro de la clase sean asociados correctamente.

Finalmente agrega la clase al modelo del archivo:

```python
self.model["classes"].append(class_model)
```

---

## Método `visit_FunctionDef(self, node)`

```python
def visit_FunctionDef(self, node):
```

Este método se ejecuta cuando el visitor encuentra una función o método.

### Ejemplo de función global

```python
def validate_user(user):
    return user is not None
```

### Ejemplo de método

```python
class UserService:
    def create_user(self, user):
        pass
```

### Información extraída

Construye un modelo de función:

```python
function_model = {
    "name": node.name,
    "parameters": [arg.arg for arg in node.args.args],
    "calls": [],
    "local_variables": [],
    "line": node.lineno
}
```

### Campos extraídos

| Campo | Descripción |
|---|---|
| `name` | Nombre de la función o método. |
| `parameters` | Lista de parámetros. |
| `calls` | Lista de llamadas realizadas dentro de la función. |
| `local_variables` | Lista de variables locales detectadas. |
| `line` | Línea donde se define la función. |

### Diferencia entre función y método

Si `self.current_class` no es `None`, entonces la función pertenece a una clase y se registra como método:

```python
self.current_class["methods"].append(function_model)
```

Si `self.current_class` es `None`, se registra como función global:

```python
self.model["functions"].append(function_model)
```

---

## Método `visit_AsyncFunctionDef(self, node)`

```python
def visit_AsyncFunctionDef(self, node):
```

Este método procesa funciones asíncronas definidas con `async def`.

### Ejemplo

```python
async def fetch_data():
    pass
```

En esta primera versión, las funciones asíncronas se procesan igual que las funciones normales:

```python
self.visit_FunctionDef(node)
```

Por lo tanto, también se extraen:

```text
- Nombre
- Parámetros
- Llamadas
- Variables locales
- Línea de definición
```

---

## Método `visit_Assign(self, node)`

```python
def visit_Assign(self, node):
```

Este método se ejecuta cuando el visitor encuentra una asignación simple.

### Ejemplos

```python
x = 10
self.repository = UserRepository()
service_name = "user-service"
```

### Información extraída

El método obtiene el nombre de cada destino de asignación:

```python
name = self._get_name(target)
```

Luego decide dónde registrar ese nombre según el contexto.

### Casos

Si la asignación ocurre directamente dentro de una clase, se registra como atributo de clase:

```python
class UserService:
    service_name = "user-service"
```

Resultado:

```json
"attributes": ["service_name"]
```

Si la asignación ocurre dentro de una función o método, se registra como variable local:

```python
def create_user(self):
    user = User()
```

Resultado:

```json
"local_variables": ["user"]
```

Si ocurre dentro de un método y tiene forma:

```python
self.repository = UserRepository()
```

En esta versión se registra dentro de `local_variables` como:

```json
"local_variables": ["self.repository"]
```

---

## Método `visit_AnnAssign(self, node)`

```python
def visit_AnnAssign(self, node):
```

Este método procesa asignaciones con anotaciones de tipo.

### Ejemplos

```python
age: int = 30
name: str
```

Funciona de manera similar a `visit_Assign`, pero para nodos del tipo `AnnAssign`.

### Información extraída

Extrae el nombre del elemento anotado:

```python
name = self._get_name(node.target)
```

Luego lo clasifica como atributo de clase o variable local según el contexto.

---

## Método `visit_Call(self, node)`

```python
def visit_Call(self, node):
```

Este método se ejecuta cuando el visitor encuentra una llamada a función, método o constructor.

### Ejemplos

```python
UserRepository()
validate_user(user)
self.repository.save(user)
```

### Información extraída

Extrae el nombre de la llamada mediante:

```python
call_name = self._get_name(node.func)
```

Si la llamada ocurre dentro de una función o método, se agrega a la lista `calls`.

### Ejemplo de salida

```json
"calls": [
    "UserRepository",
    "self.repository.save",
    "validate_user"
]
```

Este campo es importante porque luego puede mapearse a relaciones de tipo `Calls` en KDM.

---

## Método auxiliar `_get_name(self, node)`

```python
def _get_name(self, node):
```

Este método convierte algunos nodos del AST en nombres legibles. Es una función auxiliar central para poder transformar nodos sintácticos en cadenas de texto comprensibles.

### Casos soportados

#### Caso 1: `ast.Name`

Ejemplo:

```python
x
```

Retorna:

```text
x
```

Código:

```python
if isinstance(node, ast.Name):
    return node.id
```

#### Caso 2: `ast.Attribute`

Ejemplo:

```python
self.repository.save
```

Retorna:

```text
self.repository.save
```

Código:

```python
if isinstance(node, ast.Attribute):
    value = self._get_name(node.value)
    if value:
        return f"{value}.{node.attr}"
    return node.attr
```

#### Caso 3: `ast.Constant`

Ejemplo:

```python
"user-service"
```

Retorna:

```text
user-service
```

Código:

```python
if isinstance(node, ast.Constant):
    return str(node.value)
```

#### Caso 4: `ast.Subscript`

Ejemplo:

```python
users[0]
```

Retorna:

```text
users
```

Código:

```python
if isinstance(node, ast.Subscript):
    return self._get_name(node.value)
```

#### Caso 5: `ast.Call`

Ejemplo:

```python
UserRepository()
```

Retorna:

```text
UserRepository
```

Código:

```python
if isinstance(node, ast.Call):
    return self._get_name(node.func)
```

### Retorno por defecto

Si el nodo no corresponde a ninguno de los casos anteriores, retorna:

```python
None
```

Esto evita registrar nodos complejos que la primera versión todavía no analiza.

---

## Función `extract_file_model(file_path: Path, project_root: Path)`

```python
def extract_file_model(file_path: Path, project_root: Path):
```

Esta función analiza un archivo Python específico y retorna su modelo intermedio.

### Parámetros

| Parámetro | Tipo | Descripción |
|---|---|---|
| `file_path` | `Path` | Ruta del archivo Python que será analizado. |
| `project_root` | `Path` | Ruta raíz del proyecto. |

### Funcionamiento

Primero lee el código fuente:

```python
source_code = file_path.read_text(encoding="utf-8")
```

Luego construye el AST:

```python
tree = ast.parse(source_code)
```

Después crea una instancia del visitor:

```python
extractor = PythonASTExtractor(file_path, project_root)
```

Recorre el árbol:

```python
extractor.visit(tree)
```

Finalmente retorna el modelo generado:

```python
return extractor.model
```

---

# 3. Ejecución de la herramienta

Desde la carpeta raíz del proyecto, ejecutar:

```bash
python main.py example_project
```

También se puede ejecutar sobre cualquier proyecto Python:

```bash
python main.py ruta/al/proyecto_python
```

---

# 4. Salida generada

El resultado se guarda en:

```text
output/python_model.json
```

El JSON generado tiene una estructura como la siguiente:

```json
{
    "projectName": "example_project",
    "language": "python",
    "files": [
        {
            "path": "user_service.py",
            "imports": [],
            "classes": [],
            "functions": []
        }
    ]
}
```

---

# 5. Relación preliminar con KDM

El modelo JSON generado no es todavía KDM, pero actúa como una representación intermedia.

Una posible correspondencia preliminar es:

| Modelo intermedio JSON | Elemento KDM aproximado |
|---|---|
| `projectName` | `Segment` |
| `files` | `CodeModel` / `CompilationUnit` |
| `classes` | `ClassUnit` |
| `methods` | `MethodUnit` |
| `functions` | `CallableUnit` |
| `parameters` | `ParameterUnit` |
| `attributes` | `StorableUnit` |
| `local_variables` | `StorableUnit` |
| `calls` | `Calls` |
| `imports` | Relaciones de dependencia |

---

# 6. Limitaciones de esta primera versión

Esta versión inicial tiene algunas limitaciones importantes:

```text
- No resuelve tipos reales de variables.
- No distingue completamente llamadas internas y externas.
- No resuelve dinámicamente imports.
- No analiza herencia de forma profunda.
- No conserva comentarios ni formato original.
- No genera todavía un archivo KDM en formato XMI.
- No genera todavía modelos EMF.
```

---

# 7. Próximos pasos

Los próximos pasos sugeridos son:

```text
1. Mejorar la resolución de imports.
2. Diferenciar llamadas internas y externas.
3. Identificar relaciones entre clases.
4. Construir un grafo de dependencias.
5. Definir reglas de mapeo desde JSON intermedio hacia KDM.
6. Generar una primera salida XMI compatible con EMF.
```

---

# 8. Objetivo académico del prototipo

Este prototipo busca validar la factibilidad de extraer información estructural y conductual desde proyectos Python usando análisis estático basado en AST.

La representación intermedia resultante permitirá avanzar hacia un proceso de ingeniería inversa dirigido por modelos, donde código fuente Python pueda ser transformado progresivamente en modelos KDM compatibles con herramientas del ecosistema EMF.
