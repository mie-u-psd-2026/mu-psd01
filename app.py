from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI
import json
import re

app = Flask(__name__)

if app.debug:
    @app.after_request
    def add_header(response):
        if request.endpoint == 'static':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response


client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)
OLLAMA_MODEL = "qwen2.5-coder:0.5b"


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/send_api', methods=['POST'])
def send_api():
    data = request.get_json()

    if not data:
        app.logger.error("Request JSON is missing.")
        return jsonify({
            "error": "リクエストデータがありません。"
        }), 400

    required_fields = [
        "sender",
        "recipient",
        "purpose",
        "content",
        "tone"
    ]
 
    for field in required_fields:
        if field not in data or not str(data[field]).strip():
            app.logger.error(f"Missing field: {field}")
            return jsonify({
                "error": f"{field}が入力されていません。"
                }), 400

    
    sender = str(data["sender"]).strip()
    recipient = str(data["recipient"]).strip()
    purpose = str(data["purpose"]).strip()
    content = str(data["content"]).strip()
    tone = str(data["tone"]).strip()

    system_prompt = """
    あなたは日本語のビジネスメールをAIです。

    ユーザーが入力した情報をもとに、
    社会人が使用しても自然で失礼のないビジネスメールを作成して下さい。

    以下のルールを必ず守ってください。

    ・ユーザーが入力した内容を正しく反映する
    ・入力されていない事実を勝手に追加しない
    ・名前、会社名、日付、場所などを勝手に作らない
    ・送信相手との関係に適した敬語を使用する
    ・読みやすく自然な日本語にする
    ・元の内容を変えない
    ・指定された文章の雰囲気を反映する
    ・メールの件名と本文を作成する
    ・回答はJSON形式のみで返す


    JSON形式：

    {
        "subject": "メールの件名",
        "body":"メール本文"
    }
   """ 

    user_prompt = f"""
以下の情報をもとに、適切なビジネスメールを作成してください。

【あなたの立場】
{sender}

【送信相手】
{recipient}

【メールの目的】
{purpose}

【伝えたい内容】
{content}

【文章の雰囲気】
{tone}
"""


    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=OLLAMA_MODEL,
        )

        if chat_completion.choices and chat_completion.choices[0].message:
            ai_response = chat_completion.choices[0].message.content
        else:
            return jsonify({
                "error": "AIから有効な応答がありませんでした"
            }), 500

        if not ai_response:
            return jsonify({
                "error": "AIから有効な応答がありませんでした"
            }), 500

    try:
        json_match = re.search(
            r'```(?:json)?\s*(\{.*?\})\s*```',
            ai_response,
            re.DOTALL
        )

        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = ai_response.strip()

        result = json.loads(json_text)

    except json.JSONDecodeError:
        app.logger.error(
            f"Invalid JSON response from AI: {ai_response}"
        )

        return jsonify({
            "error": "AIの解答を正しい形式として読み取れませんでした。"
        }), 500

    subject = result.get("subject")
    body = result.get("body")

     if not subject or not body:
        return jsonify({
            "error": "AIから件名または本文を取得できませんでした。"
        }), 500

    return jsonify({
        "messege": "AIによってメールが作成されました。",
        "subject": subject,
        "body": body,
        "processed_text": f"件名：{subject}\n\n{body}"
    })

except Exception as e:
    app.logger.error(f"Ollama API call failed: {e}")
    return jsonify({"error": f"AIサービスとの通信中にエラーが発生しました。"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
