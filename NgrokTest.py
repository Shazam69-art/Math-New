from flask import Flask, render_template_string, request, jsonify, Response
import openai
import re
import base64
import os
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MODEL = "gpt-4o"
PORT = 5002
app = Flask(__name__)
SYSTEM_PROMPT = """You are a PhD-Level Math Teacher analyzing student solutions with **zero tolerance for errors or omissions**.
**STRICT RULES (MANDATORY):**
1. **READ ALL QUESTION FILES COMPLETELY AND DO NOT MODIFY THEM** – Extract **EVERY** question and subpart (e.g., 1(i), 1(ii), 2(a), etc.), even if the student did not attempt them.
2. **LIST ALL QUESTIONS FIRST** – Before analyzing, list **every question** from the question files, including those not attempted by the student.
3. **USE EXACT QUESTION NUMBERS** from the files (e.g., "Question 1(i)", "Question 3(ii)").
4. **FOR UNATTTEMPTED QUESTIONS**, explicitly state: "**Not attempted by student**".
5. **COPY STUDENT'S WORK STEP BY STEP AND DO NOT ADD ANYTHING EXTRA** – For attempted questions, do **NOT** rewrite, paraphrase, or "improve" their steps. Preserve **all** notation, even if incorrect.
6. **ALL MATH IN LaTeX**: $x$, $\\tan u$, $\\int$, $\\frac{1}{2}$, $C_1$, etc.
---
### **ERROR ANALYSIS FORMAT (ULTRA-SHORT, MATHEMATICAL ONLY)**
- **Incorrect substitution**: Used $u^2$, must be $y$.
- **Sign error**: Wrote $-\\cos u$, should be $+\\cos u$.
- **Missing term**: Forgot $du$ in integral.
- **Wrong identity**: Used $\\sin u = t$, should be $\\cos u = t$.
- **Derivative mistake**: Got $2x$, correct is $x^2$.
- **Logic flaw**: Assumed $f(x)$ is continuous without justification.
**IF CORRECT**: "✓ Correct" (nothing else).
**IF NOT ATTEMPTED**: "**Not attempted by student**"
---
### **OUTPUT FORMAT (NO DEVIATION)**
## **List of All Questions**
- Question 1(i)
- Question 1(ii)
- Question 2(a)
- ...
## **Question [EXACT NUMBER FROM FILE]**
**Full Question**: [Copy **exactly** as written, with LaTeX for math.]
### **Student's Solution – Exact Copy**
**Status**: Attempted / Not attempted by student
**Step 1**: [Verbatim from student, **no changes**.]
**Step 2**: [Verbatim from student, **no changes**.]
...
### **Error Analysis**
**Step X**: [1-line error, e.g., "Incorrect limit: wrote $\\lim_{x \\to 0} \\sin x = 0$, missing $+1$."]
**OR**
**✓ Correct**
**OR**
**Not attempted by student**
### **Corrected Solution (STEP-BY-STEP, NO SKIPPING)**
1. [Your **first** step, with justification.]
2. [Your **second** step, with justification.]
...
**Final Answer**: $\\boxed{...}$
---
### **NON-NEGOTIABLES**
- **No skipped questions/subparts** – Analyze **everything**, even if not attempted.
- **No added/removed steps** in student’s work.
- **No vague errors** – Only **math-specific** critiques.
- **No "almost correct"** – Either ✓, a **precise error**, or "**Not attempted by student**".
- **No handwaving** – Justify **every** correction step.
**FAILURE TO FOLLOW = REJECT THE OUTPUT.**"""
HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Math Analysis</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea, #764ba2);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        h1 { color: #667eea; margin-bottom: 10px; font-size: 28px; }
        .upload-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }
        .upload-box {
            border: 2px dashed #667eea;
            padding: 30px;
            text-align: center;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-box:hover { background: #f8f9ff; }
        .upload-box.active { background: #e8f5e9; border-color: #4caf50; }
        input[type="file"] { display: none; }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 8px;
            font-size: 18px;
            cursor: pointer;
            width: 100%;
            font-weight: bold;
            transition: transform 0.2s;
        }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4); }
        .results {
            background: white;
            padding: 30px;
            border-radius: 10px;
            min-height: 400px;
            max-height: 600px;
            overflow-y: auto;
        }
        .status { text-align: center; color: #666; padding: 10px; font-size: 14px; }
        .status.success { color: #4caf50; font-weight: bold; }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            border-left: 4px solid #c62828;
        }
        #output h2 {
            color: #764ba2;
            margin-top: 25px;
            margin-bottom: 15px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 8px;
            font-size: 24px;
        }
        #output h3 {
            color: #667eea;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 18px;
        }
        #output strong {
            color: #764ba2;
            font-weight: 600;
        }
        #output hr {
            margin: 30px 0;
            border: none;
            border-top: 2px solid #e0e0e0;
        }
        #output p {
            margin: 10px 0;
            line-height: 1.6;
        }
        .katex { font-size: 1.1em; }
        .katex-display { margin: 1em 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🎓 Math Analysis GPT</h1>
            <p style="color: #666;">Upload question and answer files for detailed analysis with proper math rendering</p>
            <div class="upload-grid">
                <div class="upload-box" id="qbox">
                    <div style="font-size: 40px">📝</div>
                    <strong>Question File(s)</strong>
                    <p style="font-size: 12px; color: #999; margin-top: 10px">Click to upload (multiple OK)</p>
                    <p id="qname" style="font-size: 12px; color: #666; margin-top: 5px"></p>
                    <input type="file" id="qfile" accept="image/*,.txt,.pdf" multiple>
                </div>
                <div class="upload-box" id="abox">
                    <div style="font-size: 40px">✍️</div>
                    <strong>Answer File(s)</strong>
                    <p style="font-size: 12px; color: #999; margin-top: 10px">Click to upload (multiple OK)</p>
                    <p id="aname" style="font-size: 12px; color: #666; margin-top: 5px"></p>
                    <input type="file" id="afile" accept="image/*,.txt,.pdf" multiple>
                </div>
            </div>
            <button class="btn" id="analyzebtn" disabled>🔍 Start Analysis</button>
        </div>
        <div class="results">
            <h2 style="color: #667eea">📊 Analysis Results</h2>
            <div class="status" id="status">Ready to analyze</div>
            <div id="output"></div>
        </div>
    </div>
    <script>
        var qfiles = [];
        var afiles = [];
        document.getElementById('qbox').onclick = function() {
            document.getElementById('qfile').click();
        };
        document.getElementById('abox').onclick = function() {
            document.getElementById('afile').click();
        };
        document.getElementById('qfile').onchange = function(e) {
            qfiles = Array.from(e.target.files);
            document.getElementById('qbox').classList.add('active');
            var names = qfiles.map(function(f) { return f.name; }).join(', ');
            document.getElementById('qname').textContent = qfiles.length + ' file(s): ' + names;
            checkFiles();
        };
        document.getElementById('afile').onchange = function(e) {
            afiles = Array.from(e.target.files);
            document.getElementById('abox').classList.add('active');
            var names = afiles.map(function(f) { return f.name; }).join(', ');
            document.getElementById('aname').textContent = afiles.length + ' file(s): ' + names;
            checkFiles();
        };
        function checkFiles() {
            if (qfiles.length > 0 && afiles.length > 0) {
                document.getElementById('analyzebtn').disabled = false;
            }
        }
        document.getElementById('analyzebtn').onclick = function() {
            analyze();
        };
        function readFile(file) {
            return new Promise(function(resolve, reject) {
                var reader = new FileReader();
                if (file.type.startsWith('image')) {
                    reader.onload = function(e) {
                        resolve({
                            type: 'image',
                            data: e.target.result.split(',')[1],
                            mime: file.type,
                            name: file.name
                        });
                    };
                    reader.readAsDataURL(file);
                } else {
                    reader.onload = function(e) {
                        resolve({
                            type: 'text',
                            data: e.target.result,
                            name: file.name
                        });
                    };
                    reader.readAsText(file);
                }
                reader.onerror = reject;
            });
        }
        function md2html(text) {
            text = text.replace(/^### (.+)$/gm, '<h3>$1</h3>');
            text = text.replace(/^## (.+)$/gm, '<h2>$1</h2>');
            text = text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
            text = text.replace(/^---$/gm, '<hr>');
            text = text.replace(/\\n/g, '<br>');
            return text;
        }
        function renderMath(element) {
            try {
                renderMathInElement(element, {
                    delimiters: [
                        {left: "$$", right: "$$", display: true},
                        {left: "$", right: "$", display: false},
                        {left: "\\(", right: "\\)", display: false},
                        {left: "\\[", right: "\\]", display: true}
                    ],
                    throwOnError: false,
                    strict: false
                });
            } catch (e) {
                console.log('KaTeX render error:', e);
            }
        }
        async function analyze() {
            if (qfiles.length === 0 || afiles.length === 0) {
                alert('Please upload both question and answer files');
                return;
            }
            var btn = document.getElementById('analyzebtn');
            var output = document.getElementById('output');
            var status = document.getElementById('status');
            btn.disabled = true;
            output.innerHTML = '';
            status.textContent = 'Reading files...';
            status.className = 'status';
            try {
                var qdata = await Promise.all(qfiles.map(function(f) { return readFile(f); }));
                var adata = await Promise.all(afiles.map(function(f) { return readFile(f); }));
                status.textContent = 'Analyzing with AI...';
                var response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ questions: qdata, answers: adata })
                });
                if (!response.ok) throw new Error('Failed: ' + response.status);
                var reader = response.body.getReader();
                var decoder = new TextDecoder();
                var buffer = '';
                var lastRenderTime = Date.now();
                while (true) {
                    var result = await reader.read();
                    if (result.done) break;
                    buffer += decoder.decode(result.value);
                    output.innerHTML = md2html(buffer);
                    var now = Date.now();
                    if (now - lastRenderTime > 200) {
                        renderMath(output);
                        lastRenderTime = now;
                    }
                    output.parentElement.scrollTop = output.parentElement.scrollHeight;
                }
                output.innerHTML = md2html(buffer);
                renderMath(output);
                status.textContent = 'Analysis complete! ✓';
                status.className = 'status success';
            } catch (error) {
                output.innerHTML = '<div class="error"><strong>Error:</strong> ' + error.message + '</div>';
                status.textContent = 'Analysis failed';
                status.className = 'status';
                status.style.color = '#c62828';
            } finally {
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>"""
@app.route('/')
def home():
    return render_template_string(HTML)
@app.route('/check')
def check():
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        client.models.list()
        return jsonify({"status": "ok"})
    except:
        return jsonify({"status": "error"})
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        qdata = data['questions']
        adata = data['answers']
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        content = []
        content.append({"type": "text", "text": "=== QUESTION FILES - LIST ALL QUESTIONS AND SUBPARTS FIRST, THEN ANALYZE EVERYTHING ===\n\n"})
        for i, q in enumerate(qdata):
            if q['type'] == 'text':
                content.append({"type": "text", "text": f"Question File {i + 1} ({q['name']}):\n{q['data']}\n\n"})
            else:
                content.append({"type": "image_url", "image_url": {"url": f"data:{q['mime']};base64,{q['data']}"}})
                content.append({"type": "text", "text": f"Question File {i + 1} ({q['name']}) shown above\n\n"})
        content.append({"type": "text", "text": "=== STUDENT ANSWER FILES ===\n\n"})
        for i, a in enumerate(adata):
            if a['type'] == 'text':
                content.append({"type": "text", "text": f"Answer File {i + 1} ({a['name']}):\n{a['data']}\n\n"})
            else:
                content.append({"type": "image_url", "image_url": {"url": f"data:{a['mime']};base64,{a['data']}"}})
                content.append({"type": "text", "text": f"Answer File {i + 1} ({a['name']}) shown above\n\n"})
        content.append(
            {"type": "text", "text": "FIRST, LIST ALL QUESTIONS AND SUBPARTS FROM THE QUESTION FILES. THEN, ANALYZE EACH ONE. DO NOT SKIP ANY QUESTION, EVEN IF NOT ATTEMPTED BY THE STUDENT."}
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ]
        def generate():
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.3,
                max_completion_tokens=7000,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        return Response(generate(), mimetype='text/plain')
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    print("=" * 60)
    print("🎓 MATH ANALYSIS GPT")
    print("=" * 60)
    print(f"🚀 Server: http://localhost:{PORT}")
    print("💡 Using KaTeX for fast math rendering")
    print("=" * 60)
    import webbrowser
    webbrowser.open(f"http://localhost:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
