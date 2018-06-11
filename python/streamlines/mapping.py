"""
TBD
"""

import numpy  as np
import pandas as pd
from cmath import rect, polar
from sklearn.preprocessing import normalize
from skimage.morphology    import skeletonize, thin, medial_axis, disk
from skimage.filters       import gaussian
from skimage.filters.rank  import mean,median
from scipy.ndimage            import gaussian_filter
from scipy.ndimage.morphology import binary_fill_holes
from scipy.ndimage.morphology import binary_dilation,generate_binary_structure
import warnings
import sys
from os import environ
environ['PYTHONUNBUFFERED']='True'

from streamlines.core  import Core
from streamlines       import connect, channelheads, countlink, label, \
                              segment, linkhillslopes, lengths, useful
from streamlines.trace import Info, Data
from streamlines.pocl  import Initialize_cl

__all__ = ['Mapping']

pdebug = print

class Mapping(Core):
    """
    TBD.
    """
    def __init__(self,state,imported_parameters,geodata,preprocess,trace,analysis):
        """
        TBD
        """
        super().__init__(state,imported_parameters)  
        self.geodata = geodata
        self.preprocess = preprocess
        self.trace = trace
        self.analysis = analysis
        self.cl_state = Initialize_cl(self.state.cl_src_path, 
                                      self.state.cl_platform, 
                                      self.state.cl_device )
    
    def _augment(self, plot):
        self.plot = plot
     
    def do(self):
        """
        TBD.
        """
        self.print('\n**Mapping begin**') 

        # Active masks presumably set:  
        #    - geodata.dtm_mask_array
        #    - geodata.basin_mask_array (if set)
        #    - preprocess.uv_mask_array
        #
        
        # 1st pass:
        #    - coarsely (sub)segment and label using an imposed threshold
        #       - map_channels()
        #       - connect_channel_pixels()
        #       - thin_channels()
        #       - map_channel_heads()
        #       - count_downchannels()
        #       - flag_downchannels()
        #       - label_confluences()
        #       - segment_downchannels()
        #       - link_hillslopes()
        #       - segment_hillslopes()
        #       - subsegment_flanks()
        #
        #    - keep coarse subsegment labels array
        #
        #    - estimate approximate channel threshold for whole ROI
        #       - analysis.estimate_channel_threshold()
        #
        #    - keep fine subsegment labels array
        self.pass1()
        
        # 2nd pass:
        #    - loop over coarse subsegments
        #       - add (not) coarse subsegment to list of active masks
        #
        #       - estimate channel threshold for coarse subsegment
        #
        #       - finely (sub)segment and label using approximate channel threshold
        #          - map_channels()
        #          - connect_channel_pixels()
        #          - thin_channels()
        #          - map_channel_heads()
        #          - count_downchannels()
        #          - flag_downchannels()
        #          - label_confluences()
        #          - segment_downchannels()
        #          - link_hillslopes()
        #          - segment_hillslopes()
        #          - subsegment_flanks()
        #
        #       - measure partial HSL on fine subsegments within the coarse subsegment
        #          - map_midslopes()
        #          - map_ridges()
        #          - measure_hsl()
        #
        #       - merge partial HSL onto aggregating HSL array
        #
        #       - remove (not) coarse subsegment from list of active masks
        #
        #    - map (median & mean filter) aggregate HSL measurements
        self.pass2()
        
        # Post HSL:
        #    - map aspect
        #    - compute HSL(aspect)
        self.print('**Mapping end**\n')  

    def prepare(self, channel_threshold=None, segmentation_threshold=None):
        self.print('Preparing...',end='')  
        try:
            del self.mapping_array
        except:
            pass
        try:
            del self.data
        except:
            pass
        try:
            del self.label_array
        except:
            pass
        try:
            del self.hsl_array
        except:
            pass
        try:
            del self.hsl_smoothed_array
        except:
            pass
        self.mapping_array = np.zeros_like(self.trace.mapping_array).astype(np.uint32)
        if self.mapping_array[self.mapping_array>0]!=[]:
            self.print('Mapping array should be empty at this point'
                       +' - carrying on regardless')
        self.data = Data( mask_array    = self.state.merge_active_masks(),
                          uv_array      = self.preprocess.uv_array,
                          mapping_array = self.mapping_array )  
        self.verbose = self.state.verbose
        if channel_threshold is None:
            self.channel_threshold = self.analysis.mpdf_dslt.channel_threshold_x
        else:
            self.channel_threshold = channel_threshold
        if segmentation_threshold is None:
            self.segmentation_threshold = self.fine_segmentation_threshold
        else:
            self.segmentation_threshold = segmentation_threshold
        self.info = Info(self.trace, mapping=self)
        self.print('done')    
            
    def pass1(self):
        # Pass §1
        #
        self.print('\n**Pass#1 begin**') 
        self.state.reset_active_masks()
        self.prepare(channel_threshold=self.coarse_channel_threshold,
                     segmentation_threshold=self.coarse_segmentation_threshold)
        self.mapping_segments_channels()
        self.coarse_label_array = self.label_array
        self.list_subsegments(do_without_ridges_midslopes=True)
        self.coarse_labels = np.sort(self.hillslope_labels)
        self.plot.plot_channels(window_size_factor=3)
        self.plot.plot_segments(window_size_factor=3)
        
        # Estimate whole-ROI, approximate channel threshold
        self.analysis.estimate_channel_threshold()
