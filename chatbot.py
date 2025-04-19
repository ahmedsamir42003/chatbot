from langchain_google_genai import ChatGoogleGenerativeAI
import requests
import google.generativeai as genai
import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import warnings
import json
from pandasql import sqldf
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import fitz  
import io


API_KEY = "AIzaSyBk0R9Ik12JrJeTCfi-VtYKzS8TeC31AfU"
genai.configure(api_key=API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")


# ----------- Device Control Function -----------
def greenhouse_chatbot(prompt):
    structured_prompt = f"""
    تصرف كمساعد للبيت الزجاجي. حلل الطلب التالي من المستخدم وحدد فقط:

    1. نوع العملية: فتح أو إغلاق (اكتبها بالإنجليزية: open أو close).
    2. اسم الجهاز باللغة الإنجليزية (اختر من: Air Cooler, Heat Lamp, Fluorescent Lamp).
    
    - إذا طلب المستخدم تشغيل أو إيقاف "مصباح" بدون تحديد نوعه (فلوريسنت أو تنجستين)، فاكتب فقط: lamp.
    - تجاهل أي طلبات غير مرتبطة بالأجهزة المذكورة.
    - لا تشرح، فقط أعطِ الجواب بهذا الشكل:
    
    # (open|close) (Air Cooler|Heat Lamp|Fluorescent Lamp)

    طلب المستخدم: {prompt}
    """
    
    response = gemini_model.generate_content(structured_prompt)
    return response.text.strip()

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)  # This expects a file path string
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# Correct way - pass the file path directly to extract_text_from_pdf
pdf_file_path = "document.pdf"  
pdf_text = extract_text_from_pdf(pdf_file_path)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100
)

chunks = text_splitter.split_text(pdf_text)

instruction = """
أنت مساعد ذكي وظيفتك فقط الإجابة على الأسئلة بناءً على محتوى ملف PDF سأقدمه لك.
يجب أن تستخرج المعلومات من هذا الملف فقط، سواء كانت الأسئلة بالعربية أو بالإنجليزية.
إذا تم سؤالك عن أي شيء غير موجود في الملف أو لا يوجد له علاقة بمحتوى الملف،
اعتذر بلباقة وأخبر المستخدم:
"عذرًا، هذا السؤال خارج نطاق المعلومات المتاحة في الملف المقدم، ولا يمكنني الإجابة عليه."
من فضلك كن دقيقًا، مختصرًا، وواضحًا في إجاباتك، ولا تخمّن أبدًا.
"""

def project_info(question: str):  # Changed input_text to question to match usage
    full_prompt = f"{instruction}\n\nمحتوى الملف:\n{chunks[:5]}\n\nالسؤال: {question}"
    response = gemini_model.generate_content([full_prompt])
    return response.text.strip()





# load data

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("project-muthmir11-5bbd46dc5e91.json", scope)
client = gspread.authorize(creds)

sheets_list = client.list_spreadsheet_files()
sheets = {sheet["name"]: f"https://docs.google.com/spreadsheets/d/{sheet['id']}/edit" for sheet in sheets_list}
sheets


try:
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1TwZoi8ehhCq1GNWm1YeTuIzMLpdTy6pnwnafJVJd604/edit").sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    print("❌ حدث خطأ في تحميل البيانات:", e)
    df = pd.DataFrame() 
    
def fix_timestamp_column(df):
    def parse_date(x):
        try:
            return pd.to_datetime(x, dayfirst=False)  # يحاول أولاً بصيغة شهر/يوم/سنة
        except:
            return pd.to_datetime(x, dayfirst=True)   # إذا فشل، يجرب يوم/شهر/سنة

    df["Timestamp"] = df["Timestamp"].apply(parse_date)
    return df

df = fix_timestamp_column(df)



# ----------- analyses Function -----------


# System prompt for greenhouse sensor data analysis
system_prompt = f"""You are an assistant designed to answer questions about greenhouse sensor data stored in a Pandas DataFrame in Arabic.
**Instructions:**
1. **DataFrame Structure:** The DataFrame contains sensor readings. Each column represents a different sensor reading.
2. **User Query:** The user will provide a question related to the sensor data.
3. **Answer Generation:**
   * Analyze the Pandas DataFrame to extract the relevant information to answer the user's query.
   * Provide the answer in Arabic.
4. **Ignore Unrelated Questions.**

Here is the columns of Sensor data explained of the pandas data frame:
Timestamp: time that data generated, the date formatted mm/dd/yyyy in the first 11 rows and formatted dd/mm/yyyy in the remaining rows followed by the time formatted h:m:s PM/AM.
time_ac: time Air conditioning operates in that hour measured by milliseconds (make sure to convert that to hours/minutes when responding).
temperature_api: temperature from the API.
temperature_external: temperature reading out of the greenhouse.
temperature_internal: temperature reading inside of the greenhouse.
humidity_api: humidity from the API.
humidity_external: humidity reading out of the greenhouse.
humidity_internal: humidity reading inside of the greenhouse.
moisture_1: the soil moisture for the first soil.
moisture_2: the soil moisture for the second soil.
light_outer: light reading out of the greenhouse measured by ldr.
light_inner: light reading inside of the greenhouse measured by ldr.
time_heat_lamp: heat lamp operates in milliseconds (make sure to convert that to hours/minutes when responding).
time_lamp: light lamp operates in milliseconds (make sure to convert that to hours/minutes when responding).
time_pump_1: the normalized seconds that pump operates on first soil (1 represents minutes).
time_pump_2: the normalized seconds that pump operates on second soil (1 represents minutes).
Consider that in row 1032, 1033 the time_pump_1 and time_pump_2 represent in seconds.
irrigation_count_1: how many irrigations done in that hour for the first soil.
irrigation_count_2: how many irrigations done in that hour for the second soil.
The IOT system uploads a new row every hour, so each row represents an hour.
If the user asks about aggregated data, perform calculations and answer.
the defult answer for humidity and temperature is based on the internal column unless the user request other 
Dataframe: {df}
"""
# Load data
chat = gemini_model.start_chat(history=[])
chat.send_message(system_prompt) 
# chat = gemini_model.start_chat(history=[])
# response = chat.send_message(structured_prompt)
# Analysis function
def analyze_sensor_data(prompt):
    """Send user query to the existing chat session and return the response."""
    response = chat.send_message(prompt)
    return response.text     # or return response.text.strip()?????


def leader(prompt):
    structured_prompt = f"""
    أنت نموذج تصنيف للأسئلة التي تُطرح على نظام بيت زراعي ذكي.
    مهمتك فقط أن ترد بإحدى الأرقام التالية:
    1 → إذا كان السؤال يطلب معلومات عامة عن المشروع أو الفريق أو الأمراض أو أي شيء غير تحليلي أو تنفيذي.
    2 → إذا كان السؤال يتعلق بتحليل إحصائي لبيانات أجهزة الاستشعار (مثل درجة الحرارة، الرطوبة، رطوبة التربة، شدة الضوء).
    3 → إذا كان السؤال يطلب التحكم في أجهزة معينة في البيت الزجاجي (مثل المكيف، المضخة، الضوء، المدفأة).
    
    يجب أن ترد فقط بالرقم المناسب (1 أو 2 أو 3) بدون أي شرح.
   {prompt}
    """     
    response = gemini_model.generate_content(structured_prompt)
    return response.text.strip()



app = Flask(__name__)

@app.route("/chat", methods=["POST","GET"])
def chat():
    data = request.json
    user_input = data.get("user_input")
    response = leader(user_input)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
