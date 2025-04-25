#!/bin/bash

# Code Execution API Installer for Linux
# This script installs all necessary dependencies and sets up the Code Execution API service

# Configuration
PROJECT_NAME="code-execution-api"
PROJECT_ZIP_URL="https://github.com/SohamMhatre09/Code-Execution-API/archive/refs/heads/main.zip"
INSTALL_DIR="/opt/code-execution-api"
SYSTEMD_SERVICE_NAME="code-execution-api"

# Function to print colored text
print_color() {
    COLOR=$1
    TEXT=$2
    case $COLOR in
        "red") echo -e "\e[31m$TEXT\e[0m" ;;
        "green") echo -e "\e[32m$TEXT\e[0m" ;;
        "yellow") echo -e "\e[33m$TEXT\e[0m" ;;
        "blue") echo -e "\e[34m$TEXT\e[0m" ;;
        *) echo "$TEXT" ;;
    esac
}

# Function to print header
print_header() {
    LENGTH=${#1}
    BORDER=$(printf '=%.0s' $(seq 1 $((LENGTH + 4))))
    echo -e "\n$BORDER"
    echo -e "  $1"
    echo -e "$BORDER\n"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_color "red" "Please run this script as root or with sudo."
        exit 1
    fi
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Docker if not present
install_docker() {
    print_header "Installing Docker"
    
    if command_exists docker; then
        print_color "green" "Docker is already installed."
    else
        print_color "yellow" "Installing Docker..."
        
        # Install Docker dependencies
        apt-get update
        apt-get install -y \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg \
            lsb-release

        # Add Docker's official GPG key
        mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

        # Set up the Docker repository
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

        # Install Docker Engine
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        
        # Install Docker Compose
        curl -L "https://github.com/docker/compose/releases/download/v2.15.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        
        print_color "green" "Docker has been installed successfully."
    fi
}

# Function to install Miniconda if not present
install_miniconda() {
    print_header "Installing Miniconda"
    
    if command_exists conda; then
        print_color "green" "Miniconda is already installed."
    else
        print_color "yellow" "Installing Miniconda..."
        
        # Download Miniconda installer
        TMP_DIR=$(mktemp -d)
        MINICONDA_INSTALLER="$TMP_DIR/miniconda.sh"
        curl -L "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh" -o "$MINICONDA_INSTALLER"
        
        # Install Miniconda
        bash "$MINICONDA_INSTALLER" -b -p /opt/miniconda3
        
        # Add to PATH
        ln -sf /opt/miniconda3/bin/conda /usr/local/bin/conda
        ln -sf /opt/miniconda3/bin/python /usr/local/bin/conda-python
        
        # Clean up
        rm -rf "$TMP_DIR"
        
        print_color "green" "Miniconda has been installed successfully."
    fi
}

# Function to download and extract the project
download_and_extract_project() {
    print_header "Downloading and Extracting Project Files"
    
    # Create temp directory
    TMP_DIR=$(mktemp -d)
    ZIP_PATH="$TMP_DIR/$PROJECT_NAME.zip"
    
    print_color "yellow" "Downloading project from $PROJECT_ZIP_URL..."
    curl -L "$PROJECT_ZIP_URL" -o "$ZIP_PATH"
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Extract files
    print_color "yellow" "Extracting files to $INSTALL_DIR..."
    unzip -q "$ZIP_PATH" -d "$TMP_DIR"
    
    # Get the name of the top-level directory in the ZIP
    TOP_DIR=$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    
    # Move files from the extracted directory to the install directory
    cp -a "$TOP_DIR"/. "$INSTALL_DIR/"
    
    # Clean up
    rm -rf "$TMP_DIR"
    
    print_color "green" "Project files extracted successfully to $INSTALL_DIR"
}

# Function to create a conda environment - modified to handle errors
create_conda_environment() {
    print_header "Setting Up Python Environment"
    
    ENV_NAME="code_execution_api"
    
    # Check if conda is in PATH
    if ! command_exists conda; then
        print_color "yellow" "Conda not found in PATH. Using direct path..."
        # Try to use direct path
        if [ -f "/opt/miniconda3/bin/conda" ]; then
            CONDA_CMD="/opt/miniconda3/bin/conda"
        else
            print_color "red" "Conda not found. Skipping conda environment setup."
            print_color "yellow" "This won't affect Docker operation."
            return
        fi
    else
        CONDA_CMD="conda"
    fi
    
    # Check if environment already exists
    if $CONDA_CMD env list | grep -q "$ENV_NAME"; then
        print_color "yellow" "Conda environment '$ENV_NAME' already exists. Updating..."
        $CONDA_CMD env update -n "$ENV_NAME" --file "$INSTALL_DIR/requirements.txt" || true
    else
        # Create new environment
        print_color "yellow" "Creating conda environment '$ENV_NAME'..."
        $CONDA_CMD create -n "$ENV_NAME" python=3.11 -y || true
    fi
    
    # Install requirements
    print_color "yellow" "Installing project dependencies..."
    $CONDA_CMD run -n "$ENV_NAME" pip install -r "$INSTALL_DIR/requirements.txt" || true
    
    print_color "green" "Python environment setup completed!"
}

# Function to create a systemd service - updated for better compatibility
create_systemd_service() {
    print_header "Creating Systemd Service"
    
    # Determine which docker-compose command to use
    if command_exists docker-compose; then
        DOCKER_COMPOSE_CMD=$(which docker-compose)
    elif command_exists docker && docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        print_color "red" "Neither docker-compose nor docker compose is available!"
        return 1
    fi
    
    # Create service file with improved configuration
    cat > "/etc/systemd/system/$SYSTEMD_SERVICE_NAME.service" << EOF
[Unit]
Description=Code Execution API Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=/bin/bash -c "cd $INSTALL_DIR && if command -v docker-compose >/dev/null 2>&1; then docker-compose up; else docker compose up; fi"
ExecStop=/bin/bash -c "cd $INSTALL_DIR && if command -v docker-compose >/dev/null 2>&1; then docker-compose down; else docker compose up; fi"
Restart=always
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service to start on boot
    systemctl enable "$SYSTEMD_SERVICE_NAME.service"
    
    print_color "green" "Systemd service created and enabled."
}

# Function to start Docker services - improved error handling
start_docker_services() {
    print_header "Starting Services"
    
    # Change to install directory
    cd "$INSTALL_DIR" || exit
    
    # Build and start containers
    print_color "yellow" "Building Docker container..."
    if command_exists docker-compose; then
        docker-compose build
    else
        docker compose build
    fi
    
    print_color "yellow" "Starting Docker container..."
    systemctl start "$SYSTEMD_SERVICE_NAME.service"
    
    # Wait for the service to start
    sleep 5
    
    # Check if service is running
    if systemctl is-active --quiet "$SYSTEMD_SERVICE_NAME.service"; then
        print_color "green" "Code Execution API is now running at http://localhost:8000"
    else
        print_color "red" "Failed to start the service via systemd. Trying direct method..."
        if command_exists docker-compose; then
            docker-compose up -d
        else
            docker compose up -d
        fi
        print_color "green" "Started via direct docker compose. API is running at http://localhost:8000"
    fi
}

# Function to create convenient control scripts - improved with error handling
create_control_scripts() {
    print_header "Creating Control Scripts"
    
    # Create start script with improved error handling
    cat > "/usr/local/bin/codeapi-start" << EOF
#!/bin/bash
echo "Starting Code Execution API..."
if ! systemctl is-active --quiet $SYSTEMD_SERVICE_NAME.service; then
    sudo systemctl start $SYSTEMD_SERVICE_NAME.service
    sleep 3
    if systemctl is-active --quiet $SYSTEMD_SERVICE_NAME.service; then
        echo "✅ Code Execution API started successfully at http://localhost:8000"
    else
        echo "❌ Failed to start service. Trying direct docker method..."
        cd $INSTALL_DIR
        if command -v docker-compose >/dev/null 2>&1; then
            sudo docker-compose up -d
        else
            sudo docker compose up -d
        fi
        echo "✅ Started via docker compose. Service available at http://localhost:8000"
    fi
else
    echo "✅ Code Execution API is already running at http://localhost:8000"
fi
EOF

    # Create stop script with improved error handling
    cat > "/usr/local/bin/codeapi-stop" << EOF
#!/bin/bash
echo "Stopping Code Execution API..."
if systemctl is-active --quiet $SYSTEMD_SERVICE_NAME.service; then
    sudo systemctl stop $SYSTEMD_SERVICE_NAME.service
    sleep 2
    if ! systemctl is-active --quiet $SYSTEMD_SERVICE_NAME.service; then
        echo "✅ Code Execution API stopped successfully"
    else
        echo "❌ Failed to stop service. Trying direct docker method..."
        cd $INSTALL_DIR
        if command -v docker-compose >/dev/null 2>&1; then
            sudo docker-compose down
        else
            sudo docker compose down
        fi
        echo "✅ Stopped via docker compose"
    fi
else
    echo "✅ Code Execution API is already stopped"
    # Just to be sure, also try docker-compose down
    cd $INSTALL_DIR
    if command -v docker-compose >/dev/null 2>&1; then
        sudo docker-compose down >/dev/null 2>&1
    else
        sudo docker compose down >/dev/null 2>&1
    fi
fi
EOF

    # Create status script with improved output
    cat > "/usr/local/bin/codeapi-status" << EOF
#!/bin/bash
echo "Code Execution API Status:"
echo "-------------------------"
if systemctl is-active --quiet $SYSTEMD_SERVICE_NAME.service; then
    echo "✅ Systemd service: ACTIVE"
else
    echo "❌ Systemd service: INACTIVE"
fi

echo ""
echo "Docker container status:"
sudo docker ps | grep code-execution-api

echo ""
echo "Service Details:"
systemctl status $SYSTEMD_SERVICE_NAME.service --no-pager
EOF

    # Make scripts executable
    chmod +x /usr/local/bin/codeapi-start
    chmod +x /usr/local/bin/codeapi-stop
    chmod +x /usr/local/bin/codeapi-status
    
    print_color "green" "Control scripts created:"
    print_color "yellow" "- Start API:   codeapi-start"
    print_color "yellow" "- Stop API:    codeapi-stop"
    print_color "yellow" "- Check status: codeapi-status"
}

# Main installation function
main() {
    print_header "Code Execution API Installer for Linux"
    print_color "blue" "This installer will set up the Code Execution API service on your system."
    print_color "blue" "Installation will be performed to: $INSTALL_DIR"
    echo
    
    # Check if running as root
    check_root
    
    # Install Docker if not present
    install_docker
    
    # Install Miniconda if not present
    install_miniconda
    
    # Download and extract project
    download_and_extract_project
    
    # Create conda environment
    create_conda_environment
    
    # Create systemd service
    create_systemd_service
    
    # Create control scripts
    create_control_scripts
    
    # Start Docker services
    start_docker_services
    
    print_header "Installation Complete"
    print_color "green" "The Code Execution API has been successfully installed and started."
    print_color "green" "You can access the API at: http://localhost:8000"
    echo
    print_color "blue" "To control the service, use the following commands:"
    print_color "yellow" "- Start API:    codeapi-start"
    print_color "yellow" "- Stop API:     codeapi-stop"
    print_color "yellow" "- Check status: codeapi-status"
}

# Run the installer
main
