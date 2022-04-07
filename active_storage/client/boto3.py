import dataclasses
import json
import re
import typing as t
from urllib.parse import urlsplit

from botocore.auth import AUTH_TYPE_MAPS, S3SigV4Auth
from botocore.awsrequest import create_request_object, prepare_request_dict
from botocore.httpsession import URLLib3Session


@dataclasses.dataclass
class S3ActiveStorageProxyInfo:
    """
    Class containing information about an S3 active storage proxy.
    """
    #: The scheme used by the active storage proxy when talking to the upstream S3
    upstream_scheme: str
    #: The network location (host:port) used by the active storage proxy when talking
    #: to the upstream S3
    upstream_netloc: str
    #: The regex to use to strip the reducer and parameters from an object path
    path_regex: re.Pattern


class S3ActiveStorageProxyDiscovery:
    """
    Object for coordinating the discovery of information about S3 active storage proxies.
    """
    WELL_KNOWN_ENDPOINT = "/.well-known/s3-active-storage"

    def __init__(self):
        self._proxies = {}

    def _compile_path_regex(self, well_known_data: t.Dict[str, t.Any]) -> re.Pattern:
        """
        Compiles a regex for stripping the path prefix for the supported operations
        and datatypes of an S3 active storage endpoint.
        """
        reducers = "|".join(well_known_data["available_reducers"])
        datatypes = "|".join(well_known_data["supported_datatypes"])
        return re.compile(f"^/((({reducers})/({datatypes}))|obj)")

    def proxy_info(self, url: str) -> t.Optional[S3ActiveStorageProxyInfo]:
        """
        Returns the S3 active storage proxy information associated with the given URL,
        if the S3 endpoint supports it.
        """
        url_parts = urlsplit(url)
        if url_parts.netloc not in self._proxies:
            # Send a request to the .well-known endpoint using botocore's native method
            session = URLLib3Session()
            request_dict = {
                "url_path": self.WELL_KNOWN_ENDPOINT,
                "query_string": "",
                "method": "GET",
                "headers": { "Content-Type": "application/json" },
                "body": b""
            }
            prepare_request_dict(request_dict, f"{url_parts.scheme}://{url_parts.netloc}")
            request = create_request_object(request_dict)
            response = session.send(request.prepare())
            if 200 <= response.status_code < 300:
                well_known_data = json.loads(response.content)
                upstream_parts = urlsplit(well_known_data['s3_endpoint'])
                self._proxies[url_parts.netloc] = S3ActiveStorageProxyInfo(
                    upstream_parts.scheme,
                    upstream_parts.netloc,
                    self._compile_path_regex(well_known_data)
                )
            else:
                self._proxies[url_parts.netloc] = None
        return self._proxies[url_parts.netloc]

    @classmethod
    def instance(cls) -> 'S3ActiveStorageProxyDiscovery':
        """
        Returns the singleton instance of the discovery service.
        """
        if not hasattr(cls, "__instance__"):
            cls.__instance__ = cls()
        return cls.__instance__


class S3ActiveStorageV4Auth(S3SigV4Auth):
    """
    Custom authenticator for use with S3 active storage.
    """
    SIGNATURE_VERSION = "s3v4-activestorage"

    def _canonical_object_url(self, proxy_url: str) -> str:
        """
        Translates a proxy URL into the URL for the canonical object.
        """
        proxy_info = S3ActiveStorageProxyDiscovery.instance().proxy_info(proxy_url)
        if proxy_info:
            proxy_parts = urlsplit(proxy_url)
            canonical_parts = proxy_parts._replace(
                scheme = proxy_info.upstream_scheme,
                netloc = proxy_info.upstream_netloc,
                path = proxy_info.path_regex.sub("", proxy_parts.path)
            )
            return canonical_parts.geturl()
        else:
            return proxy_url

    def add_auth(self, request):
        # Temporarily replace the proxy URL with the canonical object URL for signing
        proxy_url = request.url
        request.url = self._canonical_object_url(proxy_url)
        super().add_auth(request)
        request.url = proxy_url

    @classmethod
    def register(cls):
        """
        Registers the custom signature version with botocore.
        """
        AUTH_TYPE_MAPS[cls.SIGNATURE_VERSION] = cls
