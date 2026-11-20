from main import trefle


def _image_url(plant: dict) -> str | None:
    image_url = plant.get("image_url")
    if isinstance(image_url, str) and image_url.strip():
        return image_url

    main_image = plant.get("main_image") or {}
    image_url = main_image.get("image_url")
    if isinstance(image_url, str) and image_url.strip():
        return image_url

    main_species = plant.get("main_species") or {}
    image_url = main_species.get("image_url")
    if isinstance(image_url, str) and image_url.strip():
        return image_url

    return None


def _source_url(plant: dict) -> str | None:
    links = plant.get("links") or {}
    source_url = links.get("self")
    if not isinstance(source_url, str) or not source_url:
        return None
    if source_url.startswith("http://") or source_url.startswith("https://"):
        return source_url
    return f"{trefle.TREFLE_BASE_URL}{source_url}"


def serialize_plant_summary(plant: dict) -> dict:
    return {
        "slug": plant.get("slug"),
        "scientific_name": plant.get("scientific_name"),
        "common_name": plant.get("common_name"),
        "family": plant.get("family") or plant.get("family_common_name"),
        "genus": plant.get("genus"),
        "year": plant.get("year"),
        "image_url": _image_url(plant),
        "links": {"self": _source_url(plant)},
    }


def serialize_plant_detail(plant: dict) -> dict:
    care = {}
    for card in trefle.extract_care_cards(plant):
        if card.get("categorical"):
            continue
        label = card.get("label")
        value = card.get("value")
        if label == "Kebutuhan cahaya":
            care["light"] = value
        elif label == "Kelembapan udara":
            care["atmospheric_humidity"] = value
        elif label == "Nutrisi tanah":
            care["soil_nutrients"] = value
        elif label == "Toleransi salinitas":
            care["soil_salinity"] = value
        elif label == "Kelembapan tanah":
            care["soil_humidity"] = value

    growth = (plant.get("main_species") or {}).get("growth") or {}
    bloom_months = growth.get("bloom_months", [])
    if not isinstance(bloom_months, list):
        bloom_months = []
    care["bloom_months"] = bloom_months
    result = serialize_plant_summary(plant)
    result.update({
        "bibliography": plant.get("bibliography"),
        "observations": plant.get("observations"),
        "care": care,
    })
    return result
