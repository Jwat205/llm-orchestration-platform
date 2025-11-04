#!/usr/bin/env python3
"""
Debug Script for Both Django and FastAPI Services
This script helps set up debugging for both services simultaneously
"""

import subprocess
import sys
import time
import socket
from typing import List

def check_port(host: str, port: int) -> bool:
    """Check if a port is open"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def wait_for_service(host: str, port: int, service_name: str, max_attempts: int = 30) -> bool:
    """Wait for a service to be available"""
    print(f"Waiting for {service_name} on {host}:{port}...")

    for attempt in range(max_attempts):
        if check_port(host, port):
            print(f"✅ {service_name} is ready on {host}:{port}")
            return True

        print(f"⏳ Attempt {attempt + 1}/{max_attempts} - {service_name} not ready yet...")
        time.sleep(2)

    print(f"❌ {service_name} failed to start on {host}:{port}")
    return False

def run_command(command: List[str], description: str) -> bool:
    """Run a command and return success status"""
    print(f"\n🔧 {description}")
    print(f"Running: {' '.join(command)}")

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("✅ Success")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {e}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def main():
    """Main debugging setup function"""
    print("🐛 LLM API Platform - Debug Setup")
    print("=" * 50)

    # Check if Docker Compose is available
    if not run_command(["docker-compose", "--version"], "Checking Docker Compose"):
        print("❌ Docker Compose is not available")
        sys.exit(1)

    # Check if services are running
    print("\n📋 Checking service status...")
    try:
        result = subprocess.run(
            ["docker-compose", "-f", "docker-compose.dev.yml", "ps"],
            capture_output=True,
            text=True,
            check=True
        )
        print("Current service status:")
        print(result.stdout)
    except subprocess.CalledProcessError:
        print("❌ Failed to check service status")

    # Start services if not running
    print("\n🚀 Starting development services...")
    if not run_command(
        ["docker-compose", "-f", "docker-compose.dev.yml", "up", "-d"],
        "Starting services"
    ):
        print("❌ Failed to start services")
        sys.exit(1)

    # Wait for debug ports to be available
    services = [
        ("localhost", 5678, "Django Debug"),
        ("localhost", 5679, "FastAPI Debug"),
        ("localhost", 8000, "Django HTTP"),
        ("localhost", 8001, "FastAPI HTTP"),
    ]

    print("\n🔍 Waiting for debug services...")
    all_ready = True
    for host, port, name in services:
        if not wait_for_service(host, port, name):
            all_ready = False

    if not all_ready:
        print("\n⚠️  Some services are not ready. Check the logs:")
        print("   docker-compose -f docker-compose.dev.yml logs")
        sys.exit(1)

    # Show debug information
    print("\n" + "=" * 50)
    print("🎯 DEBUG SETUP COMPLETE")
    print("=" * 50)

    print("\n📍 Debug Ports Available:")
    print("   Django:  localhost:5678")
    print("   FastAPI: localhost:5679")

    print("\n🌐 HTTP Services:")
    print("   Django:  http://localhost:8000")
    print("   FastAPI: http://localhost:8001")

    print("\n🔧 VSCode Debug Instructions:")
    print("   1. Open VSCode in the project directory")
    print("   2. Set breakpoints in your Python code")
    print("   3. Press F5 or go to Run & Debug")
    print("   4. Select 'Debug Django + FastAPI' configuration")
    print("   5. Both debuggers will attach automatically")

    print("\n📖 Manual Debug Commands:")
    print("   Django:  Attach to localhost:5678")
    print("   FastAPI: Attach to localhost:5679")

    print("\n🔗 Useful URLs:")
    print("   Django Admin: http://localhost:8000/admin/ (admin/admin123)")
    print("   FastAPI Docs: http://localhost:8001/docs")
    print("   Frontend:     http://localhost:3000")

    print("\n📊 View Logs:")
    print("   All services: docker-compose -f docker-compose.dev.yml logs -f")
    print("   Django only:  docker-compose -f docker-compose.dev.yml logs -f django")
    print("   FastAPI only: docker-compose -f docker-compose.dev.yml logs -f fastapi")

    print("\n🛑 Stop Services:")
    print("   docker-compose -f docker-compose.dev.yml down")

    print("\n" + "=" * 50)
    print("🎉 Ready for debugging! Happy coding!")
    print("=" * 50)

if __name__ == "__main__":
    main()