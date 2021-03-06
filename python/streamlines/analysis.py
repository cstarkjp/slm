"""
---------------------------------------------------------------------

Module providing tools to compute 1d & 2d pdfs, calculate some statistics,
and perform related analyses.

---------------------------------------------------------------------

Requires Python packages/modules:
  -  :mod:`scipy.stats`
  -  :mod:`scipy.signal`
  -  :mod:`sklearn.neighbors`

Imports ``Streamlines`` module :mod:`.kde`

Imports :class:`.Core` class

Imports functions from: :mod:`.useful` module

---------------------------------------------------------------------

.. _sklearn: http://scikit-learn.org/
.. _scipy: https://www.scipy.org/

"""

import numpy as np
from scipy.stats       import gaussian_kde, norm
from scipy.signal      import argrelextrema
from sklearn.neighbors import KernelDensity
import os
from os import environ
environ['PYTHONUNBUFFERED']='True'

from streamlines import kde
from streamlines.core   import Core
from streamlines.useful import vprint

__all__ = ['Analysis','Univariate_distribution','Bivariate_distribution']

pdebug = print

class Analysis(Core):
    """
    Class providing statistics & probability tools to analyze streamline data and its
    probability distributions.
    """
    def __init__(self,state,imported_parameters,geodata,preprocess,trace):
        """
        TBD
        """
        super().__init__(state,imported_parameters) 
        self.state = state
        self.geodata = geodata
        self.preprocess = preprocess
        self.trace = trace
        self.mapping = None
        self.area_correction_factor = 1.0
        self.length_correction_factor = 1.0
        
    def _augment(self, mapping):
        """
        Args:
            mapping (reference):  to :class:`.Mapping` instance
            
        Add a hook to the :class:`.Mapping` class instance
        """
        self.mapping = mapping

    def do(self):
        """
        Analyze streamline count, length distbns etc, generate stats and pdfs
        """
        self.print('\n**Analysis begin**')  
        self.print('Kernel-density estimating marginal PDFs using "{}" kernels'
                   .format(self.marginal_distbn_kde_kernel))
        self.print('Processing using "{}" method'
                   .format(self.marginal_distbn_kde_method))
        if self.do_marginal_distbn_dsla:
            self.compute_marginal_distribn_dsla()
        if self.do_marginal_distbn_usla:
            self.compute_marginal_distribn_usla()
        if self.do_marginal_distbn_dslt:
            self.compute_marginal_distribn_dslt()
        if self.do_marginal_distbn_uslt:
            self.compute_marginal_distribn_uslt()
        if self.do_marginal_distbn_dslc:
            self.compute_marginal_distribn_dslc()
        if self.do_marginal_distbn_uslc:
            self.compute_marginal_distribn_uslc()
