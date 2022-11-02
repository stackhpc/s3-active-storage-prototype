
import pathlib
import s3fs
import numpy as np
from active_storage.models import AllowedDatatypes

s3_fs = s3fs.S3FileSystem(key='minioadmin', secret='minioadmin', client_kwargs={'endpoint_url': 'http://localhost:9000'})
data_dir = pathlib.Path('./testdata')
bucket = pathlib.Path('sample-data')

#Make sure s3 bucket exists
try:
    s3_fs.mkdir(bucket)
except FileExistsError:
    pass

# Create numpy arrays and upload to S3 as bytes
for d in AllowedDatatypes.__members__.keys():
    with s3_fs.open(bucket / f'data-{d}.dat', 'wb') as s3_file:
        s3_file.write(np.arange(10, dtype=d).tobytes())

print("Data upload successful")
