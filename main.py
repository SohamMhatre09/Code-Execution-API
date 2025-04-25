# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os
import time
import tempfile
import shutil
import logging
from typing import List, Optional
import json
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("code_execution_api")

app = FastAPI(title="Code Execution API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Base directory for all assignment environments
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "environments")
os.makedirs(BASE_DIR, exist_ok=True)

# Pydantic models for request validation
class AssignmentCreate(BaseModel):
    assignment_name: str
    language: str  # 'python', 'javascript', or 'cpp'
    requirements: List[str] = []

class CodeExecution(BaseModel):
    assignment_name: str
    code: str

class ExecutionResult(BaseModel):
    output: str
    error: str
    execution_time: float

@app.get("/")
def read_root():
    return {"message": "Code Execution API is running"}

@app.post("/create/assignment")
def create_assignment(assignment_data: AssignmentCreate):
    """Create a new environment for an assignment with specified requirements"""
    assignment_name = assignment_data.assignment_name
    language = assignment_data.language.lower()
    requirements = assignment_data.requirements
    
    # Validate assignment name (alphanumeric with underscores)
    if not assignment_name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Assignment name must be alphanumeric with underscores")
    
    # Check if assignment already exists
    assignment_dir = os.path.join(BASE_DIR, assignment_name)
    if os.path.exists(assignment_dir):
        # Delete the existing assignment directory before recreating
        logger.info(f"Assignment '{assignment_name}' already exists - deleting previous data")
        try:
            shutil.rmtree(assignment_dir)
        except Exception as e:
            logger.error(f"Failed to delete existing assignment: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete existing assignment: {str(e)}")
    
    # Check if language is supported
    if language not in ["python", "javascript", "cpp"]:
        raise HTTPException(status_code=400, 
                           detail=f"Language '{language}' is not supported. Supported languages: python, javascript, cpp")
    
    try:
        # Create assignment directory
        os.makedirs(assignment_dir, exist_ok=True)
        
        # Create a metadata file to track language and requirements
        metadata = {
            "language": language,
            "requirements": requirements,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(os.path.join(assignment_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        logger.info(f"Created directory for assignment: {assignment_name} with language: {language}")
        
        # Language-specific setup
        try:
            if language == "python":
                setup_python_environment(assignment_dir, requirements)
            elif language == "javascript":
                setup_javascript_environment(assignment_dir, requirements)
            elif language == "cpp":
                setup_cpp_environment(assignment_dir, requirements)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Some requirements could not be installed: {str(e)}")
            # We'll continue with the assignment creation even if some requirements failed
        
        return {
            "message": f"Assignment '{assignment_name}' created successfully",
            "assignment_name": assignment_name,
            "language": language,
            "requirements": requirements
        }
    
    except Exception as e:
        logger.error(f"Unexpected error creating assignment: {str(e)}")
        # Clean up if there was an error
        if os.path.exists(assignment_dir):
            shutil.rmtree(assignment_dir)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def setup_python_environment(assignment_dir, requirements):
    """Set up a Python virtual environment with specified requirements"""
    # Create virtual environment
    venv_dir = os.path.join(assignment_dir, "venv")
    subprocess.run(["python", "-m", "venv", venv_dir], check=True)
    logger.info(f"Created Python virtual environment at {venv_dir}")
    
    # Install requirements if any
    if requirements:
        if os.name == 'nt':  # Windows
            pip_path = os.path.join(venv_dir, "Scripts", "pip")
        else:  # Unix-like
            pip_path = os.path.join(venv_dir, "bin", "pip")
        
        # Upgrade pip first
        try:
            # Add --no-index flag if we need to work completely offline
            subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not upgrade pip, continuing with installation: {str(e)}")
        
        # Install each requirement with enhanced error handling
        failed_requirements = []
        for req in requirements:
            try:
                # Try with hash verification
                subprocess.run([pip_path, "install", "--prefer-binary", req], check=True)
                logger.info(f"Successfully installed {req}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed strict install for {req}: {str(e)}")
                try:
                    # Try bypassing hash verification
                    subprocess.run([pip_path, "install", "--prefer-binary", "--no-cache-dir", 
                                   "--disable-pip-version-check", req], check=True)
                    logger.info(f"Successfully installed {req} (hash check bypassed)")
                except subprocess.CalledProcessError as e:
                    # Fall back to package name without version
                    if any(op in req for op in ["==", ">=", "<="]):
                        package_name = req.split("==")[0].split(">=")[0].split("<=")[0]
                        try:
                            subprocess.run([pip_path, "install", "--prefer-binary", 
                                          "--no-cache-dir", package_name], check=True)
                            logger.info(f"Successfully installed {package_name} (without version constraint)")
                        except subprocess.CalledProcessError:
                            failed_requirements.append(req)
                    else:
                        failed_requirements.append(req)
        
        if failed_requirements:
            logger.warning(f"Could not install some requirements: {failed_requirements}")
        else:
            logger.info(f"Installed all Python requirements: {requirements}")

def setup_javascript_environment(assignment_dir, requirements):
    """Set up a Node.js environment with specified npm packages"""
    # Create package directory
    pkg_dir = os.path.join(assignment_dir, "node_modules")
    os.makedirs(pkg_dir, exist_ok=True)
    
    # Create package.json
    package_json = {
        "name": os.path.basename(assignment_dir),
        "version": "1.0.0",
        "description": "Assignment environment",
        "dependencies": {}
    }
    
    # Write package.json
    with open(os.path.join(assignment_dir, "package.json"), "w") as f:
        json.dump(package_json, f, indent=2)
    
    # Install npm packages if any
    if requirements:
        # Package name mappings for common errors
        package_mappings = {
            "tensorflow-js": "@tensorflow/tfjs",
            "three.js": "three"
        }
        
        # Update requirements with correct package names
        corrected_requirements = []
        for req in requirements:
            if req in package_mappings:
                corrected_requirements.append(package_mappings[req])
                logger.info(f"Corrected package name: {req} -> {package_mappings[req]}")
            else:
                corrected_requirements.append(req)
        
        # Install packages one by one with error handling
        failed_packages = []
        for package in corrected_requirements:
            try:
                # Use --no-fund and --no-audit to reduce network calls
                # Use --prefer-offline to use cached packages when possible
                cmd = ["npm", "install", "--prefer-offline", "--no-fund", "--no-audit", 
                       "--prefix", assignment_dir, package]
                subprocess.run(cmd, check=True)
                logger.info(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to install {package}: {str(e)}")
                failed_packages.append(package)
        
        if failed_packages:
            logger.warning(f"Could not install some packages: {failed_packages}")
        else:
            logger.info(f"Installed all JavaScript packages: {corrected_requirements}")

def setup_cpp_environment(assignment_dir, requirements):
    """Set up a C++ environment (minimal setup as requirements handling would be complex)"""
    # Create src and build directories
    src_dir = os.path.join(assignment_dir, "src")
    build_dir = os.path.join(assignment_dir, "build")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)
    
    # Create a simple CMakeLists.txt for building C++ programs
    cmake_content = """
cmake_minimum_required(VERSION 3.10)
project(CppAssignment)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Add executable target
add_executable(program src/main.cpp)
"""
    
    with open(os.path.join(assignment_dir, "CMakeLists.txt"), "w") as f:
        f.write(cmake_content)
    
    logger.info(f"Created C++ environment with CMake configuration")

@app.post("/execute/code", response_model=ExecutionResult)
def execute_code(execution_data: CodeExecution):
    """Execute code in the specified assignment environment"""
    assignment_name = execution_data.assignment_name
    code = execution_data.code
    
    # Check if assignment exists
    assignment_dir = os.path.join(BASE_DIR, assignment_name)
    if not os.path.exists(assignment_dir):
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_name}' not found")
    
    try:
        # Read metadata to determine language
        with open(os.path.join(assignment_dir, "metadata.json"), "r") as f:
            metadata = json.load(f)
        
        language = metadata.get("language", "python")  # Default to python if not specified
        
        # Execute code based on language
        if language == "python":
            return execute_python_code(assignment_dir, code)
        elif language == "javascript":
            return execute_javascript_code(assignment_dir, code)
        elif language == "cpp":
            return execute_cpp_code(assignment_dir, code)
        else:
            logger.error(f"Unsupported language: {language}")
            return {
                "output": "",
                "error": f"Unsupported language: {language}",
                "execution_time": 0.0
            }
    
    except FileNotFoundError as e:
        logger.error(f"Assignment metadata not found: {str(e)}")
        return {
            "output": "",
            "error": f"Assignment metadata not found: {str(e)}",
            "execution_time": 0.0
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid assignment metadata: {str(e)}")
        return {
            "output": "",
            "error": f"Invalid assignment metadata: {str(e)}",
            "execution_time": 0.0
        }
    
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        return {
            "output": "",
            "error": f"Execution error: {str(e)}",
            "execution_time": 0.0
        }

def execute_python_code(assignment_dir, code):
    """Execute Python code in a virtual environment"""
    temp_file_path = None
    try:
        # Create a temporary file for the code
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)
        
        # Get path to Python interpreter in the virtual environment
        if os.name == 'nt':  # Windows
            python_path = os.path.join(assignment_dir, "venv", "Scripts", "python.exe")
        else:  # Unix-like
            python_path = os.path.join(assignment_dir, "venv", "bin", "python")
        
        # Execute the code with the virtual environment's Python
        start_time = time.time()
        result = subprocess.run(
            [python_path, temp_file_path],
            capture_output=True,
            text=True,
            timeout=30  # Timeout after 30 seconds
        )
        execution_time = time.time() - start_time
        
        # Collect output and error
        output = result.stdout
        error = result.stderr
        
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        return {
            "output": output,
            "error": error,
            "execution_time": round(execution_time, 3)
        }
    
    except subprocess.TimeoutExpired:
        # Clean up the temporary file if it exists
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        return {
            "output": "",
            "error": "Execution timed out after 30 seconds",
            "execution_time": 30.0
        }
    
    except Exception as e:
        # Clean up the temporary file if it exists
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        logger.error(f"Python execution error: {str(e)}")
        return {
            "output": "",
            "error": f"Python execution error: {str(e)}",
            "execution_time": 0.0
        }

def execute_javascript_code(assignment_dir, code):
    """Execute JavaScript code using Node.js"""
    temp_file_path = None
    try:
        # Create a temporary file for the code
        with tempfile.NamedTemporaryFile(suffix='.js', mode='w', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(code)
        
        # Execute the code with Node.js
        start_time = time.time()
        
        # Set NODE_PATH to include the assignment's node_modules
        env = os.environ.copy()
        node_modules_path = os.path.join(assignment_dir, "node_modules")
        
        # Handle NODE_PATH differently based on OS
        if os.name == 'nt':  # Windows
            path_separator = ";"
        else:  # Unix-like
            path_separator = ":"
            
        if "NODE_PATH" in env:
            env["NODE_PATH"] = f"{node_modules_path}{path_separator}{env['NODE_PATH']}"
        else:
            env["NODE_PATH"] = node_modules_path
        
        logger.info(f"Setting NODE_PATH to: {env['NODE_PATH']}")
        
        result = subprocess.run(
            ["node", temp_file_path],
            capture_output=True,
            text=True,
            timeout=30,  # Timeout after 30 seconds
            env=env,
            cwd=assignment_dir  # Run in the assignment directory to access local modules
        )
        execution_time = time.time() - start_time
        
        # Collect output and error
        output = result.stdout
        error = result.stderr
        
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        return {
            "output": output,
            "error": error,
            "execution_time": round(execution_time, 3)
        }
    
    except subprocess.TimeoutExpired:
        # Clean up the temporary file if it exists
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        return {
            "output": "",
            "error": "JavaScript execution timed out after 30 seconds",
            "execution_time": 30.0
        }
    
    except Exception as e:
        # Clean up the temporary file if it exists
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        logger.error(f"JavaScript execution error: {str(e)}")
        return {
            "output": "",
            "error": f"JavaScript execution error: {str(e)}",
            "execution_time": 0.0
        }

def execute_cpp_code(assignment_dir, code):
    """Execute C++ code by directly compiling with g++ or another compiler if available"""
    try:
        # Create source file
        src_dir = os.path.join(assignment_dir, "src")
        os.makedirs(src_dir, exist_ok=True)
        
        src_file = os.path.join(src_dir, "main.cpp")
        
        # Write code to the source file
        with open(src_file, "w") as f:
            f.write(code)
        
        # Start timing
        start_time = time.time()
        
        # In Docker, we know g++ is installed
        compiler = "g++"
        output_file = os.path.join(assignment_dir, "program")
        if os.name == 'nt':  # Windows
            output_file += ".exe"
        
        # Compile the code
        compile_result = subprocess.run(
            [compiler, "-std=c++17", src_file, "-o", output_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if compile_result.returncode != 0:
            return {
                "output": "",
                "error": f"Compilation failed:\n{compile_result.stderr}",
                "execution_time": round(time.time() - start_time, 3)
            }
        
        # Run the compiled program
        run_result = subprocess.run(
            [output_file],
            capture_output=True,
            text=True,
            timeout=30,  # Timeout after 30 seconds
            cwd=assignment_dir
        )
        
        execution_time = time.time() - start_time
        
        return {
            "output": run_result.stdout,
            "error": run_result.stderr,
            "execution_time": round(execution_time, 3)
        }
    
    except subprocess.TimeoutExpired:
        return {
            "output": "",
            "error": "C++ execution timed out after 30 seconds",
            "execution_time": 30.0
        }
    
    except Exception as e:
        logger.error(f"C++ execution error: {str(e)}")
        return {
            "output": "",
            "error": f"C++ execution error: {str(e)}",
            "execution_time": 0.0
        }

@app.delete("/delete/assignment/{assignment_name}")
def delete_assignment(assignment_name: str):
    """Delete an assignment environment"""
    assignment_dir = os.path.join(BASE_DIR, assignment_name)
    
    if not os.path.exists(assignment_dir):
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_name}' not found")
    
    try:
        # Remove the assignment directory
        shutil.rmtree(assignment_dir)
        return {"message": f"Assignment '{assignment_name}' deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting assignment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete assignment: {str(e)}")

@app.get("/list/assignments")
def list_assignments():
    """List all available assignments with their languages"""
    try:
        assignments = []
        
        for name in os.listdir(BASE_DIR):
            dir_path = os.path.join(BASE_DIR, name)
            if os.path.isdir(dir_path):
                # Try to get language from metadata
                metadata_path = os.path.join(dir_path, "metadata.json")
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                            assignments.append({
                                "name": name,
                                "language": metadata.get("language", "unknown"),
                                "created_at": metadata.get("created_at", "unknown")
                            })
                    except (json.JSONDecodeError, IOError):
                        assignments.append({
                            "name": name,
                            "language": "unknown",
                            "created_at": "unknown"
                        })
                else:
                    assignments.append({
                        "name": name,
                        "language": "unknown",
                        "created_at": "unknown"
                    })
        
        return {"assignments": assignments}
    
    except Exception as e:
        logger.error(f"Error listing assignments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list assignments: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)