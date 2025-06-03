#!/bin/bash

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install requirements
pip3 install -r requirements.txt

echo "Setup complete! To activate the virtual environment in the future, run:"
echo "source venv/bin/activate"
