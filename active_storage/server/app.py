from fastapi import FastAPI, Depends, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response, StreamingResponse

import httpx

import numpy as np

from .config import settings
from .models import Reducer, NumericDataType


app = FastAPI()


@app.on_event("startup")
def on_startup():
    """
    Initialises the HTTPX client on startup.
    """
    app.state.client = httpx.AsyncClient()


@app.on_event("shutdown")
async def on_shutdown():
    """
    Closes the HTTPX client on shutdown.
    """
    await app.state.client.aclose()


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(request, exc):
    """
    Handles request validation errors by producing S3-style XML documents.

    https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html#RESTErrorResponses
    https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html#ErrorCodeList
    """
    # Just use the message from the first error
    message = exc.errors()[0]["msg"]
    content = "\n".join([
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<Error>",
            "<Code>InvalidRequest</Code>",
            f"<Message>{message}</Message>",
            f"<Resource>{request['path']}</Resource>",
#            "<RequestId>4442587FB7D0A2F9</RequestId>",
        "</Error>"
    ])
    return Response(content, status_code = 400, media_type = "application/xml")


@app.exception_handler(httpx.HTTPStatusError)
async def handle_upstream_exception(request, exc):
    """
    Handles exceptions from querying the upstream S3 endpoint.
    """
    return Response(
        exc.response.text,
        status_code = exc.response.status_code,
        media_type = exc.response.headers['content-type']
    )


def httpx_client(request: Request):
    """
    Returns the httpx client for the app.
    """
    return request.app.state.client


async def upstream_response(
    request: Request,
    client: httpx.AsyncClient = Depends(httpx_client),
    obj_path: str = Path(...)
):
    """
    Returns a streaming response from the upstream based on the incoming request.
    """
    obj_url = f"{settings.s3_endpoint}/{obj_path}"
    incoming_headers = list(request.headers.items())
    async with client.stream("GET", obj_url, headers = incoming_headers) as response:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            await response.aread()
            raise
        else:
            yield response


@app.get("/{reducer}/{dtype}/{obj_path:path}")
async def reduce(
    reducer: Reducer,
    dtype: NumericDataType,
    upstream_response: httpx.Response = Depends(upstream_response)
):
    """
    Returns the max of the numbers in the specified object.
    """
    result = None
    async for chunk in upstream_response.aiter_bytes():
        if not chunk:
            continue
        nparr = np.frombuffer(chunk, dtype)
        if result is not None:
            nparr = np.append(nparr, result)
        result = reducer(nparr)
    return Response(result.tobytes(), media_type = "application/octet-stream")


@app.get("/obj/{obj_path:path}")
async def obj(upstream_response: httpx.Response = Depends(upstream_response)):
    """
    Returns the content of the object at the given path.
    """
    return StreamingResponse(
        upstream_response.aiter_bytes(),
        status_code = upstream_response.status_code
    )
