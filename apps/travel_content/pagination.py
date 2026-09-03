"""Travel Content — pagination."""

from rest_framework.pagination import PageNumberPagination


class TravelContentPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 48
