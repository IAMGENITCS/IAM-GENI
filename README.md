**Create a new folder --IAM Agents-- in your system.**

---
**Add these in your .gitignore file:**
```.gitignore
*.env
venv/
__pycache__/
```
---
Open the folder in VS Code(or any other IDE/editor).

**In VS Code create and activate a Virtual Environment**

1. Open the terminal
   
2. command to create virtual environment:
```bash
python -m venv venv
```

 _this will create a folder named "venv"._


3. command to activate virtual environment:

```bash
venv/Scripts/activate
```

_Note: always avtivate the virtual environment before installing any libraries or modules, or before running the code._

---
**Install required libraries**

- command to install libraries:
```bash
pip install -r requirements.txt
```
---
