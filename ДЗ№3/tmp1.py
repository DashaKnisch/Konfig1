import xml.etree.ElementTree as ET
import argparse


class Parser:
    def __init__(self, root):
        self.root = root
        self.buffer = {}

    def get_data(self) -> dict:
        tmp_data: list = self._parse()["root"]["children"]
        
        for item in tmp_data:
            var_name = list(item.keys())[0]

            attrs = item[var_name]["attributes"]
            match attrs["type"]:
                case "list": 
                    res = []
                    for d in item[var_name]["children"]:
                        res.append(float(d["item"]["value"]))
                    self.buffer[var_name] = {
                        "value": res,
                        "type": "list"
                    }
                
                case "float":
                    self.buffer[var_name] = {
                        "value": float(item[var_name]["value"]),
                        "type": "float"
                    }
                
                case "string":
                    self.buffer[var_name] = {
                        "value": str(item[var_name]["value"]),
                        "type": "string"
                    }
                
                case "comment":
                    # Обработка комментариев
                    self.buffer[var_name] = {
                        "value": str(item[var_name]["value"]),
                        "type": "comment"
                    }

        return self.buffer

    def _parse(self) -> dict:
        return self._element_to_dict(self.root)

    def _element_to_dict(self, element) -> dict:
        element_dict = {}
    
        tag_name = element.tag
        value = element.text.strip() if element.text else None

        if value is not None:
            value = self._determine_type(value)

        if element.attrib:
            element_dict['attributes'] = element.attrib
    
        if value is not None:
            element_dict['value'] = value
        
        children = []
        for child in element:
            children.append(self._element_to_dict(child))
        
        if children:
            element_dict['children'] = children
        
        return {tag_name: element_dict}

    def _determine_type(self, value):
        if value.isdigit():
            return int(value)
        try:
            return float(value)
        except ValueError:
            return value  


def main():
    # Создаем парсер аргументов ком строки
    parser = argparse.ArgumentParser()
    # Добавляем аргументы
    parser.add_argument('--inf', type=str)
    parser.add_argument('--outf', type=str)
    # Парсим аргументы
    args = parser.parse_args()

    # создаем дерево
    tree = ET.parse(args.inf)
    root = tree.getroot()
    p = Parser(root)

    data = p.get_data()

    with open(args.outf, "w") as f:
        lines = []
        for k, v in data.items():
            match v["type"]:
                case "float":
                    lines.append(f"var {k} = {v['value']}\n")
                case "string":
                    tmp = v["value"]
                    if k == "h":  # Обработка тега h
                        lines.append(f"var {k} = ![{tmp}]\n")
                    else:
                        lines.append(f'var {k} = @"{tmp}"\n')
                case "list":
                    line = f"var {k} = ("
                    line += "{ "
                    line += ", ".join(str(x) for x in v["value"])
                    line += " })\n"
                    lines.append(line)
                case "comment":
                    # Обработка комментариев
                    lines.append(f"{{{{!-- {v['value']} --}}}}\n")
            lines.append("\n")
        f.writelines(lines)


if __name__ == "__main__":
    # Запуск основной функции
    main()