"""
Miscellaneous useful functions for PyOpenCL code
"""

import numpy as np
# Needs GDAL. Had issues with 2.2.0 and had to do:
#    pip install gdal==2.1.3
from osgeo import gdal
import pandas as pd
from scipy.ndimage.morphology import binary_dilation, generate_binary_structure
from pympler.asizeof import asizeof
import os
os.environ['PYTHONUNBUFFERED']='True'
import sys

__all__ = ['Data', 'Info', 'get_bbox','check_sizes', 'prepare_data',
           'read_geotiff','write_geotiff','npamem','true_size','neatly','vprint',
           'create_seeds','pick_seeds','compute_stats','dilate']

pdebug = print

class Data():    
    def __init__(self, info=None, bbox=None, pad=0,
                 mask_array      = None,
                 uv_array        = None,
                 mapping_array   = None,
                 traj_stats_df   = None,
                 sla_array       = None,
                 slc_array       = None,
                 slt_array       = None,
                 hsl_array       = None ):
#     self.print('Preparing data...',end='')  
#     self.verbose  = verbose
        if bbox is not None:
            bbox = [bbox[0]-pad,bbox[1]+pad,bbox[2]-pad,bbox[3]+pad]
            bounds_grid = np.index_exp[bbox[0]:(bbox[1]+1), bbox[2]:(bbox[3]+1)]
            bounds_slx  = np.index_exp[bbox[0]:(bbox[1]+1), bbox[2]:(bbox[3]+1),:]
        else:
            bounds_grid = np.index_exp[:,:]
            bounds_slx  = np.index_exp[:,:,:]
        # Copying is essential here, because slicing only creates views,
        #   and we want to generate new arrays that can be monkeyed with
        #   without having to worry about the source arrays being affected
        self.mask_array    = mask_array[bounds_grid].copy()
        self.mapping_array = mapping_array[bounds_grid].copy()
        if uv_array is not None:
            self.uv_array  = uv_array[bounds_slx].copy()
        else:
            self.uv_array  = None
        if sla_array is not None:
            self.sla_array = sla_array[bounds_slx].copy()
        else:
            self.sla_array  = None
        if slc_array is not None:
            self.slc_array = slc_array[bounds_slx].copy()
        else:
            self.slc_array  = None
        if slt_array is not None:
            self.slt_array = slt_array[bounds_slx].copy()
        else:
            self.slt_array  = None
        self.traj_stats_df = traj_stats_df
        self.bounds_grid = bounds_grid
        self.bounds_slx  = bounds_slx
        self.count_array = None
        self.link_array = None
        self.label_array = None
        self.channel_label_array = None
        self.hillslope_labels = None
        self.traj_label_array = None
        self.traj_length_array = None
        if hsl_array is not None:
            self.hsl_array = hsl_array[bounds_slx].copy()
        else:
            self.hsl_array = None
#     self.print('done')

