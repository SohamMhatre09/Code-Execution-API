import os
import sys
import subprocess
import shutil
import tempfile
import zipfile
import urllib.request
import ctypes
import winreg
import time
import getpass
from pathlib import Path

# Configuration
PROJECT_NAME = "code-execution-api"
PROJECT_ZIP_URL = "https://github.com/SohamMhatre09/Code-Execution-API/archive/refs/heads/main.zip"
INSTALL_DIR = os.path.join(os.environ["PROGRAMDATA"], "CodeExecutionAPI")
DOCKER_INSTALLER_URL = "https://desktop.docker.com/win/stable/Docker%20Desktop%20Installer.exe"
MINICONDA_INSTALLER_URL = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"

def is_admin():
    """Check if the script is running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def restart_as_admin():
    """Restart the script with administrator privileges"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)

def print_header(message):
    """Print a formatted header message"""
    border = "=" * (len(message) + 4)
    print(f"\n{border}")
    print(f"  {message}")
    print(f"{border}\n")

def download_file(url, destination):
    """Download a file with progress indication"""
    print(f"Downloading from {url}...")
    
    def report_progress(blocknum, blocksize, totalsize):
        readsofar = blocknum * blocksize
        if totalsize > 0:
            percent = readsofar * 100 / totalsize
            progress = int(percent / 2)
            sys.stdout.write(f"\r[{'#' * progress}{' ' * (50-progress)}] {percent:.1f}%")
            if readsofar >= totalsize:
                sys.stdout.write("\n")
        else:
            sys.stdout.write(f"\rRead {readsofar} bytes")
    
    try:
        urllib.request.urlretrieve(url, destination, reporthook=report_progress)
        print(f"Download completed to {destination}")
        return True
    except Exception as e:
        print(f"Error downloading file: {e}")
        return False

def check_docker_installed():
    """Check if Docker Desktop is installed"""
    try:
        # Check Docker Registry Key
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Docker Inc.\\Docker Desktop") as key:
            return True
    except WindowsError:
        return False

