// A diagnostic kernel using the NVIDIA CUDA Runtime; no model inference here.
#include <cuda_runtime.h>
#include <cstdio>

__global__ void probe_kernel(int *value) { *value = 42; }

int fail(const char *stage, cudaError_t error) {
    std::printf("{\"ok\":false,\"stage\":\"%s\",\"cuda_error\":%d,\"message\":\"%s\"}\n",
                stage, static_cast<int>(error), cudaGetErrorString(error));
    return 1;
}

int main() {
    int runtime = 0, driver = 0, count = 0;
    cudaRuntimeGetVersion(&runtime);
    cudaDriverGetVersion(&driver);
    auto error = cudaGetDeviceCount(&count);
    if (error != cudaSuccess) return fail("device_count", error);
    if (!count) return fail("device_count", cudaErrorNoDevice);
    cudaDeviceProp properties{};
    error = cudaGetDeviceProperties(&properties, 0);
    if (error != cudaSuccess) return fail("device_properties", error);
    int *device_value = nullptr;
    error = cudaMalloc(&device_value, sizeof(int));
    if (error != cudaSuccess) return fail("allocation", error);
    probe_kernel<<<1, 1>>>(device_value);
    error = cudaGetLastError();
    if (error == cudaSuccess) error = cudaDeviceSynchronize();
    int value = 0;
    if (error == cudaSuccess) error = cudaMemcpy(&value, device_value, sizeof(int), cudaMemcpyDeviceToHost);
    cudaFree(device_value);
    if (error != cudaSuccess) return fail("kernel", error);
    std::printf("{\"ok\":%s,\"runtime_version\":%d,\"driver_version\":%d,"
                "\"device\":\"%s\",\"compute_capability\":\"%d.%d\","
                "\"vram_bytes\":%zu,\"kernel_result\":%d}\n",
                value == 42 ? "true" : "false", runtime, driver, properties.name,
                properties.major, properties.minor, properties.totalGlobalMem, value);
    return value == 42 ? 0 : 1;
}