#         self.plot.plot_marginal_pdf_dslt()
        self.info.channel_threshold = self.analysis.mpdf_dslt.channel_threshold_x
        self.print('\n**Pass#1  end**') 

    def pass2(self):
        # Pass §2
        self.print('\n**Pass#2 begin**') 
        self.state.reset_active_masks()
        self.print('Subsegment labels: {}'.format(self.coarse_labels))
#         for coarse_label in self.coarse_labels:
        for coarse_label in self.coarse_labels[::-1]:
            self.print('Mapping HSL on subsegment #{}'.format(coarse_label))
            # Create a mask array for this coarse subsegment and add to active list
            coarse_mask_array = np.zeros_like(self.coarse_label_array, dtype=np.bool)
            coarse_mask_array[self.coarse_label_array==coarse_label] = True
            n_iterations = (2 if coarse_label<0 else 1)
            coarse_mask_array= np.invert(useful.dilate(coarse_mask_array,
                                                       n_iterations=n_iterations))
            self.state.add_active_mask({'coarse_mask_array': coarse_mask_array})
            # Compute slt pdf and estimate channel threshold from it
#             self.plot.plot_marginal_pdf_dslt()
            self.analysis.estimate_channel_threshold()

            # Get ready to map HSL
            self.prepare()
            # Map channel heads, thin channel pixels, subsegments
            self.mapping_segments_channels()
            # Map ridges and midslopes
            self.map_midslopes()
            self.map_ridges()
            self.list_subsegments(do_without_ridges_midslopes=False)
            self.plot.plot_segments(window_size_factor=3)
            self.plot.plot_channels(window_size_factor=3)
            # Measure HSL from ridges or midslopes to thin channels per subsegment
            self.measure_hsl()
            self.map_hsl()
            # Delete this coarse mask from the active list
            self.state.remove_active_mask('coarse_mask_array')
        
        self.print('\n**Pass#2  end**') 
                
    def mapping_segments_channels(self):
        """
        TBD.
        """
        self.print('\n**Mapping segments and channels begin**') 
        # Use downstream slt,sla pdfs to designate pixels as channels
        self.map_channels()
        # Join up disconnected channel pixels if they are not too widely spaced
        self.connect_channel_pixels()
        # Skeletonize channel pixels into thin network
        self.thin_channels()
        # Locate upstream ends of thinned channel network & designate as heads
        self.map_channel_heads()
        # Link downstream from channel heads
        self.count_downchannels()
        # Count downstream from channel heads
        self.flag_downchannels()
        # Map locations of channel confluences & designate types
        self.label_confluences()
        # Label channel segments with channel head idxs
        self.segment_downchannels()
        # Designate downstream linkages for all hillslope pixels
        self.link_hillslopes()
        # Label correspondingly upstream hillslope pixels
        self.segment_hillslopes()
        # Designate as L or R of channel to subsegment hillslope flanks
        self.subsegment_flanks()
        self.print('**Mapping segments and channels end**\n')  
        
    def mapping_ridges_midslopes_hsl_aspect(self):
        """
        TBD.
        """
        self.print('\n**Mapping ridges, midslopes, HSL, aspect begin**') 
        # Use up- and downstream sla to designate midslope pixels
        self.map_midslopes()
        # Use up- and downstream sla to designate ridge pixels
        self.map_ridges()
        # Make subsegment label list
        self.list_subsegments()
        # Measure mean streamline distances from midslope to channel pixels
        self.measure_hsl()
        # Measure mean streamline distances from midslope to channel pixels
        self.map_hsl()
        # Gradient-thresholded hillslope horizontal orientation = aspect
        self.map_aspect()
        self.compute_hsl_aspect()
        self.print('**Mapping ridges, midslopes, HSL, aspect end**\n')  


    def map_channels(self):
        self.print('Channels...',end='')
        # Designate channel pixels according to dslt pdf analysis
        self.data.mapping_array[  
                          (self.trace.slt_array[:,:,0]>=self.info.channel_threshold)
                        & (self.trace.slt_array[:,:,0]*2>=self.trace.slc_array[:,:,0])
                                ] = self.info.is_channel                                
        self.print('done')  

    def connect_channel_pixels(self):
        connect.connect_channel_pixels(self.cl_state,self.info,self.data,self.verbose)
        
    def thin_channels(self):
        self.print('Thinning channels...',end='')  
        is_channel      = self.info.is_channel
        is_interchannel = self.info.is_interchannel
        mapping_array   = self.data.mapping_array
        channel_array   = np.zeros_like(mapping_array, dtype=np.bool)
        channel_array[  ((mapping_array & is_channel)==is_channel)
                      | ((mapping_array & is_interchannel)==is_interchannel)
                     ] = True
        self.print('skeletonizing...',end='')  
        skeleton_array = skeletonize(medial_axis(channel_array))
        mapping_array[skeleton_array] |= self.info.is_thinchannel
        self.print('done')  

    def map_channel_heads(self):
        channelheads.map_channel_heads(self.cl_state, self.info, self.data, 
                                       self.verbose)
        mapping_array = self.data.mapping_array
        channelheads.prune_channel_heads(self.cl_state, self.info, self.data, 
                                         self.verbose)
        
    def count_downchannels(self):
        self.data.count_array = np.zeros_like(self.mapping_array, dtype=np.uint32)
        self.data.link_array  = np.zeros_like(self.mapping_array, dtype=np.uint32)
        countlink.count_downchannels(self.cl_state, self.info, self.data, 
                                     self.verbose)
        
    def flag_downchannels(self):
        countlink.flag_downchannels(self.cl_state, self.info, self.data,
                                    self.verbose)

    def label_confluences(self):
        self.data.dn_slt_array = self.trace.slt_array[:,:,0].copy()
        label.label_confluences(self.cl_state, self.info, self.data, self.verbose)
        # Three passes to try to eliminate all 'parasite' streamlets
        countlink.flag_downchannels(self.cl_state, self.info, self.data,
                                    self.verbose)
        countlink.flag_downchannels(self.cl_state, self.info, self.data,
                                    self.verbose, do_reset_count=False)
        countlink.flag_downchannels(self.cl_state, self.info, self.data,
                                    self.verbose, do_reset_count=False)
        
    def segment_downchannels(self):
        self.data.label_array = np.zeros_like(self.mapping_array, dtype=np.uint32)
        self.n_segments = segment.segment_channels(self.cl_state, self.info, 
                                                   self.data, self.verbose)
        # Save the channel-only segment labeling for now
        self.data.channel_label_array = self.data.label_array.copy().astype(np.uint32)
        is_majorconfluence = self.info.is_majorconfluence
        
