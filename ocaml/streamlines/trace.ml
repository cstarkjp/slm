(** {v Copyright (C) 2017-2018,  Colin P Stark and Gavin J Stark.  All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * @file   trace.ml
 * @brief  Trace workflow
 * v}
 *)

(*a Module abbreviations *)
module Option=Batteries.Option
open Globals
open Core
open Properties

(*a Types *)
(*t t_data *)
type t_data = {
    properties : t_props;
    props : t_props_trace;
  }

(*a Useful functions *)
let pv_noisy   t = Workflow.pv_noisy   t.props.workflow
let pv_debug   t = Workflow.pv_debug   t.props.workflow
let pv_info    t = Workflow.pv_info    t.props.workflow
let pv_verbose t = Workflow.pv_verbose t.props.workflow

(*f create props *)
let create props =
  {
    properties = props;
    props=props.trace;
  }

(*f create_seeds
  Generate a matrix with 2 rows and N columns where each column is an (x,y) index in to the ROI (unpadded)

  Ignore points that have a mask
 *)
let create_seeds t data =
    pv_debug t (fun _ -> Printf.printf "Generating seed points\n%!");
    let mask = data.basin_mask_array in
    let pad = data.properties.geodata.pad_width in
    let num_seeds = ba_fold (fun acc bm->if bm='\000' then (acc+1) else acc) 0 data.basin_mask_array in
    pv_debug t (fun _ -> Printf.printf "%d unmasked data points, one seed for each\n%!" num_seeds);
    let seeds  = ba_float2d num_seeds 2 in
    let n = ref 0 in
    let add_seed x y bm =
      if bm='\000' then (
        ODM.set seeds (!n) 0 (float (x-pad));
        ODM.set seeds (!n) 1 (float (y-pad));
        n := !n +1
      )
    in
    ODM.iteri_2d add_seed data.basin_mask_array;
    pv_debug t (fun _ -> Printf.printf "...done\n%!");
    seeds

(*f trace_streamlines
        Trace up or downstreamlines across region of interest (ROI) of DTM grid.
    
        Returns:
            list, numpy.ndarray, numpy.ndarray, pandas.DataFrame,
            numpy.ndarray, numpy.ndarray, numpy.ndarray: 
            streamline_arrays_list, traj_nsteps_array, traj_length_array, traj_stats_df,
            slc_array, slt_array, sla_array
let trace_streamlines blah =
        (self.streamline_arrays_list,
         self.traj_nsteps_array, self.traj_length_array, self.traj_stats_df,
         self.slc_array, self.slt_array, self.sla_array) \
            = integrate_trajectories(
                self.state.path, self.state.cl_platform, self.state.cl_device, 
                self.build_info_struct(),
                self.seed_point_array, 
                self.geodata.basin_mask_array,
                self.preprocess.u_array,self.preprocess.v_array,
                self.do_trace_downstream, self.do_trace_upstream, 
                self.state.verbose
            )
 *)
let trace_streamlines t pocl data seeds =
  Integration.integrate_trajectories t.props pocl data seeds

(*f process
        Trace all streamlines both upstream and downstream
        and derive mean streamline point spacing.
            
        Attributes:
            seed_point_array (numpy.ndarray):
            streamline_arrays_list (list):
            traj_nsteps_array (numpy.ndarray):
            traj_length_array (numpy.ndarray):
            traj_stats_df (pandas.DataFrame):
            slc_array (numpy.ndarray):
            slt_array (numpy.ndarray):
            sla_array (numpy.ndarray):
 *)
let process t pocl data =
  Workflow.workflow_start t.props.workflow;
  let seeds = create_seeds t data in
  data.seeds <- seeds;
  let result = trace_streamlines t pocl data seeds in
  Workflow.workflow_end t.props.workflow;
  result
