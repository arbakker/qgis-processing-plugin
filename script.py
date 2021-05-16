from enum import Enum


class LsType(Enum):
    provincie = "provincie"
    gemeente = "gemeente"
    woonplaats = "woonplaats"
    weg = "weg"
    postcode = "postcode"
    adres = "adres"
    perceel = "perceel"
    hectometerpaal = "hectometerpaal"
    wijk = "wijk"
    buurt = "buurt"
    waterschapsgrens = "waterschapsgrens"
    appartementsrecht = "appartementsrecht"


def main():
    filterTypes: [LsType] = list(map(lambda x: LsType[x.value], LsType))
    print(len(filterTypes))
    print(filterTypes)
    print(type(LsType))
    print(list(map(lambda x: x.value, filterTypes)))


if __name__ == "__main__":
    main()