#         thinchannel_array = np.zeros_like(self.mapping_array, dtype=np.bool)
#         thinchannel_array[(self.mapping_array & self.info.is_thinchannel)!=0] |= True
#         skeleton_thinchannel_array = skeletonize(thinchannel_array)
#         self.mapping_array[(self.mapping_array & self.info.is_thinchannel)!=0] \
#             ^= self.info.is_thinchannel
#         self.mapping_array[skeleton_thinchannel_array] |= self.info.is_thinchannel        

    def link_hillslopes(self):
        linkhillslopes.link_hillslopes(self.cl_state, self.info, self.data,
                                       self.verbose)

    def segment_hillslopes(self):
        segment.segment_hillslopes(self.cl_state, self.info, self.data, 
                                   self.verbose )

    def subsegment_flanks(self):
        # Channel edges first, and then flanks
        segment.subsegment_flanks(self.cl_state, self.info, self.data, self.verbose)
        self.data.label_array = self.data.label_array.astype(dtype=np.int32)
        self.data.label_array[self.data.label_array<0] \
            = - (  self.data.label_array[self.data.label_array<0] 
                 + self.info.left_flank_addition )
        self.label_array = self.data.label_array
        
    def map_midslopes(self):
        self.print('Midslopes...',end='')  
        dsla = self.trace.sla_array[:,:,0]
        usla = self.trace.sla_array[:,:,1]
        mask = self.data.mask_array

        midslope_array = np.zeros_like(dsla, dtype=np.bool)
        midslope_array[ (~mask) & (np.fabs(
            gaussian_filter((np.arctan2(dsla,usla)-np.pi/4), self.midslope_filter_sigma))
                             <=self.midslope_threshold)] = True
