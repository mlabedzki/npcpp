import numpy as np
import os
import _ctypes
import ctypes
import subprocess
import sys
import importlib.machinery
import re

cppTemplate = """#include <vector>

/* Compound C structure for vector imitation */
//typedef struct {
//    double * arr;
//    int size;
//} vect;

template<typename T>
struct vect {
    T* arr;
    int size;
    // Default constructor to initialize members
    vect() : arr(nullptr), size(0) {}
    // Constructor for convenience
    vect(T* _arr, int _size) : arr(_arr), size(_size) {}
    ~vect() {
    }
};

template< typename T>
vect<T> vec2arr (std::vector<T> vec)
{
    vect<T> out;
    out.arr = new T[vec.size()];
    out.size = vec.size();
    //std::copy(vec.begin(), vec.end(), out);
    //for(int i = 0; i < vec.size(); ++i)
    for(typename std::vector<T>::size_type i = 0; i < vec.size(); ++i)
        out.arr[i] = vec[i];
    return out;
}

template< typename T>
vect<T> _vec2arr (std::vector<T> vec)
{
    //vect out;
    //out.arr = &vec[0];
    //out.size = vec.size();
    return {.arr = &vec[0], .size =  vec.size()};
}

template<typename T>
std::vector<T> arr2vec(const vect<T>& x) // Pass by const reference for efficiency and safety
{
    if (x.arr == nullptr || x.size <= 0) {
        return std::vector<T>(); // Return an empty vector for invalid input
    }
    return std::vector<T>(x.arr, x.arr + x.size);
}

"""

class compiler():

    def __init__(self, path):
        self.PATH = path
        self.SYS_TYPE = getSystem()

    def makelib(self, name, sys_type=None):
        return makelib(name, sys_type=sys_type, alt_path=self.PATH)
    
    def loadlib(name,sys_type=None):
        return loadlib(name,sys_type=sys_type)
    
    def deloadlib(self, namespace, sys_type=None, handle_custom=None):
        return deloadlib(namespace,sys_type=sys_type,handle_custom=handle_custom)
    
    def sourceCpp(self, name, recompile=True):
        return sourceCpp(name, recompile=recompile, alt_path=self.PATH)

    def sourceCppSimple(self, name, recompile=True):
        return sourceCppSimple(name, recompile=recompile, alt_path=self.PATH)

    def cppFunction(self, code):
        return cppFunction(code, alt_path=self.PATH)

class vecti(ctypes.Structure):
    #np.ctypeslib.ndpointer(dtype=ctypes.c_double, shape=(n,))    
    #_fields_ = [('arr', ctypes.c_void_p), ('size', ctypes.c_int)]
    _fields_ = [('arr', ctypes.POINTER(ctypes.c_int)), ('size', ctypes.c_int)]
    # Add a slot to store the reference to the original numpy array  
    _numpy_ref = None 
    def __repr__(self):
        return '({0}, {1})'.format(self.arr, self.size)       
    @classmethod
    def fromnp(cls, a):
        # Create a contiguous copy that will own the memory
        a_c = np.ascontiguousarray(a, dtype=ctypes.c_int) #due to different length of int64 and c_int
        # Create the instance
        instance = cls(a_c.ctypes.data_as(ctypes.POINTER(ctypes.c_int)), len(a_c))
        # FIX: Store a reference to the numpy array instance to keep it alive
        instance._numpy_ref = a_c 
        return instance
    @classmethod
    def li(cls,l):
        return cls((ctypes.c_int * len(l))(*l),len(l))
    def tonp(cls):
        return np.array(cls.arr[0:cls.size])   
    
class vectd(ctypes.Structure):
    _fields_ = [('arr', ctypes.POINTER(ctypes.c_double)), ('size', ctypes.c_int)]
    def __repr__(self):
        return '({0}, {1})'.format(self.arr, self.size)       
    @classmethod
    def fromnp(cls, a):
        return cls(a.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),len(a))
    @classmethod
    def li(cls,l):
        return cls((ctypes.c_double * len(l))(*l),len(l))
    def tonp(cls):
        return np.array(cls.arr[0:cls.size])
   
