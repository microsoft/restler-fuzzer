# Setting up the RESTler Engine in Visual Studio Code on windows

## Step 1: Install Visual Studio Code

*  https://code.visualstudio.com/download

## Step 2: Install Python 3.8.2

* https://www.python.org/downloads/windows/

## Step 3: Make sure VSCode points to the right version of python

* In your settings.json file add the path to your virtual environment's python.exe (recommended)
or the Python38 python.exe:
  * "python.pythonPath": [path to your virtual environment's python.exe]
  * "python.pythonPath": "C:\Python38\python.exe"

## Step 4: Make this version of python your default

 Adding the following two paths as the first paths to your windows user environment __PATH__ variable

* C:\Python38\Scripts
* C:\Python38

## Step 5: Create a working directory

* c:/temp/restler

## Step 6: Test your environment:

* Switch to the Debug view
* Select and launch __Python: restler.py -h__
* RESTler should start in debug mode and stop at the first statement
* Continue debugging (F5)
* You should see no errors and the help documentation output in the debug console