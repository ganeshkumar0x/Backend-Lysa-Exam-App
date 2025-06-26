# Create Python virtual environment in `.venv` directory
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install all required Python packages from requirements.txt
pip install -r requirements.txt

# Run
uvicorn app:app --reload
