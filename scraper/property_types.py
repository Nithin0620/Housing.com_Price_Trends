PROPERTY_TYPE_MAP = {
    "buy": {
        1: "Apartment",
        2: "Independent House",
        38: "Villa",
    },
    "rent": {
        2: "1 BHK",
        3: "2 BHK",
        4: "3 BHK",
    },
}


def get_property_name(product, type_id):
    mapping = PROPERTY_TYPE_MAP.get(product, {})
    return mapping.get(type_id)
