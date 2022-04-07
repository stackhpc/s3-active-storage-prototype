import numpy as np


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
