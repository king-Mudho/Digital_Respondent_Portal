from rest_framework.pagination import PageNumberPagination

PAGE_SIZE_OPTIONS = (10, 20, 50, 100, 200)  # what the screens offer under "Show"


class StandardPagination(PageNumberPagination):
    """20 a page unless the screen asks otherwise (?page_size=), up to 200: the
    registers let people choose how many rows to see."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = max(PAGE_SIZE_OPTIONS)
