setx PIPENV_PIPFILE "../Pipfile"
rem echo Creating virtual environment...
rem pipenv install --ignore-pipfile
cls
pipenv run python server/server.py --log_folder="experiments/"
pause