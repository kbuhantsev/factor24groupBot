import json
from pprint import pprint


def read_write_topicks():
    areas = {}

    with open("topics.csv", "r", encoding='utf-8') as fr:
        while True:
            line = fr.readline()
            if not line:
                break
            sublines = line.split(";")
            areas[sublines[0].lower()] = {"ukr_name": sublines[1], "topic": int(sublines[2].strip())}

    pprint(areas)

    with open("topics.json", "w", encoding='utf-8') as fw:
        fw.write(json.dumps(areas,
                            sort_keys=False,
                            indent=4,
                            ensure_ascii=False,
                            separators=(',', ': ')))

    # with open("topics.json", "r", encoding="utf-8") as fr:
    #     topics = json.load(fr)
    #
    # pprint(topics)


if __name__ == "__main__":
    read_write_topicks()