class Info():    
    def __init__(self, state, trace, pixel_size, mapping=None, n_seed_points=None):
        self.state   = state
        self.trace   = trace
        self.mapping = mapping

        if mapping is not None:
            self.do_measure_hsl_from_ridges = mapping.do_measure_hsl_from_ridges
        else:
            self.do_measure_hsl_from_ridges = False
        self.segmentation_threshold = np.uint32(0)
        self.channel_threshold      = np.uint32(0)

        if trace.max_length==np.float32(0.0):
            max_length = np.finfo(numpy.float32).max
        else:
            max_length = trace.max_length
        max_n_steps = np.uint32(trace.max_length/trace.integrator_step_factor)
        if trace.interchannel_max_n_steps==0:
            interchannel_max_n_steps = max_n_steps
        else:
            interchannel_max_n_steps = trace.interchannel_max_n_steps
        self.max_n_steps   = np.uint32(max_n_steps)
         
        seed_point_density = np.float32(trace.subpixel_seed_point_density)
        subpixel_seed_span = 1-1.0/seed_point_density
        subpixel_seed_step = subpixel_seed_span/max(seed_point_density, 1.0)
        
        self.debug                       = np.bool8(state.debug)
        self.verbose                     = np.bool8(state.gpu_verbose)
        self.n_trajectory_seed_points    = np.uint32(trace.n_trajectory_seed_points)
        self.n_seed_points               = np.uint32(0)
        self.n_padded_seed_points        = np.uint32(0)
        self.do_shuffle                  = np.bool8(trace.do_shuffle_seed_points)
        self.shuffle_rng_seed            = np.uint32(trace.shuffle_rng_seed)
        self.downup_sign                 = np.float32(np.nan)
        self.gpu_memory_limit_pc         = np.uint32(state.gpu_memory_limit_pc)
        self.n_work_items                = np.uint32(state.n_work_items)
        self.chunk_size_factor           = np.uint32(state.chunk_size_factor)
        self.max_time_per_kernel         = np.float32(state.max_time_per_kernel)
        self.integrator_step_factor      = np.float32(trace.integrator_step_factor)
        self.max_integration_step_error  = np.float32(trace.max_integration_step_error)
        self.adjusted_max_error          = 0.85*np.sqrt(trace.max_integration_step_error)
        self.integration_halt_threshold  = np.float32(trace.integration_halt_threshold)
        self.max_length                  = np.float32(max_length/pixel_size)
        self.pixel_size                  = np.float32(pixel_size)
        self.trajectory_resolution       = np.uint32(trace.trajectory_resolution)
        self.seeds_chunk_offset          = np.uint32(0)
        self.subpixel_seed_point_density = np.uint32(trace.subpixel_seed_point_density)
        self.subpixel_seed_halfspan      = np.float32(subpixel_seed_span/2.0)
        self.subpixel_seed_step          = np.float32(subpixel_seed_step)
        self.jitter_magnitude            = np.float32(trace.jitter_magnitude)
        self.interchannel_max_n_steps    = np.uint32(interchannel_max_n_steps)
        
        self.left_flank_addition = 2147483648
        flags = [
            'is_channel',         # 1
            'is_thinchannel',     # 2
            'is_interchannel',    # 4
            'is_channelhead',     # 8
            'is_channeltail',     # 16
            'is_majorconfluence', # 32
            'is_minorconfluence', # 64
            'is_majorinflow',     # 128
            'is_minorinflow',     # 256
            'is_leftflank',       # 512
            'is_rightflank',      # 1024
            'is_midslope',        # 2048
            'is_ridge',           # 4028
            'was_channelhead',    # 8196
            'is_subsegmenthead',  # 16384
            'is_loop',            # 32768
            'is_blockage'         # 65536
            ]
        [setattr(self,flag,np.uint(2**idx)) for idx,flag in enumerate(flags)]

    def set_xy(self, nx,ny, pad, bbox=None):
        self.bbox = bbox        
        # essentials.cl...
        self.pad_width = pad
        # not used in CL codes
        self.nx = nx
        self.ny = ny
        # essentials.cl, jittertrajectory.cl, segment.cl, writearray.cl...
        # useful.py...
        self.nx_padded = self.nx+self.pad_width*2
        self.ny_padded = self.ny+self.pad_width*2

    def set_thresholds(self,segmentation_threshold=None, channel_threshold=None):
        if segmentation_threshold is not None:        
            self.segmentation_threshold = segmentation_threshold
        if channel_threshold is not None:
            self.channel_threshold = channel_threshold
                    
def get_bbox(array):
    # True for each column that has an element>0, false for columns with all zeros
    cols = np.any(array, axis=0)
    # True for each row that has an element>0, false for rows with all zeros
    rows = np.any(array, axis=1)
    # Get index spans where elements>0
    x_min, x_max = np.where(rows)[0][[0,-1]]
    y_min, y_max = np.where(cols)[0][[0,-1]]
    # Return as bbox tuple
    return (x_min,x_max, y_min,y_max), (x_max+1-x_min), (y_max+1-y_min)

