from enum import Enum
from typing import Optional, List, Callable
import numpy as np
from pydantic import BaseModel, Field
from dataclasses import dataclass


#Use enum which also subclasses string type so that auto-generated OpenAPI schema can determine allowed dtypes
class AllowedDatatypes(str, Enum):
    """ Data types supported by active storage proxy """
    int64 = 'int64'
    int32 = 'int32'
    float64 = 'float64'
    float32 = 'float32'
    uint64 = 'uint64'
    uint32 = 'uint32'

    def n_bytes(self):
        """ Returns the number of bytes in the data type """
        return np.dtype(self.name).itemsize


class RequestData(BaseModel):
    source: str
    bucket: str
    obj_path: str
    dtype: AllowedDatatypes
    offset: Optional[int] = 0
    size: Optional[int] = Field(example=1024) #Use example kwarg for OpenAPI generated schema
    shape: Optional[List[int]] = Field(example=[10])
    order: str = 'C'
    selection: Optional[List[List[int]]] = Field(example=[[0, 10, 2]], description='Format: [[start, stop, range], [...]]')


# For each reduction operation that we implement, we need to specify two functions:
# - One which acts on a single chunk to get the desired result (e.g. np.amax for the 'max' operation)
# - Another which combines the result of the first operation from two separate chunks
   
# This second function is required since the correct way to combine individual chunk results is operation 
# dependent e.g. for the 'max' operation we want to re-apply the max function to the list of separate chunk 
# results to get the max over all chunks but for the 'count' operation we can't just re-apply the count 
# operation to a list of chunk results - we need to sum the individual chunk results instead.

@dataclass
class Reducer:
    """ Container to hold functions required for a chunk-wise reduction """
    name: str
    chunk_reducer: Callable
    aggregator: Callable

ALLOWED_OPERATIONS = {
    'sum': Reducer('sum', chunk_reducer = lambda arr: np.sum(arr, dtype=arr.dtype), aggregator = lambda result1, result2: np.sum([result1, result2], dtype=result1.dtype)),
    'min': Reducer('min', chunk_reducer = np.min, aggregator = lambda result1, result2: np.min([result1, result2])),
    'max': Reducer('max', chunk_reducer = np.max, aggregator = lambda result1, result2: np.max([result1, result2])),
    'count': Reducer('count', chunk_reducer = lambda arr: np.prod(arr.shape, dtype = 'int64'), aggregator = lambda result1, result2: np.sum([result1, result2], dtype='int64')), #Sum is the correct aggregator here
    'select': Reducer('select', chunk_reducer = lambda arr: arr, aggregator = lambda result1, result2: np.concatenate([result2, result1], dtype=result1.dtype)),
}