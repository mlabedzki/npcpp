GENERAL INSTRUCTIONS OF USE:

1. the npcpp packages provides instant wrappers of vectorized and non vectorized C++ functions
and Python/numpy, both exported function and the arguemnts may be either scalar variables or vectors
2. the prefered type of vectors for C++ in vectorized function cases is std::vector<> which is mapped into numpy array
3. it is possible to compile file also with types such as vect<> struct internally created in this packages
or C array (like double*), but the lattter is not recomended as it require further tweaks after wrapping the function,
4. all variable types that are compatible are types written as 1 word, exception is long long type, in case of pointers it should also be 1 word, e.g. int*.
5. if compilation is done on cpp file then all exported functions should have
before their first line a meta-comment containing 'npcpp::export'
6. arguments definitions in C++ code are expected to be either all in the same line as function name,
or they should be separeted by new line signs, i.e. each argument in a separate line.

USE EXAMPLE:

in Linux we may safely assume that gcc compiler is present, 
in Windows when mingw compiler is present and it is in one of 2 default dirs then it is possible to just use npcpp.sourceCpp function calls, 
first change working directory as it is a reference point for the whole library:

``` Python
import npcpp
os.setdir(path_to_cpp_file)
```

then compilation is possible once function to be exported is saved in cpp file with the line preceeding function definition containing export comment: //npcpp::export 

``` Python
hofstadterq = npcpp.sourceCpp("hofstadterq.cpp")
```

when there is a custom compiler or mingw is in different location then it is possible to define the path for the library by means of class, before the first use create an instance:

``` Python
cpp = npcpp.compiler(your_mingw_bin_path)
```

then the compiler path is already defined when calling functions as method of cpp object:

``` Python
hofstadterq = cpp.sourceCpp("hofstadterq.cpp")
```

alternatively, it is possible to compile from a cpp code inside string like here, the export meta comment will be auto added:

``` Python
hofstadterq = npcpp.cppFunction("""
//https://en.wikipedia.org/wiki/Hofstadter_sequence
std::vector<long long> generateHofstadterQSequence(int n) {
    if (n <= 0) {
        return {}; // Return an empty vector for invalid input.
    }
    std::vector<long long> q_sequence;
    q_sequence.reserve(n); // Pre-allocate memory to avoid reallocations
    if (n >= 1) {
        q_sequence.push_back(1);
    }
    if (n >= 2) {
        q_sequence.push_back(1);
    }
    for (int i = 2; i < n; ++i) {       
        long long next_q = q_sequence[i - q_sequence[i-1]] + q_sequence[i - q_sequence[i-2]];
        q_sequence.push_back(next_q);
    }
    return q_sequence;
}
""")
```

after the function is compiled, it is possible to use the function by the following call:

``` Python
out = hofstadterq.generateHofstadterQSequence(10**7)
print(out[10**7-1])
```

by defult after compiling once, the cpp file may be recompiled using the same call
if there is a need to delete the dll file or stop using it after it is connected to python then without closing the console it can be done as:

``` Python
npcpp.deloadlib(hofstadterq)
```

npcpp.cppFunction saves cpp code from string into temp.cpp in the same folder
