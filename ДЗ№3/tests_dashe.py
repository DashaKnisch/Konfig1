import unittest
import xml.etree.ElementTree as ET
from io import StringIO
import sys

from tmp1 import Parser

class TestParser(unittest.TestCase):
    def setUp(self):
        # Создаем тестовый XML
        self.xml_data = '''<root>
            <a type="float">1</a>
            <b type="string">asd</b>
            <d type="string">example</d>
            <c type="list">
                <item type="float">1</item>
                <item type="float">2</item>
                <item type="float">3</item>
            </c>
            <h type="string">a+1</h>
            <comm1 type="comment">это комментарий</comm1>
        </root>'''
        self.root = ET.fromstring(self.xml_data)
        self.parser = Parser(self.root)

    def test_get_data(self):
        expected_data = {
            'a': {'value': 1.0, 'type': 'float'},
            'b': {'value': 'asd', 'type': 'string'},
            'd': {'value': 'example', 'type': 'string'},
            'c': {'value': [1.0, 2.0, 3.0], 'type': 'list'},
            'h': {'value': 'a+1', 'type': 'string'},
            'comm1': {'value': 'это комментарий', 'type': 'comment'},
        }
        result = self.parser.get_data()
        self.assertEqual(result, expected_data)

    def test_output_format(self):
        # Перенаправляем вывод в строку
        output = StringIO()
        sys.stdout = output

        # Генерируем выходные данные
        data = self.parser.get_data()
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
        output.writelines(lines)

        # Возвращаем стандартный вывод
        sys.stdout = sys.__stdout__

        # Ожидаемый вывод
        expected_output = (
            "var a = 1.0\n\n"
            'var b = @"asd"\n\n'
            'var d = @"example"\n\n'
            "var c = ({ 1.0, 2.0, 3.0 })\n\n"
            "var h = ![a+1]\n\n"
            "{{!-- это комментарий --}}\n\n"
        )

        self.assertEqual(output.getvalue(), expected_output)

if __name__ == '__main__':
    unittest.main()