class vectb(ctypes.Structure):
    _fields_ = [('arr', ctypes.POINTER(ctypes.c_bool)), ('size', ctypes.c_int)]
    def __repr__(self):
        return '({0}, {1})'.format(self.arr, self.size)       
    @classmethod
    def fromnp(cls, a):
        return cls(a.ctypes.data_as(ctypes.POINTER(ctypes.c_bool)),len(a))
    @classmethod
    def li(cls,l):
        return cls((ctypes.c_bool * len(l))(*l),len(l))
    def tonp(cls):
        return np.array(cls.arr[0:cls.size])    

class vectll(ctypes.Structure):
    _fields_ = [('arr', ctypes.POINTER(ctypes.c_longlong)), ('size', ctypes.c_int)]
    def __repr__(self):
        return '({0}, {1})'.format(self.arr, self.size)       
    @classmethod
    def fromnp(cls, a):
        return cls(a.ctypes.data_as(ctypes.POINTER(ctypes.c_longlong)),len(a))
    @classmethod
    def li(cls,l):
        return cls((ctypes.c_longlong * len(l))(*l),len(l))
    def tonp(cls):
        return np.array(cls.arr[0:cls.size]) 

def wrap_function(lib, funcname, restype, argtypes):
    """Simplify wrapping ctypes functions"""
    func = lib.__getattr__(funcname)
    func.restype = restype
    func.argtypes = argtypes
    return func

def makelib(name,sys_type=None,alt_path=None):
    pathfilename = os.path.join(os.getcwd(), name)
    if sys_type is None:
        sys_type = getSystem()    
    if sys_type==0:
        shell = "cmd.exe"
        if alt_path is not None:
            mingw_bin_path = alt_path
        else:
            mingw_bin_path = r"C:\RBuildTools\rtools42\x86_64-w64-mingw32.static.posix\bin"
            if not os.path.isdir(mingw_bin_path):
                mingw_bin_path = r"C:\Program Files (x86)\Embarcadero\Dev-Cpp\TDM-GCC-64\bin"
            else:
                print("Compilation failed. Default mingw directories don't exist and alternative path was not provided.")
                return 1
        custom_env = os.environ.copy() # Start with a copy of the current environment
        if mingw_bin_path:
            # Add mingw_bin_path to the PATH for the subprocess
            # Prepend it to ensure it's found before any conflicting tools
            # IMPORTANT: Use os.pathsep (;) for separator on Windows
            #custom_env['PATH'] = f"{mingw_bin_path}{os.pathsep}{custom_env.get('PATH', '')}"
            custom_env['PATH'] = "{}{}{}".format(mingw_bin_path, os.pathsep, custom_env.get('PATH', ''))
        # Chain all commands with ' & '
        command1 = r'g++.exe -c "'+pathfilename+'.cpp" -o "'+pathfilename+'.o" -Wall -std=c++17'
        command2 = r'g++.exe -shared -o "'+pathfilename+'.dll" "'+pathfilename+'.o"'
        commands_list = [command1,command2]    
        full_command_string = " & ".join(commands_list)
    
        # Use cmd /C to execute the command string in a new cmd instance
        cmd_prefix = "{} /C".format(shell) if shell == "cmd.exe" else shell
        final_command = '{0} "{1}"'.format(cmd_prefix, full_command_string) # The command string to pass to subprocess.run
    
        try:
            proc = subprocess.Popen(
                final_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=custom_env,
                creationflags=subprocess.CREATE_NEW_CONSOLE if shell == "cmd.exe" else 0 # This argument is Windows-specific
            )
            print("Errors/Warnings: ", proc.communicate()[1])
            if re.search(r'\b(?:error|fatal error):', str(proc.communicate()[1]), re.IGNORECASE):
                proc = 1
            else:
                proc = 0
            try:
                subprocess.call(["del","'"+pathfilename+".o'"],shell=True)
            except:
                pass
            # see errors here: proc.communicate()[1]
        except:
            pass
    else:   
        proc=subprocess.call(["g++","-fPIC","-c",pathfilename+".cpp"])
        proc+=subprocess.call(["g++","-shared","-o",pathfilename+".so",pathfilename+".o"])
    return proc

