from flask import Flask, request, jsonify
import google.generativeai as genai

API_KEY = "AIzaSyBk0R9Ik12JrJeTCfi-VtYKzS8TeC31AfU"
genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-pro")

def greenhouse_chatbot(prompt):
    structured_prompt = f"""
    Act as a greenhouse assistant. Respond in Arabic with structured answers only in this format:
    'حسنًا، سأقوم بـ "{{action}}" جهاز "{{device}}"'.
    The available devices are:
    - مصباح فلوريسنت للإضاءة
    - مصباح تنجستين للتدفئة
    - المضخة للري
    - مكيف الهواء للتبريد
    Actions can only be: فتح (open) or إغلاق (close).
    If a request is ambiguous, ask which specific device. Ignore unrelated questions.
    User request: {prompt}
    """
    response = model.generate_content(structured_prompt)
    return response.text

app = Flask(__name__)

@app.route("/chat", methods=["POST","GET"])
def chat():
    data = request.get_json()
    user_input = data.get("user_input")
    response = greenhouse_chatbot(user_input)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

