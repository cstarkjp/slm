"""
Segment downstream.
"""

import pyopencl as cl
import pyopencl.array
import numpy as np
import os
os.environ['PYTHONUNBUFFERED']='True'
import warnings

from streamlines import pocl
from streamlines.useful import vprint, pick_seeds

__all__ = ['hillslope_lengths']

pdebug = print

def hillslope_lengths( cl_src_path, which_cl_platform, which_cl_device, info_dict, 
                       mask_array, uv_array,
                       mapping_array, label_array, traj_length_array, verbose ):
        
    """
    Measure mean (half) hillslope lengths.
    
    Args:
        cl_src_path (str):
        which_cl_platform (int):
        which_cl_device   (int):
        info_dict (numpy.ndarray):
        mask_array  (numpy.ndarray):
        uv_array (numpy.ndarray):
        mapping_array (numpy.ndarray):
        label_array   (numpy.ndarray):
        traj_length_array (numpy.ndarray):
        verbose (bool):
        
    """
    vprint(verbose,'Measuring hillslope lengths...')
    
    # Prepare CL essentials
    platform, device, context= pocl.prepare_cl_context(which_cl_platform,which_cl_device)
    queue = cl.CommandQueue(context,
                            properties=cl.command_queue_properties.PROFILING_ENABLE)
    cl_files = ['essentials.cl','updatetraj.cl','computestep.cl',
                'rungekutta.cl','lengths.cl']
    cl_kernel_source = ''
    for cl_file in cl_files:
        with open(os.path.join(cl_src_path,cl_file), 'r') as fp:
            cl_kernel_source += fp.read()
            
    # Trace downstream from midslope pixels to thin channel pixels, 
    #   measuring streamline distance; double and scale by pixel width 
    #   to estimate hillslope length for that midslope pixel
    pad = info_dict['pad_width']
    is_midslope = info_dict['is_midslope']
    pixel_size = info_dict['pixel_size']
    flag = is_midslope
    seed_point_array = pick_seeds(mask=mask_array, map=mapping_array, flag=flag, pad=pad)
    if ( seed_point_array.shape[0]!=traj_length_array.shape[0] ):
        print('\nMismatched midslope point arrays: ',
              seed_point_array.shape,traj_length_array.shape)
    array_dict = { 'seed_point': {'array': seed_point_array, 'rwf': 'RO'},
                   'mask':       {'array': mask_array,       'rwf': 'RO'}, 
                   'uv':         {'array': uv_array,         'rwf': 'RO'}, 
                   'mapping':    {'array': mapping_array,    'rwf': 'RO'}, 
                   'label':      {'array': label_array,      'rwf': 'RO'}, 
                   'traj_length':{'array': traj_length_array,'rwf': 'RW'} }
    info_dict['n_seed_points'] = seed_point_array.shape[0]
    
    # Do integrations on the GPU
    cl_kernel_fn = 'hillslope_lengths'
    pocl.gpu_compute(device, context, queue, cl_kernel_source,cl_kernel_fn, 
                     info_dict, array_dict, verbose)
    
    # Scale by pixel size and by two because we measured only half lengths
    traj_length_array *= pixel_size*2
    # Done
    vprint(verbose,'...done')  
