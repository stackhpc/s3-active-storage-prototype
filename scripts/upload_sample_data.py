
import os
import pathlib
import s3fs

s3_fs = s3fs.S3FileSystem(key='minioadmin', secret='minioadmin', client_kwargs={'endpoint_url': 'http://localhost:9000'})
data_dir = pathlib.Path('./testdata')
bucket = pathlib.Path('sample-data')

#Make sure s3 bucket exists
try:
    s3_fs.mkdir(bucket)
except FileExistsError:
    pass

#Loop through files on disk and upload to s3 bucket
data_files = os.listdir(data_dir / bucket)
for name in data_files:
    with open(data_dir / bucket / name, 'rb') as f1:
        data = f1.read()
        with s3_fs.open(bucket / name, 'wb') as f2:
            f2.write(data)

bucket_content = s3_fs.ls(bucket)  
if all(str(bucket/file) in bucket_content for file in data_files):
    print("Data upload successful")
else:
    print(bucket_content)