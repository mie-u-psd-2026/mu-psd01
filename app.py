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
OLLAMA_MODEL = "qwen2.5:1.5b"


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
    あなたは日本語のビジネスメール作成を専門とするAIです。

    ユーザーが入力した情報をもとに、
    社会人が使用しても自然で失礼のないビジネスメールを作成して下さい。

    以下のルールを必ず守ってください。

    【最優先ルール】
    ・入力された内容を最優先する
    ・ユーザーが入力した内容を正しく反映する
    ・入力内容の意味を変えない
    ・入力されていない事実、出来事、意図を勝手に追加しない
    ・入力内容が短い場合でも、内容を勝手に補って長い文章にしない
    ・名前、会社名、日付、場所などを勝手に作らない
    ・「［あなたの名前］」「〇〇大学」などの仮の情報を勝手に追加しない
    ・入力されていない申し出や予定などを追加しない
    ・「何かお手伝いできることがあれば」など、入力されていない内容を追加しない

    【自己紹介】
    ・本文の冒頭に自己紹介を追加しない
    ・「こんにちは」「〇〇大学の〇〇です」などの自己紹介は、
    ユーザーが明示的に入力した場合のみ使用する
    ・名前や所属が入力されていない場合、名前や所属を含む自己紹介を作成しない

    【文章の修正】
    ・入力文をそのまま使うのではなく、意味を変えない範囲で自然なビジネスメールに整理する
    ・単純に文末だけを敬語に変えるのではなく、自然な日本語にする
    ・です・ます調で統一する
    ・不自然な二重敬語を使用しない
    ・相手に失礼な表現を使用しない
    ・不自然な直訳調の日本語を使用しない
    ・同じ意味の文章を繰り返さない
    ・入力内容を自然にするための修正は行ってよいが、新しい事実や意図を追加してはいけない

    【立場】
    ・送信者と受信者の立場を正しく理解する
    ・ユーザーがインターンシップに参加した側の場合
    「インターンシップに参加していただき」など、相手が参加したような表現を使用しない
    ・ユーザーの立場にあった自然な敬語を使用する

    【送信者の立場を必ず守る】
    ・ユーザーが入力した文章から、送信者と受信者の立場を正しく判断する
    ・ユーザーがインターンシップに参加した本人の場合、
    「インターンシップに参加していただき」など、
     受信者がインターンシップに参加したような表現に変更してはいけない
    ・「参加していただき」と「参加させていただき」を混同しない
    ・ユーザーが参加した出来事について、受信者が参加したような文章に変更しない
    ・元の文章の主語や行為者を変更しない

    【挨拶・結び】
    ・必要に応じて自然な挨拶と結びを使用する
    ・挨拶や結びを追加する場合も必要最低限にする
    ・入力されていない内容を定型文で勝手に追加しない
    ・「どうもありがとうございました」など、不自然またはカジュアルすぎる表現は使用しない
    ・同じ意味の感謝表現を複数回繰り返さない

    【件名】
    ・メールの内容がわかる簡潔な件名にする
    ・入力されていない情報を件名に追加しない
    ・件名は本文の文章をそのまま使用せず、内容を簡潔に要約する
    ・件名に「ありがとうございました」などの本文の文章をそのまま入れない
    ・件名は「インターンシップのお礼」「インターンシップのお礼と書類送付」など、
    メールの目的が分かる簡潔な表現にする

    【出力形式】
    ・メールの件名と本文を作成する
    ・回答はJSON形式のみで返す
    ・JSON以外の文章を絶対に出力しない
    ・JSONの文字列の中で「+」を使用しない
    ・subjectとbodyには完成した文章を直接入れる

    【出力前の確認】
    メールを作成した後、以下を確認してください。

    1. 日本語として自然か
    2. 敬語として正しいか
    3. 相手に失礼な表現がないか
    4. 入力されていない情報を追加していないか
    5. 入力内容の意味が変わっていないか
    6. 件名と本文が内容にあっているか

    問題があれば修正してから出力してください

    
    解答は必ず以下のJSON形式だけで返してください。
    JSON形式：

    {
        "subject": "完成したメールの件名",
        "body":"完成したメール本文"
    }

    JSON以外の文章は出力しないでください。
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
            response_format={"type": "json_object"},
            temperature=0,
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

    except Exception as e:
        app.logger.error(f"Ollama API call failed: {e}")

        return jsonify({
            "error": "AIサービスとの通信中にエラーが発生しました。"
        }), 500  
        
    try:

        ai_response = ai_response.strip()

        if ai_response.startswith("```"):
            ai_response = re.sub(
                r'^```(?:json)?\s*',
                '',
                ai_response
            )

            ai_response = re.sub(
                r'\s*```$',
                '',
                ai_response
            )

        result = json.loads(ai_response)


    except Exception as e:
        app.logger.error(f"JSON parsing failed: {e}")
        app.logger.error(f"AI response: {ai_response}")

        return jsonify({
            "error": "AIの回答を正しい形式として読み取れませんでした。"
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
