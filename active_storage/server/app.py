from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import itertools
import botocore
import aioboto3
import numpy as np

from .models import RequestData, OperationType, AllowedDatatypes, ALLOWED_OPERATIONS


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
    Handles request validation errors by producing S3-style XML documents.

    https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html#RESTErrorResponses
    https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html#ErrorCodeList
    """
    # Just use the message from the first error
    aws_err_code = exc.upstream_response['Error']['Code']
    aws_message = exc.upstream_response['Error']['Message']
    aws_resource = exc.upstream_response['Error']['Resource']
    content = "\n".join([
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<Error>",
            f" <Code>{aws_err_code}</Code>",
            f" <Message>{aws_message}</Message>",
            f" <Resource>{aws_resource}</Resource>",
        "</Error>"
    ])
    return Response(content, status_code=exc.upstream_response['ResponseMetadata']['HTTPStatusCode'], media_type='application/xml')



def validate_request(request_data: RequestData):

    """
    Checks that the supplied request data confroms to the API spec and tries to provide informative error messages if not. \
    """

    if request_data.dtype not in AllowedDatatypes.__members__.keys():
        raise HTTPException(status_code=400, detail=f'Invalid data type ({request_data.dtype})')

    elif request_data.offset is not None and (request_data.offset < 0 or request_data.offset % AllowedDatatypes[request_data.dtype].n_bytes() != 0):
        raise HTTPException(status_code=400, detail=f'Offset parameter must be a positive integer and be divisible by number of bytes in dtype (usually 4 or 8). Given offset = {request_data.offset}')

    elif request_data.size is not None and request_data.size < 1:
        raise HTTPException(status_code=400, detail=f"Size parameter must be a positive integer. Given size = {request_data.size}")

    elif request_data.order not in ['C', 'F']:
        raise HTTPException(status_code=400, detail=f"'order' parameter was '{request_data.order}' but must be either 'C' or 'F'")

    elif request_data.shape is None and request_data.selection is not None:
        raise HTTPException(status_code=400, detail='When providing a selection parameter you must also provide an shape parameter')

    elif request_data.shape is not None:
        
        if any(map(lambda x: x < 1, request_data.shape)):
            raise HTTPException(status_code=400, detail='All elements in shape list must be positive integers')

        if request_data.selection:

            if len(request_data.shape) != len(request_data.selection):
                raise HTTPException(status_code=400, detail='Selection parameter list must have same number of elements as shape parameter')
            elif any(map(lambda s: len(s) != 3, request_data.selection)):
                raise HTTPException(status_code=400, detail='Each element of selection parameter list must have exactly 3 elements formatted as [start, stop, stride]')

    return



def generate_bytes_ranges(request_data: RequestData) -> list[str]:

    """ 
    Calculates the appropriate bytes range to request from upstream depending on (offset, size, selection) fields in request data.
    When a 'selection' is specified, the naive version implemented here creates a separate byte range header for each index in the selection.
    -> This should be improved in future versions.
    """

    if request_data.selection is None:
        #Return single byte range specified by offset and size parameters
        bytes_start = request_data.offset or 0
        bytes_end = '' #Use empty str so open-ended range expression 'bytes=0-' is default
        if request_data.size:
            bytes_end = bytes_start + request_data.size - 1 #Subract 1 since HTTP range is inclusive
        return [f'bytes={bytes_start}-{bytes_end}']
    
    else:
        #Convert selection specification into linear indices since each chunk of bytes returned by s3 is 1D
        expanded_ranges = [list(range(*s)) for s in request_data.selection]
        multi_dim_indices = list(itertools.product(*expanded_ranges))
        linear_indices = list(np.ravel_multi_index(idx, request_data.shape) for idx in multi_dim_indices)
        
        #Convert to bytes values
        n_bytes = AllowedDatatypes[request_data.dtype].n_bytes()
        bytes_indices = [i * n_bytes for i in linear_indices]

        #Trim down bytes range
        if request_data.offset:
            bytes_indices = filter(lambda x: request_data.offset < x, bytes_indices)
        if request_data.size:
            bytes_end = (0 or request_data.offset) + request_data.size - 1 #Subract 1 since HTTP range is inclusive
            bytes_indices = filter(lambda x: x < bytes_end, bytes_indices)

        #Retrun HTTP Range header compliant string for each bytes range
        return [f'bytes={i}-{i+n_bytes-1}' for i in bytes_indices]



async def upstream_s3_response_generator(
        request_data: RequestData,
        credentials: HTTPBasicCredentials = Depends(security),
    ):

    """
    Returns an async generator for the upstream request data.
    """

    bytes_ranges = generate_bytes_ranges(request_data)
    s3_session = aioboto3.Session()
    async with s3_session.client('s3', endpoint_url=request_data.source, aws_access_key_id=credentials.username, aws_secret_access_key=credentials.password) as s3_client:

            try:

                if len(bytes_ranges) == 1:
                    #Read response in chunks using iter_chunks method of S3 StreamingResponse
                    response = await s3_client.get_object(Bucket=request_data.bucket, Key=request_data.obj_path, Range=bytes_ranges[0])
                    async for chunk in response['Body'].iter_chunks(chunk_size=1024*8):
                        yield chunk

                elif len(bytes_ranges) > 1:
                    #Otherwise, make one upstream request per byte range and return these as a generator
                    for b in bytes_ranges: 
                        response = await s3_client.get_object(Bucket=request_data.bucket, Key=request_data.obj_path, Range=b)
                        data = await response['Body'].read()
                        yield data
        
            except botocore.exceptions.ClientError as err:
                raise S3Exception(err.response)
            
            except botocore.exceptions.EndpointConnectionError as err:
                #Create S3-like error dict to be parsed by exception handler
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




def make_reducer_handler(operation: OperationType) -> callable:

    """ Constructs a handler function for each allowed api operation """

    async def handler(request_data: RequestData, credentials = Depends(security)):

        validate_request(request_data) #Will return a relevant HTTP response to the client if request is invalid

        #Can't use generator funcs with Depends(...) so call here instead
        upstream_response = upstream_s3_response_generator(request_data, credentials)

        #Process upstream response in chunks
        result = None
        async for chunk in upstream_response:
            np_arr = np.frombuffer(chunk, dtype=request_data.dtype)
            chunk_result = operation.chunk_reducer(np_arr)
            if result is None:
                result = chunk_result #Only happens for first chunk to be processed
            else:
                result = operation.aggregator(chunk_result, result)

        response_headers = {
            'x-activestorage-dtype': str(result.dtype),
            'x-activestorage-shape': str(list(result.shape)),
        }

        return Response(content=result.tobytes(), status_code=200, media_type='application/octet-stream', headers=response_headers)

    return handler



class OctetStreamResponse(Response):
    """ Dummy response class which ensures that OpenAPI generated schema have correct response type for handler functions """
    media_type = 'application/octet-stream'


#Loop through allowed operations and generate api endpoints
for op in ALLOWED_OPERATIONS.values():
    app.add_api_route(
        f'/v1/{op.name}/',
        make_reducer_handler(op),
        methods=['POST'],
        response_class=OctetStreamResponse,
    )
