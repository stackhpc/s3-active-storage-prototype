#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <errno.h>


void gen_int32()
{
    int values[5] = { 1, 2, 3, 4, 5 };
    FILE *file = fopen("./sample-data/data-int32.dat", "wb");
    fwrite(values, sizeof(values[0]), sizeof(values) / sizeof(values[0]), file);
    fclose(file);
}


void gen_int64()
{
    long values[5] = { 1, 2, 3, 4, 5 };
    FILE *file = fopen("./sample-data/data-int64.dat", "wb");
    fwrite(values, sizeof(values[0]), sizeof(values) / sizeof(values[0]), file);
    fclose(file);
}


void gen_uint32()
{
    unsigned int values[5] = { 1, 2, 3, 4, 5 };
    FILE *file = fopen("./sample-data/data-uint32.dat", "wb");
    fwrite(values, sizeof(values[0]), sizeof(values) / sizeof(values[0]), file);
    fclose(file);
}


void gen_uint64()
{
    unsigned long values[5] = { 1, 2, 3, 4, 5 };
    FILE *file = fopen("./sample-data/data-uint64.dat", "wb");
    fwrite(values, sizeof(values[0]), sizeof(values) / sizeof(values[0]), file);
    fclose(file);
}


void gen_float32()
{
    float values[5] = { 1.0, 2.0, 3.0, 4.0, 5.0 };
    FILE *file = fopen("./sample-data/data-float32.dat", "wb");
    fwrite(values, sizeof(values[0]), sizeof(values) / sizeof(values[0]), file);
    fclose(file);
}


void gen_float64()
{
    double values[5] = { 1.0, 2.0, 3.0, 4.0, 5.0 };
    FILE *file = fopen("./sample-data/data-float64.dat", "wb");
    fwrite(values, sizeof(values[0]), sizeof(values) / sizeof(values[0]), file);
    fclose(file);
}


int main()
{
    if( !mkdir("./sample-data", 0755) || errno == EEXIST )
    {
        gen_int32();
        gen_int64();
        gen_uint32();
        gen_uint64();
        gen_float32();
        gen_float64();
    }
    else
    {
        fprintf(stderr, "Error creating sample-data directory");
        exit(-1);
    }
}
