"""Keep private grid responses, including validation failures, out of caches."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException


class NoStoreRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                response = await original(request)
            except RequestValidationError as error:
                response = await request_validation_exception_handler(request, error)
            except HTTPException as error:
                response = await http_exception_handler(request, error)
            response.headers["Cache-Control"] = "no-store"
            return response

        return handler
