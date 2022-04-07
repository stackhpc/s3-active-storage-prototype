import typing as t

import numpy as np


class Reducer(t.Callable[[np.ndarray], np.number]):
    """
    Model for validating a reducer given as a string.
    """
    REDUCERS = {
        "max": np.amax,
        "min": np.amin,
        # Prevent sum from using a dtype with increased precision
        "sum": lambda arr: np.sum(arr, dtype = arr.dtype),
        # Always return counts as int64
        "count": lambda arr: np.prod(arr.shape, dtype = np.int64),
    }

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("must be a string")
        try:
            return cls.REDUCERS[v]
        except KeyError:
            raise ValueError(f"unsupported reduction '{v}'")


class NumericDataType(np.number):
    """
    Model for validating a numpy datatype given as a string.
    """
    DATATYPES = {
        "int32": np.int32,
        "int64": np.int64,
        "uint32": np.uint32,
        "uint64": np.uint64,
        "float32": np.float32,
        "float64": np.float64,
    }

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("must be a string")
        try:
            return cls.DATATYPES[v]
        except KeyError:
            raise ValueError(f"unsupported dtype '{v}'")