def loadlib(name,sys_type=None):
    if sys_type is None:
        sys_type = getSystem()    
    if sys_type==0:    
        #out = ctypes.cdll.LoadLibrary(name+'.dll')
        #out = ctypes.CDLL(name+'.dll', winmode=0)
        dll_dir = os.getcwd()
        os.add_dll_directory(dll_dir)
        out = ctypes.CDLL(os.path.join(dll_dir, name+".dll"))
    else:
        out = ctypes.CDLL(os.getcwd()+'/'+name+".so") 
    return out

def deloadlib(namespace,sys_type=None,handle_custom=None):
    if sys_type is None:
        sys_type = getSystem()
    if handle_custom is not None:
        handle = handle_custom
    else:
        if isinstance(namespace, str):
            try:
                filename = namespace.split('.')[0]
                file = open(filename+"_handle_tmp.txt", "r") 
                handle = int(file.read())
                file.close()
            except:
                pass
        else:
            handle = namespace.handle
            #exec('libname = "'+namespace.libname+'"')
            #exec("lib = namespace."+libname)
            #handle = lib._handle
    if sys_type==0:  
        try:
            _ctypes.FreeLibrary(handle)
            print("DLL with handle " + str(handle) + " was freed")
            del namespace
        except:
            pass
    else:
        try:
            #mylib_handle = mylib._handle
            dlclose_func = ctypes.CDLL(None).dlclose  # This WON'T work on Win
            dlclose_func.argtypes = [ctypes.c_void_p]
            dlclose_func(handle)
            print("DLL with handle " + str(handle) + " was freed")
        except:
            pass

def grabFuncName(line):
    return line.split('(')[0].split()[-1]
    
def translate(input_list):
    if not isinstance(input_list, (list,)):
        input_list = [input_list]
    translation_map = {
        'bool': 'c_bool',
        'bool*': 'POINTER(c_bool)',
        '_Bool': 'c_bool',
        'char': 'c_char',
        'char*': 'c_char_p',
        'double': 'c_double',
        'double*': 'POINTER(c_double)',
        'float': 'c_float',
        'float*': 'POINTER(c_float)',
        'int': 'c_int',
        'int*': 'POINTER(c_int)',
        'short': 'c_short',
        'short*': 'POINTER(c_short)',
        'long': 'c_long',
        'long*': 'POINTER(c_long)',
        'longlong': 'c_longlong',
        'longlong*': 'POINTER(c_longlong)',
        'size_t': 'c_size_t',
        'void': 'None',
        'void*': 'c_void_p',
        'wchar_t': 'c_wchar',
        'wchar_t*': 'c_wchar_p',
        'std::vector<double>': 'vectd',
        'vector<double>': 'vectd',
        'vect<double>': 'vectd',
        'std::vector<float>': 'vectd',
        'vector<float>': 'vectd',
        'vect<float>': 'vectd',        
        'std::vector<int>': 'vecti',
        'vector<int>': 'vecti',
        'vect<int>': 'vecti',
        'std::vector<long>': 'vecti',
        'vector<long>': 'vecti',
        'vect<long>': 'vecti',
        'std::vector<longlong>': 'vectll',
        'vector<longlong>': 'vectll',
        'vect<longlong>': 'vectll', 
        'std::vector<short>': 'vecti',
        'vector<short>': 'vecti',
        'vect<short>': 'vecti',
        'std::vector<bool>': 'vectb',
        'vector<bool>': 'vectb',
        'vect<bool>': 'vectb'}
    output_list = []
    #iterate the input words and append translation
    #(or word if no translation) to the output
    for word in input_list:
        translation = translation_map.get(word)
        output_list.append(translation if translation else word)

    #convert output list back to string
    return output_list

