✅ STEP 1: Install Ollama (For LLaMA)
👉 Download based on OS:

Windows: https://ollama.com/download

After installing, verify:
ollama --version

✅ STEP 2: Download LLaMA 2 7B
ollama pull llama2:7b

Test: ollama run llama2:7b
If you see a prompt like:
>>> 
Type:Hello

✅ STEP 3: Initialize DB & Run
Initialize DB:
# from backend folder
venv\Scripts\activate
python db_init.py

Run Project Finally
python app.py
# opens at http://127.0.0.1:5000
