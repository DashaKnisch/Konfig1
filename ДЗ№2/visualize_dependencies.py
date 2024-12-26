import os
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
import subprocess
import re

def read_config(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config

def groupId_to_path(groupId):
    return groupId.replace('.', '/')

def download_pom(repository_url, groupId, artifactId, version):
    group_path = groupId_to_path(groupId)
    pom_url = f"{repository_url.rstrip('/')}/{group_path}/{artifactId}/{version}/{artifactId}-{version}.pom"
    try:
        with urllib.request.urlopen(pom_url) as response:
            pom_data = response.read()
        return pom_data
    except Exception as e:
        # print(f"Ошибка при загрузке POM-файла по адресу {pom_url}: {e}")
        return None

def parse_pom(pom_data, repository_url, properties, parent_chain, dependency_management):
    root = ET.fromstring(pom_data)
    namespace = {'m': 'http://maven.apache.org/POM/4.0.0'}

    # Собираем свойства из секции properties
    props = {}
    properties_element = root.find('m:properties', namespace)
    if properties_element is not None:
        for prop in properties_element:
            prop_name = prop.tag.replace('{http://maven.apache.org/POM/4.0.0}', '')
            prop_value = prop.text.strip() if prop.text else ''
            props[prop_name] = prop_value

    properties = {**properties, **props}

    # Собираем управление зависимостями из dependencyManagement
    dep_mgmt_element = root.find('m:dependencyManagement', namespace)
    if dep_mgmt_element is not None:
        dependencies_element = dep_mgmt_element.find('m:dependencies', namespace)
        if dependencies_element is not None:
            for dep in dependencies_element.findall('m:dependency', namespace):
                dep_groupId = resolve_property(dep.find('m:groupId', namespace).text.strip(), properties)
                dep_artifactId = resolve_property(dep.find('m:artifactId', namespace).text.strip(), properties)
                dep_version = dep.find('m:version', namespace)
                dep_version = resolve_property(dep_version.text.strip(), properties) if dep_version is not None else None
                key = f"{dep_groupId}:{dep_artifactId}"
                dependency_management[key] = dep_version

    # Обрабатываем родительский POM, если есть
    parent = root.find('m:parent', namespace)
    if parent is not None:
        parent_groupId = parent.find('m:groupId', namespace).text.strip()
        parent_artifactId = parent.find('m:artifactId', namespace).text.strip()
        parent_version = parent.find('m:version', namespace).text.strip()

        parent_key = f"{parent_groupId}:{parent_artifactId}:{parent_version}"
        if parent_key not in parent_chain:
            parent_chain.add(parent_key)
            parent_pom_data = download_pom(repository_url, parent_groupId, parent_artifactId, parent_version)
            if parent_pom_data is not None:
                # Исправление здесь: распаковываем три значения, игнорируя dependencies
                properties, dependency_management, _ = parse_pom(parent_pom_data, repository_url, properties, parent_chain, dependency_management)

    # Собираем зависимости
    dependencies = []
    for dep in root.findall('.//m:dependencies/m:dependency', namespace):
        groupId = dep.find('m:groupId', namespace)
        artifactId = dep.find('m:artifactId', namespace)
        version = dep.find('m:version', namespace)
        scope = dep.find('m:scope', namespace)
        optional = dep.find('m:optional', namespace)
        if groupId is not None and artifactId is not None:
            dep_groupId = resolve_property(groupId.text.strip(), properties)
            dep_artifactId = resolve_property(artifactId.text.strip(), properties)
            if version is not None:
                dep_version = resolve_property(version.text.strip(), properties)
            else:
                # Пытаемся получить версию из dependencyManagement
                key = f"{dep_groupId}:{dep_artifactId}"
                dep_version = dependency_management.get(key)
            dep_scope = resolve_property(scope.text.strip(), properties) if scope is not None else None
            dep_optional = resolve_property(optional.text.strip(), properties) if optional is not None else None
            # Пропускаем тестовые и опциональные зависимости
            if dep_scope == 'test' or dep_optional == 'true':
                continue
            # Пропускаем зависимости без версии
            if dep_version is None:
                # Можно добавить предупреждение, если нужно
                # print(f"Предупреждение: Зависимость {dep_groupId}:{dep_artifactId} не имеет версии и будет пропущена.")
                continue
            dependencies.append((dep_groupId, dep_artifactId, dep_version))
    return properties, dependency_management, dependencies

def resolve_property(value, properties):
    # Функция для замены переменных в строке на соответствующие значения из свойств
    pattern = re.compile(r'\$\{([^}]+)\}')
    while True:
        match = pattern.search(value)
        if not match:
            break
        prop_name = match.group(1)
        prop_value = properties.get(prop_name, '')
        value = value[:match.start()] + prop_value + value[match.end():]
    return value

def build_dependency_graph(package, repository_url, edges, visited, depth, max_depth, properties, dependency_management):
    if depth > max_depth:
        return
    groupId, artifactId, version = package
    key = f"{groupId}:{artifactId}:{version}"
    if key in visited:
        return
    visited.add(key)
    pom_data = download_pom(repository_url, groupId, artifactId, version)
    if pom_data is None:
        return
    parent_chain = set()
    properties, dependency_management, dependencies = parse_pom(pom_data, repository_url, properties, parent_chain, dependency_management)
    for dep in dependencies:
        dep_key = f"{dep[0]}:{dep[1]}:{dep[2]}"
        edges.add((key, dep_key))
        build_dependency_graph(dep, repository_url, edges, visited, depth + 1, max_depth, properties, dependency_management)

def write_dot_file(edges, output_dot_file):
    with open(output_dot_file, 'w', encoding='utf-8') as f:
        f.write('digraph dependencies {\n')
        for edge in edges:
            from_node = edge[0].replace(':', '\\n')
            to_node = edge[1].replace(':', '\\n')
            f.write(f'    "{from_node}" -> "{to_node}";\n')
        f.write('}\n')

def main():
    if len(sys.argv) < 2:
        print("Использование: python visualize_dependencies.py <config_file>")
        sys.exit(1)
    config_file = sys.argv[1]
    config = read_config(config_file)
    graphviz_program_path = config.get('graphviz_program_path')
    package_name = config.get('package_name')
    output_file_path = config.get('output_file_path')
    max_depth = int(config.get('max_depth', 3))
    repository_url = config.get('repository_url')

    if not all([graphviz_program_path, package_name, output_file_path, repository_url]):
        print("Отсутствуют необходимые параметры в конфигурационном файле")
        sys.exit(1)

    # Проверяем наличие программы Graphviz
    if not os.path.isfile(graphviz_program_path):
        print(f"Программа Graphviz не найдена по пути {graphviz_program_path}")
        sys.exit(1)

    # Парсим имя пакета в формат groupId, artifactId, version
    try:
        groupId, artifactId, version = package_name.split(':')
    except ValueError:
        print("Неверный формат имени пакета. Ожидается 'groupId:artifactId:version'")
        sys.exit(1)

    edges = set()
    visited = set()
    properties = {}
    dependency_management = {}
    build_dependency_graph((groupId, artifactId, version), repository_url, edges, visited, 0, max_depth, properties, dependency_management)

    if not edges:
        print("Не удалось построить граф зависимостей. Возможно, пакет не имеет зависимостей или произошла ошибка при парсинге.")
        sys.exit(1)

    # Пишем DOT-файл
    output_dot_file = output_file_path + '.dot'
    write_dot_file(edges, output_dot_file)

    # Генерируем PNG с помощью Graphviz
    try:
        subprocess.run([graphviz_program_path, '-Tpng', output_dot_file, '-o', output_file_path + '.png'], check=True)
        print("Граф успешно сгенерирован и сохранён в файл", output_file_path + '.png')
    except Exception as e:
        print("Ошибка при генерации графа:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()