def replace_all_types(mystr):
    mystr = mystr.replace('std::vector<double>', 'vect<double>')        
    mystr = mystr.replace('std::vector<float>', 'vect<float>')
    mystr = mystr.replace('std::vector<short>', 'vect<short>')                
    mystr = mystr.replace('std::vector<int>', 'vect<int>')
    mystr = mystr.replace('std::vector<long>', 'vect<long>')
    mystr = mystr.replace('std::vector<longlong>', 'vect<long long>')
    mystr = mystr.replace('std::vector<bool>', 'vect<bool>')
    return mystr

def do_argument_line(data_i,file):
    fargs = []
    someline = data_i.split(",")
    if len(someline) == 1: #only one case
        fargs.append(someline[0].split(')')[0])
    else:
        if len(someline[1]) > 0 and someline[1]!='\n': #longer line case
            pass #next argument after colon, think about it
        else:
            fargs.append(someline[0].split(')')[0])
    #fargs.append(data_i.split(","))
    #if data_i.find('std::vector<') != -1:
        #vectors.append(len(fargs))
    data_i = data_i.replace('{', '').replace(')', '')
    data_i = replace_all_types(data_i)   
    file.write(data_i)
    return fargs

def make_ext(name,sys_type=0):#the main parsing function
    newcodes = []
    filename = name.split('.')[0]
    with open(name, "r")  as f:
        data = f.readlines()
    for i in range(len(data)):
        data[i] = data[i].replace('long long', 'longlong')
    file = open(filename+"_ext.cpp", "w")
    file.write(cppTemplate)
    if sys_type==0:
        file.write('#define DLLEXPORT extern "C" __declspec(dllexport)\n')
    else:
        file.write('#define DLLEXPORT extern "C"\n')
    file.write('#include "'+name+'"\n\n')
    i=0
    while i < len(data):
        if data[i][0]!='#' and data[i].find("npcpp::export") != -1:
            continues = False
            vectors = []
            vects = []
            fargs = []
            fargs_types = []
            fargs_names = []
            i+=1
            fname = grabFuncName(data[i])
            ftype = data[i].lstrip().split(' ')[0]
            #fargs_types.append(ftype)
            header = 'DLLEXPORT '+ftype+' _'+fname+'(\n'
            if header.find('std::vector') != -1:
                vectors.append(0)            
                header = replace_all_types(header)
            if header.find('vect<') != -1:#needed?
                vects.append(0)           #needed?  
            file.write(header)               
            firstline = data[i]
            #check if there are arguments
            firstline = firstline.split('(')
            if len(firstline) > 1: #both fname and argnames in 1 line
                if len(firstline[1]) > 0 and firstline[1]!='\n': #longer line case
                    firstline_args = firstline[1].replace('{', '').replace(')', '').split(',')
                    if firstline_args[len(firstline_args )-1] == '\n':
                        firstline_args = firstline_args[0:(len(firstline_args)-1)]
                        continues = True
                    elif ('\n' in firstline_args[len(firstline_args )-1]) and (')' not in firstline[1]):
                        continues = True
                    fargs.append(firstline_args)
                    #for case when function line is 1-liner
                    fargs=fargs[0] #newline as we had [list]
                    for j in range(0,len(fargs)):
                        altfarg = replace_all_types(fargs[j])
                        file.write(altfarg)
                        if j!=len(fargs)-1:
                            file.write(',')
                        elif continues:
                            pass
                        else:
                            file.write('){')
            if data[i].find(')') == -1:
                while data[i].find(')') == -1: #loop for arguments here
                    i+=1
                    #data_i = data[i].split(')')
                    #if len(data_i)==0:
                        
                    if data[i].lstrip().find(')') != 0:
                        if continues:
                            file.write(',')
                            continues = False
                        fargs.extend(do_argument_line(data[i],file))
                file.write(')\n{\n')
            if continues:
                pass#file.write(',')
                #continues = False
            #special case for last argument, the one with ')'
            if data[i].find(')') != -1:
                if data[i].find('{') == -1: #if begin sign is not present move one extra
                    i+=1
                    #file.write('{\n')
                if ftype.find('vector') != -1:
                    file.write('\treturn vec2arr('+fname+'(')
                else:
                    file.write('\treturn '+fname+'(')
                for j in range(0,len(fargs)):
                    nz = fargs[j].split('=')
                    z = nz[0].lstrip().split(' ')
                    if len(nz)>1:
                        val = ' = '+(str(nz[1]).strip().capitalize()).replace(')','').replace('\n','')
                    else:
                        val = ''
                    argtype = z[0].replace('\t','')
                    fargs_types.append(argtype)
                    if len(z)>1:
                        fargs_names.append(z[1]+val)
                    else:
                        fargs_names.append(z[0])
                    if argtype.find('vector') != -1:                        
                        arg = 'arr2vec('+z[1]+')'
                        vectors.append(j+1)
                    else:
                        if len(z)>1:    
                            arg = z[1]
                        else:
                            arg = z[0]
                    if argtype.find('vect<') != -1:
                        vects.append(j+1)
                    if j==0:
                        file.write(arg)
                    else:
                        file.write(', '+arg)
                if ftype.find('vector') != -1:                        
                    file.write('));\n')
                else:
                    file.write(');\n')                    
                file.write('}\n')
            newcodes.append([fname,translate(ftype)[0],translate(fargs_types),fargs_names,vectors,vects])
        else:
            i+=1
    file.close()
    return newcodes