def install_docker():
    """Download and install Docker Desktop"""
    print_header("Installing Docker Desktop")
    
    # Download Docker installer
    temp_dir = tempfile.gettempdir()
    docker_installer = os.path.join(temp_dir, "DockerDesktopInstaller.exe")
    
    if download_file(DOCKER_INSTALLER_URL, docker_installer):
        print("Running Docker Desktop installer...")
        # Run the installer silently
        result = subprocess.run([docker_installer, "install", "--quiet"], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Docker Desktop installation completed successfully!")
            return True
        else:
            print(f"Docker Desktop installation failed: {result.stderr}")
            print("Please install Docker Desktop manually from https://www.docker.com/products/docker-desktop")
            input("Press Enter to continue after installing Docker Desktop manually...")
    return False

def check_conda_installed():
    """Check if Miniconda is installed"""
    try:
        result = subprocess.run(["conda", "--version"], 
                               capture_output=True, text=True, shell=True)
        return result.returncode == 0
    except:
        return False

def install_miniconda():
    """Download and install Miniconda"""
    print_header("Installing Miniconda")
    
    # Download Miniconda installer
    temp_dir = tempfile.gettempdir()
    miniconda_installer = os.path.join(temp_dir, "Miniconda3_Installer.exe")
    
    if download_file(MINICONDA_INSTALLER_URL, miniconda_installer):
        print("Running Miniconda installer...")
        # Run the installer silently
        result = subprocess.run([miniconda_installer, "/InstallationType=JustMe", 
                               "/RegisterPython=0", "/S", "/D=%UserProfile%\\Miniconda3"], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Miniconda installation completed successfully!")
            # Add conda to PATH for this session
            os.environ["PATH"] = f"{os.path.join(os.environ['USERPROFILE'], 'Miniconda3')};" + \
                                f"{os.path.join(os.environ['USERPROFILE'], 'Miniconda3', 'Scripts')};" + \
                                os.environ["PATH"]
            return True
        else:
            print(f"Miniconda installation failed: {result.stderr}")
            print("Please install Miniconda manually from https://docs.conda.io/en/latest/miniconda.html")
            input("Press Enter to continue after installing Miniconda manually...")
    return False

def download_and_extract_project():
    """Download and extract the project files"""
    print_header("Downloading and Extracting Project Files")
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "code-execution-api.zip")
    
    # Download project ZIP
    if not download_file(PROJECT_ZIP_URL, zip_path):
        print("Failed to download project files. Aborting installation.")
        return False
    
    # Create installation directory
    os.makedirs(INSTALL_DIR, exist_ok=True)
    
    # Extract files
    print(f"Extracting files to {INSTALL_DIR}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Get the name of the top-level directory in the ZIP
        top_dir = os.path.commonprefix([name for name in zip_ref.namelist() if name.endswith('/')])
        
        # Extract all files
        zip_ref.extractall(temp_dir)
        
        # Move files from the extracted directory to the install directory
        extracted_dir = os.path.join(temp_dir, top_dir)
        for item in os.listdir(extracted_dir):
            source = os.path.join(extracted_dir, item)
            dest = os.path.join(INSTALL_DIR, item)
            
            # Remove destination if it exists
            if os.path.exists(dest):
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                else:
                    os.remove(dest)
            
            # Move item to destination
            shutil.move(source, dest)
    
    # Clean up
    shutil.rmtree(temp_dir)
    print("Project files extracted successfully!")
    return True

def create_conda_environment():
    """Create a conda environment for the project"""
    print_header("Setting Up Python Environment")
    
    env_name = "code_execution_api"
    
    # Check if environment already exists
    result = subprocess.run(["conda", "env", "list"], capture_output=True, text=True, shell=True)
    if env_name in result.stdout:
        print(f"Conda environment '{env_name}' already exists. Updating...")
        subprocess.run(["conda", "env", "update", "-n", env_name, "--file", 
                       os.path.join(INSTALL_DIR, "requirements.txt")], shell=True)
    else:
        # Create new environment
        print(f"Creating conda environment '{env_name}'...")
        subprocess.run(["conda", "create", "-n", env_name, "python=3.11", "-y"], shell=True)
    
    # Install requirements
    print("Installing project dependencies...")
    subprocess.run(["conda", "run", "-n", env_name, "pip", "install", "-r", 
                   os.path.join(INSTALL_DIR, "requirements.txt")], shell=True)
    
    print("Python environment setup completed successfully!")
    return True

def create_startup_scripts():
    """Create batch scripts to start and stop the service"""
    print_header("Creating Startup Scripts")
    
    # Start script
    start_script = os.path.join(INSTALL_DIR, "start_api.bat")
    with open(start_script, "w") as f:
        f.write("@echo off\n")
        f.write("echo Starting Code Execution API...\n")
        f.write(f"cd /d {INSTALL_DIR}\n")
        f.write("docker-compose up -d\n")
        f.write("echo API is running at http://localhost:8000\n")
        f.write("start http://localhost:8000\n")
        f.write("pause\n")
    
    # Stop script
    stop_script = os.path.join(INSTALL_DIR, "stop_api.bat")
    with open(stop_script, "w") as f:
        f.write("@echo off\n")
        f.write("echo Stopping Code Execution API...\n")
        f.write(f"cd /d {INSTALL_DIR}\n")
        f.write("docker-compose down\n")
        f.write("echo API has been stopped.\n")
        f.write("pause\n")
    
    # Create desktop shortcut
    desktop_path = os.path.join(os.environ["USERPROFILE"], "Desktop")
    shortcut_path = os.path.join(desktop_path, "Code Execution API.lnk")
    
    vbs_script = os.path.join(tempfile.gettempdir(), "create_shortcut.vbs")
    with open(vbs_script, "w") as f:
        f.write(f'Set oWS = WScript.CreateObject("WScript.Shell")\n')
        f.write(f'sLinkFile = "{shortcut_path}"\n')
        f.write(f'Set oLink = oWS.CreateShortcut(sLinkFile)\n')
        f.write(f'oLink.TargetPath = "{start_script}"\n')
        f.write(f'oLink.WorkingDirectory = "{INSTALL_DIR}"\n')
        f.write(f'oLink.Description = "Start Code Execution API"\n')
        f.write(f'oLink.Save\n')
    
    subprocess.run(["cscript", "/nologo", vbs_script])
    os.remove(vbs_script)
    
    print(f"Startup scripts created in {INSTALL_DIR}")
    print(f"Desktop shortcut created at {shortcut_path}")
    return True

def start_docker_services():
    """Start the Docker services"""
    print_header("Starting Services")
    
    # Change to install directory
    os.chdir(INSTALL_DIR)
    
    # Build and start containers
    print("Building Docker container...")
    subprocess.run(["docker-compose", "build"], shell=True)
    
    print("Starting Docker container...")
    subprocess.run(["docker-compose", "up", "-d"], shell=True)
    
    print("Code Execution API is now running at http://localhost:8000")
    return True

def main():
    """Main installation function"""
    # Check for admin privileges
    if not is_admin():
        print("This installer requires administrator privileges.")
        print("Restarting with admin rights...")
        restart_as_admin()
    
    print_header("Code Execution API Installer")
    print("This installer will set up the Code Execution API service on your computer.")
    print("Installation will be performed to:", INSTALL_DIR)
    print()
    input("Press Enter to begin installation...")
    
    # Check and install Docker
    if not check_docker_installed():
        print("Docker Desktop is not installed.")
        install_docker()
    else:
        print("Docker Desktop is already installed.")
    
    # Check and install Miniconda
    if not check_conda_installed():
        print("Miniconda is not installed.")
        install_miniconda()
    else:
        print("Miniconda is already installed.")
    
    # Download and extract project
    if not download_and_extract_project():
        print("Failed to download and extract project files. Aborting installation.")
        input("Press Enter to exit...")
        return
    
    # Create conda environment
    create_conda_environment()
    
    # Create startup scripts
    create_startup_scripts()
    
    # Start Docker services
    start_docker_services()
    
    print_header("Installation Complete")
    print("The Code Execution API has been successfully installed and started.")
    print("You can access the API at: http://localhost:8000")
    print("To start or stop the service, use the desktop shortcut or scripts in:", INSTALL_DIR)
    
    # Open in browser
    open_browser = input("Would you like to open the API in your browser now? (y/n): ").lower()
    if open_browser == 'y':
        subprocess.run(["start", "http://localhost:8000"], shell=True)
    
    input("Press Enter to exit the installer...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred during installation: {e}")
        input("Press Enter to exit...")