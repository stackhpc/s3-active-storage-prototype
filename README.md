# s3-active-storage

This project implements simple reductions on S3 objects containing numeric binary data.
By implementing these reductions in the storage system the volume of data that needs to be
transferred is vastly reduced, leading to faster computations.

The work is funded by the
[ExCALIBUR project](https://www.metoffice.gov.uk/research/approach/collaboration/spf/excalibur)
and is done in collaboration with the
[University of Reading](http://www.reading.ac.uk/).

## Concepts

The S3 active storage proxy supports the application of reductions to S3 objects that contain
numeric binary data. These reductions are specified by modifying the path that is used to access
the object.

The S3 active storage proxy does not attempt to infer the datatype - it must be told the datatype
to use based on knowledge that the client already has about the S3 object.

For example, if the original object has the following URL:

```
http[s]://s3.example.org/my-bucket/path/to/object
```

Then S3 active storage proxy endpoints take the form:

```
http[s]://s3-proxy.example.org/{reducer}/{datatype}/my-bucket/path/to/object
```

The currently supported datatypes are `int32`, `int64`, `uint32`, `uint64`, `float32` and `float64`.

The currently supported reducers are `max`, `min`, `sum` and `count`.

`max`, `min` and `sum` return the result using the same datatype as specified in the request.
`count` always returns the result as `int64`.

## Caveats

This is a very early-stage project, and as such supports limited functionality.

In particular, the following are known limitations which we intend to address:

  * Only unsigned requests are currently supported, e.g. public buckets only
  * Error handling and reporting is minimal
  * No support for extents, e.g. start, count, stride
    * However `Range GET` requests should work, with the requested operation performed
      on only the data returned from the upstream
  * No support for missing data
  * No support for compressed or encrypted objects

## Install and run the demo server

First, clone the repository:

```sh
git clone https://github.com/stackhpc/s3-active-storage.git
cd s3-active-storage
```

Start the local [Minio](https://min.io/) server which serves the test data:

```sh
./bin/minio-run
```

The Minio server will run until it is stopped using `Ctrl+C`.

In a separate terminal, install and run the S3 active storage proxy using a Python virtualenv:

```sh
# Create a virtualenv
python -m venv ./venv
# Install the S3 active storage package and dependencies
pip install git+https://github.com/stackhpc/configomatic.git
pip install -e .
# Install an ASGI server to run the application
pip install uvicorn
# Launch the application
uvicorn --reload active_storage.server:app
```

### Using boto3 to query active storage endpoints

As mentioned above, the S3 active storage proxy currently only supports unsigned requests
so `boto3` must be configured appropriately:

```python
import boto3
from botocore import UNSIGNED
from botocore.client import Config

s3 = boto3.resource(
    "s3",
    endpoint_url = "http://localhost:8000",
    config = Config(signature_version = UNSIGNED)
)
```

Then use the reducer as the bucket and add the datatype to the key. Here we use
[numpy](https://numpy.org/) to interpret the raw binary data returned by the S3 proxy:

```python
import numpy as np

for dtype in ["int32", "int64", "uint32", "uint64", "float32", "float64"]:
    print(f"dtype: {dtype}")

    obj = s3.Object("count", f"{dtype}/sample-data/data-{dtype}.dat")
    data = obj.get()["Body"].read()
    arr = np.frombuffer(data, dtype = np.int64)
    print(f"  count data: {arr}")

    for reducer in ["max", "min", "sum"]:
        obj = s3.Object(reducer, f"{dtype}/sample-data/data-{dtype}.dat")
        data = obj.get()["Body"].read()
        arr = np.frombuffer(data, dtype = getattr(np, dtype))
        print(f"  {reducer} data: {arr}")
```
