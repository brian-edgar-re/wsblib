"""
Contains a `ProcessRequest` class to process and get a response
from a given route and requested method. Use to process client requests.
"""

import json

import http_pyparser
from typing import List, Tuple, Union

from .route import Route
from .status import status
from .server import Client
from .errors import Error


class RequestData:
    def __init__(
        self,
        parsed_http: http_pyparser.parser.HTTPData,
        remote_addr: tuple,
        parameters: dict
    ):
        self.real_path = parsed_http.real_path

        self.path = parsed_http.path
        self.method = parsed_http.method
        self.version = parsed_http.version
        
        self.host = parsed_http.host
        self.user_agent = parsed_http.user_agent
        self.accept = parsed_http.accept

        self.body = parsed_http.body
        self.headers = parsed_http.headers
        self.cookies = parsed_http.cookies
        self.query = parsed_http.query

        self.remote_addr = remote_addr
        self.parameters = parameters

    def json(self) -> Union[None, dict]:
        """Return body as JSON.

        If None is returned, it means that the request
        does not have a body. This method does not handle exceptions,
        decoding errors will be thrown by the `json` module.

        :return: Body as JSON format or None
        :rtype: Union[None, dict]
        """

        if self.body:
            data = json.loads(self.body)
        else:
            data = None

        return data

    def __repr__(self) -> str:
        return (f'RequestData(real_path="{self.real_path}", path="{self.path}", method="{self.method}", '
                f'version="{self.version}", host="{self.host}", user_agent="{self.user_agent}", '
                f'accept="{self.accept}", body={self.body}, headers={self.headers}, cookies={self.cookies}, '
                f'query={self.query}, remote_addr={self.remote_addr}, parameters={self.parameters})')


class RequestProcessed:
    def __init__(self, route: Union[Route, Error], request: RequestData, use_globals: bool = False) -> None:
        self.route = route
        self.request = request
        self.use_globals = use_globals

        if isinstance(route, Route):
            self.type = 'route'
        elif isinstance(route, Error):
            self.type = 'error'


class ProcessRequest:
    def __init__(self, routes: List[Route], errors_callback: List[Error] = []) -> None:
        self._routes = routes
        self._errors_callback = errors_callback

    def process(self, client: Client) -> RequestProcessed:
        """Process and get or create a response to
        specified path and requested method.

        The HTTP message is obtained by `Client`
        class; the `http_pyparser` library parse this
        and return a class with HTTP data.

        If successful, this method will return an instance
        of `http_pyparser.Response` with the response generated
        to the client and an instance of `RequestData` with the
        request data.

        :param client: A `Client` instance
        :type client: Client
        :return: Return response and request object
        :rtype: RequestProcessed
        """

        # get client request
        message = client.get_message()

        if not message:
            client.destroy()
        else:
            http_parser = http_pyparser.parser.HTTPParser()
            parsed_http = http_parser.parser(message)

            match_route: Route = None

            # checking routes
            for route in self._routes:
                if route.match_route(parsed_http.path):
                    match_route = route
                    break

            remote_addr = client.get_address()
            parameters = route.get_parameters(parsed_http.path)
            request = RequestData(parsed_http, remote_addr, parameters)

            # make route response
            if match_route:
                if route.accept_method(request.method):
                    processed_request = RequestProcessed(route, request)
                else:
                    for error_handle in self._errors_callback:
                        if error_handle.match_status_code(405):
                            processed_request = RequestProcessed(error_handle, request)
                            break
            else:
                for error_handle in self._errors_callback:
                    if error_handle.match_status_code(404):
                        processed_request = RequestProcessed(error_handle, request)
                        break

            return processed_request