def list2str(somelist):
    return '['+', '.join(somelist)+']'

def make_wrapper(filename,codes):
    if (not codes[4]) and (not codes[5]):
        return codes[0]+' = wrap_function('+filename+', \'_'+codes[0]+'\', '+codes[1]+', '+list2str(codes[2])+')'
    else:
        return codes[0]+'_ = wrap_function('+filename+', \'_'+codes[0]+'\', '+codes[1]+', '+list2str(codes[2])+')'

def np_wrap(arg_types,arguments,vectors,vects):
    newcodes = []
    i=0
    for a in arguments:
        i+=1        
        if (i in vectors) or (i in vects):
            newcodes.append(arg_types[i-1]+'.fromnp('+a.split('=')[0]+')')
        else:#
            newcodes.append(a.split('=')[0])
    return ', '.join(newcodes)        
    
def make_np_wrapper(codes):
    if (0 in codes[4]) or (0 in codes[5]):
        end = '.tonp()'
    else:
        end = ''
    return 'def '+codes[0]+'('+', '.join(codes[3])+'):\n\treturn '+codes[0]+'_('+np_wrap(codes[2],codes[3],codes[4],codes[5])+')'+end

def getSystem():
    if sys.platform == "win32":
        sys_type=0
    elif sys.platform == "linux" or sys.platform == "linux2":
        sys_type=1
    elif sys.platform == "darwin":#OSX
        sys_type=2
    return sys_type

def cppFunction(code,alt_path=None):
    lines = code.split('\n')
    file = open("temp.cpp", "w")
    header = True
    for l in lines:
        if l!='':
            if len(l)>=15:
                if l[0:15]=="//npcpp::export":
                    header = False
            if header and l[0]!='#' and l[0:2] not in ('/*',' *', '*/', '//'):
                file.write("//npcpp::export\n")
                header = False
        file.write(l+'\n')
    file.close()
    return sourceCpp("temp.cpp",recompile=True,alt_path=alt_path)

def sourceCpp(name,recompile=True,alt_path=None):
    libname, proc = prepImport(name,recompile=recompile,alt_path=alt_path)
    file_path = os.path.join("", libname+".py")
    if proc==0:
        return load_dynamic_module_from_file(file_path)
    else:
        raise ValueError("Loading cannot happen as compilation was not successfull.")

