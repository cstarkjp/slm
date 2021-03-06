"""
---------------------------------------------------------------------

Perform ``slm`` analysis of topographic structure, including channels, 
channel heads, hillslope lengths (HSL), and relationships between HSL, aspect,
etc.

---------------------------------------------------------------------

Requires Python packages/modules:
  - :mod:`json`
  - :mod:`datetime`
  - :mod:`dateutil.tz`

Imports the following ``Streamlines`` modules:
 - :mod:`.connect`
 - :mod:`.channelheads`
 - :mod:`.countlink`
 - :mod:`.label`
 - :mod:`.segment`
 - :mod:`.hillslopes`
 - :mod:`.lengths`

Imports the folllowing classes:
 - :class:`.Core`
 - :class:`.State`
 - :class:`.Geodata`
 - :class:`.Preprocess`
 - :class:`.Trace`
 - :class:`.Analysis`
 - :class:`.Mapping`
 - :class:`.Plot`
 - :class:`.Save`

Imports functions from :mod:`useful <streamlines.useful>`.

---------------------------------------------------------------------

.. _json: https://docs.python.org/3/library/json.html
.. _datetime: https://docs.python.org/3/library/datetime.html
.. _dateutil: https://pypi.org/project/python-dateutil/

"""

from json     import loads
from datetime import datetime
from dateutil import tz
import os
os.environ['PYTHONUNBUFFERED']='True'

from streamlines.core       import Core
from streamlines.parameters import read_json_file, import_parameters
from streamlines.state      import State
from streamlines.geodata    import Geodata
from streamlines.preprocess import Preprocess
from streamlines.trace      import Trace
from streamlines.analysis   import Analysis
from streamlines.mapping    import Mapping
from streamlines.plot       import Plot
from streamlines.save       import Save

__all__ = ['Streamlining']

pdebug = print

class Streamlining(Core):
    """
    Args:
        **kwargs (list): Keyword arguments.

    Class providing set of methods to compute streamline trajectories and 
    densities from raw DTM data.
    
    Inherits the :class:`Core <.Core>` class.

    
    Provides top-level methods to: 
        - TBD
        - prepare DTM grid for streamline computation
          by fixing blockages (single-diagonal-outflow pixels) and loops 
          (divergence, curl and net vector magnitude exceeding trio of thresholds)
        - set 'seed' points aka start locations (sub-pixel positions) of all streamlines 
        - generate streamlines
          from all seed points either upstream or downstream, returning seed point 
          locations if generated in-situ, and returning arrays of streamline points 
          and their mean spacing
        - generate all streamlines (up and downstream) and compute the overall
          mean streamline point spacing
          
    Instantiates and assigns to self attributes each of the principal workflow classes:
         - :class:`State <.State>` 
         - :class:`Geodata <.Geodata>` 
         - :class:`Preprocess <.Preprocess>` 
         - :class:`Trace <.Trace>` 
         - :class:`Analysis <.Analysis>` 
         - :class:`Mapping <.Mapping>` 
         - :class:`Plot <.Plot>` 
         - :class:`Save <.Save>` 

    

    
        """  
    def __init__(self, **kwargs):
        """
        Args:
            **kwargs (list): Keyword arguments.
    
        Initialize the principal 'streamlines' class instance, whose object
        will contain references to the each of the key class instances of 
        the streamlines workflow, e.g., geodata(), trace(), analysis()
        

        Attributes:
            parameters_file (str): Name of JSON parameters file 
                                   (parsed from kwargs 'parameters_file')
            parameters_dir (str): Path to folder containing JSON parameters file 
                                  (parsed from kwargs 'parameters_file')
        

        """
        
        # Are we running in a notebook?
        environment = os.path.basename(os.environ['_'])
        notebook_path = os.path.realpath(
            os.path.join((*os.path.split(os.getcwd())),'..','..'))
        if 'notebook' not in environment and 'jupyter' not in environment \
            and  'ipython' not in environment:
            environment = 'shell (probably)'
        print('Environment:',environment)
        
        #
        # Parse workflow parameters in JSON files and command line
        #
        if 'parameters_file' not in kwargs.keys() or kwargs['parameters_file'] is None:
            parameters_path = ''
            parameters_file = 'defaults'
#             raise ValueError('Must specify a parameters JSON file')
        else:
            parameters_path, parameters_file  = os.path.split(kwargs['parameters_file'])
        # Remove trailing .json for now if there is one
        parameters_file = ''.join(parameters_file.split('.json',-1))
        
        # Look for the JSON file in several likely places
        if parameters_path=='':   
            # Try the current directory - in UNIX, the dir from which slm was invoked         
            possible_paths = ['.']
            # Try the slm "home" dir given in the SLM environment variable
            try:
                possible_paths += [os.path.join(os.environ['SLM'],'json')]
            except:
                pass
            # Try the likely relative path to JSON parameters file
            try:
                possible_paths += [os.path.join(os.path.realpath('.'),'..','Parameters')]
            except:
                pass
#             guess = os.path.join(os.path.realpath('.'),'..','Parameters')
#             if os.path.isdir(guess):
#                 possible_paths += [guess]
            for path in possible_paths:
                real_path = os.path.realpath(os.path.join(path, parameters_file+'.json'))
