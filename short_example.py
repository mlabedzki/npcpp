import os
import time
# change dir to place where npcpp is saved and testing will also happen
os.chdir(r'C:\Users\mlabedzki\Documents\Python')
import npcpp

# first install either Rcpp package through Rstudio, which should install compiler here:
# mingw_bin_path = r"C:\RBuildTools\rtools42\x86_64-w64-mingw32.static.posix\bin"
# or download from github a release of Dev-Cpp IDE with compiler in 7z portable format:
# https://github.com/Embarcadero/Dev-Cpp/releases/download/v6.3/Embarcadero_Dev-Cpp_6.3_TDM-GCC_9.2_Portable.7z
# unpack then provide path such as:
# mingw_bin_path = r'C:\Users\mlabedzki\Downloads\Embarcadero_Dev-Cpp\TDM-GCC-64\bin"
# in my case I have full install so I am using below address:
mingw_bin_path = r"C:\Program Files (x86)\Embarcadero\Dev-Cpp\TDM-GCC-64\bin"

cpp = npcpp.compiler(mingw_bin_path)

hofstadterq = cpp.cppFunction("""
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

#alternative code using python only for benchmarking
def generate_hofstadter_q_sequence(n):
    if n <= 0:
        return []
    if n == 1:
        return [1]   
    q_sequence = [1, 1]
    for i in range(2, n):
        index_1 = (i + 1) - q_sequence[i - 1] - 1
        index_2 = (i + 1) - q_sequence[i - 2] - 1
        q_sequence.append(q_sequence[index_1] + q_sequence[index_2])   
    return q_sequence

seq_count = 10**7

start_time = time.time()
outcpp = hofstadterq.generateHofstadterQSequence(seq_count)
end_time = time.time()
c1 = end_time-start_time
print(c1)

start_time = time.time()
outpy = generate_hofstadter_q_sequence(seq_count)
end_time = time.time()
c2 = end_time-start_time
print(c2)

outcpp[seq_count-1] == outpy[seq_count-1]

#different method to assess performance - working only in ipython console
%timeit hofstadterq.generateHofstadterQSequence(int(seq_count/100))
%timeit generate_hofstadter_q_sequence(int(seq_count/100))

#to free temp.dll file from being used:
npcpp.deloadlib(hofstadterq)