def check_sizes(nx,ny,array_dict):
    for ad_item in array_dict.items():
        array_name = ad_item[0]
        if array_name not in ('seed_point','traj_length'):
            array = ad_item[1]['array']
            if array.shape[0]!=nx or array.shape[1]!=ny:
                # raise ValueError
                pdebug('Array "{0}" size {1} vs mismatches info {2}'
                                 .format(array_name, array.shape, (nx,ny)) )

def read_geotiff(path, filename):
    """
    Read GeoTIFF file.
    Assumes file contains a single-band 2d grid of equal x-y dimension pixels.

    Args:
        path (str): Path to folder containing GeoTIFF file to be read
        filename (str): GeoTIFF filename
    
    Raises:
        ValueError if file cannot be opened for reading
        
    Returns:
        numpy.ndarray, float: Numpy array of GeoTIFF grid, size (in meters) 
                                of a grid pixel
    """          
    fullpath_filename = os.path.join(path,filename)
    tiff=gdal.Open(fullpath_filename)
    if tiff is None:
        raise ValueError('Cannot open GeoTIFF file "{}" for reading'
                         .format(fullpath_filename))
    geotransform = tiff.GetGeoTransform()
    x_easting_bottomleft  = geotransform[0]
    y_northing_bottomleft = geotransform[3]+geotransform[5]
    pixel_size = geotransform[1]
    vprint('DTM GeoTIFF coordinate "geotransform":',geotransform)
    if not np.isclose(pixel_size,geotransform[5]*(-1),rtol=1e-3):
        raise ValueError(
            'Pixel x={0} and y={1} dimensions not equal in "{2}":'
            .format(pixel_size, (-1)*geotransform[5], fullpath_filename)
            +' cannot handle non-square pixels' )
    return (tiff.GetRasterBand(1).ReadAsArray().astype(np.float32), 
            pixel_size, geotransform)
        
def write_geotiff(path, filename, array):
    """
    Write GeoTIFF file.
    Assumes file contains a single-band 2d grid of equal x-y dimension pixels.

    Args:
        path (str): Path to folder containing GeoTIFF file to be read
        filename (str): GeoTIFF filename
        numpy.ndarray, float: Numpy array of GeoTIFF grid, size (in meters) 
                                of a grid pixel
    
    Raises:
        ValueError if file cannot be opened for writing
    """          
    # TBD
    pass
        
def npamem(obj, name=None):
    if name is None:
        array = obj
        return '{0:x} = {1}'.format(array.__array_interface__['data'][0],
                                    neatly(asizeof(array))  )
    else:
        array = getattr(obj,name)
        return '{0} @ {1:x} = {2}'.format(name,
                                    array.__array_interface__['data'][0],
                                    neatly(asizeof(array))  )

def true_size(subobject):
    """
    TBD
    """
    # For semi-obscure reasons, Pympler does better if we enquire about a hard copy of the object
    try:
        sizeof = asizeof(subobject.copy())
    except:
        sizeof = asizeof(subobject)            
    return sizeof
    
def neatly(byte_size):
    """Returns a human readable string reprentation of bytes"""
    units=['B ','kB','MB','GB']  # Note: actually MiB etc
    for unit in units:
        if byte_size>=1024:
            byte_size = byte_size/1024.0
        else:
            break
    if unit=='GB':
        return str(int(0.5+10*byte_size)/10)+unit
    else:
        return str(int(0.5+byte_size))+unit

def vprint(verbose, *args, **kwargs):
    """
    Wrapper for print() with verbose flag to suppress output if desired
    
    Args:
        verbose  (bool): turn printing on or off
        *args (str): print() function args
        **kwargs (str): print() function keyword args
    """
    if verbose:
        print(*args, **kwargs, flush=True)
        # Try to really force this line to print before the GPU prints anything
        sys.stdout.flush()

