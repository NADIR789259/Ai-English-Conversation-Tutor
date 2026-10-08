#!/bin/bash
echo "=========================================="
echo "  AI English Conversation Tutor Setup"
echo "=========================================="
echo

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo

# Start the server
echo "Starting the server..."
python server.py