#         dilation_structure = generate_binary_structure(2, 2)
#         fat_midslope_array = binary_dilation(midslope_array, 
#                                              structure=dilation_structure, iterations=1)
#         filled_midslope_array = binary_fill_holes(midslope_array)
        skeleton_midslope_array = skeletonize(midslope_array)
#         fat_midslope_array = binary_dilation(skeleton_midslope_array, 
#                                              structure=dilation_structure, iterations=1)
        self.data.mapping_array[skeleton_midslope_array] |= self.info.is_midslope
        self.print('done')  

    def map_ridges(self):
        self.print('Ridges...',end='')  
        dsla = self.trace.sla_array[:,:,0]
        usla = self.trace.sla_array[:,:,1]
        mask = self.data.mask_array
        ridge_array = np.zeros_like(dsla, dtype=np.bool)
        ridge_array[ (~mask) & ((
            gaussian_filter((np.arctan2(dsla,usla)-np.pi/4), self.ridge_filter_sigma))
                             <= -(np.pi/4)*self.ridge_threshold)] = True
        dilation_structure = generate_binary_structure(2, 2)
        fat_ridge_array = binary_dilation(ridge_array, 
                                          structure=dilation_structure, iterations=1)
        filled_ridge_array = binary_fill_holes(fat_ridge_array)
        skeleton_ridge_array = skeletonize(filled_ridge_array)
#         fat_ridge_array = binary_dilation(skeleton_ridge_array, 
#                                           structure=dilation_structure, iterations=1)
        self.data.mapping_array[skeleton_ridge_array] |= self.info.is_ridge
        self.print('done')  

    def list_subsegments(self, do_without_ridges_midslopes=False):
        self.print('Listing subsegments...',end='')  
        if do_without_ridges_midslopes:
            self.data.traj_label_array \
                = self.data.label_array[~self.data.mask_array].astype(np.int32).ravel()
        else:
            if self.do_measure_hsl_from_ridges:
                flag = self.info.is_ridge
            else:
                flag = self.info.is_midslope
            self.data.traj_label_array \
                = self.data.label_array[
                     ((self.data.mapping_array & flag)>0) & (~self.data.mask_array)
                                        ].astype(np.int32).ravel()
        unique_labels = np.unique(self.data.traj_label_array)
        self.hillslope_labels = unique_labels[unique_labels!=0].astype(np.int32)
        self.print('...done')  
                
    def measure_hsl(self):
        self.print('Measuring hillslope lengths wrapper...',flush=True)