def create_seeds(mask, pad, n_work_items, n_seed_points=None,
                 do_shuffle=True, rng_seed=1, verbose=False):
    """
    Generate seed points for tracing of streamline trajectories.   
        
    Returns:
        numpy.ndarray: seed point array   
        int: n_seed_points  
        int: n_padded_seed_points  
    """    
    vprint(verbose,'Generating seed points...', end='')
    seed_point_array = ((np.argwhere(~mask).astype(np.float32)-pad))
    # Randomize seed point sequence to help space out memory accesses by kernel instances
    if do_shuffle:
        vprint(verbose,'shuffling...', end='')
        np.random.seed(rng_seed)
        np.random.shuffle(seed_point_array)
    # Truncate if we only want to visualize a subset of streamlines across the DTM
    if n_seed_points is not None and n_seed_points>0:
        seed_point_array = seed_point_array[:n_seed_points].astype(np.float32)
    else:
        n_seed_points = seed_point_array.shape[0]

    pad_length = (np.uint32(np.round(
                    n_seed_points/n_work_items+0.5))*n_work_items-n_seed_points)
    n_padded_seed_points = n_seed_points+pad_length
    if pad_length>0:
        vprint(verbose,'padding for {0} CL work items/group: {1}->{2}...'
                .format(n_work_items, n_seed_points,n_padded_seed_points ), end='')
    else:
        vprint(verbose,'no padding needed...', end='')
    vprint(verbose,'done')
    return seed_point_array.copy(), n_seed_points, n_padded_seed_points

def pick_seeds(mask=None, map=None, flag=None, pad=None):
    """
    Generate a vector array of seed points to send to the GPU/OpenCl device
    
    Args:
        mask (numpy.ndarray): pixel mask array
        map (numpy.ndarray):  mapping array (as generated by mapping())
        flag (bool): binary flag ORed with mapping array to pick seed pixels
        pad (int): grid boundary padding with in pixels
    
    Returns:
        numpy.ndarray: seed point array
    """
    if mask is None and map is not None:
        seed_point_array = (np.argwhere((map & flag)>0).astype(np.float32)-pad)
    elif mask is not None and map is None:
        seed_point_array = (np.argwhere(~mask).astype(np.float32)-pad)
    else:
        seed_point_array = (np.argwhere(~mask & ((map & flag)>0)).astype(np.float32)-pad)
    return seed_point_array.copy()
    
def compute_stats(traj_length_array, traj_nsteps_array, pixel_size, verbose):
    """
    Compute streamline integration point spacing and trajectory length statistics 
    (min, mean, max) for the sets of both downstream and upstream trajectories.
    Return them as a small Pandas dataframe table.
    
    Args:
        traj_length_array (numpy.ndarray):
        traj_nsteps_array (numpy.ndarray):
        pixel_size (float):
        verbose (bool):
        
    Returns:
        pandas.DataFrame:  lnds_stats_df
    """
    vprint(verbose,'Computing streamlines statistics')
    lnds_stats = []
    for downup_idx in [0,1]:
        lnds = np.array( [ [ln[0],ln[1],ln[0]/ln[1]] 
                            for ln in (np.stack(
                                 (traj_length_array[:,downup_idx]*pixel_size, 
                                            traj_nsteps_array[:,downup_idx])   ).T) ] )
        lnds_stats += [np.min(lnds,axis=0), np.mean(lnds,axis=0), np.max(lnds,axis=0)]
    lnds_stats_array = np.array(lnds_stats,dtype=np.float32)
    lnds_indexes = [np.array(['downstream', 'downstream', 'downstream', 
                              'upstream', 'upstream', 'upstream']),
                         np.array(['min','mean','max','min','mean','max'])]
    lnds_stats_df = pd.DataFrame(data=lnds_stats_array, 
                                 columns=['l','n','ds'],
                                 index=lnds_indexes)
    vprint(verbose,lnds_stats_df.T)
    return lnds_stats_df

def dilate(array, n_iterations=1, out=None):
    dilation_structure = generate_binary_structure(2, 2)
    return binary_dilation(array, structure=dilation_structure, 
                           iterations=n_iterations, output=out)