#    
#         self.channel_threshold = self.marginal_distribn_dsla.kde.channel_threshold_x
        self.print('Kernel-density estimating joint PDFs using "{}" kernels'
                   .format(self.joint_distbn_kde_kernel))
        self.print('Processing using "{}" method'
                   .format(self.joint_distbn_kde_method))
        if self.do_joint_distribn_dsla_usla:
            self.compute_joint_distribn_dsla_usla()
        if self.do_joint_distribn_usla_uslt:
            self.compute_joint_distribn_usla_uslt()
        if self.do_joint_distribn_dsla_dslt:
            self.compute_joint_distribn_dsla_dslt()
        if self.do_joint_distribn_dslt_dslc:
            self.compute_joint_distribn_dslt_dslc()
        if self.do_joint_distribn_uslt_dslt:
            self.compute_joint_distribn_uslt_dslt()
        if self.do_joint_distribn_usla_uslc:
            self.compute_joint_distribn_usla_uslc()
        if self.do_joint_distribn_dsla_dslc:
            self.compute_joint_distribn_dsla_dslc()
        if self.do_joint_distribn_uslc_dslc:
            self.compute_joint_distribn_uslc_dslc()

        self.print('**Analysis end**\n')  
      
    def extra(self):
        if self.do_compute_elevation_slope_pdfs:
            self.compute_elevation_slope_pdfs()  
    
    def estimate_channel_threshold(self, data, verbose=None):
        """
        TBD
        """
        if verbose is None:
            verbose=self.verbose
        try:
            self.compute_marginal_distribn_dslt(data)
            return self.mpdf_dslt.channel_threshold_x
        except AttributeError as error:
            self.print('Failed to estimate channel threshold:', error)
            return None
        except Exception as error:
            vprint(verbose,'Failed to estimate channel threshold:', repr(error))
            raise
        
    def compute_marginal_distribn(self, x_array,y_array,mask_array=None,
                                  up_down_idx_x=0, up_down_idx_y=0, 
                                  n_hist_bins=None, n_pdf_points=None, 
                                  kernel=None, bandwidth=None, method=None,
                                  logx_min=None, logy_min=None, 
                                  logx_max=None, logy_max=None):
        """
        TBD
        """
        if mask_array is not None:
            tx_array = x_array[~mask_array,up_down_idx_x].astype(dtype=np.float32)
            ty_array = y_array[~mask_array,up_down_idx_y].astype(dtype=np.float32)
        else:
            tx_array = x_array[:,:,up_down_idx_x].astype(dtype=np.float32).ravel()
            ty_array = y_array[:,:,up_down_idx_y].astype(dtype=np.float32).ravel()
        logx_array = np.log(tx_array[(tx_array>0.0) & (ty_array>0.0)])
        logy_array = np.log(ty_array[(tx_array>0.0) & (ty_array>0.0)])
        if method is None:
            method = self.marginal_distbn_kde_method
        if n_hist_bins is None:
            n_hist_bins = self.n_hist_bins
        if n_pdf_points is None:
            n_pdf_points = self.n_pdf_points
        if kernel is None:
            kernel = self.marginal_distbn_kde_kernel
        if bandwidth is None:
            bandwidth = self.marginal_distbn_kde_bandwidth  
        uv_distbn = Univariate_distribution( logx_array=logx_array, logy_array=logy_array,
                                             pixel_size = self.geodata.roi_pixel_size,
                                             method=method, 
                                             n_hist_bins=n_hist_bins,
                                             n_pdf_points=n_pdf_points,
                                             logx_min=logx_min, logy_min=logy_min, 
                                             logx_max=logx_max, logy_max=logy_max,
                                             search_cdf_min = self.search_cdf_min,
                                             search_cdf_max = self.search_cdf_max,
                                             cl_src_path=self.state.cl_src_path, 
                                             cl_platform=self.state.cl_platform, 
                                             cl_device=self.state.cl_device,
                                             debug=self.state.debug,
                                             verbose=self.state.verbose,
                                             gpu_verbose=self.state.gpu_verbose )
        if method=='opencl':
            uv_distbn.compute_kde_opencl(kernel=kernel, bandwidth=bandwidth)
        elif method=='sklearn':
            uv_distbn.compute_kde_sklearn(kernel=kernel, bandwidth=bandwidth)
        elif method=='scipy':
            uv_distbn.compute_kde_scipy(bw_method=self.marginal_distbn_kde_bw_method)
        else:
            raise NameError('KDE method "{}" not recognized'.format(method))
        uv_distbn.find_modes()
        uv_distbn.statistics()
        uv_distbn.locate_threshold()
        return uv_distbn
   
    def compute_marginal_distribn_dsla(self, data=None):
        """
        TBD
        """
        self.print('Computing marginal distribution "dsla"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.sla_array, data.slc_array
        else:
            x_array,y_array = self.trace.sla_array, self.trace.slc_array
            mask_array = None
        up_down_idx_x, up_down_idx_y = 0, 0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_sla_min','pdf_sla_max','pdf_slc_min','pdf_slc_max'])
        self.mpdf_dsla \
            = self.compute_marginal_distribn(x_array,y_array, mask_array,
                                             up_down_idx_x=up_down_idx_x,
                                             up_down_idx_y=up_down_idx_y,
                                             logx_min=logx_min,logy_min=logy_min, 
                                             logx_max=logx_max,logy_max=logy_max)
        self.print('...done')            
        
    def compute_marginal_distribn_usla(self, data=None):
        """
        TBD
        """
        self.print('Computing marginal distribution "usla"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.sla_array, data.slc_array
        else:
            x_array,y_array = self.trace.sla_array, self.trace.slc_array
            mask_array = None
        mask_array      = data.mask_array
        up_down_idx_x, up_down_idx_y = 1, 1
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_sla_min','pdf_sla_max','pdf_slc_min','pdf_slc_max'])
        self.mpdf_usla \
            = self.compute_marginal_distribn(x_array,y_array, mask_array,
                                             up_down_idx_x=up_down_idx_x,
                                             up_down_idx_y=up_down_idx_y,
                                             logx_min=logx_min,logy_min=logy_min, 
                                             logx_max=logx_max,logy_max=logy_max)
        self.print('...done')            
        
    def compute_marginal_distribn_dslt(self, data=None):
        """
        TBD
        """
        self.print('Computing marginal distribution "dslt"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slt_array, data.sla_array
        else:
            x_array,y_array = self.trace.slt_array, self.trace.sla_array
            mask_array = None
        up_down_idx_x, up_down_idx_y = 0, 0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_slt_min','pdf_slt_max','pdf_sla_min','pdf_sla_max'])
        self.mpdf_dslt \
            = self.compute_marginal_distribn(x_array,y_array, mask_array,
                                             up_down_idx_x=up_down_idx_x,
                                             up_down_idx_y=up_down_idx_y,
                                             logx_min=logx_min,logy_min=logy_min, 
                                             logx_max=logx_max,logy_max=logy_max)
        self.print('...done')            
        
    def compute_marginal_distribn_uslt(self, data=None):
        """
        TBD
        """
        self.print('Computing marginal distribution "uslt"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slt_array, data.sla_array
        else:
            x_array,y_array = self.trace.slt_array, self.trace.sla_array
            mask_array = None
        up_down_idx_x, up_down_idx_y = 1, 1
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_slt_min','pdf_slt_max','pdf_sla_min','pdf_sla_max'])
        self.mpdf_uslt \
            = self.compute_marginal_distribn(x_array,y_array, mask_array,
                                             up_down_idx_x=up_down_idx_x,
                                             up_down_idx_y=up_down_idx_y,
                                             logx_min=logx_min,logy_min=logy_min, 
                                             logx_max=logx_max,logy_max=logy_max)
        self.print('...done')            

    def compute_marginal_distribn_dslc(self, data=None):
        """
        TBD
        """
        self.print('Computing marginal distribution "dslc"...')
        
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slc_array, data.sla_array
        else:
            x_array,y_array = self.trace.slc_array, self.trace.sla_array
            mask_array = None
        up_down_idx_x, up_down_idx_y = 0, 0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_slc_min','pdf_slc_max','pdf_sla_min','pdf_sla_max'])
        self.mpdf_dslc \
            = self.compute_marginal_distribn(x_array,y_array, mask_array,
                                             up_down_idx_x=up_down_idx_x,
                                             up_down_idx_y=up_down_idx_y,
                                             logx_min=logx_min,logy_min=logy_min, 
                                             logx_max=logx_max,logy_max=logy_max)
        self.print('...done')            
        
    def compute_marginal_distribn_uslc(self, data=None):
        """
        TBD
        """
        self.print('Computing marginal distribution "uslc"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slc_array, data.sla_array
        else:
            x_array,y_array = self.trace.slc_array, self.trace.sla_array
            mask_array = None
        up_down_idx_x, up_down_idx_y = 1, 1
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_slc_min','pdf_slc_max','pdf_sla_min','pdf_sla_max'])
        self.mpdf_uslc \
            = self.compute_marginal_distribn(x_array,y_array, mask_array,
                                             up_down_idx_x=up_down_idx_x,
                                             up_down_idx_y=up_down_idx_y,
                                             logx_min=logx_min,logy_min=logy_min, 
                                             logx_max=logx_max,logy_max=logy_max)
        self.print('...done')            


    def compute_joint_distribn(self, x_array,y_array, mask_array=None,
                               up_down_idx_x=0, up_down_idx_y=0, 
                               n_hist_bins=None, n_pdf_points=None, 
                               thresholding_marginal_distbn=None,
                               kernel=None, bandwidth=None, method=None,
                               logx_min=None, logy_min=None, 
                               logx_max=None, logy_max=None, 
                               upstream_modal_length=None):
        """
        TBD
        """
        if mask_array is not None:
            tx_array = x_array[~mask_array,up_down_idx_x].copy().astype(dtype=np.float32)
            ty_array = y_array[~mask_array,up_down_idx_y].copy().astype(dtype=np.float32)
        else:
            tx_array = x_array[:,:,up_down_idx_x].copy().ravel().astype(dtype=np.float32)
            ty_array = y_array[:,:,up_down_idx_y].copy().ravel().astype(dtype=np.float32)
        logx_array = np.log(tx_array[(tx_array>0.0) & (ty_array>0.0)])
        logy_array = np.log(ty_array[(tx_array>0.0) & (ty_array>0.0)])
        if method is None:
            method = self.joint_distbn_kde_method
        if n_hist_bins is None:
            n_hist_bins = self.n_hist_bins
        else:
            n_hist_bins = n_hist_bins
        if n_pdf_points is None:
            n_pdf_points = self.n_pdf_points
        if kernel is None:
            kernel = self.joint_distbn_kde_kernel
        if bandwidth is None:
            bandwidth = self.joint_distbn_kde_bandwidth  
        bv_distbn = Bivariate_distribution( logx_array=logx_array, logy_array=logy_array,
                                            pixel_size = self.geodata.roi_pixel_size,
                                            method=method, 
                                            n_hist_bins=n_hist_bins,
                                            n_pdf_points=n_pdf_points,
                                            logx_min=logx_min, logy_min=logy_min, 
                                            logx_max=logx_max, logy_max=logy_max,
                                            cl_src_path=self.state.cl_src_path, 
                                            cl_platform=self.state.cl_platform, 
                                            cl_device=self.state.cl_device,
                                            debug=self.state.debug,
                                            verbose=self.state.verbose,
                                            gpu_verbose=self.state.gpu_verbose )
        
        if method=='opencl':
            bv_distbn.compute_kde_opencl(kernel=kernel, bandwidth=bandwidth)
        elif method=='sklearn':
            bv_distbn.compute_kde_sklearn(kernel=kernel, bandwidth=bandwidth)
        elif method=='scipy':
            bv_distbn.compute_kde_scipy(bw_method=self.joint_distbn_kde_bw_method)
        else:
            raise NameError('KDE method "{}" not recognized'.format(method))

        bv_distbn.find_mode()
        return bv_distbn

    def compute_joint_distribn_dsla_usla(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "dsla_usla"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.sla_array, data.sla_array
        else:
            x_array,y_array = self.trace.sla_array, self.trace.sla_array
            mask_array = None
        up_down_idx_x,up_down_idx_y = 0,1
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_sla_min','pdf_sla_max','pdf_sla_min','pdf_sla_max'])
        self.jpdf_dsla_usla \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')

    def compute_joint_distribn_dsla_dslt(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "dsla_dslt"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slt_array, data.sla_array
        else:
            x_array,y_array = self.trace.slt_array, self.trace.sla_array
            mask_array = None
        up_down_idx_x,up_down_idx_y = 0,0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_sla_min','pdf_sla_max','pdf_slt_min','pdf_slt_max'])
        try:
            mpdf_dsla = self.mpdf_dsla
        except:
            mpdf_dsla = None
        self.jpdf_dsla_dslt \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          thresholding_marginal_distbn=mpdf_dsla,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')

    def compute_joint_distribn_dslt_dslc(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "dslt_dslc"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slt_array, data.slc_array
        else:
            x_array,y_array = self.trace.slt_array, self.trace.slc_array
            mask_array = None
        up_down_idx_x,up_down_idx_y = 0,0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_slt_min','pdf_slt_max','pdf_slc_min','pdf_slc_max'])
        try:
            mpdf_dsla = self.mpdf_dsla
        except:
            mpdf_dsla = None
        self.jpdf_dslt_dslc \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          thresholding_marginal_distbn=mpdf_dsla,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')

    def compute_joint_distribn_usla_uslt(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "usla_uslt"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.sla_array, data.slt_array
        else:
            x_array,y_array = self.trace.sla_array, self.trace.slt_array
            mask_array = None
        up_down_idx_x,up_down_idx_y = 1,1
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_sla_min','pdf_sla_max','pdf_slt_min','pdf_slt_max'])
        self.jpdf_usla_uslt \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')

    def compute_joint_distribn_uslt_dslt(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "uslt_dslt"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slt_array, data.slt_array
        else:
            x_array,y_array = self.trace.slt_array, self.trace.slt_array
            mask_array = None
        up_down_idx_x,up_down_idx_y = 1,0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_slt_min','pdf_slt_max','pdf_slt_min','pdf_slt_max'])
        self.jpdf_uslt_dslt \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')

    def compute_joint_distribn_dsla_dslc(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "dsla_dslc"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.sla_array, data.slc_array
        else:
            x_array,y_array = self.trace.sla_array, self.trace.slc_array
            mask_array = None
        up_down_idx_x,up_down_idx_y = 0,0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_sla_min','pdf_sla_max','pdf_slc_min','pdf_slc_max'])
        try:
            mpdf_dsla = self.mpdf_dsla
        except:
            mpdf_dsla = None
        self.jpdf_dsla_dslc \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          thresholding_marginal_distbn=mpdf_dsla,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')

    def compute_joint_distribn_usla_uslc(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "usla_uslc"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.sla_array, data.slc_array
        else:
            x_array,y_array = self.trace.sla_array, self.trace.slc_array
            mask_array = None
        up_down_idx_x,up_down_idx_y = 1,1
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_sla_min','pdf_sla_max','pdf_slc_min','pdf_slc_max'])
        self.jpdf_usla_uslc \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')

    def compute_joint_distribn_uslc_dslc(self, data=None):
        """
        TBD
        """
        self.print('Computing joint distribution "uslc_dslc"...')
        if data is not None:
            mask_array = data.mask_array
            x_array,y_array = data.slc_array, data.slc_array
        else:
            x_array,y_array = self.trace.slc_array, self.trace.slc_array
            mask_array = None
        up_down_idx_x, up_down_idx_y = 1,0
        (logx_min, logx_max, logy_min, logy_max) \
          = self._get_limits(['pdf_slc_min','pdf_slc_max','pdf_slc_min','pdf_slc_max'])
        self.jpdf_uslc_dslc \
            = self.compute_joint_distribn(x_array,y_array, mask_array,
                                          up_down_idx_x=up_down_idx_x,
                                          up_down_idx_y=up_down_idx_y,
                                          logx_min=logx_min,logy_min=logy_min, 
                                          logx_max=logx_max,logy_max=logy_max)
        self.print('...done')


    def _get_limits(self, attr_list):
        return [np.log(getattr(self,attr)) if hasattr(self,attr) else None 
                for attr in attr_list]
        
        
    def compute_elevation_slope_pdfs(self, bw_method=None,
                                     h_min=None, h_max=None, h_steps=None,
                                     bw_factor_h_midline=None, bw_factor_h_all=None, 
                                     h_midline_max_bound=None,
                                     slope_min=None, slope_max=None, slope_steps=None,
                                     bw_factor_slope=None):
        
        if bw_method is None:
            bw_method = self.pdf_bw_method
        if h_min is None:
            h_min = self.pdf_h_min
        if h_max is None:
            h_max = self.pdf_h_max
        if h_steps is None:
            h_steps = self.pdf_h_steps
        if bw_factor_h_midline is None:
            bw_factor_h_midline = self.pdf_bw_factor_h_midline
        if bw_factor_h_all is None:
            bw_factor_h_all = self.pdf_bw_factor_h_all
        if h_midline_max_bound is None:
            h_midline_max_bound = self.pdf_h_midline_max_bound
        if slope_min is None:
            slope_min = self.pdf_slope_min
        if slope_max is None:
            slope_max = self.pdf_slope_max
        if slope_steps is None:
            slope_steps = self.pdf_slope_steps
        if bw_factor_slope is None:
            bw_factor_slope = self.pdf_bw_factor_slope
        
        self.mapping.midslope_array \
            = (self.mapping.mapping_array 
               & self.mapping.info.is_midslope).copy().astype(np.bool)
        
        h_midline_pts \
            = self.geodata.roi_array[self.mapping.midslope_array[2:-2,2:-2]].ravel()
        h_all_pts \
          = self.geodata.roi_array[~self.geodata.basin_mask_array[2:-2,2:-2]].ravel()
        slope_midline_pts \
          = np.abs(self.preprocess.slope_array[self.mapping.midslope_array].ravel())
        slope_midline_pts \
            = np.concatenate([slope_midline_pts,-slope_midline_pts])
                    
        h_array = np.linspace(h_min,h_max,h_steps)
        slope_array = np.linspace(slope_min,slope_max,(slope_max-slope_min)*slope_steps+1)
        
        h_midline_pdf     = gaussian_kde(h_midline_pts, bw_method=bw_method)
        h_all_pdf         = gaussian_kde(h_all_pts, bw_method=bw_method)
        slope_midline_pdf = gaussian_kde(slope_midline_pts,bw_method=bw_method)
        
        h_midline_pdf.set_bandwidth(h_midline_pdf.factor*bw_factor_h_midline)
        h_all_pdf.set_bandwidth(h_all_pdf.factor*bw_factor_h_all)
        slope_midline_pdf.set_bandwidth(slope_midline_pdf.factor*bw_factor_slope)
        h_midline_pdf.factor
        h_all_pdf.factor
        slope_midline_pdf.factor
        
        h_midline_pdf_array = h_midline_pdf.evaluate(points=h_array)
        h_all_pdf_array = h_all_pdf.evaluate(points=h_array)
        slope_midline_pdf_array = slope_midline_pdf.evaluate(points=slope_array)
        sf = np.max(h_midline_pdf_array)
        
        h_midline_pdf_max1 = np.max(h_midline_pdf_array[h_array>h_midline_max_bound])
        h_midline_pdf_max1_h = h_array[h_midline_pdf_array==h_midline_pdf_max1]
        slope_midline_pdf_max = np.max(slope_midline_pdf_array[slope_array>=10])
        slope_midline_pdf_max_slope \
            = slope_array[slope_midline_pdf_array==slope_midline_pdf_max]
        
        self.h_midline_pdf_array  = h_midline_pdf_array
        self.h_midline_pdf_max1   = h_midline_pdf_max1
        self.h_midline_pdf_max1_h = h_midline_pdf_max1_h
        self.h_all_pdf_array      = h_all_pdf_array
        self.h_array              = h_array
        self.h_pdf_sf             = sf
        self.slope_midline_pdf_array     = slope_midline_pdf_array
        self.slope_midline_pdf_max       = slope_midline_pdf_max
        self.slope_midline_pdf_max_slope = slope_midline_pdf_max_slope
        self.slope_array                 = slope_array
                    
class Univariate_distribution():
    """
    Class for making and recording kernel-density estimate of univariate 
    probability distribution f(x) data and metadata. 
    Provides a method to find the modal average: x | max{f(x}.
    """
    def __init__(self, logx_array=None, logy_array=None, pixel_size=None,
                 method='opencl', 
                 n_hist_bins=2048, n_pdf_points=256, 
                 search_cdf_min=0.95, search_cdf_max=0.99,
                 logx_min=None, logy_min=None, logx_max=None, logy_max=None,
                 cl_src_path=None, cl_platform=None, cl_device=None,
                 debug=False, verbose=False, gpu_verbose=False):
        if logx_min is None:
            logx_min = logx_array[logx_array>np.finfo(np.float32).min].min()
        if logx_max is None:
            logx_max = logx_array[logx_array>np.finfo(np.float32).min].max()
        if logy_min is None:
            logy_min = logy_array[logy_array>np.finfo(np.float32).min].min()
        if logy_max is None:
            logy_max = logy_array[logy_array>np.finfo(np.float32).min].max()      
        self.logx_data = logx_array[  (logx_array>=logx_min) & (logx_array<=logx_max)
                                    & (logy_array>=logy_min) & (logy_array<=logy_max)  ]
        self.logx_data = self.logx_data.reshape((self.logx_data.shape[0],1))
        # Re-estimate min,max since some array values may have just been eliminated
        self.logx_min = np.min(self.logx_data)
        self.logx_max = np.max(self.logx_data)
        self.logx_range = self.logx_max-self.logx_min
        self.logy_min   = 0.0
        self.logy_max   = 0.0
        self.logy_range = 0.0
        self.n_data = self.logx_data.shape[0]
        self.n_hist_bins = n_hist_bins
        self.n_pdf_points = n_pdf_points
        self.bin_dx = self.logx_range/self.n_hist_bins
        self.pdf_dx = self.logx_range/self.n_pdf_points        
        self.bin_dy = 0.0
        self.pdf_dy = 0.0       
        
        self.logx_vec \
            = np.linspace(self.logx_min,self.logx_max,self.n_pdf_points) \
                        .reshape((self.n_pdf_points,1))
        self.logx_vec_histogram \
            = np.linspace(self.logx_min,self.logx_max,self.n_hist_bins) \
                        .reshape((self.n_hist_bins,1))
        self.x_vec = np.exp(self.logx_vec)
        self.dlogx = self.logx_vec[1]-self.logx_vec[0]
 
        self.search_cdf_min = search_cdf_min
        self.search_cdf_max = search_cdf_max
        
        self.pixel_size = pixel_size
        self.cl_src_path = cl_src_path
        self.cl_platform = cl_platform
        self.cl_device = cl_device
        
        self.debug = debug
        self.verbose = verbose
        self.gpu_verbose = gpu_verbose

    def print(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    def compute_kde_scipy(self, bw_method='scott'):
        self.bw_method = bw_method
        self.model \
            = gaussian_kde(self.logx_data.reshape((self.n_data_x,)), 
                           bw_method=self.bw_method)
        self.pdf \
            = self.model.pdf(self.x_vec.reshape((self.x_vec.shape[0],)))
        self.pdf = self.kde.pdf.reshape((self.x_vec.shape[0],1))
        self.cdf = np.cumsum(self.pdf)*self.dlogx
        if not np.isclose(self.cdf[-1], 1.0, rtol=5e-3):
            self.print(
                'Error/imprecision when computing cumulative probability distribution:',
                       'pdf integrates to {:3f} not to 1.0'.format(self.kde.cdf[-1]))
                               
    def compute_kde_sklearn(self, kernel='gaussian', bandwidth=0.15):
        self.kernel = kernel
        self.bandwidth = bandwidth
        # defaults.json specifies a Gaussian, but in practice, when deducing a 
        # channel threshold from the multi-modal pdf of dslt, an Epanechnikov kernel
        # gives a noisy pdf for the same bandwidth. So this is a hack
        # to ensure consistency of channel threshold estimation with either kernel,
        # by forcing the Epanechnikov bandwidth to be double the Gaussian.
#         if kernel=='epanechnikov':
#             self.bandwidth *= 2.0
#         pdebug(self.logx_data.shape,self.x_vec.shape)
        self.model = KernelDensity(kernel=self.kernel, 
                                   bandwidth=self.bandwidth).fit(self.logx_data)
        # Exponentiation needed here because of the (odd) way sklearn generates
        # log pdf values in its score_samples() method
        self.pdf = np.exp(self.model.score_samples(self.logx_vec))\
                            .reshape((self.n_pdf_points,1))
        self.cdf = np.cumsum(self.pdf)*self.dlogx
        cdf_max = self.cdf[-1]
        self.pdf /= cdf_max
        self.cdf /= cdf_max
        if not np.isclose(self.kde.cdf[-1], 1.0, rtol=5e-3):
            self.print(
                'Error/imprecision when computing cumulative probability distribution:',
                       'pdf integrates to {:3f} not to 1.0'.format(self.cdf[-1]))

    def compute_kde_opencl(self, kernel='epanechnikov', bandwidth=0.15):
        self.kernel = kernel
        self.bandwidth = bandwidth
        # hack
        if self.kernel=='gaussian':
            self.bandwidth /= 2.0
        available_kernels = ['tophat','triangle','epanechnikov','cosine','gaussian']
        if self.kernel not in available_kernels:
            raise ValueError('PDF kernel "{}" is not among those available: {}'
                             .format(self.kernel, available_kernels))
        self.pdf, self.histogram \
            = kde.estimate_univariate_pdf( self )
        self.cdf = np.cumsum(self.pdf)*self.bin_dx
        cdf_max = self.cdf[-1]
        self.pdf /= cdf_max
        self.cdf /= cdf_max
        if not np.isclose(self.cdf[-1], 1.0, rtol=5e-3):
            self.print(
                'Error/imprecision when computing cumulative probability distribution:',
                       'pdf integrates to {:3f} not to 1.0'.format(self.cdf[-1]))
        # Hack - turning off detrending for now
#         self.detrended_pdf, self.detrended_histogram \
#             = kde.estimate_univariate_pdf( self, do_detrend=True,
#                                            logx_vec=self.logx_vec_histogram )

    def statistics(self):
        logx = self.logx_vec
        pdf = self.pdf
        mean = (np.sum(logx*pdf)/np.sum(pdf))
        variance = (np.sum( (logx-mean)**2 * pdf)/np.sum(pdf))
        self.mean = np.exp(mean)
        self.stddev = np.exp(np.sqrt(variance))
        self.var = np.exp(variance)
        self.raw_mean = np.exp(self.logx_data.mean())
        self.raw_stddev = np.exp(self.logx_data.std())
        self.raw_var = np.exp(self.logx_data.var())

    def find_modes(self):
        pdf = self.pdf
        approx_mode = np.round(self.x_vec[pdf==pdf.max()][0],2)
        peaks = argrelextrema(np.reshape(pdf,pdf.shape[0],), np.greater, order=3)[0]
        peaks = [peak for peak in list(peaks) if self.x_vec[peak]>=approx_mode*0.5 ]
        try:
            self.mode_i = peaks[0]
            self.mode_x = self.x_vec[peaks[0]][0]
            self.print('Mode @ {0:.0f}m'.format(self.mode_x))
        except:
            self.print('Failed to find mode')
            self.mode_i = self.pdf.shape[0]//2
            self.mode_x = 100.0

    def locate_threshold(self):
        x_vec = self.x_vec
        pdf = self.pdf
        cdf = self.cdf
        mode_x = self.mode_x
        detrended_pdf = pdf/norm.pdf(np.log(x_vec),np.log(self.mean),
                                     np.log(self.stddev))
#         detrended_pdf = self.detrended_pdf
        n_bins = pdf.shape[0]
        all_extrema_i = argrelextrema(np.reshape(detrended_pdf,n_bins,), 
                                      np.less, order=3)[0]
        all_extrema_i = np.concatenate((all_extrema_i,np.array([n_bins-1],)))
        self.print('Located pdf extrema at:   x={}m'.format(
                    [np.uint32(np.round(x_vec[i][0],0)) for i in all_extrema_i]))
        self.print('Corresponding cdf values:   {}'.format(
                    [(np.round(cdf[i],3)) for i in all_extrema_i]))
        # Choose lowest-cdf minimum given cdf threshold 
        #   - if necessary, progressively lowered until a minimum is found
        search_cdf_min = self.search_cdf_min
        while (search_cdf_min>=0.70):          
            extrema_i = [extremum_i for extremum_i in all_extrema_i 
                         if x_vec[extremum_i]>=mode_x \
                            and (     cdf[extremum_i]>=search_cdf_min
                                  and cdf[extremum_i]<=self.search_cdf_max ) ]
            if len(extrema_i)>=1:
                break
            search_cdf_min -= 0.01
        self.print('Selected pdf minimum/a at:  x={}m'.format(
                    [np.uint32(np.round(x_vec[i][0],0)) for i in extrema_i]))
        try:
            self.channel_threshold_i = extrema_i[0]
            self.channel_threshold_x = x_vec[extrema_i[0]][0]
            self.print('Threshold inferred @ cdf={0:0.3}  x={1:2.0f}m'.format(
                cdf[self.channel_threshold_i],self.channel_threshold_x))
        except:
            self.print('Failed to locate threshold: cannot find cdf minima in range'
                       +' {0:0.3f}-{1:0.3f} for x ≥ {2:.0f}m'
                       .format(search_cdf_min,self.search_cdf_max,mode_x))


class Bivariate_distribution():
    """
    Container class for kernel-density-estimated bivariate probability distribution
    f(x,y) data and metadata. Also has methods to find the modal average (xm,ym)
    and to find the cluster of points surrounding the mode given a pdf threshold
    and bounding criteria.
    """
    def __init__(self, logx_array=None,logy_array=None, mask_array=None,
                 pixel_size=None, 
                 method='opencl', n_hist_bins=2048, n_pdf_points=256, 
                 logx_min=None, logy_min=None, logx_max=None, logy_max=None,
                 cl_src_path=None, cl_platform=None, cl_device=None,
                 debug=False, verbose=False, gpu_verbose=False):
        self.logx_data = logx_array
        self.logy_data = logy_array
        if logx_min is None:
            logx_min = logx_array[logx_array>np.finfo(np.float32).min].min()
        if logx_max is None:
            logx_max = logx_array[logx_array>np.finfo(np.float32).min].max()
        if logy_min is None:
            logy_min = logy_array[logy_array>np.finfo(np.float32).min].min()
        if logy_max is None:
            logy_max = logy_array[logy_array>np.finfo(np.float32).min].max()
        if mask_array is not None:
            logxy_data = np.vstack([
                logx_array[  (logx_array>=logx_min) & (logx_array<=logx_max) 
                           & (logy_array>=logy_min) & (logy_array<=logy_max)
                           & (~mask_array)],
                logy_array[  (logx_array>=logx_min) & (logx_array<=logx_max) 
                           & (logy_array>=logy_min) & (logy_array<=logy_max)
                           & (~mask_array)]
                ]).T
        else:
            logxy_data  = np.vstack([
                logx_array[  (logx_array>=logx_min) & (logx_array<=logx_max) 
                           & (logy_array>=logy_min) & (logy_array<=logy_max)],
                logy_array[  (logx_array>=logx_min) & (logx_array<=logx_max) 
                           & (logy_array>=logy_min) & (logy_array<=logy_max)]
                ]).T
        self.logxy_data = logxy_data.copy().astype(dtype=np.float32)
        # x,y meshgrid for sampling the bivariate pdf f(x,y)
        # For some weird reason, the numbers of points in x,y need to be complex-valued 
        self.logx_mesh,self.logy_mesh \
            = np.mgrid[logx_min:logx_max:np.complex(n_pdf_points),
                       logy_min:logy_max:np.complex(n_pdf_points)]
        self.logxy_data_indexes = np.vstack([self.logx_mesh.ravel(), 
                                             self.logy_mesh.ravel()]).T
        self.logx_min     = logx_min
        self.logx_max     = logx_max
        self.logy_min     = logy_min
        self.logy_max     = logy_max
        self.logx_range   = self.logx_max-self.logx_min
        self.logy_range   = self.logy_max-self.logy_min
        self.n_data       = self.logxy_data.shape[0]
        self.n_hist_bins  = n_hist_bins
        self.n_pdf_points = n_pdf_points
        self.bin_dx       = self.logx_range/self.n_hist_bins
        self.pdf_dx       = self.logx_range/self.n_pdf_points
        self.bin_dy       = self.logy_range/self.n_hist_bins
        self.pdf_dy       = self.logy_range/self.n_pdf_points
        self.x_mesh       = np.exp(self.logx_mesh)
        self.y_mesh       = np.exp(self.logy_mesh)
        self.pixel_size   = pixel_size
        
        self.cl_src_path = cl_src_path
        self.cl_platform = cl_platform
        self.cl_device   = cl_device  
             
        self.debug       = debug
        self.verbose     = verbose
        self.gpu_verbose = gpu_verbose

    def print(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    def compute_kde_scipy(self, bw_method='scott'):
        # Compute bivariate pdf
        self.bw_method = bw_method
        self.model = gaussian_kde(self.logxy_data.T, bw_method=bw_method)
        self.pdf = np.reshape( self.model(self.logxy_data_indexes.T
                                                        ),self.logx_mesh.shape)
                                       
    def compute_kde_sklearn(self, kernel='epanechnikov', bandwidth=0.10):
        self.kernel = kernel
        self.bandwidth = bandwidth
        self.model = KernelDensity(kernel=self.kernel, 
                                          bandwidth=self.bandwidth).fit(self.logxy_data)
        self.pdf = np.reshape( 
            np.exp(self.model.score_samples(self.logxy_data_indexes)
                                                        ),self.logx_mesh.shape)  

    def compute_kde_opencl(self, kernel='epanechnikov', bandwidth=0.10):
        self.kernel = kernel
        self.bandwidth = bandwidth
        available_kernels = ['tophat','triangle','epanechnikov','cosine','gaussian']
        if self.kernel not in available_kernels:
            raise ValueError('PDF kernel "{}" is not among those available: {}'
                             .format(self.kernel, available_kernels))

        self.pdf,self.histogram = kde.estimate_bivariate_pdf(self)
        self.cdf = np.cumsum(self.pdf)*self.bin_dx
#         if not np.isclose(self.cdf[-1], 1.0, rtol=5e-3):
#             self.print(
#                 'Error/imprecision when computing cumulative probability distribution:',
#                        'pdf integrates to {:3f} not to 1.0'.format(self.cdf[-1]))

    def find_mode(self):
        # Prep
        kde_pdf = self.pdf.copy()
        # Hack
        kde_pdf[(self.x_mesh<=3.0) | (self.y_mesh<=3.0)]=0.0
        # Find mode = (x,y) @ max{f(x,y)}
        max_pdf_idx = np.argmax(kde_pdf,axis=None)
        mode_ij = np.unravel_index(max_pdf_idx, kde_pdf.shape)
        mode_xy = np.array([ self.x_mesh[mode_ij[0],0],self.y_mesh[0,mode_ij[1]] ])
        
        # Record mode info
        self.mode_max = kde_pdf[ mode_ij[0],mode_ij[1] ]
        self.mode_ij  = mode_ij
        self.mode_xy  = mode_xy
            
        
