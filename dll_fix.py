import os
import ctypes
import sys

def apply_dll_fix():
    # print("DEBUG: Applying DLL Fix from dll_fix.py...")
    try:
        import torch
        
        # 1. Add Torch Lib to DLL Search
        torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
        if os.path.exists(torch_lib):
            os.add_dll_directory(torch_lib)
            # print(f"DEBUG: Added {torch_lib} to DLL directory.")
        
        # 2. Add Current Directory to DLL Search (Crucial for zlibwapi.dll if in root)
        cwd = os.getcwd()
        try:
            os.add_dll_directory(cwd)
            # print(f"DEBUG: Added {cwd} to DLL directory.")
        except:
            pass
            
        # Aggressively load all CuDNN and CuBLAS DLLs
        # Search locations: Torch Lib, Current Dir
        search_paths = [torch_lib, cwd]
        
        dlls_to_load = [
            "zlibwapi.dll", 
            "cublas64_12.dll", "cublasLt64_12.dll",
            "cudnn_ops_infer64_9.dll", "cudnn_cnn_infer64_9.dll", 
            "cudnn_adv_infer64_9.dll", "cudnn64_9.dll",
            "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll", "cudnn_adv64_9.dll"
        ]
        
        for dll_name in dlls_to_load:
            loaded = False
            for search_path in search_paths:
                dll_path = os.path.join(search_path, dll_name)
                if os.path.exists(dll_path):
                    try:
                        ctypes.CDLL(dll_path)
                        # print(f"DEBUG: Loaded {dll_name} from {search_path}")
                        loaded = True
                        break 
                    except Exception as load_err:
                        print(f"Warning: Failed manual load of {dll_name} from {search_path}: {load_err}")
            
            if not loaded and dll_name == "zlibwapi.dll":
                 # Zlibwapi is critical
                 print(f"WARNING: {dll_name} not found in search paths. CUDA may crash.")
                 
    except Exception as e:
        print(f"Warning: DLL injection failed: {e}")

# Apply immediately on import
apply_dll_fix()