def prepImport(name,recompile=True,alt_path=None):
    sys_type = getSystem()
    filename = name.split('.')[0]
    if os.path.isfile(filename+"_ext.dll")==1:
        try:
            file = open(filename+"_handle_tmp.txt", "r") 
            handle = int(file.read())
            file.close()
            deloadlib(None,sys_type,handle)
        except:
            pass
    newcodes = make_ext(name,sys_type)
    if recompile:
        proc = makelib(filename+"_ext",sys_type,alt_path=alt_path)
    else:
        proc = 0        
    fnames = [c[0] for c in newcodes]
    if filename in fnames:
        libname = filename + '_lib'    
    else:
        libname = filename
    if proc==0:
        #libname = loadlib(filename+"_ext",sys_type) # not needed as will be done in external py file
        #libname cannot be equal to any of imported functions, so if filename matches fname we extend
        file = open(libname+".py","w")
        file.write('from npcpp import *\n')
        file.write('from ctypes import *\n')
        file.write(libname+" = loadlib(r'"+filename+"_ext',"+str(sys_type)+")\n")
        file.write("handle = "+libname+"._handle\n")
        for code in newcodes:
            file.write(make_wrapper(libname,code)+'\n')
            if code[4] or code[5]:
                file.write(make_np_wrapper(code)+'\n')
            #exec(code)
        file.write("file = open('"+filename+"_handle_tmp.txt', 'w')\n")
        file.write("file.write(str("+libname+"._handle))\n")
        file.write("file.close()\n")
        file.close()       
    return libname, proc

#below sourceCpp version wraps on the fly instead of creating more files
#loadAll and hence sourceCppSimple work in py2 normally and in py3 only when exported function doesnt have vector args and doesnt return vector
def sourceCppSimple(name,recompile=True,alt_path=None):
    return Namespace(**loadAll(name,recompile=recompile,alt_path=alt_path))

def loadAll(name,recompile=True,alt_path=None):
    sys_type = getSystem()
    filename = name.split('.')[0]
    if os.path.isfile(filename+"_ext.dll")==1:
        try:
            file = open(filename+"_handle_tmp.txt", "r") 
            handle = int(file.read())
            file.close()
            deloadlib(None,sys_type,handle)
        except:
            pass    
    newcodes = make_ext(name,sys_type)
    if recompile:
        proc = makelib(filename+"_ext",sys_type,alt_path=alt_path)
    else:#success returns 0
        proc = 0
    #filename is going to be used as lib name in py, it cannot be equal to any of imported functions
    fnames = [c[0] for c in newcodes]
    if filename in fnames:
        libname = filename + '_lib'    
    else:
        libname = filename
    if proc==0:
        libname_instance = loadlib(filename+"_ext",sys_type)
        handle = libname_instance._handle
        exec(libname+"=libname_instance")
        del libname_instance
        #exec(libname+" = loadlib('"+filename+"_ext',sys_type)")
        #exec('handle = '+libname+'._handle')
        for code in newcodes:
            exec(make_wrapper(libname,code))
            if code[4]:
                exec(make_np_wrapper(code))
        file = open(filename+"_handle_tmp.txt", "w")
        try:
            file.write(str(handle))
        except:
            pass
        file.close()        
    else:
        raise ValueError("Loading cannot happen as compilation was not successfull.")
    return locals()

class Namespace(object):
    """
    A simple class to mimic types.SimpleNamespace for Python 2.
    Allows accessing dictionary items as attributes.
    """
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        # For a better representation when printing the object
        attrs = ', '.join("%s=%r" % (k, v) for k, v in self.__dict__.items())
        return "Namespace(%s)" % attrs
    
