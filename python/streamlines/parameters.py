"""
---------------------------------------------------------------------

Module to read/write/assign the data contained in the :class:`.Streamlining` 
class instance. 

---------------------------------------------------------------------

Requires Python packages/modules:
  -  :mod:`json`

---------------------------------------------------------------------

.. _json: https://docs.python.org/3/library/json.html

"""

import os
from json import load
import streamlines

__all__ = ['read_json_file','import_parameters']

pdebug = print

def import_parameters(parameters_path, parameters_file): #,do_reload_state=False
    """
    Args:
        parameters_path (list): path to JSON parameters files (broken out as OS path list)
        parameters_file (str): name of job JSON parameters file

    Load JSON parameters files (defaults and job) and parse them in turn to 
    generate a workflow parameters dictionary. 
    
    Return:
        dict:  workflow parameter dictionary
    """        
    # Parse default and assigned JSON parameters files
    slm_path = os.path.realpath(os.path.join(streamlines.__path__[0],'..','..'))
    defaults_path = os.path.realpath(os.path.join(slm_path,'json','defaults'))
    parameters_path = os.path.realpath(os.path.join(parameters_path,parameters_file))
    parameters_files_list = [defaults_path,parameters_path]
    return read_json_file(parameters_files_list), slm_path, parameters_path


def read_json_file(parameters_file_name_list):
    """
    Args:
        parameters_file_name_list (list): JSON parameters files to be read and parsed

    Load and parse a list of JSON parameters files into a parameters dict.

    Step through a list of JSON parameters files (usually "defaults.json" 
    and the job JSON file).
    Parse each into a parameters dict, ensuring that subsequent JSON parameters
    override any set by previous JSON files.
    
    Return:
        dict:  workflow parameter dictionary
    """
    # Start wit a clean parameters dictionary
    parameters_dict = {}
    # Step through each JSON parameters file in turn
    for parameters_file_name in parameters_file_name_list:
        parameters_file_name += ".json"
        # Read in the parameters file
        with open(parameters_file_name) as json_file:
            parameters = load(json_file)
        # Step through all the dict items in turn
        # We do this so that we can replace a (sub-)dict item
        #   if the second (etc) JSON file needs to override
        #   an item value set in the first (etc) JSON parameters file.
        for key,item in zip(parameters.keys(),parameters.items()):
            # Check to see if the item is itself a dict
            if isinstance(item[1],dict):
                # If so, step through this source sub-dict
                for subitem in item[1].items():
                    # If the destination sub-dict doesn't exist yet, create it
                    # Either way, add the item to this sub-dict
                    try:
                        # The sub-dict exists: update this key and value
                        parameters_dict[item[0]].update({subitem[0] : subitem[1]})
                    except:
                        # The sub-dict does not exist yet, so set this key and value
                        #   as its first item
                        parameters_dict[item[0]] = {subitem[0] : subitem[1]}
            else:
                # If not a dict, set the key, value
                parameters_dict[key] = item[1] 
                # This should not happen if the parameters file is a set
                #   of sub-dicts only, one per workflow class instance
    return parameters_dict



