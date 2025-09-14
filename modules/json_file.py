import os
import json
from typing import Any

class JSON_File:
    def __init__(self, filename: str):
        self.__filename = filename
        if not os.path.exists(filename):
            raise FileNotFoundError

    def get(self, key: str) -> Any:
        with open(self.__filename, 'r', encoding="UTF-8") as json_file:
            return json.load(json_file).get(key)

    def set(self, values: dict[str, Any]) -> None:
        with open(self.__filename, 'r+', encoding="UTF-8") as json_file:
            json_data = json.load(json_file)
            assert isinstance(json_data, dict)
            json_data.update(values)
            json_file.seek(0)
            json.dump(json_data, json_file, indent=2, ensure_ascii=False, allow_nan=False)
            json_file.truncate()

if __name__ == "__main__":
    exit()
