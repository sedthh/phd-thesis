setx PIPENV_PIPFILE "../Pipfile"
rem Creating virtual environment...
pipenv clean
pipenv install --ignore-pipfile
cls
pipenv run python server/server.py --log_folder="experiments/"
pause