def load_dynamic_module_from_file(file_path):
    """
    Loads a Python module from the given file path.
    """
    if not os.path.exists(file_path):
        raise IOError("Dynamic module file not found: %s" % file_path)

    # Get a unique module name from the file path
    # We'll use the base name without extension, e.g., 'dynamic_module_advanced_sim_config'
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    # Check if module is already loaded to prevent redundant loading
    if module_name in sys.modules:
        sys.stdout.write("Module '%s' already loaded. Returning updated instance.\\n" % module_name)
        return sys.modules[module_name]

    try:
        # imp.load_source(name, pathname) is the Python 2 way to load
        # a module from a specific file path.
        # It executes the file and returns the module object.
        # It also adds the module to sys.modules.
        sys.stdout.write("Loading dynamic module '%s' from '%s'...\\n" % (module_name, file_path))
        dynamic_module = importlib.machinery.SourceFileLoader(module_name, file_path).load_module()
        #dynamic_module = imp.load_source(module_name, file_path)
        sys.stdout.write("Successfully loaded dynamic module '%s'.\\n" % module_name)
        return dynamic_module
    except Exception as e:
        sys.stderr.write("Error loading dynamic module from '%s': %s\\n" % (file_path, e))
        raise

#
# GENERAL INSTRUCTIONS OF USE:
#
# 1. the npcpp packages provides instant wrappers of vectorized and non vectorized C++ functions
# and Python/numpy, both exported function and the arguemnts may be either scalar variables or vectors
# 2. the prefered type of vectors for C++ in vectorized function cases is std::vector<> which is mapped into numpy array
# 3. it is possible to compile file also with types such as vect<> struct internally created in this packages
# or C array (like double*), but the lattter is not recomended as it require further tweaks after wrapping the function,
# 4. all variable types that are compatible are types written as 1 word, exception is long long type, in case of pointers it should also be 1 word, e.g. int*.
# 5. if compilation is done on cpp file then all exported functions should have
# before their first line a meta-comment containing 'npcpp::export'
# 6. arguments definitions in C++ code are expected to be either all in the same line as function name,
# or they should be separeted by new line signs, i.e. each argument in a separate line.
#
# USE EXAMPLE:
#
# #in Linux we may safely assume that gcc compiler is present,
# #in Windows when mingw compiler is present and it is in one of 2 default dirs then it is possible to just use npcpp.sourceCpp function calls, 
# #first change working directory as it is a reference point for the whole library:
#
# import npcpp
# os.setdir(path_to_cpp_file)
#
# #then compilation is possible once function to be exported is saved in cpp file with the line preceeding function definition containing export comment: //npcpp::export 
# hofstadterq = npcpp.sourceCpp("hofstadterq.cpp")
#
# #when there is a custom compiler or mingw is in different location then it is possible to define the path for the library by means of class, before the first use create an instance:
# cpp = npcpp.compiler(your_mingw_bin_path)
# #then the compiler path is already defined when calling functions as method of cpp object:
# hofstadterq = cpp.sourceCpp("hofstadterq.cpp")
#
# #alternatively, it is possible to compile from a cpp code inside string like here, the export meta comment will be auto added:
# hofstadterq = npcpp.cppFunction("""
# //https://en.wikipedia.org/wiki/Hofstadter_sequence
# std::vector<long long> generateHofstadterQSequence(int n) {
#     if (n <= 0) {
#         return {}; // Return an empty vector for invalid input.
#     }
#     std::vector<long long> q_sequence;
#     q_sequence.reserve(n); // Pre-allocate memory to avoid reallocations
#     if (n >= 1) {
#         q_sequence.push_back(1);
#     }
#     if (n >= 2) {
#         q_sequence.push_back(1);
#     }
#     for (int i = 2; i < n; ++i) {       
#         long long next_q = q_sequence[i - q_sequence[i-1]] + q_sequence[i - q_sequence[i-2]];
#         q_sequence.push_back(next_q);
#     }
#     return q_sequence;
# }
# """)
#
# #after the function is compiled, it is possible to use the function by following call:
# out = hofstadterq.generateHofstadterQSequence(10**7)
# print(out[10**7-1])
#
# #by defult after compiling once, the cpp file may be recompiled using the same call
# #if there is a need to delete the dll file or stop using it after it is connected to python then without closing the console it can be done as:
# npcpp.deloadlib(hofstadterq)
#
# #npcpp.cppFunction saves cpp code from string into temp.cpp in the same folder
#