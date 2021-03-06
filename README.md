# Streamline Mapping of Landscape Structure: slm  #

The **slm** package provides a set of tools to map landscape structure using topographic streamline tracing. These tools are implemented in Python, OpenCL and OCaml. The main documentation can be found [here](https://cstarknyc.github.io/slm).

***proviso:*** *this is a work in progress*

The git repo here is the main **slm** code base repository. Companion repos house [Jupyter notebooks](https://github.com/cstarknyc/slmnb) and [DTM  data](https://github.com/cstarknyc/slmdata) (lidar digital terrain models).


## What **slm** can do

Capabilities available now or anticipated soon include the ability to:
   - map channels and identify the locations of channel heads
   - visualize patterns of topographic surface flow
   - measure hillslope lengths across a DTM landscape
   - route flow over pit-prone and divergent topography such as alluvial fans
   - carry out GPU-accelerated processing of large DTM data sets
 
 Longer-term goals include:
   - kinematic mapping of surface water flow depth
      - the main aim is to estimate channel inundation and flow geometry in lidar DTMs
      - contrasts with typical GIS methods of DTM flow routing which have no sense of channel flow geometry
   - deployment of these methods in a landscape evolution model
      - will be able to resolve hillslope-channel transitions and approximate channel flow geometry
      - speed will be a challenge

## Code base

**slm** has a code base founded on:
   - [Python 3](https://docs.python.org/3/)
      - development is with [version 3.6.x](https://docs.python.org/3/) on MacOSX
      - several packages are required, notably [Numba](http://numba.pydata.org/), which is used to accelerate preprocessing steps
   - [OpenCL](https://www.khronos.org/opencl/) 
      - accessed from Python using [PyOpenCL](https://documen.tician.de/pyopencl/index.html)
      - development is with [version 1.2](https://www.khronos.org/registry/OpenCL/sdk/1.2/docs/man/xhtml/) on AMD and NVIDIA GPUs
   - [OCaml](https://ocaml.org/)
       - intended to be a fast replacement for the Python component of **slm**
       - porting currently underway
       - will work with common OpenCL code base
   

## Documentation

   - [**slm** hub](https://cstarknyc.github.io/slm)
      - core documentation of **slm** idea, implementation and example results
      - links to Jupyter notebook demos
      - documents the **Python** portion of the code
   - [OpenCL docs](https://cstarknyc.github.io/slm/opencl/index.html)
      - documents the OpenCL kernels and related functions used in **slm** 
      - generated with Doxygen 
   - [OCaml docs](https://cstarknyc.github.io/slm/ocaml)
      - not yet implemented
      - will document the OCaml portion of **slm**