#         if self.do_measure_hsl_from_ridges:
#             flag = self.info.is_ridge
#         else:
#             flag = self.info.is_midslope
#         self.data.traj_label_array = (self.data.label_array[
#                                        ((self.data.mapping_array & flag)>0)
#                                        &   (~self.data.mask_array)
#                                                 ].astype(np.int32)).ravel().copy()
#         unique_labels = np.unique(self.data.traj_label_array)
#         self.hillslope_labels = unique_labels[unique_labels!=0].astype(np.int32)

        self.data.traj_length_array \
            = np.zeros_like(self.data.traj_label_array,dtype=np.float32)
        lengths.hsl(self.cl_state, self.info, self.data, self.verbose)
        
        df  = pd.DataFrame(np.zeros((self.data.traj_length_array.shape[0],), 
                                    dtype=[('label', np.int32), ('length', np.float32)]))
        df['label']  = self.data.traj_label_array
        df['length'] = self.data.traj_length_array
        df = df[df.label!=0]
        self.hsl_df = df
        
        stats_df = pd.DataFrame(self.hillslope_labels,columns=['label'])
        stats_list = ( ('count','count'),('mean','mean [m]'), ('std','stddev [m]') )
        for stat in stats_list:
            stats_df = stats_df.join( getattr(df.groupby('label'),stat[0])() ,on='label')
            stats_df.rename(index=str, columns={'length':stat[1]}, inplace=True)
        stats_df.set_index('label',inplace=True)
        self.hsl_stats_df = stats_df
        
        self.hsl_array=np.zeros_like(self.data.label_array,dtype=np.float32)
        for idx,row in stats_df.iterrows():
            if row['count']>=self.n_hsl_averaging_threshold:
                self.hsl_array[self.data.label_array==idx] = row['mean [m]']
            else:
                self.hsl_array[self.data.label_array==idx] = 0
        self.print('done')  

    def map_hsl(self):
        self.print('Mapping hillslope lengths...',end='',flush=True)
        sys.stdout.flush()
        
        hsl = self.hsl_array
        hsl_bool = hsl.astype(np.bool)
        hsl_clipped = np.ma.array(hsl, mask=~hsl_bool)
        hsl_min = np.min(hsl_clipped)
        hsl_max = np.max(hsl_clipped)
        hsl_clipped = 65535*(hsl_clipped-hsl_min)/(hsl_max-hsl_min)
        hsl_masked = np.ma.array(hsl_clipped.astype(np.uint16),mask=~hsl_bool)

        median_radius = int(self.hsl_median_radius/self.geodata.roi_pixel_size)
        mean_radius   = int(self.hsl_mean_radius/self.geodata.roi_pixel_size)
        median_disk = disk(median_radius)
        mean_disk   = disk(mean_radius)
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.print('median filtering with {0}m ({1}-pixel) diameter disk...'
                       .format(self.hsl_median_radius,median_radius), 
                       end='',flush=True)
            if self.state.verbose:
                sys.stdout.flush()
            # Strangely, mask logic is backwards for median(): 
            #    - true pixels are used (median-filtered), while false are untouched
            if median_radius==0:
                hsl_median = hsl_masked
            else:
                hsl_median = np.ma.array(median(hsl_masked,median_disk,mask=hsl_bool),
                                         mask=~hsl_bool)
            self.print('mean filtering with {0}m ({1}-pixel) diameter disk...'
                       .format(self.hsl_mean_radius,mean_radius),
                       end='',flush=True) 
            if self.state.verbose:
                sys.stdout.flush()
            hsl_median_nm = mean(hsl_median,mean_disk)
            
        self.hsl_smoothed_array \
            = ((hsl_median_nm[self.geodata.pad_width:-self.geodata.pad_width,
                              self.geodata.pad_width:-self.geodata.pad_width]
                                .astype(np.float32))/65535)*(hsl_max-hsl_min)+hsl_min
        self.print('done')  
        
    def map_aspect(self):
        self.print('Computing hillslope aspect...',end='',flush=True)
        sys.stdout.flush()

        slope_threshold = self.aspect_slope_threshold
        median_radius   = self.aspect_median_filter_radius/self.geodata.pixel_size
        slope_array     = self.preprocess.slope_array.copy()
        uv_array        = self.preprocess.uv_array.copy()
        is_channel      = self.info.is_channel
        mapping_array   = self.data.mapping_array
        mask_array      = np.zeros_like(mapping_array, dtype=np.bool)
        slope_array[((mapping_array & is_channel)==is_channel)] = 0.0
        if self.do_aspect_median_filtering:
            sf = np.max(slope_array)/255.0
            median_slope_array = sf*median(np.uint8(slope_array/sf),disk(median_radius))
            slope_array = median_slope_array

        median_radius   = self.uv_median_radius/self.geodata.pixel_size
        sf = 2.0/255.0
        uvx_array = sf*median(np.uint8((uv_array[:,:,0]+1.0)/sf),disk(median_radius))-1.0
        uvy_array = sf*median(np.uint8((uv_array[:,:,1]+1.0)/sf),disk(median_radius))-1.0
        mask_array[  (slope_array<slope_threshold)
                   | ((mapping_array & is_channel)==is_channel) ] = True
        self.aspect_array = np.ma.masked_array( np.arctan2(uvy_array,uvx_array), 
                                                mask=mask_array )
        self.print('done')  
                                                         
    def compute_hsl_aspect(self, n_bins=None, hsl_averaging_threshold=None):
        self.print('Computing hillslope length-aspect function...',end='',flush=True)
        sys.stdout.flush()
        
        if n_bins is None:
            n_bins = 60
        if hsl_averaging_threshold is None:
            hsl_averaging_threshold = self.hsl_averaging_threshold
        
        pad           = self.geodata.pad_width
        mask_array    = self.data.mask_array[pad:-pad,pad:-pad]
        aspect_array  = self.aspect_array[pad:-pad,pad:-pad].copy()[~mask_array]
        hsl_array     = self.hsl_smoothed_array.copy()[~mask_array]
        aspect_array  = np.rad2deg(aspect_array[hsl_array>hsl_averaging_threshold])
        hsl_array     = hsl_array[hsl_array>hsl_averaging_threshold]
        hsl_aspect_array = np.stack( (hsl_array,aspect_array), axis=1)
        
        # Sort in-place using column 1 (aspect) as key
        self.hsl_aspect_array = hsl_aspect_array[hsl_aspect_array[:,1].argsort()]
        self.hsl_aspect_df    = pd.DataFrame(data=self.hsl_aspect_array,
                                             columns=['hsl','aspect'])
        half_bin_width = 180/n_bins
        bin_width = half_bin_width*2
        bins = np.linspace(-180,+180+bin_width,n_bins+2)-half_bin_width
        self.hsl_aspect_df['groups'] = pd.cut(self.hsl_aspect_df['aspect'], bins)
        self.hsl_aspect_averages = self.hsl_aspect_df.groupby('groups')['hsl'].mean()
        bins = np.deg2rad(bins[:-1]+half_bin_width)
        hsl = self.hsl_aspect_averages.values
        west_hsl = (hsl[0]+hsl[-1])/2.0
        hsl[0]  = west_hsl
        hsl[-1] = west_hsl
        self.hsl_aspect_averages_array = np.stack((hsl,bins),axis=1)
        
        haa = self.hsl_aspect_averages_array
        hsl = haa[~np.isnan(haa[:,0]),0]
        asp = haa[~np.isnan(haa[:,0]),1]
        hsl_south_array = hsl[asp<=0.0]
        hsl_north_array = hsl[asp>=0.0]
        if -asp[0]==asp[-1]:
            self.hsl_mean     = np.mean(hsl[1:])
        else:
            self.hsl_mean     = np.mean(hsl)
        self.hsl_mean_south   = np.mean(hsl_south_array)
        self.hsl_mean_north   = np.mean(hsl_north_array)
        self.hsl_ns_disparity = np.abs(self.hsl_mean_north-self.hsl_mean_south)
        self.hsl_ns_disparity_normed = self.hsl_ns_disparity/self.hsl_mean/2.0
        
        self.hsl_stddev       = np.std(hsl)
        self.hsl_split_stddev = np.mean(np.array([np.std(hsl_split[~np.isnan(hsl_split)])
                                                for hsl_split in np.split(haa[1:,0],4)]))
        self.hsl_split_stddev_normed = self.hsl_split_stddev/self.hsl_mean

        hsl_complex_vector_array = (np.array([rect(ha[0],ha[1]) for ha in haa]))
        hsl_mean_complex_vector \
            = np.mean(hsl_complex_vector_array[~np.isnan(hsl_complex_vector_array)])
        mhsl = polar(hsl_mean_complex_vector)
        self.hsl_mean_magnitude = mhsl[0]
        self.hsl_mean_azimuth = np.rad2deg(mhsl[1])
        
        self.hsl_ns_disparity_confidence \
            = self.hsl_ns_disparity_normed/self.hsl_split_stddev_normed

        self.print('done')  
        
    def check_hsl_ns_disparity(self):
        self.print('HSL mean:'
                   +'\t\t\t\t {:2.1f}m'
                   .format(self.hsl_mean)
                   +' ± {:2.1f}m (seg)'
                   .format(self.hsl_split_stddev)
                   +' {:2.1f}m (all)'
                   .format(self.hsl_stddev) )
        self.print('HSL N-S disparity:'
                   +'\t\t\t {0:2.1f}mN <=> {1:2.1f}mS  2∆≈{2:2.1f}m'
                   .format(self.hsl_mean_north, self.hsl_mean_south,
                           self.hsl_ns_disparity) )
        self.print('HSL N-S relative disparity vs variation:'
                   +' {0:2.1f}%NS vs {1:2.1f}%'
                   .format(self.hsl_ns_disparity_normed*100,
                           self.hsl_split_stddev_normed*100) )
        self.print('HSL N-S disparity degree of confidence:\t {0:2.1f}'
                   .format(self.hsl_ns_disparity_confidence) )
        if self.hsl_ns_disparity_confidence<0.5:
            self.print('\t\t\t=> no significant disparity')
        elif self.hsl_ns_disparity_confidence<1.0:
            self.print('\t\t\t=> likely no significant disparity')
        elif self.hsl_ns_disparity_confidence<2.0:
            self.print('\t\t\t=> possibly significant disparity')
        else:
            self.print('\t\t\t=> likely significant disparity')                                                         
