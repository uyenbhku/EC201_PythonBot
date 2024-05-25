#!bin/bash

python -m venv venv
source venv/Scripts/activate
echo 'venv activated' 

pip install -r requirements.txt
echo 'packages installed'

echo 'running the server'
python server.py 
