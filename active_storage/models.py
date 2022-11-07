
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass

from pydantic import BaseModel, Field, constr, conint, conlist
import numpy as np


#Use enum which also subclasses string type so that 
# auto-generated OpenAPI schema can determine allowed dtypes
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
    source: constr(min_length=1)
    bucket: constr(min_length=1)
    object: constr(min_length=1)
    dtype: AllowedDatatypes
    offset: Optional[conint(ge=0)]
    #Use example kwarg for OpenAPI generated schema
    size: Optional[conint(ge=1)] = Field(example=1024)
    shape: Optional[conlist(item_type=conint(ge=1), min_items=1)]
    order: str = 'C'
    selection: Optional[List[conlist(item_type=conint(ge=0), max_items=3, min_items=3)]]


#Use enum which also subclasses string type so that 
# auto-generated OpenAPI schema can determine allowed dtypes
class AllowedReductions(str, Enum):
    """ Reduction operations supported by active storage proxy """
    sum = 'sum'
    min = 'min'
    max = 'max'
    count = 'count'
    select = 'select'
    mean = 'mean'

REDUCERS = {
    'sum': lambda arr: np.sum(arr, dtype=arr.dtype),
    'min': np.min,
    'max': np.max,
    'count': lambda arr: np.prod(arr.shape, dtype = 'int64'), #Force specific dtype
    'select': lambda arr: arr,
    'mean': lambda arr: (np.sum(arr) / np.size(arr)).astype(arr.dtype),
}
