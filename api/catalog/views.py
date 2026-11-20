from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from main import trefle

from .serializers import serialize_plant_detail, serialize_plant_summary


def _error_response(error: trefle.TrefleError) -> Response:
    if isinstance(error, trefle.TrefleNotConfigured):
        code = "trefle_not_configured"
        response_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(error, trefle.TrefleRateLimited):
        code = "trefle_rate_limited"
        response_status = status.HTTP_429_TOO_MANY_REQUESTS
    else:
        code = "trefle_unavailable"
        response_status = status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(
        {"error": {"code": code, "message": error.message}},
        status=response_status,
    )


def _page_number(value: str | None) -> int:
    try:
        page = int(value or 1)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def _sort_plants(plants: list[dict], sort: str) -> list[dict]:
    if sort in ("name_asc", "name_desc"):
        return sorted(
            plants,
            key=lambda plant: (
                plant.get("scientific_name") or plant.get("common_name") or ""
            ).casefold(),
            reverse=sort == "name_desc",
        )
    if sort == "year_asc":
        return sorted(
            plants,
            key=lambda plant: (plant.get("year") is None, plant.get("year") or 0),
        )
    return plants


@api_view(["GET"])
def plant_list(request):
    query = request.query_params.get("q", "").strip()
    sort = request.query_params.get("sort", "name_asc")
    page = _page_number(request.query_params.get("page"))
    try:
        if query:
            plants, meta = trefle.search_plants(query, page=page)
        else:
            plants, meta = trefle.list_plants(page=page)
    except trefle.TrefleError as error:
        return _error_response(error)

    plants = _sort_plants(plants, sort)
    per_page = int(meta.get("per_page") or len(plants) or 1)
    total = meta.get("total")
    has_next = False
    if isinstance(total, int):
        has_next = page * per_page < total
    else:
        has_next = len(plants) == per_page
    return Response({
        "data": [serialize_plant_summary(plant) for plant in plants],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "has_next": has_next,
            "has_previous": page > 1,
        },
    })


@api_view(["GET"])
def plant_detail(request, slug):
    try:
        plant = trefle.get_plant_detail(slug)
    except trefle.TrefleError as error:
        return _error_response(error)
    if plant is None:
        return Response(
            {"error": {"code": "plant_not_found", "message": "Tanaman tidak ditemukan."}},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(serialize_plant_detail(plant))
