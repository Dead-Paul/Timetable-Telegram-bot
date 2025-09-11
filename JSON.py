import json
import os

class JSON:
    def __init__(self, filename: str):
        self.__filename = filename
        if not os.path.exists(filename):
            raise FileNotFoundError

    def get(self, key: str) -> str|int|float|bool|dict|list|None:
        with open(self.__filename, 'r', encoding="UTF-8") as json_file:
            try:
                return json.load(json_file)[key]
            except KeyError:
                return None

    def set(self, values: dict[str, str|int|float|bool|dict|list|None]) -> None:
        with open(self.__filename, 'r+', encoding="UTF-8") as json_file:
            json_data = json.load(json_file)
            assert isinstance(json_data, dict)
            json_data.update(values)
            json.dump(json_data, json_file, indent=2, ensure_ascii=False, allow_nan=False)

        