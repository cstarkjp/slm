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
 *
 * Up to date with python of git CS 54b7ed9ebd253403c1851764035b5c718d5937d3
 * except for padding that is being removed
 *
 * v}
 *)

(*a Module abbreviations *)
module Option=Batteries.Option
open Globals
open Core
open Properties

(** {1 Types } *)

(**  [t_data]

  Structure for the Trace workflow

 *)
type t_data = {
    properties : t_props;
    props : t_props_trace;
  }

(** {1 pv_verbosity functions} *)

(**  [pv_noisy t]

  Shortcut to use {!type:Trace.t_data} verbosity for {!val:Properties.pv_noisy}

 *)
let pv_noisy   t = Workflow.pv_noisy t.props.workflow

(**  [pv_debug t]

  Shortcut to use {!type:Trace.t_data} verbosity for {!val:Properties.pv_debug}

 *)
let pv_debug   t = Workflow.pv_noisy t.props.workflow

(**  [pv_info t]

  Shortcut to use {!type:Trace.t_data} verbosity for {!val:Properties.pv_info}

 *)
let pv_info    t = Workflow.pv_info t.props.workflow

(**  [pv_verbose t]

  Shortcut to use {!type:Trace.t_data} verbosity for {!val:Properties.pv_verbose}

 *)
let pv_verbose t = Workflow.pv_verbose t.props.workflow

(** {1 Results} *)

(**  [results_create data seeds]

  Create the trace results structure given the seeds

 *)
let results_create data seeds =
  let (num_seeds,_) = ODM.shape seeds in
  let roi_nx = data.roi_nx + data.pad_width*2 in
  let roi_ny = data.roi_ny + data.pad_width*2 in

  (* Result arrays *)
  let traj_nsteps_array  = ba_int16s (num_seeds*2) in (* *2 as there are 2 directions ? *)
  let traj_lengths_array = ba_floats (num_seeds*2) in (* *2 as there are 2 directions ? *)
  let slc_array          = ba_int3d   2 roi_nx roi_ny in
  let slt_array          = ba_float3d 2 roi_nx roi_ny in
  let sla_array          = ba_float3d 2 roi_nx roi_ny in
  ODN.fill traj_nsteps_array  0;
  ODN.fill traj_lengths_array 0.;
  ODN.fill slc_array 0;
  ODN.fill slt_array 0.;
  ODN.fill sla_array 0.;
  {
    streamline_arrays= Array.make 2 (Array.make 0 (Bytes.make 0 ' '));
    traj_nsteps_array;
    traj_lengths_array;
    slc_array;
    slt_array;
    sla_array;
    ds_stats = None;
    us_stats = None;
  }

(** {1 Seed functions} *)

(**  [create_seeds t data]

  Generate an N by 2 matrix, of seed vectors for every unmasked ROI (x,y) (in unpadded coordinates)

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
    ODM.iteri_2d add_seed mask;
    pv_debug t (fun _ -> Printf.printf "...done\n%!");
    seeds

(**  [trace_streamlines t pocl data results seeds]

  Trace up or downstreamlines across region of interest (ROI) of DTM grid with the given seeds.

  The seeds are a big array of unpadded (x,y) ROI locations

 *)
let trace_streamlines t pocl data results seeds =
  Trajectories.integrate_trajectories t.props pocl data results seeds

(** {1 Workflow functions} *)

(**  [create props]

  Create the Trace workflow data from its properties

 *)
let create props =
  {
    properties = props;
    props      = props.trace;
  }

(**  [process t pocl data]

  Run the Trace workflow

  This traces all the streamlines both upstream and downstream,
  and derive means streamline point spacing.

  @return trace result
            
 *)
let process t pocl data =
  Workflow.workflow_start t.props.workflow;
  let seeds = create_seeds t data in
  let results = results_create data seeds in
  data.seeds <- seeds;
  let (num_seeds,_) = ODM.shape seeds in
  Info.set data.info "n_seed_points" (Info.Int num_seeds);
  trace_streamlines t pocl data results seeds;
  Workflow.workflow_end t.props.workflow;
  results
