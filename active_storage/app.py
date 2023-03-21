import json

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import botocore
import aioboto3
import numpy as np

from .models import RequestData, AllowedReductions, AllowedDatatypes, REDUCERS


app = FastAPI()
security = HTTPBasic()


class S3Exception(Exception):
    """ Custom exception class for catching upstream S3 exception """

    def __init__(self, upstream_response):
        super().__init__(self)
        self.upstream_response = upstream_response


@app.exception_handler(S3Exception)
async def handle_upstream_s3_exception(request, exc: S3Exception):
    """
    Handles request validation errors stemming from the upstream S3 source.
    """
    # Just use the message from the first error
    try:
        aws_err_code = exc.upstream_response['Error']['Code']
        aws_message = exc.upstream_response['Error']['Message']
        aws_resource = exc.upstream_response['Error']['Resource']
        content = {
            'aws_error_code': aws_err_code,
            'aws_error_message': aws_message,
            'aws_target': aws_resource,
        }
    except KeyError: # Some S3-like services have different keys (e.g. ceph's radosgw)
        content = {'aws_error': exc.upstream_response['Error']}

    return JSONResponse(
        content,
        status_code=exc.upstream_response['ResponseMetadata']['HTTPStatusCode'],
        media_type='application/json'
    )



def validate_request(request_data: RequestData):
    """
    Checks that the supplied request data confroms to the API spec
    and tries to provide informative error messages if not.
    """
    dtype = request_data.dtype
    offset = request_data.offset
    n_bytes = AllowedDatatypes[dtype].n_bytes()

    if offset is not None and (offset < 0 or offset % n_bytes != 0):
        msg = ' '.join([
            'Offset parameter must be divisible by number of bytes in dtype',
            f'(i.e. {n_bytes} for dtype {dtype}).',
            f'Given offset = {request_data.offset}',
        ])
        raise HTTPException(status_code=400, detail=msg)
        pass

    elif request_data.order not in ['C', 'F']:
        msg = f"'order' parameter was '{request_data.order}' but must be either 'C' or 'F'"
        raise HTTPException(status_code=400, detail=msg)

    elif request_data.shape is None and request_data.selection is not None:
        msg = 'When providing a selection parameter you must also provide an shape parameter'
        raise HTTPException(status_code=400, detail=msg)

    elif request_data.shape is not None:

        if request_data.selection and len(request_data.shape) != len(request_data.selection):
            raise HTTPException(
                status_code=400,
                detail='Selection parameter list must have same number of elements as shape parameter'
            )

    return


async def upstream_s3_response(request_data: RequestData, credentials: HTTPBasicCredentials):

    s3_session = aioboto3.Session()

    async with s3_session.client(
        's3', 
        endpoint_url=request_data.source, 
        aws_access_key_id=credentials.username, 
        aws_secret_access_key=credentials.password
    ) as s3_client:

        try:
            #Use the HTTP Range header to fetch only the bytes we need
            bytes_start = request_data.offset or 0
            bytes_end = '' #Use empty string to default to open-ended range request
            if request_data.size is not None:
                #Subtract 1 since bytes ranges are inclusive
                bytes_end = bytes_start + request_data.size - 1
            response = await s3_client.get_object(
                Bucket=request_data.bucket, 
                Key=request_data.object, 
                Range=f'bytes={bytes_start}-{bytes_end}'
            )
            response_data = await response['Body'].read()
        
        except botocore.exceptions.ClientError as err:
            raise S3Exception(err.response)

        except botocore.exceptions.EndpointConnectionError as err:
            # Create S3-like error dict to be parsed by exception handler
            error_info = {
                'Error': {
                    'Code': 'UpstreamSourceNotFound',
                    'Message': 'Could not connect to configured S3 source',
                    'Resource': 'N/A'
                },
                'ResponseMetadata': {
                    'HTTPStatusCode': 404
                }
            }
            raise S3Exception(error_info)        
        return response_data #Bytes format



class OctetStreamResponse(Response):
    """ 
    Dummy response class which ensures that OpenAPI generated 
    schema have correct response type for handler functions 
    """
    media_type = 'application/octet-stream'



@app.post('/v1/{operation_name}/', response_class=OctetStreamResponse)
async def handler(
        operation_name: AllowedReductions, 
        request_data: RequestData,
        credentials=Depends(security)
    ):

    # Will return a relevant HTTP response to the client if request is invalid
    validate_request(request_data)

    # Look up required function in dict
    reduction_func = REDUCERS[operation_name]

    # Fetch upstream response and wrangle it into desired format
    response_data = await upstream_s3_response(request_data, credentials)
    response_arr = np.frombuffer(response_data, dtype=request_data.dtype)

    shape = request_data.shape or response_arr.shape
    try:
        response_arr = response_arr.reshape(shape, order=request_data.order)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err).replace('array', 'chunk'))

    if request_data.selection is not None:
        slices = tuple(slice(*s) for s in request_data.selection)
        response_arr = response_arr[slices]

    # Perform main reduction
    result = reduction_func(response_arr)

    response_headers = {
        'x-activestorage-dtype': str(result.dtype),
        'x-activestorage-shape': json.dumps(list(result.shape)),
    }

    return Response(
        # Make sure to return result in same bytes order input
        content=result.tobytes(order=request_data.order),
        status_code=200, 
        media_type='application/octet-stream', 
        headers=response_headers
    )