#                 pdebug('path?',path,real_path)
                if os.path.isfile(real_path):
                    parameters_path = path
                    break
            # If we still can't find the specified JSON file, bail
            if parameters_path=='':
                raise ValueError('Cannot find JSON parameters file "{0}.json" in {1}'
                                 .format(parameters_file,possible_paths))
        parameters_path = os.path.realpath(parameters_path)
        
        # Read in parameters and assign to the State class instance
        imported_parameters, slm_path, slmnb_path \
            = import_parameters(parameters_path, parameters_file)
        if ( ('verbose' not in kwargs.keys() or kwargs['verbose'] is None and 
                  'verbose' in imported_parameters['state'].keys() 
                   and imported_parameters['state']['verbose']) 
             or ('verbose' in kwargs.keys() and kwargs['verbose'] is not None 
                   and kwargs['verbose'])):
            # dateutil seems like best way to insert local TZ info into naive datetime
            now = datetime.now().replace(tzinfo=tz.tzlocal())            
            print(now.strftime('\n%a %Y-%m-%d %H:%M:%S %Z%z'))
            print('\n**Initialization begin**') 
            print('Loaded JSON parameters file "{}"'
                  .format(os.path.realpath(os.path.join(parameters_path, 
                                                        parameters_file+'.json'))))
        # If the command line requires override of JSON-file parameters, make it happen
        try:
            override_parameters = kwargs['override_parameters']
        except:
            override_parameters = None
        if override_parameters is not None and override_parameters!='':
            # The override parameter string is itself JSON data 
            override_dict = loads(override_parameters)
            for item in override_dict.items():
                imported_parameters[item[0]].update(item[1])

        # Instantiate the workflow "state"
        self.state = State(None,imported_parameters)
        # Record the JSON parameters file path & name 
        self.state.parameters_path = parameters_path
        self.state.parameters_file = parameters_file

        # Parse command line args and assign to State attributes in most cases
        for item in kwargs.items():
            if item[0]=='do_plot':
                if item[1]=='0' or item[1]=='off' or item[1]=='false':
                    self.state.do_plot=False
                elif item[1]=='maps':
                    self.state.do_plot=True
                    imported_parameters['plot']['do_plot_maps']=True
                    imported_parameters['plot']['do_plot_distributions']=False
                elif item[1]=='pdfs' or item[1]=='distributions':
                    self.state.do_plot=True
                    imported_parameters['plot']['do_plot_maps']=False
                    imported_parameters['plot']['do_plot_distributions']=True
                elif item[1]=='all' or item[1]=='1' \
                        or item[1]=='True' or item[1]=='true':
                    self.state.do_plot=True
                    imported_parameters['plot']['do_plot_maps']=True
                    imported_parameters['plot']['do_plot_distributions']=True
                elif item[1] is not None:
                    self.state.do_plot = item[1]
            elif item[1] is not None:
                setattr(self.state, item[0],item[1])
        # Used by State.inventorize_run_state() and other State methods
        self.state.obj_list=[self.state]
        
        # Build list of paths to likely git repos
        repo_search_list = [['slm',  slm_path]]
        if 'notebook' in environment or 'jupyter' in environment \
            or  'ipython' in environment:
            repo_search_list += [['notebook', notebook_path]]
        else:
            environment = 'shell (probably)'
            
        # Likely git repo for JSON file
        json_path = os.path.realpath(
            os.path.join(os.path.realpath(parameters_path),'..','..'))
        repo_search_list += [['parameters', json_path]]
        json_path = os.path.realpath(
            os.path.join(os.path.realpath(parameters_path),'..','..','..'))
        repo_search_list += [['parameters', json_path]]
        
        # Instantiate slm data class instance
        self.geodata = Geodata(self.state,imported_parameters)
        repo_search_list += [['data', self.geodata.data_path[0]]]
                

#         print('repo_search_list:',repo_search_list)
        # Try to fetch latest slm-related git repo information
        #   - notably the commit hash, author, date & time
        if self.state.do_git_info:
            # Avoid the need to have the Python git module installed
            #   by only importing if do_git_info is true
            import git
            for repo_name, repo_path in repo_search_list:
#                 print(repo_name,repo_path)
                print('{} repo path: {}'.format(repo_name,repo_path))
                try:
                    # Create a short-lived git repo class instance
                    repo = git.Repo(repo_path)
                    # Grab its summary - seems to be the fastest way to get git info
                    summary = repo.git.show('--summary').split('\n')
                    git_info = [  [summary[0]]+[summary[1].split(' <')[0]]+[summary[2]] 
                                + ([summary[4]] if summary[4]!='' else []) 
                                + ([summary[5]] if summary[5]!='' else []) ]
                    setattr(self.state,repo_name+'_gitinfo',git_info)
                    # Print git info if verbose mode is on
                    self.print('{} repo info:'.format(repo_name))
                    self.pprint(git_info)
                except:
                    pass
        
        # Instantiate slm workflow classes
        self.preprocess = Preprocess(self.state,imported_parameters,self.geodata)
        self.trace      = Trace(self.state,imported_parameters,self.geodata,
                                self.preprocess)
        self.analysis   = Analysis(self.state,imported_parameters,self.geodata,
                                    self.preprocess, self.trace)
        self.mapping    = Mapping(self.state,imported_parameters,
                                  self.geodata,self.preprocess,self.trace,self.analysis)
        self.plot       = Plot(self.state,imported_parameters, self.geodata,
                               self.preprocess, self.trace, self.analysis, self.mapping)
        # Hackish way to allow plotting from mapping
        self.mapping._augment(self.plot)
        self.analysis._augment(self.mapping)
        self.save       = Save(self.state,imported_parameters,
                               self.geodata, self.preprocess, self.analysis, 
                               self.trace, self.mapping, self.plot)
        # Used by State.save_state()
        self.state.trace = self.trace
                             
        self.print('**Initialization end**\n') 
    
